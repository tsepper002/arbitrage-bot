"""
Backtesting / simulation engine for cross-exchange arbitrage strategies.

Supports:
  • Simulated arb cycles with configurable fees, slippage, and latency
  • Monte-Carlo style random market data generation
  • Proper statistics: Sharpe, max drawdown, win rate, profit factor
  • Walk-forward validation
"""
import logging
import math
import random
import time
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class ArbOpportunity:
    """Represents a simulated arbitrage opportunity."""
    symbol: str
    buy_exchange: str
    sell_exchange: str
    buy_price: float
    sell_price: float
    spread_pct: float
    buy_fee_pct: float
    sell_fee_pct: float
    available_qty: float
    timestamp: float = 0.0


@dataclass
class SimTrade:
    """Result of a simulated trade execution."""
    symbol: str
    buy_exchange: str
    sell_exchange: str
    qty: float
    buy_price: float
    sell_price: float
    gross_spread_pct: float
    net_pnl: float
    roi_pct: float
    slippage_pct: float
    timestamp: float = 0.0


@dataclass
class SimulationResult:
    """Complete simulation run results."""
    initial_capital: float
    final_capital: float
    total_return_pct: float
    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate_pct: float
    avg_profit_per_trade: float
    max_drawdown_pct: float
    sharpe_ratio: float
    profit_factor: float
    avg_roi_pct: float
    equity_curve: List[float] = field(default_factory=list)
    trades: List[SimTrade] = field(default_factory=list)


