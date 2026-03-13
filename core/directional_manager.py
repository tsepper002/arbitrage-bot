"""
DirectionalTradeManager — Single-exchange directional trade execution.

Handles strategies that BUY on one exchange and SELL later when target is hit.
Separate execution path from the cross-exchange arbitrage engine.

Strategies routed here: MOMENTUM, BREAKOUT, DCA, GRID_TRADING, VOLATILITY.
"""
import asyncio
import logging
import time
import uuid
from dataclasses import dataclass, field
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class OpenPosition:
    """A single directional position."""
    id: str
    symbol: str
    exchange: str
    side: str           # 'long'
    qty: float
    entry_price: float
    entry_time: float
    strategy: str
    tp_pct: float       # take-profit %
    sl_pct: float       # stop-loss %
    cost_usdt: float    # total cost in USDT
    order_id: str = ''  # exchange order ID
    status: str = 'open'
    exit_price: float = 0.0
    exit_time: float = 0.0
    pnl_usdt: float = 0.0


class DirectionalTradeManager:
    """Manages directional (single-exchange) trades with TP/SL.
    
    Integration points:
    - Receives signals from strategy_dispatcher_loop (MOMENTUM, BREAKOUT, etc.)
    - Uses rest_clients for order placement
    - Uses price_store for current price checks
    - Uses balance_manager for balance verification
    """
    
    def __init__(self, rest_clients: dict, price_store, balance_manager, settings_mod):
        self.rest_clients = rest_clients
        self.price_store = price_store
        self.balance_manager = balance_manager
        self.settings = settings_mod
        
        self.positions: List[OpenPosition] = []
        self.closed_positions: List[OpenPosition] = []
        self._lock = asyncio.Lock()
        
        # Stats
        self.total_trades = 0
        self.winning_trades = 0
        self.losing_trades = 0
        self.total_pnl = 0.0
        self._signals_received = 0
        self._signals_rejected = 0
        
        # Config
        self.max_positions = getattr(settings_mod, 'MAX_DIRECTIONAL_POSITIONS', 8)
        self.risk_pct = getattr(settings_mod, 'DIRECTIONAL_RISK_PCT', 1.5) / 100.0
        self.tp_sl_config = getattr(settings_mod, 'DIRECTIONAL_TP_SL', {})
        self.check_interval = getattr(settings_mod, 'DIRECTIONAL_CHECK_INTERVAL_SEC', 2.0)
        
        logger.info(f"📊 DirectionalTradeManager initialized: max_positions={self.max_positions}, "
                     f"risk={self.risk_pct*100:.1f}%, check_interval={self.check_interval}s")
    
    # ------------------------------------------------------------------
    # Signal Processing
    # ------------------------------------------------------------------
    async def process_signal(self, signal: dict) -> Optional[str]:
        """Process a directional strategy signal. Returns position ID if opened."""
        async with self._lock:
            self._signals_received += 1
            strategy = signal.get('strategy', '')
            symbol = signal.get('symbol', '')
            data = signal.get('data', {})
            
            # Validate
            if not symbol or not strategy:
                self._signals_rejected += 1
                return None
            
            # Max positions check
            open_count = len([p for p in self.positions if p.status == 'open'])
            if open_count >= self.max_positions:
                logger.debug(f"⏭️ Directional: max positions ({self.max_positions}) reached, skip {strategy} {symbol}")
                self._signals_rejected += 1
                return None
            
            # Duplicate check: don't open same symbol+strategy twice
            for p in self.positions:
                if p.status == 'open' and p.symbol == symbol and p.strategy == strategy:
                    self._signals_rejected += 1
                    return None
            
            # Find best exchange to trade on
            exchange = self._select_exchange(symbol)
            if not exchange:
                logger.debug(f"⏭️ Directional: no exchange available for {symbol}")
                self._signals_rejected += 1
                return None
            
            # Get current price
            price = self._get_price(symbol, exchange)
            if not price or price <= 0:
                self._signals_rejected += 1
                return None
            
            # Calculate position size
            trade_size_usdt = self._calculate_size(exchange)
            if trade_size_usdt < 5.0:  # Absolute minimum
                logger.debug(f"⏭️ Directional: trade size ${trade_size_usdt:.2f} too small for {symbol}")
                self._signals_rejected += 1
                return None
            
            # Get TP/SL config for this strategy
            tp_sl = self.tp_sl_config.get(strategy, {'tp_pct': 1.5, 'sl_pct': 1.0})
            
            # Signal confidence can tighten/loosen TP
            confidence = data.get('confidence', data.get('strength', 0.5))
            if confidence > 0.8:
                tp_sl = {**tp_sl, 'tp_pct': tp_sl['tp_pct'] * 0.8}  # Tighter TP for high confidence
            
            # Calculate quantity
            qty = trade_size_usdt / price
            
            # Execute buy
            pos_id = await self._open_position(
                symbol=symbol,
                exchange=exchange,
                qty=qty,
                price=price,
                strategy=strategy,
                tp_pct=tp_sl['tp_pct'],
                sl_pct=tp_sl['sl_pct'],
                cost_usdt=trade_size_usdt,
            )
            return pos_id
    
    def _select_exchange(self, symbol: str) -> Optional[str]:
        """Select best exchange for a directional trade.
        
        Prefers exchanges with:
        1. Available balance
        2. Price data available
        3. Lower fees (MEXC > Bybit > Binance > KuCoin > HTX)
        """
        # Priority order: MEXC (0% maker), Bybit, Binance, KuCoin, HTX
        exchange_priority = ['MEXC', 'Bybit', 'Binance', 'KuCoin', 'HTX']
        
        for ex in exchange_priority:
            if ex not in self.rest_clients:
                continue
            # Check if we have price data for this symbol on this exchange
            price = self._get_price(symbol, ex)
            if price and price > 0:
                # Check balance
                bal = self._get_usdt_balance(ex)
                if bal and bal > 5.0:
                    return ex
        return None
    
    def _get_price(self, symbol: str, exchange: str) -> float:
        """Get current price from price store."""
        if not self.price_store:
            return 0.0
        try:
            prices = self.price_store.get(symbol)
            if prices and exchange in prices:
                ex_data = prices[exchange]
                if isinstance(ex_data, dict):
                    bid = ex_data.get('bid', 0)
                    ask = ex_data.get('ask', 0)
                    if bid > 0 and ask > 0:
                        return (bid + ask) / 2
                elif isinstance(ex_data, (int, float)) and ex_data > 0:
                    return float(ex_data)
        except Exception:
            pass
        return 0.0
    
    def _get_usdt_balance(self, exchange: str) -> float:
        """Get available USDT balance on exchange."""
        if not self.balance_manager:
            return 0.0
        try:
            bal = self.balance_manager.get_balance(exchange)
            if isinstance(bal, dict):
                return bal.get('USDT', bal.get('usdt', 0.0))
            return 0.0
        except Exception:
            return 0.0
    
    def _calculate_size(self, exchange: str) -> float:
        """Calculate trade size based on risk percentage."""
        bal = self._get_usdt_balance(exchange)
        if bal <= 0:
            return 0.0
        size = bal * self.risk_pct
        # Clamp to 8-15 USDT range for small accounts
        min_size = getattr(self.settings, 'MIN_TRADE_SIZE_USDT', 8.0)
        max_size = min(bal * 0.3, 15.0)  # Never more than 30% of exchange balance
        return max(min(size, max_size), min(min_size, bal * 0.9))
    
    # ------------------------------------------------------------------
    # Position Management
    # ------------------------------------------------------------------
    async def _open_position(self, symbol: str, exchange: str, qty: float,
                             price: float, strategy: str, tp_pct: float,
                             sl_pct: float, cost_usdt: float) -> Optional[str]:
        """Execute a market buy and create a tracked position."""
        client = self.rest_clients.get(exchange)
        if not client:
            return None
        
        pos_id = str(uuid.uuid4())[:8]
        
        try:
            # Place market buy order
            result = await client.place_order(
                symbol=symbol,
                side='buy',
                order_type='market',
                quantity=qty,
            )
            order_id = ''
            if isinstance(result, dict):
                order_id = str(result.get('orderId', result.get('order_id', '')))
            
            pos = OpenPosition(
                id=pos_id,
                symbol=symbol,
                exchange=exchange,
                side='long',
                qty=qty,
                entry_price=price,
                entry_time=time.time(),
                strategy=strategy,
                tp_pct=tp_pct,
                sl_pct=sl_pct,
                cost_usdt=cost_usdt,
                order_id=order_id,
            )
            self.positions.append(pos)
            self.total_trades += 1
            
            logger.info(f"📈 DIRECTIONAL BUY: {strategy} {symbol} on {exchange} "
                        f"qty={qty:.4f} @ ${price:.4f} (${cost_usdt:.2f}) "
                        f"TP={tp_pct}% SL={sl_pct}% [ID:{pos_id}]")
            return pos_id
            
        except Exception as e:
            logger.warning(f"⚠️ Directional buy failed: {exchange} {symbol}: {e}")
            return None
    
    async def _close_position(self, pos: OpenPosition, reason: str) -> bool:
        """Close a position by selling."""
        client = self.rest_clients.get(pos.exchange)
        if not client:
            return False
        
        try:
            current_price = self._get_price(pos.symbol, pos.exchange)
            
            await client.place_order(
                symbol=pos.symbol,
                side='sell',
                order_type='market',
                quantity=pos.qty,
            )
            
            pos.exit_price = current_price if current_price > 0 else pos.entry_price
            pos.exit_time = time.time()
            pos.status = 'closed'
            pos.pnl_usdt = (pos.exit_price - pos.entry_price) * pos.qty
            
            self.total_pnl += pos.pnl_usdt
            if pos.pnl_usdt >= 0:
                self.winning_trades += 1
            else:
                self.losing_trades += 1
            
            # Move to closed list
            self.closed_positions.append(pos)
            self.positions = [p for p in self.positions if p.id != pos.id]
            
            emoji = "✅" if pos.pnl_usdt >= 0 else "❌"
            pnl_pct = ((pos.exit_price - pos.entry_price) / pos.entry_price) * 100 if pos.entry_price > 0 else 0
            logger.info(f"{emoji} DIRECTIONAL CLOSE ({reason}): {pos.strategy} {pos.symbol} on {pos.exchange} "
                        f"PnL: ${pos.pnl_usdt:.4f} ({pnl_pct:+.2f}%) "
                        f"held {pos.exit_time - pos.entry_time:.0f}s [ID:{pos.id}]")
            return True
            
        except Exception as e:
            logger.warning(f"⚠️ Directional sell failed: {pos.exchange} {pos.symbol}: {e}")
            return False
    
    # ------------------------------------------------------------------
    # Position Monitoring Loop
    # ------------------------------------------------------------------
    async def monitoring_loop(self):
        """Background task: check all open positions for TP/SL every N seconds."""
        logger.info(f"📊 Directional position monitor started (interval={self.check_interval}s)")
        
        while True:
            try:
                await asyncio.sleep(self.check_interval)
                await self._check_all_positions()
            except asyncio.CancelledError:
                # Graceful shutdown: close all positions
                logger.info("📊 Directional manager shutting down — closing all positions...")
                await self._close_all_positions("SHUTDOWN")
                raise
            except Exception as e:
                logger.error(f"Directional monitor error: {e}")
                await asyncio.sleep(5)
    
    async def _check_all_positions(self):
        """Check TP/SL for all open positions."""
        async with self._lock:
            for pos in list(self.positions):
                if pos.status != 'open':
                    continue
                
                current_price = self._get_price(pos.symbol, pos.exchange)
                if not current_price or current_price <= 0:
                    continue
                
                pnl_pct = ((current_price - pos.entry_price) / pos.entry_price) * 100
                
                # Take profit
                if pnl_pct >= pos.tp_pct:
                    await self._close_position(pos, f"TP hit ({pnl_pct:+.2f}% >= {pos.tp_pct}%)")
                    continue
                
                # Stop loss
                if pnl_pct <= -pos.sl_pct:
                    await self._close_position(pos, f"SL hit ({pnl_pct:+.2f}% <= -{pos.sl_pct}%)")
                    continue
                
                # Timeout: close positions older than 1 hour
                age_sec = time.time() - pos.entry_time
                if age_sec > 3600:
                    await self._close_position(pos, f"TIMEOUT ({age_sec:.0f}s)")
                    continue
    
    async def _close_all_positions(self, reason: str):
        """Emergency close all open positions."""
        async with self._lock:
            for pos in list(self.positions):
                if pos.status == 'open':
                    await self._close_position(pos, reason)
    
    # ------------------------------------------------------------------
    # Status/Dashboard
    # ------------------------------------------------------------------
    def get_status(self) -> dict:
        """Get current status for dashboard display."""
        open_pos = [p for p in self.positions if p.status == 'open']
        return {
            'open_positions': len(open_pos),
            'total_trades': self.total_trades,
            'winning': self.winning_trades,
            'losing': self.losing_trades,
            'win_rate': (self.winning_trades / max(self.total_trades, 1)) * 100,
            'total_pnl': self.total_pnl,
            'signals_received': self._signals_received,
            'signals_rejected': self._signals_rejected,
            'positions': [
                {
                    'id': p.id,
                    'symbol': p.symbol,
                    'exchange': p.exchange,
                    'strategy': p.strategy,
                    'entry_price': p.entry_price,
                    'cost_usdt': p.cost_usdt,
                    'tp_pct': p.tp_pct,
                    'sl_pct': p.sl_pct,
                    'age_sec': time.time() - p.entry_time,
                    'unrealized_pnl_pct': (
                        ((self._get_price(p.symbol, p.exchange) or p.entry_price) - p.entry_price) 
                        / p.entry_price * 100
                    ),
                }
                for p in open_pos
            ],
        }
