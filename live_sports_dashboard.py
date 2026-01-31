"""
Live Sports Dashboard - Polymarket
Shows LIVE games being played RIGHT NOW and upcoming games
Times shown in Chinese Standard Time (UTC+8)

Uses Polymarket Sports API:
- live=true: Games currently being played
- Upcoming: Games starting within 24 hours
"""

import streamlit as st
import pandas as pd
import requests
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Optional, Tuple
import json

# Chinese timezone (UTC+8)
CHINA_TZ_OFFSET = timedelta(hours=8)
API_BASE_URL = "https://gamma-api.polymarket.com"


def to_china_time(dt: datetime) -> datetime:
    """Convert UTC datetime to Chinese time (UTC+8)"""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt + CHINA_TZ_OFFSET


def format_china_time(dt: datetime) -> str:
    """Format datetime in Chinese time"""
    china_dt = to_china_time(dt)
    return china_dt.strftime("%Y-%m-%d %H:%M CST")


def parse_date(date_str: str) -> Optional[datetime]:
    """Parse date string to datetime"""
    if not date_str:
        return None
    try:
        if 'T' in date_str:
            return datetime.fromisoformat(date_str.replace('Z', '+00:00'))
        else:
            return datetime.fromisoformat(date_str + 'T00:00:00+00:00')
    except (ValueError, TypeError):
        return None


def format_currency(value) -> str:
    """Format currency value"""
    try:
        val = float(value) if value else 0
        if val >= 1_000_000:
            return f"${val/1_000_000:.2f}M"
        elif val >= 1_000:
            return f"${val/1_000:.1f}K"
        else:
            return f"${val:.2f}"
    except:
        return "$0"


def format_time_until(dt: datetime) -> str:
    """Format time until event starts"""
    now = datetime.now(timezone.utc)
    diff = dt - now
    hours = diff.total_seconds() / 3600

    if hours < 0:
        return "Started"
    elif hours < 1:
        return f"{int(hours * 60)} min"
    elif hours < 24:
        return f"{hours:.1f}h"
    else:
        return f"{hours / 24:.1f} days"


class PolymarketSportsAPI:
    """Client for Polymarket Sports API"""

    def __init__(self, proxy: Optional[str] = None, timeout: int = 30):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        self.timeout = timeout

        if proxy:
            self.session.proxies = {'http': proxy, 'https': proxy}

    def get_live_events(self) -> tuple:
        """
        Fetch events that are LIVE (games being played right now)
        Returns: (active_games, suspended_games)
        - active_games: Games actively being played
        - suspended_games: Games on break/halftime (period=SUS)
        """
        try:
            r = self.session.get(f"{API_BASE_URL}/events", params={
                'live': 'true',
                'active': 'true',
                'closed': 'false',
                'limit': 100
            }, timeout=self.timeout)
            r.raise_for_status()
            events = r.json() if isinstance(r.json(), list) else []

            # Separate active games from suspended ones
            active_games = []
            suspended_games = []

            for event in events:
                period = event.get('period', '')
                ended = event.get('ended', False)

                # Skip ended games
                if ended:
                    continue

                # Suspended = halftime, break, pause
                if period in ['SUS', 'HT', 'BT', 'SUSP', 'BREAK']:
                    suspended_games.append(event)
                else:
                    active_games.append(event)

            return active_games, suspended_games
        except Exception as e:
            st.error(f"Error fetching live events: {e}")
            return [], []

    def get_upcoming_events(self, hours_ahead: int = 24) -> List[Dict]:
        """Fetch upcoming game events (not live yet, starting soon)"""
        try:
            r = self.session.get(f"{API_BASE_URL}/events", params={
                'tag_id': '100639',  # Games tag (excludes futures/season markets)
                'active': 'true',
                'closed': 'false',
                'live': 'false',
                'limit': 100,
                'order': 'startDate',
                'ascending': 'true'
            }, timeout=self.timeout)
            r.raise_for_status()
            events = r.json() if isinstance(r.json(), list) else []

            # Filter to only events starting within hours_ahead
            now = datetime.now(timezone.utc)
            cutoff = now + timedelta(hours=hours_ahead)

            upcoming = []
            for event in events:
                start_dt = parse_date(event.get('startDate', ''))
                if start_dt and now < start_dt <= cutoff:
                    upcoming.append(event)

            return upcoming
        except Exception as e:
            st.error(f"Error fetching upcoming events: {e}")
            return []

    def get_sports_leagues(self) -> List[Dict]:
        """Fetch available sports/leagues"""
        try:
            r = self.session.get(f"{API_BASE_URL}/sports", timeout=self.timeout)
            r.raise_for_status()
            return r.json() if isinstance(r.json(), list) else []
        except Exception as e:
            return []

    def test_connection(self) -> Tuple[bool, str]:
        """Test API connection"""
        try:
            r = self.session.get(f"{API_BASE_URL}/events", params={'limit': 1}, timeout=10)
            r.raise_for_status()
            return True, "Connected"
        except Exception as e:
            return False, str(e)


