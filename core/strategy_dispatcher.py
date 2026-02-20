"""
Strategy Dispatcher - Manages all 14 trading strategies

This module implements a two-tier scanning system:
- Fast strategies (0.15s): Arbitrage strategies that need speed
- Slow strategies (5 min): Position strategies that need time
"""

import asyncio
import logging
import time
from typing import Dict, List, Any, Optional

import settings

logger = logging.getLogger(__name__)


class StrategyDispatcher:
    """
    Dispatcher for all 14 trading strategies.
    Manages fast (arbitrage) and slow (position) strategy scanning.
    """
    
    def __init__(self, bot_manager):
        """
        Initialize the strategy dispatcher.
        
        Args:
            bot_manager: Reference to main bot manager
        """
        self.bot_manager = bot_manager
        self.last_slow_scan = 0
        self.slow_scan_interval = 300  # 5 minutes
        
        # Strategy performance tracking
        self.strategy_stats = {
            'CROSS_EXCHANGE': {'calls': 0, 'opportunities': 0},
            'TRIANGULAR': {'calls': 0, 'opportunities': 0},
            'SMART_ORDER': {'calls': 0, 'opportunities': 0},
            'VOLATILITY': {'calls': 0, 'opportunities': 0},
            'GRID_TRADING': {'calls': 0, 'opportunities': 0},
            'DCA': {'calls': 0, 'opportunities': 0},
            'MARKET_MAKING': {'calls': 0, 'opportunities': 0},
            'PAIRS_TRADING': {'calls': 0, 'opportunities': 0},
            'FUNDING_RATE': {'calls': 0, 'opportunities': 0},
            'VOLATILITY_ARB': {'calls': 0, 'opportunities': 0},
            'INDEX_ARB': {'calls': 0, 'opportunities': 0},
            'SPREAD_BETTING': {'calls': 0, 'opportunities': 0},
            'MOMENTUM': {'calls': 0, 'opportunities': 0},
            'BREAKOUT': {'calls': 0, 'opportunities': 0},
        }
        
        fast_names = ['CROSS_EXCHANGE', 'TRIANGULAR', 'SMART_ORDER', 'VOLATILITY']
        slow_names = [k for k in self.strategy_stats if k not in fast_names]
        logger.info(f"✅ StrategyDispatcher initialized with {len(self.strategy_stats)} strategies")
        logger.info(f"   Fast strategies ({len(fast_names)}): {', '.join(fast_names)}")
        logger.info(f"   Slow strategies ({len(slow_names)}): {', '.join(slow_names)}")
    
    async def scan_fast(self) -> List[Dict[str, Any]]:
        """
        Scan fast strategies (arbitrage).
        Called every scan loop (~0.15s).
        
        Returns:
            List of opportunities from fast strategies
        """
        opportunities = []
        
        try:
            # These are handled by ArbitrageEngine's existing methods
            # We just track them here for statistics
            self.strategy_stats['CROSS_EXCHANGE']['calls'] += 1
            self.strategy_stats['TRIANGULAR']['calls'] += 1
            self.strategy_stats['SMART_ORDER']['calls'] += 1
            self.strategy_stats['VOLATILITY']['calls'] += 1
            
            # Fast strategies are already integrated in ArbitrageEngine
            # This method exists for consistency and future expansion
            
        except Exception as e:
            logger.error(f"Error in fast strategy scan: {e}")
        
        return opportunities
    
    async def scan_slow(self) -> List[Dict[str, Any]]:
        """
        Scan slow strategies (position-based).
        Called every 5 minutes.
        
        Returns:
            List of opportunities from slow strategies
        """
        opportunities = []
        
        logger.info("⏰ Scanning 10 slow strategies...")
        
        try:
            # Grid Trading
            grid_opps = await self._scan_grid_trading()
            opportunities.extend(grid_opps)
            
            # DCA
            dca_opps = await self._scan_dca()
            opportunities.extend(dca_opps)
            
            # Market Making
            mm_opps = await self._scan_market_making()
            opportunities.extend(mm_opps)
            
            # Pairs Trading
            pairs_opps = await self._scan_pairs_trading()
            opportunities.extend(pairs_opps)
            
            # Funding Rate
            funding_opps = await self._scan_funding_rate()
            opportunities.extend(funding_opps)
            
            # Volatility Arbitrage
            vol_opps = await self._scan_volatility_arb()
            opportunities.extend(vol_opps)
            
            # Index Arbitrage
            index_opps = await self._scan_index_arb()
            opportunities.extend(index_opps)
            
            # Spread Betting
            spread_opps = await self._scan_spread_betting()
            opportunities.extend(spread_opps)
            
            # Momentum
            momentum_opps = await self._scan_momentum()
            opportunities.extend(momentum_opps)
            
            # Breakout
            breakout_opps = await self._scan_breakout()
            opportunities.extend(breakout_opps)
            
            logger.info(f"   ✅ Slow scan complete: {len(opportunities)} opportunities found")
            
        except Exception as e:
            logger.error(f"Error in slow strategy scan: {e}")
        
        self.last_slow_scan = time.time()
        return opportunities
    
    def should_scan_slow(self) -> bool:
        """Check if it's time for slow strategy scan."""
        return (time.time() - self.last_slow_scan) >= self.slow_scan_interval
    
    # Individual strategy scanners
    
    async def _scan_grid_trading(self) -> List[Dict[str, Any]]:
        """Scan for grid trading opportunities."""
        self.strategy_stats['GRID_TRADING']['calls'] += 1
        opportunities = []
        
        try:
            # Check if grid strategy exists in bot_manager
            if hasattr(self.bot_manager, 'grid_trading'):
                grid_strategy = self.bot_manager.grid_trading
                if hasattr(grid_strategy, 'check_positions'):
                    result = await grid_strategy.check_positions()
                    if result:
                        opportunities.append({
                            'strategy': 'GRID_TRADING',
                            'type': 'position',
                            'data': result
                        })
                        self.strategy_stats['GRID_TRADING']['opportunities'] += 1
        except Exception as e:
            logger.debug(f"Grid trading scan: {e}")
        
        return opportunities
    
    async def _scan_dca(self) -> List[Dict[str, Any]]:
        """Scan for DCA opportunities."""
        self.strategy_stats['DCA']['calls'] += 1
        opportunities = []
        
        try:
            if hasattr(self.bot_manager, 'dca_strategy'):
                dca_strategy = self.bot_manager.dca_strategy
                if hasattr(dca_strategy, 'should_buy'):
                    if await dca_strategy.should_buy():
                        opportunities.append({
                            'strategy': 'DCA',
                            'type': 'accumulation',
                            'data': {}
                        })
                        self.strategy_stats['DCA']['opportunities'] += 1
        except Exception as e:
            logger.debug(f"DCA scan: {e}")
        
        return opportunities
    
    async def _scan_market_making(self) -> List[Dict[str, Any]]:
        """Scan for market making opportunities."""
        self.strategy_stats['MARKET_MAKING']['calls'] += 1
        opportunities = []
        
        try:
            if hasattr(self.bot_manager, 'market_making'):
                mm_strategy = self.bot_manager.market_making
                if hasattr(mm_strategy, 'calculate_spread'):
                    spread = await mm_strategy.calculate_spread()
                    if spread and spread > 0.001:  # 0.1% min spread
                        opportunities.append({
                            'strategy': 'MARKET_MAKING',
                            'type': 'liquidity',
                            'data': {'spread': spread}
                        })
                        self.strategy_stats['MARKET_MAKING']['opportunities'] += 1
        except Exception as e:
            logger.debug(f"Market making scan: {e}")
        
        return opportunities
    
    async def _scan_pairs_trading(self) -> List[Dict[str, Any]]:
        """Scan for pairs trading opportunities."""
        self.strategy_stats['PAIRS_TRADING']['calls'] += 1
        opportunities = []
        
        try:
            if hasattr(self.bot_manager, 'pairs_trading'):
                pairs_strategy = self.bot_manager.pairs_trading
                if hasattr(pairs_strategy, 'find_divergence'):
                    result = await pairs_strategy.find_divergence()
                    if result:
                        opportunities.append({
                            'strategy': 'PAIRS_TRADING',
                            'type': 'correlation',
                            'data': result
                        })
                        self.strategy_stats['PAIRS_TRADING']['opportunities'] += 1
        except Exception as e:
            logger.debug(f"Pairs trading scan: {e}")
        
        return opportunities
    
    async def _scan_funding_rate(self) -> List[Dict[str, Any]]:
        """Scan for funding rate opportunities."""
        self.strategy_stats['FUNDING_RATE']['calls'] += 1
        opportunities = []
        
        try:
            if hasattr(self.bot_manager, 'funding_rate_enhanced'):
                funding_strategy = self.bot_manager.funding_rate_enhanced
                if hasattr(funding_strategy, 'check_funding_rates'):
                    result = await funding_strategy.check_funding_rates()
                    if result:
                        opportunities.append({
                            'strategy': 'FUNDING_RATE',
                            'type': 'funding',
                            'data': result
                        })
                        self.strategy_stats['FUNDING_RATE']['opportunities'] += 1
        except Exception as e:
            logger.debug(f"Funding rate scan: {e}")
        
        return opportunities
    
    async def _scan_volatility_arb(self) -> List[Dict[str, Any]]:
        """Scan for volatility arbitrage opportunities."""
        self.strategy_stats['VOLATILITY_ARB']['calls'] += 1
        opportunities = []
        
        try:
            if hasattr(self.bot_manager, 'volatility_arb'):
                vol_strategy = self.bot_manager.volatility_arb
                if hasattr(vol_strategy, 'detect_volatility_mispricing'):
                    result = await vol_strategy.detect_volatility_mispricing()
                    if result:
                        opportunities.append({
                            'strategy': 'VOLATILITY_ARB',
                            'type': 'volatility',
                            'data': result
                        })
                        self.strategy_stats['VOLATILITY_ARB']['opportunities'] += 1
        except Exception as e:
            logger.debug(f"Volatility arb scan: {e}")
        
        return opportunities
    
    async def _scan_index_arb(self) -> List[Dict[str, Any]]:
        """Scan for index arbitrage opportunities."""
        self.strategy_stats['INDEX_ARB']['calls'] += 1
        opportunities = []
        
        try:
            if hasattr(self.bot_manager, 'index_arb'):
                index_strategy = self.bot_manager.index_arb
                if hasattr(index_strategy, 'calculate_index_vs_components'):
                    result = await index_strategy.calculate_index_vs_components()
                    if result:
                        opportunities.append({
                            'strategy': 'INDEX_ARB',
                            'type': 'basket',
                            'data': result
                        })
                        self.strategy_stats['INDEX_ARB']['opportunities'] += 1
        except Exception as e:
            logger.debug(f"Index arb scan: {e}")
        
        return opportunities
    
    async def _scan_spread_betting(self) -> List[Dict[str, Any]]:
        """Scan for spread betting opportunities."""
        self.strategy_stats['SPREAD_BETTING']['calls'] += 1
        opportunities = []
        
        try:
            if hasattr(self.bot_manager, 'spread_betting'):
                spread_strategy = self.bot_manager.spread_betting
                if hasattr(spread_strategy, 'calculate_z_score'):
                    result = await spread_strategy.calculate_z_score()
                    if result and abs(result.get('z_score', 0)) > 2:
                        opportunities.append({
                            'strategy': 'SPREAD_BETTING',
                            'type': 'mean_reversion',
                            'data': result
                        })
                        self.strategy_stats['SPREAD_BETTING']['opportunities'] += 1
        except Exception as e:
            logger.debug(f"Spread betting scan: {e}")
        
        return opportunities
    
    async def _scan_momentum(self) -> List[Dict[str, Any]]:
        """Scan for momentum opportunities."""
        self.strategy_stats['MOMENTUM']['calls'] += 1
        opportunities = []
        
        try:
            if hasattr(self.bot_manager, 'momentum_strategy'):
                momentum_strategy = self.bot_manager.momentum_strategy
                if hasattr(momentum_strategy, 'calculate_rsi'):
                    result = await momentum_strategy.calculate_rsi()
                    if result:
                        rsi = result.get('rsi', 50)
                        if rsi < 30 or rsi > 70:  # Oversold or overbought
                            opportunities.append({
                                'strategy': 'MOMENTUM',
                                'type': 'trend',
                                'data': result
                            })
                            self.strategy_stats['MOMENTUM']['opportunities'] += 1
        except Exception as e:
            logger.debug(f"Momentum scan: {e}")
        
        return opportunities
    
    async def _scan_breakout(self) -> List[Dict[str, Any]]:
        """Scan for breakout opportunities."""
        self.strategy_stats['BREAKOUT']['calls'] += 1
        opportunities = []
        
        try:
            if hasattr(self.bot_manager, 'breakout_strategy'):
                breakout_strategy = self.bot_manager.breakout_strategy
                if hasattr(breakout_strategy, 'detect_breakout'):
                    result = await breakout_strategy.detect_breakout()
                    if result:
                        opportunities.append({
                            'strategy': 'BREAKOUT',
                            'type': 'technical',
                            'data': result
                        })
                        self.strategy_stats['BREAKOUT']['opportunities'] += 1
        except Exception as e:
            logger.debug(f"Breakout scan: {e}")
        
        return opportunities
    
    def print_stats(self):
        """Print strategy statistics."""
        logger.info("=" * 60)
        logger.info("STRATEGY DISPATCHER STATISTICS")
        logger.info("=" * 60)
        
        total_calls = sum(s['calls'] for s in self.strategy_stats.values())
        total_opps = sum(s['opportunities'] for s in self.strategy_stats.values())
        
        logger.info(f"Total Strategy Calls: {total_calls}")
        logger.info(f"Total Opportunities: {total_opps}")
        logger.info("")
        
        for strategy, stats in self.strategy_stats.items():
            if stats['calls'] > 0:
                hit_rate = (stats['opportunities'] / stats['calls'] * 100) if stats['calls'] > 0 else 0
                logger.info(f"{strategy:20} | Calls: {stats['calls']:6} | Opps: {stats['opportunities']:6} | Rate: {hit_rate:5.2f}%")
        
        logger.info("=" * 60)
