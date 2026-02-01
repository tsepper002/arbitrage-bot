import asyncio
import websockets
import json

# Пример класса для подключения к каждой бирже
class BybitWS:
    def __init__(self, symbol: str):
        self.symbol = symbol
        self.ws_url = "wss://stream.bybit.com/spot/ws"

    async def connect(self):
        async with websockets.connect(self.ws_url) as ws:
            await ws.send(json.dumps({"op": "subscribe", "args": [f"trade.{self.symbol}"]}))
            while True:
                msg = await ws.recv()
                print(f"Bybit Price: {msg}")

class KucoinWS:
    def __init__(self, symbol: str):
        self.symbol = symbol
        self.ws_url = "wss://push1-v2.kucoin.com/endpoint"

    async def connect(self):
        async with websockets.connect(self.ws_url) as ws:
            await ws.send(json.dumps({"type": "subscribe", "symbol": self.symbol}))
            while True:
                msg = await ws.recv()
                print(f"KuCoin Price: {msg}")

class MexcWS:
    def __init__(self, symbol: str):
        self.symbol = symbol
        self.ws_url = "wss://contract.mexc.com/edge"

    async def connect(self):
        async with websockets.connect(self.ws_url) as ws:
            await ws.send(json.dumps({"op": "subscribe", "args": [f"trade.{self.symbol}"]}))
            while True:
                msg = await ws.recv()
                print(f"MEXC Price: {msg}")

class HtxWS:
    def __init__(self, symbol: str):
        self.symbol = symbol
        self.ws_url = "wss://api.huobi.pro/ws"

    async def connect(self):
        async with websockets.connect(self.ws_url) as ws:
            await ws.send(json.dumps({"sub": f"market.{self.symbol}.trade.detail"}))
            while True:
                msg = await ws.recv()
                print(f"HTX Price: {msg}")

class XtWS:
    def __init__(self, symbol: str):
        self.symbol = symbol
        self.ws_url = "wss://ws.xt.com"

    async def connect(self):
        async with websockets.connect(self.ws_url) as ws:
            await ws.send(json.dumps({"op": "subscribe", "args": [f"trade.{self.symbol}"]}))
            while True:
                msg = await ws.recv()
                print(f"XT Price: {msg}")


# Класс сканера, который будет подключаться ко всем биржам
class Scanner:
    def __init__(self, symbol: str):
        self.symbol = symbol
        self.bybit = BybitWS(symbol)
        self.kucoin = KucoinWS(symbol)
        self.mexc = MexcWS(symbol)
        self.htx = HtxWS(symbol)
        self.xt = XtWS(symbol)

    async def start_scanner(self):
        tasks = [
            self.bybit.connect(),
            self.kucoin.connect(),
            self.mexc.connect(),
            self.htx.connect(),
            self.xt.connect()
        ]
        await asyncio.gather(*tasks)

# Запуск сканера
if __name__ == "__main__":
    scanner = Scanner("BTC-USDT")
    asyncio.run(scanner.start_scanner())
