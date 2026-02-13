"""Strategy combiner for multi-strategy execution."""
import logging

logger = logging.getLogger(__name__)

class StrategyCombiner:
    def __init__(self, strategies):
        self.strategies = strategies
        self.weights = {s: 1.0 for s in strategies}
        self.logger = logging.getLogger(__name__)
    
    def combine_signals(self, market_data):
        signals = []
        for strategy in self.strategies:
            signal = strategy.generate_signal(market_data)
            if signal:
                signals.append(signal)
        
        if not signals:
            return None
        
        # Weighted average
        total_weight = sum(self.weights.values())
        combined_score = sum(
            s.get('score', 0) * self.weights.get(s['strategy'], 1.0)
            for s in signals
        ) / total_weight
        
        return {'score': combined_score, 'signals': signals}
