"""
Smart Order Router
Автоматический выбор лучшей биржи для исполнения ордера
"""
import asyncio
import logging
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime
import statistics

logger = logging.getLogger(__name__)


@dataclass
class VenueQuote:
    """Котировка с биржи"""
    exchange: str
    price: float
    volume: float
    fee: float
    latency: float
    liquidity_score: float
    timestamp: datetime


@dataclass
class RouteResult:
    """Результат маршрутизации"""
    selected_exchange: str
    price: float
    expected_fee: float
    price_improvement: float
    confidence: float
    alternatives: List[VenueQuote]
    reason: str


class SmartOrderRouter:
    """Умная маршрутизация ордеров на лучшую биржу"""
    
    def __init__(self, config: Optional[Dict] = None):
        self.config = config or {}
        
        # Веса для скоринга
        self.price_weight = self.config.get('price_weight', 0.4)
        self.fee_weight = self.config.get('fee_weight', 0.2)
        self.liquidity_weight = self.config.get('liquidity_weight', 0.2)
        self.latency_weight = self.config.get('latency_weight', 0.1)
        self.reliability_weight = self.config.get('reliability_weight', 0.1)
        
        # История надежности бирж
        self.venue_reliability: Dict[str, float] = {}
        self.venue_success_rate: Dict[str, List[bool]] = {}
        self.venue_avg_latency: Dict[str, List[float]] = {}
        
        # Статистика
        self.stats = {
            'total_routes': 0,
            'price_improvements': 0,
            'total_improvement_amount': 0.0,
            'venue_selections': {}
        }
        
        logger.info("SmartOrderRouter initialized")
    
    def calculate_venue_score(
        self, 
        quote: VenueQuote, 
        side: str,  # 'buy' or 'sell'
        amount: float
    ) -> float:
        """Вычислить score биржи для данного ордера"""
        
        # Price score (лучше = выше)
        # Для покупки: ниже цена = лучше
        # Для продажи: выше цена = лучше
        price_score = quote.price if side == 'sell' else (1 / quote.price if quote.price > 0 else 0)
        
        # Fee score (ниже = лучше)
        fee_score = 1 / (1 + quote.fee) if quote.fee >= 0 else 0
        
        # Liquidity score
        liquidity_score = min(quote.liquidity_score, 1.0)
        
        # Latency score (ниже = лучше)
        latency_score = 1 / (1 + quote.latency) if quote.latency > 0 else 1.0
        
        # Reliability score
        reliability_score = self.venue_reliability.get(quote.exchange, 0.9)
        
        # Взвешенная сумма
        total_score = (
            price_score * self.price_weight +
            fee_score * self.fee_weight +
            liquidity_score * self.liquidity_weight +
            latency_score * self.latency_weight +
            reliability_score * self.reliability_weight
        )
        
        return total_score
    
    async def route_order(
        self,
        symbol: str,
        side: str,
        amount: float,
        venues: List[VenueQuote]
    ) -> RouteResult:
        """Выбрать лучшую биржу для ордера"""
        
        if not venues:
            raise ValueError("No venues provided")
        
        # Вычислить scores для всех бирж
        venue_scores = []
        for quote in venues:
            score = self.calculate_venue_score(quote, side, amount)
            venue_scores.append((quote, score))
        
        # Сортировать по score
        venue_scores.sort(key=lambda x: x[1], reverse=True)
        
        best_quote, best_score = venue_scores[0]
        
        # Вычислить price improvement relative to worst venue
        worst_price = max(v.price for v in venues) if side == 'buy' else min(v.price for v in venues)
        if side == 'sell':
            price_improvement = (best_quote.price - worst_price) / worst_price if worst_price > 0 else 0
        else:
            price_improvement = (worst_price - best_quote.price) / worst_price if worst_price > 0 else 0
        
        # Определить причину выбора
        reasons = []
        if best_quote.price == (max(v.price for v in venues) if side == 'sell' else min(v.price for v in venues)):
            reasons.append("best_price")
        if best_quote.fee == min(v.fee for v in venues):
            reasons.append("lowest_fee")
        if best_quote.liquidity_score == max(v.liquidity_score for v in venues):
            reasons.append("best_liquidity")
        if best_quote.latency == min(v.latency for v in venues):
            reasons.append("lowest_latency")
        
        reason = ", ".join(reasons) if reasons else "best_overall_score"
        
        # Confidence based on score difference
        if len(venue_scores) > 1:
            second_best_score = venue_scores[1][1]
            score_diff = best_score - second_best_score
            confidence = min(0.5 + score_diff, 1.0)
        else:
            confidence = 0.9
        
        # Обновить статистику
        self.stats['total_routes'] += 1
        if price_improvement > 0:
            self.stats['price_improvements'] += 1
            self.stats['total_improvement_amount'] += price_improvement * amount * best_quote.price
        
        venue_name = best_quote.exchange
        self.stats['venue_selections'][venue_name] = self.stats['venue_selections'].get(venue_name, 0) + 1
        
        logger.info(
            f"Routed {side} order for {symbol} to {best_quote.exchange} "
            f"(price={best_quote.price}, improvement={price_improvement*100:.2f}%)"
        )
        
        return RouteResult(
            selected_exchange=best_quote.exchange,
            price=best_quote.price,
            expected_fee=best_quote.fee,
            price_improvement=price_improvement,
            confidence=confidence,
            alternatives=[q for q, _ in venue_scores[1:]],
            reason=reason
        )
    
    def update_venue_reliability(self, exchange: str, success: bool, latency: float):
        """Обновить информацию о надежности биржи"""
        
        # Инициализация
        if exchange not in self.venue_success_rate:
            self.venue_success_rate[exchange] = []
            self.venue_avg_latency[exchange] = []
        
        # Добавить результат (keep last 100)
        self.venue_success_rate[exchange].append(success)
        if len(self.venue_success_rate[exchange]) > 100:
            self.venue_success_rate[exchange].pop(0)
        
        self.venue_avg_latency[exchange].append(latency)
        if len(self.venue_avg_latency[exchange]) > 100:
            self.venue_avg_latency[exchange].pop(0)
        
        # Вычислить reliability score
        self.venue_reliability[exchange] = self._calculate_success_rate(exchange)
    
    def _calculate_success_rate(self, exchange: str) -> float:
        """Calculate success rate for an exchange, defaults to 0.9 if no data."""
        rates = self.venue_success_rate.get(exchange, [])
        return sum(rates) / len(rates) if rates else 0.9
    
    def get_venue_statistics(self, exchange: str) -> Dict:
        """Получить статистику по бирже"""
        if exchange not in self.venue_success_rate:
            return {
                'success_rate': 0.9,  # Default
                'avg_latency': 0.0,
                'total_orders': 0
            }
        
        success_rate = self._calculate_success_rate(exchange)
        avg_latency = statistics.mean(self.venue_avg_latency[exchange]) if self.venue_avg_latency[exchange] else 0.0
        
        return {
            'success_rate': success_rate,
            'avg_latency': avg_latency,
            'total_orders': len(self.venue_success_rate[exchange]),
            'reliability_score': self.venue_reliability.get(exchange, 0.9)
        }
    
    def get_best_venues(self, symbol: str, side: str, top_n: int = 3) -> List[str]:
        """Получить топ бирж для символа"""
        # Simplified - would need actual market data
        return list(self.venue_reliability.keys())[:top_n]
    
    def get_routing_statistics(self) -> Dict:
        """Получить общую статистику маршрутизации"""
        avg_improvement = (
            self.stats['total_improvement_amount'] / self.stats['total_routes']
            if self.stats['total_routes'] > 0 else 0
        )
        
        return {
            **self.stats,
            'average_improvement': avg_improvement,
            'improvement_rate': (
                self.stats['price_improvements'] / self.stats['total_routes']
                if self.stats['total_routes'] > 0 else 0
            )
        }


# Пример использования
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    router = SmartOrderRouter()
    
    # Симуляция котировок с разных бирж
    venues = [
        VenueQuote(
            exchange="Binance",
            price=50000.5,
            volume=10.0,
            fee=0.001,
            latency=0.05,
            liquidity_score=0.95,
            timestamp=datetime.now()
        ),
        VenueQuote(
            exchange="KuCoin",
            price=50001.0,
            volume=8.0,
            fee=0.0008,
            latency=0.08,
            liquidity_score=0.85,
            timestamp=datetime.now()
        ),
        VenueQuote(
            exchange="Bybit",
            price=49999.0,
            volume=12.0,
            fee=0.0012,
            latency=0.06,
            liquidity_score=0.90,
            timestamp=datetime.now()
        )
    ]
    
    # Маршрутизация
    async def test():
        result = await router.route_order("BTC/USDT", "buy", 1.0, venues)
        print(f"Selected: {result.selected_exchange}")
        print(f"Price: {result.price}")
        print(f"Improvement: {result.price_improvement*100:.2f}%")
        print(f"Reason: {result.reason}")
        print(f"Statistics: {router.get_routing_statistics()}")
    
    asyncio.run(test())
