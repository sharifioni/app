"""
WebSocket Client - Real-time Market Data
Receives live price updates, trades, and orderbook changes
"""

import asyncio
import websockets
import json
import logging
import time
from typing import Dict, List, Optional, Callable, Any
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import threading
from queue import Queue

logger = logging.getLogger(__name__)


class MessageType(Enum):
    PRICE_UPDATE = "price_change"
    TRADE = "trade"
    ORDERBOOK = "book_change"
    SUBSCRIPTION = "subscribed"
    ERROR = "error"
    HEARTBEAT = "heartbeat"


@dataclass
class PriceUpdate:
    """Price update message"""
    token_id: str
    price: float
    timestamp: float
    change: float = 0.0


@dataclass
class TradeMessage:
    """Trade notification message"""
    token_id: str
    price: float
    size: float
    side: str
    timestamp: float


@dataclass
class Subscription:
    """Market subscription"""
    token_id: str
    subscribed_at: float
    active: bool = True


class WebSocketClient:
    """
    WebSocket client for real-time Polymarket data

    Features:
    - Subscribe to multiple markets
    - Auto-reconnect on disconnect
    - Message callbacks
    - Fallback to HTTP polling
    """

    def __init__(self, url: str = "wss://ws-subscriptions-clob.polymarket.com/ws/market",
                 on_price_update: Optional[Callable[[PriceUpdate], None]] = None,
                 on_trade: Optional[Callable[[TradeMessage], None]] = None,
                 on_error: Optional[Callable[[str], None]] = None,
                 on_reconnect: Optional[Callable[[int], None]] = None,
                 reconnect_delay: float = 2.0,
                 max_reconnect_attempts: int = 50):
        """
        Args:
            url: WebSocket URL
            on_price_update: Callback for price updates
            on_trade: Callback for trades
            on_error: Callback for errors
            on_reconnect: Callback when reconnecting (receives attempt count)
            reconnect_delay: Initial delay between reconnect attempts (uses exponential backoff)
            max_reconnect_attempts: Max reconnection attempts before giving up
        """
        self.url = url
        self.on_price_update = on_price_update
        self.on_trade = on_trade
        self.on_error = on_error
        self.on_reconnect = on_reconnect
        self.reconnect_delay = reconnect_delay
        self.max_reconnect_attempts = max_reconnect_attempts

        self._websocket = None
        self._running = False
        self._subscriptions: Dict[str, Subscription] = {}
        self._message_queue: Queue = Queue()
        self._reconnect_count = 0
        self._total_reconnects = 0  # Lifetime reconnect counter
        self._last_message_time = 0
        self._last_connect_time = 0
        self._thread = None
        self._loop = None

        # Price cache
        self._prices: Dict[str, float] = {}
        self._price_history: Dict[str, List[tuple]] = {}  # token_id -> [(timestamp, price), ...]

    @property
    def is_connected(self) -> bool:
        return self._websocket is not None and self._running

    @property
    def subscribed_tokens(self) -> List[str]:
        return list(self._subscriptions.keys())

    def get_price(self, token_id: str) -> Optional[float]:
        """Get last known price for token"""
        return self._prices.get(token_id)

    def get_price_history(self, token_id: str, seconds: int = 60) -> List[tuple]:
        """Get price history for token within last N seconds"""
        if token_id not in self._price_history:
            return []
        cutoff = time.time() - seconds
        return [(t, p) for t, p in self._price_history.get(token_id, []) if t > cutoff]

    async def _connect(self):
        """Establish WebSocket connection with timeout and retry logic"""
        try:
            # More generous timeouts to handle slow connections
            self._websocket = await asyncio.wait_for(
                websockets.connect(
                    self.url,
                    ping_interval=20,  # Send ping every 20 seconds
                    ping_timeout=30,   # Wait 30 seconds for pong
                    close_timeout=10,  # Wait 10 seconds for close handshake
                    open_timeout=30,   # Wait 30 seconds for connection
                ),
                timeout=45  # Overall connection timeout
            )
            logger.info(f"WebSocket connected to {self.url}")
            self._reconnect_count = 0  # Reset consecutive failures
            self._last_connect_time = time.time()

            # Resubscribe to all markets at once (more efficient)
            if self._subscriptions:
                asset_ids = list(self._subscriptions.keys())
                # Batch subscriptions in chunks to avoid overwhelming server
                chunk_size = 100
                for i in range(0, len(asset_ids), chunk_size):
                    chunk = asset_ids[i:i + chunk_size]
                    message = {
                        "assets_ids": chunk,
                        "type": "market"
                    }
                    await self._websocket.send(json.dumps(message))
                    if len(asset_ids) > chunk_size:
                        await asyncio.sleep(0.1)  # Small delay between batches
                logger.info(f"Subscribed to {len(asset_ids)} assets")

            return True
        except asyncio.TimeoutError:
            logger.warning("WebSocket connection timed out during handshake")
            if self.on_error:
                self.on_error("Connection timeout - server may be slow or unreachable")
            return False
        except Exception as e:
            logger.error(f"WebSocket connection failed: {e}")
            if self.on_error:
                self.on_error(f"Connection failed: {e}")
            return False

    async def _subscribe_internal(self, token_id: str):
        """Send subscription message"""
        if self._websocket:
            # Use correct Polymarket format
            message = {
                "assets_ids": [token_id],
                "type": "market"
            }
            await self._websocket.send(json.dumps(message))
            logger.debug(f"Subscribed to {token_id}")

    async def _unsubscribe_internal(self, token_id: str):
        """Send unsubscription message"""
        if self._websocket:
            message = {
                "assets_ids": [token_id],
                "operation": "unsubscribe",
                "custom_feature_enabled": False
            }
            await self._websocket.send(json.dumps(message))
            logger.debug(f"Unsubscribed from {token_id}")

    def subscribe(self, token_id: str):
        """Subscribe to market updates for a token"""
        self._subscriptions[token_id] = Subscription(
            token_id=token_id,
            subscribed_at=time.time()
        )
        if self._loop and self._websocket:
            # Use dynamic subscription for already-connected client
            asyncio.run_coroutine_threadsafe(
                self._dynamic_subscribe([token_id]),
                self._loop
            )
        logger.info(f"Added subscription for {token_id}")

    async def _dynamic_subscribe(self, token_ids: List[str]):
        """Dynamically subscribe to additional assets"""
        if self._websocket:
            message = {
                "assets_ids": token_ids,
                "operation": "subscribe",
                "custom_feature_enabled": False
            }
            await self._websocket.send(json.dumps(message))
            logger.debug(f"Dynamically subscribed to {len(token_ids)} assets")

    def unsubscribe(self, token_id: str):
        """Unsubscribe from market updates"""
        if token_id in self._subscriptions:
            del self._subscriptions[token_id]
            if self._loop and self._websocket:
                asyncio.run_coroutine_threadsafe(
                    self._dynamic_unsubscribe([token_id]),
                    self._loop
                )
            logger.info(f"Removed subscription for {token_id}")

    async def _dynamic_unsubscribe(self, token_ids: List[str]):
        """Dynamically unsubscribe from assets"""
        if self._websocket:
            message = {
                "assets_ids": token_ids,
                "operation": "unsubscribe",
                "custom_feature_enabled": False
            }
            await self._websocket.send(json.dumps(message))
            logger.debug(f"Dynamically unsubscribed from {len(token_ids)} assets")

    def subscribe_many(self, token_ids: List[str]):
        """Subscribe to multiple tokens"""
        for token_id in token_ids:
            self._subscriptions[token_id] = Subscription(
                token_id=token_id,
                subscribed_at=time.time()
            )

        if self._loop and self._websocket:
            # Use dynamic subscription for batch
            asyncio.run_coroutine_threadsafe(
                self._dynamic_subscribe(token_ids),
                self._loop
            )
        logger.info(f"Added subscriptions for {len(token_ids)} tokens")

    def unsubscribe_all(self):
        """Unsubscribe from all tokens"""
        for token_id in list(self._subscriptions.keys()):
            self.unsubscribe(token_id)

    def _handle_message(self, data: Dict):
        """Process incoming WebSocket message"""
        self._last_message_time = time.time()

        event_type = data.get('event_type', '')

        # Handle price_change with nested price_changes array (actual Polymarket format)
        if event_type == 'price_change' and 'price_changes' in data:
            for price_change in data['price_changes']:
                token_id = price_change.get('asset_id', '')
                price_str = price_change.get('price', '0')

                try:
                    price = float(price_str)
                except (ValueError, TypeError):
                    continue

                if not token_id or price == 0:
                    continue

                # Update cache
                old_price = self._prices.get(token_id, price)
                self._prices[token_id] = price

                # Store history
                if token_id not in self._price_history:
                    self._price_history[token_id] = []
                self._price_history[token_id].append((time.time(), price))

                # Trim history to last 5 minutes
                cutoff = time.time() - 300
                self._price_history[token_id] = [
                    (t, p) for t, p in self._price_history[token_id] if t > cutoff
                ]

                # Callback
                if self.on_price_update:
                    update = PriceUpdate(
                        token_id=token_id,
                        price=price,
                        timestamp=time.time(),
                        change=price - old_price
                    )
                    self.on_price_update(update)
            return

        # Handle last_trade_price (direct format)
        if event_type == 'last_trade_price':
            token_id = data.get('asset_id', '')
            price = float(data.get('price', 0))

            if not token_id or price == 0:
                return

            # Update cache
            old_price = self._prices.get(token_id, price)
            self._prices[token_id] = price

            # Store history
            if token_id not in self._price_history:
                self._price_history[token_id] = []
            self._price_history[token_id].append((time.time(), price))

            # Trim history to last 5 minutes
            cutoff = time.time() - 300
            self._price_history[token_id] = [
                (t, p) for t, p in self._price_history[token_id] if t > cutoff
            ]

            # Callback
            if self.on_price_update:
                update = PriceUpdate(
                    token_id=token_id,
                    price=price,
                    timestamp=time.time(),
                    change=price - old_price
                )
                self.on_price_update(update)

        # Handle order book updates
        elif event_type == 'book':
            token_id = data.get('asset_id', '')
            # Calculate mid-price from best bid/ask
            bids = data.get('bids', [])
            asks = data.get('asks', [])

            if bids and asks:
                best_bid = float(bids[0].get('price', 0))
                best_ask = float(asks[0].get('price', 0))
                mid_price = (best_bid + best_ask) / 2

                # Treat as price update
                old_price = self._prices.get(token_id, mid_price)
                self._prices[token_id] = mid_price

                if token_id not in self._price_history:
                    self._price_history[token_id] = []
                self._price_history[token_id].append((time.time(), mid_price))

                cutoff = time.time() - 300
                self._price_history[token_id] = [
                    (t, p) for t, p in self._price_history[token_id] if t > cutoff
                ]

                if self.on_price_update:
                    update = PriceUpdate(
                        token_id=token_id,
                        price=mid_price,
                        timestamp=time.time(),
                        change=mid_price - old_price
                    )
                    self.on_price_update(update)

        # Handle trade messages (if callback provided)
        elif event_type == 'last_trade_price' and self.on_trade:
            token_id = data.get('asset_id', '')
            trade = TradeMessage(
                token_id=token_id,
                price=float(data.get('price', 0)),
                size=float(data.get('size', 0)),
                side=data.get('side', 'unknown'),
                timestamp=time.time()
            )
            self.on_trade(trade)

        # Handle tick size changes (just log)
        elif event_type == 'tick_size_change':
            token_id = data.get('asset_id', '')
            logger.debug(f"Tick size changed for {token_id}: {data.get('old_tick_size')} -> {data.get('new_tick_size')}")

        # Handle errors
        elif event_type == 'error':
            error_msg = data.get('message', 'Unknown error')
            logger.error(f"WebSocket error: {error_msg}")
            if self.on_error:
                self.on_error(error_msg)

    async def _receive_loop(self):
        """Main message receiving loop with exponential backoff"""
        while self._running:
            try:
                if not self._websocket:
                    # Calculate exponential backoff delay
                    backoff_delay = min(
                        self.reconnect_delay * (2 ** self._reconnect_count),
                        60  # Max 60 seconds between attempts
                    )

                    if self._reconnect_count > 0:
                        logger.info(f"Reconnecting in {backoff_delay:.1f}s (attempt {self._reconnect_count + 1}/{self.max_reconnect_attempts})")
                        if self.on_reconnect:
                            self.on_reconnect(self._reconnect_count + 1)
                        await asyncio.sleep(backoff_delay)

                    if not await self._connect():
                        self._reconnect_count += 1
                        self._total_reconnects += 1
                        if self._reconnect_count >= self.max_reconnect_attempts:
                            logger.error("Max reconnect attempts reached, resetting counter and continuing...")
                            # Don't stop, just reset and keep trying
                            self._reconnect_count = 0
                            await asyncio.sleep(30)  # Wait 30 seconds before fresh attempt cycle
                        continue

                message = await asyncio.wait_for(
                    self._websocket.recv(),
                    timeout=90  # Increased timeout to 90 seconds
                )

                try:
                    data = json.loads(message)

                    # Handle different message types
                    if isinstance(data, dict):
                        self._handle_message(data)
                    elif isinstance(data, list):
                        # Subscription confirmation returns a list of asset IDs
                        logger.debug(f"Received subscription confirmation for {len(data)} assets")
                    else:
                        logger.warning(f"Unknown message type: {type(data)}")

                except json.JSONDecodeError:
                    logger.warning(f"Invalid JSON received: {message[:100]}")

            except asyncio.TimeoutError:
                # No message for 90 seconds - connection may be stale
                logger.debug("WebSocket idle timeout, checking if connection is alive...")
                # Try to send a ping to check connection
                try:
                    if self._websocket:
                        pong_waiter = await self._websocket.ping()
                        await asyncio.wait_for(pong_waiter, timeout=10)
                        logger.debug("Connection still alive (ping successful)")
                except Exception:
                    logger.warning("Connection appears dead, will reconnect...")
                    if self._websocket:
                        try:
                            await self._websocket.close()
                        except Exception:
                            pass
                    self._websocket = None

            except websockets.ConnectionClosed as e:
                logger.warning(f"WebSocket connection closed: {e}")
                self._websocket = None
                # Small delay before reconnect attempt
                await asyncio.sleep(1)

            except Exception as e:
                logger.error(f"WebSocket receive error: {e}")
                self._websocket = None
                await asyncio.sleep(2)

    def _run_async_loop(self):
        """Run asyncio event loop in thread"""
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        try:
            self._loop.run_until_complete(self._receive_loop())
        finally:
            self._loop.close()

    def start(self):
        """Start WebSocket client in background thread"""
        if self._running:
            return

        self._running = True
        self._thread = threading.Thread(target=self._run_async_loop, daemon=True)
        self._thread.start()
        logger.info("WebSocket client started")

    def stop(self):
        """Stop WebSocket client"""
        self._running = False
        if self._websocket and self._loop:
            asyncio.run_coroutine_threadsafe(
                self._websocket.close(),
                self._loop
            )
        if self._thread:
            self._thread.join(timeout=5)
        logger.info("WebSocket client stopped")

    def get_connection_status(self) -> Dict:
        """Get current connection status"""
        now = time.time()
        return {
            'connected': self.is_connected,
            'subscriptions': len(self._subscriptions),
            'reconnect_count': self._reconnect_count,
            'total_reconnects': self._total_reconnects,
            'last_message': self._last_message_time,
            'last_message_ago': now - self._last_message_time if self._last_message_time > 0 else -1,
            'last_connect': self._last_connect_time,
            'uptime': now - self._last_connect_time if self._last_connect_time > 0 else 0,
            'cached_prices': len(self._prices),
        }


