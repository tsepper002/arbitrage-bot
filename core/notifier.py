#!/usr/bin/env python3
"""
Telegram Notifier - Send notifications via Telegram Bot API.
Provides real-time alerts for trades, errors, and bot status.
"""
import logging
import time
import os
from typing import Optional, Dict
import requests
from datetime import datetime

logger = logging.getLogger("notifier")


class TelegramNotifier:
    """
    Sends notifications via Telegram.
    Configured via environment variables.
    """
    
    def __init__(self, bot_token: Optional[str] = None, chat_id: Optional[str] = None,
                 rate_limit: float = 1.0):
        """
        Initialize Telegram notifier.
        
        Args:
            bot_token: Telegram bot token (from @BotFather)
            chat_id: Telegram chat ID to send messages to
            rate_limit: Minimum seconds between messages (anti-spam)
        """
        self.bot_token = bot_token or os.getenv('TELEGRAM_BOT_TOKEN')
        self.chat_id = chat_id or os.getenv('TELEGRAM_CHAT_ID')
        self.rate_limit = rate_limit
        
        self.last_message_time = 0.0
        self.message_count = 0
        self.enabled = bool(self.bot_token and self.chat_id)
        
        if not self.enabled:
            logger.warning("Telegram notifier disabled - set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID to enable")
        else:
            logger.info(f"Telegram notifier initialized (chat_id: {self.chat_id})")
            # Send test message
            self.send_message("🤖 Arbitrage Bot started successfully!")
    
    def _can_send(self) -> bool:
        """Check if sending is allowed (rate limit)."""
        if not self.enabled:
            return False
        
        current_time = time.time()
        if current_time - self.last_message_time < self.rate_limit:
            logger.debug("Message rate limited")
            return False
        
        return True
    
    def send_message(self, text: str, parse_mode: str = "Markdown",
                    disable_notification: bool = False) -> bool:
        """
        Send a message via Telegram.
        
        Args:
            text: Message text
            parse_mode: Parse mode ("Markdown", "HTML", or None)
            disable_notification: Send silently
            
        Returns:
            True if sent successfully, False otherwise
        """
        if not self._can_send():
            return False
        
        try:
            url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
            payload = {
                'chat_id': self.chat_id,
                'text': text,
                'parse_mode': parse_mode,
                'disable_notification': disable_notification
            }
            
            response = requests.post(url, json=payload, timeout=10)
            response.raise_for_status()
            
            self.last_message_time = time.time()
            self.message_count += 1
            logger.debug(f"Telegram message sent ({self.message_count} total)")
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to send Telegram message: {e}")
            return False
    
    def notify_trade(self, trade_info: Dict):
        """
        Send trade notification.
        
        Args:
            trade_info: Trade information dictionary
        """
        symbol = trade_info.get('symbol', 'UNKNOWN')
        quantity = trade_info.get('quantity', 0.0)
        buy_exchange = trade_info.get('buy_exchange', '')
        sell_exchange = trade_info.get('sell_exchange', '')
        buy_price = trade_info.get('buy_price', 0.0)
        sell_price = trade_info.get('sell_price', 0.0)
        net_profit = trade_info.get('net_profit', 0.0)
        roi_pct = trade_info.get('roi_pct', 0.0)
        
        # Emoji based on profit
        emoji = "💰" if net_profit > 0 else "⚠️"
        
        message = f"""
{emoji} *Trade Executed*

📊 Symbol: `{symbol}`
🔄 Route: {buy_exchange} → {sell_exchange}
📦 Quantity: `{quantity:.6f}`
💵 Buy: `${buy_price:.2f}` | Sell: `${sell_price:.2f}`
💸 Profit: `${net_profit:.4f}` ({roi_pct:.3f}% ROI)
"""
        
        self.send_message(message.strip())
    
    def notify_error(self, error_message: str, critical: bool = False):
        """
        Send error notification.
        
        Args:
            error_message: Error description
            critical: Whether this is a critical error
        """
        emoji = "🚨" if critical else "⚠️"
        message = f"{emoji} *{'CRITICAL' if critical else 'ERROR'}*\n\n{error_message}"
        self.send_message(message, disable_notification=not critical)
    
    def notify_daily_summary(self, stats: Dict):
        """
        Send daily summary.
        
        Args:
            stats: Statistics dictionary
        """
        total_trades = stats.get('total_trades', 0)
        total_pnl = stats.get('total_pnl', 0.0)
        daily_pnl = stats.get('daily_pnl', 0.0)
        win_rate = stats.get('win_rate', 0.0)
        
        emoji = "📈" if daily_pnl >= 0 else "📉"
        
        message = f"""
{emoji} *Daily Summary*

📊 Trades Today: {total_trades}
💰 Daily PnL: `${daily_pnl:.2f}`
💸 Total PnL: `${total_pnl:.2f}`
🎯 Win Rate: {win_rate:.1f}%
🕐 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
        
        self.send_message(message.strip())
    
    def notify_bot_restart(self, reason: str = "Manual restart"):
        """
        Send bot restart notification.
        
        Args:
            reason: Reason for restart
        """
        message = f"🔄 *Bot Restarting*\n\nReason: {reason}"
        self.send_message(message)
    
    def notify_bot_stopped(self, stats: Dict):
        """
        Send bot stopped notification with final stats.
        
        Args:
            stats: Final statistics
        """
        total_trades = stats.get('total_trades', 0)
        total_pnl = stats.get('total_pnl', 0.0)
        uptime_hours = stats.get('uptime_seconds', 0) / 3600.0
        
        message = f"""
