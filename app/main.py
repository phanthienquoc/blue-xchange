import asyncio
import json
from datetime import datetime, date
from telethon import TelegramClient, events

from app.config import load_settings
from app.logger import setup_logger
from app.parser import parse_signal
from app.binance_client import BinanceFutures
from app.bot_server import build_bot_app

settings = load_settings()
log = setup_logger(settings.LOG_LEVEL)

client = TelegramClient(settings.TG_SESSION, settings.TG_API_ID, settings.TG_API_HASH)

binance = BinanceFutures(
    api_key=settings.BINANCE_API_KEY,
    api_secret=settings.BINANCE_API_SECRET,
    base_url=settings.BINANCE_BASE_URL,
)


def map_symbol(tg_symbol: str) -> str:
    return settings.SYMBOL_MAP.get(tg_symbol, tg_symbol)


def calc_qty(usdt: float, leverage: int, entry_price: float) -> float:
    notional = usdt * leverage
    return notional / entry_price

@client.on(events.NewMessage())
async def forward_all_messages(event):
    """Forward ALL incoming messages as JSON if TG_FORWARD_CHAT_ID is configured"""
    if not settings.TG_FORWARD_CHAT_ID:
        return
    
    text = getattr(event.message, 'message', '')
    try:
        chat = await event.get_chat()
        chat_info = f"{chat.title if hasattr(chat, 'title') else chat.first_name} (ID: {event.chat_id})"
        log.info(f"📩 Message from {chat_info} | Text: {text[:50]}... | Forwarding to {settings.TG_FORWARD_CHAT_ID}")
        
        msg_dict = event.message.to_dict()
        def json_serial(obj):
            if isinstance(obj, (datetime, date)):
                return obj.isoformat()
            if isinstance(obj, bytes):
                return obj.hex()
            return str(obj)

        msg_json = json.dumps(msg_dict, default=json_serial, indent=2)
        
        forward_id = settings.TG_FORWARD_CHAT_ID
        if forward_id.isdigit() or (forward_id.startswith('-') and forward_id[1:].isdigit()):
            forward_id = int(forward_id)
        
        # 1. Native Telegram Forward (preserves media, formatting, etc.)
        try:
            await event.message.forward_to(forward_id)
            log.info(f"➡️ Native forward successful")
        except Exception as e:
            log.error(f"❌ Native forward failed: {e}")

        # 2. JSON Dump (as requested in previous feature)
        if len(msg_json) > 4000:
            from io import BytesIO
            f = BytesIO(msg_json.encode('utf-8'))
            f.name = f"msg_{event.message.id}.json"
            await client.send_file(forward_id, f, caption=f"From {chat_info}")
        else:
            await client.send_message(forward_id, f"**From {chat_info}:**\n```json\n{msg_json}\n```")
        log.info(f"✅ JSON dump completed")
    except Exception as e:
        log.error(f"❌ Failed to forward message: {e}")

async def notify_chats(message: str):
    """Send message to TG_ADMIN_CHAT_ID and TG_ORDER_CHAT_ID"""
    chats_to_notify = []
    if settings.TG_ADMIN_CHAT_ID:
        chats_to_notify.append(settings.TG_ADMIN_CHAT_ID)
    if settings.TG_ORDER_CHAT_ID:
        chats_to_notify.append(settings.TG_ORDER_CHAT_ID)

    for chat_id in chats_to_notify:
        try:
            target_id = chat_id
            if str(target_id).replace('-', '').isdigit():
                target_id = int(target_id)
            await client.send_message(target_id, message)
        except Exception as e:
            log.error(f"Failed to send notification to {chat_id}: {e}")

