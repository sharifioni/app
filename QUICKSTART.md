# Momentum Trader - Quick Start Guide

## 📦 What's Been Completed (Phase 1)

### ✅ Core Infrastructure (Day 1-2 Complete)

1. **Project Structure**
   - Full directory organization
   - All module folders created
   - Clean separation of concerns

2. **Configuration System** ([config.py](momentum_trader/config.py))
   - All parameters centralized
   - Environment variable support
   - Easy parameter tuning

3. **API Clients** ([api/](momentum_trader/api/))
   - **Gamma API**: Market data fetching
   - **CLOB API**: Trading interface (simulation mode)
   - **WebSocket**: Real-time price streaming
   - Rate limiting built-in
   - Auto-retry on failures

4. **Event Filter** ([filters/](momentum_trader/filters/))
   - Scores events 0-65 points
   - Filters by liquidity, spread, progress
   - Ranks by trading suitability
   - Auto-rejects unsuitable events

---

## 🚀 Installation

```bash
# Navigate to project
cd c:\Users\shahj\Downloads\Project

# Install dependencies
pip install -r requirements.txt

# Optional: Set proxy if needed
set POLYMARKET_PROXY=http://127.0.0.1:7890
```

---

## 🎯 Test Drive (5 Minutes)

### Step 1: Run the Event Filter Demo

```bash
cd momentum_trader
python examples\event_filter_demo.py
```

**What it does:**
- Connects to Polymarket API
- Fetches all live sports events
- Filters based on quality criteria
- Scores and ranks events
- Shows top 10 tradeable events

**Expected output:**
```
POLYMARKET MOMENTUM TRADER - Event Filter Demo
================================================================

Configuration loaded:
  - Min 24h Volume: $500,000
  - Min Liquidity: $100,000
  - Max Spread: 3.0%
  - Priority Sports: nfl, nba, epl, tennis, mlb, nhl

Connecting to Polymarket API...
✅ Connected successfully (0.45s response time)

Fetching live events...
✅ Fetched 15 live events in 1.23s

Filtering and scoring events...
✅ Filtering complete in 0.05s
   Qualified: 3/15 events

================================================================
TOP 3 QUALIFIED EVENTS
================================================================

1. Los Angeles Lakers vs Boston Celtics
   Score: 45.0 (Liq:15 Spread:7 Act:10 Vol:7 Bonus:10)
   Volume: $1,234,567 | Liquidity: $456,789 | Spread: 1.8%
   Status: Q3 | Markets: 8

2. Chelsea FC vs Manchester United FC
   Score: 38.0 (Liq:10 Spread:10 Act:5 Vol:4 Bonus:10)
   Volume: $876,543 | Liquidity: $234,567 | Spread: 0.9%
   Status: H2 | Markets: 5

3. UFC 300: Main Event
   Score: 32.0 (Liq:10 Spread:4 Act:5 Vol:4 Bonus:10)
   Volume: $654,321 | Liquidity: $123,456 | Spread: 2.5%
   Status: 2/5 | Markets: 6
```

### Step 2: Check the Live Sports Dashboard

```bash
# From the main Project folder
streamlit run live_sports_dashboard.py
```

This shows the same events but in a beautiful web interface with Chinese time.

---

## 📊 How the System Works

### Current Capabilities

```
┌─────────────────┐
│  Live Events    │  15 games happening now
│  from API       │  (NBA, NFL, Soccer, etc.)
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Event Filter   │  Checks each event:
│  (Scoring)      │  • Volume > $500K? ✓
│                 │  • Spread < 3%? ✓
│                 │  • Game 30-70% done? ✓
│                 │  • Binary markets? ✓
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Top 3-5        │  Only best events qualify
│  Qualified      │  Score: 30-65 points
│  Events         │  Ready for trading
└─────────────────┘
```

### What's Next (To Be Built)

```
┌─────────────────┐
│  Test Orders    │  Place $5 on each side
│  (Probing)      │  Watch for 5 minutes
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Momentum       │  Price up 2% + Volume up 30%
│  Detection      │  = BUY SIGNAL!
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Trading        │  Buy $100-200
│  Engine         │  Hold 5 mins max
│                 │  Sell on reversal
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Risk           │  Daily loss limit: $200
│  Management     │  Max positions: 10
│                 │  Stop loss: -2%
└─────────────────┘
```

---

## 📁 Key Files