🛑 *Bot Stopped*

📊 Total Trades: {total_trades}
💰 Total PnL: `${total_pnl:.2f}`
⏱️ Uptime: {uptime_hours:.1f} hours
🕐 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
        
        self.send_message(message.strip())
    
    def notify_risk_alert(self, alert_type: str, message: str):
        """
        Send risk management alert.
        
        Args:
            alert_type: Type of alert (e.g., "Daily Loss Limit", "Drawdown")
            message: Alert details
        """
        text = f"⚠️ *Risk Alert: {alert_type}*\n\n{message}"
        self.send_message(text, disable_notification=False)
    
    def notify_balance_low(self, exchange: str, currency: str, balance: float,
                          threshold: float):
        """
        Send low balance alert.
        
        Args:
            exchange: Exchange name
            currency: Currency symbol
            balance: Current balance
            threshold: Threshold that triggered alert
        """
        message = f"""
⚠️ *Low Balance Alert*

Exchange: {exchange}
Currency: `{currency}`
Balance: `{balance:.6f}`
Threshold: `{threshold:.6f}`

Consider rebalancing funds.
"""
        
        self.send_message(message.strip())
    
    def get_stats(self) -> Dict:
        """Get notifier statistics."""
        return {
            'enabled': self.enabled,
            'message_count': self.message_count,
            'last_message_time': self.last_message_time,
        }


class DummyNotifier:
    """Dummy notifier for when Telegram is disabled."""
    
    def __init__(self):
        self.enabled = False
        logger.info("Using dummy notifier (Telegram disabled)")
    
    def send_message(self, text: str, **kwargs) -> bool:
        logger.debug(f"[NOTIFIER] {text}")
        return False
    
    def notify_trade(self, trade_info: Dict):
        pass
    
    def notify_error(self, error_message: str, critical: bool = False):
        logger.warning(f"[NOTIFIER] Error: {error_message}")
    
    def notify_daily_summary(self, stats: Dict):
        pass
    
    def notify_bot_restart(self, reason: str = "Manual restart"):
        pass
    
    def notify_bot_stopped(self, stats: Dict):
        pass
    
    def notify_risk_alert(self, alert_type: str, message: str):
        logger.warning(f"[NOTIFIER] Risk Alert - {alert_type}: {message}")
    
    def notify_balance_low(self, exchange: str, currency: str, balance: float, threshold: float):
        logger.warning(f"[NOTIFIER] Low balance - {exchange} {currency}: {balance:.6f}")
    
    def get_stats(self) -> Dict:
        return {'enabled': False, 'message_count': 0}
