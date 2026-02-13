"""Correlation analysis for portfolio diversification."""
import logging
from typing import List, Dict
import numpy as np

logger = logging.getLogger(__name__)

class CorrelationAnalyzer:
    """Analyze correlations between assets."""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.price_history = {}
    
    def add_prices(self, symbol: str, prices: List[float]):
        """Add price history for symbol."""
        self.price_history[symbol] = prices
    
    def calculate_correlation_matrix(self) -> Dict:
        """Calculate correlation matrix."""
        symbols = list(self.price_history.keys())
        n = len(symbols)
        
        if n < 2:
            return {}
        
        matrix = {}
        for i, sym1 in enumerate(symbols):
            matrix[sym1] = {}
            for j, sym2 in enumerate(symbols):
                if i == j:
                    matrix[sym1][sym2] = 1.0
                else:
                    corr = self._calculate_correlation(
                        self.price_history[sym1],
                        self.price_history[sym2]
                    )
                    matrix[sym1][sym2] = corr
        
        return matrix
    
    def _calculate_correlation(self, x: List[float], y: List[float]) -> float:
        """Calculate Pearson correlation."""
        if len(x) != len(y) or len(x) < 2:
            return 0.0
        
        mean_x = sum(x) / len(x)
        mean_y = sum(y) / len(y)
        
        num = sum((x[i] - mean_x) * (y[i] - mean_y) for i in range(len(x)))
        den_x = (sum((xi - mean_x)**2 for xi in x)) ** 0.5
        den_y = (sum((yi - mean_y)**2 for yi in y)) ** 0.5
        
        if den_x == 0 or den_y == 0:
            return 0.0
        
        return num / (den_x * den_y)
    
    def find_low_correlation_pairs(self, threshold: float = 0.3) -> List:
        """Find pairs with low correlation for diversification."""
        matrix = self.calculate_correlation_matrix()
        pairs = []
        
        symbols = list(matrix.keys())
        for i, sym1 in enumerate(symbols):
            for sym2 in symbols[i+1:]:
                corr = matrix[sym1].get(sym2, 0)
                if abs(corr) < threshold:
                    pairs.append((sym1, sym2, corr))
        
        return sorted(pairs, key=lambda x: abs(x[2]))
