"""
Binance WebSocket Client - REAL IMPLEMENTATION
Connects to Binance WebSocket API for real-time market data
"""
import asyncio
import json
import logging
import websockets
from typing import Callable, List, Optional

logger = logging.getLogger(__name__)


class BinanceWS:
    """Real Binance WebSocket client for streaming market data."""
    
    # Binance WebSocket endpoints
    WS_BASE = "wss://stream.binance.com:9443/ws"
    WS_BASE_TESTNET = "wss://testnet.binance.vision/ws"
    
    def __init__(
        self,
        symbols: List[str],
        price_store,
        loop: asyncio.AbstractEventLoop,
        exchange_name: str = "Binance",
        stagger_start: float = 0.0,
        testnet: bool = False
    ):
        """
        Initialize Binance WebSocket client.
        
        Args:
            symbols: List of trading pairs (e.g., ['BTC/USDT', 'ETH/USDT'])
            price_store: PriceStore instance for storing orderbook data
            loop: Asyncio event loop
            exchange_name: Name of the exchange (default: "Binance")
            stagger_start: Delay before starting (seconds)
            testnet: Use testnet endpoint
        """
        self.symbols = symbols
        self.price_store = price_store
        self.loop = loop
        self.exchange_name = exchange_name
        self.stagger_start = stagger_start
        self.testnet = testnet
        
        # Convert symbols to Binance format (BTC/USDT -> btcusdt)
        self.binance_symbols = [s.replace('/', '').lower() for s in symbols]
        self.ws_base = self.WS_BASE_TESTNET if testnet else self.WS_BASE
        
        self.ws = None
        self.running = False
        self._task = None
        
        # Start connection
        self.loop.create_task(self._delayed_start())
        
        logger.info(f"{self.exchange_name}WS initialized for {len(self.symbols)} symbols")
    
    async def _delayed_start(self):
        """Start with optional delay."""
        if self.stagger_start > 0:
            await asyncio.sleep(self.stagger_start)
        await self.connect()
    
    def _build_ws_url(self) -> str:
        """Build WebSocket URL with all symbol streams."""
        # Binance supports multiple streams in one connection
        # Format: /stream?streams=<streamName1>/<streamName2>/<streamName3>
        streams = [f"{symbol}@depth20@100ms" for symbol in self.binance_symbols]
        stream_path = "/".join(streams)
        url = f"{self.ws_base}/stream?streams={stream_path}"
        return url
    
    async def connect(self):
        """Start WebSocket connection."""
        self.running = True
        self._task = asyncio.create_task(self._run())
        logger.info(f"✅ {self.exchange_name}WS connection task started")
    
    async def _run(self):
        """Main WebSocket loop with auto-reconnect."""
        reconnect_delay = 5
        
        while self.running:
            try:
                url = self._build_ws_url()
                logger.info(f"Connecting to {self.exchange_name} WebSocket...")
                
                async with websockets.connect(url, ping_interval=20, ping_timeout=10) as websocket:
                    self.ws = websocket
                    logger.info(f"✅ Connected to {self.exchange_name} WebSocket")
                    
                    async for message in websocket:
                        if not self.running:
                            break
                        
                        try:
                            data = json.loads(message)
                            await self._process_message(data)
                        except json.JSONDecodeError as e:
                            logger.error(f"JSON decode error: {e}")
                        except Exception as e:
                            logger.error(f"Error processing message: {e}")
                            
            except websockets.exceptions.ConnectionClosed:
                logger.warning(f"{self.exchange_name} WebSocket connection closed, reconnecting...")
            except Exception as e:
                logger.error(f"{self.exchange_name} WebSocket error: {e}")
            
            if self.running:
                logger.info(f"Reconnecting in {reconnect_delay} seconds...")
                await asyncio.sleep(reconnect_delay)
    
    async def _process_message(self, data: dict):
        """Process incoming WebSocket message."""
        # Binance multi-stream format: {"stream": "btcusdt@depth20@100ms", "data": {...}}
        if 'stream' not in data or 'data' not in data:
            return
        
        stream_name = data['stream']
        stream_data = data['data']
        
        # Extract symbol from stream name (e.g., "btcusdt@depth20@100ms" -> "btcusdt")
        symbol_lower = stream_name.split('@')[0]
        
        # Convert to standard format: btcusdt -> BTC/USDT
        symbol = self._format_symbol(symbol_lower)
        
        # Parse orderbook data
        if 'bids' in stream_data and 'asks' in stream_data:
            try:
                # Binance format: [["price", "qty"], ...]
                bids = [[float(b[0]), float(b[1])] for b in stream_data['bids'][:20]]
                asks = [[float(a[0]), float(a[1])] for a in stream_data['asks'][:20]]
                
                # Update price store
                await self.price_store.update_levels(
                    exchange=self.exchange_name,
                    symbol=symbol,
                    bids_levels=bids,
                    asks_levels=asks
                )
                
            except (ValueError, IndexError, KeyError) as e:
                logger.error(f"Error parsing orderbook: {e}")
    
    def _format_symbol(self, binance_symbol: str) -> str:
        """Convert Binance symbol format to standard format."""
        # btcusdt -> BTC/USDT
        symbol_upper = binance_symbol.upper()
        
        # Most common quote currencies
        for quote in ['USDT', 'BUSD', 'USDC', 'BTC', 'ETH', 'BNB']:
            if symbol_upper.endswith(quote):
                base = symbol_upper[:-len(quote)]
                return f"{base}/{quote}"
        
        # Fallback
        return symbol_upper
    
    async def close(self):
        """Close WebSocket connection gracefully."""
        logger.info(f"Closing {self.exchange_name}WS connection...")
        self.running = False
        
        if self.ws:
            await self.ws.close()
        
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        
        logger.info(f"✅ {self.exchange_name}WS connection closed")