class PollingFallback:
    """
    HTTP polling fallback when WebSocket is unavailable

    Polls prices at regular intervals as backup
    """

    def __init__(self, gamma_api, interval: float = 1.0,
                 on_price_update: Optional[Callable[[PriceUpdate], None]] = None):
        """
        Args:
            gamma_api: GammaAPI instance for fetching prices
            interval: Polling interval in seconds
            on_price_update: Callback for price updates
        """
        self.gamma_api = gamma_api
        self.interval = interval
        self.on_price_update = on_price_update

        self._running = False
        self._thread = None
        self._token_ids: List[str] = []
        self._prices: Dict[str, float] = {}

    def subscribe(self, token_id: str):
        """Add token to polling list"""
        if token_id not in self._token_ids:
            self._token_ids.append(token_id)

    def unsubscribe(self, token_id: str):
        """Remove token from polling list"""
        if token_id in self._token_ids:
            self._token_ids.remove(token_id)

    def _poll_loop(self):
        """Main polling loop"""
        while self._running:
            for token_id in self._token_ids:
                try:
                    # Fetch current price from API
                    # This would need to be implemented based on available endpoints
                    # For now, we skip actual implementation
                    pass
                except Exception as e:
                    logger.error(f"Polling error for {token_id}: {e}")

            time.sleep(self.interval)

    def start(self):
        """Start polling"""
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._poll_loop, daemon=True)
        self._thread.start()
        logger.info("Polling fallback started")

    def stop(self):
        """Stop polling"""
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)
        logger.info("Polling fallback stopped")
