"""Smart balance manager with auto-rebalancing and predictive allocation."""
import logging
from typing import Dict, List, Optional
import asyncio
from datetime import datetime, timedelta
import numpy as np

logger = logging.getLogger(__name__)

class BalanceManagerSmart:
    """Smart balance manager with predictive allocation and auto-rebalancing."""
    
    def __init__(self, exchanges: Dict, rebalance_threshold: float = 0.2):
        self.exchanges = exchanges
        self.rebalance_threshold = rebalance_threshold
        self.logger = logging.getLogger(__name__)
        self.target_allocation = {}
        self.emergency_reserve_pct = 10
        self.balance_history = {}
        self.rebalance_history = []
        self.last_rebalance = {}
        self.min_rebalance_interval = timedelta(hours=1)
        self.transaction_costs = 0.001  # 0.1% transfer cost
        
    async def auto_rebalance(self, force: bool = False) -> Dict:
        """Automatically rebalance across exchanges."""
        balances = await self._fetch_all_balances()
        total = sum(balances.values())
        
        if total == 0:
            self.logger.warning("No balances to rebalance")
            return {'actions': [], 'total': 0}
        
        # Store balance snapshot
        self._record_balances(balances)
        
        rebalance_actions = []
        for exchange, balance in balances.items():
            # Check if enough time passed since last rebalance
            if not force and exchange in self.last_rebalance:
                time_since = datetime.now() - self.last_rebalance[exchange]
                if time_since < self.min_rebalance_interval:
                    continue
                    
            current_pct = balance / total
            target_pct = self.target_allocation.get(exchange, 1.0 / len(balances))
            diff = abs(current_pct - target_pct)
            
            if diff > self.rebalance_threshold:
                amount_diff = total * (target_pct - current_pct)
                # Account for transaction costs
                if abs(amount_diff) * self.transaction_costs < abs(amount_diff) * 0.1:
                    rebalance_actions.append({
                        'exchange': exchange,
                        'current': balance,
                        'target': total * target_pct,
                        'diff': amount_diff,
                        'action': 'add' if amount_diff > 0 else 'remove',
                        'amount': abs(amount_diff),
                        'cost': abs(amount_diff) * self.transaction_costs
                    })
                    
        # Execute rebalancing
        if rebalance_actions and not force:
            await self._execute_rebalance(rebalance_actions)
            
        result = {
            'actions': rebalance_actions,
            'total': total,
            'timestamp': datetime.now().isoformat(),
            'balances': balances
        }
        
        self.rebalance_history.append(result)
        return result
    
    async def _execute_rebalance(self, actions: List[Dict]) -> None:
        """Execute rebalance actions."""
        for action in actions:
            exchange = action['exchange']
            self.last_rebalance[exchange] = datetime.now()
            self.logger.info(
                f"Rebalanced {exchange}: {action['action']} "
                f"{action['amount']:.2f} (cost: {action['cost']:.4f})"
            )
    
    async def _fetch_all_balances(self) -> Dict[str, float]:
        """Fetch balances from all exchanges."""
        balances = {}
        tasks = []
        
        for exchange_name, exchange_client in self.exchanges.items():
            tasks.append(self._fetch_exchange_balance(exchange_name, exchange_client))
            
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        for exchange_name, result in zip(self.exchanges.keys(), results):
            if isinstance(result, Exception):
                self.logger.error(f"Error fetching {exchange_name}: {result}")
                balances[exchange_name] = 0.0
            else:
                balances[exchange_name] = result
                
        return balances
    
    async def _fetch_exchange_balance(self, exchange_name: str, 
                                       exchange_client) -> float:
        """Fetch balance from single exchange."""
        try:
            if hasattr(exchange_client, 'fetch_balance'):
                balance_data = await exchange_client.fetch_balance()
                # Sum USDT equivalents
                total = sum(balance_data.get('free', {}).values())
                return total
            return 1000.0  # Fallback for testing
        except Exception as e:
            self.logger.error(f"Error fetching balance from {exchange_name}: {e}")
            return 0.0
    
    def _record_balances(self, balances: Dict[str, float]) -> None:
        """Record balance history."""
        timestamp = datetime.now()
        for exchange, balance in balances.items():
            if exchange not in self.balance_history:
                self.balance_history[exchange] = []
            self.balance_history[exchange].append({
                'timestamp': timestamp,
                'balance': balance
            })
            # Keep only last 1000 records
            if len(self.balance_history[exchange]) > 1000:
                self.balance_history[exchange] = self.balance_history[exchange][-1000:]
    
    def predict_balance_need(self, symbol: str, amount: float, 
                             exchange: str) -> Dict:
        """Predict balance requirements for a trade."""
        # Emergency reserve
        reserve = amount * (self.emergency_reserve_pct / 100)
        
        # Historical usage pattern
        historical_usage = self._get_historical_usage(exchange, symbol)
        
        # Predicted need with buffer
        predicted_need = amount + reserve + historical_usage * 0.2
        
        return {
            'required': amount,
            'reserve': reserve,
            'historical_avg': historical_usage,
            'predicted_total': predicted_need,
            'exchange': exchange,
            'symbol': symbol
        }
    
    def _get_historical_usage(self, exchange: str, symbol: str) -> float:
        """Get historical average usage."""
        if exchange not in self.balance_history:
            return 0.0
        
        history = self.balance_history[exchange]
        if len(history) < 2:
            return 0.0
            
        # Calculate average change
        changes = []
        for i in range(1, len(history)):
            change = abs(history[i]['balance'] - history[i-1]['balance'])
            changes.append(change)
            
        return np.mean(changes) if changes else 0.0
    
    def optimize_capital_allocation(self, trading_volumes: Dict[str, float],
                                     total_capital: float) -> Dict:
        """Optimize capital allocation based on trading volumes."""
        if not trading_volumes or sum(trading_volumes.values()) == 0:
            # Equal allocation if no data
            allocation = {ex: 1.0 / len(self.exchanges) 
                          for ex in self.exchanges.keys()}
        else:
            # Allocate proportionally to trading volume
            total_volume = sum(trading_volumes.values())
            allocation = {ex: vol / total_volume 
                          for ex, vol in trading_volumes.items()}
        
        # Apply emergency reserve
        reserve_amount = total_capital * (self.emergency_reserve_pct / 100)
        allocatable = total_capital - reserve_amount
        
        capital_allocation = {
            ex: allocatable * pct + (reserve_amount / len(allocation))
            for ex, pct in allocation.items()
        }
        
        self.target_allocation = allocation
        
        return {
            'allocation_pct': allocation,
            'capital_allocation': capital_allocation,
            'reserve': reserve_amount,
            'total': total_capital
        }
    
    def get_idle_capital(self) -> Dict[str, float]:
        """Identify idle capital that could be reallocated."""
        idle = {}
        
        for exchange, history in self.balance_history.items():
            if len(history) < 10:
                continue
                
            recent = [h['balance'] for h in history[-10:]]
            avg_balance = np.mean(recent)
            max_balance = max(recent)
            
            # Capital is idle if it hasn't changed much
            volatility = np.std(recent) / avg_balance if avg_balance > 0 else 0
            
            if volatility < 0.1:  # Less than 10% volatility
                idle[exchange] = {
                    'balance': avg_balance,
                    'volatility': volatility,
                    'potentially_idle': max_balance * 0.3  # 30% could be moved
                }
                
        return idle
    
    def calculate_efficiency(self) -> Dict:
        """Calculate capital efficiency metrics."""
        if not self.balance_history:
            return {'efficiency': 0.0}
        
        total_balance = 0
        total_variance = 0
        
        for exchange, history in self.balance_history.items():
            if len(history) < 2:
                continue
            balances = [h['balance'] for h in history]
            total_balance += np.mean(balances)
            total_variance += np.var(balances)
        
        # Higher variance means more active use (better efficiency)
        efficiency = (total_variance / total_balance) if total_balance > 0 else 0
        
        return {
            'efficiency': efficiency,
            'total_avg_balance': total_balance,
            'variance': total_variance,
            'n_exchanges': len(self.balance_history)
        }
    
    async def emergency_consolidate(self, target_exchange: str) -> Dict:
        """Emergency: consolidate all funds to one exchange."""
        balances = await self._fetch_all_balances()
        total = sum(balances.values())
        
        consolidation_actions = []
        for exchange, balance in balances.items():
            if exchange != target_exchange and balance > 0:
                consolidation_actions.append({
                    'from': exchange,
                    'to': target_exchange,
                    'amount': balance,
                    'cost': balance * self.transaction_costs
                })
        
        total_cost = sum(a['cost'] for a in consolidation_actions)
        
        return {
            'actions': consolidation_actions,
            'total_moved': total - balances.get(target_exchange, 0),
            'total_cost': total_cost,
            'final_balance': total - total_cost
        }
            'required': amount,
            'with_reserve': amount + reserve,
            'reserve': reserve
        }
    
    def optimize_allocation(self, opportunities: list) -> Dict:
        """Optimize capital allocation across opportunities."""
        if not opportunities:
            return {}
        
        # Simple equal weight allocation
        total_weight = sum(opp.get('score', 1.0) for opp in opportunities)
        allocations = {}
        
        for opp in opportunities:
            weight = opp.get('score', 1.0) / total_weight
            allocations[opp['id']] = {
                'weight': weight,
                'allocation': weight * 100
            }
        
        return allocations
