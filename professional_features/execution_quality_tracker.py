"""
Execution Quality Tracker - Tracks execution quality metrics
Measures slippage, fill rates, and execution performance
"""
import logging
from typing import Dict, List
import time
import numpy as np

logger = logging.getLogger(__name__)

class ExecutionQualityTracker:
    """Tracks and analyzes execution quality"""
    
    def __init__(self):
        self.executions = []
        self.metrics = {}
        logger.info("✅ ExecutionQualityTracker initialized")
    
    def record_execution(self, order_id: str, symbol: str, side: str,
                        requested_price: float, executed_price: float,
                        requested_quantity: float, filled_quantity: float,
                        execution_time_ms: float):
        """Record order execution"""
        try:
            slippage = abs(executed_price - requested_price) / requested_price if requested_price > 0 else 0
            fill_rate = filled_quantity / requested_quantity if requested_quantity > 0 else 0
            
            execution = {
                'order_id': order_id,
                'symbol': symbol,
                'side': side,
                'requested_price': requested_price,
                'executed_price': executed_price,
                'requested_quantity': requested_quantity,
                'filled_quantity': filled_quantity,
                'slippage': slippage,
                'slippage_bps': slippage * 10000,
                'fill_rate': fill_rate,
                'execution_time_ms': execution_time_ms,
                'timestamp': time.time()
            }
            
            self.executions.append(execution)
            
            # Keep recent history
            if len(self.executions) > 1000:
                self.executions = self.executions[-500:]
            
            logger.debug(f"Recorded execution: {symbol} slippage={slippage:.4%}, fill_rate={fill_rate:.2%}")
            
        except Exception as e:
            logger.error(f"Error recording execution: {e}")
    
    def get_metrics(self, symbol: Optional[str] = None, lookback_minutes: int = 60) -> Dict:
        """Get execution quality metrics"""
        try:
            # Filter executions
            cutoff_time = time.time() - (lookback_minutes * 60)
            recent_execs = [
                e for e in self.executions
                if e['timestamp'] >= cutoff_time and (symbol is None or e['symbol'] == symbol)
            ]
            
            if not recent_execs:
                return {
                    'total_executions': 0,
                    'avg_slippage_bps': 0,
                    'avg_fill_rate': 0,
                    'avg_execution_time_ms': 0
                }
            
            # Calculate metrics
            slippages = [e['slippage_bps'] for e in recent_execs]
            fill_rates = [e['fill_rate'] for e in recent_execs]
            exec_times = [e['execution_time_ms'] for e in recent_execs]
            
            metrics = {
                'total_executions': len(recent_execs),
                'avg_slippage_bps': np.mean(slippages),
                'median_slippage_bps': np.median(slippages),
                'max_slippage_bps': np.max(slippages),
                'avg_fill_rate': np.mean(fill_rates),
                'avg_execution_time_ms': np.mean(exec_times),
                'symbol': symbol if symbol else 'all'
            }
            
            self.metrics[symbol if symbol else 'all'] = metrics
            return metrics
            
        except Exception as e:
            logger.error(f"Error calculating metrics: {e}")
            return {}
    
    def get_quality_score(self, symbol: Optional[str] = None) -> float:
        """Get quality score (0-100)"""
        try:
            metrics = self.get_metrics(symbol)
            if not metrics or metrics['total_executions'] == 0:
                return 50.0  # Neutral score
            
            # Score based on slippage and fill rate
            slippage_score = max(0, 100 - metrics['avg_slippage_bps'])
            fill_rate_score = metrics['avg_fill_rate'] * 100
            
            quality_score = (slippage_score + fill_rate_score) / 2
            return min(max(quality_score, 0), 100)
            
        except Exception as e:
            logger.error(f"Error calculating quality score: {e}")
            return 50.0

def get_execution_quality_tracker():
    """Factory function"""
    return ExecutionQualityTracker()
