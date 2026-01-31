# How to Run the Dashboard

## ✅ Fixed - 3 Easy Ways to Launch

### Option 1: Double-Click (Windows) ⭐ EASIEST
```
Double-click: START_DASHBOARD.bat
```

### Option 2: Python Command
```powershell
cd C:\Users\shahj\Downloads\Project
python dashboard.py
```

### Option 3: Direct Streamlit (with PYTHONPATH)
```powershell
cd C:\Users\shahj\Downloads\Project
set PYTHONPATH=%CD%
streamlit run momentum_trader\dashboard\realtime_dashboard.py
```

---

## 🎯 What You'll See

The dashboard will:
1. Open automatically in your browser
2. Connect to Polymarket API
3. Scan for qualified events
4. Show real-time price charts
5. Alert on momentum signals
6. Auto-refresh every second

---

## 📊 Dashboard Features

### Tab 1: Live Charts
- Real-time price graphs (60-second window)
- Updates every second
- Shows momentum percentage

### Tab 2: Momentum Signals
- Alerts when price rises 2%+
- Shows signal strength (WEAK/MEDIUM/STRONG)
- Time of detection

### Tab 3: Qualified Events
- List of all tradeable events
- Scores, volume, liquidity
- Market counts

---

## ⚙️ Settings (Sidebar)

- **Auto Refresh**: Toggle 1-second updates on/off
- **Proxy URL**: Optional proxy for network access
- **Refresh Button**: Manual refresh trigger

---

## 🐛 Troubleshooting

### Error: "No module named 'momentum_trader'"

**Solution 1:**
```powershell
cd C:\Users\shahj\Downloads\Project
python dashboard.py
```

**Solution 2:**
```powershell
set PYTHONPATH=C:\Users\shahj\Downloads\Project
streamlit run momentum_trader\dashboard\realtime_dashboard.py
```

**Solution 3:**
Double-click `START_DASHBOARD.bat`

### Error: "streamlit: command not found"

**Solution:**
```powershell
pip install streamlit
```

### Dashboard is slow

**Causes:**
- Too many events being tracked
- Slow internet connection
- WebSocket disconnected

**Solutions:**
- Reduce time window in settings
- Check internet connection
- Restart dashboard

---

## 🎨 Tips

### For Best Performance:
1. Use **Chrome or Edge** browser
2. Close other tabs
3. Use **smaller time windows** (12-24 hours)
4. Reduce **number of tracked events**

### For More Events:
1. Go to `momentum_trader/config.py`
2. Lower `min_24h_volume` (currently $10)
3. Raise `max_spread` (currently 5%)
4. Restart dashboard

---

## 🚀 Quick Start

1. **Open command prompt** in Project folder
2. **Run:** `python dashboard.py`
3. **Wait** for browser to open
4. **Watch** the live data stream!

That's it! 🎉

---

## 📝 Notes

- Dashboard runs until you press **Ctrl+C**
- Data is **not saved** (only in memory)
- **Reloads** qualified events every 5 minutes
- **Auto-reconnects** if WebSocket drops

---

**Status:** ✅ Fixed and ready to use!