@client.on(events.NewMessage())
async def on_new_message(event):
    """Process trading signals from configured listen chat for notification and execution"""
    DEFAULT_LISTEN_CHAT_ID = 1685845137

    allowed_chat_ids = set()

    # 1. Configured Listen ID (or default)
    listen_id = getattr(settings, "TG_LISTEN_CHAT_ID", None)
    if listen_id in (None, "", 0, ""):
        listen_id = DEFAULT_LISTEN_CHAT_ID
    
    try:
        listen_id_str = str(listen_id).strip()
        if listen_id_str.replace("-", "").isdigit():
            allowed_chat_ids.add(int(listen_id_str))
    except Exception as e:
        log.error(f"Error parsing listen_id: {e}")

    # 2. Admin ID (always allowed to send signals)
    if settings.TG_ADMIN_CHAT_ID:
        try:
            admin_id_str = str(settings.TG_ADMIN_CHAT_ID).strip()
            if admin_id_str.replace("-", "").isdigit():
                allowed_chat_ids.add(int(admin_id_str))
        except Exception as e:
            log.error(f"Error parsing admin_id: {e}")

    if event.chat_id not in allowed_chat_ids:
        return


    text = event.raw_text.strip()
    if not text:
        return

    # Try to parse as signal first
    sig = parse_signal(text)
    if not sig:
        return

    # If it is a signal, always prepare info
    symbol = 'XAUUSDT'# map_symbol(sig.symbol)
    side = sig.side.upper()
    close_side = "BUY" if side == "SELL" else "SELL"
    
    qty = calc_qty(settings.DEFAULT_USDT_PER_TRADE, settings.DEFAULT_LEVERAGE, sig.entry)
    qty = await binance.round_quantity(symbol, qty)
    qty = float(f"{qty:.3f}")

    # Determine SL price
    sl_price = sig.sl
    if sl_price is None and settings.PLACE_SL_ORDER:
        if side == "BUY":
            sl_price = sig.entry - 10
        else:
            sl_price = sig.entry + 10

    # Determine TP price
    tp_price = None
    if settings.PLACE_TP_ORDERS and sig.tps:
        idx = settings.TP_INDEX - 1
        if 0 <= idx < len(sig.tps):
            tp_price = sig.tps[idx]

    chat = await event.get_chat()
    chat_info = f"{chat.title if hasattr(chat, 'title') else chat.first_name} (ID: {event.chat_id})"
    
    order_info = (
        f"🌟 *Signal Detected*\n"
        f"• From: `{chat_info}`\n"
        f"• Symbol: `{symbol}` ({sig.symbol})\n"
        f"• Side: `{side}`\n"
        f"• Entry: `{sig.entry}`\n"
        f"• SL: `{sl_price if sl_price else 'N/A'}`\n"
        f"• TP: `{tp_price if tp_price else 'N/A'}`"
    )
    
    # Always notify TG_ORDER_CHAT_ID if it's a signal
    # if settings.TG_ORDER_CHAT_ID:
    #     try:
    #         target_id = settings.TG_ORDER_CHAT_ID
    #         if str(target_id).replace('-', '').isdigit():
    #             target_id = int(target_id)
    #         await client.send_message(target_id, order_info)
    #         log.info(f"📢 Signal info sent to {settings.TG_ORDER_CHAT_ID}")
    #     except Exception as e:
    #         log.error(f"Failed to send order info to order chat: {e}")

    log.info(f"🚀 Executing trade for signal from {chat_info}...")
    
    # Notify Admin that execution is starting
    notify_msg = f"⚡ *Executing Trade*\n" + order_info
    await notify_chats(notify_msg)

    if qty <= 0:
        log.error("Invalid qty")
        return

    # entry order
    try:
        r_entry = await binance.market_order(symbol, side, qty)
        await notify_chats(f"✅ *ENTRY OK*\n`{symbol}` {side} qty `{qty}` price `{r_entry.get('avgPrice', sig.entry)}`")
    except Exception as e:
        err_msg = f"❌ *ENTRY FAILED*\n`{symbol}` {side} qty `{qty}` price `\nError: `{e}`"
        log.error(f"Entry order failed: {e}")
        await notify_chats(err_msg)
        return

    # TP
    if tp_price:
        try:
            r_tp = await binance.limit_reduce_only(symbol, close_side, qty, tp_price)
            log.info(f"TP{settings.TP_INDEX} placed @ {tp_price}: {r_tp}")
            await notify_chats(f"🎯 *TP{settings.TP_INDEX} Placed*\nPrice: `{tp_price}`")
        except Exception as e:
            log.error(f"TP{settings.TP_INDEX} failed @ {tp_price}: {e}")
            await notify_chats(f"⚠️ *TP{settings.TP_INDEX} Failed*\nError: `{e}`")

    # SL
    if settings.PLACE_SL_ORDER and sl_price:
        try:
            r_sl = await binance.stop_market_reduce_only(symbol, close_side, qty, sl_price)
            log.info(f"SL placed @ {sl_price}: {r_sl}")
            await notify_chats(f"🛑 *SL Placed*\nPrice: `{sl_price}`")
        except Exception as e:
            log.error(f"SL failed: {e}")
            await notify_chats(f"⚠️ *SL Failed*\nError: `{e}`")

async def run_telethon():
    await client.start()
    me = await client.get_me()
    log.info(f"Telethon signed in as: {me.first_name} (@{me.username})")
    log.info("Listening for signals from ALL joined chats...")
        
    await client.run_until_disconnected()

async def run_bot():
    bot_app = build_bot_app()
    await bot_app.initialize()
    await bot_app.start()
    await bot_app.updater.start_polling()
    await asyncio.Event().wait()

async def main():
    log.info("Starting Telethon + Telegram Bot...")
    
    # Verify Binance connection
    try:
        balance = await binance.futures_account_balance()
        log.info("✅ Binance connection verified.")
        # Attempt to log USDT balance if available
        usdt_balance = next((b for b in balance if b['asset'] == 'USDT'), None)
        if usdt_balance:
            log.info(f"💰 USDT Balance: {usdt_balance['balance']}")
    except Exception as e:
        log.error(f"❌ Binance connection failed: {e}")

    await asyncio.gather(run_telethon(), run_bot())

if __name__ == "__main__":
    asyncio.run(main())
