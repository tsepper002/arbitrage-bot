import aiohttp

class BybitREST(BaseExchange):
    def __init__(self, api_key: str, api_secret: str):
        self.api_key = api_key
        self.api_secret = api_secret
        self.base_url = "https://api.bybit.com"

    async def get_price(self, symbol: str) -> float:
        async with aiohttp.ClientSession() as session:
            url = f"{self.base_url}/v2/public/tickers?symbol={symbol}"
            async with session.get(url) as response:
                data = await response.json()
                return float(data['result'][0]['last_price'])

    async def place_order(self, symbol: str, amount: float, price: float) -> dict:
        # Логика для размещения ордера через REST API Bybit
        pass

    async def connect(self):
        # Этот метод можно не использовать для REST API
        pass
