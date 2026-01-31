# Polymarket Momentum Trading System

A real-time momentum-following quantitative trading system for live sports events on Polymarket.

## 🎯 Project Status

### ✅ Completed (Phase 1 - Day 1-2)

1. **Project Structure** - Full directory organization
2. **Configuration System** - Comprehensive config with all parameters
3. **API Clients**
   - ✅ Gamma API - Market data fetching
   - ✅ CLOB API - Trading interface (simulation mode)
   - ✅ WebSocket Client - Real-time data streaming
4. **Event Filter** - Scores and ranks events by trading suitability

### 🚧 In Progress

5. **Momentum Detection** - Signal detection algorithm
6. **Test Order System** - Small probe orders for signal validation
7. **Trading Engine** - Entry/exit logic with position management
8. **Risk Management** - Capital limits, stop losses, daily limits
9. **Simulation Engine** - Paper trading for testing
10. **Monitoring Dashboard** - Real-time system monitoring

## 📁 Project Structure

```
momentum_trader/
├── __init__.py                 # Package initialization
├── config.py                   # Configuration system
├── api/                        # API clients
│   ├── gamma_api.py           # Market data API
│   ├── clob_api.py            # Trading API
│   └── websocket_client.py    # Real-time data
├── filters/                    # Event filtering
│   └── event_filter.py        # Scores/ranks events
├── signals/                    # Signal detection
│   ├── test_orders.py         # Test order management
│   └── momentum_detector.py   # Momentum signals
├── trading/                    # Trading logic
│   ├── position_manager.py    # Position tracking
│   └── trading_engine.py      # Entry/exit execution
├── risk/                       # Risk management
│   └── risk_manager.py        # Limits and controls
├── data/                       # Data storage
│   └── database.py            # SQLite database
├── backtesting/               # Historical testing
│   └── backtest_engine.py     # Backtesting framework
└── dashboard/                 # Monitoring UI
    └── dashboard_app.py       # Streamlit dashboard
```

## 🚀 Quick Start

### Installation

```bash
# Install dependencies
pip install requests pandas streamlit websockets asyncio

# Set up environment (optional)
export POLYMARKET_PROXY="http://127.0.0.1:7890"
export TEST_ORDER_AMOUNT="5.0"
export MAX_DAILY_LOSS="200.0"
```

### Basic Usage

```python
from momentum_trader import config, load_config_from_env
from momentum_trader.api import GammaAPI
from momentum_trader.filters import EventFilter

# Load configuration
cfg = load_config_from_env()

# Initialize API
api = GammaAPI(proxy=cfg.api.proxy)

# Test connection
success, msg, latency = api.test_connection()
print(f"API Connection: {msg} ({latency:.2f}s)")

# Filter events
event_filter = EventFilter(api, cfg)
qualified_events = event_filter.filter_and_score_events()

# Print top 10 events
event_filter.print_top_events(limit=10)
```

## 🎯 System Strategy

### Core Logic

1. **Scanning** - Find high-liquidity live sports events
2. **Testing** - Place $5-10 test orders on both sides
3. **Signal Detection** - Identify momentum (price rise ≥2%, volume ≥30%)
4. **Entry** - Invest $100-200 on rising side
5. **Monitoring** - Check every 10 seconds
6. **Exit** - Sell when momentum reverses or take profit hit

### Target Returns

- Earn 3-5 points per close ($3-5 profit)
- Trade 10-20 times per game
- 3-5 games per day
- Target: $50-150 daily (conservative)

## 📊 Configuration

All parameters can be configured in `config.py`:

### Filter Settings
```python
min_24h_volume = $500,000      # Minimum trading volume
min_liquidity = $100,000       # Minimum liquidity
max_spread = 3%                # Maximum bid-ask spread
```

### Test Orders
```python
test_amount = $5               # Test order size
observation_window = 300s      # 5-minute observation
```

