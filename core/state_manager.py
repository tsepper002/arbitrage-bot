#!/usr/bin/env python3
"""
State Manager - Persistent state management for seamless 24/7 operation.
Saves and restores bot state to/from disk for crash recovery.
"""
import json
import logging
import os
import time
from typing import Dict, Optional, Any
from pathlib import Path
import asyncio

logger = logging.getLogger("state_manager")


class StateManager:
    """
    Manages persistent bot state across restarts.
    Enables seamless recovery and 24/7 operation.
    """
    
    def __init__(self, state_file: str = "data/state.json", save_interval: float = 30.0):
        """
        Initialize state manager.
        
        Args:
            state_file: Path to state file
            save_interval: Auto-save interval in seconds
        """
        self.state_file = Path(state_file)
        self.save_interval = save_interval
        
        # Ensure data directory exists
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        
        # State data
        self.state: Dict[str, Any] = {
            'bot_started': time.time(),
            'last_saved': None,
            'total_pnl': 0.0,
            'daily_pnl': 0.0,
            'total_trades': 0,
            'trade_history': [],
            'balances': {},
            'positions': {},
            'risk_stats': {},
            'config_snapshot': {},
            'uptime_seconds': 0.0,
        }
        
        # Auto-save task
        self._save_task = None
        self._stop_event = asyncio.Event()
        
        logger.info(f"StateManager initialized: state_file={self.state_file}, save_interval={save_interval}s")
    
    def load_state(self) -> bool:
        """
        Load state from disk.
        
        Returns:
            True if state was loaded successfully, False otherwise
        """
        if not self.state_file.exists():
            logger.info("No previous state file found - starting fresh")
            return False
        
        try:
            with open(self.state_file, 'r') as f:
                loaded_state = json.load(f)
            
            # Merge loaded state (preserve any new fields)
            for key, value in loaded_state.items():
                self.state[key] = value
            
            logger.info(f"State loaded from {self.state_file}")
            logger.info(f"  Total PnL: ${self.state['total_pnl']:.2f}")
            logger.info(f"  Total Trades: {self.state['total_trades']}")
            logger.info(f"  Previous Uptime: {self.state['uptime_seconds']:.0f}s")
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to load state: {e}")
            return False
    
    def save_state(self):
        """Save current state to disk."""
        try:
            # Update last saved timestamp
            self.state['last_saved'] = time.time()
            
            # Calculate uptime
            if 'bot_started' in self.state:
                self.state['uptime_seconds'] = time.time() - self.state['bot_started']
            
            # Create backup of existing state
            if self.state_file.exists():
                backup_file = self.state_file.with_suffix('.json.bak')
                self.state_file.rename(backup_file)
            
            # Write new state
            with open(self.state_file, 'w') as f:
                json.dump(self.state, f, indent=2, default=str)
            
            logger.debug(f"State saved to {self.state_file}")
            
        except Exception as e:
            logger.error(f"Failed to save state: {e}")
    
    async def start_auto_save(self):
        """Start automatic periodic state saving."""
        logger.info(f"Starting auto-save task (interval: {self.save_interval}s)")
        
        while not self._stop_event.is_set():
            try:
                await asyncio.wait_for(
                    self._stop_event.wait(),
                    timeout=self.save_interval
                )
            except asyncio.TimeoutError:
                # Timeout is expected - time to save
                self.save_state()
    
    def stop_auto_save(self):
        """Stop automatic saving."""
        self._stop_event.set()
        logger.info("Auto-save task stopped")
    
    def update_from_order_executor(self, executor_stats: Dict):
        """
        Update state from order executor statistics.
        
        Args:
            executor_stats: Statistics from OrderExecutor.get_statistics()
        """
        self.state['total_trades'] = executor_stats.get('total_orders', 0)
        self.state['total_pnl'] = executor_stats.get('total_profit', 0.0)
    
    def update_from_risk_manager(self, risk_stats: Dict):
        """
        Update state from risk manager statistics.
        
        Args:
            risk_stats: Statistics from RiskManager.get_statistics()
        """
        self.state['risk_stats'] = {
            'total_capital': risk_stats.get('total_capital', 0.0),
            'daily_pnl': risk_stats.get('daily_pnl', 0.0),
            'drawdown_pct': risk_stats.get('drawdown_pct', 0.0),
            'win_rate': risk_stats.get('win_rate', 0.0),
            'is_paused': risk_stats.get('is_paused', False),
        }
    
    def update_from_balance_manager(self, balance_summary: Dict):
        """
        Update state from balance manager.
        
        Args:
            balance_summary: Summary from BalanceManager.get_summary()
        """
        self.state['balances'] = balance_summary.get('balances', {})
    
    def add_trade(self, trade_info: Dict):
        """
        Add a trade to history.
        
        Args:
            trade_info: Trade information dictionary
        """
        # Limit trade history to last 1000 trades to prevent file bloat
        if len(self.state['trade_history']) >= 1000:
            self.state['trade_history'] = self.state['trade_history'][-999:]
        
        self.state['trade_history'].append({
            'timestamp': trade_info.get('timestamp', time.time()),
            'symbol': trade_info.get('symbol'),
            'buy_exchange': trade_info.get('buy_exchange'),
            'sell_exchange': trade_info.get('sell_exchange'),
            'quantity': trade_info.get('quantity'),
            'buy_price': trade_info.get('buy_price'),
            'sell_price': trade_info.get('sell_price'),
            'net_profit': trade_info.get('net_profit'),
            'roi_pct': trade_info.get('roi_pct'),
        })
    
    def get_state(self) -> Dict[str, Any]:
        """Get current state."""
        return self.state.copy()
    
    def get_summary(self) -> str:
        """Get human-readable state summary."""
        uptime_hours = self.state.get('uptime_seconds', 0) / 3600.0
        
        summary = f"""
=== Bot State Summary ===
Status: {'🟢 RUNNING' if self.state.get('risk_stats', {}).get('is_paused', False) == False else '🔴 PAUSED'}
Uptime: {uptime_hours:.1f} hours
Total Trades: {self.state.get('total_trades', 0)}
Total PnL: ${self.state.get('total_pnl', 0.0):.2f}
Daily PnL: ${self.state.get('risk_stats', {}).get('daily_pnl', 0.0):.2f}
Win Rate: {self.state.get('risk_stats', {}).get('win_rate', 0.0):.1f}%
Drawdown: {self.state.get('risk_stats', {}).get('drawdown_pct', 0.0):.2f}%
Last Saved: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(self.state.get('last_saved', 0))) if self.state.get('last_saved') else 'Never'}
========================
"""
        return summary
    
    def print_summary(self):
        """Print state summary to console."""
        print(self.get_summary())
    
    def export_trade_history(self, output_file: str = "data/trade_history.json"):
        """
        Export trade history to a separate file.
        
        Args:
            output_file: Path to output file
        """
        try:
            output_path = Path(output_file)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(output_path, 'w') as f:
                json.dump(self.state.get('trade_history', []), f, indent=2, default=str)
            
            logger.info(f"Trade history exported to {output_file}")
            
        except Exception as e:
            logger.error(f"Failed to export trade history: {e}")
    
    def cleanup_old_backups(self, keep_count: int = 5):
        """
        Clean up old backup files, keeping only the most recent.
        
        Args:
            keep_count: Number of backups to keep
        """
        try:
            backup_pattern = f"{self.state_file.stem}.json.bak*"
            backup_files = sorted(
                self.state_file.parent.glob(backup_pattern),
                key=lambda p: p.stat().st_mtime,
                reverse=True
            )
            
            for backup in backup_files[keep_count:]:
                backup.unlink()
                logger.debug(f"Deleted old backup: {backup}")
                
        except Exception as e:
            logger.error(f"Failed to cleanup old backups: {e}")
