"""Position manager."""
import logging

logger = logging.getLogger(__name__)

class PositionManager:
    def __init__(self):
        self.positions = {}
        self.logger = logging.getLogger(__name__)
    
    def open_position(self, symbol, amount, price):
        self.positions[symbol] = {'amount': amount, 'entry_price': price}
    
    def close_position(self, symbol, exit_price):
        if symbol in self.positions:
            pos = self.positions[symbol]
            pnl = (exit_price - pos['entry_price']) * pos['amount']
            del self.positions[symbol]
            return pnl
        return 0
    
    def get_pnl(self, symbol, current_price):
        if symbol not in self.positions:
            return 0
        pos = self.positions[symbol]
        return (current_price - pos['entry_price']) * pos['amount']