def render_live_event_card(event: Dict):
    """Render a LIVE event card with score and real-time info"""
    title = event.get('title', 'Unknown Event')
    score = event.get('score', 'N/A')
    period = event.get('period', '')
    elapsed = event.get('elapsed', '')

    # Build status line
    status_parts = []
    if score and score != 'N/A':
        status_parts.append(f"**Score: {score}**")
    if period:
        status_parts.append(f"Period: {period}")
    if elapsed:
        status_parts.append(f"Time: {elapsed}")

    status_line = " | ".join(status_parts) if status_parts else "Live"

    with st.container():
        # Header with live badge
        col1, col2 = st.columns([4, 1])
        with col1:
            st.markdown(f"### 🔴 {title}")
        with col2:
            st.markdown("**LIVE**")

        # Score and status
        st.markdown(status_line)

        # Stats row
        stat_cols = st.columns(3)
        with stat_cols[0]:
            st.metric("Volume", format_currency(event.get('volume', 0)))
        with stat_cols[1]:
            st.metric("Liquidity", format_currency(event.get('liquidity', 0)))
        with stat_cols[2]:
            st.metric("Markets", len(event.get('markets', [])))

        # Markets
        markets = event.get('markets', [])
        if markets:
            st.markdown("**Markets:**")
            for market in markets:
                render_market_row(market)

        st.divider()


def render_suspended_event_card(event: Dict):
    """Render a suspended/halftime event card"""
    title = event.get('title', 'Unknown Event')
    score = event.get('score', 'N/A')
    period = event.get('period', 'SUS')

    # Period display
    period_display = {
        'SUS': 'Suspended',
        'HT': 'Halftime',
        'BT': 'Break Time',
        'SUSP': 'Suspended',
        'BREAK': 'Break'
    }.get(period, period)

    with st.container():
        col1, col2 = st.columns([4, 1])
        with col1:
            st.markdown(f"### ⏸️ {title}")
        with col2:
            st.markdown(f"**{period_display}**")

        # Score
        if score and score != 'N/A':
            st.markdown(f"**Current Score: {score}**")

        # Stats row
        stat_cols = st.columns(3)
        with stat_cols[0]:
            st.metric("Volume", format_currency(event.get('volume', 0)))
        with stat_cols[1]:
            st.metric("Liquidity", format_currency(event.get('liquidity', 0)))
        with stat_cols[2]:
            st.metric("Markets", len(event.get('markets', [])))

        # Markets (collapsed)
        markets = event.get('markets', [])
        if markets:
            with st.expander(f"View {len(markets)} Markets"):
                for market in markets:
                    render_market_row(market)

        st.divider()


