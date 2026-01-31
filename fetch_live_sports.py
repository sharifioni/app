"""
Fetch Live Sports Events from Polymarket

This script demonstrates how to fetch only live sports events from Polymarket.
A "live" event is one where the current time is between the start and end dates.
"""

import requests
from datetime import datetime, timezone
from typing import List, Dict, Optional
import json
from polymarket_fetcher import PolymarketAPI


class LiveSportsFilter:
    """Filter and fetch live sports events from Polymarket"""

    # Common sports keywords to identify sports events
    SPORTS_KEYWORDS = [
        'nfl', 'nba', 'mlb', 'nhl', 'soccer', 'football', 'basketball',
        'baseball', 'hockey', 'tennis', 'ufc', 'mma', 'boxing', 'golf',
        'cricket', 'rugby', 'f1', 'formula', 'super bowl', 'world cup',
        'champions league', 'premier league', 'playoffs', 'championship',
        'tournament', 'game', 'match', 'series'
    ]

    def __init__(self, api: PolymarketAPI):
        """Initialize with PolymarketAPI instance"""
        self.api = api

    def is_live_event(self, event: Dict, hours_window: int = 48) -> bool:
        """
        Check if an event is currently live (happening now or very soon)

        For sports betting, "live" means the game/event is happening RIGHT NOW
        or within the next few hours/days, not just that betting is open.

        Args:
            event: Event dictionary
            hours_window: How many hours ahead to consider "live" (default: 48 hours)

        Returns:
            True if event is live or starting very soon, False otherwise
        """
        from datetime import timedelta

        now = datetime.now(timezone.utc)

        # Get start and end dates
        start_date_str = event.get('startDate', event.get('startDateIso', ''))
        end_date_str = event.get('endDate', event.get('endDateIso', ''))

        if not start_date_str or not end_date_str:
            return False

        try:
            # Parse dates (handle both ISO format and date-only format)
            if 'T' in start_date_str:
                start_date = datetime.fromisoformat(start_date_str.replace('Z', '+00:00'))
            else:
                start_date = datetime.fromisoformat(start_date_str + 'T00:00:00+00:00')

            if 'T' in end_date_str:
                end_date = datetime.fromisoformat(end_date_str.replace('Z', '+00:00'))
            else:
                end_date = datetime.fromisoformat(end_date_str + 'T23:59:59+00:00')

            # Check if event is active and not closed
            is_active = event.get('active', False) and not event.get('closed', True)
            if not is_active:
                return False

            # Calculate event duration
            event_duration = (end_date - start_date).total_seconds() / 3600  # in hours

            # Option 1: Event is happening now (between start and end) AND has short duration
            # (Short duration = less than 7 days, typical for actual games/matches)
            if start_date <= now <= end_date and event_duration <= 168:  # 7 days
                return True

            # Option 2: Event is starting very soon (within the hours_window)
            time_until_start = (start_date - now).total_seconds() / 3600  # in hours
            if 0 <= time_until_start <= hours_window:
                return True

            # Option 3: Event is ending very soon (within the hours_window)
            # This catches games that are currently being played
            time_until_end = (end_date - now).total_seconds() / 3600  # in hours
            if 0 <= time_until_end <= hours_window and start_date <= now:
                return True

            return False

        except (ValueError, TypeError) as e:
            print(f"Error parsing dates for event {event.get('id', 'unknown')}: {e}")
            return False

    def is_sports_event(self, event: Dict) -> bool:
        """
        Check if an event is sports-related based on title, description, and tags

        Args:
            event: Event dictionary

        Returns:
            True if event is sports-related, False otherwise
        """
        title = event.get('title', '').lower()
        description = event.get('description', '').lower()

        # Check if any sports keyword is in title or description
        for keyword in self.SPORTS_KEYWORDS:
            if keyword in title or keyword in description:
                return True

        return False

    def get_live_sports_events(self, hours_window: int = 48, use_tag_filter: bool = False, sport_tag: Optional[str] = None) -> List[Dict]:
        """
        Fetch all live sports events (happening now or very soon)

        Args:
            hours_window: How many hours ahead to consider "live" (default: 48 hours)
            use_tag_filter: If True, try to use tag filtering (requires sport_tag)
            sport_tag: Specific sport tag to filter by (e.g., 'NFL', 'NBA')

        Returns:
            List of live sports events
        """
        print("=" * 60)
        print(f"FETCHING LIVE SPORTS EVENTS (within {hours_window} hours)")
        print("=" * 60)

        # Fetch all active events
        if use_tag_filter and sport_tag:
            print(f"Fetching events with tag: {sport_tag}")
            try:
                all_events = self.api.get_all_events(active_only=True)
            except Exception as e:
                print(f"Error fetching events with tag filter: {e}")
                all_events = self.api.get_all_events(active_only=True)
        else:
            all_events = self.api.get_all_events(active_only=True)

        print(f"\nFiltering for live sports events...")

        # Filter for sports events
        sports_events = [event for event in all_events if self.is_sports_event(event)]
        print(f"  Found {len(sports_events)} sports events out of {len(all_events)} total events")

        # Filter for live events (with the specified time window)
        live_sports_events = [event for event in sports_events if self.is_live_event(event, hours_window)]
        print(f"  Found {len(live_sports_events)} LIVE sports events (within {hours_window}h window)")

        return live_sports_events

    def get_upcoming_sports_events(self, days_ahead: int = 7) -> List[Dict]:
        """
        Fetch upcoming sports events (starting within next X days)

        Args:
            days_ahead: Number of days to look ahead

        Returns:
            List of upcoming sports events
        """
        from datetime import timedelta

        now = datetime.now(timezone.utc)
        future_date = now + timedelta(days=days_ahead)

        print(f"\nFetching sports events starting within next {days_ahead} days...")

        all_events = self.api.get_all_events(active_only=True)
        sports_events = [event for event in all_events if self.is_sports_event(event)]

        upcoming_events = []
        for event in sports_events:
            start_date_str = event.get('startDate', event.get('startDateIso', ''))
            if not start_date_str:
                continue

            try:
                if 'T' in start_date_str:
                    start_date = datetime.fromisoformat(start_date_str.replace('Z', '+00:00'))
                else:
                    start_date = datetime.fromisoformat(start_date_str + 'T00:00:00+00:00')

                if now <= start_date <= future_date:
                    upcoming_events.append(event)
            except (ValueError, TypeError):
                continue

        print(f"  Found {len(upcoming_events)} upcoming sports events")
        return upcoming_events

    def get_past_month_events(self, days_back: int = 30) -> List[Dict]:
        """
        Fetch sports events from the past month (events that started within last X days)

        Args:
            days_back: Number of days to look back (default: 30)

        Returns:
            List of past sports events
        """
        from datetime import timedelta

        now = datetime.now(timezone.utc)
        past_date = now - timedelta(days=days_back)

        print("=" * 60)
        print(f"FETCHING PAST MONTH SPORTS EVENTS (last {days_back} days)")
        print("=" * 60)

        # Fetch all events including closed ones
        all_events = self.api.get_all_events(active_only=False)
        print(f"\nTotal events fetched: {len(all_events)}")

        # Filter for sports events
        sports_events = [event for event in all_events if self.is_sports_event(event)]
        print(f"Sports events found: {len(sports_events)}")

        past_events = []
        for event in sports_events:
            start_date_str = event.get('startDate', event.get('startDateIso', ''))
            if not start_date_str:
                continue

            try:
                if 'T' in start_date_str:
                    start_date = datetime.fromisoformat(start_date_str.replace('Z', '+00:00'))
                else:
                    start_date = datetime.fromisoformat(start_date_str + 'T00:00:00+00:00')

                # Check if event started within the past month
                if past_date <= start_date <= now:
                    past_events.append(event)
            except (ValueError, TypeError):
                continue

        print(f"Past month sports events: {len(past_events)}")
        return past_events


