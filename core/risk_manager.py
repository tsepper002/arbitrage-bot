#!/usr/bin/env python3
"""
Multi-layer risk management system (A5).
Protects against excessive losses and anomalous conditions.
"""
import time
import logging
from typing import Dict, Optional, Tuple
from datetime import datetime, timedelta
import settings

logger = logging.getLogger("risk_manager")


class RiskManager:
    """
    Multi-layer risk guard with configurable limits.
    
    Implements Strategy A5:
    - MAX_DAILY_LOSS: Stop trading for 24h
    - MAX_SINGLE_TRADE_LOSS: Cancel individual trades
    - MAX_HOURLY_LOSS: Pause for 1h
    - MAX_OPEN_EXPOSURE: Limit total position value
    - MAX_CONSECUTIVE_LOSSES: Pause after N losses
    - ANOMALOUS_SPREAD_PCT: Skip likely data errors
    - MAX_DATA_AGE_SEC: Don't trade on stale data
    - MIN_BALANCE_PER_EXCHANGE: Exclude low-balance exchanges
    """
    
    MAX_ADVERSE_MOVE_PCT = 2.0  # Worst-case execution adverse move for arb

    def __init__(self):
        # Daily tracking
        self.daily_pnl = 0.0
        self.daily_trades = 0
        self.daily_reset_time = self._get_next_reset_time()
        
        # Hourly tracking
        self.hourly_pnl = 0.0
        self.hourly_reset_time = time.time() + 3600
        
        # Consecutive losses
        self.consecutive_losses = 0
        self.last_loss_time = 0.0  # Top bots: reset after 1h even without profit
        
        # Open exposure
        self.open_exposure = 0.0
        
        # Pause states
        self.paused_until: Optional[float] = None
        self.pause_reason: Optional[str] = None
        
        # Exchange balances (updated externally)
        self.exchange_balances: Dict[str, float] = {}
        
        logger.info("RiskManager initialized with limits:")
        logger.info(f"  MAX_DAILY_LOSS: ${settings.MAX_DAILY_LOSS}")
        logger.info(f"  MAX_HOURLY_LOSS: ${settings.MAX_HOURLY_LOSS}")
        logger.info(f"  MAX_SINGLE_TRADE_LOSS: ${settings.MAX_SINGLE_TRADE_LOSS}")
        logger.info(f"  MAX_OPEN_EXPOSURE: ${settings.MAX_OPEN_EXPOSURE}")
        logger.info(f"  MAX_CONSECUTIVE_LOSSES: {settings.MAX_CONSECUTIVE_LOSSES}")
    
    def _get_next_reset_time(self) -> float:
        """Get timestamp for next daily reset (midnight UTC)."""
        now = datetime.utcnow()
        tomorrow = now + timedelta(days=1)
        midnight = datetime(tomorrow.year, tomorrow.month, tomorrow.day)
        return midnight.timestamp()
    
    def _check_daily_reset(self):
        """Reset daily counters if needed."""
        now = time.time()
        if now >= self.daily_reset_time:
            # Only log once per actual reset (not per call)
            if self.daily_pnl != 0.0 or self.daily_trades > 0:
                logger.info(f"Daily reset: PnL was ${self.daily_pnl:.2f}, trades: {self.daily_trades}")
            self.daily_pnl = 0.0
            self.daily_trades = 0
            self.daily_reset_time = self._get_next_reset_time()
            # Clear pause if it was daily loss related
            if self.paused_until and "daily loss" in (self.pause_reason or "").lower():
                self.paused_until = None
                self.pause_reason = None
    
    def _check_hourly_reset(self):
        """Reset hourly counters if needed."""
        now = time.time()
        if now >= self.hourly_reset_time:
            if self.hourly_pnl < 0:
                logger.info(f"Hourly reset: PnL was ${self.hourly_pnl:.2f}")
            self.hourly_pnl = 0.0
            self.hourly_reset_time = now + 3600
            # Clear pause if it was hourly loss related
            if self.paused_until and "hourly loss" in (self.pause_reason or "").lower():
                self.paused_until = None
                self.pause_reason = None
    
    def is_trading_allowed(self) -> Tuple[bool, Optional[str]]:
        """
        Check if trading is currently allowed.
        
        Returns:
            (allowed, reason) - reason is None if allowed
        """
        # Check time-based resets
        self._check_daily_reset()
        self._check_hourly_reset()
        
        # Check if paused
        if self.paused_until:
            now = time.time()
            if now < self.paused_until:
                remaining = int(self.paused_until - now)
                return False, f"Trading paused: {self.pause_reason} (resume in {remaining}s)"
            else:
                # Pause expired
                logger.info(f"Pause expired: {self.pause_reason}")
                self.paused_until = None
                self.pause_reason = None
        
        # Check daily loss limit
        if self.daily_pnl <= -settings.MAX_DAILY_LOSS:
            self.paused_until = self.daily_reset_time
            self.pause_reason = f"Daily loss limit hit (${abs(self.daily_pnl):.2f})"
            logger.error(f"🔴 {self.pause_reason} - trading stopped until midnight UTC")
            return False, self.pause_reason
        
        # Check hourly loss limit
        if self.hourly_pnl <= -settings.MAX_HOURLY_LOSS:
            self.paused_until = time.time() + 3600
            self.pause_reason = f"Hourly loss limit hit (${abs(self.hourly_pnl):.2f})"
            logger.warning(f"🟡 {self.pause_reason} - pausing for 1 hour")
            return False, self.pause_reason
        
        # Check consecutive losses (with time-based decay like top bots)
        # Top bots reset consecutive loss counter after 1h even without profit
        if self.consecutive_losses >= settings.MAX_CONSECUTIVE_LOSSES:
            if self.last_loss_time > 0 and (time.time() - self.last_loss_time) > 3600:
                logger.info(f"✅ Consecutive loss counter reset (1h elapsed since last loss)")
                self.consecutive_losses = 0
            else:
                self.paused_until = time.time() + 900  # 15 minutes
                self.pause_reason = f"Consecutive losses ({self.consecutive_losses})"
                logger.warning(f"🟡 {self.pause_reason} - pausing for 15 minutes")
                return False, self.pause_reason
        
        # Check open exposure
        if self.open_exposure >= settings.MAX_OPEN_EXPOSURE:
            return False, f"Max open exposure reached (${self.open_exposure:.2f})"
        
        return True, None
    
    def check_can_trade(self, opportunity: Dict) -> Tuple[bool, Optional[str]]:
        """
        Check if a specific trading opportunity is allowed.
        
        Args:
            opportunity: Dict with trade details
            
        Returns:
            (can_trade, reason) - reason is None if allowed
        """
        # First check if trading is globally allowed
        allowed, reason = self.is_trading_allowed()
        if not allowed:
            return False, reason
        
        # Check for anomalous spreads (likely data errors)
        roi_pct = opportunity.get('roi_pct', 0)
        if abs(roi_pct) > settings.ANOMALOUS_SPREAD_PCT:
            return False, f"Anomalous spread: {roi_pct:.2f}% (max: {settings.ANOMALOUS_SPREAD_PCT}%)"
        
        # Check trade amount
        buy_price = opportunity.get('buy_avg', opportunity.get('buy_price', 0))
        qty = opportunity.get('qty', 0)
        if buy_price <= 0 or qty <= 0:
            return False, f"Invalid trade: buy_price={buy_price}, qty={qty}"
        amount = buy_price * qty
        
        return self.can_trade_amount(amount)
    
    def can_trade_amount(self, amount: float) -> Tuple[bool, Optional[str]]:
        """
        Check if a specific trade amount is allowed.
        
        Args:
            amount: Trade size in USDT
            
        Returns:
            (allowed, reason)
        """
        # Check if trading is allowed at all
        allowed, reason = self.is_trading_allowed()
        if not allowed:
            return False, reason
        
        # Check single trade loss limit
        # In arbitrage, max loss ≈ amount × slippage + fees (not full spread)
        # Top bots (Hummingbot): max_loss = amount × (max_slippage_pct/100 + total_fee_pct)
        # Conservative: assume worst case 2% adverse move during execution
        max_loss_pct = min(settings.ANOMALOUS_SPREAD_PCT, self.MAX_ADVERSE_MOVE_PCT)
        max_possible_loss = amount * (max_loss_pct / 100.0)
        if max_possible_loss > settings.MAX_SINGLE_TRADE_LOSS:
            return False, f"Potential loss (${max_possible_loss:.2f}) exceeds max single trade limit (${settings.MAX_SINGLE_TRADE_LOSS:.2f})"
        
        # Check if would exceed open exposure
        if self.open_exposure + amount > settings.MAX_OPEN_EXPOSURE:
            available = settings.MAX_OPEN_EXPOSURE - self.open_exposure
            return False, f"Would exceed max exposure (available: ${available:.2f})"
        
        return True, None
    
    def can_trade_on_exchange(self, exchange: str) -> Tuple[bool, Optional[str]]:
        """
        Check if trading is allowed on a specific exchange.
        
        Args:
            exchange: Exchange name
            
        Returns:
            (allowed, reason)
        """
        balance = self.exchange_balances.get(exchange, 0.0)
        if balance < settings.MIN_BALANCE_PER_EXCHANGE:
            return False, f"Insufficient balance on {exchange} (${balance:.2f} < ${settings.MIN_BALANCE_PER_EXCHANGE})"
        return True, None
    
    def is_data_fresh(self, timestamp: float) -> bool:
        """
        Check if data is fresh enough to trade on.
        
        Args:
            timestamp: Data timestamp
            
        Returns:
            True if fresh, False if stale
        """
        age = time.time() - timestamp
        return age <= settings.MAX_DATA_AGE_SEC
    
    def is_spread_normal(self, spread_pct: float) -> bool:
        """
        Check if spread is within normal range (not anomalous).
        
        Args:
            spread_pct: Spread percentage
            
        Returns:
            True if normal, False if anomalous
        """
        return spread_pct <= settings.ANOMALOUS_SPREAD_PCT
    
    def record_trade(self, trade_info: Dict):
        """
        Record a completed trade from trade_info dict.
        
        Args:
            trade_info: Dict containing trade details (net_profit, exposure, etc.)
        """
        pnl = trade_info.get('net_profit', 0.0)
        
        # Calculate exposure from trade info
        buy_price = trade_info.get('buy_price', 0.0)
        qty = trade_info.get('qty', 0.0)
        exposure = buy_price * qty if buy_price and qty else 0.0
        
        self.record_trade_result(pnl, exposure)
    
    def record_trade_result(self, pnl: float, exposure: float):
        """
        Record the result of a completed trade.
        
        Args:
            pnl: Profit/loss in USDT (positive or negative)
            exposure: Trade size in USDT
        """
        self.daily_pnl += pnl
        self.hourly_pnl += pnl
        self.daily_trades += 1
        
        # Track consecutive losses
        if pnl < 0:
            self.consecutive_losses += 1
            self.last_loss_time = time.time()
            logger.info(f"Loss recorded: ${pnl:.2f} (consecutive losses: {self.consecutive_losses})")
        else:
            self.consecutive_losses = 0  # Reset on profit
            logger.info(f"Profit recorded: ${pnl:.2f}")
        
        # Log summaries
        logger.info(f"Daily P&L: ${self.daily_pnl:.2f} ({self.daily_trades} trades)")
        logger.info(f"Hourly P&L: ${self.hourly_pnl:.2f}")
    
    def add_open_position(self, exposure: float):
        """Add to open exposure."""
        self.open_exposure += exposure
        logger.debug(f"Open exposure: ${self.open_exposure:.2f}")
    
    def remove_open_position(self, exposure: float):
        """Remove from open exposure."""
        self.open_exposure = max(0, self.open_exposure - exposure)
        logger.debug(f"Open exposure: ${self.open_exposure:.2f}")
    
    def update_exchange_balance(self, exchange: str, balance: float):
        """Update tracked balance for an exchange."""
        self.exchange_balances[exchange] = balance
        logger.debug(f"{exchange} balance: ${balance:.2f}")
    
    def get_status(self) -> Dict:
        """Get current risk manager status."""
        self._check_daily_reset()
        self._check_hourly_reset()
        
        allowed, reason = self.is_trading_allowed()
        
        return {
            "trading_allowed": allowed,
            "pause_reason": reason,
            "daily_pnl": self.daily_pnl,
            "daily_trades": self.daily_trades,
            "hourly_pnl": self.hourly_pnl,
            "consecutive_losses": self.consecutive_losses,
            "open_exposure": self.open_exposure,
            "exchange_balances": self.exchange_balances.copy(),
        }


# Factory function for easy initialization
_risk_manager_instance = None

def get_risk_manager() -> RiskManager:
    """Get or create RiskManager singleton."""
    global _risk_manager_instance
    if _risk_manager_instance is None:
        _risk_manager_instance = RiskManager()
    return _risk_manager_instance
