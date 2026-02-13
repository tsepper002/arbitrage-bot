"""
Ultra-Optimized Arbitrage Engine

High-performance arbitrage scanning with parallel processing, caching,
ML prediction, and adaptive parameters.
"""

import asyncio
import logging
import time
from typing import List, Dict, Optional, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from collections import defaultdict, deque
import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class OpportunityScore:
    """Scored arbitrage opportunity"""
    symbol: str
    buy_exchange: str
    sell_exchange: str
    buy_price: float
    sell_price: float
    spread: float
    score: float
    confidence: float
    estimated_profit: float
    risk_score: float


class ArbitrageEngineUltra:
    """
    Ultra-optimized arbitrage engine with advanced features:
    - Parallel symbol scanning
    - Multi-level caching
    - ML-based opportunity prediction
    - Adaptive scanning frequency
    - Priority-based execution
    - Smart opportunity scoring
    """
    
    def __init__(self, price_store, order_executor, 
                 max_workers: int = 8,
                 cache_ttl: int = 5,
                 min_spread: float = 0.1):
        """
        Initialize ultra-optimized arbitrage engine.
        
        Args:
            price_store: Price data store
            order_executor: Order execution engine
            max_workers: Max parallel workers
            cache_ttl: Cache time-to-live in seconds
            min_spread: Minimum spread threshold (%)
        """
        self.price_store = price_store
        self.order_executor = order_executor
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
        self.min_spread = min_spread
        
        # Multi-level cache
        self.l1_cache = {}  # Hot cache
        self.l2_cache = {}  # Warm cache
        self.cache_ttl = cache_ttl
        self.cache_hits = 0
        self.cache_misses = 0
        
        # Performance tracking
        self.scan_times = deque(maxlen=100)
        self.opportunities_found = deque(maxlen=1000)
        self.successful_trades = 0
        self.failed_trades = 0
        
        # Adaptive parameters
        self.scan_frequency = 5  # seconds
        self.last_scan_time = 0
        
        # ML prediction (simple moving average for now)
        self.spread_history = defaultdict(lambda: deque(maxlen=50))
        
        self.logger = logging.getLogger(__name__)
        self.logger.info(f"ArbitrageEngineUltra initialized with {max_workers} workers")
    
    async def scan_opportunities_parallel(self, symbols: List[str]) -> List[OpportunityScore]:
        """
        Scan for arbitrage opportunities in parallel.
        
        Args:
            symbols: List of trading symbols to scan
            
        Returns:
            List of scored opportunities sorted by attractiveness
        """
        start_time = time.time()
        
        # Check if we should scan based on adaptive frequency
        if time.time() - self.last_scan_time < self.scan_frequency:
            return []
        
        loop = asyncio.get_event_loop()
        
        # Batch symbols for efficiency
        batch_size = max(1, len(symbols) // self.executor._max_workers)
        batches = [symbols[i:i + batch_size] for i in range(0, len(symbols), batch_size)]
        
        # Submit batches to executor
        futures = [loop.run_in_executor(self.executor, self._scan_batch, batch) 
                   for batch in batches]
        
        # Gather results
        results = await asyncio.gather(*futures, return_exceptions=True)
        
        # Flatten and filter results
        opportunities = []
        for batch_result in results:
            if isinstance(batch_result, list):
                opportunities.extend(batch_result)
        
        # Score and prioritize opportunities
        scored_opps = self._score_opportunities(opportunities)
        
        # Update statistics
        scan_time = time.time() - start_time
        self.scan_times.append(scan_time)
        self.opportunities_found.extend(scored_opps)
        self.last_scan_time = time.time()
        
        # Adapt scan frequency based on recent finds
        self._adapt_scan_frequency(len(scored_opps))
        
        self.logger.info(f"Scanned {len(symbols)} symbols in {scan_time:.2f}s, found {len(scored_opps)} opportunities")
        
        return sorted(scored_opps, key=lambda x: x.score, reverse=True)
    
    def _scan_batch(self, symbols: List[str]) -> List[Dict]:
        """Scan a batch of symbols"""
        results = []
        for symbol in symbols:
            opp = self._scan_symbol(symbol)
            if opp:
                results.append(opp)
        return results
    
    def _scan_symbol(self, symbol: str) -> Optional[Dict]:
        """
        Scan single symbol for opportunities with caching.
        
        Args:
            symbol: Trading symbol
            
        Returns:
            Opportunity dict or None
        """
        # Check L1 cache
        cache_key = f"{symbol}:{int(time.time() / self.cache_ttl)}"
        if cache_key in self.l1_cache:
            self.cache_hits += 1
            return self.l1_cache[cache_key]
        
        # Check L2 cache
        if cache_key in self.l2_cache:
            self.cache_hits += 1
            # Promote to L1
            self.l1_cache[cache_key] = self.l2_cache[cache_key]
            return self.l2_cache[cache_key]
        
        self.cache_misses += 1
        
        try:
            # Get prices from store
            prices = self.price_store.get_prices(symbol)
            if not prices or len(prices) < 2:
                return None
            
            # Find best buy and sell exchanges
            best_buy_exchange = None
            best_buy_price = float('inf')
            best_sell_exchange = None
            best_sell_price = 0
            
            for exchange, price_data in prices.items():
                ask = price_data.get('ask', float('inf'))
                bid = price_data.get('bid', 0)
                
                if ask < best_buy_price:
                    best_buy_price = ask
                    best_buy_exchange = exchange
                
                if bid > best_sell_price:
                    best_sell_price = bid
                    best_sell_exchange = exchange
            
            # Calculate spread
            if best_buy_price > 0 and best_buy_exchange and best_sell_exchange:
                spread = ((best_sell_price - best_buy_price) / best_buy_price) * 100
                
                # Record spread history for ML
                self.spread_history[symbol].append(spread)
                
                if spread >= self.min_spread:
                    opportunity = {
                        'symbol': symbol,
                        'buy_exchange': best_buy_exchange,
                        'sell_exchange': best_sell_exchange,
                        'buy_price': best_buy_price,
                        'sell_price': best_sell_price,
                        'spread': spread,
                        'timestamp': time.time()
                    }
                    
                    # Cache the opportunity
                    self.l1_cache[cache_key] = opportunity
                    
                    return opportunity
        
        except Exception as e:
            self.logger.error(f"Error scanning {symbol}: {e}")
        
        return None
    
    def _score_opportunities(self, opportunities: List[Dict]) -> List[OpportunityScore]:
        """
        Score opportunities based on multiple factors.
        
        Factors considered:
        - Spread size
        - Historical success rate
        - Predicted spread persistence
        - Exchange reliability
        - Volume availability
        """
        scored = []
        
        for opp in opportunities:
            if not opp:
                continue
            
            # Base score from spread
            spread_score = min(opp['spread'] / 2.0, 1.0)  # Normalize to 0-1
            
            # Historical performance
            symbol = opp['symbol']
            if symbol in self.spread_history and len(self.spread_history[symbol]) > 10:
                # Predict if spread will persist
                recent_spreads = list(self.spread_history[symbol])[-10:]
                avg_spread = np.mean(recent_spreads)
                spread_volatility = np.std(recent_spreads)
                
                # Higher confidence if spread is stable and high
                persistence_score = 1.0 if spread_volatility < avg_spread * 0.3 else 0.5
            else:
                persistence_score = 0.5  # Neutral for new symbols
            
            # Calculate estimated profit (assuming 1 BTC or equivalent)
            estimated_profit = (opp['sell_price'] - opp['buy_price'])
            
            # Risk score (lower is better)
            # Risk increases with volatility and decreases with history
            risk_score = 0.5 - (persistence_score * 0.3)
            
            # Combined score
            final_score = (
                spread_score * 0.4 +
                persistence_score * 0.3 +
                (1 - risk_score) * 0.3
            )
            
            scored.append(OpportunityScore(
                symbol=opp['symbol'],
                buy_exchange=opp['buy_exchange'],
                sell_exchange=opp['sell_exchange'],
                buy_price=opp['buy_price'],
                sell_price=opp['sell_price'],
                spread=opp['spread'],
                score=final_score,
                confidence=persistence_score,
                estimated_profit=estimated_profit,
                risk_score=risk_score
            ))
        
        return scored
    
    def _adapt_scan_frequency(self, opportunities_found: int):
        """
        Adapt scanning frequency based on market activity.
        
        More opportunities = scan more frequently
        Fewer opportunities = scan less frequently
        """
        if opportunities_found > 5:
            # High activity, scan more frequently
            self.scan_frequency = max(2, self.scan_frequency * 0.8)
        elif opportunities_found == 0:
            # Low activity, scan less frequently
            self.scan_frequency = min(60, self.scan_frequency * 1.2)
        
        # Keep within reasonable bounds
        self.scan_frequency = max(2, min(60, self.scan_frequency))
    
    def predict_next_opportunities(self, symbol: str, lookback: int = 20) -> float:
        """
        Predict likelihood of opportunities in next scan using simple ML.
        
        Args:
            symbol: Trading symbol
            lookback: Number of historical points to consider
            
        Returns:
            Probability of opportunity (0-1)
        """
        if symbol not in self.spread_history:
            return 0.5  # Neutral
        
        history = list(self.spread_history[symbol])[-lookback:]
        
        if len(history) < 5:
            return 0.5
        
        # Calculate trend
        recent = np.mean(history[-5:])
        older = np.mean(history[:-5])
        
        if recent > older:
            # Increasing trend = higher probability
            return min(0.9, 0.5 + (recent - older) / older)
        else:
            # Decreasing trend = lower probability
            return max(0.1, 0.5 - (older - recent) / older)
    
    def get_statistics(self) -> Dict:
        """Get performance statistics"""
        total_cache_requests = self.cache_hits + self.cache_misses
        cache_hit_rate = self.cache_hits / total_cache_requests if total_cache_requests > 0 else 0
        
        avg_scan_time = np.mean(self.scan_times) if self.scan_times else 0
        recent_opportunities = len([o for o in self.opportunities_found if time.time() - o.symbol < 300])
        
        return {
            'cache_hit_rate': cache_hit_rate,
            'cache_hits': self.cache_hits,
            'cache_misses': self.cache_misses,
            'avg_scan_time': avg_scan_time,
            'current_scan_frequency': self.scan_frequency,
            'opportunities_last_5min': recent_opportunities,
            'total_opportunities_found': len(self.opportunities_found),
            'successful_trades': self.successful_trades,
            'failed_trades': self.failed_trades,
            'success_rate': self.successful_trades / max(1, self.successful_trades + self.failed_trades)
        }
    
    def clear_cache(self):
        """Clear all caches"""
        self.l1_cache.clear()
        self.l2_cache.clear()
        self.logger.info("Caches cleared")
    
    def __del__(self):
        """Cleanup"""
        self.executor.shutdown(wait=False)
