"""
Optimized Real-time Data Collector
Efficiently fetches and stores live market data every second
"""

import asyncio
import time
import json
import logging
from datetime import datetime
from typing import Dict, List, Optional
from collections import deque
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from momentum_trader.api import GammaAPI, WebSocketClient, PriceUpdate, CLOBAPI
from momentum_trader.filters import EventFilter
from momentum_trader.config import config

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class OptimizedDataCollector:
    """
    High-performance real-time data collector

    Features:
    - WebSocket for sub-second updates
    - Efficient in-memory caching
    - Automatic reconnection
    - Momentum detection
    """

    def __init__(self):
        self.gamma_api = GammaAPI(proxy=config.api.proxy)
        self.clob_api = CLOBAPI(simulation_mode=True)

        # Data storage
        self.price_data: Dict[str, deque] = {}  # token_id -> [(timestamp, price), ...]
        self.volume_data: Dict[str, deque] = {}
        self.events: Dict[str, Dict] = {}  # event_id -> event data
        self.token_to_event: Dict[str, str] = {}  # token_id -> event_id

        # Performance metrics
        self.update_count = 0
        self.start_time = time.time()
        self.last_scan_time = 0

        # WebSocket client
        self.ws_client = None
        self.qualified_event_ids: List[str] = []

    def on_price_update(self, update: PriceUpdate):
        """Handle price update from WebSocket"""
        token_id = update.token_id

        # Store price
        if token_id not in self.price_data:
            self.price_data[token_id] = deque(maxlen=300)  # Last 5 minutes
        self.price_data[token_id].append((update.timestamp, update.price))

        self.update_count += 1

        # Detect momentum
        signal = self.detect_momentum(token_id)
        if signal:
            self.log_signal(signal)

    def detect_momentum(self, token_id: str) -> Optional[Dict]:
        """
        Detect momentum in price movement

        Returns signal if:
        - Price up 2%+ in last 20 seconds
        - Compared to 40-second baseline
        """
        if token_id not in self.price_data:
            return None

        prices = list(self.price_data[token_id])
        if len(prices) < 60:  # Need 60 seconds of data
            return None

        # Baseline: 40 seconds ago to 20 seconds ago
        baseline = prices[-60:-20]
        # Recent: last 20 seconds
        recent = prices[-20:]

        if not baseline or not recent:
            return None

        baseline_avg = sum(p for _, p in baseline) / len(baseline)
        current_price = recent[-1][1]

        price_change = (current_price - baseline_avg) / baseline_avg

        if price_change >= 0.02:  # 2%+ rise
            # Get event info
            event_id = self.token_to_event.get(token_id)
            event_data = self.events.get(event_id, {})

            return {
                'token_id': token_id,
                'event_id': event_id,
                'event_title': event_data.get('title', 'Unknown'),
                'baseline_price': baseline_avg,
                'current_price': current_price,
                'price_change_pct': price_change * 100,
                'detected_at': time.time(),
                'signal_strength': self.classify_signal(price_change)
            }

        return None

    def classify_signal(self, price_change: float) -> str:
        """Classify signal strength"""
        if price_change >= 0.05:  # 5%+
            return 'STRONG'
        elif price_change >= 0.03:  # 3%+
            return 'MEDIUM'
        else:  # 2%+
            return 'WEAK'

    def log_signal(self, signal: Dict):
        """Log momentum signal"""
        logger.info(f"🚨 MOMENTUM SIGNAL DETECTED")
        logger.info(f"   Event: {signal['event_title']}")
        logger.info(f"   Price: {signal['baseline_price']:.3f} → {signal['current_price']:.3f}")
        logger.info(f"   Change: {signal['price_change_pct']:+.2f}%")
        logger.info(f"   Strength: {signal['signal_strength']}")

    async def scan_and_subscribe(self):
        """Scan for qualified events and subscribe to their markets"""
        logger.info("Scanning for qualified events...")

        # Fetch live events
        live_events = self.gamma_api.get_live_events()
        logger.info(f"Fetched {len(live_events)} live events")

        # Filter events
        event_filter = EventFilter(self.gamma_api, config)
        qualified = event_filter.filter_and_score_events(live_events)

        logger.info(f"Qualified events: {len(qualified)}")

        if not qualified:
            logger.warning("No qualified events found")
            return

        # Store events
        for score in qualified:
            event = next((e for e in live_events if e.get('id') == score.event_id), None)
            if event:
                self.events[score.event_id] = event

                # Extract token IDs from markets
                for market in event.get('markets', []):
                    token_ids_raw = market.get('clobTokenIds', '[]')
                    # Parse JSON string to list if needed
                    try:
                        token_ids = json.loads(token_ids_raw) if isinstance(token_ids_raw, str) else token_ids_raw
                    except json.JSONDecodeError:
                        token_ids = []
                    for token_id in token_ids:
                        if token_id:
                            self.token_to_event[str(token_id)] = score.event_id

                            # Subscribe via WebSocket
                            if self.ws_client:
                                self.ws_client.subscribe(str(token_id))

        self.qualified_event_ids = [s.event_id for s in qualified]
        self.last_scan_time = time.time()

        logger.info(f"Subscribed to {len(self.token_to_event)} markets")

    async def start_collection(self):
        """Start collecting real-time data"""
        logger.info("Starting optimized data collector...")

        # Initialize WebSocket
        self.ws_client = WebSocketClient(
            on_price_update=self.on_price_update,
            on_error=lambda e: logger.error(f"WebSocket error: {e}")
        )
        self.ws_client.start()

        # Initial scan
        await self.scan_and_subscribe()

        # Main loop
        try:
            while True:
                # Rescan every 5 minutes
                if time.time() - self.last_scan_time >= 300:
                    await self.scan_and_subscribe()

                # Print statistics every 10 seconds
                if self.update_count % 100 == 0:
                    self.print_stats()

                await asyncio.sleep(1)

        except KeyboardInterrupt:
            logger.info("Stopping data collector...")
            self.ws_client.stop()
            self.print_final_stats()

    def print_stats(self):
        """Print current statistics"""
        runtime = time.time() - self.start_time
        updates_per_sec = self.update_count / runtime if runtime > 0 else 0

        logger.info("="*60)
        logger.info("REAL-TIME DATA COLLECTOR STATISTICS")
        logger.info("="*60)
        logger.info(f"Runtime: {runtime:.0f}s")
        logger.info(f"Total updates: {self.update_count}")
        logger.info(f"Updates/second: {updates_per_sec:.1f}")
        logger.info(f"Tracked tokens: {len(self.price_data)}")
        logger.info(f"Qualified events: {len(self.qualified_event_ids)}")
        logger.info(f"WebSocket status: {'Connected' if self.ws_client.is_connected else 'Disconnected'}")
        logger.info("="*60)

    def print_final_stats(self):
        """Print final statistics"""
        runtime = time.time() - self.start_time

        logger.info("\n" + "="*60)
        logger.info("FINAL STATISTICS")
        logger.info("="*60)
        logger.info(f"Total runtime: {runtime:.0f}s ({runtime/60:.1f} minutes)")
        logger.info(f"Total price updates: {self.update_count}")
        logger.info(f"Average updates/sec: {self.update_count/runtime:.2f}")
        logger.info(f"Tokens tracked: {len(self.price_data)}")
        logger.info(f"Events monitored: {len(self.events)}")

        # Data completeness
        complete_data = sum(1 for d in self.price_data.values() if len(d) >= 60)
        logger.info(f"Tokens with >60s data: {complete_data}/{len(self.price_data)}")

        logger.info("="*60)


async def main():
    """Main function"""
    print("\n" + "="*80)
    print("OPTIMIZED REAL-TIME DATA COLLECTOR")
    print("Fetches live sports betting data every second")
    print("="*80 + "\n")

    # Test API connection first
    print("Testing API connection...")
    api = GammaAPI(proxy=config.api.proxy)
    success, msg, latency = api.test_connection()

    if not success:
        print(f"❌ Connection failed: {msg}")
        print("\nPlease check:")
        print("  1. Internet connection")
        print("  2. Proxy settings (if needed)")
        print("  3. Polymarket API availability")
        return 1

    print(f"✅ Connected successfully ({latency:.2f}s latency)")
    print(f"\nConfiguration:")
    print(f"  - Proxy: {config.api.proxy or 'None'}")
    print(f"  - Min Volume: ${config.filter.min_24h_volume:,.0f}")
    print(f"  - Update Frequency: 1 second")
    print(f"  - History Buffer: 5 minutes")

    print("\n" + "="*80)
    print("STARTING DATA COLLECTION - Press Ctrl+C to stop")
    print("="*80 + "\n")

    # Start collector
    collector = OptimizedDataCollector()
    await collector.start_collection()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\nStopped by user.")
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