| File | Purpose |
|------|---------|
| [config.py](momentum_trader/config.py) | All configurable parameters |
| [api/gamma_api.py](momentum_trader/api/gamma_api.py) | Fetch market data |
| [api/clob_api.py](momentum_trader/api/clob_api.py) | Place orders (simulation) |
| [api/websocket_client.py](momentum_trader/api/websocket_client.py) | Real-time price updates |
| [filters/event_filter.py](momentum_trader/filters/event_filter.py) | Event scoring/ranking |
| [README.md](momentum_trader/README.md) | Full documentation |

---

## 🎛️ Configuration

Edit [config.py](momentum_trader/config.py) to change parameters:

### Filter Settings (Lines 50-89)
```python
# Liquidity requirements
min_24h_volume: float = 500_000  # Lower to 250_000 for more events
min_liquidity: float = 100_000   # Lower to 50_000 for more events
max_spread: float = 0.03         # Raise to 0.05 for more events
```

### Test Order Settings (Lines 91-105)
```python
test_amount: float = 5.0         # Change to 2.0 to reduce costs
observation_window: int = 300    # 5 minutes observation
```

### Risk Limits (Lines 151-183)
```python
max_single_trade: float = 200.0  # Max investment per trade
max_daily_loss: float = 200.0    # Stop trading after $200 loss
```

---

## ⚙️ Environment Variables

Create a `.env` file or set these:

```bash
# Optional proxy for accessing Polymarket
POLYMARKET_PROXY=http://127.0.0.1:7890

# Test order amount
TEST_ORDER_AMOUNT=5.0

# Risk limits
MAX_SINGLE_TRADE=200.0
MAX_DAILY_LOSS=200.0

# Enable debug mode
DEBUG_MODE=false
```

---

## 📈 What Happens Next

### Remaining Week 1 Tasks (Day 3-7)

1. **Test Order System** (Day 3-4)
   - Place small probe orders
   - Collect price/volume data
   - Build baseline for comparison

2. **Momentum Detector** (Day 3-4)
   - Detect 2%+ price rises
   - Verify with volume increase
   - Calculate signal strength

3. **Trading Engine** (Day 5-6)
   - Entry logic (2-batch placement)
   - Exit logic (take profit/stop loss)
   - Position tracking

4. **Backtesting** (Day 7)
   - Historical data replay
   - Strategy validation
   - Parameter optimization

### Week 2 Tasks (Day 8-14)

5. **WebSocket Integration** (Day 8-9)
6. **Simulation Trading** (Day 8-9)
7. **Monitoring Dashboard** (Day 10-12)
8. **Risk Management** (Day 10-12)
9. **Comprehensive Testing** (Day 13-14)

---

## 🔍 Troubleshooting

### "Connection failed" error

```bash
# Try with proxy
set POLYMARKET_PROXY=http://127.0.0.1:7890
python examples\event_filter_demo.py
```

### "No events meet criteria"

This is normal during off-peak hours. Try:
1. Lower `min_24h_volume` to 250,000
2. Raise `max_spread` to 0.05
3. Check when major sports are actually playing

### Import errors

```bash
# Make sure you're in the right directory
cd c:\Users\shahj\Downloads\Project\momentum_trader
python examples\event_filter_demo.py
```

---

## 🎯 Success Criteria

By end of Week 1, you should have:

- [x] ✅ APIs working and connected
- [x] ✅ Event filter finding 3-10 qualified events
- [ ] Test orders being placed automatically
- [ ] Momentum signals being detected
- [ ] Simulated trades being executed
- [ ] Win rate >55% in backtesting

---

## 🚨 Important Reminders

### ⚠️ SIMULATION MODE IS ON

All trading is currently **SIMULATED**. No real money is involved.

To enable real trading later:
```python
# In your trading script
clob = CLOBAPI(simulation_mode=False)  # CAREFUL!
```

### Before Going Live

1. ✅ Run backtest (win rate >55%)
2. ✅ Run simulation for 72 hours
3. ✅ Test with $10-20 per trade first
4. ✅ Monitor closely for first week
5. ✅ Ensure all risk limits working

---

## 📞 Need Help?

1. **Check the logs**: System logs all operations
2. **Review README.md**: Full technical documentation
3. **Read the plan**: `polymarket_momentum_cn.md`
4. **Debug mode**: Set `DEBUG_MODE=true` for verbose output

---

## ✨ Next Action

**Run the demo now:**

```bash
cd momentum_trader
python examples\event_filter_demo.py
```

You should see 3-10 qualified events if there are live sports happening.

**Then review the results and prepare for Day 3-4: Test Orders & Momentum Detection!**

---

**Status**: ✅ Phase 1 Complete - Infrastructure Ready
**Progress**: 30% of full system (Day 2/14)
**Next**: Implement test order placement and momentum detection
