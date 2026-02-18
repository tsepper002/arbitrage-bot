#!/usr/bin/env python3
"""
Balance Manager - Tracks balances across exchanges with local caching.
Provides pre-trade validation and automatic exclusion of underfunded exchanges.
"""
import asyncio
import time
import logging
from typing import Dict, Optional, Tuple, Set
from datetime import datetime
import settings

logger = logging.getLogger("balance_manager")


class BalanceManager:
    """
    Manages balance tracking across multiple exchanges with optimistic updates.
    
    Features:
    - Local balance cache with optimistic updates after trades
    - Periodic REST sync every 60s for accuracy
    - Pre-trade balance validation
    - Auto-exclusion of exchanges with insufficient funds
    - Balance alerts via Telegram (if configured)
    """
    
    def __init__(self, rest_clients: Optional[Dict] = None):
        """
        Initialize balance manager.
        
        Args:
            rest_clients: Dict of {exchange_name: REST_client} for fetching balances
        """
        self.rest_clients = rest_clients or {}
        self.balances: Dict[str, Dict[str, float]] = {}  # {exchange: {currency: amount}}
        self.last_sync: Dict[str, float] = {}  # {exchange: timestamp}
        self.sync_interval = 60.0  # Sync every 60 seconds
        self.excluded_exchanges: Set[str] = set()
        self.initialized = False
        
        logger.info("✅ BalanceManager initialized")
    
    async def initialize(self):
        """
        Fetch initial balances from all exchanges.
        Must be called before trading starts.
        """
        if not self.rest_clients:
            logger.warning("⚠️  No REST clients configured - balance tracking disabled")
            return False
        
        logger.info(f"🔄 Fetching initial balances from {len(self.rest_clients)} exchanges...")
        
        tasks = []
        for exchange_name, client in self.rest_clients.items():
            tasks.append(self._fetch_balance(exchange_name, client))
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        success_count = sum(1 for r in results if not isinstance(r, Exception))
        logger.info(f"✅ Initialized balances for {success_count}/{len(results)} exchanges")
        
        # If DRY_RUN mode and no balances loaded, use mock data
        if settings.DRY_RUN and success_count == 0:
            logger.info("ℹ️  DRY_RUN mode: Using mock balances for testing (real network unavailable)")
            self._use_mock_balances()
            success_count = len(self.rest_clients)
        
        self.initialized = True
        return success_count > 0
    
    def _use_mock_balances(self):
        """Use mock balance data for DRY_RUN testing when network unavailable."""
        mock_balance = {
            'USDT': 100.0,  # $100 per exchange for testing
            'BTC': 0.001,   # ~$68 worth
            'ETH': 0.05,    # ~$97 worth
            'BNB': 0.15,    # ~$92 worth
            'SOL': 1.0      # ~$85 worth
        }
        
        for exchange_name in self.rest_clients.keys():
            self.balances[exchange_name] = mock_balance.copy()
            self.last_sync[exchange_name] = time.time()
            logger.info(f"📊 {exchange_name}: Mock balance = ${mock_balance['USDT']:.2f} USDT + crypto")
        
        logger.info("✅ Mock balances loaded for all exchanges")
    
    async def _fetch_balance(self, exchange_name: str, client) -> Dict[str, float]:
        """
        Fetch balance from a single exchange.
        
        Returns:
            Dict of {currency: amount}
        """
        try:
            if not hasattr(client, 'get_balance'):
                logger.warning(f"⚠️  {exchange_name} client has no get_balance method")
                return {}
            
            balance = await client.get_balance()
            self.balances[exchange_name] = balance
            self.last_sync[exchange_name] = time.time()
            
            # Check if exchange should be excluded
            usdt_balance = balance.get('USDT', 0)
            if usdt_balance < settings.MIN_BALANCE_PER_EXCHANGE:
                if exchange_name not in self.excluded_exchanges:
                    logger.warning(
                        f"⚠️  {exchange_name} excluded: USDT balance ${usdt_balance:.2f} "
                        f"< minimum ${settings.MIN_BALANCE_PER_EXCHANGE:.2f}"
                    )
                    self.excluded_exchanges.add(exchange_name)
            else:
                if exchange_name in self.excluded_exchanges:
                    logger.info(f"✅ {exchange_name} re-enabled: balance sufficient")
                    self.excluded_exchanges.discard(exchange_name)
            
            logger.debug(f"{exchange_name} balance: {balance}")
            return balance
            
        except Exception as e:
            logger.error(f"❌ Failed to fetch balance from {exchange_name}: {e}")
            return {}
    
    async def sync_balances(self):
        """
        Sync all balances from exchanges.
        Called periodically to maintain accuracy.
        """
        if not self.rest_clients:
            return
        
        current_time = time.time()
        tasks = []
        
        for exchange_name, client in self.rest_clients.items():
            last_sync = self.last_sync.get(exchange_name, 0)
            if current_time - last_sync >= self.sync_interval:
                tasks.append(self._fetch_balance(exchange_name, client))
        
        if tasks:
            logger.debug(f"🔄 Syncing {len(tasks)} exchange balances...")
            await asyncio.gather(*tasks, return_exceptions=True)
    
    def has_sufficient_balance(
        self, 
        exchange: str, 
        currency: str, 
        amount: float
    ) -> Tuple[bool, Optional[str]]:
        """
        Check if exchange has sufficient balance for trade.
        
        Uses dynamic safety margins:
        - Small balances (<$50): 5% buffer for flexibility
        - Medium balances ($50-$200): 10% buffer
        - Large balances (>$200): 15% buffer for safety
        
        Returns:
            (has_sufficient, reason) tuple
        """
        if exchange in self.excluded_exchanges:
            return False, f"{exchange} excluded due to low balance"
        
        if exchange not in self.balances:
            # No balance data - assume sufficient in dry-run mode
            if settings.DRY_RUN:
                return True, None
            return False, f"No balance data for {exchange}"
        
        current_balance = self.balances[exchange].get(currency, 0)
        
        if current_balance < amount:
            return False, f"Insufficient {currency}: have {current_balance:.4f}, need {amount:.4f}"
        
        # Dynamic safety margin based on balance size
        if current_balance < 50:
            safety_margin = 1.05  # 5% for small accounts
        elif current_balance < 200:
            safety_margin = 1.10  # 10% for medium accounts
        else:
            safety_margin = 1.15  # 15% for large accounts
        
        if current_balance < amount * safety_margin:
            return False, (
                f"Balance too low for safety margin: {current_balance:.4f} "
                f"< {amount * safety_margin:.4f} (need {(safety_margin-1)*100:.0f}% buffer)"
            )
        
        return True, None
    
    def update_balance_optimistic(
        self,
        exchange: str,
        currency: str,
        delta: float
    ):
        """
        Optimistically update balance after trade (before confirmation).
        Will be corrected by next sync.
        
        Args:
            exchange: Exchange name
            currency: Currency symbol
            delta: Amount to add (positive) or subtract (negative)
        """
        if exchange not in self.balances:
            self.balances[exchange] = {}
        
        current = self.balances[exchange].get(currency, 0)
        new_balance = current + delta
        self.balances[exchange][currency] = max(0, new_balance)  # Don't go negative
        
        logger.debug(
            f"Optimistic update: {exchange} {currency} "
            f"{current:.4f} → {new_balance:.4f} (Δ {delta:+.4f})"
        )
    
    def record_trade(
        self,
        buy_exchange: str,
        sell_exchange: str,
        base_currency: str,
        quote_currency: str,
        quantity: float,
        buy_cost: float,
        sell_proceeds: float
    ):
        """
        Record a trade and update balances optimistically.
        
        Args:
            buy_exchange: Exchange where buy order executed
            sell_exchange: Exchange where sell order executed
            base_currency: Base currency (e.g., BTC)
            quote_currency: Quote currency (e.g., USDT)
            quantity: Amount of base currency traded
            buy_cost: Cost in quote currency for buy
            sell_proceeds: Proceeds in quote currency from sell
        """
        # Buy exchange: +base, -quote
        self.update_balance_optimistic(buy_exchange, base_currency, quantity)
        self.update_balance_optimistic(buy_exchange, quote_currency, -buy_cost)
        
        # Sell exchange: -base, +quote
        self.update_balance_optimistic(sell_exchange, base_currency, -quantity)
        self.update_balance_optimistic(sell_exchange, quote_currency, sell_proceeds)
        
        logger.info(
            f"📊 Trade recorded: {buy_exchange}(-${buy_cost:.2f}) → {sell_exchange}(+${sell_proceeds:.2f})"
        )
    
    def get_balance(self, exchange: str, currency: str) -> float:
        """Get current cached balance."""
        return self.balances.get(exchange, {}).get(currency, 0)
    
    def get_all_balances(self) -> Dict[str, Dict[str, float]]:
        """Get all cached balances."""
        return self.balances.copy()
    
    def get_total_balance(self, currency: str = 'USDT') -> float:
        """Get total balance across all exchanges for a currency."""
        total = 0
        for exchange_balances in self.balances.values():
            total += exchange_balances.get(currency, 0)
        return total
    
    def get_excluded_exchanges(self) -> Set[str]:
        """Get set of exchanges currently excluded due to low balance."""
        return self.excluded_exchanges.copy()
    
    def print_summary(self):
        """Print balance summary to console."""
        print(f"\n{'='*60}")
        print(f"  Balance Summary")
        print(f"{'='*60}")
        
        if not self.balances:
            print("  No balance data available")
        else:
            total_usdt = 0
            for exchange, currencies in sorted(self.balances.items()):
                usdt = currencies.get('USDT', 0)
                total_usdt += usdt
                status = "❌ EXCLUDED" if exchange in self.excluded_exchanges else "✅"
                print(f"  {exchange:12s} {status:12s} ${usdt:>10.2f} USDT")
            
            print(f"  {'-'*60}")
            print(f"  {'Total':12s} {'':12s} ${total_usdt:>10.2f} USDT")
        
        print(f"{'='*60}\n")
    
    async def monitoring_loop(self):
        """
        Background task to periodically sync balances.
        Run this as an asyncio task.
        """
        logger.info("🔄 Balance monitoring loop started")
        
        while True:
            try:
                await asyncio.sleep(self.sync_interval)
                await self.sync_balances()
            except asyncio.CancelledError:
                logger.info("Balance monitoring loop stopped")
                break
            except Exception as e:
                logger.error(f"Error in balance monitoring loop: {e}")
                await asyncio.sleep(5)  # Brief pause before retry


# Singleton instance
_instance: Optional[BalanceManager] = None


def get_balance_manager() -> BalanceManager:
    """Get or create singleton BalanceManager instance."""
    global _instance
    if _instance is None:
        _instance = BalanceManager()
    return _instance
