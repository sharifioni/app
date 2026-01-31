"""
HTTP Polling Alternative to WebSocket
Polls Polymarket API for price updates when WebSocket is unavailable
"""

import time
import threading
import logging
import json
from typing import Dict, List, Optional, Callable
from collections import defaultdict

from .gamma_api import GammaAPI
from .websocket_client import PriceUpdate

logger = logging.getLogger(__name__)


class HTTPPoller:
    """
    HTTP polling for real-time price updates

    Polls Polymarket API at regular intervals for price data.
    Used as fallback when WebSocket is unavailable or incompatible.
    """

    def __init__(
        self,
        gamma_api: GammaAPI,
        on_price_update: Optional[Callable[[PriceUpdate], None]] = None,
        on_error: Optional[Callable[[str], None]] = None,
        interval: float = 2.0
    ):
        """
        Args:
            gamma_api: GammaAPI instance for fetching data
            on_price_update: Callback for price updates
            on_error: Callback for errors
            interval: Polling interval in seconds (default 2s)
        """
        self.gamma_api = gamma_api
        self.on_price_update = on_price_update
        self.on_error = on_error
        self.interval = interval

        self._running = False
        self._thread = None
        self._token_ids: List[str] = []
        self._last_prices: Dict[str, float] = {}
        self._market_cache: Dict[str, Dict] = {}  # token_id -> market data

    @property
    def is_connected(self) -> bool:
        return self._running

    @property
    def subscribed_tokens(self) -> List[str]:
        return list(self._token_ids)

    def subscribe(self, token_id: str):
        """Add token to polling list"""
        if token_id not in self._token_ids:
            self._token_ids.append(token_id)
            logger.info(f"[HTTP Poller] Subscribed to {token_id}")
            print(f"[HTTP Poller] Subscribed to {token_id}")

    def unsubscribe(self, token_id: str):
        """Remove token from polling list"""
        if token_id in self._token_ids:
            self._token_ids.remove(token_id)
            logger.info(f"[HTTP Poller] Unsubscribed from {token_id}")

    def subscribe_many(self, token_ids: List[str]):
        """Subscribe to multiple tokens"""
        for token_id in token_ids:
            self.subscribe(token_id)

    def unsubscribe_all(self):
        """Unsubscribe from all tokens"""
        self._token_ids.clear()
        logger.info("[HTTP Poller] Unsubscribed from all tokens")

    def _fetch_market_price(self, token_id: str) -> Optional[float]:
        """Fetch current price for a token"""
        try:
            # Get market from cache
            market = self._market_cache.get(token_id)
            if not market:
                return None

            # Find which outcome index this token_id represents
            clob_token_ids_raw = market.get('clobTokenIds', '[]')
            try:
                clob_token_ids = json.loads(clob_token_ids_raw) if isinstance(clob_token_ids_raw, str) else clob_token_ids_raw
            except json.JSONDecodeError:
                clob_token_ids = []
            if token_id not in clob_token_ids:
                return None

            token_idx = clob_token_ids.index(token_id)

            # Get outcome prices
            outcome_prices = market.get('outcomePrices')
            if outcome_prices and token_idx < len(outcome_prices):
                price_str = outcome_prices[token_idx]
                return float(price_str)

            return None

        except Exception as e:
            logger.debug(f"[HTTP Poller] Error fetching price for {token_id}: {e}")
            return None

    def _update_market_cache(self, events: List[Dict]):
        """Update market cache from events"""
        for event in events:
            markets = event.get('markets', [])
            for market in markets:
                token_ids_raw = market.get('clobTokenIds', '[]')
                try:
                    token_ids = json.loads(token_ids_raw) if isinstance(token_ids_raw, str) else token_ids_raw
                except json.JSONDecodeError:
                    token_ids = []
                for token_id in token_ids:
                    if token_id:
                        self._market_cache[str(token_id)] = market

    def _poll_loop(self):
        """Main polling loop"""
        logger.info(f"[HTTP Poller] Started with {self.interval}s interval")
        print(f"[HTTP Poller] Started - waiting for subscriptions...")

        while self._running:
            try:
                if not self._token_ids:
                    time.sleep(self.interval)
                    continue

                # Log polling activity
                print(f"[HTTP Poller] Polling {len(self._token_ids)} tokens...")

                # Fetch live events to update cache
                live_events = self.gamma_api.get_live_events()
                self._update_market_cache(live_events)

                print(f"[HTTP Poller] Market cache updated: {len(self._market_cache)} tokens")

                # Check each subscribed token
                prices_updated = 0
                for token_id in self._token_ids:
                    try:
                        price = self._fetch_market_price(token_id)

                        if price is not None:
                            # Check if price changed
                            old_price = self._last_prices.get(token_id)

                            if old_price is None or abs(price - old_price) > 0.0001:
                                self._last_prices[token_id] = price
                                prices_updated += 1

                                # Call update callback
                                if self.on_price_update:
                                    update = PriceUpdate(
                                        token_id=token_id,
                                        price=price,
                                        timestamp=time.time(),
                                        change=price - old_price if old_price else 0.0
                                    )
                                    self.on_price_update(update)

                    except Exception as e:
                        logger.error(f"[HTTP Poller] Error polling {token_id}: {e}")

                if prices_updated > 0:
                    print(f"[HTTP Poller] Updated {prices_updated} prices")
                else:
                    print(f"[HTTP Poller] No price updates this cycle")

            except Exception as e:
                error_msg = f"Polling error: {e}"
                logger.error(f"[HTTP Poller] {error_msg}")
                if self.on_error:
                    self.on_error(error_msg)

            time.sleep(self.interval)

        logger.info("[HTTP Poller] Stopped")

    def start(self):
        """Start polling"""
        if self._running:
            return

        self._running = True
        self._thread = threading.Thread(target=self._poll_loop, daemon=True)
        self._thread.start()
        logger.info("[HTTP Poller] Started")

    def stop(self):
        """Stop polling"""
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)
        logger.info("[HTTP Poller] Stopped")

    def get_connection_status(self) -> Dict:
        """Get current connection status"""
        return {
            'connected': self.is_connected,
            'subscriptions': len(self._token_ids),
            'cached_markets': len(self._market_cache),
            'tracked_prices': len(self._last_prices),
        }