def render_upcoming_event_card(event: Dict):
    """Render an upcoming event card"""
    title = event.get('title', 'Unknown Event')
    start_dt = parse_date(event.get('startDate', ''))

    time_until = format_time_until(start_dt) if start_dt else "N/A"
    start_cst = format_china_time(start_dt) if start_dt else "N/A"

    with st.container():
        col1, col2 = st.columns([4, 1])
        with col1:
            st.markdown(f"### ⏰ {title}")
        with col2:
            st.markdown(f"**{time_until}**")

        st.caption(f"Starts: {start_cst}")

        # Stats row
        stat_cols = st.columns(3)
        with stat_cols[0]:
            st.metric("Volume", format_currency(event.get('volume', 0)))
        with stat_cols[1]:
            st.metric("Liquidity", format_currency(event.get('liquidity', 0)))
        with stat_cols[2]:
            st.metric("Markets", len(event.get('markets', [])))

        # Markets (collapsed by default)
        markets = event.get('markets', [])
        if markets:
            with st.expander(f"View {len(markets)} Markets"):
                for market in markets:
                    render_market_row(market)

        st.divider()


def render_market_row(market: Dict):
    """Render a single market row with outcomes and prices"""
    question = market.get('question', 'N/A')

    # Parse outcomes and prices
    try:
        outcomes = json.loads(market.get('outcomes', '[]')) if isinstance(market.get('outcomes'), str) else market.get('outcomes', [])
        prices = json.loads(market.get('outcomePrices', '[]')) if isinstance(market.get('outcomePrices'), str) else market.get('outcomePrices', [])
    except:
        outcomes = ['Yes', 'No']
        prices = [0.5, 0.5]

    # Create outcome strings with prices
    outcome_strs = []
    for outcome, price in zip(outcomes or [], prices or []):
        try:
            pct = float(price) * 100
            outcome_strs.append(f"{outcome}: {pct:.1f}%")
        except:
            outcome_strs.append(f"{outcome}: N/A")

    outcomes_display = " vs ".join(outcome_strs) if outcome_strs else "N/A"
    volume = format_currency(market.get('volume', 0))

    st.markdown(f"- **{question}**")
    st.caption(f"  {outcomes_display} | Volume: {volume}")


@st.cache_data(ttl=60)  # Cache for 1 minute (live data needs frequent refresh)
def fetch_data(proxy: Optional[str] = None, hours_ahead: int = 24):
    """Fetch all data with caching"""
    api = PolymarketSportsAPI(proxy=proxy)

    # Test connection
    connected, msg = api.test_connection()
    if not connected:
        return None, None, None, msg

    active_games, suspended_games = api.get_live_events()
    upcoming_events = api.get_upcoming_events(hours_ahead=hours_ahead)

    return active_games, suspended_games, upcoming_events, None


