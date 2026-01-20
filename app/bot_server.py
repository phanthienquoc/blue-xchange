from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

from app.config import load_settings
from app.logger import setup_logger
from app.binance_client import BinanceFutures

settings = load_settings()
log = setup_logger(settings.LOG_LEVEL)

binance = BinanceFutures(
    api_key=settings.BINANCE_API_KEY,
    api_secret=settings.BINANCE_API_SECRET,
    base_url=settings.BINANCE_BASE_URL,
)

def is_admin(update: Update) -> bool:
    if not update.effective_chat:
        return False
    return str(update.effective_chat.id) == str(settings.TG_ADMIN_CHAT_ID)

async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("✅ Bot is online. Use /balance")

async def balance_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        await update.message.reply_text("❌ Not authorized")
        return
    try:
        balances = await binance.futures_account_balance()
        account = await binance.futures_account_info()
        positions = await binance.positions_risk()
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {e}")
        return
    usdt = next((b for b in balances if b.get("asset") == "USDT"), None)
    total_wallet = account.get("totalWalletBalance")
    total_unrealized = account.get("totalUnrealizedProfit")
    available = account.get("availableBalance")
    active_pos = []
    for p in positions:
        amt = float(p.get("positionAmt", 0))
        if abs(amt) > 0:
            active_pos.append(p)
    msg = []
    msg.append("📊 *Futures Balance*")
    if usdt:
        msg.append(f"- USDT balance: `{usdt.get('balance')}`")
        msg.append(f"- USDT available: `{usdt.get('availableBalance')}`")
    msg.append("")
    msg.append("💼 *Account Summary*")
    msg.append(f"- Wallet: `{total_wallet}`")
    msg.append(f"- Available: `{available}`")
    msg.append(f"- Unrealized PnL: `{total_unrealized}`")
    msg.append("")
    msg.append(f"📌 *Open Positions ({len(active_pos)})*")
    if not active_pos:
        msg.append("- (none)")
    else:
        for p in active_pos[:10]:
            msg.append(
                f"- `{p.get('symbol')}` amt=`{p.get('positionAmt')}` entry=`{p.get('entryPrice')}` pnl=`{p.get('unRealizedProfit')}`"
            )
    await update.message.reply_text("\n".join(msg), parse_mode="Markdown")

def build_bot_app() -> Application:
    app = Application.builder().token(settings.TG_BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start_cmd))
    app.add_handler(CommandHandler("balance", balance_cmd))
    return app
