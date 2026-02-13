"""Price aggregator from multiple sources."""
import logging

logger = logging.getLogger(__name__)

class PriceAggregator:
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    def aggregate(self, prices):
        if not prices:
            return 0
        
        # Remove outliers
        sorted_prices = sorted(prices)
        n = len(sorted_prices)
        q1 = sorted_prices[n//4]
        q3 = sorted_prices[3*n//4]
        iqr = q3 - q1
        
        filtered = [p for p in prices if q1 - 1.5*iqr <= p <= q3 + 1.5*iqr]
        
        return sum(filtered) / len(filtered) if filtered else sum(prices) / len(prices)
