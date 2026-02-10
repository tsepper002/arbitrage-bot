#!/usr/bin/env python3
"""
State manager for persistent bot state (A6).
Saves and loads bot state to survive restarts.
"""
import json
import logging
import time
from typing import Dict, Any, Optional
import asyncio
import settings

logger = logging.getLogger("state_manager")


class StateManager:
    """
    Manages persistent bot state across restarts.
    
    A6 IMPLEMENTATION:
    - Saves state every 30s to JSON file
    - Tracks: daily P&L, trades, balances, pending orders, withdrawals
    - On startup: loads state, checks pending orders, restores daily P&L
    - Ensures continuity across crashes/restarts
    """
    
    def __init__(self, state_file: Optional[str] = None):
        """
        Initialize state manager.
        
        Args:
            state_file: Path to state file (default from settings)
        """
        self.state_file = state_file or settings.STATE_FILE_PATH
        self.state: Dict[str, Any] = self._get_default_state()
        self.last_save_time = 0.0
        self.save_interval = 30.0  # Save every 30 seconds
        self.auto_save_enabled = True
        
        logger.info(f"StateManager initialized with file: {self.state_file}")
    
    def _get_default_state(self) -> Dict[str, Any]:
        """Get default empty state."""
        return {
            "version": "1.0",
            "last_updated": 0.0,
            "daily_pnl": 0.0,
            "total_trades_today": 0,
            "daily_reset_timestamp": 0.0,
            "balances": {},  # exchange -> currency -> amount
            "pending_orders": [],  # list of order dicts
            "pending_withdrawals": [],  # list of withdrawal dicts
            "last_rebalance_timestamp": 0.0,
            "strategy_scores": {},  # strategy -> score dict
            "blocked_until": {},  # symbol/exchange -> timestamp
            "settings_overrides": {},  # runtime setting overrides
            "consecutive_losses": 0,
            "hourly_pnl": 0.0,
            "hourly_reset_timestamp": 0.0,
            "open_exposure": 0.0,
            "total_lifetime_pnl": 0.0,
            "total_lifetime_trades": 0,
        }
    
    def load_state(self) -> bool:
        """
        Load state from disk.
        
        Returns:
            True if loaded successfully, False otherwise
        """
        try:
            with open(self.state_file, 'r') as f:
                self.state = json.load(f)
            
            logger.info(f"✅ State loaded from {self.state_file}")
            logger.info(f"   Daily P&L: ${self.state.get('daily_pnl', 0):.2f}")
            logger.info(f"   Trades today: {self.state.get('total_trades_today', 0)}")
            logger.info(f"   Pending orders: {len(self.state.get('pending_orders', []))}")
            logger.info(f"   Last updated: {time.ctime(self.state.get('last_updated', 0))}")
            
            return True
        
        except FileNotFoundError:
            logger.info(f"No previous state file found, starting fresh")
            return False
        
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse state file: {e}")
            logger.info("Starting with clean state")
            return False
        
        except Exception as e:
            logger.exception(f"Error loading state: {e}")
            logger.info("Starting with clean state")
            return False
    
    def save_state(self) -> bool:
        """
        Save current state to disk.
        
        Returns:
            True if saved successfully, False otherwise
        """
        try:
            self.state["last_updated"] = time.time()
            
            # Write to temp file first, then rename (atomic on most systems)
            temp_file = f"{self.state_file}.tmp"
            with open(temp_file, 'w') as f:
                json.dump(self.state, f, indent=2)
            
            # Atomic rename
            import os
            if os.path.exists(self.state_file):
                os.replace(temp_file, self.state_file)
            else:
                os.rename(temp_file, self.state_file)
            
            self.last_save_time = time.time()
            logger.debug(f"State saved to {self.state_file}")
            
            return True
        
        except Exception as e:
            logger.exception(f"Error saving state: {e}")
            return False
    
    async def auto_save_loop(self):
        """Automatically save state every N seconds."""
        logger.info(f"Auto-save loop started (interval: {self.save_interval}s)")
        
        while self.auto_save_enabled:
            await asyncio.sleep(self.save_interval)
            if self.auto_save_enabled:
                self.save_state()
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get a value from state."""
        return self.state.get(key, default)
    
    def set(self, key: str, value: Any):
        """Set a value in state."""
        self.state[key] = value
    
    def update(self, updates: Dict[str, Any]):
        """Update multiple values in state."""
        self.state.update(updates)
    
    # Convenience methods for common operations
    
    def get_daily_pnl(self) -> float:
        """Get today's P&L."""
        return self.state.get("daily_pnl", 0.0)
    
    def set_daily_pnl(self, pnl: float):
        """Set today's P&L."""
        self.state["daily_pnl"] = pnl
    
    def add_to_daily_pnl(self, amount: float):
        """Add to today's P&L."""
        self.state["daily_pnl"] = self.state.get("daily_pnl", 0.0) + amount
        self.state["total_lifetime_pnl"] = self.state.get("total_lifetime_pnl", 0.0) + amount
    
    def increment_trades(self):
        """Increment trade counters."""
        self.state["total_trades_today"] = self.state.get("total_trades_today", 0) + 1
        self.state["total_lifetime_trades"] = self.state.get("total_lifetime_trades", 0) + 1
    
    def get_balance(self, exchange: str, currency: str) -> float:
        """Get balance for exchange and currency."""
        return self.state.get("balances", {}).get(exchange, {}).get(currency, 0.0)
    
    def set_balance(self, exchange: str, currency: str, amount: float):
        """Set balance for exchange and currency."""
        if "balances" not in self.state:
            self.state["balances"] = {}
        if exchange not in self.state["balances"]:
            self.state["balances"][exchange] = {}
        self.state["balances"][exchange][currency] = amount
    
    def add_pending_order(self, order: Dict[str, Any]):
        """Add an order to pending orders list."""
        if "pending_orders" not in self.state:
            self.state["pending_orders"] = []
        order["added_at"] = time.time()
        self.state["pending_orders"].append(order)
        logger.info(f"Added pending order: {order.get('order_id', 'unknown')}")
    
    def remove_pending_order(self, order_id: str):
        """Remove an order from pending orders list."""
        if "pending_orders" in self.state:
            self.state["pending_orders"] = [
                o for o in self.state["pending_orders"]
                if o.get("order_id") != order_id
            ]
            logger.info(f"Removed pending order: {order_id}")
    
    def get_pending_orders(self) -> list:
        """Get list of pending orders."""
        return self.state.get("pending_orders", [])
    
    def add_pending_withdrawal(self, withdrawal: Dict[str, Any]):
        """Add a withdrawal to pending withdrawals list."""
        if "pending_withdrawals" not in self.state:
            self.state["pending_withdrawals"] = []
        withdrawal["added_at"] = time.time()
        self.state["pending_withdrawals"].append(withdrawal)
        logger.info(f"Added pending withdrawal: {withdrawal.get('withdrawal_id', 'unknown')}")
    
    def remove_pending_withdrawal(self, withdrawal_id: str):
        """Remove a withdrawal from pending withdrawals list."""
        if "pending_withdrawals" in self.state:
            self.state["pending_withdrawals"] = [
                w for w in self.state["pending_withdrawals"]
                if w.get("withdrawal_id") != withdrawal_id
            ]
            logger.info(f"Removed pending withdrawal: {withdrawal_id}")
    
    def get_pending_withdrawals(self) -> list:
        """Get list of pending withdrawals."""
        return self.state.get("pending_withdrawals", [])
    
    def should_check_daily_reset(self) -> bool:
        """Check if daily reset time has passed."""
        reset_time = self.state.get("daily_reset_timestamp", 0.0)
        return time.time() >= reset_time
    
    def reset_daily_counters(self, next_reset_timestamp: float):
        """Reset daily counters."""
        self.state["daily_pnl"] = 0.0
        self.state["total_trades_today"] = 0
        self.state["consecutive_losses"] = 0
        self.state["daily_reset_timestamp"] = next_reset_timestamp
        logger.info(f"Daily counters reset, next reset at {time.ctime(next_reset_timestamp)}")
    
    def get_statistics(self) -> Dict:
        """Get state statistics."""
        return {
            "state_file": self.state_file,
            "last_save_time": self.last_save_time,
            "daily_pnl": self.get_daily_pnl(),
            "trades_today": self.state.get("total_trades_today", 0),
            "pending_orders": len(self.get_pending_orders()),
            "pending_withdrawals": len(self.get_pending_withdrawals()),
            "total_lifetime_pnl": self.state.get("total_lifetime_pnl", 0.0),
            "total_lifetime_trades": self.state.get("total_lifetime_trades", 0),
        }
