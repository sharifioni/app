"""
Gamma API Client - Market Data
Fetches events, markets, prices from Polymarket Gamma API
"""

import requests
import time
import logging
from typing import List, Dict, Optional, Any
from datetime import datetime, timezone
from dataclasses import dataclass
import json

logger = logging.getLogger(__name__)


@dataclass
class RateLimiter:
    """Token bucket rate limiter"""
    max_tokens: int
    refill_rate: float  # tokens per second
    tokens: float = None
    last_refill: float = None

    def __post_init__(self):
        self.tokens = float(self.max_tokens)
        self.last_refill = time.time()

    def acquire(self, tokens: int = 1) -> bool:
        """Try to acquire tokens, returns True if successful"""
        now = time.time()
        elapsed = now - self.last_refill
        self.tokens = min(self.max_tokens, self.tokens + elapsed * self.refill_rate)
        self.last_refill = now

        if self.tokens >= tokens:
            self.tokens -= tokens
            return True
        return False

    def wait_for_token(self, tokens: int = 1):
        """Wait until token is available"""
        while not self.acquire(tokens):
            time.sleep(0.1)


class GammaAPI:
    """
    Polymarket Gamma API Client for market data

    Endpoints:
    - /events - Get events list
    - /events/{id} - Get event details
    - /markets - Get markets list
    - /sports - Get sports categories
    """

    def __init__(self, base_url: str = "https://gamma-api.polymarket.com",
                 proxy: Optional[str] = None,
                 timeout: int = 30,
                 max_retries: int = 3):
        self.base_url = base_url
        self.timeout = timeout
        self.max_retries = max_retries

        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'application/json',
        })

        if proxy:
            self.session.proxies = {'http': proxy, 'https': proxy}

        # Rate limiter: 100 requests per minute = ~1.67 per second
        self.rate_limiter = RateLimiter(max_tokens=100, refill_rate=1.67)

        # Response time tracking
        self.last_response_time: float = 0

    def _request(self, endpoint: str, params: Optional[Dict] = None) -> Any:
        """Make HTTP request with retry and rate limiting"""
        self.rate_limiter.wait_for_token()

        url = f"{self.base_url}{endpoint}"
        last_error = None

        for attempt in range(self.max_retries):
            try:
                start_time = time.time()
                response = self.session.get(url, params=params, timeout=self.timeout)
                self.last_response_time = time.time() - start_time

                response.raise_for_status()
                return response.json()

            except requests.exceptions.Timeout as e:
                last_error = e
                logger.warning(f"Timeout on attempt {attempt + 1}/{self.max_retries}: {endpoint}")
                time.sleep(2 ** attempt)

            except requests.exceptions.ChunkedEncodingError as e:
                # Server closed connection mid-response (InvalidChunkLength)
                last_error = e
                logger.warning(f"Chunked encoding error on attempt {attempt + 1}/{self.max_retries}: {endpoint}")
                time.sleep(2 ** attempt)

            except requests.exceptions.ConnectionError as e:
                last_error = e
                logger.warning(f"Connection error on attempt {attempt + 1}/{self.max_retries}: {endpoint}")
                time.sleep(2 ** attempt)

            except requests.exceptions.HTTPError as e:
                if response.status_code == 429:  # Rate limited
                    logger.warning("Rate limited, waiting 60 seconds...")
                    time.sleep(60)
                    continue
                elif response.status_code >= 500:  # Server error, retry
                    last_error = e
                    logger.warning(f"Server error {response.status_code} on attempt {attempt + 1}/{self.max_retries}: {endpoint}")
                    time.sleep(2 ** attempt)
                    continue
                last_error = e
                logger.error(f"HTTP error {response.status_code}: {endpoint}")
                break

            except Exception as e:
                last_error = e
                logger.error(f"Unexpected error: {e}")
                # For unexpected errors, also retry
                time.sleep(2 ** attempt)

        raise Exception(f"Failed after {self.max_retries} attempts: {last_error}")

    def get_live_events(self) -> List[Dict]:
        """
        Get all currently live events

        Returns:
            List of live event dictionaries with fields:
            - id, title, live, score, period, elapsed, ended
            - volume, liquidity, markets, etc.
        """
        params = {
            'live': 'true',
            'active': 'true',
            'closed': 'false',
            'limit': 100
        }
        result = self._request('/events', params)
        return result if isinstance(result, list) else []

    def get_event(self, event_id: str) -> Optional[Dict]:
        """Get single event details by ID"""
        try:
            return self._request(f'/events/{event_id}')
        except Exception as e:
            logger.error(f"Error fetching event {event_id}: {e}")
            return None

    def get_events(self, active: bool = True, closed: bool = False,
                   live: Optional[bool] = None, tag_id: Optional[str] = None,
                   limit: int = 100, offset: int = 0) -> List[Dict]:
        """
        Get events with filters

        Args:
            active: Include active events
            closed: Include closed events
            live: Filter for live events only
            tag_id: Filter by tag (e.g., '100639' for games)
            limit: Max results per request
            offset: Pagination offset
        """
        params = {
            'active': str(active).lower(),
            'closed': str(closed).lower(),
            'limit': limit,
            'offset': offset
        }
        if live is not None:
            params['live'] = str(live).lower()
        if tag_id:
            params['tag_id'] = tag_id

        result = self._request('/events', params)
        return result if isinstance(result, list) else []

    def get_all_events(self, **kwargs) -> List[Dict]:
        """Get all events with automatic pagination"""
        all_events = []
        offset = 0
        limit = 100

        while True:
            events = self.get_events(limit=limit, offset=offset, **kwargs)
            if not events:
                break
            all_events.extend(events)
            if len(events) < limit:
                break
            offset += limit

        return all_events

    def get_markets(self, active: bool = True, closed: bool = False,
                    limit: int = 100, offset: int = 0) -> List[Dict]:
        """Get markets list"""
        params = {
            'active': str(active).lower(),
            'closed': str(closed).lower(),
            'limit': limit,
            'offset': offset
        }
        result = self._request('/markets', params)
        return result if isinstance(result, list) else []

    def get_market(self, market_id: str) -> Optional[Dict]:
        """Get single market details"""
        try:
            return self._request(f'/markets/{market_id}')
        except Exception as e:
            logger.error(f"Error fetching market {market_id}: {e}")
            return None

    def get_sports(self) -> List[Dict]:
        """Get all sports categories"""
        result = self._request('/sports')
        return result if isinstance(result, list) else []

    def get_sports_events(self, sport: str, active: bool = True) -> List[Dict]:
        """Get events for a specific sport"""
        sports = self.get_sports()
        sport_info = next((s for s in sports if s.get('sport', '').lower() == sport.lower()), None)

        if not sport_info:
            return []

        series_id = sport_info.get('series')
        if not series_id:
            return []

        return self.get_events(active=active, tag_id=series_id)

    def test_connection(self) -> tuple:
        """
        Test API connection

        Returns:
            (success: bool, message: str, response_time: float)
        """
        try:
            start = time.time()
            result = self._request('/events', {'limit': 1})
            elapsed = time.time() - start
            return True, "Connected", elapsed
        except Exception as e:
            return False, str(e), 0


