"""
Paper Trading Dashboard
Test momentum strategy with fake money using real market data
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime, timedelta
import time
import json
from typing import Dict, List
import threading
from collections import deque
import atexit

# Add parent directory to path
import sys
import os

dashboard_dir = os.path.dirname(os.path.abspath(__file__))
momentum_trader_dir = os.path.dirname(dashboard_dir)
project_root = os.path.dirname(momentum_trader_dir)
sys.path.insert(0, project_root)

from momentum_trader.api import GammaAPI, WebSocketClient, PriceUpdate
from momentum_trader.filters import EventFilter
from momentum_trader.config import config
from momentum_trader.trading import PaperTrader, TestOrder, Position, Trade, SignalStrength, AsyncDataLogger


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


class PaperTradingState:
    """Thread-safe state for paper trading"""

    def __init__(self):
        self.price_history: Dict[str, deque] = {}
        self.volume_history: Dict[str, deque] = {}
        self.ws_connected = False
        self.last_update = time.time()
        self.max_history = 300

        # Paper trader instance
        self.paper_trader: PaperTrader = None

        # Data logger for CSV export
        self.data_logger: AsyncDataLogger = None

        # Signal log
        self.signal_log: List[Dict] = []
        self.trade_log: List[Dict] = []

        # Token to event mapping
        self.token_to_event: Dict[str, Dict] = {}

        # Session start time
        self.session_start = time.time()

    def add_price(self, token_id: str, price: float, volume: float = 0.0, ws_received_time: float = 0.0):
        """Add price update and forward to paper trader"""
        now = time.time()
        if ws_received_time == 0.0:
            ws_received_time = now

        if token_id not in self.price_history:
            self.price_history[token_id] = deque(maxlen=self.max_history)
        self.price_history[token_id].append((now, price))

        if volume > 0:
            if token_id not in self.volume_history:
                self.volume_history[token_id] = deque(maxlen=self.max_history)
            self.volume_history[token_id].append((now, volume))

        self.last_update = now

        # Get event info for logging
        event_info = self.token_to_event.get(token_id, {})
        event_title = event_info.get('event', {}).get('title', '')[:50] if event_info else ''
        team = event_info.get('outcome', '')

        # Forward to paper trader with latency tracking
        if self.paper_trader:
            self.paper_trader.add_price_update(token_id, price, volume, ws_received_time)

        # Log to CSV (non-blocking)
        if self.data_logger:
            # Calculate price change if we have history
            price_change_pct = 0.0
            if token_id in self.paper_trader.test_orders if self.paper_trader else False:
                order = self.paper_trader.test_orders.get(token_id)
                if order:
                    price_change_pct = order.price_change_pct

            self.data_logger.log_price_update(
                token_id=token_id,
                price=price,
                event_title=event_title,
                team=team,
                price_change_pct=price_change_pct,
                volume=volume,
                ws_received_time=ws_received_time
            )

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

    def get_current_price(self, token_id: str) -> float:
        """Get current price for token"""
        if token_id in self.price_history and self.price_history[token_id]:
            return self.price_history[token_id][-1][1]
        return 0.0


# Initialize state
if 'paper_state' not in st.session_state:
    st.session_state.paper_state = PaperTradingState()

if 'paper_trader' not in st.session_state:
    st.session_state.paper_trader = None

if 'websocket_client' not in st.session_state:
    st.session_state.websocket_client = None

if 'trading_active' not in st.session_state:
    st.session_state.trading_active = False

# Initialize language
if 'language' not in st.session_state:
    st.session_state.language = 'en'


def format_currency(value: float) -> str:
    """Format currency"""
    if abs(value) >= 1_000_000:
        return f"${value/1_000_000:.2f}M"
    elif abs(value) >= 1_000:
        return f"${value/1_000:.1f}K"
    else:
        return f"${value:.2f}"


def format_pct(value: float) -> str:
    """Format percentage"""
    return f"{value:+.2f}%"


def create_pnl_chart(trades: List[Trade], translations: Dict = None) -> go.Figure:
    """Create cumulative P&L chart"""
    if translations is None:
        translations = load_translations('en')

    if not trades:
        fig = go.Figure()
        fig.add_annotation(
            text=t(translations, 'common', 'no_trades_yet'),
            xref="paper", yref="paper",
            x=0.5, y=0.5, showarrow=False,
            font=dict(size=16, color="gray")
        )
        fig.update_layout(height=250, margin=dict(l=20, r=20, t=40, b=20))
        return fig

    # Calculate cumulative P&L
    timestamps = [datetime.fromtimestamp(t.exit_time) for t in trades]
    cumulative_pnl = []
    running_total = 0
    for trade in trades:
        running_total += trade.pnl
        cumulative_pnl.append(running_total)

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=timestamps,
        y=cumulative_pnl,
        mode='lines+markers',
        name=t(translations, 'paper', 'cumulative_pnl'),
        line=dict(color='green' if cumulative_pnl[-1] >= 0 else 'red', width=2),
        fill='tozeroy',
        fillcolor='rgba(0,255,0,0.1)' if cumulative_pnl[-1] >= 0 else 'rgba(255,0,0,0.1)'
    ))

    fig.add_hline(y=0, line_dash="dash", line_color="gray")

    fig.update_layout(
        title=t(translations, 'paper', 'cumulative_pnl'),
        height=250,
        margin=dict(l=20, r=20, t=40, b=20),
        xaxis_title=t(translations, 'paper', 'time'),
        yaxis_title=f"{t(translations, 'paper', 'pnl')} ($)",
        showlegend=False
    )

    return fig


def create_win_rate_chart(stats, translations: Dict = None) -> go.Figure:
    """Create win rate pie chart"""
    if translations is None:
        translations = load_translations('en')

    fig = go.Figure(data=[go.Pie(
        labels=[t(translations, 'paper', 'wins'), t(translations, 'paper', 'losing_trades')],
        values=[stats.winning_trades, stats.losing_trades],
        marker_colors=['#00C853', '#FF5252'],
        hole=0.4,
        textinfo='label+value'
    )])

    fig.update_layout(
        title=f"{t(translations, 'paper', 'win_rate')}: {stats.win_rate*100:.1f}%",
        height=200,
        margin=dict(l=20, r=20, t=40, b=20),
        showlegend=False
    )

    return fig


@st.cache_resource
def initialize_api():
    """Initialize API clients"""
    gamma_api = GammaAPI(proxy=config.api.proxy)
    return gamma_api


def initialize_paper_trader():
    """Initialize paper trading engine and data logger"""
    state = st.session_state.paper_state

    # Initialize data logger for CSV export
    log_dir = os.path.join(project_root, "trading_logs")
    data_logger = AsyncDataLogger(output_dir=log_dir)
    data_logger.start()
    state.data_logger = data_logger

    # Register cleanup on exit
    def cleanup():
        if state.data_logger:
            state.data_logger.stop()
    atexit.register(cleanup)

    def on_signal_detected(test_order: TestOrder):
        state.signal_log.append({
            'time': datetime.now().strftime('%H:%M:%S'),
            'event': test_order.event_title[:40],
            'team': test_order.team,
            'price_change': f"{test_order.price_change_pct*100:.2f}%",
            'signal': test_order.signal_strength.value if test_order.signal_strength else 'N/A'
        })
        if len(state.signal_log) > 50:
            state.signal_log = state.signal_log[-50:]

        # Log signal to CSV
        if state.data_logger:
            state.data_logger.log_signal(
                token_id=test_order.token_id,
                event_title=test_order.event_title,
                team=test_order.team,
                entry_price=test_order.entry_price,
                current_price=test_order.current_price,
                price_change_pct=test_order.price_change_pct,
                volume_change_pct=test_order.volume_change_pct,
                signal_strength=test_order.signal_strength.value if test_order.signal_strength else 'N/A'
            )

    def on_trade_complete(trade: Trade):
        state.trade_log.append({
            'time': datetime.fromtimestamp(trade.exit_time).strftime('%H:%M:%S'),
            'event': trade.event_title[:30],
            'pnl': trade.pnl,
            'pnl_pct': trade.pnl_pct * 100,
            'reason': trade.exit_reason,
            'hold': f"{trade.hold_duration:.0f}s"
        })
        if len(state.trade_log) > 100:
            state.trade_log = state.trade_log[-100:]

        # Log trade to CSV
        if state.data_logger:
            state.data_logger.log_trade(
                trade_id=trade.id,
                token_id=trade.token_id,
                event_id=trade.event_id,
                event_title=trade.event_title,
                team=trade.team,
                entry_price=trade.entry_price,
                exit_price=trade.exit_price,
                quantity=trade.quantity,
                amount=trade.amount,
                pnl=trade.pnl,
                pnl_pct=trade.pnl_pct,
                exit_reason=trade.exit_reason,
                signal_strength=trade.signal_strength.value,
                hold_duration=trade.hold_duration,
                signal_latency_ms=trade.signal_latency_ms,
                execution_latency_ms=trade.execution_latency_ms
            )

    paper_trader = PaperTrader(
        initial_capital=50000.0,
        test_order_amount=5.0,
        on_signal_detected=on_signal_detected,
        on_trade_complete=on_trade_complete,
    )

    state.paper_trader = paper_trader
    st.session_state.paper_trader = paper_trader

    # Log session start info
    print(f"[Paper Trading] Session started. Logs will be saved to: {log_dir}")

    return paper_trader


def initialize_websocket():
    """Initialize WebSocket client"""
    if st.session_state.websocket_client is None:
        state = st.session_state.paper_state

        def on_price_update(update: PriceUpdate):
            try:
                ws_received_time = time.time()  # Capture receive time for latency tracking
                state.add_price(update.token_id, update.price, 0.0, ws_received_time)
                state.ws_connected = True
            except Exception:
                pass

        def on_error(error_msg: str):
            try:
                state.ws_connected = False
            except Exception:
                pass

        ws_client = WebSocketClient(
            on_price_update=on_price_update,
            on_error=on_error
        )
        ws_client.start()
        st.session_state.websocket_client = ws_client

    return st.session_state.websocket_client


def main():
    st.set_page_config(
        page_title="Paper Trading - Momentum Strategy",
        page_icon="📊",
        layout="wide",
        initial_sidebar_state="expanded"
    )

    # Load translations
    translations = load_translations(st.session_state.language)

    # Custom CSS
    st.markdown("""
    <style>
    .metric-card {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 15px;
        border-radius: 10px;
        color: white;
        margin: 5px 0;
    }
    .signal-alert {
        background-color: #FFD700;
        padding: 10px;
        border-radius: 5px;
        animation: pulse 1s infinite;
    }
    .profit { color: #00C853; font-weight: bold; }
    .loss { color: #FF5252; font-weight: bold; }
    @keyframes pulse {
        0%, 100% { opacity: 1; }
        50% { opacity: 0.7; }
    }
    </style>
    """, unsafe_allow_html=True)

    # Header
    col1, col2, col3, col4 = st.columns([2, 1, 1, 1])
    with col1:
        st.title(f"📊 {t(translations, 'paper', 'title')}")
        st.caption(t(translations, 'paper', 'subtitle'))
    with col2:
        now = datetime.now()
        st.metric(t(translations, 'paper', 'time'), now.strftime("%H:%M:%S"))
    with col3:
        state = st.session_state.paper_state
        status = f"🟢 {t(translations, 'common', 'live')}" if state.ws_connected else f"🔴 {t(translations, 'common', 'offline')}"
        st.metric(t(translations, 'common', 'status'), status)
    with col4:
        # Show session runtime
        if hasattr(state, 'session_start'):
            runtime_sec = time.time() - state.session_start
            hours = int(runtime_sec // 3600)
            mins = int((runtime_sec % 3600) // 60)
            secs = int(runtime_sec % 60)
            runtime_str = f"{hours:02d}:{mins:02d}:{secs:02d}"
        else:
            runtime_str = "00:00:00"
        st.metric(t(translations, 'paper', 'runtime'), runtime_str)

    # Sidebar
    with st.sidebar:
        st.header(f"⚙️ {t(translations, 'paper', 'paper_settings')}")

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

        # Trading controls
        st.subheader(t(translations, 'paper', 'trading_controls'))

        if st.session_state.paper_trader is None:
            if st.button(f"🚀 {t(translations, 'paper', 'start_paper_trading')}", width="stretch", type="primary"):
                initialize_paper_trader()
                st.session_state.trading_active = True
                st.rerun()
        else:
            col_a, col_b = st.columns(2)
            with col_a:
                if st.session_state.trading_active:
                    if st.button(f"⏸️ {t(translations, 'paper', 'pause')}", width="stretch"):
                        st.session_state.trading_active = False
                        st.rerun()
                else:
                    if st.button(f"▶️ {t(translations, 'paper', 'resume')}", width="stretch"):
                        st.session_state.trading_active = True
                        st.rerun()
            with col_b:
                if st.button(f"🔄 {t(translations, 'paper', 'reset')}", width="stretch"):
                    st.session_state.paper_trader = None
                    st.session_state.paper_state = PaperTradingState()
                    st.session_state.trading_active = False
                    st.rerun()

        st.divider()

        # Strategy parameters
        st.subheader(t(translations, 'paper', 'strategy_parameters'))
        st.caption(t(translations, 'paper', 'momentum_thresholds'))

        price_threshold = st.slider(t(translations, 'paper', 'price_rise_pct'), 1.0, 5.0, 2.0, 0.5)
        volume_threshold = st.slider(t(translations, 'paper', 'volume_increase_pct'), 10, 100, 30, 10)
        test_order_amt = st.slider(t(translations, 'paper', 'test_order_amount'), 2, 20, 5, 1)

        st.divider()

        # Risk settings
        st.subheader(t(translations, 'paper', 'risk_controls'))
        take_profit = st.slider(t(translations, 'paper', 'take_profit_pct'), 2, 10, 4, 1)
        stop_loss = st.slider(t(translations, 'paper', 'stop_loss_pct'), 1, 5, 2, 1)
        max_hold = st.slider(t(translations, 'paper', 'max_hold_min'), 1, 10, 5, 1)

        st.divider()

        auto_refresh = st.checkbox(t(translations, 'common', 'auto_refresh'), value=True)

        st.divider()

        # Export data
        st.subheader(f"📁 {t(translations, 'paper', 'data_export')}")
        if st.session_state.paper_trader and st.session_state.paper_state.data_logger:
            files = st.session_state.paper_state.data_logger.get_file_paths()
            st.caption(f"{t(translations, 'paper', 'session')}: {st.session_state.paper_state.data_logger.session_id}")
            if st.button(f"💾 {t(translations, 'paper', 'save_data_now')}", width="stretch"):
                st.session_state.paper_state.data_logger._flush_all_buffers()
                st.success(t(translations, 'paper', 'data_saved'))
            st.caption(f"{t(translations, 'paper', 'log_folder')}: trading_logs/")

    # Initialize API and WebSocket
    gamma_api = initialize_api()
    ws_client = initialize_websocket()

    # Fetch live events with error handling
    @st.cache_data(ttl=10)
    def fetch_live_events():
        try:
            return gamma_api.get_live_events()
        except Exception as e:
            st.warning(f"{t(translations, 'paper', 'api_connection_issue')}: {str(e)[:100]}. {t(translations, 'paper', 'retrying')}")
            return []

    live_events = fetch_live_events()

    if not live_events:
        st.warning(f"⚠️ {t(translations, 'paper', 'unable_fetch_events')}")

    # Get state
    state = st.session_state.paper_state
    paper_trader = st.session_state.paper_trader

    # Main dashboard area
    if paper_trader is None:
        st.info(f"👆 {t(translations, 'paper', 'click_start_note')}")
        st.markdown(f"""
        ### {t(translations, 'paper', 'how_it_works')}
        1. {t(translations, 'paper', 'step1')}
        2. {t(translations, 'paper', 'step2')}
        3. {t(translations, 'paper', 'step3')}
        4. {t(translations, 'paper', 'step4')}
        5. {t(translations, 'paper', 'step5')}
        """)
        return

    # Filter qualified events using EventFilter
    event_filter = EventFilter(gamma_api, config)
    qualified_events = event_filter.filter_and_score_events(live_events)

    # Build mapping of qualified event IDs to event data
    qualified_event_ids = {e.event_id for e in qualified_events}
    qualified_live_events = [e for e in live_events if e.get('id') in qualified_event_ids]

    # Subscribe to ALL tokens from ALL qualified events and ALL their markets
    if qualified_live_events and ws_client:
        token_ids = []
        token_to_event = {}  # Map token_id -> (event_data, market_data)

        for event in qualified_live_events:
            markets = event.get('markets', [])
            for market in markets:
                clob_ids_raw = market.get('clobTokenIds', '[]')
                try:
                    clob_ids = json.loads(clob_ids_raw) if isinstance(clob_ids_raw, str) else clob_ids_raw
                except json.JSONDecodeError:
                    clob_ids = []

                # Get outcomes for this market
                outcomes_raw = market.get('outcomes', '["Yes", "No"]')
                try:
                    outcomes = json.loads(outcomes_raw) if isinstance(outcomes_raw, str) else outcomes_raw
                except json.JSONDecodeError:
                    outcomes = ['Yes', 'No']

                # Subscribe to ALL tokens in this market (both sides)
                for idx, token_id in enumerate(clob_ids):
                    if token_id:
                        tid = str(token_id)
                        token_ids.append(tid)
                        outcome_name = outcomes[idx] if idx < len(outcomes) else f"Outcome {idx}"
                        token_to_event[tid] = {
                            'event': event,
                            'market': market,
                            'outcome': outcome_name,
                            'outcome_idx': idx
                        }

        # Store token mapping in state for later use
        state.token_to_event = token_to_event

        if token_ids:
            current_subs = set(ws_client.subscribed_tokens)
            new_tokens = [t for t in token_ids if t not in current_subs]
            if new_tokens:
                ws_client.subscribe_many(new_tokens)  # Subscribe to ALL tokens
                print(f"[Paper Trading] Subscribed to {len(new_tokens)} tokens from {len(qualified_live_events)} qualified events")

    # Auto-place test orders on ALL qualified events and ALL their markets
    if st.session_state.trading_active and qualified_live_events:
        for event in qualified_live_events:
            markets = event.get('markets', [])

            for market in markets:
                clob_ids_raw = market.get('clobTokenIds', '[]')
                try:
                    clob_ids = json.loads(clob_ids_raw) if isinstance(clob_ids_raw, str) else clob_ids_raw
                except json.JSONDecodeError:
                    continue

                # Get outcomes for this market
                outcomes_raw = market.get('outcomes', '["Yes", "No"]')
                try:
                    outcomes = json.loads(outcomes_raw) if isinstance(outcomes_raw, str) else outcomes_raw
                except json.JSONDecodeError:
                    outcomes = ['Yes', 'No']

                if not clob_ids:
                    continue

                # Place test orders on BOTH sides of each market
                for idx, token_id in enumerate(clob_ids):
                    if not token_id:
                        continue

                    tid = str(token_id)
                    current_price = state.get_current_price(tid)
                    outcome_name = outcomes[idx] if idx < len(outcomes) else f"Outcome {idx}"

                    if current_price > 0:
                        # Place test order if not already tracking this token
                        market_question = market.get('question', '')[:30]
                        paper_trader.place_test_order(
                            token_id=tid,
                            event_id=event.get('id', ''),
                            event_title=f"{event.get('title', 'Unknown')[:40]} - {market_question}",
                            team=outcome_name,
                            current_price=current_price,
                        )

    # Dashboard Layout
    summary = paper_trader.get_summary()

    # Coverage info
    num_qualified_events = len(qualified_live_events) if qualified_live_events else 0
    total_markets = sum(len(e.get('markets', [])) for e in qualified_live_events) if qualified_live_events else 0
    total_tokens = len(state.token_to_event)

    # Top metrics row
    st.markdown("---")

    # First row - Capital and Performance
    m1, m2, m3, m4, m5, m6 = st.columns(6)

    with m1:
        pnl = summary['capital']['pnl']
        st.metric(
            t(translations, 'paper', 'capital'),
            f"${summary['capital']['current']:.2f}",
            f"{summary['capital']['pnl_pct']:+.2f}%"
        )

    with m2:
        st.metric(t(translations, 'paper', 'total_trades'), summary['stats']['total_trades'])

    with m3:
        st.metric(t(translations, 'paper', 'win_rate'), f"{summary['stats']['win_rate']:.1f}%")

    with m4:
        st.metric(t(translations, 'paper', 'profit_factor'), f"{summary['stats']['profit_factor']:.2f}")

    with m5:
        st.metric(t(translations, 'paper', 'open_positions'), summary['positions']['open'])

    with m6:
        st.metric(t(translations, 'paper', 'test_orders'), summary['positions']['test_orders'])

    # Second row - Coverage metrics
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.metric(t(translations, 'realtime', 'qualified_events'), num_qualified_events, help=t(translations, 'paper', 'events_meeting_filter'))
    with c2:
        st.metric(t(translations, 'paper', 'total_markets'), total_markets, help=t(translations, 'paper', 'markets_across_events'))
    with c3:
        st.metric(t(translations, 'paper', 'tokens_tracked'), total_tokens, help=t(translations, 'paper', 'both_sides_market'))
    with c4:
        st.metric(t(translations, 'paper', 'ws_subscriptions'), len(ws_client.subscribed_tokens) if ws_client else 0)

    # Third row - Latency metrics
    latency = summary.get('latency', {})
    l1, l2, l3, l4 = st.columns(4)
    with l1:
        st.metric(t(translations, 'paper', 'price_updates'), f"{latency.get('total_updates', 0):,}", help=t(translations, 'paper', 'total_updates_processed'))
    with l2:
        st.metric(t(translations, 'paper', 'avg_latency'), f"{latency.get('avg_ms', 0):.1f}ms", help=t(translations, 'paper', 'avg_processing_latency'))
    with l3:
        st.metric(t(translations, 'paper', 'min_latency'), f"{latency.get('min_ms', 0):.1f}ms", help=t(translations, 'paper', 'min_latency_recorded'))
    with l4:
        st.metric(t(translations, 'paper', 'max_latency'), f"{latency.get('max_ms', 0):.1f}ms", help=t(translations, 'paper', 'max_latency_recorded'))

    # Show log file info
    if state.data_logger:
        files = state.data_logger.get_file_paths()
        with st.expander(f"📁 {t(translations, 'paper', 'data_log_files')}"):
            st.caption(t(translations, 'paper', 'all_data_saved_note'))
            st.code(f"Prices: {files['prices']}\nTrades: {files['trades']}\nSignals: {files['signals']}\nLatency: {files['latency']}\nSummary: {files['summary']}")

    st.markdown("---")

    # Main content tabs
    tab1, tab2, tab3, tab4 = st.tabs([f"📈 {t(translations, 'paper', 'live_monitoring')}", f"📊 {t(translations, 'paper', 'performance')}", f"📋 {t(translations, 'paper', 'trade_history')}", f"🎯 {t(translations, 'paper', 'signals')}"])

    with tab1:
        col_left, col_right = st.columns([2, 1])

        with col_left:
            st.subheader(t(translations, 'paper', 'open_positions'))
            positions = paper_trader.get_open_positions()

            if not positions:
                st.info(t(translations, 'paper', 'no_open_positions'))
            else:
                for pos in positions:
                    with st.container():
                        pc1, pc2, pc3, pc4 = st.columns([3, 2, 2, 1])
                        with pc1:
                            st.write(f"**{pos.event_title[:40]}**")
                            st.caption(f"{t(translations, 'paper', 'entry')}: ${pos.entry_price:.4f}")
                        with pc2:
                            st.metric(t(translations, 'paper', 'current'), f"${pos.current_price:.4f}")
                        with pc3:
                            pnl_class = "profit" if pos.unrealized_pnl >= 0 else "loss"
                            st.metric(
                                t(translations, 'paper', 'unrealized_pnl'),
                                f"${pos.unrealized_pnl:.2f}",
                                f"{pos.unrealized_pnl_pct*100:+.2f}%"
                            )
                        with pc4:
                            hold_time = time.time() - pos.entry_time
                            st.metric(t(translations, 'paper', 'hold'), f"{hold_time:.0f}s")
                        st.divider()

            st.subheader(t(translations, 'paper', 'active_test_orders'))
            test_orders = paper_trader.get_active_test_orders()

            if not test_orders:
                st.info(t(translations, 'paper', 'no_active_test_orders'))
            else:
                for order in test_orders[:5]:
                    with st.container():
                        tc1, tc2, tc3 = st.columns([3, 2, 2])
                        with tc1:
                            st.write(f"**{order.event_title[:40]}**")
                            st.caption(f"{t(translations, 'paper', 'entry')}: ${order.entry_price:.4f}")
                        with tc2:
                            change_color = "profit" if order.price_change_pct >= 0 else "loss"
                            st.metric(
                                t(translations, 'paper', 'price_change'),
                                f"${order.current_price:.4f}",
                                f"{order.price_change_pct*100:+.2f}%"
                            )
                        with tc3:
                            elapsed = time.time() - order.entry_time
                            remaining = max(0, order.observation_window - elapsed)
                            st.metric(t(translations, 'paper', 'time_left'), f"{remaining:.0f}s")
                        st.divider()

        with col_right:
            st.subheader(t(translations, 'paper', 'quick_stats'))

            # Today's performance
            st.markdown(f"**{t(translations, 'paper', 'today')}**")
            st.write(f"{t(translations, 'paper', 'trades')}: {summary['today']['trades']}")
            today_pnl = summary['today']['pnl']
            pnl_str = f"${today_pnl:+.2f}" if today_pnl != 0 else "$0.00"
            st.write(f"{t(translations, 'paper', 'pnl')}: {pnl_str}")
            st.write(f"{t(translations, 'paper', 'wins')}: {summary['today']['wins']}")

            st.divider()

            # Averages
            st.markdown(f"**{t(translations, 'paper', 'averages')}**")
            st.write(f"{t(translations, 'paper', 'avg_win')}: ${summary['stats']['avg_win']:.2f}")
            st.write(f"{t(translations, 'paper', 'avg_loss')}: ${summary['stats']['avg_loss']:.2f}")

            st.divider()

            # Risk metrics
            st.markdown(f"**{t(translations, 'paper', 'risk')}**")
            st.write(f"{t(translations, 'paper', 'max_drawdown')}: {summary['stats']['max_drawdown']:.1f}%")
            st.write(f"{t(translations, 'paper', 'test_costs')}: ${summary['stats']['test_order_costs']:.2f}")

            st.divider()

            # Latency metrics
            st.markdown(f"**⚡ {t(translations, 'paper', 'latency')}**")
            latency = summary.get('latency', {})
            st.write(f"{t(translations, 'paper', 'updates')}: {latency.get('total_updates', 0):,}")
            st.write(f"{t(translations, 'paper', 'avg')}: {latency.get('avg_ms', 0):.2f}ms")
            st.write(f"{t(translations, 'paper', 'min')}: {latency.get('min_ms', 0):.2f}ms")
            st.write(f"{t(translations, 'paper', 'max')}: {latency.get('max_ms', 0):.2f}ms")

    with tab2:
        col_chart1, col_chart2 = st.columns(2)

        with col_chart1:
            trades = paper_trader.get_recent_trades(50)
            fig_pnl = create_pnl_chart(trades, translations)
            st.plotly_chart(fig_pnl, width="stretch", key="pnl_chart")

        with col_chart2:
            if paper_trader.stats.total_trades > 0:
                fig_win = create_win_rate_chart(paper_trader.stats, translations)
                st.plotly_chart(fig_win, width="stretch", key="win_chart")
            else:
                st.info(t(translations, 'paper', 'complete_trades_note'))

        # Detailed stats table
        st.subheader(t(translations, 'paper', 'detailed_statistics'))
        stats_data = {
            t(translations, 'paper', 'metric'): [
                t(translations, 'paper', 'total_trades'),
                t(translations, 'paper', 'winning_trades'),
                t(translations, 'paper', 'losing_trades'),
                t(translations, 'paper', 'win_rate'),
                t(translations, 'paper', 'profit_factor'),
                t(translations, 'paper', 'total_pnl'),
                t(translations, 'paper', 'avg_win'),
                t(translations, 'paper', 'avg_loss'),
                t(translations, 'paper', 'max_drawdown')
            ],
            t(translations, 'paper', 'value'): [
                str(paper_trader.stats.total_trades),
                str(paper_trader.stats.winning_trades),
                str(paper_trader.stats.losing_trades),
                f"{paper_trader.stats.win_rate*100:.1f}%",
                f"{paper_trader.stats.profit_factor:.2f}",
                f"${paper_trader.stats.total_pnl:.2f}",
                f"${paper_trader.stats.avg_win:.2f}",
                f"${paper_trader.stats.avg_loss:.2f}",
                f"{paper_trader.stats.max_drawdown*100:.1f}%"
            ]
        }
        st.dataframe(pd.DataFrame(stats_data), width="stretch", hide_index=True)

    with tab3:
        st.subheader(t(translations, 'paper', 'recent_trades'))
        trades = paper_trader.get_recent_trades(20)

        if not trades:
            st.info(t(translations, 'paper', 'no_completed_trades'))
        else:
            trade_data = []
            for trade in reversed(trades):
                trade_data.append({
                    t(translations, 'paper', 'time'): datetime.fromtimestamp(trade.exit_time).strftime('%H:%M:%S'),
                    t(translations, 'realtime', 'event'): trade.event_title[:30],
                    t(translations, 'paper', 'entry'): f"${trade.entry_price:.4f}",
                    t(translations, 'paper', 'exit'): f"${trade.exit_price:.4f}",
                    t(translations, 'paper', 'pnl'): f"${trade.pnl:+.2f}",
                    t(translations, 'paper', 'pnl_pct'): f"{trade.pnl_pct*100:+.2f}%",
                    t(translations, 'paper', 'reason'): trade.exit_reason,
                    t(translations, 'paper', 'hold'): f"{trade.hold_duration:.0f}s",
                    t(translations, 'paper', 'signal'): trade.signal_strength.value
                })

            df = pd.DataFrame(trade_data)
            st.dataframe(df, width="stretch", hide_index=True)

    with tab4:
        st.subheader(t(translations, 'realtime', 'signals_detected'))

        if not state.signal_log:
            st.info(t(translations, 'paper', 'waiting_signals'))
        else:
            for signal in reversed(state.signal_log[-10:]):
                signal_color = {
                    'strong': '#FF4444',
                    'medium': '#FFAA00',
                    'weak': '#44FF44'
                }.get(signal.get('signal', '').lower(), '#888888')

                st.markdown(f"""
                <div style="background-color: {signal_color}20; padding: 10px; border-radius: 5px; margin: 5px 0; border-left: 4px solid {signal_color};">
                    <strong>{signal['signal'].upper()}</strong> at {signal['time']}<br>
                    {signal['event']}<br>
                    {t(translations, 'paper', 'price_change')}: {signal['price_change']}
                </div>
                """, unsafe_allow_html=True)

    # Auto-refresh
    if auto_refresh:
        time.sleep(1)
        st.rerun()


if __name__ == "__main__":
    main()
