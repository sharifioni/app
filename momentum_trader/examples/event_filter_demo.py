"""
Example: Basic Event Filtering
Demonstrates how to use the event filter to find trading opportunities
"""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from momentum_trader import config, load_config_from_env
from momentum_trader.api import GammaAPI
from momentum_trader.filters import EventFilter
import time
import logging

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def main():
    """Main function demonstrating event filtering"""

    print("\n" + "="*80)
    print("POLYMARKET MOMENTUM TRADER - Event Filter Demo")
    print("="*80 + "\n")

    # Load configuration
    cfg = load_config_from_env()
    print(f"Configuration loaded:")
    print(f"  - Min 24h Volume: ${cfg.filter.min_24h_volume:,.0f}")
    print(f"  - Min Liquidity: ${cfg.filter.min_liquidity:,.0f}")
    print(f"  - Max Spread: {cfg.filter.max_spread:.1%}")
    print(f"  - Priority Sports: {', '.join(cfg.filter.priority_sports)}")

    # Initialize API
    print(f"\nConnecting to Polymarket API...")
    if cfg.api.proxy:
        print(f"  Using proxy: {cfg.api.proxy}")

    api = GammaAPI(
        base_url=cfg.api.gamma_base_url,
        proxy=cfg.api.proxy,
        timeout=cfg.api.request_timeout
    )

    # Test connection
    print("\nTesting API connection...")
    success, msg, latency = api.test_connection()

    if not success:
        print(f"❌ Connection failed: {msg}")
        print("\nTroubleshooting:")
        print("  1. Check your internet connection")
        print("  2. Try using a proxy (set POLYMARKET_PROXY env var)")
        print("  3. Verify Polymarket API is accessible")
        return 1

    print(f"✅ Connected successfully ({latency:.2f}s response time)")

    # Get live events
    print("\nFetching live events...")
    start_time = time.time()
    live_events = api.get_live_events()
    fetch_time = time.time() - start_time

    print(f"✅ Fetched {len(live_events)} live events in {fetch_time:.2f}s")

    if not live_events:
        print("\n⚠️  No live events found at this time.")
        print("   Try again when there are live sports games happening.")
        return 0

    # Initialize event filter
    print("\nInitializing event filter...")
    event_filter = EventFilter(api, cfg)

    # Filter and score events
    print("\nFiltering and scoring events...")
    start_time = time.time()
    qualified_events = event_filter.filter_and_score_events(live_events)
    filter_time = time.time() - start_time

    print(f"✅ Filtering complete in {filter_time:.2f}s")
    print(f"   Qualified: {len(qualified_events)}/{len(live_events)} events")

    if not qualified_events:
        print("\n⚠️  No events meet the qualification criteria.")
        print("\nCommon reasons:")
        print("  - Volume too low (need >$500K)")
        print("  - Spread too wide (need <3%)")
        print("  - Game not in suitable progress range (30-70%)")
        print("\nTry lowering filter thresholds or check back later.")
        return 0

    # Display top events
    event_filter.print_top_events(limit=min(10, len(qualified_events)))

    # Show detailed info for top event
    if qualified_events:
        print("\n" + "="*80)
        print("DETAILED INFO: TOP EVENT")
        print("="*80)

        top_score = qualified_events[0]
        print(f"\nEvent: {top_score.title}")
        print(f"ID: {top_score.event_id}")
        print(f"\nScoring Breakdown:")
        print(f"  Liquidity Score:  {top_score.liquidity_score:>6.1f} / 20")
        print(f"  Spread Score:     {top_score.spread_score:>6.1f} / 10")
        print(f"  Activity Score:   {top_score.activity_score:>6.1f} / 15")
        print(f"  Volatility Score: {top_score.volatility_score:>6.1f} / 10")
        print(f"  Category Bonus:   {top_score.category_bonus:>6.1f} / 10")
        print(f"  {'─'*30}")
        print(f"  TOTAL SCORE:      {top_score.total_score:>6.1f} / 65")

        print(f"\nKey Metrics:")
        print(f"  24h Volume:  ${top_score.volume_24h:>12,.0f}")
        print(f"  Liquidity:   ${top_score.liquidity:>12,.0f}")
        print(f"  Avg Spread:  {top_score.spread:>12.2%}")
        print(f"  Markets:     {top_score.markets_count:>12,}")

        print(f"\nGame Status:")
        print(f"  Live:     {top_score.live}")
        print(f"  Period:   {top_score.period}")
        print(f"  Elapsed:  {top_score.elapsed}")

        print(f"\n{'='*80}")

    # Summary
    print(f"\n{'='*80}")
    print("SUMMARY")
    print(f"{'='*80}")
    print(f"Total live events:        {len(live_events)}")
    print(f"Qualified events:         {len(qualified_events)}")
    print(f"Qualification rate:       {len(qualified_events)/len(live_events):.1%}")
    print(f"\nAPI latency:              {latency:.2f}s")
    print(f"Fetch time:               {fetch_time:.2f}s")
    print(f"Filter time:              {filter_time:.2f}s")
    print(f"{'='*80}\n")

    print("✅ Event filter demo complete!")
    print("\nNext steps:")
    print("  1. Review the qualified events above")
    print("  2. These events are suitable for momentum trading")
    print("  3. Next: Implement test order placement")

    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n\nInterrupted by user.")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
        sys.exit(1)
