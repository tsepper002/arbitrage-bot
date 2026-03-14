"""Fee optimizer for maker/taker selection and VIP tier optimization."""
import logging
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
import numpy as np

logger = logging.getLogger(__name__)

class FeeOptimizer:
    """Optimize trading fees through smart order type selection and VIP tier management."""
    
    def __init__(self, config: Optional[Dict] = None):
        self.logger = logging.getLogger(__name__)
        self.config = config or {}
        self.fee_structures = {}
        self.trading_volumes = {}
        self.fee_history = []
        self.vip_tiers = {}
        self._load_fee_structures()
        
    def _load_fee_structures(self):
        """Load fee structures for different exchanges."""
        # Base-tier fee structures (no VIP, no exchange tokens, no BNB/KCS/MX)
        # Last verified: Feb 2026
        self.fee_structures = {
            'binance': {
                'maker': 0.001,   # 0.10% (no BNB discount)
                'taker': 0.001,   # 0.10% (no BNB discount)
                'vip_tiers': {
                    0: {'maker': 0.001, 'taker': 0.001, 'volume_30d': 0},
                    1: {'maker': 0.0009, 'taker': 0.001, 'volume_30d': 50},
                    2: {'maker': 0.0008, 'taker': 0.0009, 'volume_30d': 500},
                    3: {'maker': 0.0007, 'taker': 0.0008, 'volume_30d': 2000},
                }
            },
            'bybit': {
                'maker': 0.001,   # 0.10% (base tier, no rebate)
                'taker': 0.001,   # 0.10% (base tier)
                'vip_tiers': {
                    0: {'maker': 0.001, 'taker': 0.001, 'volume_30d': 0},
                    1: {'maker': 0.0008, 'taker': 0.001, 'volume_30d': 100},
                    2: {'maker': 0.0006, 'taker': 0.0008, 'volume_30d': 500},
                }
            },
            'kucoin': {
                'maker': 0.001,   # 0.10% (no KCS discount)
                'taker': 0.001,   # 0.10% (no KCS discount)
                'vip_tiers': {
                    0: {'maker': 0.001, 'taker': 0.001, 'volume_30d': 0},
                }
            },
            'htx': {
                'maker': 0.002,   # 0.20% (base tier)
                'taker': 0.002,   # 0.20% (base tier)
                'vip_tiers': {
                    0: {'maker': 0.002, 'taker': 0.002, 'volume_30d': 0},
                }
            },
            'mexc': {
                'maker': 0.000,   # 0.00% (free for all)
                'taker': 0.0005,  # 0.05% (base tier, no MX discount)
                'vip_tiers': {
                    0: {'maker': 0.000, 'taker': 0.0005, 'volume_30d': 0},
                }
            },
        }
    
    def select_order_type(self, urgency: float, spread: float, 
                          exchange: str, symbol: str) -> Dict:
        """Select optimal order type based on urgency and market conditions."""
        fee_data = self.fee_structures.get(exchange, {})
        maker_fee = fee_data.get('maker', 0.001)
        taker_fee = fee_data.get('taker', 0.001)
        
        # Calculate cost difference
        fee_diff = taker_fee - maker_fee
        
        # If spread is wider than fee difference, maker is always better
        if spread > fee_diff and urgency < 0.7:
            return {
                'order_type': 'maker',
                'fee': maker_fee,
                'reason': 'spread_advantage',
                'expected_cost': maker_fee,
                'urgency': urgency
            }
        
        # High urgency: use taker
        if urgency > 0.7:
            return {
                'order_type': 'taker',
                'fee': taker_fee,
                'reason': 'high_urgency',
                'expected_cost': taker_fee,
                'urgency': urgency
            }
        
        # Medium urgency: probabilistic approach
        if urgency > 0.4:
            # Calculate expected cost with fill probability
            maker_fill_prob = 1.0 - urgency
            maker_expected = maker_fee * maker_fill_prob + taker_fee * (1 - maker_fill_prob)
            
            if maker_expected < taker_fee:
                return {
                    'order_type': 'maker',
                    'fee': maker_fee,
                    'reason': 'probabilistic_advantage',
                    'expected_cost': maker_expected,
                    'urgency': urgency,
                    'fill_prob': maker_fill_prob
                }
        
        # Default to maker for low urgency
        return {
            'order_type': 'maker',
            'fee': maker_fee,
            'reason': 'low_urgency',
            'expected_cost': maker_fee,
            'urgency': urgency
        }
    
    def calculate_optimal_fee(self, exchanges: List[str], 
                              symbol: str, amount: float) -> Tuple[str, Dict]:
        """Find exchange with lowest fee for given trade."""
        best_exchange = None
        best_fee_data = None
        lowest_cost = float('inf')
        
        for exchange in exchanges:
            fee_data = self.fee_structures.get(exchange, {})
            
            # Get current VIP tier
            current_tier = self._get_current_vip_tier(exchange)
            tier_data = fee_data.get('vip_tiers', {}).get(current_tier, {})
            
            # Calculate costs for both maker and taker
            maker_fee = tier_data.get('maker', fee_data.get('maker', 0.001))
            taker_fee = tier_data.get('taker', fee_data.get('taker', 0.001))
            
            # Use maker fee as default (assuming we can wait)
            cost = amount * abs(maker_fee)
            
            if cost < lowest_cost:
                lowest_cost = cost
                best_exchange = exchange
                best_fee_data = {
                    'exchange': exchange,
                    'maker_fee': maker_fee,
                    'taker_fee': taker_fee,
                    'cost': cost,
                    'vip_tier': current_tier,
                    'is_rebate': maker_fee < 0
                }
        
        return best_exchange, best_fee_data
    
    def _get_current_vip_tier(self, exchange: str) -> int:
        """Get current VIP tier for exchange."""
        return self.vip_tiers.get(exchange, 0)
    
    def optimize_vip_tier(self, exchange: str, 
                          projected_volume_30d: float) -> Dict:
        """Determine optimal VIP tier to target."""
        fee_data = self.fee_structures.get(exchange, {})
        tiers = fee_data.get('vip_tiers', {})
        
        current_tier = self._get_current_vip_tier(exchange)
        current_fees = tiers.get(current_tier, {})
        
        # Calculate savings for each tier
        tier_analysis = []
        for tier, tier_data in tiers.items():
            if tier <= current_tier:
                continue
                
            volume_needed = tier_data.get('volume_30d', 0)
            if projected_volume_30d < volume_needed:
                # Calculate additional volume needed
                additional_volume = volume_needed - projected_volume_30d
                
                # Estimate fee savings
                maker_savings = (current_fees.get('maker', 0.001) - 
                                 tier_data.get('maker', 0.001))
                taker_savings = (current_fees.get('taker', 0.001) - 
                                 tier_data.get('taker', 0.001))
                
                # Assuming 50/50 maker/taker split
                avg_savings = (maker_savings + taker_savings) / 2
                monthly_savings = projected_volume_30d * avg_savings
                
                # Cost of additional volume (in fees)
                additional_cost = additional_volume * current_fees.get('taker', 0.001)
                
                tier_analysis.append({
                    'tier': tier,
                    'volume_needed': volume_needed,
                    'additional_volume': additional_volume,
                    'monthly_savings': monthly_savings,
                    'additional_cost': additional_cost,
                    'net_benefit': monthly_savings - additional_cost,
                    'roi': (monthly_savings / additional_cost) if additional_cost > 0 else 0
                })
        
        if not tier_analysis:
            return {
                'current_tier': current_tier,
                'optimal_tier': current_tier,
                'recommendation': 'maintain',
                'reason': 'already_optimal_or_max_tier'
            }
        
        # Find tier with best ROI
        best_tier = max(tier_analysis, key=lambda x: x['roi'])
        
        if best_tier['roi'] > 1.5:  # 50% ROI threshold
            return {
                'current_tier': current_tier,
                'optimal_tier': best_tier['tier'],
                'recommendation': 'upgrade',
                'analysis': best_tier,
                'reason': 'positive_roi'
            }
        
        return {
            'current_tier': current_tier,
            'optimal_tier': current_tier,
            'recommendation': 'maintain',
            'reason': 'insufficient_roi',
            'best_alternative': best_tier
        }
    
    def calculate_rebate_potential(self, exchanges: List[str],
                                    trading_volume: Dict[str, float]) -> Dict:
        """Calculate potential rebate earnings from maker orders."""
        total_rebate = 0
        rebate_by_exchange = {}
        
        for exchange in exchanges:
            volume = trading_volume.get(exchange, 0)
            fee_data = self.fee_structures.get(exchange, {})
            
            tier = self._get_current_vip_tier(exchange)
            tier_data = fee_data.get('vip_tiers', {}).get(tier, {})
            maker_fee = tier_data.get('maker', fee_data.get('maker', 0.001))
            
            if maker_fee < 0:  # Rebate
                rebate = volume * abs(maker_fee)
                total_rebate += rebate
                rebate_by_exchange[exchange] = {
                    'volume': volume,
                    'maker_fee': maker_fee,
                    'rebate': rebate
                }
        
        return {
            'total_rebate': total_rebate,
            'by_exchange': rebate_by_exchange,
            'exchanges_with_rebates': len(rebate_by_exchange)
        }
    
    def record_trade_fee(self, exchange: str, symbol: str, 
                         amount: float, fee_paid: float, 
                         order_type: str) -> None:
        """Record a trade fee for analysis."""
        self.fee_history.append({
            'timestamp': datetime.now(),
            'exchange': exchange,
            'symbol': symbol,
            'amount': amount,
            'fee_paid': fee_paid,
            'order_type': order_type,
            'fee_rate': fee_paid / amount if amount > 0 else 0
        })
        
        # Update trading volumes
        if exchange not in self.trading_volumes:
            self.trading_volumes[exchange] = []
        self.trading_volumes[exchange].append({
            'timestamp': datetime.now(),
            'volume': amount
        })
        
        # Keep only last 30 days
        cutoff = datetime.now() - timedelta(days=30)
        self.trading_volumes[exchange] = [
            v for v in self.trading_volumes[exchange]
            if v['timestamp'] > cutoff
        ]
    
    def get_fee_statistics(self, days: int = 30) -> Dict:
        """Get fee statistics for recent period."""
        cutoff = datetime.now() - timedelta(days=days)
        recent_fees = [f for f in self.fee_history if f['timestamp'] > cutoff]
        
        if not recent_fees:
            return {'total_fees': 0, 'n_trades': 0}
        
        total_fees = sum(f['fee_paid'] for f in recent_fees)
        total_volume = sum(f['amount'] for f in recent_fees)
        
        maker_fees = [f for f in recent_fees if f['order_type'] == 'maker']
        taker_fees = [f for f in recent_fees if f['order_type'] == 'taker']
        
        return {
            'total_fees': total_fees,
            'total_volume': total_volume,
            'avg_fee_rate': total_fees / total_volume if total_volume > 0 else 0,
            'n_trades': len(recent_fees),
            'maker_trades': len(maker_fees),
            'taker_trades': len(taker_fees),
            'maker_pct': len(maker_fees) / len(recent_fees) if recent_fees else 0,
            'period_days': days
        }
