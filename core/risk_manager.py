#!/usr/bin/env python3
"""
Risk Manager - Implements risk management rules and position limits.
Prevents over-exposure and enforces daily loss limits.
"""
import logging
import time
from typing import Dict, Optional, List, Tuple
from dataclasses import dataclass
from datetime import datetime, timedelta
import os

logger = logging.getLogger("risk_manager")


@dataclass
class Trade:
    """Record of a completed trade."""
    timestamp: float
    symbol: str
    buy_exchange: str
    sell_exchange: str
    quantity: float
    buy_price: float
    sell_price: float
    net_profit: float
    roi_pct: float


class RiskManager:
    """
    Manages trading risk with configurable limits.
    Tracks positions, losses, and enforces safety rules.
    """
    
    def __init__(self, total_capital: Optional[float] = None):
        """
        Initialize risk manager.
        
        Args:
            total_capital: Total capital in USDT (fetched from BalanceManager if None)
        """
        # Risk limits (configurable via environment variables)
        self.max_daily_loss_pct = float(os.getenv('ARB_MAX_DAILY_LOSS_PCT', '2.0'))  # 2% of capital
        self.max_single_trade_pct = float(os.getenv('ARB_MAX_SINGLE_TRADE_PCT', '5.0'))  # 5% of capital
        self.max_drawdown_pct = float(os.getenv('ARB_MAX_DRAWDOWN_PCT', '10.0'))  # 10% total
        self.max_exposure_per_exchange_pct = float(os.getenv('ARB_MAX_EXPOSURE_PER_EXCHANGE_PCT', '30.0'))  # 30% per exchange
        
        self.total_capital = total_capital or 1000.0  # Default $1000 if not specified
        
        # Trading state
        self.trades: List[Trade] = []
        self.daily_pnl = 0.0
        self.total_pnl = 0.0
        self.peak_equity = self.total_capital
        self.daily_reset_time = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        
        # Position tracking: {exchange: {symbol: net_position}}
        self.positions: Dict[str, Dict[str, float]] = {}
        
        # Exposure tracking: {exchange: total_exposure_usdt}
        self.exchange_exposure: Dict[str, float] = {}
        
        # Circuit breaker state
        self.is_paused = False
        self.pause_reason = None
        self.pause_until = None
        
        logger.info(f"RiskManager initialized: capital=${self.total_capital:.2f}, "
                   f"daily_loss_limit={self.max_daily_loss_pct}%, "
                   f"max_single_trade={self.max_single_trade_pct}%, "
                   f"max_drawdown={self.max_drawdown_pct}%")
    
    def update_capital(self, new_capital: float):
        """Update total capital (from BalanceManager)."""
        self.total_capital = new_capital
        if new_capital > self.peak_equity:
            self.peak_equity = new_capital
        logger.info(f"Updated capital: ${new_capital:.2f}")
    
    def _reset_daily_stats(self):
        """Reset daily statistics if new day."""
        now = datetime.now()
        reset_time = now.replace(hour=0, minute=0, second=0, microsecond=0)
        
        if reset_time > self.daily_reset_time:
            logger.info(f"Resetting daily stats. Previous day PnL: ${self.daily_pnl:.2f}")
            self.daily_pnl = 0.0
            self.daily_reset_time = reset_time
    
    def check_trade_allowed(self, symbol: str, buy_exchange: str, sell_exchange: str,
                           quantity: float, buy_price: float, sell_price: float,
                           expected_profit: float) -> Tuple[bool, Optional[str]]:
        """
        Check if a trade is allowed under current risk rules.
        
        Args:
            symbol: Trading pair
            buy_exchange: Exchange to buy from
            sell_exchange: Exchange to sell on
            quantity: Trade quantity
            buy_price: Buy price
            sell_price: Sell price
            expected_profit: Expected net profit in USDT
            
        Returns:
            (allowed, reason) tuple
        """
        self._reset_daily_stats()
        
        # Check if paused
        if self.is_paused:
            if self.pause_until and time.time() < self.pause_until:
                remaining = self.pause_until - time.time()
                return False, f"Trading paused: {self.pause_reason} (resume in {remaining:.0f}s)"
            else:
                # Auto-resume
                self.is_paused = False
                self.pause_reason = None
                self.pause_until = None
                logger.info("Auto-resuming trading after pause")
        
        # Calculate trade size
        trade_size_usdt = quantity * buy_price
        max_trade_size = self.total_capital * (self.max_single_trade_pct / 100.0)
        
        if trade_size_usdt > max_trade_size:
            return False, f"Trade size ${trade_size_usdt:.2f} exceeds limit ${max_trade_size:.2f} ({self.max_single_trade_pct}% of capital)"
        
        # Check daily loss limit
        max_daily_loss = self.total_capital * (self.max_daily_loss_pct / 100.0)
        if self.daily_pnl < -max_daily_loss:
            self.pause_trading("Daily loss limit reached", duration=3600 * 24)  # Pause until next day
            return False, f"Daily loss limit reached: ${self.daily_pnl:.2f} (limit: -${max_daily_loss:.2f})"
        
        # Check drawdown
        current_equity = self.total_capital + self.total_pnl
        drawdown_pct = ((self.peak_equity - current_equity) / self.peak_equity) * 100.0
        
        if drawdown_pct > self.max_drawdown_pct:
            self.pause_trading(f"Max drawdown {drawdown_pct:.1f}% exceeded", duration=3600)
            return False, f"Max drawdown exceeded: {drawdown_pct:.2f}% (limit: {self.max_drawdown_pct}%)"
        
        # Check exchange exposure limits
        buy_exposure = self.exchange_exposure.get(buy_exchange, 0.0) + trade_size_usdt
        max_exchange_exposure = self.total_capital * (self.max_exposure_per_exchange_pct / 100.0)
        
        if buy_exposure > max_exchange_exposure:
            return False, f"Exchange exposure limit: {buy_exchange} would have ${buy_exposure:.2f} (limit: ${max_exchange_exposure:.2f})"
        
        # All checks passed
        return True, None
    
    def record_trade(self, symbol: str, buy_exchange: str, sell_exchange: str,
                    quantity: float, buy_price: float, sell_price: float,
                    net_profit: float, roi_pct: float):
        """
        Record a completed trade and update statistics.
        
        Args:
            symbol: Trading pair
            buy_exchange: Exchange bought from
            sell_exchange: Exchange sold on
            quantity: Trade quantity
            buy_price: Actual buy price
            sell_price: Actual sell price
            net_profit: Actual net profit in USDT
            roi_pct: Return on investment percentage
        """
        trade = Trade(
            timestamp=time.time(),
            symbol=symbol,
            buy_exchange=buy_exchange,
            sell_exchange=sell_exchange,
            quantity=quantity,
            buy_price=buy_price,
            sell_price=sell_price,
            net_profit=net_profit,
            roi_pct=roi_pct
        )
        
        self.trades.append(trade)
        self.daily_pnl += net_profit
        self.total_pnl += net_profit
        
        # Update peak equity
        current_equity = self.total_capital + self.total_pnl
        if current_equity > self.peak_equity:
            self.peak_equity = current_equity
        
        # Update exposure
        trade_size = quantity * buy_price
        self.exchange_exposure[buy_exchange] = self.exchange_exposure.get(buy_exchange, 0.0) + trade_size
        self.exchange_exposure[sell_exchange] = self.exchange_exposure.get(sell_exchange, 0.0) + trade_size
        
        # Update positions
        if buy_exchange not in self.positions:
            self.positions[buy_exchange] = {}
        if sell_exchange not in self.positions:
            self.positions[sell_exchange] = {}
        
        # Net position accounting (simplified - assumes immediate execution)
        # In reality, this should track actual fills
        
        logger.info(f"Trade recorded: {symbol} {quantity:.6f} @ buy={buy_price:.2f} sell={sell_price:.2f} "
                   f"profit=${net_profit:.4f} ({roi_pct:.3f}%) | "
                   f"Daily PnL: ${self.daily_pnl:.2f}, Total PnL: ${self.total_pnl:.2f}")
    
    def pause_trading(self, reason: str, duration: Optional[float] = None):
        """
        Pause trading (circuit breaker).
        
        Args:
            reason: Reason for pause
            duration: Pause duration in seconds (None = manual resume required)
        """
        self.is_paused = True
        self.pause_reason = reason
        self.pause_until = time.time() + duration if duration else None
        
        logger.warning(f"🛑 Trading PAUSED: {reason}" + 
                      (f" (auto-resume in {duration:.0f}s)" if duration else " (manual resume required)"))
    
    def resume_trading(self):
        """Resume trading after pause."""
        if self.is_paused:
            logger.info("▶️  Trading RESUMED")
            self.is_paused = False
            self.pause_reason = None
            self.pause_until = None
    
    def get_statistics(self) -> Dict:
        """Get current risk statistics."""
        current_equity = self.total_capital + self.total_pnl
        drawdown_pct = ((self.peak_equity - current_equity) / self.peak_equity) * 100.0 if self.peak_equity > 0 else 0.0
        
        winning_trades = len([t for t in self.trades if t.net_profit > 0])
        losing_trades = len([t for t in self.trades if t.net_profit < 0])
        win_rate = (winning_trades / len(self.trades) * 100) if self.trades else 0.0
        
        return {
            'total_capital': self.total_capital,
            'total_pnl': self.total_pnl,
            'daily_pnl': self.daily_pnl,
            'current_equity': current_equity,
            'peak_equity': self.peak_equity,
            'drawdown_pct': drawdown_pct,
            'total_trades': len(self.trades),
            'winning_trades': winning_trades,
            'losing_trades': losing_trades,
            'win_rate': win_rate,
            'is_paused': self.is_paused,
            'pause_reason': self.pause_reason,
            'limits': {
                'max_daily_loss_pct': self.max_daily_loss_pct,
                'max_single_trade_pct': self.max_single_trade_pct,
                'max_drawdown_pct': self.max_drawdown_pct,
                'max_exposure_per_exchange_pct': self.max_exposure_per_exchange_pct
            }
        }
    
    def print_statistics(self):
        """Print risk statistics to console."""
        stats = self.get_statistics()
        
        print("\n" + "="*60)
        print("  Risk Manager Statistics")
        print("="*60)
        print(f"  Capital: ${stats['total_capital']:.2f}")
        print(f"  Total PnL: ${stats['total_pnl']:.2f}")
        print(f"  Daily PnL: ${stats['daily_pnl']:.2f}")
        print(f"  Current Equity: ${stats['current_equity']:.2f}")
        print(f"  Drawdown: {stats['drawdown_pct']:.2f}% (max: {stats['limits']['max_drawdown_pct']}%)")
        print(f"  Total Trades: {stats['total_trades']}")
        print(f"  Win Rate: {stats['win_rate']:.1f}% ({stats['winning_trades']}W / {stats['losing_trades']}L)")
        
        if stats['is_paused']:
            print(f"  Status: 🛑 PAUSED - {stats['pause_reason']}")
        else:
            print(f"  Status: ✅ ACTIVE")
        
        print("="*60 + "\n")