class MarketDataCache:
    """Cache for market data to reduce API calls"""

    def __init__(self, ttl: int = 5):
        """
        Args:
            ttl: Time to live in seconds
        """
        self.ttl = ttl
        self._cache: Dict[str, tuple] = {}  # key -> (data, timestamp)

    def get(self, key: str) -> Optional[Any]:
        """Get cached data if not expired"""
        if key in self._cache:
            data, timestamp = self._cache[key]
            if time.time() - timestamp < self.ttl:
                return data
            del self._cache[key]
        return None

    def set(self, key: str, data: Any):
        """Store data in cache"""
        self._cache[key] = (data, time.time())

    def clear(self):
        """Clear all cached data"""
        self._cache.clear()


# Utility functions
def parse_price(price_str: str) -> List[float]:
    """Parse price string to list of floats"""
    try:
        if isinstance(price_str, str):
            prices = json.loads(price_str)
        else:
            prices = price_str
        return [float(p) for p in prices] if isinstance(prices, list) else []
    except:
        return []


def parse_outcomes(outcomes_str: str) -> List[str]:
    """Parse outcomes string to list"""
    try:
        if isinstance(outcomes_str, str):
            outcomes = json.loads(outcomes_str)
        else:
            outcomes = outcomes_str
        return outcomes if isinstance(outcomes, list) else []
    except:
        return []


def calculate_spread(prices: List[float]) -> float:
    """Calculate bid-ask spread from prices"""
    if len(prices) >= 2:
        # Assuming prices[0] is Yes, prices[1] is No
        # Spread = |1 - (Yes + No)|
        return abs(1.0 - sum(prices[:2]))
    return 0.0
