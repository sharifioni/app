"""
Event Filter - Selects high-quality trading events
Scores and ranks events based on liquidity, spread, activity, and volatility
"""

import logging
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timezone
import time
from ..api import GammaAPI, parse_price, calculate_spread

logger = logging.getLogger(__name__)


@dataclass
class EventScore:
    """Event scoring details"""
    event_id: str
    title: str
    total_score: float = 0.0

    # Component scores
    liquidity_score: float = 0.0
    spread_score: float = 0.0
    activity_score: float = 0.0
    volatility_score: float = 0.0
    category_bonus: float = 0.0

    # Metrics
    volume_24h: float = 0.0
    liquidity: float = 0.0
    spread: float = 0.0

    # Event details
    live: bool = False
    period: str = ""
    elapsed: str = ""
    markets_count: int = 0

    @property
    def rank_display(self) -> str:
        """Display string for ranking"""
        return f"{self.title[:50]} - Score: {self.total_score:.1f}"


class EventFilter:
    """
    Filters and scores live sports events for trading suitability

    Criteria:
    - Game progress between 30%-70%
    - High liquidity (>$100K)
    - Low spread (<3%)
    - Active trading (recent volume)
    """

    def __init__(self, gamma_api: GammaAPI, config):
        self.api = gamma_api
        self.config = config

        # Cache for event scores
        self._event_scores: Dict[str, EventScore] = {}
        self._last_scan_time: float = 0

        # Top events list
        self._top_events: List[EventScore] = []

    def _calculate_game_progress(self, event: Dict) -> Optional[float]:
        """
        Calculate game progress percentage (0.0 - 1.0)

        Returns:
            Progress ratio or None if unable to determine
        """
        period = event.get('period', '')
        elapsed = event.get('elapsed', '')

        # Try to parse elapsed time
        # Format examples: "12:34", "01:23:45"
        if elapsed and ':' in elapsed:
            try:
                parts = elapsed.split(':')
                if len(parts) == 2:  # MM:SS
                    minutes = int(parts[0])
                    seconds = int(parts[1])
                    total_seconds = minutes * 60 + seconds
                elif len(parts) == 3:  # HH:MM:SS
                    hours = int(parts[0])
                    minutes = int(parts[1])
                    seconds = int(parts[2])
                    total_seconds = hours * 3600 + minutes * 60 + seconds
                else:
                    total_seconds = 0

                # Estimate total game time based on sport
                # This is simplified - actual logic would detect sport type
                estimated_total = 5400  # 90 minutes for soccer
                if total_seconds > 0:
                    return min(1.0, total_seconds / estimated_total)
            except:
                pass

        # Fallback: use period information
        if period:
            # Basketball: 4 quarters
            if period in ['Q1', '1Q', '1/4']:
                return 0.25
            elif period in ['Q2', '2Q', '2/4']:
                return 0.50
            elif period in ['Q3', '3Q', '3/4']:
                return 0.75
            elif period in ['Q4', '4Q', '4/4']:
                return 0.90
            # Soccer: 2 halves
            elif period in ['H1', '1H', 'FH']:
                return 0.45
            elif period in ['H2', '2H', 'SH']:
                return 0.85
            # Generic
            elif '/' in period:
                try:
                    current, total = period.split('/')
                    return float(current) / float(total)
                except:
                    pass

        return None

    def _meets_status_criteria(self, event: Dict) -> Tuple[bool, str]:
        """
        Check if event meets status criteria

        Returns:
            (meets_criteria, reason_if_not)
        """
        # Must be live
        if not event.get('live', False):
            return False, "not live"

        # Must not be ended
        if event.get('ended', False):
            return False, "ended"

        # Check period - skip suspended/halftime
        period = event.get('period', '')
        if period in ['SUS', 'HT', 'BT', 'SUSP', 'BREAK']:
            return False, f"on break ({period})"

        # Check game progress
        progress = self._calculate_game_progress(event)
        if progress is not None:
            if progress < self.config.filter.min_game_progress:
                return False, f"too early ({progress:.1%})"
            if progress > self.config.filter.max_game_progress:
                return False, f"too late ({progress:.1%})"

        return True, ""

    def _meets_liquidity_criteria(self, event: Dict) -> Tuple[bool, str]:
        """
        Check if event meets liquidity criteria

        Returns:
            (meets_criteria, reason_if_not)
        """
        volume_24h = event.get('volume24hr', event.get('volume', 0))
        liquidity = event.get('liquidity', 0)

        if volume_24h < self.config.filter.min_24h_volume:
            return False, f"low volume (${volume_24h:,.0f})"

        if liquidity < self.config.filter.min_liquidity:
            return False, f"low liquidity (${liquidity:,.0f})"

        return True, ""

    def _calculate_spread(self, event: Dict) -> float:
        """Calculate average spread across all markets in event"""
        markets = event.get('markets', [])
        if not markets:
            return 1.0  # Max spread if no markets

        spreads = []
        for market in markets:
            prices = parse_price(market.get('outcomePrices', '[]'))
            if prices:
                spread = calculate_spread(prices)
                spreads.append(spread)

        return sum(spreads) / len(spreads) if spreads else 1.0

    def _meets_technical_criteria(self, event: Dict) -> Tuple[bool, str]:
        """
        Check if event meets technical criteria (spread, market type)

        Returns:
            (meets_criteria, reason_if_not)
        """
        # Check spread
        avg_spread = self._calculate_spread(event)
        if avg_spread > self.config.filter.max_spread:
            return False, f"high spread ({avg_spread:.1%})"

        # Check if binary markets (2 outcomes)
        markets = event.get('markets', [])
        if not markets:
            return False, "no markets"

        # At least one market should be binary
        has_binary = False
        for market in markets:
            outcomes = market.get('outcomes', [])
            if isinstance(outcomes, str):
                import json
                try:
                    outcomes = json.loads(outcomes)
                except:
                    outcomes = []
            if len(outcomes) == 2:
                has_binary = True
                break

        if not has_binary:
            return False, "no binary markets"

        return True, ""

    def _calculate_score(self, event: Dict) -> EventScore:
        """
        Calculate comprehensive score for event

        Returns:
            EventScore object with detailed scoring
        """
        event_id = event.get('id', '')
        title = event.get('title', 'Unknown')

        score = EventScore(event_id=event_id, title=title)

        # Get metrics
        volume_24h = event.get('volume24hr', event.get('volume', 0))
        volume_1h = event.get('volume1hr', volume_24h / 24)  # Estimate if not available
        liquidity = event.get('liquidity', 0)
        avg_spread = self._calculate_spread(event)

        score.volume_24h = volume_24h
        score.liquidity = liquidity
        score.spread = avg_spread

        # 1. Liquidity Score (0-20 points)
        # Higher volume = higher score
        if volume_24h >= 5_000_000:  # $5M+
            score.liquidity_score = 20
        elif volume_24h >= 2_000_000:  # $2M+
            score.liquidity_score = 15
        elif volume_24h >= 1_000_000:  # $1M+
            score.liquidity_score = 10
        elif volume_24h >= 500_000:    # $500K+
            score.liquidity_score = 5
        else:
            score.liquidity_score = 0

        # 2. Spread Score (0-10 points)
        # Lower spread = higher score
        if avg_spread <= 0.01:  # <1%
            score.spread_score = 10
        elif avg_spread <= 0.02:  # <2%
            score.spread_score = 7
        elif avg_spread <= 0.03:  # <3%
            score.spread_score = 4
        else:
            score.spread_score = 0

        # 3. Activity Score (0-15 points)
        # Recent activity relative to 24h average
        activity_ratio = volume_1h / (volume_24h / 24) if volume_24h > 0 else 0
        if activity_ratio >= 2.0:  # 2x average
            score.activity_score = 15
        elif activity_ratio >= 1.5:  # 1.5x average
            score.activity_score = 10
        elif activity_ratio >= 1.0:  # At least average
            score.activity_score = 5
        else:
            score.activity_score = 0

        # 4. Volatility Score (0-10 points)
        # Higher volatility = more opportunities
        # Simplified: use spread as proxy for volatility
        if avg_spread >= 0.025:
            score.volatility_score = 10
        elif avg_spread >= 0.02:
            score.volatility_score = 7
        elif avg_spread >= 0.015:
            score.volatility_score = 4
        else:
            score.volatility_score = 0

        # 5. Category Bonus (0-10 points)
        # Priority sports get bonus
        title_lower = title.lower()
        for sport in self.config.filter.priority_sports:
            if sport in title_lower:
                score.category_bonus = self.config.filter.category_bonus
                break

        # Event details
        score.live = event.get('live', False)
        score.period = event.get('period', '')
        score.elapsed = event.get('elapsed', '')
        score.markets_count = len(event.get('markets', []))

        # Total score
        score.total_score = (
            score.liquidity_score +
            score.spread_score +
            score.activity_score +
            score.volatility_score +
            score.category_bonus
        )

        return score

    def filter_and_score_events(self, events: Optional[List[Dict]] = None) -> List[EventScore]:
        """
        Filter and score all events

        Args:
            events: List of events to filter (if None, fetches from API)

        Returns:
            List of EventScore objects, sorted by score (highest first)
        """
        if events is None:
            logger.info("Fetching live events from API...")
            events = self.api.get_live_events()

        logger.info(f"Filtering {len(events)} live events...")

        qualifying_events = []
        rejection_reasons: Dict[str, int] = {}

        for event in events:
            # Check status criteria
            meets_status, reason = self._meets_status_criteria(event)
            if not meets_status:
                rejection_reasons[reason] = rejection_reasons.get(reason, 0) + 1
                continue

            # Check liquidity criteria
            meets_liquidity, reason = self._meets_liquidity_criteria(event)
            if not meets_liquidity:
                rejection_reasons[reason] = rejection_reasons.get(reason, 0) + 1
                continue

            # Check technical criteria
            meets_technical, reason = self._meets_technical_criteria(event)
            if not meets_technical:
                rejection_reasons[reason] = rejection_reasons.get(reason, 0) + 1
                continue

            # Calculate score
            score = self._calculate_score(event)
            qualifying_events.append((score, event))

        # Sort by score (descending)
        qualifying_events.sort(key=lambda x: x[0].total_score, reverse=True)

        # Log results
        logger.info(f"Qualified events: {len(qualifying_events)}/{len(events)}")
        if rejection_reasons:
            logger.info("Rejection reasons:")
            for reason, count in sorted(rejection_reasons.items(), key=lambda x: -x[1]):
                logger.info(f"  - {reason}: {count}")

        # Cache scores
        self._event_scores.clear()
        for score, event in qualifying_events:
            self._event_scores[score.event_id] = score

        # Update top events (keep top 20)
        self._top_events = [score for score, _ in qualifying_events[:20]]
        self._last_scan_time = time.time()

        # Return scores with original events attached
        return [score for score, _ in qualifying_events]

    def get_top_events(self, limit: int = 20) -> List[EventScore]:
        """Get top N events by score"""
        return self._top_events[:limit]

    def get_event_score(self, event_id: str) -> Optional[EventScore]:
        """Get cached score for specific event"""
        return self._event_scores.get(event_id)

    def should_rescan(self) -> bool:
        """Check if it's time to rescan events"""
        elapsed = time.time() - self._last_scan_time
        return elapsed >= self.config.filter.rescan_interval

    def get_qualified_event_ids(self) -> List[str]:
        """Get list of all qualified event IDs"""
        return list(self._event_scores.keys())

    def print_top_events(self, limit: int = 10):
        """Print top events for debugging"""
        print(f"\n{'='*80}")
        print(f"TOP {limit} QUALIFIED EVENTS")
        print(f"{'='*80}")

        for i, score in enumerate(self._top_events[:limit], 1):
            print(f"\n{i}. {score.title[:60]}")
            print(f"   Score: {score.total_score:.1f} "
                  f"(Liq:{score.liquidity_score:.0f} "
                  f"Spread:{score.spread_score:.0f} "
                  f"Act:{score.activity_score:.0f} "
                  f"Vol:{score.volatility_score:.0f} "
                  f"Bonus:{score.category_bonus:.0f})")
            print(f"   Volume: ${score.volume_24h:,.0f} | "
                  f"Liquidity: ${score.liquidity:,.0f} | "
                  f"Spread: {score.spread:.1%}")
            print(f"   Status: {score.period} | Markets: {score.markets_count}")

        print(f"\n{'='*80}\n")
