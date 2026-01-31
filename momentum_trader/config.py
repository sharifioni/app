"""
Polymarket Momentum Trading System - Configuration
All configurable parameters for the trading system
"""

from dataclasses import dataclass, field
from typing import List, Optional
import os


@dataclass
class APIConfig:
    """API Configuration"""
    gamma_base_url: str = "https://gamma-api.polymarket.com"
    clob_base_url: str = "https://clob.polymarket.com"
    websocket_url: str = "wss://ws-subscriptions-clob.polymarket.com/ws/market"

    # Rate limits
    gamma_rate_limit: int = 100  # requests per minute
    clob_rate_limit: int = 50   # requests per 10 seconds

    # Timeouts
    request_timeout: int = 30
    websocket_timeout: int = 60

    # Retry settings
    max_retries: int = 3
    retry_delay: float = 1.0

    # Proxy (optional)
    proxy: Optional[str] = None


@dataclass
class FilterConfig:
    """Event Filter Configuration"""
    # Status conditions
    min_game_progress: float = 0.10  # 10% game completed (lowered to capture early game)
    max_game_progress: float = 0.90  # 90% game completed (raised to capture late game)
    min_time_remaining: int = 120    # 2 minutes in seconds (lowered)

    # Liquidity conditions
    min_24h_volume: float = 10   # $10K (lowered to capture more events)
    min_liquidity: float = 50     # $5K (lowered to capture more events)
    max_spread: float = 0.05         # 5% (raised to capture more events)

    # Orderbook conditions
    min_bid_depth: float = 10       # $100 (lowered)
    min_ask_depth: float = 10       # $100 (lowered)

    # Priority sports (higher scoring)
    priority_sports: List[str] = field(default_factory=lambda: [
        'nfl', 'nba', 'epl', 'tennis', 'mlb', 'nhl'
    ])

    # Scoring weights
    liquidity_weight: int = 20
    spread_weight: int = 10
    activity_weight: int = 15
    volatility_weight: int = 10
    category_bonus: int = 10

    # Rescan interval
    rescan_interval: int = 300  # 5 minutes


@dataclass
class TestOrderConfig:
    """Test Order Configuration"""
    test_amount: float = 5.0        # $5 per test order
    min_test_amount: float = 2.0    # Minimum $2
    max_test_amount: float = 10.0   # Maximum $10

    observation_window: int = 300   # 5 minutes observation
    check_interval: int = 10        # Check every 10 seconds

    # States
    STATE_OBSERVING = "observing"
    STATE_SIGNAL_TRIGGERED = "signal_triggered"
    STATE_TIMEOUT = "timeout_ended"


@dataclass
class MomentumConfig:
    """Momentum Detection Configuration"""
    # Signal thresholds
    min_price_rise: float = 0.02    # 2% minimum price rise
    min_volume_increase: float = 0.30  # 30% volume increase

    # Trend confirmation
    trend_periods: int = 2          # 2 consecutive periods

    # Signal strength levels
    weak_price_rise: tuple = (0.02, 0.03)      # 2-3%
    weak_volume_increase: tuple = (0.30, 0.50)  # 30-50%
    weak_position_size: float = 100.0           # $100

    medium_price_rise: tuple = (0.03, 0.05)     # 3-5%
    medium_volume_increase: tuple = (0.50, 1.0) # 50-100%
    medium_position_size: float = 150.0         # $150

    strong_price_rise: float = 0.05             # >5%
    strong_volume_increase: float = 1.0         # >100%
    strong_position_size: float = 200.0         # $200 (cap)


@dataclass
class TradingConfig:
    """Trading Configuration"""
    # Entry settings
    entry_batches: int = 2          # Split into 2 batches
    first_batch_ratio: float = 0.6  # 60% first batch
    batch_delay: float = 2.0        # 2 seconds between batches

    # Exit settings
    take_profit: float = 0.04       # 4% profit target
    stop_loss: float = 0.02         # 2% stop loss
    max_hold_time: int = 300        # 5 minutes max hold
    game_end_buffer: int = 60       # Exit 1 minute before game ends

    # Monitoring
    exit_check_interval: int = 10   # Check every 10 seconds

    # Reversal detection
    reversal_periods: int = 2       # 2 consecutive down periods
    volume_drop_threshold: float = 0.20  # 20% volume drop


