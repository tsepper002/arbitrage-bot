"""Ultra-optimized arbitrage engine with parallel scanning."""
import asyncio
import logging
from typing import List, Dict
from concurrent.futures import ThreadPoolExecutor

logger = logging.getLogger(__name__)

class ArbitrageEngineUltra:
    """Ultra-optimized arbitrage engine."""
    
    def __init__(self, price_store, order_executor, max_workers=4):
        self.price_store = price_store
        self.order_executor = order_executor
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
        self.cache = {}
        self.logger = logging.getLogger(__name__)
    
    async def scan_opportunities_parallel(self, symbols: List[str]) -> List[Dict]:
        """Scan opportunities in parallel."""
        loop = asyncio.get_event_loop()
        tasks = [loop.run_in_executor(self.executor, self._scan_symbol, symbol) 
                 for symbol in symbols]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        return [r for r in results if r and not isinstance(r, Exception)]
    
    def _scan_symbol(self, symbol: str) -> Dict:
        """Scan single symbol for opportunities."""
        try:
            prices = self.price_store.get_prices(symbol)
            if not prices or len(prices) < 2:
                return None
            
            # Find best buy and sell
            sorted_prices = sorted(prices.items(), key=lambda x: x[1]['ask'])
            best_buy = sorted_prices[0]
            best_sell = sorted_prices[-1]
            
            spread = (best_sell[1]['bid'] - best_buy[1]['ask']) / best_buy[1]['ask'] * 100
            
            if spread > 0.1:  # 0.1% threshold
                return {
                    'symbol': symbol,
                    'buy_exchange': best_buy[0],
                    'sell_exchange': best_sell[0],
                    'buy_price': best_buy[1]['ask'],
                    'sell_price': best_sell[1]['bid'],
                    'spread': spread
                }
        except Exception as e:
            self.logger.error(f"Error scanning {symbol}: {e}")
        return None
    
    def get_cached_opportunity(self, key: str):
        """Get cached opportunity."""
        return self.cache.get(key)
    
    def cache_opportunity(self, key: str, data: Dict):
        """Cache opportunity."""
        self.cache[key] = data
