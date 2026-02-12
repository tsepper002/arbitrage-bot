"""Market adaptive strategy that adjusts to market conditions."""
import logging
from typing import Dict
from enum import Enum

logger = logging.getLogger(__name__)

class MarketRegime(Enum):
    TRENDING = "trending"
    RANGING = "ranging"
    VOLATILE = "volatile"

class MarketAdaptiveStrategy:
    """Strategy that adapts to market conditions."""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.current_regime = MarketRegime.RANGING
        self.parameters = {
            'threshold': 0.5,
            'lookback': 100,
            'sensitivity': 1.0
        }
    
    def detect_market_regime(self, prices: list) -> MarketRegime:
        """Detect current market regime."""
        if len(prices) < 2:
            return MarketRegime.RANGING
        
        # Calculate volatility
        returns = [prices[i] - prices[i-1] for i in range(1, len(prices))]
        volatility = np.std(returns) if returns else 0
        
        # Calculate trend
        trend = (prices[-1] - prices[0]) / prices[0] if prices[0] != 0 else 0
        
        if volatility > 0.05:
            return MarketRegime.VOLATILE
        elif abs(trend) > 0.03:
            return MarketRegime.TRENDING
        else:
            return MarketRegime.RANGING
    
    def adapt_parameters(self, regime: MarketRegime):
        """Adapt strategy parameters to market regime."""
        if regime == MarketRegime.TRENDING:
            self.parameters['threshold'] = 0.3
            self.parameters['sensitivity'] = 1.5
        elif regime == MarketRegime.VOLATILE:
            self.parameters['threshold'] = 0.7
            self.parameters['sensitivity'] = 0.5
        else:  # RANGING
            self.parameters['threshold'] = 0.5
            self.parameters['sensitivity'] = 1.0
        
        self.current_regime = regime
    
    def get_signal(self, market_data: Dict) -> Dict:
        """Generate trading signal based on current regime."""
        prices = market_data.get('prices', [])
        regime = self.detect_market_regime(prices)
        self.adapt_parameters(regime)
        
        return {
            'regime': regime.value,
            'parameters': self.parameters,
            'confidence': 0.8
        }
