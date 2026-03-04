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
        self.sync_interval = 30.0  # Top bots sync every 15-30s; 60s was too slow
        self.excluded_exchanges: Set[str] = set()
        self.locked_funds: Dict[str, Dict[str, float]] = {}  # {exchange: {currency: locked_amount}}
        self.initialized = False
        
        logger.info("✅ BalanceManager initialized")
    
    async def initialize(self):
        """
        Fetch initial balances from all exchanges.
        In DRY_RUN mode, uses virtual balances immediately (no real API calls).
        Must be called before trading starts.
        """
        if not self.rest_clients:
            logger.warning("⚠️  No REST clients configured - balance tracking disabled")
            return False
        
        if settings.DRY_RUN:
            # DRY_RUN: use virtual balances immediately, no real API calls needed
            self._use_virtual_balances()
            self.initialized = True
            return True
        
        # LIVE mode: fetch real balances from exchanges
        logger.info(f"🔄 Fetching initial balances from {len(self.rest_clients)} exchanges...")
        
        tasks = []
        for exchange_name, client in self.rest_clients.items():
            tasks.append(self._fetch_balance(exchange_name, client))
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        success_count = sum(1 for r in results if not isinstance(r, Exception))
        logger.info(f"✅ Initialized balances for {success_count}/{len(results)} exchanges")
        
        self.initialized = True
        return success_count > 0
    
    # All 5 supported exchanges for virtual balance creation
    ALL_EXCHANGES = ["Bybit", "KuCoin", "HTX", "MEXC", "Binance"]

    def _use_virtual_balances(self):
        """Use virtual balances for DRY_RUN mode. No real API calls needed.
        
        Starts with USDT-only balances (realistic simulation).
        The SignalAllocator will buy base coins based on signal activity.
        """
        capital = settings.VIRTUAL_CAPITAL_PER_EXCHANGE
        # Start with USDT only — just like a real account after deposit
        # SignalAllocator will distribute into base coins after signal collection
        mock_balance = {
            'USDT': capital,
        }
        
        # In DRY RUN, create balances for ALL 5 exchanges (not just those with API keys)
        for exchange_name in self.ALL_EXCHANGES:
            self.balances[exchange_name] = mock_balance.copy()
            self.last_sync[exchange_name] = time.time()
        
        num_exchanges = len(self.ALL_EXCHANGES)
        total_virtual = capital * num_exchanges
        logger.info(f"🔵 DRY RUN: Virtual balances loaded — ${capital:.0f} USDT × {num_exchanges} exchanges = ${total_virtual:.0f} total")
        for exchange_name in sorted(self.ALL_EXCHANGES):
            logger.info(f"   {exchange_name:12s} ✅ ${capital:.2f} USDT (virtual)")
        logger.info(f"✅ Virtual balances ready for simulation")
    
    async def _fetch_balance(self, exchange_name: str, client) -> Dict[str, float]:
        """
        Fetch balance from a single exchange.
        Syncs server time first to prevent timestamp errors.
        
        Returns:
            Dict of {currency: amount}
        """
        try:
            if not hasattr(client, 'get_balance'):
                logger.warning(f"⚠️  {exchange_name} client has no get_balance method")
                return {}
            
            # Sync time before balance fetch to prevent recvWindow errors
            if hasattr(client, 'sync_server_time'):
                try:
                    await client.sync_server_time()
                except Exception as e:
                    logger.debug(f"{exchange_name}: time sync before balance failed: {e}")
            
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
        Skipped in DRY_RUN mode (virtual balances don't need syncing).
        """
        if not self.rest_clients:
            return
        
        if settings.DRY_RUN:
            return  # Virtual balances don't need syncing
        
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
        locked = self.locked_funds.get(exchange, {}).get(currency, 0)
        available = max(0, current_balance - locked)
        
        if available < amount:
            return False, f"Insufficient {currency}: have {available:.4f} (total {current_balance:.4f} - locked {locked:.4f}), need {amount:.4f}"
        
        # Dynamic safety margin based on balance size
        if available < 50:
            safety_margin = 1.05  # 5% for small accounts
        elif available < 200:
            safety_margin = 1.10  # 10% for medium accounts
        else:
            safety_margin = 1.15  # 15% for large accounts
        
        if available < amount * safety_margin:
            return False, (
                f"Balance too low for safety margin: {available:.4f} "
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

    def lock_funds(self, exchange: str, currency: str, amount: float):
        """Lock funds for a pending order (prevents double-spend).
        Top arb bots (Hummingbot/CCXT) track locked vs available separately."""
        if exchange not in self.locked_funds:
            self.locked_funds[exchange] = {}
        current_locked = self.locked_funds[exchange].get(currency, 0)
        self.locked_funds[exchange][currency] = current_locked + amount
        logger.debug(f"🔒 Locked {amount:.4f} {currency} on {exchange}")

    def unlock_funds(self, exchange: str, currency: str, amount: float):
        """Release locked funds after order completion/cancellation."""
        if exchange in self.locked_funds:
            current_locked = self.locked_funds[exchange].get(currency, 0)
            self.locked_funds[exchange][currency] = max(0, current_locked - amount)
            logger.debug(f"🔓 Unlocked {amount:.4f} {currency} on {exchange}")

    def get_available_balance(self, exchange: str, currency: str) -> float:
        """Get available (total - locked) balance. Used for trade sizing."""
        total = self.balances.get(exchange, {}).get(currency, 0)
        locked = self.locked_funds.get(exchange, {}).get(currency, 0)
        return max(0, total - locked)

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
    
    def get_total_balance_usdt(self, price_store=None) -> float:
        """Get total portfolio value across all exchanges in USDT equivalent.
        
        Converts ALL coin holdings (BTC, ETH, SOL, etc.) to USDT using
        current market prices from PriceStore.
        
        Args:
            price_store: PriceStore instance for current prices. If None, counts only USDT.
            
        Returns:
            Total portfolio value in USDT
        """
        total = 0.0
        for exchange, currencies in self.balances.items():
            total += self._exchange_balance_usdt(exchange, currencies, price_store)
        return total
    
    def _exchange_balance_usdt(self, exchange: str, currencies: Dict[str, float], price_store=None) -> float:
        """Convert all holdings on one exchange to USDT equivalent."""
        total = 0.0
        for coin, amount in currencies.items():
            if amount <= 0:
                continue
            if coin == 'USDT':
                total += amount
            elif price_store:
                # Try to get price from PriceStore: e.g. BTC → BTC-USDT
                symbol = f"{coin}-USDT"
                price = self._get_price_from_store(price_store, symbol, exchange)
                if price > 0:
                    total += amount * price
                else:
                    # Try without exchange-specific price (any exchange)
                    price = self._get_any_price(price_store, symbol)
                    if price > 0:
                        total += amount * price
        return total
    
    def _get_price_from_store(self, price_store, symbol: str, exchange: str) -> float:
        """Get mid-price for a symbol on a specific exchange from PriceStore.
        
        PriceStore.snapshot() returns: {symbol: {exchange: {bid, ask, ...}}}
        """
        try:
            snapshot = price_store.snapshot()
            exmap = snapshot.get(symbol, {})
            if exchange in exmap:
                entry = exmap[exchange]
                bid = entry.get('bid', 0) or 0
                ask = entry.get('ask', 0) or 0
                if bid > 0 and ask > 0:
                    return (bid + ask) / 2
                return bid or ask
        except Exception:
            pass
        return 0.0
    
    def _get_any_price(self, price_store, symbol: str) -> float:
        """Get mid-price for a symbol from any exchange in PriceStore.
        
        PriceStore.snapshot() returns: {symbol: {exchange: {bid, ask, ...}}}
        """
        try:
            snapshot = price_store.snapshot()
            exmap = snapshot.get(symbol, {})
            for _ex, entry in exmap.items():
                bid = entry.get('bid', 0) or 0
                ask = entry.get('ask', 0) or 0
                if bid > 0 and ask > 0:
                    return (bid + ask) / 2
                if bid > 0 or ask > 0:
                    return bid or ask
        except Exception:
            pass
        return 0.0

    def get_symbol_price(self, price_store, symbol: str, exchange: str = '') -> float:
        """Public method: get price for a symbol, trying specific exchange first then any.
        
        Args:
            price_store: PriceStore instance
            symbol: e.g. 'BTC-USDT'
            exchange: specific exchange to check first (optional)
        
        Returns:
            Mid-price in USDT, or 0.0 if unavailable
        """
        if not price_store:
            return 0.0
        price = self._get_price_from_store(price_store, symbol, exchange) if exchange else 0.0
        if price <= 0:
            price = self._get_any_price(price_store, symbol)
        return price

    def get_exchange_balance_usdt(self, exchange: str, price_store=None) -> float:
        """Get total portfolio value for one exchange in USDT equivalent."""
        currencies = self.balances.get(exchange, {})
        return self._exchange_balance_usdt(exchange, currencies, price_store)
    
    def get_portfolio_breakdown(self, price_store=None) -> Dict[str, Dict]:
        """Get detailed portfolio breakdown per exchange.
        
        Returns:
            Dict of {exchange: {coins: {coin: {amount, usdt_value}}, total_usdt: float}}
        """
        result = {}
        for exchange, currencies in sorted(self.balances.items()):
            coins = {}
            exchange_total = 0.0
            for coin, amount in sorted(currencies.items()):
                if amount <= 0:
                    continue
                if coin == 'USDT':
                    usdt_value = amount
                elif price_store:
                    symbol = f"{coin}-USDT"
                    price = self._get_price_from_store(price_store, symbol, exchange)
                    if price <= 0:
                        price = self._get_any_price(price_store, symbol)
                    usdt_value = amount * price if price > 0 else 0.0
                else:
                    usdt_value = 0.0
                coins[coin] = {'amount': amount, 'usdt_value': usdt_value}
                exchange_total += usdt_value
            result[exchange] = {'coins': coins, 'total_usdt': exchange_total}
        return result

    def get_excluded_exchanges(self) -> Set[str]:
        """Get set of exchanges currently excluded due to low balance."""
        return self.excluded_exchanges.copy()
    
    def print_summary(self, price_store=None):
        """Print balance summary to console with all coins in USDT equivalent."""
        mode_label = " (VIRTUAL)" if settings.DRY_RUN else ""
        print(f"\n{'='*60}")
        print(f"  Balance Summary{mode_label}")
        print(f"{'='*60}")
        
        if not self.balances:
            print("  No balance data available")
        else:
            breakdown = self.get_portfolio_breakdown(price_store)
            grand_total = 0.0
            
            for exchange, data in sorted(breakdown.items()):
                status = "❌ EXCLUDED" if exchange in self.excluded_exchanges else "✅"
                ex_total = data['total_usdt']
                grand_total += ex_total
                
                # Show main line: exchange total
                print(f"  {exchange:12s} {status} ${ex_total:>10.2f} USDT equiv")
                
                # Show coin breakdown (skip if only USDT)
                coins = data['coins']
                non_usdt_coins = {c: v for c, v in coins.items() if c != 'USDT' and v['usdt_value'] > 0.01}
                if non_usdt_coins:
                    usdt_amt = coins.get('USDT', {}).get('amount', 0)
                    parts = []
                    if usdt_amt > 0.01:
                        parts.append(f"USDT: ${usdt_amt:.2f}")
                    for coin, info in sorted(non_usdt_coins.items()):
                        parts.append(f"{coin}: {info['amount']:.6g} (${info['usdt_value']:.2f})")
                    if parts:
                        print(f"  {'':12s}    {' | '.join(parts)}")
            
            print(f"  {'-'*58}")
            print(f"  {'Total':12s}    ${grand_total:>10.2f} USDT equiv")
        
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
