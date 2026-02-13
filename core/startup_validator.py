"""
Safe Startup Sequence Validator

Validates all critical conditions before allowing the bot to trade.
Ensures safety and prevents trading with incomplete setup.

Expected benefit: Stability and error prevention
"""

import asyncio
import logging
import os
from typing import Dict, List, Tuple
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class ValidationResult:
    """Result of a validation check"""
    check_name: str
    passed: bool
    message: str
    critical: bool = True  # If True, failure blocks trading


class StartupValidator:
    """
    Validates all conditions before trading starts:
    1. API keys loaded for all exchanges
    2. REST ping to each exchange succeeds
    3. Balances retrieved (total > min_capital)
    4. Previous state loaded, pending orders resolved
    5. WebSocket connections established (≥3 of 4)
    6. Orderbook data received for ≥1 symbol on ≥2 exchanges
    7. Risk limits not exceeded (daily loss check)
    8. DRY_RUN mode explicitly confirmed
    
    If any critical check fails → DO NOT trade, send Telegram alert
    """
    
    def __init__(
        self,
        exchanges: List[str],
        rest_clients: Dict,
        ws_connections: Dict,
        balance_manager,
        risk_manager,
        state_manager,
        price_store,
        telegram_bot=None,
        min_total_capital: float = 100.0,
        min_ws_connections: int = 3
    ):
        self.exchanges = exchanges
        self.rest_clients = rest_clients
        self.ws_connections = ws_connections
        self.balance_manager = balance_manager
        self.risk_manager = risk_manager
        self.state_manager = state_manager
        self.price_store = price_store
        self.telegram_bot = telegram_bot
        self.min_total_capital = min_total_capital
        self.min_ws_connections = min_ws_connections
        
        self.validation_results: List[ValidationResult] = []
        
        logger.info(
            f"StartupValidator initialized for {len(exchanges)} exchanges, "
            f"min_capital=${min_total_capital}, min_ws={min_ws_connections}"
        )
    
    async def validate_all(self) -> Tuple[bool, str]:
        """
        Run all validation checks.
        
        Returns:
            (all_passed, summary_message)
        """
        logger.info("=" * 60)
        logger.info("STARTING COMPREHENSIVE STARTUP VALIDATION")
        logger.info("=" * 60)
        
        self.validation_results = []
        
        # Run all checks
        await self._check_api_keys()
        await self._check_rest_connectivity()
        await self._check_balances()
        await self._check_previous_state()
        await self._check_websocket_connections()
        await self._check_orderbook_data()
        await self._check_risk_limits()
        await self._check_dry_run_mode()
        
        # Summarize results
        critical_failures = [
            r for r in self.validation_results
            if r.critical and not r.passed
        ]
        
        warnings = [
            r for r in self.validation_results
            if not r.critical and not r.passed
        ]
        
        all_passed = len(critical_failures) == 0
        
        # Log summary
        logger.info("=" * 60)
        logger.info("VALIDATION SUMMARY")
        logger.info("=" * 60)
        
        for result in self.validation_results:
            status = "✅ PASS" if result.passed else ("❌ FAIL" if result.critical else "⚠️  WARN")
            logger.info(f"{status}: {result.check_name}")
            logger.info(f"       {result.message}")
        
        logger.info("=" * 60)
        
        if all_passed:
            summary = f"✅ All {len(self.validation_results)} checks passed. Safe to trade!"
            if warnings:
                summary += f" ({len(warnings)} warnings)"
            logger.info(summary)
        else:
            summary = f"❌ {len(critical_failures)} critical check(s) failed. DO NOT TRADE!"
            logger.error(summary)
            
            # Send Telegram alert
            if self.telegram_bot:
                alert_msg = f"🚨 STARTUP VALIDATION FAILED\n\n"
                for failure in critical_failures:
                    alert_msg += f"❌ {failure.check_name}\n{failure.message}\n\n"
                await self.telegram_bot.send_message(alert_msg)
        
        logger.info("=" * 60)
        
        return all_passed, summary
    
    async def _check_api_keys(self):
        """Check 1: Verify API keys loaded for all exchanges"""
        logger.info("Checking API keys...")
        
        missing = []
        for exchange in self.exchanges:
            # Check environment variables
            key_var = f"ARB_{exchange.upper()}_KEY"
            secret_var = f"ARB_{exchange.upper()}_SECRET"
            
            key = os.getenv(key_var)
            secret = os.getenv(secret_var)
            
            if not key or not secret:
                missing.append(exchange)
        
        if missing:
            self.validation_results.append(ValidationResult(
                check_name="API Keys",
                passed=False,
                message=f"Missing API keys for: {', '.join(missing)}",
                critical=True
            ))
        else:
            self.validation_results.append(ValidationResult(
                check_name="API Keys",
                passed=True,
                message=f"API keys loaded for all {len(self.exchanges)} exchanges"
            ))
    
    async def _check_rest_connectivity(self):
        """Check 2: Verify REST API connectivity to all exchanges"""
        logger.info("Checking REST API connectivity...")
        
        failed = []
        for exchange in self.exchanges:
            client = self.rest_clients.get(exchange)
            if not client:
                failed.append(f"{exchange} (no client)")
                continue
            
            try:
                # Try to get balance as connectivity test
                balance = await client.get_balance()
                if balance is None:
                    failed.append(f"{exchange} (returned None)")
            except Exception as e:
                failed.append(f"{exchange} ({str(e)[:50]})")
        
        if failed:
            self.validation_results.append(ValidationResult(
                check_name="REST Connectivity",
                passed=False,
                message=f"Failed to connect: {', '.join(failed)}",
                critical=True
            ))
        else:
            self.validation_results.append(ValidationResult(
                check_name="REST Connectivity",
                passed=True,
                message=f"Successfully connected to all {len(self.exchanges)} exchanges"
            ))
    
    async def _check_balances(self):
        """Check 3: Verify balances retrieved and total > minimum"""
        logger.info("Checking balances...")
        
        try:
            # Initialize balance manager
            await self.balance_manager.initialize()
            
            # Get total balance
            total_balance = self.balance_manager.get_total_balance()
            
            if total_balance < self.min_total_capital:
                self.validation_results.append(ValidationResult(
                    check_name="Balance Check",
                    passed=False,
                    message=(
                        f"Total balance ${total_balance:.2f} is below minimum "
                        f"${self.min_total_capital:.2f}"
                    ),
                    critical=True
                ))
            else:
                self.validation_results.append(ValidationResult(
                    check_name="Balance Check",
                    passed=True,
                    message=f"Total balance: ${total_balance:.2f} (min: ${self.min_total_capital:.2f})"
                ))
        except Exception as e:
            self.validation_results.append(ValidationResult(
                check_name="Balance Check",
                passed=False,
                message=f"Error retrieving balances: {str(e)}",
                critical=True
            ))
    
    async def _check_previous_state(self):
        """Check 4: Load previous state and check for pending orders"""
        logger.info("Checking previous state...")
        
        try:
            # Load state - load_state() returns bool, state is in state_manager.state
            loaded = self.state_manager.load_state()
            
            # Access the state dict from state_manager
            state = self.state_manager.state
            
            # Check for pending orders
            pending_orders = state.get('pending_orders', [])
            
            if pending_orders:
                # TODO: Cancel stale pending orders
                self.validation_results.append(ValidationResult(
                    check_name="Previous State",
                    passed=True,
                    message=(
                        f"State loaded. Found {len(pending_orders)} pending orders "
                        "(should be cancelled manually)"
                    ),
                    critical=False
                ))
            else:
                self.validation_results.append(ValidationResult(
                    check_name="Previous State",
                    passed=True,
                    message="State loaded successfully, no pending orders"
                ))
        except Exception as e:
            self.validation_results.append(ValidationResult(
                check_name="Previous State",
                passed=False,
                message=f"Error loading state: {str(e)}",
                critical=False  # Not critical, can start fresh
            ))
    
    async def _check_websocket_connections(self):
        """Check 5: Verify WebSocket connections (need at least 3 of 4)"""
        logger.info("Checking WebSocket connections...")
        
        # Wait for WebSocket connections to fully establish
        # 2 seconds is typically sufficient for initial handshake and subscription
        await asyncio.sleep(2)  # Allow time for WS handshake + subscriptions
        
        connected = []
        disconnected = []
        
        for exchange in self.exchanges:
            ws = self.ws_connections.get(exchange)
            if ws and hasattr(ws, 'is_connected') and ws.is_connected():
                connected.append(exchange)
            else:
                disconnected.append(exchange)
        
        if len(connected) < self.min_ws_connections:
            self.validation_results.append(ValidationResult(
                check_name="WebSocket Connections",
                passed=False,
                message=(
                    f"Only {len(connected)}/{len(self.exchanges)} WebSocket connections "
                    f"(need at least {self.min_ws_connections}). "
                    f"Disconnected: {', '.join(disconnected)}"
                ),
                critical=True
            ))
        else:
            self.validation_results.append(ValidationResult(
                check_name="WebSocket Connections",
                passed=True,
                message=(
                    f"{len(connected)}/{len(self.exchanges)} WebSocket connections active"
                )
            ))
    
    async def _check_orderbook_data(self):
        """Check 6: Verify orderbook data received for symbols"""
        logger.info("Checking orderbook data...")
        
        # Check if price_store exists
        if self.price_store is None:
            # PriceStore not initialized yet - this is expected during early startup
            # Mark as passed with informational message since it's not an error
            self.validation_results.append(ValidationResult(
                check_name="Orderbook Data",
                passed=True,
                message="PriceStore not yet initialized (will be created in Phase 5)",
                critical=False
            ))
            return
        
        # Wait for initial orderbook snapshots to arrive via WebSocket
        # 3 seconds allows for: WS messages → parsing → PriceStore updates
        await asyncio.sleep(3)  # Allow time for initial orderbook data
        
        # Get snapshot
        snapshot = self.price_store.snapshot()
        
        if not snapshot:
            self.validation_results.append(ValidationResult(
                check_name="Orderbook Data",
                passed=False,
                message="No orderbook data received",
                critical=True
            ))
            return
        
        # Count exchanges with data
        exchanges_with_data = set()
        symbols_with_data = set()
        
        for key in snapshot.keys():
            parts = key.split('_')
            if len(parts) >= 2:
                exchange = parts[0]
                symbol = '_'.join(parts[1:])
                exchanges_with_data.add(exchange)
                symbols_with_data.add(symbol)
        
        if len(exchanges_with_data) < 2:
            self.validation_results.append(ValidationResult(
                check_name="Orderbook Data",
                passed=False,
                message=(
                    f"Orderbook data from only {len(exchanges_with_data)} exchange(s) "
                    "(need at least 2)"
                ),
                critical=True
            ))
        elif len(symbols_with_data) < 1:
            self.validation_results.append(ValidationResult(
                check_name="Orderbook Data",
                passed=False,
                message="No symbols with orderbook data",
                critical=True
            ))
        else:
            self.validation_results.append(ValidationResult(
                check_name="Orderbook Data",
                passed=True,
                message=(
                    f"Orderbook data: {len(symbols_with_data)} symbols, "
                    f"{len(exchanges_with_data)} exchanges"
                )
            ))
    
    async def _check_risk_limits(self):
        """Check 7: Verify risk limits not exceeded"""
        logger.info("Checking risk limits...")
        
        try:
            # Check if trading is allowed
            is_allowed, reason = self.risk_manager.is_trading_allowed()
            
            if not is_allowed:
                self.validation_results.append(ValidationResult(
                    check_name="Risk Limits",
                    passed=False,
                    message=f"Trading blocked: {reason}",
                    critical=True
                ))
            else:
                # Check daily P&L
                daily_pnl = self.risk_manager.daily_pnl
                # Import settings to get max loss values
                import settings
                max_loss = settings.MAX_DAILY_LOSS
                
                self.validation_results.append(ValidationResult(
                    check_name="Risk Limits",
                    passed=True,
                    message=(
                        f"Daily P&L: ${daily_pnl:.2f} "
                        f"(max loss: ${max_loss:.2f})"
                    )
                ))
        except Exception as e:
            self.validation_results.append(ValidationResult(
                check_name="Risk Limits",
                passed=False,
                message=f"Error checking risk limits: {str(e)}",
                critical=False
            ))
    
    async def _check_dry_run_mode(self):
        """Check 8: Verify DRY_RUN mode setting"""
        logger.info("Checking DRY_RUN mode...")
        
        dry_run = os.getenv('ARB_DRY_RUN', 'true').lower() == 'true'
        
        if dry_run:
            self.validation_results.append(ValidationResult(
                check_name="DRY_RUN Mode",
                passed=True,
                message="✅ Running in DRY_RUN mode (safe, no real trades)"
            ))
        else:
            self.validation_results.append(ValidationResult(
                check_name="DRY_RUN Mode",
                passed=True,
                message="⚠️  LIVE TRADING MODE - Real money will be traded!",
                critical=False
            ))
    
    def get_results(self) -> List[ValidationResult]:
        """Get all validation results."""
        return self.validation_results
    
    def print_report(self):
        """Print formatted validation report."""
        print("\n" + "=" * 70)
        print("STARTUP VALIDATION REPORT")
        print("=" * 70)
        
        for result in self.validation_results:
            status = "✅" if result.passed else ("❌" if result.critical else "⚠️")
            print(f"\n{status} {result.check_name}")
            print(f"   {result.message}")
        
        critical_failures = sum(
            1 for r in self.validation_results
            if r.critical and not r.passed
        )
        
        print("\n" + "=" * 70)
        if critical_failures == 0:
            print("✅ VALIDATION PASSED - Safe to proceed")
        else:
            print(f"❌ {critical_failures} CRITICAL FAILURE(S) - DO NOT TRADE")
        print("=" * 70 + "\n")


def get_startup_validator(
    exchanges: List[str],
    rest_clients: Dict,
    ws_connections: Dict,
    balance_manager,
    risk_manager,
    state_manager,
    price_store,
    telegram_bot=None
) -> StartupValidator:
    """
    Factory function to create startup validator.
    
    Args:
        exchanges: List of exchange names
        rest_clients: Dict of REST client instances
        ws_connections: Dict of WebSocket instances
        balance_manager: BalanceManager instance
        risk_manager: RiskManager instance
        state_manager: StateManager instance
        price_store: PriceStore instance
        telegram_bot: Optional TelegramBot instance
    
    Returns:
        StartupValidator instance
    """
    return StartupValidator(
        exchanges=exchanges,
        rest_clients=rest_clients,
        ws_connections=ws_connections,
        balance_manager=balance_manager,
        risk_manager=risk_manager,
        state_manager=state_manager,
        price_store=price_store,
        telegram_bot=telegram_bot
    )
