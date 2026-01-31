"""
Paper Trading Engine for Momentum Strategy
Simulates trading with fake money using real market data
"""

import time
import threading
import logging
from datetime import datetime
from typing import Dict, List, Optional, Callable
from dataclasses import dataclass, field
from enum import Enum
from collections import deque
import json

logger = logging.getLogger(__name__)


class OrderSide(Enum):
    BUY = "buy"
    SELL = "sell"


class OrderStatus(Enum):
    PENDING = "pending"
    FILLED = "filled"
    CANCELLED = "cancelled"


class PositionStatus(Enum):
    OPEN = "open"
    CLOSED = "closed"


class SignalStrength(Enum):
    WEAK = "weak"       # 2-3% rise, 30-50% volume increase -> $100
    MEDIUM = "medium"   # 3-5% rise, 50-100% volume increase -> $150
    STRONG = "strong"   # >5% rise, >100% volume increase -> $200


@dataclass
class TestOrder:
    """Test order for probing market momentum"""
    id: str
    token_id: str
    event_id: str
    event_title: str
    team: str  # Which team/outcome
    side: OrderSide
    amount: float  # Dollar amount (e.g., $5)
    entry_price: float
    entry_time: float
    baseline_volume: float = 0.0

    # Tracking
    current_price: float = 0.0
    current_volume: float = 0.0
    price_change_pct: float = 0.0
    volume_change_pct: float = 0.0

    # Price history for trend detection
    price_history: List[tuple] = field(default_factory=list)  # [(timestamp, price), ...]

    # State
    signal_triggered: bool = False
    signal_strength: Optional[SignalStrength] = None
    expired: bool = False

    # Config
    observation_window: float = 300.0  # 5 minutes
    warmup_period: float = 10.0  # 10 seconds warmup before signal detection
    min_price_updates: int = 5   # Minimum price updates needed before signals

    # Latency tracking
    last_price_update_time: float = 0.0  # When last price update was received
    signal_detection_time: float = 0.0   # When signal was detected
    price_update_count: int = 0          # Number of price updates received


@dataclass
class Position:
    """Trading position"""
    id: str
    token_id: str
    event_id: str
    event_title: str
    team: str
    side: OrderSide

    # Entry
    entry_price: float
    entry_time: float
    quantity: float  # Number of shares
    entry_amount: float  # Dollar amount invested
    signal_strength: SignalStrength

    # Current state
    current_price: float = 0.0
    unrealized_pnl: float = 0.0
    unrealized_pnl_pct: float = 0.0

    # Exit
    exit_price: float = 0.0
    exit_time: float = 0.0
    exit_reason: str = ""
    realized_pnl: float = 0.0

    # Status
    status: PositionStatus = PositionStatus.OPEN

    # Config
    take_profit_pct: float = 0.04  # 4%
    stop_loss_pct: float = -0.02  # -2%
    max_hold_time: float = 300.0  # 5 minutes

    # Latency tracking
    signal_detection_time: float = 0.0   # When the signal was detected
    position_open_time: float = 0.0      # When position was actually opened


@dataclass
class Trade:
    """Completed trade record"""
    id: str
    token_id: str
    event_id: str
    event_title: str
    team: str

    entry_price: float
    exit_price: float
    entry_time: float
    exit_time: float
    quantity: float
    amount: float

    pnl: float
    pnl_pct: float
    exit_reason: str
    signal_strength: SignalStrength
    hold_duration: float

    # Latency tracking (in milliseconds)
    signal_latency_ms: float = 0.0      # Time from price update to signal detection
    execution_latency_ms: float = 0.0    # Time from signal to position open


@dataclass
class TradingStats:
    """Trading statistics"""
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0

    total_pnl: float = 0.0
    total_wins: float = 0.0
    total_losses: float = 0.0

    avg_win: float = 0.0
    avg_loss: float = 0.0
    win_rate: float = 0.0
    profit_factor: float = 0.0

    max_drawdown: float = 0.0
    peak_capital: float = 0.0

    test_order_costs: float = 0.0

    # Today's stats
    today_trades: int = 0
    today_pnl: float = 0.0
    today_wins: int = 0

    # Latency stats
    total_price_updates: int = 0
    avg_process_latency_ms: float = 0.0
    min_latency_ms: float = float('inf')
    max_latency_ms: float = 0.0
    total_latency_ms: float = 0.0