def main():
    st.set_page_config(
        page_title="Live Sports - Polymarket",
        page_icon="🏆",
        layout="wide",
        initial_sidebar_state="expanded"
    )

    # Custom CSS for better styling
    st.markdown("""
    <style>
    .live-badge {
        background-color: #ff4b4b;
        color: white;
        padding: 4px 12px;
        border-radius: 12px;
        font-weight: bold;
        font-size: 14px;
    }
    .stMetric {
        background-color: #f8f9fa;
        padding: 8px;
        border-radius: 8px;
    }
    </style>
    """, unsafe_allow_html=True)

    # Header
    st.title("🏆 Polymarket Live Sports")
    st.caption("Real-time sports betting markets | All times in Chinese Standard Time (CST/UTC+8)")

    # Sidebar
    with st.sidebar:
        st.header("⚙️ Settings")

        hours_ahead = st.slider(
            "Upcoming Window (hours)",
            min_value=6,
            max_value=72,
            value=24,
            step=6,
            help="Show games starting within this time window"
        )

        proxy = st.text_input(
            "Proxy URL (optional)",
            placeholder="http://127.0.0.1:7890",
            help="Enter proxy if needed for network access"
        )

        if st.button("🔄 Refresh Now", use_container_width=True):
            st.cache_data.clear()
            st.rerun()

        st.divider()

        # Current time display
        now_utc = datetime.now(timezone.utc)
        now_china = to_china_time(now_utc)
        st.markdown("**Current Time (CST):**")
        st.info(now_china.strftime("%Y-%m-%d %H:%M:%S"))

        st.divider()
        st.caption("🔄 Auto-refresh: Every 60 seconds")
        st.caption("📡 Data: Polymarket Sports API")
        st.caption(f"⏰ Showing: Live + Next {hours_ahead}h")

    # Main content
    with st.spinner("Fetching live sports data..."):
        active_games, suspended_games, upcoming_events, error = fetch_data(
            proxy=proxy if proxy else None,
            hours_ahead=hours_ahead
        )

    if error:
        st.error(f"Connection Error: {error}")
        st.info("Try using a proxy or check your network connection.")
        return

    # Combine for total count
    all_live = (active_games or []) + (suspended_games or [])

    # Summary metrics
    st.markdown("---")
    metric_cols = st.columns(5)
    with metric_cols[0]:
        st.metric("🔴 Playing Now", len(active_games or []))
    with metric_cols[1]:
        st.metric("⏸️ Halftime/Break", len(suspended_games or []))
    with metric_cols[2]:
        st.metric("⏰ Upcoming", len(upcoming_events or []))
    with metric_cols[3]:
        total_volume = sum(float(e.get('volume', 0) or 0) for e in all_live)
        st.metric("Live Volume", format_currency(total_volume))
    with metric_cols[4]:
        total_markets = sum(len(e.get('markets', [])) for e in (active_games or []))
        st.metric("Active Markets", total_markets)

    st.markdown("---")

    # Tabs
    tab1, tab2, tab3, tab4 = st.tabs(["🔴 PLAYING NOW", "⏸️ HALFTIME/BREAK", "⏰ UPCOMING", "📊 SUMMARY"])

    with tab1:
        st.subheader(f"🔴 Games In Play ({len(active_games or [])})")
        st.caption("Games being played RIGHT NOW (not on break)")

        if active_games:
            for event in active_games:
                render_live_event_card(event)
        else:
            st.info("No games are actively playing at the moment.")
            if suspended_games:
                st.markdown("**Some games are on break/halftime** — check the Halftime/Break tab.")
            if upcoming_events:
                st.markdown("### Next Up:")
                next_event = upcoming_events[0]
                start_dt = parse_date(next_event.get('startDate', ''))
                if start_dt:
                    st.markdown(f"**{next_event.get('title')}** starts in **{format_time_until(start_dt)}**")

    with tab2:
        st.subheader(f"⏸️ Halftime / Break ({len(suspended_games or [])})")
        st.caption("Games currently on break, halftime, or suspended")

        if suspended_games:
            for event in suspended_games:
                render_suspended_event_card(event)
        else:
            st.info("No games on break at the moment.")

    with tab3:
        st.subheader(f"⏰ Upcoming Games ({len(upcoming_events or [])})")
        st.caption(f"Games starting within the next {hours_ahead} hours")

        if upcoming_events:
            for event in upcoming_events:
                render_upcoming_event_card(event)
        else:
            st.info(f"No games scheduled in the next {hours_ahead} hours.")

    with tab4:
        st.subheader("📊 Summary Table")

        all_events = (active_games or []) + (suspended_games or []) + (upcoming_events or [])

        if all_events:
            table_data = []
            for event in all_events:
                is_live = event.get('live', False)
                period = event.get('period', '')
                start_dt = parse_date(event.get('startDate', ''))

                # Determine status
                if is_live and period in ['SUS', 'HT', 'BT', 'SUSP', 'BREAK']:
                    status = "⏸️ Break"
                elif is_live:
                    status = "🔴 Playing"
                else:
                    status = "⏰ Upcoming"

                table_data.append({
                    "Status": status,
                    "Event": event.get('title', 'N/A')[:60],
                    "Score": event.get('score', '-') if is_live else '-',
                    "Period": period if is_live else '-',
                    "Start (CST)": format_china_time(start_dt) if start_dt else "N/A",
                    "Volume": format_currency(event.get('volume', 0)),
                    "Markets": len(event.get('markets', []))
                })

            df = pd.DataFrame(table_data)
            st.dataframe(df, use_container_width=True, hide_index=True)

            # Export
            if st.button("📥 Export to CSV"):
                csv = df.to_csv(index=False)
                st.download_button(
                    label="Download CSV",
                    data=csv,
                    file_name=f"polymarket_sports_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
                    mime="text/csv"
                )
        else:
            st.info("No events to display.")


if __name__ == "__main__":
    main()
