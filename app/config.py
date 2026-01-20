import os
import json
from typing import Optional
from pydantic import BaseModel

class Settings(BaseModel):
    TG_API_ID: int
    TG_API_HASH: str
    TG_SESSION: str
    TG_LISTEN_CHAT_ID: str

    TG_BOT_TOKEN: str
    TG_ADMIN_CHAT_ID: str
    TG_ORDER_CHAT_ID: Optional[str] = None
    TG_FORWARD_CHAT_ID: Optional[str] = None

    BINANCE_API_KEY: str
    BINANCE_API_SECRET: str
    BINANCE_BASE_URL: str = "https://fapi.binance.com"

    DEFAULT_USDT_PER_TRADE: float = 10.0
    DEFAULT_LEVERAGE: int = 10

    SYMBOL_MAP: dict[str, str] = {}

    PLACE_TP_ORDERS: bool = True
    PLACE_SL_ORDER: bool = True

    TP_INDEX: int = 2

    LOG_LEVEL: str = "INFO"

def load_settings() -> Settings:
    symbol_map_raw = os.getenv("SYMBOL_MAP", "{}")

    return Settings(
        TG_API_ID=int(os.getenv("TG_API_ID", "0")),
        TG_API_HASH=os.getenv("TG_API_HASH", ""),
        TG_SESSION=os.getenv("TG_SESSION", "/data/tg.session"),
        TG_LISTEN_CHAT_ID=os.getenv("TG_LISTEN_CHAT_ID", ""),

        TG_BOT_TOKEN=os.getenv("TG_BOT_TOKEN", ""),
        TG_ADMIN_CHAT_ID=str(os.getenv("TG_ADMIN_CHAT_ID", "")),
        TG_ORDER_CHAT_ID=os.getenv("TG_ORDER_CHAT_ID") or None,
        TG_FORWARD_CHAT_ID=os.getenv("TG_FORWARD_CHAT_ID") or None,

        BINANCE_API_KEY=os.getenv("BINANCE_API_KEY", ""),
        BINANCE_API_SECRET=os.getenv("BINANCE_API_SECRET", ""),
        BINANCE_BASE_URL=os.getenv("BINANCE_BASE_URL", "https://fapi.binance.com"),

        DEFAULT_USDT_PER_TRADE=float(os.getenv("DEFAULT_USDT_PER_TRADE", "10")),
        DEFAULT_LEVERAGE=int(os.getenv("DEFAULT_LEVERAGE", "10")),

        SYMBOL_MAP=json.loads(symbol_map_raw),

        PLACE_TP_ORDERS=os.getenv("PLACE_TP_ORDERS", "true").lower() == "true",
        PLACE_SL_ORDER=os.getenv("PLACE_SL_ORDER", "true").lower() == "true",

        TP_INDEX=int(os.getenv("TP_INDEX", "2")),

        LOG_LEVEL=os.getenv("LOG_LEVEL", "INFO"),
    )
