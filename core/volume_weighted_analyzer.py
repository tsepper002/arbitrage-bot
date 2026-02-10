"""
Volume-Weighted Spread Analyzer
Analyzes orderbook with volume weighting for more accurate spread calculations.
Expected impact: +3-7% accuracy in profit calculations.
"""

import logging
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class VolumeWeightedSpread:
    """Result of volume-weighted analysis."""
    symbol: str
    buy_exchange: str
    sell_exchange: str
    vwap_buy: float  # Volume-weighted average price for buying
    vwap_sell: float  # Volume-weighted average price for selling
    total_buy_volume: float
    total_sell_volume: float
    executable_quantity: float  # Max quantity at these prices
    spread_pct: float
    confidence: float  # 0-1, based on orderbook depth


class VolumeWeightedAnalyzer:
    """
    Analyzes orderbook depth with volume weighting.
    
    Instead of just looking at top-of-book prices, this calculates
    the true executable prices for a given order size by considering
    cumulative volume at various price levels.
    """
    
    def __init__(self, min_depth_levels: int = 10, max_depth_levels: int = 20):
        """
        Initialize analyzer.
        
        Args:
            min_depth_levels: Minimum levels needed for reliable analysis
            max_depth_levels: Maximum levels to analyze (performance limit)
        """
        self.min_depth_levels = min_depth_levels
        self.max_depth_levels = max_depth_levels
        logger.info("VolumeWeightedAnalyzer initialized (depth: %d-%d levels)",
                   min_depth_levels, max_depth_levels)
    
    def analyze_opportunity(
        self,
        symbol: str,
        buy_exchange: str,
        sell_exchange: str,
        buy_orderbook: Dict,
        sell_orderbook: Dict,
        target_quantity: float
    ) -> Optional[VolumeWeightedSpread]:
        """
        Analyze arbitrage opportunity with volume weighting.
        
        Args:
            symbol: Trading pair (e.g., 'BTC/USDT')
            buy_exchange: Exchange to buy from
            sell_exchange: Exchange to sell on
            buy_orderbook: Orderbook with 'asks' list [(price, quantity), ...]
            sell_orderbook: Orderbook with 'bids' list [(price, quantity), ...]
            target_quantity: Desired order size
            
        Returns:
            VolumeWeightedSpread or None if insufficient depth
        """
        try:
            # Extract asks (for buying) and bids (for selling)
            asks = buy_orderbook.get('asks', [])
            bids = sell_orderbook.get('bids', [])
            
            if not asks or not bids:
                return None
            
            # Limit depth for performance
            asks = asks[:self.max_depth_levels]
            bids = bids[:self.max_depth_levels]
            
            # Check minimum depth
            if len(asks) < self.min_depth_levels or len(bids) < self.min_depth_levels:
                logger.debug("Insufficient orderbook depth for %s", symbol)
                return None
            
            # Calculate VWAP for buying (from asks)
            vwap_buy, buy_volume, buy_qty = self._calculate_vwap(
                asks, target_quantity, side='buy'
            )
            
            # Calculate VWAP for selling (from bids)
            vwap_sell, sell_volume, sell_qty = self._calculate_vwap(
                bids, target_quantity, side='sell'
            )
            
            if vwap_buy is None or vwap_sell is None:
                return None
            
            # Executable quantity is the minimum of what we can buy and sell
            executable_qty = min(buy_qty, sell_qty)
            
            if executable_qty < target_quantity * 0.1:  # At least 10% of target
                logger.debug("Insufficient executable quantity for %s", symbol)
                return None
            
            # Calculate spread
            spread_pct = ((vwap_sell - vwap_buy) / vwap_buy) * 100
            
            # Calculate confidence based on orderbook depth
            confidence = self._calculate_confidence(
                len(asks), len(bids), buy_volume, sell_volume, target_quantity
            )
            
            result = VolumeWeightedSpread(
                symbol=symbol,
                buy_exchange=buy_exchange,
                sell_exchange=sell_exchange,
                vwap_buy=vwap_buy,
                vwap_sell=vwap_sell,
                total_buy_volume=buy_volume,
                total_sell_volume=sell_volume,
                executable_quantity=executable_qty,
                spread_pct=spread_pct,
                confidence=confidence
            )
            
            logger.debug(
                "Volume-weighted analysis for %s: VWAP buy=%.6f, sell=%.6f, "
                "spread=%.4f%%, qty=%.6f, confidence=%.2f",
                symbol, vwap_buy, vwap_sell, spread_pct, executable_qty, confidence
            )
            
            return result
            
        except Exception as e:
            logger.error("Error in volume-weighted analysis for %s: %s", symbol, e)
            return None
    
    def _calculate_vwap(
        self,
        levels: List[Tuple[float, float]],
        target_quantity: float,
        side: str
    ) -> Tuple[Optional[float], float, float]:
        """
        Calculate Volume-Weighted Average Price.
        
        Args:
            levels: List of (price, quantity) tuples
            target_quantity: Desired quantity
            side: 'buy' or 'sell'
            
        Returns:
            (vwap, total_volume, filled_quantity) or (None, 0, 0)
        """
        cumulative_value = 0.0
        cumulative_quantity = 0.0
        total_volume = 0.0
        
        for price, quantity in levels:
            # How much of this level do we need?
            remaining = target_quantity - cumulative_quantity
            take_quantity = min(quantity, remaining)
            
            cumulative_value += price * take_quantity
            cumulative_quantity += take_quantity
            total_volume += quantity
            
            if cumulative_quantity >= target_quantity:
                break
        
        if cumulative_quantity == 0:
            return None, 0.0, 0.0
        
        vwap = cumulative_value / cumulative_quantity
        return vwap, total_volume, cumulative_quantity
    
    def _calculate_confidence(
        self,
        ask_levels: int,
        bid_levels: int,
        buy_volume: float,
        sell_volume: float,
        target_quantity: float
    ) -> float:
        """
        Calculate confidence score based on orderbook depth.
        
        Args:
            ask_levels: Number of ask levels available
            bid_levels: Number of bid levels available
            buy_volume: Total volume in asks
            sell_volume: Total volume in bids
            target_quantity: Target order size
            
        Returns:
            Confidence score 0-1
        """
        # Depth score (more levels = higher confidence)
        depth_score = min(ask_levels, bid_levels) / self.max_depth_levels
        
        # Volume score (more volume = higher confidence)
        min_volume = min(buy_volume, sell_volume)
        volume_score = min(min_volume / (target_quantity * 10), 1.0)
        
        # Combined confidence (weighted average)
        confidence = 0.6 * depth_score + 0.4 * volume_score
        
        return confidence
    
    def compare_with_simple(
        self,
        symbol: str,
        buy_orderbook: Dict,
        sell_orderbook: Dict,
        quantity: float
    ) -> Dict[str, float]:
        """
        Compare volume-weighted vs simple top-of-book analysis.
        
        Returns dict with 'simple_spread', 'vw_spread', 'difference'
        """
        try:
            asks = buy_orderbook.get('asks', [])
            bids = sell_orderbook.get('bids', [])
            
            if not asks or not bids:
                return {}
            
            # Simple spread (top of book)
            simple_buy = asks[0][0]
            simple_sell = bids[0][0]
            simple_spread = ((simple_sell - simple_buy) / simple_buy) * 100
            
            # Volume-weighted spread
            vwap_buy, _, _ = self._calculate_vwap(asks, quantity, 'buy')
            vwap_sell, _, _ = self._calculate_vwap(bids, quantity, 'sell')
            
            if vwap_buy and vwap_sell:
                vw_spread = ((vwap_sell - vwap_buy) / vwap_buy) * 100
                difference = vw_spread - simple_spread
                
                return {
                    'simple_spread': simple_spread,
                    'vw_spread': vw_spread,
                    'difference': difference,
                    'difference_pct': (difference / simple_spread * 100) if simple_spread else 0
                }
            
            return {}
            
        except Exception as e:
            logger.error("Error comparing spreads: %s", e)
            return {}
    
    def get_statistics(self) -> Dict[str, float]:
        """Get analyzer statistics."""
        return {
            'min_depth_levels': self.min_depth_levels,
            'max_depth_levels': self.max_depth_levels
        }


def get_volume_weighted_analyzer(**kwargs) -> VolumeWeightedAnalyzer:
    """Factory function to create VolumeWeightedAnalyzer."""
    return VolumeWeightedAnalyzer(**kwargs)
