import asyncio
from collections import defaultdict


class PriceStore:
    def __init__(self):
        self.data = defaultdict(dict)
        self.lock = asyncio.Lock()

    async def update(self, exchange, symbol, price):
        async with self.lock:
            self.data[symbol][exchange] = price

    async def get(self, symbol):
        async with self.lock:
            return dict(self.data[symbol])
