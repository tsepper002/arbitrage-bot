#!/usr/bin/env python3
"""
main.py — пример запуска Bybit / KuCoin / HTX и MEXC WebSocket клиентов
(обновлён MEXC: добавлены Origin/User-Agent, обработка ошибок).
Требования:
    pip install websocket-client requests websockets
"""
# (файл содержит весь предыдущий код клиентов Bybit/KuCoin/HTX как у вас — не повторяю здесь полностью)
# Далее — обновлённый класс MexcWS (замените ваш текущий MexcWS на этот)

import json
import logging
import asyncio
from typing import Optional
import websockets
from websockets.exceptions import ConnectionClosedError, ConnectionClosedOK, InvalidStatus, InvalidURI

logger = logging.getLogger("arbitrage_ws")
# logging.basicConfig(...) уже был в файле выше

class MexcWS:
    def __init__(
        self,
        symbol: str,
        api_key: Optional[str] = None,
        secret_key: Optional[str] = None,
        ws_url: str = "wss://contract.mexc.com/ws",
        ping_interval: float = 20.0,
    ):
        # MEXC часто использует формат BTC_USDT — заменяем дефис на подчеркивание
        self.symbol = symbol
        self.symbol_norm = symbol.replace("-", "_")
        self.api_key = api_key
        self.secret_key = secret_key
        self.ws_url = ws_url
        self.price: Optional[float] = None
        self._ws = None
        self._ping_interval = ping_interval
        self._stop = False

    async def start(self):
        backoff = 1.0
        # Добавим заголовки, которые обычно ожидает сервер
        headers = {
            "Origin": "https://www.mexc.com",
            "User-Agent": "Mozilla/5.0 (compatible; ArbitrageBot/1.0)"
        }
        while not self._stop:
            try:
                logger.info(f"MEXC: connecting to {self.ws_url} for {self.symbol_norm} ...")
                # Передаём extra_headers, увеличиваем open_timeout
                async with websockets.connect(
                    self.ws_url,
                    ping_interval=None,
                    extra_headers=headers,
                    open_timeout=10,
                ) as ws:
                    self._ws = ws
                    logger.info("MEXC: Websocket connected")
                    await self._on_connect(ws)
                    backoff = 1.0
            except InvalidStatus as e:
                # Сервер вернул статус отличный от 101 — логируем детали
                try:
                    resp = e.response
                    status = getattr(resp, "status", "unknown")
                    headers = getattr(resp, "headers", {})
                    logger.error(f"MEXC: InvalidStatus {status}, headers: {headers}. Reconnect in {backoff:.1f}s...")
                except Exception:
                    logger.exception(f"MEXC: InvalidStatus exception: {e}")
            except InvalidURI as e:
                logger.error(f"MEXC: InvalidURI (likely redirect to non-ws URL): {e}. Reconnect in {backoff:.1f}s...")
            except (ConnectionClosedError, ConnectionClosedOK) as e:
                logger.warning(f"MEXC: WebSocket closed: {e}. Reconnect in {backoff:.1f}s...")
            except Exception as e:
                logger.exception(f"MEXC: connection/error: {e}. Reconnect in {backoff:.1f}s...")
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, 60.0)

    async def _on_connect(self, ws):
        await self._send_subscribe(ws)
        receiver_task = asyncio.create_task(self._receiver(ws))
        keepalive_task = asyncio.create_task(self._keepalive(ws))
        done, pending = await asyncio.wait([receiver_task, keepalive_task], return_when=asyncio.FIRST_EXCEPTION)
        for t in pending:
            t.cancel()
            try:
                await t
            except asyncio.CancelledError:
                pass

    async def _send(self, ws, message: dict):
        try:
            text = json.dumps(message)
            await ws.send(text)
            logger.debug(f"MEXC Sent: {text}")
        except Exception as e:
            logger.error(f"MEXC: failed to send message: {e}")

    async def _send_subscribe(self, ws):
        subscribe_message = {
            "method": "sub.ticker",
            "param": {"symbol": self.symbol_norm},
        }
        await self._send(ws, subscribe_message)
        logger.info(f"MEXC: subscribed to {self.symbol_norm}")

    async def _keepalive(self, ws):
        try:
            while True:
                await asyncio.sleep(self._ping_interval)
                try:
                    logger.debug("MEXC: sending low-level ping")
                    pong_waiter = await ws.ping()
                    await asyncio.wait_for(pong_waiter, timeout=10)
                    logger.debug("MEXC: got pong")
                except asyncio.TimeoutError:
                    logger.warning("MEXC: pong timeout — closing ws to reconnect")
                    await ws.close()
                    return
                except Exception as e:
                    logger.warning(f"MEXC: ping error: {e}")
                    await ws.close()
                    return
        except asyncio.CancelledError:
            logger.debug("MEXC keepalive cancelled")
            raise

    async def _receiver(self, ws):
        try:
            async for message in ws:
                logger.debug(f"MEXC: raw message: {message}")
                await self.handle_message(message, ws)
        except asyncio.CancelledError:
            logger.debug("MEXC receiver cancelled")
            raise
        except Exception as e:
            logger.exception(f"MEXC receiver error: {e}")
            return

    async def handle_message(self, message, ws=None):
        try:
            if isinstance(message, (bytes, bytearray)):
                text = message.decode()
            else:
                text = message
            data = json.loads(text)
        except Exception:
            logger.debug("MEXC: non-json or decode error")
            return

        if isinstance(data, dict) and data.get("method") == "ping":
            try:
                resp = {"method": "pong"}
                if ws is not None:
                    await self._send(ws, resp)
                    logger.info("MEXC: replied pong")
            except Exception as e:
                logger.warning(f"MEXC: failed to send pong: {e}")
            return

        if isinstance(data, dict) and "data" in data:
            payload = data["data"]
            if isinstance(payload, dict):
                price = payload.get("lastPrice") or payload.get("price") or payload.get("last_price")
            else:
                price = None
            if price is not None:
                try:
                    self.price = float(price)
                except Exception:
                    self.price = price
                logger.info(f"MEXC {self.symbol_norm} price: {self.price}")
            else:
                logger.debug(f"MEXC got data without price: {payload}")
        else:
            logger.debug(f"MEXC other message: {data}")

    async def get_price(self):
        return self.price

    async def stop(self):
        self._stop = True
        if self._ws is not None:
            try:
                await self._ws.close()
            except Exception:
                pass

# (далее — остальной main: создание clients и запуск tasks остаются как у вас; замените только класс MexcWS)