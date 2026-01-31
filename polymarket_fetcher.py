"""
Polymarket Gamma API - Fetch Open Markets and Events

This script fetches all currently open markets and events from Polymarket's Gamma API.
API Documentation: https://docs.polymarket.com/developers/gamma-markets-api/overview
"""

import requests
from typing import List, Dict, Optional
import json
import time
import socket
import sys
import argparse


class PolymarketAPI:
    """Client for interacting with Polymarket's Gamma Markets API"""

    BASE_URL = "https://gamma-api.polymarket.com"

    def __init__(self, proxy: Optional[str] = None, timeout: int = 30, max_retries: int = 3, verify_ssl: bool = True):
        """
        Initialize Polymarket API client

        Args:
            proxy: Proxy URL (e.g., 'http://127.0.0.1:7890' or 'socks5://127.0.0.1:1080')
            timeout: Request timeout in seconds (default: 30)
            max_retries: Maximum number of retry attempts (default: 3)
            verify_ssl: Verify SSL certificates (default: True, set to False if using proxy with SSL issues)
        """
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        self.timeout = timeout
        self.max_retries = max_retries
        self.verify_ssl = verify_ssl

        # Disable SSL verification if requested (for proxies with SSL issues)
        if not verify_ssl:
            self.session.verify = False
            import urllib3
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
            print("⚠ SSL verification disabled - use only with trusted proxies")

        # Configure proxy if provided
        if proxy:
            print(f"Using proxy: {proxy}")
            self.session.proxies = {
                'http': proxy,
                'https': proxy
            }

        # Configure retry strategy
        from requests.adapters import HTTPAdapter
        from urllib3.util.retry import Retry

        try:
            # Try newer urllib3 API first
            retry_strategy = Retry(
                total=max_retries,
                backoff_factor=1,
                status_forcelist=[429, 500, 502, 503, 504],
                allowed_methods=["GET"]
            )
        except TypeError:
            # Fall back to older urllib3 API
            retry_strategy = Retry(
                total=max_retries,
                backoff_factor=1,
                status_forcelist=[429, 500, 502, 503, 504],
                method_whitelist=["GET"]
            )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)

    def test_connection(self) -> bool:
        """
        Test connection to Polymarket API

        Returns:
            True if connection successful, False otherwise
        """
        print("\n" + "=" * 60)
        print("TESTING CONNECTION")
        print("=" * 60)

        # Test DNS resolution
        try:
            print(f"Testing DNS resolution for gamma-api.polymarket.com...")
            ip = socket.gethostbyname("gamma-api.polymarket.com")
            print(f"  ✓ DNS resolved to: {ip}")
        except socket.gaierror as e:
            print(f"  ✗ DNS resolution failed: {e}")
            return False

        # Test HTTP connection
        try:
            print(f"Testing HTTP connection...")
            response = self.session.get(
                f"{self.BASE_URL}/events",
                params={"limit": 1},
                timeout=self.timeout,
                verify=self.verify_ssl
            )
            response.raise_for_status()
            print(f"  ✓ Connection successful (Status: {response.status_code})")
            print(f"  ✓ Response time: {response.elapsed.total_seconds():.2f}s")
            return True
        except requests.exceptions.ProxyError as e:
            print(f"  ✗ Proxy error: {e}")
            print(f"  → Check your proxy settings")
            return False
        except requests.exceptions.SSLError as e:
            print(f"  ✗ SSL error: {e}")
            print(f"  → Try using a VPN or different network")
            return False
        except requests.exceptions.ConnectionError as e:
            print(f"  ✗ Connection error: {e}")
            print(f"  → Network may be blocked or unreachable")
            print(f"  → Try using a proxy or VPN")
            return False
        except requests.exceptions.Timeout as e:
            print(f"  ✗ Timeout error: {e}")
            print(f"  → Try increasing timeout or use faster network")
            return False
        except Exception as e:
            print(f"  ✗ Unexpected error: {type(e).__name__}: {e}")
            return False

    def _make_request(self, endpoint: str, params: Dict) -> Dict:
        """
        Make HTTP request with retry logic and error handling

        Args:
            endpoint: API endpoint URL
            params: Query parameters

        Returns:
            Response JSON data

        Raises:
            requests.exceptions.RequestException: On request failure
        """
        for attempt in range(self.max_retries):
            try:
                response = self.session.get(endpoint, params=params, timeout=self.timeout, verify=self.verify_ssl)
                response.raise_for_status()
                return response.json()
            except requests.exceptions.Timeout:
                if attempt < self.max_retries - 1:
                    wait_time = 2 ** attempt
                    print(f"  Timeout, retrying in {wait_time}s... (attempt {attempt + 1}/{self.max_retries})")
                    time.sleep(wait_time)
                else:
                    raise
            except requests.exceptions.ConnectionError:
                if attempt < self.max_retries - 1:
                    wait_time = 2 ** attempt
                    print(f"  Connection error, retrying in {wait_time}s... (attempt {attempt + 1}/{self.max_retries})")
                    time.sleep(wait_time)
                else:
                    raise
            except requests.exceptions.RequestException:
                raise

    def get_events(
        self,
        limit: int = 100,
        offset: int = 0,
        closed: bool = False,
        archived: bool = False,
        active: bool = True,
        tag_id: Optional[str] = None
    ) -> Dict:
        """
        Fetch events from Polymarket

        Args:
            limit: Number of events to fetch per request (default: 100)
            offset: Offset for pagination (default: 0)
            closed: Include closed events (default: False)
            archived: Include archived events (default: False)
            active: Include active events (default: True)
            tag_id: Filter by specific tag ID (optional)

        Returns:
            Dictionary containing events data
        """
        endpoint = f"{self.BASE_URL}/events"
        params = {
            "limit": limit,
            "offset": offset,
            "closed": str(closed).lower(),
            "archived": str(archived).lower(),
            "active": str(active).lower()
        }

        if tag_id:
            params["tag_id"] = tag_id

        return self._make_request(endpoint, params)

    def get_markets(
        self,
        limit: int = 100,
        offset: int = 0,
        closed: bool = False,
        archived: bool = False,
        active: bool = True,
        tag_id: Optional[str] = None
    ) -> Dict:
        """
        Fetch markets from Polymarket

        Args:
            limit: Number of markets to fetch per request (default: 100)
            offset: Offset for pagination (default: 0)
            closed: Include closed markets (default: False)
            archived: Include archived markets (default: False)
            active: Include active markets (default: True)
            tag_id: Filter by specific tag ID (optional)

        Returns:
            Dictionary containing markets data
        """
        endpoint = f"{self.BASE_URL}/markets"
        params = {
            "limit": limit,
            "offset": offset,
            "closed": str(closed).lower(),
            "archived": str(archived).lower(),
            "active": str(active).lower()
        }

        if tag_id:
            params["tag_id"] = tag_id

        return self._make_request(endpoint, params)

    def get_all_events(self, active_only: bool = True) -> List[Dict]:
        """
        Fetch ALL events with automatic pagination

        Args:
            active_only: Only fetch active (open) events (default: True)

        Returns:
            List of all events
        """
        all_events = []
        offset = 0
        limit = 100

        print(f"Fetching {'active' if active_only else 'all'} events...")

        while True:
            try:
                response = self.get_events(
                    limit=limit,
                    offset=offset,
                    active=active_only,
                    closed=not active_only,
                    archived=False
                )

                events = response if isinstance(response, list) else response.get('data', [])

                if not events:
                    break

                all_events.extend(events)
                print(f"  Fetched {len(events)} events (total: {len(all_events)})")

                if len(events) < limit:
                    break

                offset += limit

            except requests.exceptions.RequestException as e:
                print(f"Error fetching events: {e}")
                break

        print(f"Total events fetched: {len(all_events)}\n")
        return all_events

    def get_all_markets(self, active_only: bool = True) -> List[Dict]:
        """
        Fetch ALL markets with automatic pagination

        Args:
            active_only: Only fetch active (open) markets (default: True)

        Returns:
            List of all markets
        """
        all_markets = []
        offset = 0
        limit = 100

        print(f"Fetching {'active' if active_only else 'all'} markets...")

        while True:
            try:
                response = self.get_markets(
                    limit=limit,
                    offset=offset,
                    active=active_only,
                    closed=not active_only,
                    archived=False
                )

                markets = response if isinstance(response, list) else response.get('data', [])

                if not markets:
                    break

                all_markets.extend(markets)
                print(f"  Fetched {len(markets)} markets (total: {len(all_markets)})")

                if len(markets) < limit:
                    break

                offset += limit

            except requests.exceptions.RequestException as e:
                print(f"Error fetching markets: {e}")
                break

        print(f"Total markets fetched: {len(all_markets)}\n")
        return all_markets

    def get_tags(self) -> List[Dict]:
        """Fetch all available tags"""
        endpoint = f"{self.BASE_URL}/tags"
        return self._make_request(endpoint, {})

    def get_sports_tags(self) -> List[Dict]:
        """Fetch all sports tags"""
        endpoint = f"{self.BASE_URL}/sports"
        return self._make_request(endpoint, {})

    def get_sports_events(self, active_only: bool = True, limit_per_tag: int = 100) -> Dict[str, List[Dict]]:
        """
        Fetch sports events grouped by sport type

        Args:
            active_only: Only fetch active (open) events (default: True)
            limit_per_tag: Maximum events to fetch per sport tag (default: 100)

        Returns:
            Dictionary with sport names as keys and lists of events as values
        """
        print("Fetching sports tags...")

        try:
            sports_tags = self.get_sports_tags()
            print(f"Found {len(sports_tags)} sports categories")
        except Exception as e:
            print(f"Error fetching sports tags: {e}")
            return {}

        sports_events = {}

        for sport in sports_tags:
            sport_label = sport.get('label', 'Unknown')
            sport_tag = sport.get('tag', '')

            if not sport_tag:
                continue

            print(f"\nFetching events for {sport_label}...")

            try:
                # Fetch events with this sport tag
                response = self.get_events(
                    limit=limit_per_tag,
                    active=active_only,
                    closed=not active_only,
                    tag_id=sport_tag
                )

                events = response if isinstance(response, list) else response.get('data', [])

                if events:
                    sports_events[sport_label] = events
                    print(f"  Found {len(events)} {sport_label} events")
                else:
                    print(f"  No events found for {sport_label}")

            except Exception as e:
                print(f"  Error fetching {sport_label} events: {e}")
                continue

        total_events = sum(len(events) for events in sports_events.values())
        print(f"\nTotal sports events fetched: {total_events}")

        return sports_events


