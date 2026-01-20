import time
import logging
from decimal import Decimal
from binance import Client, SecurityType

log = logging.getLogger("app.binance")

class BinanceFutures:
    def __init__(self, api_key: str, api_secret: str, base_url: str):
        # Initialize binance-sdk Client with api_key, api_secret and api_host
        self.base_url = base_url.rstrip("/")
        self.client = Client(
            api_key=api_key,
            api_secret=api_secret,
            api_host=self.base_url
        )

    async def _request(self, method: str, path: str, params: dict = None, security_type=SecurityType.TRADE):
        """Internal helper to dispatch requests through binance-sdk."""
        if params is None:
            params = {}
            
        # Construct full URL
        url = f"{self.base_url}{path}"
        log.info(f"Binance Req: {method} {url}")
        
        # binance-sdk methods: client.get, client.post, etc.
        func = getattr(self.client, method.lower())
        return await func(url, security_type=security_type, **params)


    async def market_order(self, symbol: str, side: str, qty: float):
        return await self._request("POST", "/fapi/v1/order", {
            "symbol": symbol,
            "side": side,
            "type": "MARKET",
            "quantity": qty,
        })

    async def limit_reduce_only(self, symbol: str, side: str, qty: float, price: float):
        return await self._request("POST", "/fapi/v1/order", {
            "symbol": symbol,
            "side": side,
            "type": "LIMIT",
            "timeInForce": "GTC",
            "quantity": qty,
            "price": f"{price}",
            "reduceOnly": "true", # Binance expects string "true" for this endpoint
            "workingType": "MARK_PRICE",
        })

    async def stop_market_reduce_only(self, symbol: str, side: str, qty: float, stop_price: float):
        return await self._request("POST", "/fapi/v1/order", {
            "symbol": symbol,
            "side": side,
            "type": "STOP_MARKET",
            "stopPrice": f"{stop_price}",
            "quantity": qty,
            "reduceOnly": "true",
            "workingType": "MARK_PRICE",
        })

    async def futures_account_balance(self):
        return await self._request("GET", "/fapi/v2/balance")

    async def futures_account_info(self):
        return await self._request("GET", "/fapi/v2/account")

    async def positions_risk(self):
        return await self._request("GET", "/fapi/v2/positionRisk")

    async def round_quantity(self, symbol: str, qty: float) -> float:
        """Round quantity down to the stepSize defined for the symbol."""
        # exchangeInfo is NONE security type (public)
        info = await self._request("GET", "/fapi/v1/exchangeInfo", security_type=SecurityType.NONE)
        for s in info.get("symbols", []):
            if s.get("symbol") == symbol:
                for f in s.get("filters", []):
                    if f.get("filterType") == "LOT_SIZE":
                        step = Decimal(str(f.get("stepSize", "1")))
                        qty_dec = Decimal(str(qty))
                        rounded = (qty_dec // step) * step
                        return float(rounded)
        return qty
