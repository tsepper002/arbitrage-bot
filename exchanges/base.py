from abc import ABC, abstractmethod

class BaseExchange(ABC):
    @abstractmethod
    async def get_price(self, symbol: str) -> float:
        """Метод для получения цены"""
        pass

    @abstractmethod
    async def place_order(self, symbol: str, amount: float, price: float) -> dict:
        """Метод для размещения ордера"""
        pass

    @abstractmethod
    async def connect(self):
        """Метод для подключения (для WebSocket)"""
        pass
