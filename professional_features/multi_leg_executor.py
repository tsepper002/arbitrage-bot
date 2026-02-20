"""
Multi-Leg Executor
Одновременное исполнение на нескольких биржах с гарантией атомарности
"""
import asyncio
import logging
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime
from enum import Enum

logger = logging.getLogger(__name__)


class LegStatus(Enum):
    """Статус части сделки"""
    PENDING = "pending"
    EXECUTING = "executing"
    COMPLETED = "completed"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"


@dataclass
class OrderLeg:
    """Одна нога многоногой сделки"""
    leg_id: str
    exchange: str
    symbol: str
    side: str  # 'buy' or 'sell'
    amount: float
    price: Optional[float] = None  # None for market order
    status: LegStatus = LegStatus.PENDING
    order_id: Optional[str] = None
    filled_amount: float = 0.0
    average_price: float = 0.0
    error: Optional[str] = None


@dataclass
class MultiLegResult:
    """Результат выполнения многоногой сделки"""
    transaction_id: str
    success: bool
    legs: List[OrderLeg]
    total_execution_time: float
    completed_legs: int
    failed_legs: int
    rolled_back: bool
    error_message: Optional[str] = None


class MultiLegExecutor:
    """Исполнитель многоноч сделок с атомарностью и rollback"""
    
    def __init__(self, exchange_clients: Dict, config: Optional[Dict] = None):
        self.exchange_clients = exchange_clients
        self.config = config or {}
        
        # Настройки
        self.max_execution_time = self.config.get('max_execution_time', 30.0)  # seconds
        self.retry_attempts = self.config.get('retry_attempts', 3)
        self.partial_fill_threshold = self.config.get('partial_fill_threshold', 0.95)  # 95%
        
        # Активные транзакции
        self.active_transactions: Dict[str, List[OrderLeg]] = {}
        
        # Статистика
        self.stats = {
            'total_transactions': 0,
            'successful_transactions': 0,
            'failed_transactions': 0,
            'rollbacks': 0,
            'total_legs_executed': 0
        }
        
        logger.info("MultiLegExecutor initialized")
    
    async def execute_multi_leg(
        self, 
        legs: List[OrderLeg],
        transaction_id: Optional[str] = None,
        require_all: bool = True
    ) -> MultiLegResult:
        """
        Выполнить многоногую сделку
        
        Args:
            legs: Список ног для выполнения
            transaction_id: ID транзакции (генерируется если None)
            require_all: Требовать выполнения всех ног (иначе откат)
        """
        if not legs:
            raise ValueError("No legs provided")
        
        transaction_id = transaction_id or f"mtx_{datetime.now().timestamp()}"
        start_time = datetime.now()
        
        self.active_transactions[transaction_id] = legs
        self.stats['total_transactions'] += 1
        
        logger.info(f"Starting multi-leg transaction {transaction_id} with {len(legs)} legs")
        
        try:
            # Выполнить все ноги параллельно
            tasks = [self._execute_leg(leg, transaction_id) for leg in legs]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Проверить результаты
            completed_legs = sum(1 for leg in legs if leg.status == LegStatus.COMPLETED)
            failed_legs = sum(1 for leg in legs if leg.status == LegStatus.FAILED)
            
            execution_time = (datetime.now() - start_time).total_seconds()
            
            # Определить успех
            if require_all:
                success = completed_legs == len(legs)
            else:
                success = completed_legs > 0
            
            # Rollback если не все ноги выполнены и require_all=True
            rolled_back = False
            if not success and require_all and completed_legs > 0:
                logger.warning(f"Rolling back transaction {transaction_id}")
                await self._rollback_transaction(transaction_id, legs)
                rolled_back = True
                self.stats['rollbacks'] += 1
            
            # Обновить статистику
            if success:
                self.stats['successful_transactions'] += 1
            else:
                self.stats['failed_transactions'] += 1
            
            self.stats['total_legs_executed'] += completed_legs
            
            error_message = None
            if failed_legs > 0:
                failed_leg_errors = [leg.error for leg in legs if leg.error]
                error_message = "; ".join(failed_leg_errors)
            
            result = MultiLegResult(
                transaction_id=transaction_id,
                success=success,
                legs=legs,
                total_execution_time=execution_time,
                completed_legs=completed_legs,
                failed_legs=failed_legs,
                rolled_back=rolled_back,
                error_message=error_message
            )
            
            logger.info(
                f"Transaction {transaction_id} {'succeeded' if success else 'failed'} "
                f"({completed_legs}/{len(legs)} legs completed in {execution_time:.2f}s)"
            )
            
            return result
            
        except Exception as e:
            logger.error(f"Error in multi-leg transaction {transaction_id}: {e}")
            self.stats['failed_transactions'] += 1
            
            # Попытка rollback
            try:
                await self._rollback_transaction(transaction_id, legs)
            except Exception as rollback_error:
                logger.error(f"Rollback failed: {rollback_error}")
            
            return MultiLegResult(
                transaction_id=transaction_id,
                success=False,
                legs=legs,
                total_execution_time=(datetime.now() - start_time).total_seconds(),
                completed_legs=0,
                failed_legs=len(legs),
                rolled_back=True,
                error_message=str(e)
            )
        
        finally:
            # Очистить активную транзакцию
            if transaction_id in self.active_transactions:
                del self.active_transactions[transaction_id]
    
    async def _execute_leg(self, leg: OrderLeg, transaction_id: str) -> OrderLeg:
        """Выполнить одну ногу сделки"""
        leg.status = LegStatus.EXECUTING
        
        try:
            # Получить клиент биржи
            if leg.exchange not in self.exchange_clients:
                raise ValueError(f"Exchange {leg.exchange} not available")
            
            exchange = self.exchange_clients[leg.exchange]
            
            # Выполнить ордер с retry
            for attempt in range(self.retry_attempts):
                try:
                    if leg.price is None:
                        # Market order
                        order = await exchange.create_market_order(
                            leg.symbol, leg.side, leg.amount
                        )
                    else:
                        # Limit order
                        order = await exchange.create_limit_order(
                            leg.symbol, leg.side, leg.amount, leg.price
                        )
                    
                    leg.order_id = order.get('id')
                    
                    # Ждать исполнения (с таймаутом)
                    filled = await self._wait_for_fill(
                        exchange, leg.order_id, leg.symbol, 
                        timeout=self.max_execution_time / len(self.active_transactions.get(transaction_id, [leg]))
                    )
                    
                    if filled:
                        leg.status = LegStatus.COMPLETED
                        leg.filled_amount = filled.get('filled', 0)
                        leg.average_price = filled.get('average', 0)
                        logger.info(f"Leg {leg.leg_id} completed on {leg.exchange}")
                        return leg
                    
                except Exception as e:
                    if attempt < self.retry_attempts - 1:
                        logger.warning(f"Leg {leg.leg_id} attempt {attempt+1} failed: {e}, retrying...")
                        await asyncio.sleep(0.5 * (attempt + 1))
                    else:
                        raise
            
            # Если дошли сюда - все попытки провалились
            leg.status = LegStatus.FAILED
            leg.error = "Max retry attempts reached"
            
        except Exception as e:
            leg.status = LegStatus.FAILED
            leg.error = str(e)
            logger.error(f"Leg {leg.leg_id} failed: {e}")
        
        return leg
    
    async def _wait_for_fill(self, exchange, order_id: str, symbol: str, timeout: float = 10.0) -> Optional[Dict]:
        """Ждать исполнения ордера"""
        start_time = datetime.now()
        
        while (datetime.now() - start_time).total_seconds() < timeout:
            try:
                order = await exchange.fetch_order(order_id, symbol)
                status = order.get('status')
                
                if status == 'closed':
                    return order
                elif status == 'canceled':
                    return None
                
                # Partial fill check
                filled = order.get('filled', 0)
                amount = order.get('amount', 1)
                if filled / amount >= self.partial_fill_threshold:
                    return order
                
            except Exception as e:
                logger.warning(f"Error checking order {order_id}: {e}")
            
            await asyncio.sleep(0.5)
        
        return None
    
    async def _rollback_transaction(self, transaction_id: str, legs: List[OrderLeg]):
        """Откатить транзакцию - отменить/реверсировать выполненные ноги"""
        logger.warning(f"Rolling back transaction {transaction_id}")
        
        rollback_tasks = []
        for leg in legs:
            if leg.status == LegStatus.COMPLETED:
                rollback_tasks.append(self._rollback_leg(leg))
        
        if rollback_tasks:
            await asyncio.gather(*rollback_tasks, return_exceptions=True)
    
    async def _rollback_leg(self, leg: OrderLeg):
        """Откатить одну ногу - создать противоположный ордер"""
        try:
            if leg.exchange not in self.exchange_clients:
                logger.error(f"Cannot rollback leg {leg.leg_id}: exchange {leg.exchange} not available")
                return
            
            exchange = self.exchange_clients[leg.exchange]
            
            # Противоположная сторона
            opposite_side = 'sell' if leg.side == 'buy' else 'buy'
            
            # Создать market order для быстрого отката
            await exchange.create_market_order(
                leg.symbol, opposite_side, leg.filled_amount
            )
            
            leg.status = LegStatus.ROLLED_BACK
            logger.info(f"Leg {leg.leg_id} rolled back")
            
        except Exception as e:
            logger.error(f"Failed to rollback leg {leg.leg_id}: {e}")
    
    def get_statistics(self) -> Dict:
        """Получить статистику"""
        success_rate = (
            self.stats['successful_transactions'] / self.stats['total_transactions']
            if self.stats['total_transactions'] > 0 else 0
        )
        
        return {
            **self.stats,
            'success_rate': success_rate,
            'active_transactions': len(self.active_transactions)
        }


# Пример использования
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    # Мок exchange clients
    class MockExchange:
        def __init__(self, name):
            self.name = name
        
        async def create_market_order(self, symbol, side, amount):
            await asyncio.sleep(0.1)
            return {'id': f'order_{self.name}_{datetime.now().timestamp()}'}
        
        async def fetch_order(self, order_id, symbol):
            return {'status': 'closed', 'filled': 1.0, 'amount': 1.0, 'average': 50000}
    
    exchanges = {
        'binance': MockExchange('binance'),
        'kucoin': MockExchange('kucoin')
    }
    
    executor = MultiLegExecutor(exchanges)
    
    # Тест
    async def test():
        legs = [
            OrderLeg(leg_id="leg1", exchange="binance", symbol="BTC/USDT", side="buy", amount=1.0),
            OrderLeg(leg_id="leg2", exchange="kucoin", symbol="BTC/USDT", side="sell", amount=1.0)
        ]
        
        result = await executor.execute_multi_leg(legs)
        print(f"Success: {result.success}")
        print(f"Completed: {result.completed_legs}/{len(result.legs)}")
        print(f"Time: {result.total_execution_time:.2f}s")
        print(f"Statistics: {executor.get_statistics()}")
    
    asyncio.run(test())
