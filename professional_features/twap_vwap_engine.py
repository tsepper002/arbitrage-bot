"""
TWAP/VWAP Execution Engine
Time-Weighted and Volume-Weighted Average Price execution algorithms
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
import numpy as np

logger = logging.getLogger(__name__)


class AlgoType(Enum):
    """Algorithm types"""
    TWAP = "twap"
    VWAP = "vwap"
    POV = "pov"  # Percentage of Volume
    ADAPTIVE = "adaptive"


@dataclass
class SliceConfig:
    """Configuration for order slicing"""
    total_quantity: float
    duration_seconds: int
    num_slices: int
    algo_type: AlgoType
    participation_rate: float = 0.1  # For POV
    min_slice_size: float = 0.0
    max_slice_size: float = float('inf')


@dataclass
class ExecutionSlice:
    """Individual execution slice"""
    slice_id: int
    quantity: float
    target_time: datetime
    executed_quantity: float = 0.0
    executed_price: float = 0.0
    status: str = "pending"


class TWAPVWAPEngine:
    """
    TWAP/VWAP execution engine for large orders
    Splits large orders into smaller slices to minimize market impact
    """
    
    def __init__(self, exchange_client, market_data):
        self.exchange = exchange_client
        self.market_data = market_data
        self.active_orders: Dict[str, List[ExecutionSlice]] = {}
        self.execution_history: List[Dict] = []
        self.volume_profile: Dict[str, List[float]] = {}
        
    async def execute_twap(
        self,
        symbol: str,
        side: str,
        quantity: float,
        duration_minutes: int,
        num_slices: Optional[int] = None
    ) -> Dict:
        """
        Execute Time-Weighted Average Price order
        
        Args:
            symbol: Trading pair
            side: 'buy' or 'sell'
            quantity: Total quantity to execute
            duration_minutes: Total execution time
            num_slices: Number of slices (default: duration_minutes)
            
        Returns:
            Execution summary
        """
        if num_slices is None:
            num_slices = duration_minutes
            
        slice_quantity = quantity / num_slices
        interval_seconds = (duration_minutes * 60) / num_slices
        
        config = SliceConfig(
            total_quantity=quantity,
            duration_seconds=duration_minutes * 60,
            num_slices=num_slices,
            algo_type=AlgoType.TWAP
        )
        
        slices = self._create_twap_slices(config)
        order_id = f"twap_{symbol}_{datetime.now().timestamp()}"
        self.active_orders[order_id] = slices
        
        logger.info(f"Starting TWAP execution: {quantity} {symbol} over {duration_minutes}min")
        
        results = []
        for i, slice_obj in enumerate(slices):
            # Wait until target time
            wait_time = (slice_obj.target_time - datetime.now()).total_seconds()
            if wait_time > 0:
                await asyncio.sleep(wait_time)
                
            # Execute slice
            try:
                result = await self._execute_slice(symbol, side, slice_obj.quantity)
                slice_obj.executed_quantity = result['filled']
                slice_obj.executed_price = result['price']
                slice_obj.status = "filled"
                results.append(result)
                
                logger.info(f"TWAP slice {i+1}/{num_slices} executed: {result['filled']} @ {result['price']}")
            except Exception as e:
                logger.error(f"TWAP slice {i+1} failed: {e}")
                slice_obj.status = "failed"
                
        return self._create_summary(order_id, slices, results)
        
    async def execute_vwap(
        self,
        symbol: str,
        side: str,
        quantity: float,
        duration_minutes: int
    ) -> Dict:
        """
        Execute Volume-Weighted Average Price order
        Distributes quantity based on historical volume profile
        
        Args:
            symbol: Trading pair
            side: 'buy' or 'sell'
            quantity: Total quantity to execute
            duration_minutes: Total execution time
            
        Returns:
            Execution summary
        """
        # Get volume profile
        volume_profile = await self._get_volume_profile(symbol, duration_minutes)
        
        # Create VWAP slices based on volume distribution
        config = SliceConfig(
            total_quantity=quantity,
            duration_seconds=duration_minutes * 60,
            num_slices=len(volume_profile),
            algo_type=AlgoType.VWAP
        )
        
        slices = self._create_vwap_slices(config, volume_profile)
        order_id = f"vwap_{symbol}_{datetime.now().timestamp()}"
        self.active_orders[order_id] = slices
        
        logger.info(f"Starting VWAP execution: {quantity} {symbol} over {duration_minutes}min")
        
        results = []
        for i, slice_obj in enumerate(slices):
            # Wait until target time
            wait_time = (slice_obj.target_time - datetime.now()).total_seconds()
            if wait_time > 0:
                await asyncio.sleep(wait_time)
                
            # Execute slice
            try:
                result = await self._execute_slice(symbol, side, slice_obj.quantity)
                slice_obj.executed_quantity = result['filled']
                slice_obj.executed_price = result['price']
                slice_obj.status = "filled"
                results.append(result)
                
                logger.info(f"VWAP slice {i+1}/{len(slices)} executed: {result['filled']} @ {result['price']}")
            except Exception as e:
                logger.error(f"VWAP slice {i+1} failed: {e}")
                slice_obj.status = "failed"
                
        return self._create_summary(order_id, slices, results)
        
    async def execute_pov(
        self,
        symbol: str,
        side: str,
        quantity: float,
        participation_rate: float = 0.1,
        duration_minutes: int = 60
    ) -> Dict:
        """
        Execute Percentage of Volume order
        Maintains participation rate relative to market volume
        
        Args:
            symbol: Trading pair
            side: 'buy' or 'sell'
            quantity: Total quantity to execute
            participation_rate: Target % of market volume (0.0-1.0)
            duration_minutes: Maximum execution time
            
        Returns:
            Execution summary
        """
        order_id = f"pov_{symbol}_{datetime.now().timestamp()}"
        start_time = datetime.now()
        end_time = start_time + timedelta(minutes=duration_minutes)
        
        executed_quantity = 0.0
        results = []
        slice_id = 0
        
        logger.info(f"Starting POV execution: {quantity} {symbol} @ {participation_rate*100}% participation")
        
        while executed_quantity < quantity and datetime.now() < end_time:
            # Get recent market volume
            market_volume = await self._get_recent_volume(symbol, period_seconds=60)
            
            # Calculate slice quantity based on participation rate
            slice_quantity = min(
                market_volume * participation_rate,
                quantity - executed_quantity
            )
            
            if slice_quantity > 0:
                try:
                    result = await self._execute_slice(symbol, side, slice_quantity)
                    executed_quantity += result['filled']
                    results.append(result)
                    
                    logger.info(f"POV slice {slice_id} executed: {result['filled']} @ {result['price']}")
                    slice_id += 1
                except Exception as e:
                    logger.error(f"POV slice {slice_id} failed: {e}")
                    
            # Wait before next check
            await asyncio.sleep(60)
            
        summary = {
            'order_id': order_id,
            'algo_type': 'POV',
            'total_executed': executed_quantity,
            'target_quantity': quantity,
            'fill_rate': executed_quantity / quantity if quantity > 0 else 0,
            'num_slices': len(results),
            'avg_price': np.mean([r['price'] for r in results]) if results else 0,
            'duration_seconds': (datetime.now() - start_time).total_seconds()
        }
        
        return summary
        
    def _create_twap_slices(self, config: SliceConfig) -> List[ExecutionSlice]:
        """Create equally-sized TWAP slices"""
        slices = []
        slice_quantity = config.total_quantity / config.num_slices
        interval = config.duration_seconds / config.num_slices
        
        for i in range(config.num_slices):
            target_time = datetime.now() + timedelta(seconds=interval * i)
            slices.append(ExecutionSlice(
                slice_id=i,
                quantity=slice_quantity,
                target_time=target_time
            ))
            
        return slices
        
    def _create_vwap_slices(
        self,
        config: SliceConfig,
        volume_profile: List[float]
    ) -> List[ExecutionSlice]:
        """Create VWAP slices based on volume profile"""
        total_volume = sum(volume_profile)
        slices = []
        interval = config.duration_seconds / len(volume_profile)
        
        for i, volume in enumerate(volume_profile):
            # Allocate quantity proportional to volume
            weight = volume / total_volume if total_volume > 0 else 1.0 / len(volume_profile)
            slice_quantity = config.total_quantity * weight
            
            target_time = datetime.now() + timedelta(seconds=interval * i)
            slices.append(ExecutionSlice(
                slice_id=i,
                quantity=slice_quantity,
                target_time=target_time
            ))
            
        return slices
        
    async def _execute_slice(self, symbol: str, side: str, quantity: float) -> Dict:
        """Execute a single slice"""
        # Get current market price
        price = await self._get_current_price(symbol, side)
        
        # Place limit order with some slippage tolerance
        slippage = 0.001  # 0.1%
        if side == 'buy':
            limit_price = price * (1 + slippage)
        else:
            limit_price = price * (1 - slippage)
            
        # Execute order (simplified - should use exchange client)
        result = {
            'filled': quantity,
            'price': price,
            'timestamp': datetime.now(),
            'side': side,
            'symbol': symbol
        }
        
        self.execution_history.append(result)
        return result
        
    async def _get_volume_profile(self, symbol: str, duration_minutes: int) -> List[float]:
        """Get historical volume profile"""
        # Simplified - should fetch from market data
        # Returns volume distribution over time intervals
        num_intervals = min(duration_minutes, 60)
        
        # Generate sample volume profile (would come from historical data)
        base_volume = 1000.0
        profile = []
        
        for i in range(num_intervals):
            # Higher volume during certain periods
            hour_factor = 1.0 + 0.5 * np.sin(i * np.pi / num_intervals)
            profile.append(base_volume * hour_factor)
            
        return profile
        
    async def _get_recent_volume(self, symbol: str, period_seconds: int = 60) -> float:
        """Get recent market volume"""
        # Simplified - should fetch from market data
        return 10000.0
        
    async def _get_current_price(self, symbol: str, side: str) -> float:
        """Get current market price"""
        # Simplified - should fetch from exchange
        if side == 'buy':
            return 50000.0  # Ask price
        else:
            return 49950.0  # Bid price
            
    def _create_summary(
        self,
        order_id: str,
        slices: List[ExecutionSlice],
        results: List[Dict]
    ) -> Dict:
        """Create execution summary"""
        total_executed = sum(s.executed_quantity for s in slices)
        filled_slices = [s for s in slices if s.status == "filled"]
        
        if filled_slices:
            avg_price = sum(s.executed_price * s.executed_quantity for s in filled_slices) / total_executed
        else:
            avg_price = 0.0
            
        return {
            'order_id': order_id,
            'total_slices': len(slices),
            'filled_slices': len(filled_slices),
            'total_executed': total_executed,
            'avg_price': avg_price,
            'slices': slices,
            'results': results
        }
        
    def get_execution_stats(self, order_id: str) -> Dict:
        """Get statistics for an execution"""
        if order_id not in self.active_orders:
            return {}
            
        slices = self.active_orders[order_id]
        filled = [s for s in slices if s.status == "filled"]
        
        if not filled:
            return {'status': 'no fills'}
            
        prices = [s.executed_price for s in filled]
        quantities = [s.executed_quantity for s in filled]
        
        return {
            'num_fills': len(filled),
            'total_quantity': sum(quantities),
            'avg_price': np.mean(prices),
            'price_std': np.std(prices),
            'vwap': sum(p * q for p, q in zip(prices, quantities)) / sum(quantities),
            'min_price': min(prices),
            'max_price': max(prices),
            'fill_rate': len(filled) / len(slices)
        }
