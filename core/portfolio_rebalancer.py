"""Portfolio rebalancer."""
import logging

logger = logging.getLogger(__name__)

class PortfolioRebalancer:
    def __init__(self, target_allocation):
        self.target_allocation = target_allocation
        self.logger = logging.getLogger(__name__)
    
    def calculate_rebalance(self, current_allocation):
        actions = []
        for asset, target in self.target_allocation.items():
            current = current_allocation.get(asset, 0)
            diff = target - current
            if abs(diff) > 0.05:  # 5% threshold
                actions.append({'asset': asset, 'amount': diff})
        return actions
