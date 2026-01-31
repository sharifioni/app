"""
Real-time Momentum Trading Dashboard
Live monitoring with WebSocket streaming and visualization
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime, timezone, timedelta
import time
import json
from typing import Dict, List, Optional
import threading
from collections import deque

# Add parent directory to path
import sys
import os

# Get the project root (two levels up from dashboard)
dashboard_dir = os.path.dirname(os.path.abspath(__file__))
momentum_trader_dir = os.path.dirname(dashboard_dir)
project_root = os.path.dirname(momentum_trader_dir)

# Add project root to path
sys.path.insert(0, project_root)

from momentum_trader.api import GammaAPI, WebSocketClient, PriceUpdate
from momentum_trader.filters import EventFilter
from momentum_trader.config import config


# Load translations
def load_translations(lang: str) -> Dict:
    """Load translation file for given language"""
    locale_path = os.path.join(dashboard_dir, "locales", f"{lang}.json")
    try:
        with open(locale_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        # Fallback to English
        en_path = os.path.join(dashboard_dir, "locales", "en.json")
        with open(en_path, "r", encoding="utf-8") as f:
            return json.load(f)


def t(translations: Dict, section: str, key: str) -> str:
    """Get translated text"""
    return translations.get(section, {}).get(key, key)


# Global state for real-time data
class RealtimeState:
    """Thread-safe state for real-time data"""
    def __init__(self):
        self.price_history: Dict[str, deque] = {}  # token_id -> deque of (timestamp, price)
        self.volume_history: Dict[str, deque] = {}  # token_id -> deque of (timestamp, volume)
        self.events: Dict[str, Dict] = {}  # event_id -> event data
        self.qualified_events: List = []
        self.ws_connected = False
        self.last_update = time.time()
        self.momentum_signals: List[Dict] = []

        # Keep last 300 data points (5 minutes at 1 update/sec)
        self.max_history = 300

    def add_price(self, token_id: str, price: float):
        """Add price data point"""
        if token_id not in self.price_history:
            self.price_history[token_id] = deque(maxlen=self.max_history)
        self.price_history[token_id].append((time.time(), price))
        self.last_update = time.time()

    def get_price_series(self, token_id: str, last_n_seconds: int = 60) -> tuple:
        """Get price series for last N seconds"""
        if token_id not in self.price_history:
            return [], []

        cutoff = time.time() - last_n_seconds
        data = [(t, p) for t, p in self.price_history[token_id] if t > cutoff]

        if not data:
            return [], []

        timestamps = [datetime.fromtimestamp(t) for t, _ in data]
        prices = [p for _, p in data]
        return timestamps, prices

    def detect_momentum(self, token_id: str) -> Optional[Dict]:
        """Detect momentum in price movement"""
        if token_id not in self.price_history or len(self.price_history[token_id]) < 20:
            return None

        recent = list(self.price_history[token_id])[-20:]  # Last 20 seconds
        baseline = list(self.price_history[token_id])[-60:-20] if len(self.price_history[token_id]) >= 60 else recent[:20]

        if not baseline:
            return None

        baseline_price = sum(p for _, p in baseline) / len(baseline)
        current_price = recent[-1][1]

        price_change = (current_price - baseline_price) / baseline_price

        # Momentum threshold: 2% rise
        if price_change >= 0.02:
            return {
                'token_id': token_id,
                'baseline_price': baseline_price,
                'current_price': current_price,
                'price_change_pct': price_change * 100,
                'detected_at': time.time(),
                'signal_strength': 'STRONG' if price_change >= 0.05 else 'MEDIUM' if price_change >= 0.03 else 'WEAK'
            }

        return None


# Initialize state
if 'realtime_state' not in st.session_state:
    st.session_state.realtime_state = RealtimeState()

# Initialize WebSocket client (only once)
if 'websocket_client' not in st.session_state:
    st.session_state.websocket_client = None

# Initialize language
if 'language' not in st.session_state:
    st.session_state.language = 'en'


def format_currency(value: float) -> str:
    """Format currency"""
    if value >= 1_000_000:
        return f"${value/1_000_000:.2f}M"
    elif value >= 1_000:
        return f"${value/1_000:.1f}K"
    else:
        return f"${value:.2f}"


def create_price_chart(token_id: str, title: str, state: RealtimeState) -> go.Figure:
    """Create real-time price chart"""
    timestamps, prices = state.get_price_series(token_id, last_n_seconds=60)

    if not timestamps:
        # Empty chart
        fig = go.Figure()
        fig.add_annotation(
            text="Waiting for data...",
            xref="paper", yref="paper",
            x=0.5, y=0.5, showarrow=False,
            font=dict(size=16, color="gray")
        )
        fig.update_layout(
            title=title,
            height=200,
            margin=dict(l=20, r=20, t=40, b=20),
            xaxis=dict(visible=False),
            yaxis=dict(visible=False)
        )
        return fig

    # Calculate momentum
    if len(prices) >= 10:
        baseline = prices[-30:-10] if len(prices) >= 30 else prices[:10]
        baseline_avg = sum(baseline) / len(baseline)
        current = prices[-1]
        momentum_pct = ((current - baseline_avg) / baseline_avg) * 100

        color = 'green' if momentum_pct > 0 else 'red'
    else:
        momentum_pct = 0
        color = 'blue'

    fig = go.Figure()

    # Price line
    fig.add_trace(go.Scatter(
        x=timestamps,
        y=prices,
        mode='lines',
        name='Price',
        line=dict(color=color, width=2),
        fill='tozeroy',
        fillcolor=f'rgba({"0,255,0" if momentum_pct > 0 else "255,0,0"}, 0.1)'
    ))

    # Baseline average
    if len(prices) >= 20:
        baseline_avg = sum(prices[-40:-20]) / 20 if len(prices) >= 40 else sum(prices[:20]) / 20
        fig.add_hline(
            y=baseline_avg,
            line_dash="dash",
            line_color="orange",
            annotation_text=f"Baseline: {baseline_avg:.3f}",
            annotation_position="right"
        )

    fig.update_layout(
        title=f"{title} ({momentum_pct:+.1f}%)",
        height=200,
        margin=dict(l=20, r=20, t=40, b=20),
        xaxis=dict(title="Time", showgrid=True),
        yaxis=dict(title="Price", showgrid=True, tickformat='.3f'),
        hovermode='x unified',
        showlegend=False
    )

    return fig


@st.cache_resource
def initialize_api():
    """Initialize API clients"""
    gamma_api = GammaAPI(proxy=config.api.proxy)
    return gamma_api


def initialize_websocket():
    """Initialize and start WebSocket client for price updates"""
    if st.session_state.websocket_client is None:
        # Get reference to state object BEFORE creating callbacks
        # This avoids accessing st.session_state from the WebSocket thread
        state = st.session_state.realtime_state

        def on_price_update(update: PriceUpdate):
            """Handle price updates - uses captured state reference"""
            try:
                state.add_price(update.token_id, update.price)
                state.ws_connected = True

                # Check for momentum
                signal = state.detect_momentum(update.token_id)
                if signal:
                    state.momentum_signals.append(signal)
                    if len(state.momentum_signals) > 50:
                        state.momentum_signals = state.momentum_signals[-50:]
            except Exception as e:
                # Silently handle errors in callback thread
                pass

        def on_error(error_msg: str):
            """Handle errors - uses captured state reference"""
            try:
                state.ws_connected = False
            except Exception:
                pass

        # Create WebSocket client
        ws_client = WebSocketClient(
            on_price_update=on_price_update,
            on_error=on_error
        )

        # Start the client
        ws_client.start()

        st.session_state.websocket_client = ws_client

    return st.session_state.websocket_client


def main():
    st.set_page_config(
        page_title="Momentum Trader - Live",
        page_icon="📈",
        layout="wide",
        initial_sidebar_state="expanded"
    )

    # Load translations
    translations = load_translations(st.session_state.language)

    # Custom CSS for real-time dashboard
    st.markdown("""
    <style>
    .big-metric {
        font-size: 24px;
        font-weight: bold;
        color: #1f77b4;
    }
    .momentum-signal {
        padding: 10px;
        border-radius: 5px;
        margin: 5px 0;
        animation: pulse 2s infinite;
    }
    .signal-strong {
        background-color: #ff4444;
        color: white;
    }
    .signal-medium {
        background-color: #ffaa00;
        color: white;
    }
    .signal-weak {
        background-color: #44ff44;
        color: white;
    }
    @keyframes pulse {
        0%, 100% { opacity: 1; }
        50% { opacity: 0.7; }
    }
    </style>
    """, unsafe_allow_html=True)

    # Header
    col1, col2, col3 = st.columns([2, 1, 1])
    with col1:
        st.title(f"📈 {t(translations, 'realtime', 'title')}")
    with col2:
        now = datetime.now()
        st.metric(t(translations, 'common', 'current_time'), now.strftime("%H:%M:%S"))
    with col3:
        state = st.session_state.realtime_state
        time_since_update = time.time() - state.last_update
        status = f"🟢 {t(translations, 'common', 'live')}" if time_since_update < 5 else f"🔴 {t(translations, 'common', 'stale')}"
        st.metric(t(translations, 'common', 'status'), status)

    # Sidebar controls
    with st.sidebar:
        st.header(f"⚙️ {t(translations, 'common', 'settings')}")

        # Language selector
        lang_options = {"English": "en", "中文": "zh"}
        current_lang_name = "中文" if st.session_state.language == "zh" else "English"
        selected_lang = st.selectbox(
            t(translations, 'common', 'language'),
            options=list(lang_options.keys()),
            index=list(lang_options.keys()).index(current_lang_name)
        )
        if lang_options[selected_lang] != st.session_state.language:
            st.session_state.language = lang_options[selected_lang]
            st.rerun()

        st.divider()

        auto_refresh = st.checkbox(t(translations, 'common', 'auto_refresh'), value=True)

        st.divider()

        proxy = st.text_input(t(translations, 'realtime', 'proxy_url'), placeholder="http://127.0.0.1:7890")

        if st.button(f"🔄 {t(translations, 'common', 'refresh_data')}", use_container_width=True):
            st.cache_data.clear()
            st.rerun()

        st.divider()

        st.subheader(t(translations, 'realtime', 'websocket_status'))
        state = st.session_state.realtime_state
        ws_client = st.session_state.websocket_client

        ws_status = f"🟢 {t(translations, 'realtime', 'connected')}" if state.ws_connected else f"🔴 {t(translations, 'realtime', 'disconnected')}"
        st.write(ws_status)

        # Show WebSocket stats
        if ws_client:
            subscribed_count = len(ws_client.subscribed_tokens)
            st.write(f"{t(translations, 'realtime', 'subscribed_tokens')}: {subscribed_count}")
            st.write(f"{t(translations, 'realtime', 'price_data_received')}: {len(state.price_history)}")
        else:
            st.write(f"{t(translations, 'realtime', 'tracked_tokens')}: 0")

        st.write(f"{t(translations, 'realtime', 'last_update')}: {time_since_update:.1f}{t(translations, 'realtime', 'seconds_ago')}")

        st.divider()

        st.caption(f"🔄 {t(translations, 'realtime', 'dashboard_refresh_note')}")
        st.caption(f"📊 {t(translations, 'realtime', 'shows_last_60s')}")
        st.caption(f"⚡ {t(translations, 'realtime', 'detects_momentum')}")

    # Initialize API
    gamma_api = initialize_api()

    # Fetch live events (cached for 5 seconds)
    @st.cache_data(ttl=5)
    def fetch_live_events():
        return gamma_api.get_live_events()

    with st.spinner(t(translations, 'realtime', 'fetching_events')):
        live_events = fetch_live_events()

    if not live_events:
        st.warning(t(translations, 'realtime', 'no_live_events'))
        return

    # Filter events
    event_filter = EventFilter(gamma_api, config)
    qualified = event_filter.filter_and_score_events(live_events)

    # Update state
    state = st.session_state.realtime_state
    state.qualified_events = qualified

    # Initialize WebSocket and subscribe to tokens
    ws_client = initialize_websocket()

    # Collect all token IDs from qualified events
    token_ids = []
    for event_score in qualified:
        event_data = next((e for e in live_events if e.get('id') == event_score.event_id), None)
        if event_data:
            markets = event_data.get('markets', [])
            for market in markets:
                clob_token_ids_raw = market.get('clobTokenIds', '[]')
                # Parse JSON string to list if needed
                try:
                    clob_token_ids = json.loads(clob_token_ids_raw) if isinstance(clob_token_ids_raw, str) else clob_token_ids_raw
                except json.JSONDecodeError:
                    clob_token_ids = []
                if clob_token_ids:
                    token_ids.extend([str(tid) for tid in clob_token_ids if tid])

    # Subscribe to all tokens (only if new tokens detected)
    if token_ids and ws_client:
        current_subscriptions = set(ws_client.subscribed_tokens)
        new_tokens = [tid for tid in token_ids if tid not in current_subscriptions]

        if new_tokens:
            ws_client.subscribe_many(new_tokens)

        state.ws_connected = ws_client.is_connected

    # Debug info (temporary)
    with st.sidebar:
        with st.expander(t(translations, 'common', 'debug_info')):
            st.write(f"{t(translations, 'realtime', 'token_ids_collected')}: {len(token_ids)}")
            st.write(f"{t(translations, 'realtime', 'websocket_running')}: {ws_client.is_connected if ws_client else False}")
            if token_ids:
                st.write(f"{t(translations, 'realtime', 'first_token')}: {token_ids[0][:20]}...")

    # Summary metrics
    st.markdown("---")
    metric_cols = st.columns(5)
    with metric_cols[0]:
        st.metric(t(translations, 'realtime', 'live_events'), len(live_events))
    with metric_cols[1]:
        st.metric(t(translations, 'realtime', 'qualified'), len(qualified))
    with metric_cols[2]:
        total_volume = sum(e.volume_24h for e in qualified)
        st.metric(t(translations, 'realtime', 'total_volume'), format_currency(total_volume))
    with metric_cols[3]:
        st.metric(t(translations, 'realtime', 'momentum_signals'), len(state.momentum_signals))
    with metric_cols[4]:
        avg_score = sum(e.total_score for e in qualified) / len(qualified) if qualified else 0
        st.metric(t(translations, 'realtime', 'avg_score'), f"{avg_score:.1f}")

    st.markdown("---")

    # Main content area
    tab1, tab2, tab3 = st.tabs([f"📊 {t(translations, 'realtime', 'live_charts')}", f"🎯 {t(translations, 'realtime', 'momentum_signals')}", f"📋 {t(translations, 'realtime', 'qualified_events')}"])

    with tab1:
        st.subheader(t(translations, 'realtime', 'realtime_price_monitoring'))
        st.caption(t(translations, 'realtime', 'charts_update_note'))

        if not qualified:
            st.info(t(translations, 'realtime', 'no_qualified_events'))
        else:
            # Show top 6 events with real-time charts
            for i, event_score in enumerate(qualified[:6]):
                st.markdown(f"### {i+1}. {event_score.title}")

                # Find event data
                event_data = next((e for e in live_events if e.get('id') == event_score.event_id), None)
                if not event_data:
                    continue

                # Get markets
                markets = event_data.get('markets', [])[:2]  # Show first 2 markets

                if markets:
                    chart_cols = st.columns(len(markets))

                    for market_idx, (col, market) in enumerate(zip(chart_cols, markets)):
                        with col:
                            question = market.get('question', 'N/A')[:50]
                            clob_ids_raw = market.get('clobTokenIds', '[]')
                            # Parse JSON string to list if needed
                            try:
                                clob_ids = json.loads(clob_ids_raw) if isinstance(clob_ids_raw, str) else clob_ids_raw
                            except json.JSONDecodeError:
                                clob_ids = []
                            token_id = str(clob_ids[0]) if clob_ids and clob_ids[0] else f'unknown_{i}_{market_idx}'

                            # Create unique key using event index, market index, and token
                            chart_key = f"chart_{i}_{market_idx}_{token_id[:20]}"

                            # Create price chart
                            fig = create_price_chart(token_id, question, state)
                            st.plotly_chart(fig, key=chart_key)

                            # Show current price
                            timestamps, prices = state.get_price_series(token_id, 60)
                            if prices:
                                current_price = prices[-1]
                                price_change = ((prices[-1] - prices[0]) / prices[0] * 100) if len(prices) > 1 else 0
                                st.metric(
                                    t(translations, 'realtime', 'current_price'),
                                    f"{current_price:.3f}",
                                    f"{price_change:+.2f}%"
                                )

                st.divider()

    with tab2:
        st.subheader(f"🎯 {t(translations, 'realtime', 'signals_detected')}")
        st.caption(t(translations, 'realtime', 'signals_trigger_note'))

        if not state.momentum_signals:
            st.info(t(translations, 'realtime', 'no_signals_yet'))
        else:
            # Show recent signals
            for signal in reversed(state.momentum_signals[-10:]):  # Last 10 signals
                strength = signal['signal_strength']
                strength_class = f"signal-{strength.lower()}"

                # Get translated signal strength
                signal_text = t(translations, 'realtime', f'signal_{strength.lower()}')

                detected_time = datetime.fromtimestamp(signal['detected_at'])
                time_ago = int(time.time() - signal['detected_at'])

                st.markdown(f"""
                <div class="momentum-signal {strength_class}">
                    <strong>{signal_text}</strong><br>
                    {t(translations, 'realtime', 'price')}: {signal['baseline_price']:.3f} → {signal['current_price']:.3f}
                    ({signal['price_change_pct']:+.2f}%)<br>
                    {t(translations, 'realtime', 'detected')}: {detected_time.strftime('%H:%M:%S')} ({time_ago}{t(translations, 'realtime', 'seconds_ago')})
                </div>
                """, unsafe_allow_html=True)

    with tab3:
        st.subheader(f"📋 {t(translations, 'realtime', 'qualified_events_trading')}")

        if not qualified:
            st.info(t(translations, 'realtime', 'no_events_criteria'))
        else:
            # Create table
            table_data = []
            for event_score in qualified:
                table_data.append({
                    t(translations, 'realtime', 'rank'): f"#{qualified.index(event_score) + 1}",
                    t(translations, 'realtime', 'event'): event_score.title[:60],
                    t(translations, 'realtime', 'score'): f"{event_score.total_score:.1f}",
                    t(translations, 'realtime', 'volume'): format_currency(event_score.volume_24h),
                    t(translations, 'realtime', 'liquidity'): format_currency(event_score.liquidity),
                    t(translations, 'realtime', 'spread'): f"{event_score.spread:.2%}",
                    t(translations, 'realtime', 'markets'): event_score.markets_count,
                    t(translations, 'common', 'status'): event_score.period
                })

            df = pd.DataFrame(table_data)
            st.dataframe(df, use_container_width=True, hide_index=True)

    # Auto-refresh
    if auto_refresh:
        time.sleep(1)
        st.rerun()


if __name__ == "__main__":
    main()