def main():
    """Main function to demonstrate fetching open markets and events"""

    # Parse command line arguments for proxy configuration
    parser = argparse.ArgumentParser(description='Fetch Polymarket open markets and events')
    parser.add_argument('--proxy', type=str, help='Proxy URL (e.g., http://127.0.0.1:7890 or socks5://127.0.0.1:1080)')
    parser.add_argument('--timeout', type=int, default=30, help='Request timeout in seconds (default: 30)')
    parser.add_argument('--test-only', action='store_true', help='Only test connection, do not fetch data')
    parser.add_argument('--no-verify-ssl', action='store_true', help='Disable SSL certificate verification (use with Clash/proxy)')
    args = parser.parse_args()

    # Initialize API client with proxy if provided
    try:
        api = PolymarketAPI(proxy=args.proxy, timeout=args.timeout, verify_ssl=not args.no_verify_ssl)
    except Exception as e:
        print(f"Error initializing API client: {e}")
        sys.exit(1)

    # Test connection first
    connection_ok = api.test_connection()

    if not connection_ok:
        print("\n" + "=" * 60)
        print("CONNECTION FAILED")
        print("=" * 60)
        print("\nPossible solutions:")
        print("1. Use a VPN or proxy:")
        print("   python polymarket_fetcher.py --proxy http://127.0.0.1:7890")
        print("   python polymarket_fetcher.py --proxy socks5://127.0.0.1:1080")
        print("\n2. Check if gamma-api.polymarket.com is accessible from your network")
        print("3. Try from a different network or location")
        print("\nFor SOCKS proxy support, install: pip install requests[socks]")
        sys.exit(1)

    if args.test_only:
        print("\n✓ Connection test successful!")
        sys.exit(0)

    # Fetch all open events
    print("\n" + "=" * 60)
    print("FETCHING OPEN EVENTS")
    print("=" * 60)
    try:
        open_events = api.get_all_events(active_only=True)
    except Exception as e:
        print(f"Failed to fetch events: {e}")
        open_events = []

    # Fetch all open markets
    print("=" * 60)
    print("FETCHING OPEN MARKETS")
    print("=" * 60)
    try:
        open_markets = api.get_all_markets(active_only=True)
    except Exception as e:
        print(f"Failed to fetch markets: {e}")
        open_markets = []

    # Display summary
    print("=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"Total open events: {len(open_events)}")
    print(f"Total open markets: {len(open_markets)}")

    if not open_events and not open_markets:
        print("\n⚠ No data fetched. Check network connection and try again.")
        sys.exit(1)

    # Save to files
    if open_events:
        with open('open_events.json', 'w') as f:
            json.dump(open_events, f, indent=2)
        print("\n✓ Open events saved to: open_events.json")

    if open_markets:
        with open('open_markets.json', 'w') as f:
            json.dump(open_markets, f, indent=2)
        print("✓ Open markets saved to: open_markets.json")

    # Display sample event (if available)
    if open_events:
        print("\n" + "=" * 60)
        print("SAMPLE EVENT")
        print("=" * 60)
        sample_event = open_events[0]
        print(f"Title: {sample_event.get('title', 'N/A')}")
        print(f"Slug: {sample_event.get('slug', 'N/A')}")
        print(f"Markets Count: {len(sample_event.get('markets', []))}")
        print(f"End Date: {sample_event.get('end_date_iso', 'N/A')}")

    # Display sample market (if available)
    if open_markets:
        print("\n" + "=" * 60)
        print("SAMPLE MARKET")
        print("=" * 60)
        sample_market = open_markets[0]
        print(f"Question: {sample_market.get('question', 'N/A')}")
        print(f"Market Slug: {sample_market.get('market_slug', 'N/A')}")
        print(f"Volume: {sample_market.get('volume', 'N/A')}")
        print(f"End Date: {sample_market.get('end_date_iso', 'N/A')}")


if __name__ == "__main__":
    main()
