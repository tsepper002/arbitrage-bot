"""
On-chain Analyzer for Cryptocurrency
Tracks whale wallets, exchange flows, and network metrics
"""
import logging
from typing import Dict, List, Optional
from datetime import datetime, timedelta
from collections import defaultdict

logger = logging.getLogger(__name__)


class OnchainAnalyzer:
    """Analyzes on-chain metrics and whale activity"""
    
    def __init__(self):
        self.whale_wallets = set()
        self.exchange_wallets = {}
        self.transaction_history = []
        self.whale_threshold = 100  # BTC or equivalent
        
    async def track_whale_wallets(self, symbol: str) -> Dict:
        """
        Track large wallet movements
        
        Args:
            symbol: Cryptocurrency symbol
            
        Returns:
            Whale activity data
        """
        try:
            # In production, would query blockchain APIs
            whale_movements = self._get_whale_movements(symbol)
            
            accumulation = 0
            distribution = 0
            
            for movement in whale_movements:
                if movement['type'] == 'accumulation':
                    accumulation += movement['amount']
                else:
                    distribution += movement['amount']
            
            net_flow = accumulation - distribution
            
            signal = self._generate_whale_signal(net_flow, accumulation + distribution)
            
            return {
                'symbol': symbol,
                'timestamp': datetime.now().isoformat(),
                'accumulation': accumulation,
                'distribution': distribution,
                'net_flow': net_flow,
                'whale_count': len(whale_movements),
                'signal': signal
            }
            
        except Exception as e:
            logger.error(f"Error tracking whale wallets: {e}")
            return {}
    
    def _get_whale_movements(self, symbol: str) -> List[Dict]:
        """Get recent whale movements (mock data)"""
        # In production, would fetch from blockchain
        return [
            {'type': 'accumulation', 'amount': 500, 'wallet': 'whale1'},
            {'type': 'distribution', 'amount': 300, 'wallet': 'whale2'},
            {'type': 'accumulation', 'amount': 200, 'wallet': 'whale3'}
        ]
    
    def _generate_whale_signal(self, net_flow: float, total_volume: float) -> str:
        """Generate signal from whale activity"""
        if total_volume == 0:
            return 'NEUTRAL'
        
        ratio = net_flow / total_volume
        
        if ratio > 0.3:
            return 'STRONG_ACCUMULATION'
        elif ratio > 0.1:
            return 'ACCUMULATION'
        elif ratio < -0.3:
            return 'STRONG_DISTRIBUTION'
        elif ratio < -0.1:
            return 'DISTRIBUTION'
        else:
            return 'NEUTRAL'
    
    async def monitor_exchange_flows(self, symbol: str) -> Dict:
        """
        Monitor inflows and outflows from exchanges
        
        Args:
            symbol: Cryptocurrency symbol
            
        Returns:
            Exchange flow data
        """
        try:
            inflow = self._get_exchange_inflow(symbol)
            outflow = self._get_exchange_outflow(symbol)
            
            net_flow = inflow - outflow
            
            # Positive net flow = more coins to exchanges (bearish)
            # Negative net flow = coins leaving exchanges (bullish)
            
            signal = 'BEARISH' if net_flow > 0 else 'BULLISH' if net_flow < 0 else 'NEUTRAL'
            
            return {
                'symbol': symbol,
                'timestamp': datetime.now().isoformat(),
                'inflow': inflow,
                'outflow': outflow,
                'net_flow': net_flow,
                'signal': signal
            }
            
        except Exception as e:
            logger.error(f"Error monitoring exchange flows: {e}")
            return {}
    
    def _get_exchange_inflow(self, symbol: str) -> float:
        """Get exchange inflow amount (mock)"""
        return 1000.0
    
    def _get_exchange_outflow(self, symbol: str) -> float:
        """Get exchange outflow amount (mock)"""
        return 1500.0
    
    async def analyze_network_metrics(self, symbol: str) -> Dict:
        """
        Analyze blockchain network metrics
        
        Args:
            symbol: Cryptocurrency symbol
            
        Returns:
            Network metrics data
        """
        try:
            metrics = {
                'symbol': symbol,
                'timestamp': datetime.now().isoformat(),
                'active_addresses': self._get_active_addresses(symbol),
                'transaction_count': self._get_transaction_count(symbol),
                'hash_rate': self._get_hash_rate(symbol),
                'difficulty': self._get_difficulty(symbol),
                'network_value': self._calculate_network_value(symbol)
            }
            
            metrics['health_score'] = self._calculate_network_health(metrics)
            
            return metrics
            
        except Exception as e:
            logger.error(f"Error analyzing network metrics: {e}")
            return {}
    
    def _get_active_addresses(self, symbol: str) -> int:
        """Get active address count (mock)"""
        return 50000
    
    def _get_transaction_count(self, symbol: str) -> int:
        """Get transaction count (mock)"""
        return 250000
    
    def _get_hash_rate(self, symbol: str) -> float:
        """Get network hash rate (mock)"""
        return 150.5  # EH/s
    
    def _get_difficulty(self, symbol: str) -> float:
        """Get mining difficulty (mock)"""
        return 25000000000000.0
    
    def _calculate_network_value(self, symbol: str) -> float:
        """Calculate network value metric (mock)"""
        return 800000000000.0  # USD
    
    def _calculate_network_health(self, metrics: Dict) -> float:
        """Calculate overall network health score (0-100)"""
        # Simple health score based on activity
        base_score = 50
        
        if metrics['active_addresses'] > 40000:
            base_score += 10
        if metrics['transaction_count'] > 200000:
            base_score += 10
        if metrics['hash_rate'] > 100:
            base_score += 10
            
        return min(base_score, 100)
    
    async def detect_large_transfers(self, symbol: str, threshold: float) -> List[Dict]:
        """
        Detect large on-chain transfers
        
        Args:
            symbol: Cryptocurrency symbol
            threshold: Minimum transfer amount to track
            
        Returns:
            List of large transfers
        """
        try:
            # In production, would query blockchain in real-time
            transfers = []
            
            # Mock data
            mock_transfers = [
                {'amount': 1000, 'from': 'whale_wallet', 'to': 'exchange', 'time': datetime.now()},
                {'amount': 500, 'from': 'exchange', 'to': 'unknown', 'time': datetime.now()}
            ]
            
            for transfer in mock_transfers:
                if transfer['amount'] >= threshold:
                    transfers.append({
                        'symbol': symbol,
                        'amount': transfer['amount'],
                        'from_type': self._classify_address(transfer['from']),
                        'to_type': self._classify_address(transfer['to']),
                        'timestamp': transfer['time'].isoformat()
                    })
            
            return transfers
            
        except Exception as e:
            logger.error(f"Error detecting large transfers: {e}")
            return []
    
    def _classify_address(self, address: str) -> str:
        """Classify wallet address type"""
        if 'exchange' in address.lower():
            return 'EXCHANGE'
        elif 'whale' in address.lower():
            return 'WHALE'
        else:
            return 'UNKNOWN'
    
    def get_onchain_stats(self) -> Dict:
        """Get on-chain analyzer statistics"""
        return {
            'tracked_wallets': len(self.whale_wallets),
            'transaction_history': len(self.transaction_history),
            'last_update': datetime.now().isoformat()
        }