class PaperTrader:
    """
    Paper Trading Engine

    Implements the momentum strategy with fake money:
    1. Places test orders on both sides of qualified events
    2. Monitors for momentum signals (price rise ≥2%, volume ≥30%)
    3. Opens positions when signals detected
    4. Manages exits (take profit, stop loss, reversal, timeout)
    """

    def __init__(
        self,
        initial_capital: float = 50000.0,
        test_order_amount: float = 5.0,
        on_trade_complete: Optional[Callable[[Trade], None]] = None,
        on_signal_detected: Optional[Callable[[TestOrder], None]] = None,
    ):
        """
        Args:
            initial_capital: Starting fake money amount
            test_order_amount: Amount for test orders ($5-10)
            on_trade_complete: Callback when trade completes
            on_signal_detected: Callback when momentum signal detected
        """
        self.initial_capital = initial_capital
        self.capital = initial_capital
        self.test_order_amount = test_order_amount
        self.on_trade_complete = on_trade_complete
        self.on_signal_detected = on_signal_detected

        # State
        self.test_orders: Dict[str, TestOrder] = {}  # token_id -> TestOrder
        self.positions: Dict[str, Position] = {}  # token_id -> Position
        self.trades: List[Trade] = []
        self.stats = TradingStats()

        # Price tracking
        self.price_history: Dict[str, deque] = {}  # token_id -> deque of (timestamp, price)
        self.volume_history: Dict[str, deque] = {}  # token_id -> deque of (timestamp, volume)

        # Risk control
        self.max_positions = 10
        self.max_single_trade = 200.0
        self.max_capital_usage = 0.8  # 80%
        self.daily_loss_limit = 200.0
        self.max_drawdown_pct = 0.15  # 15%

        # Momentum thresholds
        self.price_rise_threshold = 0.02  # 2%
        self.volume_increase_threshold = 0.30  # 30%
        self.trend_periods = 2  # Need 2 consecutive rising periods

        # Threading
        self._running = False
        self._lock = threading.Lock()

        # Order ID counter
        self._order_counter = 0

        logger.info(f"Paper Trader initialized with ${initial_capital} capital")

    def _generate_id(self) -> str:
        """Generate unique ID"""
        self._order_counter += 1
        return f"PT_{int(time.time())}_{self._order_counter}"

    def add_price_update(self, token_id: str, price: float, volume: float = 0.0, ws_received_time: float = 0.0):
        """Process incoming price update

        Args:
            token_id: Token identifier
            price: Current price
            volume: Current volume
            ws_received_time: Timestamp when WebSocket message was received (for latency tracking)
        """
        with self._lock:
            timestamp = time.time()

            # Track latency if ws_received_time provided
            if ws_received_time > 0:
                latency_ms = (timestamp - ws_received_time) * 1000
                self._update_latency_stats(latency_ms)

            # Update price history
            if token_id not in self.price_history:
                self.price_history[token_id] = deque(maxlen=300)
            self.price_history[token_id].append((timestamp, price))

            # Update volume history
            if token_id not in self.volume_history:
                self.volume_history[token_id] = deque(maxlen=300)
            if volume > 0:
                self.volume_history[token_id].append((timestamp, volume))

            # Update test orders
            if token_id in self.test_orders:
                self._update_test_order(token_id, price, volume, timestamp)

            # Update positions
            if token_id in self.positions:
                self._update_position(token_id, price)

    def _update_latency_stats(self, latency_ms: float):
        """Update latency statistics"""
        self.stats.total_price_updates += 1
        self.stats.total_latency_ms += latency_ms
        self.stats.min_latency_ms = min(self.stats.min_latency_ms, latency_ms)
        self.stats.max_latency_ms = max(self.stats.max_latency_ms, latency_ms)
        self.stats.avg_process_latency_ms = self.stats.total_latency_ms / self.stats.total_price_updates

    def place_test_order(
        self,
        token_id: str,
        event_id: str,
        event_title: str,
        team: str,
        current_price: float,
        current_volume: float = 0.0
    ) -> Optional[TestOrder]:
        """Place a test order to probe market momentum"""
        with self._lock:
            # Check if already have test order for this token
            if token_id in self.test_orders:
                return None

            # Check capital
            if self.capital < self.test_order_amount:
                logger.warning("Insufficient capital for test order")
                return None

            # Create test order
            order = TestOrder(
                id=self._generate_id(),
                token_id=token_id,
                event_id=event_id,
                event_title=event_title,
                team=team,
                side=OrderSide.BUY,
                amount=self.test_order_amount,
                entry_price=current_price,
                entry_time=time.time(),
                baseline_volume=current_volume,
                current_price=current_price,
                current_volume=current_volume,
            )

            # Deduct capital (test order cost)
            self.capital -= self.test_order_amount
            self.stats.test_order_costs += self.test_order_amount

            self.test_orders[token_id] = order
            logger.info(f"Test order placed: {event_title} - {team} @ {current_price:.4f}")

            return order

    def _update_test_order(self, token_id: str, price: float, volume: float, update_time: float = 0.0):
        """Update test order with new price data"""
        order = self.test_orders.get(token_id)
        if not order or order.expired or order.signal_triggered:
            return

        now = time.time()

        # Update current values
        order.current_price = price
        order.current_volume = volume
        order.last_price_update_time = update_time if update_time > 0 else now
        order.price_update_count += 1

        # Add to price history
        order.price_history.append((now, price))
        if len(order.price_history) > 60:
            order.price_history = order.price_history[-60:]

        # During warmup: Re-establish baseline from stable prices
        # Use the average of first few prices as true entry point
        if order.price_update_count == order.min_price_updates:
            # Calculate average of warmup prices as true baseline
            warmup_prices = [p for _, p in order.price_history]
            if warmup_prices:
                order.entry_price = sum(warmup_prices) / len(warmup_prices)
                logger.debug(f"Baseline established for {order.event_title}: ${order.entry_price:.4f}")

        # Calculate changes (only if past warmup)
        if order.entry_price > 0:
            order.price_change_pct = (price - order.entry_price) / order.entry_price

        if order.baseline_volume > 0 and volume > 0:
            order.volume_change_pct = (volume - order.baseline_volume) / order.baseline_volume

        # Check for expiration (5 minutes)
        elapsed = now - order.entry_time
        if elapsed > order.observation_window:
            order.expired = True
            # Return test order capital (with small loss for spread)
            self.capital += self.test_order_amount * 0.98  # 2% loss assumption
            logger.info(f"Test order expired: {order.event_title}")
            return

        # Skip signal detection during warmup period
        if elapsed < order.warmup_period or order.price_update_count < order.min_price_updates:
            return

        # Check for momentum signal
        signal = self._detect_momentum_signal(order)
        if signal:
            order.signal_triggered = True
            order.signal_strength = signal
            order.signal_detection_time = now
            logger.info(f"MOMENTUM SIGNAL: {order.event_title} - {signal.value.upper()}")

            if self.on_signal_detected:
                self.on_signal_detected(order)

            # Auto-open position
            self._open_position_from_signal(order)

    def _detect_momentum_signal(self, order: TestOrder) -> Optional[SignalStrength]:
        """Detect if momentum signal conditions are met"""
        # Sanity check: Reject unrealistic price changes (>50% in 5 minutes is suspicious)
        if abs(order.price_change_pct) > 0.50:
            logger.debug(f"Rejecting signal: unrealistic price change {order.price_change_pct*100:.1f}%")
            return None

        # Condition 1: Price rise >= threshold
        if order.price_change_pct < self.price_rise_threshold:
            return None

        # Condition 2: Volume increase >= threshold (if we have volume data)
        if order.baseline_volume > 0:
            if order.volume_change_pct < self.volume_increase_threshold:
                return None

        # Condition 3: Trend confirmation (2 consecutive rising periods)
        if len(order.price_history) >= self.trend_periods + 1:
            recent = order.price_history[-self.trend_periods - 1:]
            rising_count = 0
            for i in range(1, len(recent)):
                if recent[i][1] > recent[i-1][1]:
                    rising_count += 1

            if rising_count < self.trend_periods:
                return None

        # Determine signal strength
        if order.price_change_pct >= 0.05 or order.volume_change_pct >= 1.0:
            return SignalStrength.STRONG
        elif order.price_change_pct >= 0.03 or order.volume_change_pct >= 0.5:
            return SignalStrength.MEDIUM
        else:
            return SignalStrength.WEAK

    def _open_position_from_signal(self, test_order: TestOrder):
        """Open position based on momentum signal"""
        position_open_start = time.time()

        # Determine position size based on signal strength
        if test_order.signal_strength == SignalStrength.STRONG:
            position_amount = 200.0
        elif test_order.signal_strength == SignalStrength.MEDIUM:
            position_amount = 150.0
        else:
            position_amount = 100.0

        # Apply risk limits
        position_amount = min(position_amount, self.max_single_trade)
        position_amount = min(position_amount, self.capital * self.max_capital_usage)

        if position_amount < 10:
            logger.warning("Insufficient capital for position")
            return

        # Check position limits
        open_positions = sum(1 for p in self.positions.values() if p.status == PositionStatus.OPEN)
        if open_positions >= self.max_positions:
            logger.warning("Max positions reached")
            return

        # Calculate quantity
        quantity = position_amount / test_order.current_price

        # Create position with latency tracking
        position = Position(
            id=self._generate_id(),
            token_id=test_order.token_id,
            event_id=test_order.event_id,
            event_title=test_order.event_title,
            team=test_order.team,
            side=OrderSide.BUY,
            entry_price=test_order.current_price,
            entry_time=time.time(),
            quantity=quantity,
            entry_amount=position_amount,
            signal_strength=test_order.signal_strength,
            current_price=test_order.current_price,
            signal_detection_time=test_order.signal_detection_time,
            position_open_time=position_open_start,
        )

        # Deduct capital
        self.capital -= position_amount

        self.positions[test_order.token_id] = position

        # Calculate execution latency
        exec_latency_ms = (time.time() - test_order.signal_detection_time) * 1000 if test_order.signal_detection_time > 0 else 0
        logger.info(f"Position opened: {test_order.event_title} - ${position_amount:.2f} @ {position.entry_price:.4f} (exec: {exec_latency_ms:.1f}ms)")

        # Remove test order (it served its purpose)
        del self.test_orders[test_order.token_id]

    def _update_position(self, token_id: str, price: float):
        """Update position with new price and check exit conditions"""
        position = self.positions.get(token_id)
        if not position or position.status != PositionStatus.OPEN:
            return

        # Update current price
        position.current_price = price

        # Calculate unrealized P&L
        position.unrealized_pnl = (price - position.entry_price) * position.quantity
        position.unrealized_pnl_pct = (price - position.entry_price) / position.entry_price

        # Check exit conditions
        exit_reason = self._check_exit_conditions(position)
        if exit_reason:
            self._close_position(position, exit_reason)

    def _check_exit_conditions(self, position: Position) -> Optional[str]:
        """Check if any exit condition is triggered"""
        # 1. Take profit
        if position.unrealized_pnl_pct >= position.take_profit_pct:
            return "take_profit"

        # 2. Stop loss
        if position.unrealized_pnl_pct <= position.stop_loss_pct:
            return "stop_loss"

        # 3. Time stop (max hold time)
        hold_time = time.time() - position.entry_time
        if hold_time >= position.max_hold_time:
            return "timeout"

        # 4. Momentum reversal (2 consecutive declining periods)
        if position.token_id in self.price_history:
            history = list(self.price_history[position.token_id])
            if len(history) >= 3:
                recent = history[-3:]
                if recent[-1][1] < recent[-2][1] < recent[-3][1]:
                    return "reversal"

        return None

    def _close_position(self, position: Position, exit_reason: str):
        """Close position and record trade"""
        position.exit_price = position.current_price
        position.exit_time = time.time()
        position.exit_reason = exit_reason
        position.realized_pnl = position.unrealized_pnl
        position.status = PositionStatus.CLOSED

        # Return capital + P&L
        exit_amount = position.entry_amount + position.realized_pnl
        self.capital += exit_amount

        # Calculate latency metrics
        signal_latency_ms = 0.0
        execution_latency_ms = 0.0
        if position.signal_detection_time > 0 and position.position_open_time > 0:
            execution_latency_ms = (position.position_open_time - position.signal_detection_time) * 1000

        # Create trade record
        trade = Trade(
            id=self._generate_id(),
            token_id=position.token_id,
            event_id=position.event_id,
            event_title=position.event_title,
            team=position.team,
            entry_price=position.entry_price,
            exit_price=position.exit_price,
            entry_time=position.entry_time,
            exit_time=position.exit_time,
            quantity=position.quantity,
            amount=position.entry_amount,
            pnl=position.realized_pnl,
            pnl_pct=position.unrealized_pnl_pct,
            exit_reason=exit_reason,
            signal_strength=position.signal_strength,
            hold_duration=position.exit_time - position.entry_time,
            signal_latency_ms=signal_latency_ms,
            execution_latency_ms=execution_latency_ms,
        )

        self.trades.append(trade)

        # Update stats
        self._update_stats(trade)

        # Remove from positions
        del self.positions[position.token_id]

        logger.info(f"Position closed: {position.event_title} | {exit_reason} | P&L: ${position.realized_pnl:.2f}")

        if self.on_trade_complete:
            self.on_trade_complete(trade)

    def _update_stats(self, trade: Trade):
        """Update trading statistics"""
        self.stats.total_trades += 1
        self.stats.total_pnl += trade.pnl
        self.stats.today_trades += 1
        self.stats.today_pnl += trade.pnl

        if trade.pnl > 0:
            self.stats.winning_trades += 1
            self.stats.total_wins += trade.pnl
            self.stats.today_wins += 1
        else:
            self.stats.losing_trades += 1
            self.stats.total_losses += abs(trade.pnl)

        # Calculate averages
        if self.stats.winning_trades > 0:
            self.stats.avg_win = self.stats.total_wins / self.stats.winning_trades
        if self.stats.losing_trades > 0:
            self.stats.avg_loss = self.stats.total_losses / self.stats.losing_trades

        # Win rate
        if self.stats.total_trades > 0:
            self.stats.win_rate = self.stats.winning_trades / self.stats.total_trades

        # Profit factor
        if self.stats.total_losses > 0:
            self.stats.profit_factor = self.stats.total_wins / self.stats.total_losses

        # Drawdown
        current_capital = self.capital
        if current_capital > self.stats.peak_capital:
            self.stats.peak_capital = current_capital

        if self.stats.peak_capital > 0:
            drawdown = (self.stats.peak_capital - current_capital) / self.stats.peak_capital
            self.stats.max_drawdown = max(self.stats.max_drawdown, drawdown)

    def force_close_all(self):
        """Force close all positions"""
        with self._lock:
            for token_id in list(self.positions.keys()):
                position = self.positions[token_id]
                if position.status == PositionStatus.OPEN:
                    self._close_position(position, "force_close")

    def get_open_positions(self) -> List[Position]:
        """Get all open positions"""
        return [p for p in self.positions.values() if p.status == PositionStatus.OPEN]

    def get_active_test_orders(self) -> List[TestOrder]:
        """Get all active test orders"""
        return [o for o in self.test_orders.values() if not o.expired and not o.signal_triggered]

    def get_recent_trades(self, limit: int = 50) -> List[Trade]:
        """Get recent trades"""
        return self.trades[-limit:]

    def get_summary(self) -> Dict:
        """Get trading summary"""
        return {
            'capital': {
                'initial': self.initial_capital,
                'current': self.capital,
                'pnl': self.capital - self.initial_capital,
                'pnl_pct': (self.capital - self.initial_capital) / self.initial_capital * 100,
            },
            'positions': {
                'open': len(self.get_open_positions()),
                'test_orders': len(self.get_active_test_orders()),
            },
            'stats': {
                'total_trades': self.stats.total_trades,
                'win_rate': self.stats.win_rate * 100,
                'profit_factor': self.stats.profit_factor,
                'avg_win': self.stats.avg_win,
                'avg_loss': self.stats.avg_loss,
                'max_drawdown': self.stats.max_drawdown * 100,
                'test_order_costs': self.stats.test_order_costs,
            },
            'today': {
                'trades': self.stats.today_trades,
                'pnl': self.stats.today_pnl,
                'wins': self.stats.today_wins,
            },
            'latency': {
                'total_updates': self.stats.total_price_updates,
                'avg_ms': self.stats.avg_process_latency_ms,
                'min_ms': self.stats.min_latency_ms if self.stats.min_latency_ms != float('inf') else 0.0,
                'max_ms': self.stats.max_latency_ms,
            }
        }

    def reset_daily_stats(self):
        """Reset daily statistics (call at start of each day)"""
        self.stats.today_trades = 0
        self.stats.today_pnl = 0.0
        self.stats.today_wins = 0