def display_live_sports(events: List[Dict]):
    """Display live sports events in a readable format"""
    from datetime import datetime, timezone

    if not events:
        print("\nNo live sports events found at this time.")
        print("\nTip: Try increasing the time window with --hours parameter")
        print("     Example: python fetch_live_sports.py --hours 72")
        return

    print("\n" + "=" * 60)
    print(f"LIVE SPORTS EVENTS ({len(events)})")
    print("=" * 60)

    now = datetime.now(timezone.utc)

    for i, event in enumerate(events, 1):
        # Calculate time until start/end
        start_date_str = event.get('startDate', '')
        end_date_str = event.get('endDate', '')

        time_info = ""
        if start_date_str and end_date_str:
            try:
                if 'T' in start_date_str:
                    start_date = datetime.fromisoformat(start_date_str.replace('Z', '+00:00'))
                else:
                    start_date = datetime.fromisoformat(start_date_str + 'T00:00:00+00:00')

                if 'T' in end_date_str:
                    end_date = datetime.fromisoformat(end_date_str.replace('Z', '+00:00'))
                else:
                    end_date = datetime.fromisoformat(end_date_str + 'T23:59:59+00:00')

                if now < start_date:
                    hours_until = (start_date - now).total_seconds() / 3600
                    if hours_until < 1:
                        time_info = f"⏰ Starts in {int(hours_until * 60)} minutes"
                    elif hours_until < 24:
                        time_info = f"⏰ Starts in {hours_until:.1f} hours"
                    else:
                        time_info = f"⏰ Starts in {hours_until / 24:.1f} days"
                elif now > end_date:
                    time_info = "🏁 Ended"
                else:
                    hours_remaining = (end_date - now).total_seconds() / 3600
                    if hours_remaining < 1:
                        time_info = f"🔴 LIVE - Ends in {int(hours_remaining * 60)} minutes"
                    elif hours_remaining < 24:
                        time_info = f"🔴 LIVE - Ends in {hours_remaining:.1f} hours"
                    else:
                        time_info = f"🔴 LIVE - Ends in {hours_remaining / 24:.1f} days"
            except:
                pass

        print(f"\n{i}. {event.get('title', 'N/A')}")
        if time_info:
            print(f"   {time_info}")
        print(f"   ID: {event.get('id', 'N/A')}")
        print(f"   Start: {event.get('startDate', 'N/A')[:19]}")
        print(f"   End: {event.get('endDate', 'N/A')[:19]}")
        print(f"   Volume: ${event.get('volume', 0):,.2f}")
        print(f"   Liquidity: ${event.get('liquidity', 0):,.2f}")
        print(f"   Markets: {len(event.get('markets', []))}")

        # Show market questions
        markets = event.get('markets', [])
        if markets:
            print(f"   Market Questions:")
            for market in markets[:3]:  # Show first 3 markets
                print(f"     - {market.get('question', 'N/A')}")
            if len(markets) > 3:
                print(f"     ... and {len(markets) - 3} more markets")


