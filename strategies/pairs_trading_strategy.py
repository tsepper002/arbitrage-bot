"""
Pairs Trading Strategy
Implements statistical arbitrage using cointegrated pairs
"""

import logging
from typing import Dict, List, Tuple, Optional
from datetime import datetime
import numpy as np
from scipy import stats
from collections import defaultdict

logger = logging.getLogger(__name__)


class PairsTradingStrategy:
    """
    Statistical arbitrage strategy for trading cointegrated pairs
    """
    
    def __init__(self, config: Dict = None):
        """Initialize pairs trading strategy"""
        self.config = config or {}
        self.lookback_period = self.config.get('lookback_period', 60)
        self.entry_threshold = self.config.get('entry_threshold', 2.0)
        self.exit_threshold = self.config.get('exit_threshold', 0.5)
        self.correlation_threshold = self.config.get('correlation_threshold', 0.7)
        self.rolling_corr_window = self.config.get('rolling_corr_window', 30)
        self.min_rolling_corr = self.config.get('min_rolling_corr', 0.5)
        
        self.pairs = {}
        self.spreads = defaultdict(list)
        self.positions = {}
        self.signals = []
        self.price_history = defaultdict(list)
        
        logger.info("Pairs trading strategy initialized")
    
    def calculate_correlation(self, prices1: List[float], 
                             prices2: List[float]) -> float:
        """
        Calculate Pearson correlation coefficient
        
        Args:
            prices1: Price series for asset 1
            prices2: Price series for asset 2
            
        Returns:
            Correlation coefficient
        """
        if len(prices1) != len(prices2) or len(prices1) < 2:
            return 0.0
        
        correlation = np.corrcoef(prices1, prices2)[0, 1]
        return correlation
    
    def test_cointegration(self, prices1: List[float], 
                          prices2: List[float]) -> Tuple[bool, float]:
        """
        Test for cointegration using Engle-Granger method
        
        Args:
            prices1: Price series for asset 1
            prices2: Price series for asset 2
            
        Returns:
            Tuple of (is_cointegrated, p_value)
        """
        if len(prices1) < 30 or len(prices2) < 30:
            return False, 1.0
        
        # Run OLS regression
        prices1_arr = np.array(prices1)
        prices2_arr = np.array(prices2)
        
        # Add constant
        X = np.column_stack([np.ones(len(prices1_arr)), prices1_arr])
        
        # Calculate coefficients
        beta = np.linalg.lstsq(X, prices2_arr, rcond=None)[0]
        
        # Calculate residuals (spread)
        spread = prices2_arr - (beta[0] + beta[1] * prices1_arr)
        
        # ADF test on spread (simplified)
        # In production, use statsmodels.tsa.stattools.adfuller
        spread_diff = np.diff(spread)
        
        if len(spread_diff) == 0:
            return False, 1.0
        
        # Simplified stationarity test
        p_value = self._simple_adf_test(spread)
        
        is_cointegrated = p_value < 0.05
        return is_cointegrated, p_value
    
    def _simple_adf_test(self, series: np.ndarray) -> float:
        """Simplified ADF test (placeholder for real implementation)"""
        # In production, use statsmodels.tsa.stattools.adfuller
        # This is simplified version
        mean = np.mean(series)
        std = np.std(series)
        
        if std == 0:
            return 1.0
        
        # Check mean reversion tendency
        deviations = np.abs(series - mean)
        avg_deviation = np.mean(deviations)
        
        # Normalized score (0 to 1, lower is better)
        score = min(avg_deviation / (3 * std), 1.0)
        
        return score
    
    def calculate_spread(self, symbol1: str, symbol2: str,
                        price1: float, price2: float) -> float:
        """
        Calculate normalized spread between two assets
        
        Args:
            symbol1: First symbol
            symbol2: Second symbol
            price1: Price of first asset
            price2: Price of second asset
            
        Returns:
            Normalized spread
        """
        pair_key = f"{symbol1}_{symbol2}"
        
        if pair_key not in self.pairs:
            return 0.0
        
        hedge_ratio = self.pairs[pair_key]['hedge_ratio']
        spread = price2 - (hedge_ratio * price1)
        
        return spread
    
    def calculate_zscore(self, symbol1: str, symbol2: str) -> float:
        """
        Calculate z-score of current spread
        
        Args:
            symbol1: First symbol
            symbol2: Second symbol
            
        Returns:
            Z-score
        """
        pair_key = f"{symbol1}_{symbol2}"
        
        if pair_key not in self.spreads or len(self.spreads[pair_key]) < 2:
            return 0.0
        
        spreads = self.spreads[pair_key]
        mean_spread = np.mean(spreads)
        std_spread = np.std(spreads)
        
        if std_spread == 0:
            return 0.0
        
        current_spread = spreads[-1]
        zscore = (current_spread - mean_spread) / std_spread
        
        return zscore
    
    def identify_pairs(self, symbols: List[str], 
                      price_data: Dict[str, List[float]]) -> List[Tuple[str, str]]:
        """
        Identify cointegrated pairs from list of symbols
        
        Args:
            symbols: List of trading symbols
            price_data: Dictionary of price histories
            
        Returns:
            List of cointegrated pairs
        """
        cointegrated_pairs = []
        
        for i in range(len(symbols)):
            for j in range(i + 1, len(symbols)):
                symbol1, symbol2 = symbols[i], symbols[j]
                
                if symbol1 not in price_data or symbol2 not in price_data:
                    continue
                
                prices1 = price_data[symbol1]
                prices2 = price_data[symbol2]
                
                # Check correlation
                correlation = self.calculate_correlation(prices1, prices2)
                
                if abs(correlation) < self.correlation_threshold:
                    continue
                
                # Test cointegration
                is_coint, p_value = self.test_cointegration(prices1, prices2)
                
                if is_coint:
                    # Calculate hedge ratio
                    hedge_ratio = self._calculate_hedge_ratio(prices1, prices2)
                    
                    pair_key = f"{symbol1}_{symbol2}"
                    self.pairs[pair_key] = {
                        'symbol1': symbol1,
                        'symbol2': symbol2,
                        'correlation': correlation,
                        'p_value': p_value,
                        'hedge_ratio': hedge_ratio
                    }
                    
                    cointegrated_pairs.append((symbol1, symbol2))
                    logger.info(f"Cointegrated pair found: {symbol1} - {symbol2}")
        
        return cointegrated_pairs
    
    def _calculate_hedge_ratio(self, prices1: List[float], 
                               prices2: List[float]) -> float:
        """Calculate optimal hedge ratio using OLS"""
        prices1_arr = np.array(prices1)
        prices2_arr = np.array(prices2)
        
        # Simple linear regression
        X = np.column_stack([np.ones(len(prices1_arr)), prices1_arr])
        beta = np.linalg.lstsq(X, prices2_arr, rcond=None)[0]
        
        return beta[1]

    def rolling_correlation(self, symbol1: str, symbol2: str) -> Optional[float]:
        """
        Calculate rolling correlation over recent window to detect regime shifts.
        
        If rolling correlation drops below threshold, the pair relationship
        may have broken — signals should be ignored to avoid regime-shift losses.
        
        Returns:
            Rolling correlation coefficient, or None if insufficient data
        """
        prices1 = self.price_history.get(symbol1, [])
        prices2 = self.price_history.get(symbol2, [])
        
        window = self.rolling_corr_window
        if len(prices1) < window or len(prices2) < window:
            return None
        
        # Use only the last `window` prices
        recent1 = prices1[-window:]
        recent2 = prices2[-window:]
        
        return float(np.corrcoef(recent1, recent2)[0, 1])
    
    def generate_signals(self, symbol1: str, symbol2: str,
                        price1: float, price2: float) -> Optional[Dict]:
        """
        Generate trading signals based on z-score
        
        Args:
            symbol1: First symbol
            symbol2: Second symbol
            price1: Price of first asset
            price2: Price of second asset
            
        Returns:
            Trading signal or None
        """
        pair_key = f"{symbol1}_{symbol2}"
        
        if pair_key not in self.pairs:
            return None
        
        # ROLLING CORRELATION CHECK: detect regime shifts
        # If correlation has broken down recently, skip signals — pair may no longer revert
        # Pairs trading requires POSITIVE correlation (not just strong negative)
        rolling_corr = self.rolling_correlation(symbol1, symbol2)
        if rolling_corr is not None and rolling_corr < self.min_rolling_corr:
            logger.debug(f"Pairs {pair_key}: rolling correlation {rolling_corr:.3f} < {self.min_rolling_corr} — regime shift, skipping")
            return None
        
        # Calculate and store spread
        spread = self.calculate_spread(symbol1, symbol2, price1, price2)
        self.spreads[pair_key].append(spread)
        
        # Keep only recent spreads
        if len(self.spreads[pair_key]) > self.lookback_period:
            self.spreads[pair_key] = self.spreads[pair_key][-self.lookback_period:]
        
        # Need enough history
        if len(self.spreads[pair_key]) < 30:
            return None
        
        # Calculate z-score
        zscore = self.calculate_zscore(symbol1, symbol2)
        
        # Generate signals
        if zscore > self.entry_threshold:
            # Spread too high - short spread (sell asset2, buy asset1)
            signal = {
                'type': 'PAIRS_SHORT_SPREAD',
                'symbol1': symbol1,
                'symbol2': symbol2,
                'price1': price1,
                'price2': price2,
                'zscore': zscore,
                'action1': 'BUY',
                'action2': 'SELL',
                'timestamp': datetime.now(),
                'confidence': min(abs(zscore) / 3.0, 1.0)
            }
            self.signals.append(signal)
            logger.info(f"Pairs signal: SHORT spread {pair_key}, z={zscore:.2f}")
            return signal
        
        elif zscore < -self.entry_threshold:
            # Spread too low - long spread (buy asset2, sell asset1)
            signal = {
                'type': 'PAIRS_LONG_SPREAD',
                'symbol1': symbol1,
                'symbol2': symbol2,
                'price1': price1,
                'price2': price2,
                'zscore': zscore,
                'action1': 'SELL',
                'action2': 'BUY',
                'timestamp': datetime.now(),
                'confidence': min(abs(zscore) / 3.0, 1.0)
            }
            self.signals.append(signal)
            logger.info(f"Pairs signal: LONG spread {pair_key}, z={zscore:.2f}")
            return signal
        
        elif abs(zscore) < self.exit_threshold and pair_key in self.positions:
            # Exit signal
            signal = {
                'type': 'PAIRS_EXIT',
                'symbol1': symbol1,
                'symbol2': symbol2,
                'price1': price1,
                'price2': price2,
                'zscore': zscore,
                'timestamp': datetime.now()
            }
            self.signals.append(signal)
            logger.info(f"Pairs exit signal: {pair_key}, z={zscore:.2f}")
            return signal
        
        return None
    
    def update_price_history(self, symbol: str, price: float):
        """Update price history for symbol"""
        self.price_history[symbol].append(price)
        
        if len(self.price_history[symbol]) > self.lookback_period:
            self.price_history[symbol] = self.price_history[symbol][-self.lookback_period:]
    
    def get_statistics(self) -> Dict:
        """Get strategy statistics"""
        return {
            'identified_pairs': len(self.pairs),
            'total_signals': len(self.signals),
            'long_spread_signals': sum(1 for s in self.signals if s['type'] == 'PAIRS_LONG_SPREAD'),
            'short_spread_signals': sum(1 for s in self.signals if s['type'] == 'PAIRS_SHORT_SPREAD'),
            'exit_signals': sum(1 for s in self.signals if s['type'] == 'PAIRS_EXIT'),
            'active_positions': len(self.positions)
        }