@dataclass
class RiskConfig:
    """Risk Management Configuration"""
    # Single trade limits
    max_single_trade: float = 200.0     # $200 max per trade
    max_single_loss: float = 50.0       # $50 max loss per trade

    # Position limits
    max_concurrent_positions: int = 10   # Max 10 positions
    max_positions_per_event: int = 1     # 1 position per event

    # Capital limits
    max_capital_usage: float = 0.80      # 80% max deployed
    reserve_ratio: float = 0.20          # 20% reserve

    # Daily limits
    max_daily_loss: float = 200.0        # $200 daily loss limit
    max_daily_trades: int = 50           # Max 50 trades per day

    # Drawdown limits
    max_drawdown: float = 0.15           # 15% max drawdown

    # Risk states
    STATE_NORMAL = "normal"
    STATE_WARNING = "warning"
    STATE_PROTECTION = "protection"
    STATE_HALTED = "halted"


@dataclass
class SimulationConfig:
    """Simulated Trading Configuration"""
    initial_capital: float = 1000.0     # $1000 virtual capital
    slippage: float = 0.005             # 0.5% simulated slippage
    partial_fill_prob: float = 0.0      # Assume full fills in simulation

    # Success criteria
    min_runtime_hours: int = 72         # 72 hours minimum
    min_win_rate: float = 0.50          # 50% win rate
    max_response_time: float = 2.0      # 2 seconds max


@dataclass
class BacktestConfig:
    """Backtesting Configuration"""
    initial_capital: float = 1000.0

    # Success criteria
    min_win_rate: float = 0.55          # 55% minimum
    min_profit_factor: float = 1.5      # Avg win / Avg loss
    max_drawdown: float = 0.10          # 10% max


@dataclass
class DatabaseConfig:
    """Database Configuration"""
    # SQLite for simplicity (can upgrade to PostgreSQL)
    db_path: str = "momentum_trader.db"

    # Tables
    events_table: str = "events"
    test_orders_table: str = "test_orders"
    positions_table: str = "positions"
    trades_table: str = "trades"
    signals_table: str = "signals"
    risk_log_table: str = "risk_log"


@dataclass
class Config:
    """Main Configuration Container"""
    api: APIConfig = field(default_factory=APIConfig)
    filter: FilterConfig = field(default_factory=FilterConfig)
    test_order: TestOrderConfig = field(default_factory=TestOrderConfig)
    momentum: MomentumConfig = field(default_factory=MomentumConfig)
    trading: TradingConfig = field(default_factory=TradingConfig)
    risk: RiskConfig = field(default_factory=RiskConfig)
    simulation: SimulationConfig = field(default_factory=SimulationConfig)
    backtest: BacktestConfig = field(default_factory=BacktestConfig)
    database: DatabaseConfig = field(default_factory=DatabaseConfig)

    # Global settings
    timezone: str = "Asia/Shanghai"  # Chinese time
    log_level: str = "INFO"
    debug_mode: bool = False


# Default configuration instance
config = Config()


def load_config_from_env():
    """Load configuration overrides from environment variables"""
    if os.getenv("POLYMARKET_PROXY"):
        config.api.proxy = os.getenv("POLYMARKET_PROXY")

    if os.getenv("TEST_ORDER_AMOUNT"):
        config.test_order.test_amount = float(os.getenv("TEST_ORDER_AMOUNT"))

    if os.getenv("MAX_SINGLE_TRADE"):
        config.risk.max_single_trade = float(os.getenv("MAX_SINGLE_TRADE"))

    if os.getenv("MAX_DAILY_LOSS"):
        config.risk.max_daily_loss = float(os.getenv("MAX_DAILY_LOSS"))

    if os.getenv("DEBUG_MODE"):
        config.debug_mode = os.getenv("DEBUG_MODE").lower() == "true"

    return config
