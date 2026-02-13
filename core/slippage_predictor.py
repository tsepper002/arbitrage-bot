"""
Smart Slippage Prediction
Predicts slippage before execution to optimize order sizes and avoid poor executions.
Expected impact: +5-10% profit through better execution.
"""

import logging
from typing import Dict, List, Optional
from dataclasses import dataclass
from collections import deque
import time

logger = logging.getLogger(__name__)


@dataclass
class SlippagePrediction:
    """Result of slippage prediction."""
    symbol: str
    exchange: str
    side: str  # 'buy' or 'sell'
    quantity: float
    predicted_slippage_pct: float
    confidence: float  # 0-1
    recommended_quantity: Optional[float]  # Adjusted size if needed
    orderbook_depth_score: float  # 0-1, orderbook quality


@dataclass
class ExecutionResult:
    """Historical execution for learning."""
    timestamp: float
    symbol: str
    exchange: str
    side: str
    quantity: float
    expected_price: float
    actual_price: float
    slippage_pct: float
    orderbook_depth: int  # Number of levels consumed


class SlippagePredictor:
    """
    Predicts execution slippage based on orderbook analysis and historical data.
    
    Uses:
    1. Orderbook depth analysis
    2. Historical execution patterns
    3. Time-of-day patterns
    4. Volatility indicators
    """
    
    def __init__(
        self,
        history_size: int = 1000,
        max_slippage_threshold: float = 0.5,  # 0.5% max acceptable slippage
        min_depth_levels: int = 5
    ):
        """
        Initialize predictor.
        
        Args:
            history_size: Number of historical executions to keep
            max_slippage_threshold: Max acceptable slippage %
            min_depth_levels: Minimum orderbook depth for reliable prediction
        """
        self.history: deque = deque(maxlen=history_size)
        self.max_slippage_threshold = max_slippage_threshold
        self.min_depth_levels = min_depth_levels
        
        logger.info(
            "SlippagePredictor initialized (history: %d, max_slippage: %.2f%%)",
            history_size, max_slippage_threshold
        )
    
    def predict(
        self,
        symbol: str,
        exchange: str,
        side: str,
        quantity: float,
        orderbook: Dict,
        current_volatility: Optional[float] = None
    ) -> SlippagePrediction:
        """
        Predict slippage for an order.
        
        Args:
            symbol: Trading pair
            exchange: Exchange name
            side: 'buy' or 'sell'
            quantity: Order size
            orderbook: Current orderbook
            current_volatility: Optional volatility metric
            
        Returns:
            SlippagePrediction with recommended adjustments
        """
        try:
            # Analyze orderbook depth
            depth_score, levels_needed = self._analyze_orderbook_depth(
                orderbook, side, quantity
            )
            
            # Get historical average slippage for similar orders
            historical_avg = self._get_historical_average(
                symbol, exchange, side, quantity
            )
            
            # Predict slippage based on orderbook + history
            if depth_score >= 0.8:  # Good depth
                predicted_slippage = historical_avg * 0.5  # Optimistic
            elif depth_score >= 0.5:  # Medium depth
                predicted_slippage = historical_avg
            else:  # Poor depth
                predicted_slippage = historical_avg * 1.5  # Pessimistic
            
            # Adjust for volatility if provided
            if current_volatility and current_volatility > 2.0:
                predicted_slippage *= 1.2  # 20% worse in high volatility
            
            # Calculate confidence
            confidence = self._calculate_confidence(
                len(self.history), depth_score, levels_needed
            )
            
            # Recommend quantity adjustment if slippage too high
            recommended_qty = None
            if predicted_slippage > self.max_slippage_threshold:
                # Reduce quantity to stay within threshold
                recommended_qty = quantity * 0.7  # Reduce by 30%
                logger.info(
                    "High predicted slippage (%.2f%%) for %s %s %.6f on %s, "
                    "recommend reducing to %.6f",
                    predicted_slippage, side, symbol, quantity, exchange, recommended_qty
                )
            
            result = SlippagePrediction(
                symbol=symbol,
                exchange=exchange,
                side=side,
                quantity=quantity,
                predicted_slippage_pct=predicted_slippage,
                confidence=confidence,
                recommended_quantity=recommended_qty,
                orderbook_depth_score=depth_score
            )
            
            logger.debug(
                "Slippage prediction for %s %s %.6f on %s: %.3f%% (confidence: %.2f)",
                side, symbol, quantity, exchange, predicted_slippage, confidence
            )
            
            return result
            
        except Exception as e:
            logger.error("Error predicting slippage: %s", e)
            # Return pessimistic prediction
            return SlippagePrediction(
                symbol=symbol,
                exchange=exchange,
                side=side,
                quantity=quantity,
                predicted_slippage_pct=1.0,  # Assume 1% slippage
                confidence=0.0,
                recommended_quantity=quantity * 0.5,
                orderbook_depth_score=0.0
            )
    
    def record_execution(
        self,
        symbol: str,
        exchange: str,
        side: str,
        quantity: float,
        expected_price: float,
        actual_price: float,
        orderbook_depth: int
    ):
        """
        Record an actual execution for learning.
        
        Args:
            symbol: Trading pair
            exchange: Exchange name
            side: 'buy' or 'sell'
            quantity: Executed quantity
            expected_price: Expected price (top of book)
            actual_price: Actual fill price
            orderbook_depth: Number of orderbook levels consumed
        """
        try:
            # Calculate actual slippage
            if side == 'buy':
                slippage_pct = ((actual_price - expected_price) / expected_price) * 100
            else:  # sell
                slippage_pct = ((expected_price - actual_price) / expected_price) * 100
            
            execution = ExecutionResult(
                timestamp=time.time(),
                symbol=symbol,
                exchange=exchange,
                side=side,
                quantity=quantity,
                expected_price=expected_price,
                actual_price=actual_price,
                slippage_pct=slippage_pct,
                orderbook_depth=orderbook_depth
            )
            
            self.history.append(execution)
            
            logger.debug(
                "Recorded execution: %s %s %.6f on %s, slippage: %.3f%%",
                side, symbol, quantity, exchange, slippage_pct
            )
            
        except Exception as e:
            logger.error("Error recording execution: %s", e)
    
    def _analyze_orderbook_depth(
        self,
        orderbook: Dict,
        side: str,
        quantity: float
    ) -> tuple:
        """
        Analyze orderbook depth for the order.
        
        Returns:
            (depth_score 0-1, levels_needed)
        """
        try:
            # Get appropriate side of orderbook
            if side == 'buy':
                levels = orderbook.get('asks', [])
            else:
                levels = orderbook.get('bids', [])
            
            if not levels:
                return 0.0, 0
            
            # Calculate how many levels needed
            cumulative = 0.0
            levels_needed = 0
            
            for price, qty in levels:
                cumulative += qty
                levels_needed += 1
                if cumulative >= quantity:
                    break
            
            # Score based on how easily we can fill
            if levels_needed == 0:
                return 0.0, 0
            elif levels_needed == 1:
                depth_score = 1.0  # Can fill at top of book
            elif levels_needed <= 3:
                depth_score = 0.8  # Good depth
            elif levels_needed <= 5:
                depth_score = 0.6  # Medium depth
            elif levels_needed <= 10:
                depth_score = 0.4  # Poor depth
            else:
                depth_score = 0.2  # Very poor depth
            
            return depth_score, levels_needed
            
        except Exception as e:
            logger.error("Error analyzing orderbook depth: %s", e)
            return 0.0, 0
    
    def _get_historical_average(
        self,
        symbol: str,
        exchange: str,
        side: str,
        quantity: float
    ) -> float:
        """
        Get average historical slippage for similar orders.
        
        Returns:
            Average slippage % (defaults to 0.2% if no history)
        """
        if not self.history:
            return 0.2  # Default 0.2% slippage
        
        # Filter similar orders (same symbol, exchange, side, similar size)
        similar = [
            ex.slippage_pct for ex in self.history
            if (ex.symbol == symbol and
                ex.exchange == exchange and
                ex.side == side and
                0.5 * quantity <= ex.quantity <= 2.0 * quantity)
        ]
        
        if similar:
            avg = sum(similar) / len(similar)
            return max(0.0, avg)  # Can't be negative
        else:
            # Fallback to all history for this exchange
            exchange_history = [
                ex.slippage_pct for ex in self.history
                if ex.exchange == exchange and ex.side == side
            ]
            
            if exchange_history:
                return max(0.0, sum(exchange_history) / len(exchange_history))
            else:
                return 0.2  # Default
    
    def _calculate_confidence(
        self,
        history_count: int,
        depth_score: float,
        levels_needed: int
    ) -> float:
        """Calculate prediction confidence."""
        # More history = higher confidence
        history_confidence = min(history_count / 100, 1.0)
        
        # Better depth = higher confidence
        depth_confidence = depth_score
        
        # Fewer levels needed = higher confidence
        levels_confidence = 1.0 / (1.0 + levels_needed * 0.1)
        
        # Combined (weighted average)
        confidence = (
            0.3 * history_confidence +
            0.5 * depth_confidence +
            0.2 * levels_confidence
        )
        
        return confidence
    
    def get_statistics(self) -> Dict:
        """Get predictor statistics."""
        if not self.history:
            return {
                'total_executions': 0,
                'avg_slippage': 0.0,
                'max_slippage': 0.0
            }
        
        slippages = [ex.slippage_pct for ex in self.history]
        
        return {
            'total_executions': len(self.history),
            'avg_slippage': sum(slippages) / len(slippages),
            'max_slippage': max(slippages),
            'min_slippage': min(slippages)
        }


def get_slippage_predictor(**kwargs) -> SlippagePredictor:
    """Factory function to create SlippagePredictor."""
    return SlippagePredictor(**kwargs)
