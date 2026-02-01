# arbitrage_bot/exchanges/mexc_socket.py

class MexcSocket:
    def __init__(self, symbol: str):
        self.symbol = symbol
        self.price = None

    async def connect(self):
        # Логика подключения к WebSocket MEXC
        pass
    
    async def get_price(self):
        return self.price
