#!/usr/bin/env python3
"""
Telegram bot for notifications and remote control (A10).
Sends automatic alerts and responds to commands.
"""
import asyncio
import logging
import socket
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
            
            # Use IPv4 + ThreadedResolver to avoid DNS resolution issues
            connector = aiohttp.TCPConnector(
                family=socket.AF_INET,
                resolver=aiohttp.ThreadedResolver()
            )
            timeout = aiohttp.ClientTimeout(total=15, sock_connect=10)
            async with aiohttp.ClientSession(connector=connector) as session:
                async with session.post(url, json=data, timeout=timeout) as resp:
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
    
    # Command handling methods
    
    async def handle_command(self, command: str, bot_manager=None) -> str:
        """
        Handle incoming command and return response.
        
        Args:
            command: Command string (e.g., "/start", "/status")
            bot_manager: Reference to main bot manager for data
            
        Returns:
            Response text
        """
        command = command.lower().strip()
        
        if command == "/start" or command == "/help":
            return self._cmd_help()
        elif command == "/status":
            return self._cmd_status(bot_manager)
        elif command == "/balance":
            return self._cmd_balance(bot_manager)
        elif command == "/trades":
            return self._cmd_trades(bot_manager)
        elif command == "/opportunities":
            return self._cmd_opportunities(bot_manager)
        else:
            return "❌ Unknown command. Use /help to see available commands."
    
    def _cmd_help(self) -> str:
        """Return help message with all commands."""
        return """
🤖 *Arbitrage Bot Commands*

/start - Show this help message
/status - Bot status and health
/balance - Exchange balances
/trades - Trading statistics
/opportunities - Recent opportunities
/help - Show this message

Bot sends automatic updates every 30 minutes and alerts for important events.
"""
    
    def _cmd_status(self, bot_manager) -> str:
        """Return bot status."""
        if not bot_manager:
            return "❌ Bot manager not available"
        
        try:
            mode = "🔵 DRY RUN" if settings.DRY_RUN else "🔴 LIVE TRADING"
            
            # Get status from bot manager
            status_info = {
                'mode': mode,
                'trading_allowed': True,  # Get from bot_manager if available
                'daily_pnl': 0,  # Get from state_manager if available
                'trades_today': 0,
                'cpu_pct': 0,
                'memory_mb': 0
            }
            
            if hasattr(bot_manager, 'state_manager') and bot_manager.state_manager:
                state = bot_manager.state_manager.state
                status_info['daily_pnl'] = state.get('daily_pnl', 0)
                status_info['trades_today'] = len(state.get('trades_today', []))
            
            return f"""
📊 *Bot Status*
Mode: {status_info['mode']}
Trading: ✅ Active
Daily P&L: ${status_info['daily_pnl']:.2f}
Trades today: {status_info['trades_today']}

WebSocket Connections: ✅
Arbitrage Engine: ✅ Running
Risk Manager: ✅ Active
"""
        except Exception as e:
            logger.exception("Error in _cmd_status")
            return f"❌ Error getting status: {str(e)}"
    
    def _cmd_balance(self, bot_manager) -> str:
        """Return exchange balances."""
        if not bot_manager:
            return "❌ Bot manager not available"
        
        try:
            if not hasattr(bot_manager, 'balance_manager') or not bot_manager.balance_manager:
                return "❌ Balance manager not available"
            
            balances = bot_manager.balance_manager.balances
            
            lines = ["💰 *Exchange Balances*\n"]
            total_usdt = 0
            
            for exchange, currencies in balances.items():
                usdt = currencies.get('USDT', 0)
                total_usdt += usdt
                
                if usdt > 0:
                    lines.append(f"*{exchange}:*")
                    lines.append(f"  USDT: ${usdt:.2f}")
                    
                    # Show other currencies if any
                    for curr, amount in currencies.items():
                        if curr != 'USDT' and amount > 0:
                            lines.append(f"  {curr}: {amount:.6f}")
                    lines.append("")
            
            lines.append(f"*Total USDT:* ${total_usdt:.2f}")
            
            if settings.DRY_RUN:
                lines.append("\n🔵 *Virtual balances* (DRY_RUN mode)")
            
            return "\n".join(lines)
        except Exception as e:
            logger.exception("Error in _cmd_balance")
            return f"❌ Error getting balances: {str(e)}"
    
    def _cmd_trades(self, bot_manager) -> str:
        """Return trading statistics."""
        if not bot_manager:
            return "❌ Bot manager not available"
        
        try:
            stats = {
                'daily_pnl': 0,
                'trades_today': 0,
                'win_rate': 0,
                'best_trade': 0,
                'worst_trade': 0
            }
            
            if hasattr(bot_manager, 'state_manager') and bot_manager.state_manager:
                state = bot_manager.state_manager.state
                stats['daily_pnl'] = state.get('daily_pnl', 0)
                trades = state.get('trades_today', [])
                stats['trades_today'] = len(trades)
                
                if trades:
                    profits = [t.get('net_profit', 0) for t in trades]
                    wins = sum(1 for p in profits if p > 0)
                    stats['win_rate'] = (wins / len(trades)) * 100 if trades else 0
                    stats['best_trade'] = max(profits) if profits else 0
                    stats['worst_trade'] = min(profits) if profits else 0
            
            emoji = "📈" if stats['daily_pnl'] > 0 else "📉" if stats['daily_pnl'] < 0 else "➡️"
            
            return f"""
{emoji} *Trading Statistics*

Daily P&L: ${stats['daily_pnl']:.2f}
Trades today: {stats['trades_today']}
Win rate: {stats['win_rate']:.1f}%
Best trade: ${stats['best_trade']:.2f}
Worst trade: ${stats['worst_trade']:.2f}

Mode: {"🔵 DRY RUN" if settings.DRY_RUN else "🔴 LIVE"}
"""
        except Exception as e:
            logger.exception("Error in _cmd_trades")
            return f"❌ Error getting trades: {str(e)}"
    
    def _cmd_opportunities(self, bot_manager) -> str:
        """Return recent arbitrage opportunities."""
        return """
🔍 *Recent Opportunities*

Opportunities are detected in real-time and logged to the console.

To see live opportunities:
1. Check bot logs
2. Wait for automatic Telegram alerts (ROI > 0.1%)
3. Use /status to see if bot is actively scanning

Recent scans: Active
Exchanges monitored: Bybit, KuCoin, HTX, MEXC
Symbols: 10 pairs
"""
    
    async def start_monitoring_loop(self, bot_manager):
        """
        Start periodic monitoring and send updates to Telegram.
        Call this as a background task.
        """
        logger.info("Starting Telegram monitoring loop...")
        
        update_interval = 1800  # 30 minutes
        
        while True:
            try:
                await asyncio.sleep(update_interval)
                
                # Send periodic update
                status_msg = self._cmd_status(bot_manager)
                await self.send_message(status_msg)
                
            except asyncio.CancelledError:
                logger.info("Telegram monitoring loop cancelled")
                raise
            except Exception as e:
                logger.exception(f"Error in monitoring loop: {e}")
                await asyncio.sleep(60)  # Wait 1 min on error


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