def display_past_events(events: List[Dict], days_back: int = 30):
    """Display past month sports events in a readable format"""
    from datetime import datetime, timezone

    if not events:
        print("\nNo past month sports events found.")
        return

    print("\n" + "=" * 60)
    print(f"PAST MONTH SPORTS EVENTS ({len(events)})")
    print("=" * 60)

    now = datetime.now(timezone.utc)

    for i, event in enumerate(events, 1):
        start_date_str = event.get('startDate', '')
        end_date_str = event.get('endDate', '')

        time_info = ""
        if start_date_str:
            try:
                if 'T' in start_date_str:
                    start_date = datetime.fromisoformat(start_date_str.replace('Z', '+00:00'))
                else:
                    start_date = datetime.fromisoformat(start_date_str + 'T00:00:00+00:00')

                days_ago = (now - start_date).days
                time_info = f"Started {days_ago} day(s) ago"
            except:
                pass

        status = "Closed" if event.get('closed', False) else "Active"

        print(f"\n{i}. {event.get('title', 'N/A')}")
        if time_info:
            print(f"   {time_info}")
        print(f"   Status: {status}")
        print(f"   ID: {event.get('id', 'N/A')}")
        print(f"   Start: {event.get('startDate', 'N/A')[:19]}")
        print(f"   End: {event.get('endDate', 'N/A')[:19]}")
        print(f"   Volume: ${event.get('volume', 0):,.2f}")
        print(f"   Markets: {len(event.get('markets', []))}")


def main():
    """Main function"""
    import argparse

    parser = argparse.ArgumentParser(description='Fetch live sports events from Polymarket')
    parser.add_argument('--proxy', type=str, help='Proxy URL')
    parser.add_argument('--save', action='store_true', help='Save results to JSON file')
    parser.add_argument('--upcoming', type=int, help='Also fetch upcoming events (days ahead)')
    parser.add_argument('--hours', type=int, default=48,
                       help='Time window in hours for "live" events (default: 48). Events starting or ending within this window are considered live.')
    parser.add_argument('--past-month', type=int, nargs='?', const=30, default=None,
                       help='Fetch events from past X days (default: 30 days if flag used without value)')
    args = parser.parse_args()

    # Initialize API
    api = PolymarketAPI(proxy=args.proxy)

    # Test connection
    if not api.test_connection():
        print("\nConnection failed. Exiting.")
        return

    # Initialize filter
    filter = LiveSportsFilter(api)

    # Get live sports events
    live_events = filter.get_live_sports_events(hours_window=args.hours)

    # Display results
    display_live_sports(live_events)

    # Get upcoming events if requested
    if args.upcoming:
        upcoming_events = filter.get_upcoming_sports_events(days_ahead=args.upcoming)

        print("\n" + "=" * 60)
        print(f"UPCOMING SPORTS EVENTS (Next {args.upcoming} days)")
        print("=" * 60)

        for i, event in enumerate(upcoming_events[:10], 1):  # Show first 10
            print(f"\n{i}. {event.get('title', 'N/A')}")
            print(f"   Start: {event.get('startDate', 'N/A')}")
            print(f"   Markets: {len(event.get('markets', []))}")

    # Get past month events if requested
    past_events = []
    if args.past_month:
        past_events = filter.get_past_month_events(days_back=args.past_month)
        display_past_events(past_events, days_back=args.past_month)

    # Save to file if requested
    if args.save:
        if live_events:
            filename = 'live_sports_events.json'
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(live_events, f, indent=2)
            print(f"\n✓ Live sports events saved to: {filename}")
        
        if past_events:
            filename = 'past_month_sports_events.json'
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(past_events, f, indent=2)
            print(f"✓ Past month sports events saved to: {filename}")

    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"Live sports events: {len(live_events)}")
    if args.upcoming:
        print(f"Upcoming sports events (next {args.upcoming} days): {len(upcoming_events)}")
    if args.past_month:
        print(f"Past month sports events (last {args.past_month} days): {len(past_events)}")


if __name__ == "__main__":
    main()