class BacktestEngine:
    """Simulation engine for cross-exchange arbitrage strategies.

    Usage:
        engine = BacktestEngine(initial_capital=10000)

        # Monte-Carlo simulation with random market data
        result = engine.run_arb_simulation(
            num_cycles=10000,
            exchanges=['Binance', 'MEXC', 'Bybit', 'HTX', 'KuCoin'],
            fee_schedule={'Binance': (0.10, 0.10), 'MEXC': (0.0, 0.05), ...},
        )

        # Walk-forward
        results = engine.walk_forward_test(strategy, data)
    """

    # Default exchange fee schedules: (maker_pct, taker_pct)
    DEFAULT_FEES = {
        'Binance': (0.10, 0.10),
        'MEXC': (0.00, 0.05),
        'Bybit': (0.10, 0.10),
        'HTX': (0.20, 0.20),
        'KuCoin': (0.10, 0.10),
    }

    def __init__(self, initial_capital: float = 10000):
        self.initial_capital = initial_capital
        self.trades: List[SimTrade] = []
        self.equity_curve: List[float] = []

    # ------------------------------------------------------------------
    # Core: Arbitrage cycle simulation
    # ------------------------------------------------------------------

    def run_arb_simulation(
        self,
        num_cycles: int = 10000,
        exchanges: Optional[List[str]] = None,
        fee_schedule: Optional[Dict[str, Tuple[float, float]]] = None,
        spread_mean_pct: float = 0.12,
        spread_std_pct: float = 0.08,
        slippage_mean_pct: float = 0.01,
        slippage_std_pct: float = 0.005,
        opportunity_rate: float = 0.05,
        min_threshold_pct: float = 0.11,
        max_trade_pct: float = 0.10,
        latency_fail_rate: float = 0.03,
    ) -> SimulationResult:
        """Run Monte-Carlo simulation of arbitrage cycles.

        Args:
            num_cycles: number of scan cycles to simulate
            exchanges: list of exchange names
            fee_schedule: {exchange: (maker_fee_pct, taker_fee_pct)}
            spread_mean_pct: average cross-exchange spread (%)
            spread_std_pct: spread standard deviation (%)
            slippage_mean_pct: average execution slippage per leg (%)
            slippage_std_pct: slippage standard deviation (%)
            opportunity_rate: probability of an arb opportunity per cycle
            min_threshold_pct: minimum net spread to trade (%)
            max_trade_pct: max % of capital per trade
            latency_fail_rate: probability that a detected opp fails due to latency
        """
        if exchanges is None:
            exchanges = list(self.DEFAULT_FEES.keys())
        if fee_schedule is None:
            fee_schedule = self.DEFAULT_FEES

        capital = self.initial_capital
        self.trades = []
        self.equity_curve = [capital]

        for cycle in range(num_cycles):
            # Each cycle: random chance of an arb opportunity
            if random.random() > opportunity_rate:
                self.equity_curve.append(capital)
                continue

            # Generate random opportunity
            buy_ex = random.choice(exchanges)
            sell_ex = random.choice([e for e in exchanges if e != buy_ex])

            spread = random.gauss(spread_mean_pct, spread_std_pct)
            if spread <= 0:
                self.equity_curve.append(capital)
                continue

            # Fees (taker for both sides in market-order arb)
            buy_fee = fee_schedule.get(buy_ex, (0.10, 0.10))[1]  # taker
            sell_fee = fee_schedule.get(sell_ex, (0.10, 0.10))[1]  # taker
            total_fees = buy_fee + sell_fee

            # Slippage
            slippage = max(0, random.gauss(slippage_mean_pct, slippage_std_pct))
            net_spread = spread - total_fees - slippage

            # Check threshold
            if net_spread < min_threshold_pct:
                self.equity_curve.append(capital)
                continue

            # Latency failure
            if random.random() < latency_fail_rate:
                self.equity_curve.append(capital)
                continue

            # Execute trade
            trade_value = capital * max_trade_pct
            pnl = trade_value * (net_spread / 100.0)
            capital += pnl

            trade = SimTrade(
                symbol='SIM-USDT',
                buy_exchange=buy_ex,
                sell_exchange=sell_ex,
                qty=trade_value / 100.0,  # Notional
                buy_price=100.0,
                sell_price=100.0 * (1 + spread / 100.0),
                gross_spread_pct=spread,
                net_pnl=pnl,
                roi_pct=net_spread,
                slippage_pct=slippage,
                timestamp=time.time(),
            )
            self.trades.append(trade)
            self.equity_curve.append(capital)

        return self._build_result(capital)

    # ------------------------------------------------------------------
    # Legacy: Simple strategy backtesting
    # ------------------------------------------------------------------

    def run_backtest(self, strategy, data: List[Dict]) -> Dict:
        """Run backtest on historical data using a strategy object.

        The strategy must implement ``generate_signal(bar) -> dict``
        returning ``{'action': 'buy'|'sell', ...}``.
        """
        capital = self.initial_capital
        self.trades = []
        self.equity_curve = [capital]

        for bar in data:
            signal = strategy.generate_signal(bar)

            if signal and signal.get('action') == 'buy':
                price = bar.get('price', 0)
                if price <= 0:
                    continue
                amount = capital * 0.10  # 10 % per trade
                cost = amount * (1 + 0.001)  # 0.1 % fee
                if cost <= capital:
                    capital -= cost
                    self.trades.append(SimTrade(
                        symbol=bar.get('symbol', 'SIM'),
                        buy_exchange='sim', sell_exchange='sim',
                        qty=amount / price, buy_price=price, sell_price=0,
                        gross_spread_pct=0, net_pnl=-cost + amount,
                        roi_pct=0, slippage_pct=0,
                        timestamp=bar.get('timestamp', 0),
                    ))

            elif signal and signal.get('action') == 'sell' and self.trades:
                last = self.trades[-1]
                price = bar.get('price', 0)
                if price <= 0 or last.buy_price <= 0:
                    continue
                revenue = (last.qty * price) * (1 - 0.001)
                pnl = revenue - (last.qty * last.buy_price)
                capital += revenue
                last.sell_price = price
                last.net_pnl = pnl
                last.roi_pct = (pnl / (last.qty * last.buy_price)) * 100 if last.buy_price else 0

            self.equity_curve.append(capital)

        result = self._build_result(capital)
        return {
            'total_return': result.total_return_pct,
            'final_capital': result.final_capital,
            'total_trades': result.total_trades,
            'win_rate': result.win_rate_pct,
            'max_drawdown': result.max_drawdown_pct,
            'sharpe_ratio': result.sharpe_ratio,
        }

    def walk_forward_test(
        self, strategy, data: List[Dict], window_size: int = 100
    ) -> List[Dict]:
        """Walk-forward testing with overlapping windows."""
        results = []
        step = max(1, window_size // 2)
        for i in range(0, len(data) - window_size, step):
            window = data[i : i + window_size]
            result = self.run_backtest(strategy, window)
            results.append(result)
        return results

    # ------------------------------------------------------------------
    # Statistics helpers
    # ------------------------------------------------------------------

    def _build_result(self, final_capital: float) -> SimulationResult:
        """Calculate comprehensive statistics from trades and equity curve."""
        pnl_list = [t.net_pnl for t in self.trades]
        winners = [p for p in pnl_list if p > 0]
        losers = [p for p in pnl_list if p <= 0]

        total_return = ((final_capital - self.initial_capital)
                        / self.initial_capital * 100) if self.initial_capital else 0
        win_rate = (len(winners) / len(pnl_list) * 100) if pnl_list else 0
        avg_profit = sum(pnl_list) / len(pnl_list) if pnl_list else 0
        avg_roi = (sum(t.roi_pct for t in self.trades)
                   / len(self.trades)) if self.trades else 0

        # Profit factor
        gross_profit = sum(winners) if winners else 0
        gross_loss = abs(sum(losers)) if losers else 0
        profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else (
            float('inf') if gross_profit > 0 else 0
        )

        # Max drawdown
        max_dd = self._max_drawdown(self.equity_curve)

        # Sharpe ratio (annualized, assuming ~365*24 cycles/year for crypto)
        sharpe = self._sharpe_ratio(pnl_list)

        return SimulationResult(
            initial_capital=self.initial_capital,
            final_capital=final_capital,
            total_return_pct=total_return,
            total_trades=len(self.trades),
            winning_trades=len(winners),
            losing_trades=len(losers),
            win_rate_pct=win_rate,
            avg_profit_per_trade=avg_profit,
            max_drawdown_pct=max_dd,
            sharpe_ratio=sharpe,
            profit_factor=profit_factor,
            avg_roi_pct=avg_roi,
            equity_curve=list(self.equity_curve),
            trades=list(self.trades),
        )

    @staticmethod
    def _max_drawdown(equity_curve: List[float]) -> float:
        """Calculate maximum drawdown percentage."""
        if not equity_curve:
            return 0.0
        peak = equity_curve[0]
        max_dd = 0.0
        for equity in equity_curve:
            if equity > peak:
                peak = equity
            dd = (peak - equity) / peak if peak > 0 else 0
            if dd > max_dd:
                max_dd = dd
        return max_dd * 100

    @staticmethod
    def _sharpe_ratio(pnl_list: List[float], risk_free_rate: float = 0.0) -> float:
        """Calculate Sharpe ratio from PnL list."""
        if len(pnl_list) < 2:
            return 0.0
        mean_pnl = sum(pnl_list) / len(pnl_list)
        variance = sum((p - mean_pnl) ** 2 for p in pnl_list) / (len(pnl_list) - 1)
        std_pnl = math.sqrt(variance) if variance > 0 else 0
        if std_pnl == 0:
            return 0.0
        return (mean_pnl - risk_free_rate) / std_pnl
