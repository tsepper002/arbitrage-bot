import asyncio
from collections import defaultdict

# TODO: LEGACY FILE - This file is deprecated and will be removed in a future PR.
# Use core/price_store.py (PriceStore) as the canonical implementation.
# This file is kept temporarily to avoid breaking existing code.

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
