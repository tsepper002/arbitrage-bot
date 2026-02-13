#!/usr/bin/env python3
"""
Telegram bot for notifications and remote control (A10).
Sends automatic alerts and responds to commands.
"""
import asyncio
import logging
import aiohttp
from typing import Optional, Dict, Any
import settings

logger = logging.getLogger("telegram_bot")


class TelegramBot:
    """
    Telegram bot for arbitrage bot notifications and control.
    
    A10 IMPLEMENTATION:
    - Automatic messages: trade alerts, reports, disconnects, risk limits
    - Commands: /status, /balances, /stats, /pnl, /stop, /start, /mode
    """
    
    def __init__(self, token: Optional[str] = None, chat_id: Optional[str] = None):
        """
        Initialize Telegram bot.
        
        Args:
            token: Bot token from @BotFather (default from settings)
            chat_id: Chat ID to send messages to (default from settings)
        """
        self.token = token or settings.TELEGRAM_BOT_TOKEN
        self.chat_id = chat_id or settings.TELEGRAM_CHAT_ID
        self.enabled = bool(self.token and self.chat_id)
        self.base_url = f"https://api.telegram.org/bot{self.token}"
        
        if self.enabled:
            logger.info("✅ Telegram bot enabled")
        else:
            logger.info("ℹ️  Telegram bot disabled (no token/chat_id configured)")
    
    async def send_message(self, text: str, parse_mode: str = "Markdown") -> bool:
        """
        Send a message to Telegram.
        
        Args:
            text: Message text (supports Markdown)
            parse_mode: Formatting mode (Markdown or HTML)
            
        Returns:
            True if sent successfully, False otherwise
        """
        if not self.enabled:
            logger.debug(f"Telegram disabled, would have sent: {text}")
            return False
        
        try:
            url = f"{self.base_url}/sendMessage"
            data = {
                "chat_id": self.chat_id,
                "text": text,
                "parse_mode": parse_mode,
                "disable_web_page_preview": True
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=data, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                    if resp.status == 200:
                        logger.debug(f"Telegram message sent: {text[:50]}...")
                        return True
                    else:
                        error = await resp.text()
                        logger.error(f"Telegram send failed ({resp.status}): {error}")
                        return False
        
        except asyncio.TimeoutError:
            logger.error("Telegram send timeout")
            return False
        
        except Exception as e:
            logger.exception(f"Telegram send error: {e}")
            return False
    
    # Automatic notifications
    
    async def notify_trade_executed(self, trade_info: Dict[str, Any]):
        """Notify about executed trade."""
        symbol = trade_info.get("symbol", "?")
        buy_ex = trade_info.get("buy_ex", "?")
        sell_ex = trade_info.get("sell_ex", "?")
        qty = trade_info.get("qty", 0)
        net = trade_info.get("net", 0)
        roi = trade_info.get("roi_pct", 0)
        
        text = f"""
✅ *Trade Executed*
Symbol: `{symbol}`
Route: {buy_ex} → {sell_ex}
Quantity: {qty:.6f}
Net profit: ${net:.4f}
ROI: {roi:.3f}%
"""
        await self.send_message(text)
    
    async def notify_daily_report(self, stats: Dict[str, Any]):
        """Send daily performance report."""
        pnl = stats.get("daily_pnl", 0)
        trades = stats.get("trades_today", 0)
        win_rate = stats.get("win_rate", 0)
        
        emoji = "📈" if pnl > 0 else "📉" if pnl < 0 else "➡️"
        
        text = f"""
{emoji} *Daily Report*
P&L: ${pnl:.2f}
Trades: {trades}
Win rate: {win_rate:.1f}%
"""
        await self.send_message(text)
    
    async def notify_hourly_report(self, stats: Dict[str, Any]):
        """Send hourly performance report."""
        pnl = stats.get("hourly_pnl", 0)
        trades = stats.get("trades_last_hour", 0)
        
        text = f"""
⏰ *Hourly Report*
P&L: ${pnl:.2f}
Trades: {trades}
"""
        await self.send_message(text)
    
    async def notify_ws_disconnect(self, exchange: str):
        """Notify about WebSocket disconnection."""
        text = f"⚠️ *WebSocket Disconnected*\nExchange: {exchange}"
        await self.send_message(text)
    
    async def notify_ws_reconnected(self, exchange: str):
        """Notify about WebSocket reconnection."""
        text = f"✅ *WebSocket Reconnected*\nExchange: {exchange}"
        await self.send_message(text)
    
    async def notify_risk_limit_hit(self, limit_type: str, details: str):
        """Notify about risk limit being hit."""
        text = f"""
🔴 *Risk Limit Hit*
Type: {limit_type}
Details: {details}
Trading paused for safety
"""
        await self.send_message(text)
    
    async def notify_rebalance_started(self, from_exchange: str, to_exchange: str, amount: float, currency: str):
        """Notify about rebalance operation."""
        text = f"""
🔄 *Rebalancing Started*
From: {from_exchange}
To: {to_exchange}
Amount: {amount:.2f} {currency}
"""
        await self.send_message(text)
    
    async def notify_rebalance_completed(self, from_exchange: str, to_exchange: str, amount: float):
        """Notify about completed rebalance."""
        text = f"""
✅ *Rebalancing Completed*
{from_exchange} → {to_exchange}
Amount: {amount:.2f} USDT
"""
        await self.send_message(text)
    
    async def notify_error(self, error_msg: str):
        """Notify about critical error."""
        text = f"❌ *Error*\n```\n{error_msg[:500]}\n```"
        await self.send_message(text)
    
    async def notify_startup(self):
        """Notify about bot startup."""
        mode = "🔵 DRY RUN" if settings.DRY_RUN else "🔴 LIVE TRADING"
        text = f"""
🚀 *Arbitrage Bot Started*
Mode: {mode}
Exchanges: Bybit, KuCoin, HTX, XT, MEXC
Symbols: {len(settings.TRADING_SYMBOLS)}
"""
        await self.send_message(text)
    
    async def notify_shutdown(self, stats: Dict[str, Any]):
        """Notify about bot shutdown."""
        pnl = stats.get("daily_pnl", 0)
        trades = stats.get("trades_today", 0)
        
        text = f"""
🛑 *Bot Shutdown*
Session P&L: ${pnl:.2f}
Trades: {trades}
"""
        await self.send_message(text)
    
    # Command handlers (simplified - full implementation would use Telegram bot API polling)
    
    def format_status_message(self, status: Dict[str, Any]) -> str:
        """Format status information as message."""
        mode = "🔵 DRY RUN" if settings.DRY_RUN else "🔴 LIVE"
        trading_allowed = "✅" if status.get("trading_allowed", False) else "🔴"
        
        return f"""
📊 *Bot Status*
Mode: {mode}
Trading: {trading_allowed}
Daily P&L: ${status.get('daily_pnl', 0):.2f}
Trades today: {status.get('trades_today', 0)}
CPU: {status.get('cpu_pct', 0):.1f}%
Memory: {status.get('memory_mb', 0):.0f}MB
"""
    
    def format_balances_message(self, balances: Dict[str, Dict[str, float]]) -> str:
        """Format balance information as message."""
        lines = ["💰 *Balances*\n"]
        
        for exchange, currencies in balances.items():
            lines.append(f"\n*{exchange}:*")
            for currency, amount in currencies.items():
                if amount > 0:
                    lines.append(f"  {currency}: {amount:.4f}")
        
        return "\n".join(lines)
    
    def format_statistics_message(self, stats: Dict[str, Any]) -> str:
        """Format statistics as message."""
        return f"""
📈 *Statistics*
Daily P&L: ${stats.get('daily_pnl', 0):.2f}
Trades today: {stats.get('trades_today', 0)}
Win rate: {stats.get('win_rate', 0):.1f}%
Lifetime P&L: ${stats.get('lifetime_pnl', 0):.2f}
Lifetime trades: {stats.get('lifetime_trades', 0)}
"""


# Convenience function for quick messages
async def send_telegram_message(text: str):
    """Quick function to send Telegram message."""
    bot = TelegramBot()
    await bot.send_message(text)


# Factory function for easy initialization
_telegram_bot_instance = None

def get_telegram_bot(token: str, chat_id: str):
    """Get or create TelegramBot singleton."""
    global _telegram_bot_instance
    if _telegram_bot_instance is None:
        _telegram_bot_instance = TelegramBot(token, chat_id)
    return _telegram_bot_instance
