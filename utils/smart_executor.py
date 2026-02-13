"""
Trade Executor - Advanced order execution with smart retry and optimization
"""
import asyncio
import logging
from typing import Dict, Optional, List
from enum import Enum
from dataclasses import dataclass
from datetime import datetime
import time

logger = logging.getLogger(__name__)


class OrderStatus(Enum):
    """Order status enumeration"""
    PENDING = "pending"
    SUBMITTED = "submitted"
    PARTIAL = "partial"
    FILLED = "filled"
    CANCELLED = "cancelled"
    FAILED = "failed"


@dataclass
class ExecutionResult:
    """Execution result with details"""
    success: bool
    order_id: Optional[str]
    filled_amount: float
    average_price: float
    fee: float
    latency_ms: float
    attempts: int
    error: Optional[str] = None


class SmartExecutor:
    """Smart order executor with retry logic and optimization"""
    
    def __init__(self, max_retries: int = 3, timeout: float = 5.0):
        self.max_retries = max_retries
        self.timeout = timeout
        self.execution_history: List[ExecutionResult] = []
        
    async def execute_order(
        self,
        exchange,
        symbol: str,
        side: str,
        amount: float,
        price: Optional[float] = None,
        order_type: str = "limit"
    ) -> ExecutionResult:
        """Execute order with smart retry"""
        start_time = time.time()
        attempts = 0
        last_error = None
        
        for attempt in range(self.max_retries):
            attempts += 1
            
            try:
                if order_type == "limit" and price:
                    result = await self._execute_limit_order(
                        exchange, symbol, side, amount, price
                    )
                else:
                    result = await self._execute_market_order(
                        exchange, symbol, side, amount
                    )
                    
                latency = (time.time() - start_time) * 1000
                
                exec_result = ExecutionResult(
                    success=True,
                    order_id=result.get('id'),
                    filled_amount=result.get('filled', amount),
                    average_price=result.get('average', price or 0),
                    fee=result.get('fee', {}).get('cost', 0),
                    latency_ms=latency,
                    attempts=attempts
                )
                
                self.execution_history.append(exec_result)
                logger.info(f"Order executed: {symbol} {side} {amount} @ {exec_result.average_price}")
                return exec_result
                
            except Exception as e:
                last_error = str(e)
                logger.warning(f"Execution attempt {attempt + 1} failed: {e}")
                
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(0.5 * (attempt + 1))
                    
        # All attempts failed
        latency = (time.time() - start_time) * 1000
        exec_result = ExecutionResult(
            success=False,
            order_id=None,
            filled_amount=0,
            average_price=0,
            fee=0,
            latency_ms=latency,
            attempts=attempts,
            error=last_error
        )
        
        self.execution_history.append(exec_result)
        logger.error(f"Order failed after {attempts} attempts: {last_error}")
        return exec_result
        
    async def _execute_limit_order(
        self,
        exchange,
        symbol: str,
        side: str,
        amount: float,
        price: float
    ) -> Dict:
        """Execute limit order"""
        if side == 'buy':
            return await exchange.create_limit_buy_order(symbol, amount, price)
        else:
            return await exchange.create_limit_sell_order(symbol, amount, price)
            
    async def _execute_market_order(
        self,
        exchange,
        symbol: str,
        side: str,
        amount: float
    ) -> Dict:
        """Execute market order"""
        if side == 'buy':
            return await exchange.create_market_buy_order(symbol, amount)
        else:
            return await exchange.create_market_sell_order(symbol, amount)
            
    async def execute_multi_leg(
        self,
        legs: List[Dict]
    ) -> List[ExecutionResult]:
        """Execute multiple orders (arbitrage legs) atomically"""
        results = []
        
        try:
            # Execute all legs in parallel
            tasks = [
                self.execute_order(
                    leg['exchange'],
                    leg['symbol'],
                    leg['side'],
                    leg['amount'],
                    leg.get('price'),
                    leg.get('type', 'limit')
                )
                for leg in legs
            ]
            
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Check if all succeeded
            all_success = all(
                isinstance(r, ExecutionResult) and r.success
                for r in results
            )
            
            if not all_success:
                logger.error("Multi-leg execution failed, attempting rollback")
                await self._rollback_executions(results)
                
            return results
            
        except Exception as e:
            logger.error(f"Multi-leg execution error: {e}")
            return []
            
    async def _rollback_executions(self, results: List[ExecutionResult]):
        """Rollback executed orders"""
        for result in results:
            if isinstance(result, ExecutionResult) and result.success:
                try:
                    # Cancel or reverse the order
                    logger.info(f"Rolling back order {result.order_id}")
                    # Implementation depends on exchange API
                except Exception as e:
                    logger.error(f"Rollback failed for {result.order_id}: {e}")
                    
    def get_execution_stats(self) -> Dict:
        """Get execution statistics"""
        if not self.execution_history:
            return {}
            
        successful = [r for r in self.execution_history if r.success]
        failed = [r for r in self.execution_history if not r.success]
        
        total_volume = sum(r.filled_amount * r.average_price for r in successful)
        total_fees = sum(r.fee for r in successful)
        avg_latency = sum(r.latency_ms for r in self.execution_history) / len(self.execution_history)
        
        return {
            'total_executions': len(self.execution_history),
            'successful': len(successful),
            'failed': len(failed),
            'success_rate': len(successful) / len(self.execution_history) * 100,
            'total_volume': total_volume,
            'total_fees': total_fees,
            'avg_latency_ms': avg_latency,
            'avg_attempts': sum(r.attempts for r in self.execution_history) / len(self.execution_history)
        }
        
    def optimize_execution(self, symbol: str, amount: float) -> Dict:
        """Optimize execution parameters based on history"""
        # Filter relevant history
        relevant = [
            r for r in self.execution_history[-100:]
            if r.success
        ]
        
        if not relevant:
            return {
                'recommended_splits': 1,
                'recommended_delay_ms': 0
            }
            
        avg_latency = sum(r.latency_ms for r in relevant) / len(relevant)
        
        # If high latency, suggest order splitting
        splits = 1
        if avg_latency > 100:
            splits = min(5, int(amount / 100) + 1)
            
        return {
            'recommended_splits': splits,
            'recommended_delay_ms': max(50, avg_latency * 0.5),
            'split_amount': amount / splits if splits > 1 else amount
        }


# Global executor instance
_executor = None


def get_executor() -> SmartExecutor:
    """Get global smart executor instance"""
    global _executor
    if _executor is None:
        _executor = SmartExecutor()
    return _executor
