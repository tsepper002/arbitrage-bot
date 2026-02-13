"""
Volatility Arbitrage Strategy
Implements volatility trading using options pricing and volatility surface
"""

import logging
from typing import Dict, List, Optional, Tuple
from datetime import datetime
import numpy as np
from scipy.stats import norm
from collections import defaultdict

logger = logging.getLogger(__name__)


class VolatilityArbitrageStrategy:
    """
    Volatility arbitrage strategy using options pricing
    """
    
    def __init__(self, config: Dict = None):
        """Initialize volatility arbitrage strategy"""
        self.config = config or {}
        self.lookback_period = self.config.get('lookback_period', 30)
        self.risk_free_rate = self.config.get('risk_free_rate', 0.02)
        self.vol_threshold = self.config.get('vol_threshold', 0.05)
        
        self.historical_vol = {}
        self.implied_vol = {}
        self.vol_spread = {}
        self.price_history = defaultdict(list)
        self.signals = []
        
        logger.info("Volatility arbitrage strategy initialized")
    
    def calculate_historical_volatility(self, prices: List[float], 
                                       method: str = 'close') -> float:
        """
        Calculate historical volatility
        
        Args:
            prices: Historical prices
            method: 'close' (close-to-close) or 'parkinson'
            
        Returns:
            Annualized volatility
        """
        if len(prices) < 2:
            return 0.0
        
        if method == 'close':
            # Close-to-close volatility
            returns = np.diff(np.log(prices))
            volatility = np.std(returns) * np.sqrt(252)
        
        elif method == 'parkinson':
            # Parkinson volatility (requires high/low data)
            # Simplified using single prices
            returns = np.diff(np.log(prices))
            volatility = np.std(returns) * np.sqrt(252) * 1.5
        
        else:
            returns = np.diff(np.log(prices))
            volatility = np.std(returns) * np.sqrt(252)
        
        return volatility
    
    def black_scholes_price(self, S: float, K: float, T: float, 
                           r: float, sigma: float, option_type: str = 'call') -> float:
        """
        Calculate Black-Scholes option price
        
        Args:
            S: Current stock price
            K: Strike price
            T: Time to expiration (years)
            r: Risk-free rate
            sigma: Volatility
            option_type: 'call' or 'put'
            
        Returns:
            Option price
        """
        if T <= 0 or sigma <= 0:
            return 0.0
        
        d1 = (np.log(S / K) + (r + 0.5 * sigma ** 2) * T) / (sigma * np.sqrt(T))
        d2 = d1 - sigma * np.sqrt(T)
        
        if option_type == 'call':
            price = S * norm.cdf(d1) - K * np.exp(-r * T) * norm.cdf(d2)
        else:  # put
            price = K * np.exp(-r * T) * norm.cdf(-d2) - S * norm.cdf(-d1)
        
        return price
    
    def calculate_implied_volatility(self, option_price: float, S: float, 
                                     K: float, T: float, r: float,
                                     option_type: str = 'call') -> float:
        """
        Calculate implied volatility using Newton-Raphson method
        
        Args:
            option_price: Market option price
            S: Current stock price
            K: Strike price
            T: Time to expiration
            r: Risk-free rate
            option_type: 'call' or 'put'
            
        Returns:
            Implied volatility
        """
        if T <= 0:
            return 0.0
        
        # Initial guess
        sigma = 0.3
        tolerance = 0.0001
        max_iterations = 100
        
        for _ in range(max_iterations):
            price = self.black_scholes_price(S, K, T, r, sigma, option_type)
            vega = self.calculate_vega(S, K, T, r, sigma)
            
            if vega < 0.0001:
                break
            
            diff = option_price - price
            
            if abs(diff) < tolerance:
                break
            
            # Newton-Raphson update
            sigma = sigma + diff / vega
            
            # Bounds
            sigma = max(0.01, min(sigma, 3.0))
        
        return sigma
    
    def calculate_vega(self, S: float, K: float, T: float, 
                      r: float, sigma: float) -> float:
        """
        Calculate option vega (sensitivity to volatility)
        
        Args:
            S: Current stock price
            K: Strike price
            T: Time to expiration
            r: Risk-free rate
            sigma: Volatility
            
        Returns:
            Vega value
        """
        if T <= 0 or sigma <= 0:
            return 0.0
        
        d1 = (np.log(S / K) + (r + 0.5 * sigma ** 2) * T) / (sigma * np.sqrt(T))
        vega = S * norm.pdf(d1) * np.sqrt(T)
        
        return vega
    
    def calculate_delta(self, S: float, K: float, T: float, 
                       r: float, sigma: float, option_type: str = 'call') -> float:
        """
        Calculate option delta (sensitivity to price)
        
        Args:
            S: Current stock price
            K: Strike price
            T: Time to expiration
            r: Risk-free rate
            sigma: Volatility
            option_type: 'call' or 'put'
            
        Returns:
            Delta value
        """
        if T <= 0 or sigma <= 0:
            return 0.0
        
        d1 = (np.log(S / K) + (r + 0.5 * sigma ** 2) * T) / (sigma * np.sqrt(T))
        
        if option_type == 'call':
            delta = norm.cdf(d1)
        else:  # put
            delta = norm.cdf(d1) - 1
        
        return delta
    
    def calculate_gamma(self, S: float, K: float, T: float, 
                       r: float, sigma: float) -> float:
        """Calculate option gamma (rate of change of delta)"""
        if T <= 0 or sigma <= 0:
            return 0.0
        
        d1 = (np.log(S / K) + (r + 0.5 * sigma ** 2) * T) / (sigma * np.sqrt(T))
        gamma = norm.pdf(d1) / (S * sigma * np.sqrt(T))
        
        return gamma
    
    def calculate_theta(self, S: float, K: float, T: float, 
                       r: float, sigma: float, option_type: str = 'call') -> float:
        """Calculate option theta (time decay)"""
        if T <= 0 or sigma <= 0:
            return 0.0
        
        d1 = (np.log(S / K) + (r + 0.5 * sigma ** 2) * T) / (sigma * np.sqrt(T))
        d2 = d1 - sigma * np.sqrt(T)
        
        first_term = -(S * norm.pdf(d1) * sigma) / (2 * np.sqrt(T))
        
        if option_type == 'call':
            second_term = -r * K * np.exp(-r * T) * norm.cdf(d2)
            theta = (first_term + second_term) / 365
        else:  # put
            second_term = r * K * np.exp(-r * T) * norm.cdf(-d2)
            theta = (first_term + second_term) / 365
        
        return theta
    
    def detect_volatility_spread(self, symbol: str, current_price: float,
                                option_price: float, strike: float, 
                                time_to_expiry: float) -> Optional[Dict]:
        """
        Detect arbitrage opportunity in volatility spread
        
        Args:
            symbol: Trading symbol
            current_price: Current asset price
            option_price: Current option price
            strike: Option strike price
            time_to_expiry: Time to expiration (years)
            
        Returns:
            Trading signal or None
        """
        # Calculate historical volatility
        if symbol not in self.price_history or len(self.price_history[symbol]) < 10:
            return None
        
        hist_vol = self.calculate_historical_volatility(self.price_history[symbol])
        self.historical_vol[symbol] = hist_vol
        
        # Calculate implied volatility
        impl_vol = self.calculate_implied_volatility(
            option_price, current_price, strike, 
            time_to_expiry, self.risk_free_rate
        )
        self.implied_vol[symbol] = impl_vol
        
        # Calculate spread
        vol_spread = impl_vol - hist_vol
        self.vol_spread[symbol] = vol_spread
        
        # Generate signals
        if vol_spread > self.vol_threshold:
            # Implied vol too high - sell options (sell volatility)
            signal = {
                'type': 'VOL_ARB_SELL',
                'symbol': symbol,
                'price': current_price,
                'strike': strike,
                'hist_vol': hist_vol,
                'impl_vol': impl_vol,
                'spread': vol_spread,
                'action': 'SELL_OPTIONS',
                'hedge': 'BUY_UNDERLYING',
                'timestamp': datetime.now(),
                'greeks': {
                    'delta': self.calculate_delta(current_price, strike, time_to_expiry, 
                                                  self.risk_free_rate, impl_vol),
                    'gamma': self.calculate_gamma(current_price, strike, time_to_expiry,
                                                  self.risk_free_rate, impl_vol),
                    'vega': self.calculate_vega(current_price, strike, time_to_expiry,
                                               self.risk_free_rate, impl_vol),
                    'theta': self.calculate_theta(current_price, strike, time_to_expiry,
                                                 self.risk_free_rate, impl_vol)
                }
            }
            self.signals.append(signal)
            logger.info(f"Vol arb SELL signal: {symbol}, spread={vol_spread:.4f}")
            return signal
        
        elif vol_spread < -self.vol_threshold:
            # Implied vol too low - buy options (buy volatility)
            signal = {
                'type': 'VOL_ARB_BUY',
                'symbol': symbol,
                'price': current_price,
                'strike': strike,
                'hist_vol': hist_vol,
                'impl_vol': impl_vol,
                'spread': vol_spread,
                'action': 'BUY_OPTIONS',
                'hedge': 'SELL_UNDERLYING',
                'timestamp': datetime.now(),
                'greeks': {
                    'delta': self.calculate_delta(current_price, strike, time_to_expiry,
                                                  self.risk_free_rate, impl_vol),
                    'gamma': self.calculate_gamma(current_price, strike, time_to_expiry,
                                                  self.risk_free_rate, impl_vol),
                    'vega': self.calculate_vega(current_price, strike, time_to_expiry,
                                               self.risk_free_rate, impl_vol),
                    'theta': self.calculate_theta(current_price, strike, time_to_expiry,
                                                 self.risk_free_rate, impl_vol)
                }
            }
            self.signals.append(signal)
            logger.info(f"Vol arb BUY signal: {symbol}, spread={vol_spread:.4f}")
            return signal
        
        return None
    
    def update_price_history(self, symbol: str, price: float):
        """Update price history"""
        self.price_history[symbol].append(price)
        
        if len(self.price_history[symbol]) > self.lookback_period:
            self.price_history[symbol] = self.price_history[symbol][-self.lookback_period:]
    
    def get_statistics(self) -> Dict:
        """Get strategy statistics"""
        return {
            'total_signals': len(self.signals),
            'buy_vol_signals': sum(1 for s in self.signals if s['type'] == 'VOL_ARB_BUY'),
            'sell_vol_signals': sum(1 for s in self.signals if s['type'] == 'VOL_ARB_SELL'),
            'tracked_symbols': len(self.price_history),
            'avg_hist_vol': np.mean(list(self.historical_vol.values())) if self.historical_vol else 0,
            'avg_impl_vol': np.mean(list(self.implied_vol.values())) if self.implied_vol else 0
        }