### Momentum Detection
```python
min_price_rise = 2%            # Minimum price increase
min_volume_increase = 30%      # Minimum volume increase
```

### Trading
```python
take_profit = 4%               # Profit target
stop_loss = 2%                 # Stop loss
max_hold_time = 300s           # 5 minutes max
```

### Risk Limits
```python
max_single_trade = $200        # Max per position
max_concurrent_positions = 10  # Max positions
max_daily_loss = $200          # Daily loss limit
```

## 🔧 API Clients

### Gamma API - Market Data

```python
from momentum_trader.api import GammaAPI

api = GammaAPI(proxy="http://127.0.0.1:7890")

# Get live events
live_events = api.get_live_events()

# Get specific event
event = api.get_event("event_id")

# Get sports categories
sports = api.get_sports()
```

### CLOB API - Trading (Simulation Mode)

```python
from momentum_trader.api import CLOBAPI, OrderSide

# Initialize in simulation mode
clob = CLOBAPI(simulation_mode=True)

# Place market buy order
order = clob.place_order(
    token_id="token_123",
    side=OrderSide.BUY,
    size=100.0
)

# Check order status
status = clob.get_order(order.id)
```

### WebSocket - Real-time Data

```python
from momentum_trader.api import WebSocketClient

def on_price_update(update):
    print(f"Price: {update.price} for {update.token_id}")

# Start WebSocket client
ws = WebSocketClient(on_price_update=on_price_update)
ws.start()

# Subscribe to markets
ws.subscribe("token_123")

# Get current price
price = ws.get_price("token_123")
```

## 🎯 Event Filter

Scores events based on:
- **Liquidity** (20 pts) - Higher volume = higher score
- **Spread** (10 pts) - Lower spread = higher score
- **Activity** (15 pts) - Recent volume vs average
- **Volatility** (10 pts) - Price movement potential
- **Category Bonus** (10 pts) - NFL, NBA, etc get bonus

```python
from momentum_trader.filters import EventFilter

filter = EventFilter(api, config)

# Filter and score all live events
qualified = filter.filter_and_score_events()

# Get top 20 events
top_20 = filter.get_top_events(limit=20)

# Print rankings
filter.print_top_events(limit=10)
```

## ⚠️ Important Notes

### Testing Phase

**SIMULATION MODE IS ENABLED BY DEFAULT**
- No real orders are placed
- All trading is simulated with virtual capital
- Use this for testing and validation

### Before Real Trading

1. ✅ Run historical backtest (win rate >55%)
2. ✅ Run simulated trading for 72 hours
3. ✅ Verify all risk controls working
4. ✅ Test with small amounts first ($10-20 per trade)
5. ✅ Monitor closely for first week

### Key Risks

- **Test Order Costs** - Testing many events costs money
- **Momentum Duration** - Momentum may be very short
- **Slippage** - Real fills differ from simulation
- **API Rate Limits** - Don't exceed rate limits
- **Market Liquidity** - Low liquidity = poor fills

## 📈 Next Steps

### Week 1 Remaining Tasks

- [x] Day 1-2: Setup + API Integration
- [ ] Day 3-4: Test Orders + Momentum Detection
- [ ] Day 5-7: Trading Logic + Backtesting

### Week 2 Tasks

- [ ] Day 8-9: WebSocket Integration + Simulation
- [ ] Day 10-12: Dashboard + Risk Management
- [ ] Day 13-14: Testing + Documentation

## 📚 Documentation

See `polymarket_momentum_cn.md` for complete implementation plan.

## 🤝 Contributing

This is a private trading system. Do not share or distribute.

## ⚠️ Disclaimer

**FOR EDUCATIONAL PURPOSES ONLY**

- Trading involves significant risk of loss
- Past performance does not guarantee future results
- Only trade with capital you can afford to lose
- Thoroughly test before using real money
- Monitor system constantly during operation

---

**Status**: Phase 1 Complete - Core infrastructure ready
**Next**: Implement momentum detection and test order system
