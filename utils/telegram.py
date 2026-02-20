#!/usr/bin/env python3
"""
Telegram notification helper for the arbitrage bot.
Sends trade alerts and status updates via Telegram Bot API.
"""
import logging
import aiohttp
import settings

logger = logging.getLogger("telegram")


class TelegramNotifier:
    """Send notifications via Telegram Bot API."""

    BASE_URL = "https://api.telegram.org/bot{token}/sendMessage"

    def __init__(self, token: str = "", chat_id: str = ""):
        self.token = token or settings.TELEGRAM_BOT_TOKEN
        self.chat_id = chat_id or settings.TELEGRAM_CHAT_ID
        self.enabled = bool(self.token and self.chat_id and settings.TELEGRAM_ENABLED)
        if self.enabled:
            logger.info("✅ Telegram notifications enabled")
        else:
            logger.info("ℹ️ Telegram notifications disabled (set ARB_TELEGRAM_BOT_TOKEN, ARB_TELEGRAM_CHAT_ID, ARB_TELEGRAM_ENABLED=true)")

    async def send_message(self, text: str, parse_mode: str = "HTML") -> bool:
        """Send a text message to the configured Telegram chat."""
        if not self.enabled:
            return False
        url = self.BASE_URL.format(token=self.token)
        payload = {
            "chat_id": self.chat_id,
            "text": text,
            "parse_mode": parse_mode,
        }
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                    if resp.status == 200:
                        logger.debug("Telegram message sent")
                        return True
                    else:
                        body = await resp.text()
                        logger.warning(f"Telegram API error {resp.status}: {body}")
                        return False
        except Exception as e:
            logger.warning(f"Telegram send failed: {e}")
            return False

    async def notify_opportunity(self, opp: dict) -> bool:
        """Format and send an arbitrage opportunity notification."""
        text = (
            f"💰 <b>Arbitrage Opportunity</b>\n"
            f"Symbol: <code>{opp.get('symbol', '?')}</code>\n"
            f"Buy: {opp.get('buy_ex', '?')} @ ${opp.get('buy_avg', 0):.4f}\n"
            f"Sell: {opp.get('sell_ex', '?')} @ ${opp.get('sell_avg', 0):.4f}\n"
            f"Qty: {opp.get('qty', 0):.6f}\n"
            f"Net Profit: ${opp.get('net', 0):.4f}\n"
            f"ROI: {opp.get('roi_pct', 0):.3f}%"
        )
        return await self.send_message(text)

    async def notify_startup(self, num_symbols: int, num_exchanges: int) -> bool:
        """Send a startup notification."""
        mode = "DRY RUN" if settings.DRY_RUN else "LIVE"
        text = (
            f"🚀 <b>Arbitrage Bot Started</b>\n"
            f"Mode: <code>{mode}</code>\n"
            f"Symbols: {num_symbols}\n"
            f"Exchanges: {num_exchanges}"
        )
        return await self.send_message(text)

    async def notify_stats(self, stats: dict) -> bool:
        """Send statistics notification."""
        text = (
            f"📊 <b>Bot Statistics</b>\n"
            f"Orders: {stats.get('total_orders', 0)}\n"
            f"Profit: ${stats.get('total_profit', 0):.4f}\n"
            f"Avg ROI: {stats.get('average_roi', 0):.3f}%\n"
            f"Balance: ${stats.get('virtual_balance', 0):.2f}"
        )
        return await self.send_message(text)
