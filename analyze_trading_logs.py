"""
Comprehensive Trading Log Analysis
Critical analysis for real money implementation readiness
"""

import pandas as pd
import numpy as np
from datetime import datetime
import os
import glob
from collections import defaultdict

def load_latest_logs(log_dir="trading_logs"):
    """Load the most recent trading log files"""
    files = {}

    # Find the most recent session
    price_files = glob.glob(os.path.join(log_dir, "prices_*.csv"))
    if not price_files:
        print("No log files found!")
        return None

    # Get the most recent session ID
    latest_price = max(price_files, key=os.path.getmtime)
    session_id = os.path.basename(latest_price).replace("prices_", "").replace(".csv", "")

    print(f"Analyzing session: {session_id}")
    print("=" * 80)

    # Load all files for this session
    for file_type in ["prices", "trades", "signals"]:
        filepath = os.path.join(log_dir, f"{file_type}_{session_id}.csv")
        if os.path.exists(filepath):
            try:
                files[file_type] = pd.read_csv(filepath)
                print(f"Loaded {file_type}: {len(files[file_type])} records")
            except Exception as e:
                print(f"Error loading {file_type}: {e}")

    return files, session_id


def analyze_price_data(prices_df):
    """Analyze price data for anomalies and patterns"""
    print("\n" + "=" * 80)
    print("PRICE DATA ANALYSIS")
    print("=" * 80)

    if prices_df is None or prices_df.empty:
        print("No price data available")
        return

    # Basic stats
    print(f"\nTotal price updates: {len(prices_df):,}")

    # Time range
    prices_df['timestamp'] = pd.to_numeric(prices_df['timestamp'])
    start_time = datetime.fromtimestamp(prices_df['timestamp'].min())
    end_time = datetime.fromtimestamp(prices_df['timestamp'].max())
    duration = (prices_df['timestamp'].max() - prices_df['timestamp'].min()) / 60

    print(f"Session duration: {duration:.1f} minutes")
    print(f"Start: {start_time}")
    print(f"End: {end_time}")

    # Updates per second
    updates_per_sec = len(prices_df) / (duration * 60) if duration > 0 else 0
    print(f"Average updates/second: {updates_per_sec:.1f}")

    # Unique tokens
    unique_tokens = prices_df['token_id'].nunique()
    print(f"Unique tokens tracked: {unique_tokens}")

    # Events breakdown
    print("\n--- Events Tracked ---")
    events = prices_df.groupby('event_title').agg({
        'token_id': 'nunique',
        'price': ['count', 'mean', 'std', 'min', 'max']
    }).round(4)

    for event in prices_df['event_title'].unique()[:10]:
        if pd.isna(event):
            continue
        event_data = prices_df[prices_df['event_title'] == event]
        event_str = str(event)[:60] if event else "Unknown"
        print(f"\n{event_str}...")
        print(f"  Updates: {len(event_data):,}")
        print(f"  Tokens: {event_data['token_id'].nunique()}")
        print(f"  Price range: ${event_data['price'].min():.4f} - ${event_data['price'].max():.4f}")

    # Price volatility analysis per token
    print("\n--- Price Volatility Analysis ---")
    volatility = prices_df.groupby('token_id').agg({
        'price': ['std', 'mean', 'min', 'max', 'count']
    })
    volatility.columns = ['std', 'mean', 'min', 'max', 'count']
    volatility['range_pct'] = (volatility['max'] - volatility['min']) / volatility['mean'] * 100

    high_volatility = volatility[volatility['range_pct'] > 50].sort_values('range_pct', ascending=False)
    print(f"\nHigh volatility tokens (>50% range): {len(high_volatility)}")

    if len(high_volatility) > 0:
        print("\nTop 5 most volatile:")
        for idx, row in high_volatility.head().iterrows():
            print(f"  Token: {idx[:20]}... | Range: {row['range_pct']:.1f}% | Min: ${row['min']:.4f} | Max: ${row['max']:.4f}")

    # Latency analysis
    print("\n--- Latency Analysis ---")
    prices_df['ws_latency_ms'] = pd.to_numeric(prices_df['ws_latency_ms'], errors='coerce')
    latency = prices_df['ws_latency_ms'].dropna()

    if len(latency) > 0:
        print(f"Average latency: {latency.mean():.2f}ms")
        print(f"Min latency: {latency.min():.2f}ms")
        print(f"Max latency: {latency.max():.2f}ms")
        print(f"95th percentile: {latency.quantile(0.95):.2f}ms")

    return volatility


def analyze_signals(signals_df, prices_df=None):
    """Analyze momentum signals detected"""
    print("\n" + "=" * 80)
    print("SIGNAL ANALYSIS")
    print("=" * 80)

    if signals_df is None or signals_df.empty:
        print("No signals detected in this session")
        return

    print(f"\nTotal signals detected: {len(signals_df)}")

    # Signal strength breakdown
    print("\n--- Signal Strength Distribution ---")
    strength_counts = signals_df['signal_strength'].value_counts()
    for strength, count in strength_counts.items():
        pct = count / len(signals_df) * 100
        print(f"  {strength}: {count} ({pct:.1f}%)")

    # Price change analysis
    signals_df['price_change_pct'] = pd.to_numeric(signals_df['price_change_pct'], errors='coerce')

    print("\n--- Price Change at Signal ---")
    print(f"  Average: {signals_df['price_change_pct'].mean():.2f}%")
    print(f"  Min: {signals_df['price_change_pct'].min():.2f}%")
    print(f"  Max: {signals_df['price_change_pct'].max():.2f}%")
    print(f"  Std Dev: {signals_df['price_change_pct'].std():.2f}%")

    # Extreme signals (potential false positives)
    extreme = signals_df[signals_df['price_change_pct'].abs() > 50]
    print(f"\n  ALERT: Extreme signals (>50% change): {len(extreme)}")
    if len(extreme) > 0:
        print("  These are likely FALSE SIGNALS from price cache issues!")

    # Events with most signals
    print("\n--- Events with Most Signals ---")
    event_signals = signals_df.groupby('event_title').size().sort_values(ascending=False)
    for event, count in event_signals.head(10).items():
        print(f"  {count} signals: {event[:50]}...")

    # Time distribution of signals
    signals_df['timestamp'] = pd.to_numeric(signals_df['timestamp'])
    signals_df['minute'] = ((signals_df['timestamp'] - signals_df['timestamp'].min()) / 60).astype(int)

    print("\n--- Signal Rate Over Time ---")
    signals_per_minute = signals_df.groupby('minute').size()
    print(f"  Average signals/minute: {signals_per_minute.mean():.1f}")
    print(f"  Max signals in one minute: {signals_per_minute.max()}")


def analyze_trades(trades_df):
    """Comprehensive trade analysis"""
    print("\n" + "=" * 80)
    print("TRADE ANALYSIS - CRITICAL FOR REAL MONEY")
    print("=" * 80)

    if trades_df is None or trades_df.empty:
        print("No trades executed in this session")
        return

    print(f"\nTotal trades: {len(trades_df)}")

    # Convert numeric columns
    for col in ['pnl', 'pnl_pct', 'entry_price', 'exit_price', 'amount', 'hold_duration_sec']:
        trades_df[col] = pd.to_numeric(trades_df[col], errors='coerce')

    # Win/Loss analysis
    wins = trades_df[trades_df['pnl'] > 0]
    losses = trades_df[trades_df['pnl'] <= 0]

    print("\n--- Win/Loss Statistics ---")
    print(f"  Winning trades: {len(wins)} ({len(wins)/len(trades_df)*100:.1f}%)")
    print(f"  Losing trades: {len(losses)} ({len(losses)/len(trades_df)*100:.1f}%)")

    # P&L analysis
    total_pnl = trades_df['pnl'].sum()
    avg_pnl = trades_df['pnl'].mean()

    print("\n--- P&L Analysis ---")
    print(f"  Total P&L: ${total_pnl:.2f}")
    print(f"  Average P&L per trade: ${avg_pnl:.2f}")
    print(f"  Best trade: ${trades_df['pnl'].max():.2f}")
    print(f"  Worst trade: ${trades_df['pnl'].min():.2f}")

    if len(wins) > 0:
        print(f"  Average win: ${wins['pnl'].mean():.2f}")
    if len(losses) > 0:
        print(f"  Average loss: ${losses['pnl'].mean():.2f}")

    # P&L percentage analysis
    print("\n--- P&L Percentage Analysis ---")
    print(f"  Average P&L %: {trades_df['pnl_pct'].mean():.2f}%")
    print(f"  Best trade %: {trades_df['pnl_pct'].max():.2f}%")
    print(f"  Worst trade %: {trades_df['pnl_pct'].min():.2f}%")

    # Extreme losses (RED FLAG)
    extreme_losses = trades_df[trades_df['pnl_pct'] < -30]
    print(f"\n  ** EXTREME LOSSES (>30%): {len(extreme_losses)} trades")
    if len(extreme_losses) > 0:
        print("  This indicates SERIOUS ISSUES with the strategy!")
        for _, trade in extreme_losses.head(5).iterrows():
            print(f"    {trade['event_title'][:40]}: {trade['pnl_pct']:.1f}%")

    # Exit reason analysis
    print("\n--- Exit Reasons ---")
    exit_reasons = trades_df.groupby('exit_reason').agg({
        'pnl': ['count', 'sum', 'mean'],
        'pnl_pct': 'mean'
    })
    exit_reasons.columns = ['count', 'total_pnl', 'avg_pnl', 'avg_pnl_pct']

    for reason in trades_df['exit_reason'].unique():
        reason_data = trades_df[trades_df['exit_reason'] == reason]
        print(f"\n  {reason.upper()}:")
        print(f"    Count: {len(reason_data)}")
        print(f"    Total P&L: ${reason_data['pnl'].sum():.2f}")
        print(f"    Avg P&L: ${reason_data['pnl'].mean():.2f}")
        print(f"    Avg P&L %: {reason_data['pnl_pct'].mean():.2f}%")

    # Signal strength performance
    print("\n--- Performance by Signal Strength ---")
    for strength in trades_df['signal_strength'].unique():
        strength_data = trades_df[trades_df['signal_strength'] == strength]
        wins_pct = len(strength_data[strength_data['pnl'] > 0]) / len(strength_data) * 100
        print(f"\n  {strength.upper()}:")
        print(f"    Trades: {len(strength_data)}")
        print(f"    Win rate: {wins_pct:.1f}%")
        print(f"    Avg P&L: ${strength_data['pnl'].mean():.2f}")

    # Hold duration analysis
    print("\n--- Hold Duration Analysis ---")
    print(f"  Average hold: {trades_df['hold_duration_sec'].mean():.1f} seconds")
    print(f"  Min hold: {trades_df['hold_duration_sec'].min():.1f} seconds")
    print(f"  Max hold: {trades_df['hold_duration_sec'].max():.1f} seconds")

    # Very short holds (potential issue)
    short_holds = trades_df[trades_df['hold_duration_sec'] < 1]
    print(f"\n  ** Sub-second holds: {len(short_holds)} trades")
    if len(short_holds) > 0:
        print("  This suggests trades closing immediately after opening!")

    # Amount invested analysis
    print("\n--- Position Sizing ---")
    print(f"  Average position: ${trades_df['amount'].mean():.2f}")
    print(f"  Total invested: ${trades_df['amount'].sum():.2f}")

    # Risk metrics
    print("\n" + "=" * 80)
    print("RISK METRICS - CRITICAL")
    print("=" * 80)

    # Calculate drawdown
    cumulative_pnl = trades_df['pnl'].cumsum()
    running_max = cumulative_pnl.cummax()
    drawdown = cumulative_pnl - running_max
    max_drawdown = drawdown.min()

    print(f"\n  Maximum drawdown: ${max_drawdown:.2f}")

    # Profit factor
    gross_profit = wins['pnl'].sum() if len(wins) > 0 else 0
    gross_loss = abs(losses['pnl'].sum()) if len(losses) > 0 else 1
    profit_factor = gross_profit / gross_loss if gross_loss > 0 else 0

    print(f"  Profit factor: {profit_factor:.2f}")
    print(f"  Gross profit: ${gross_profit:.2f}")
    print(f"  Gross loss: ${gross_loss:.2f}")

    # Sharpe-like ratio (simplified)
    if trades_df['pnl'].std() > 0:
        sharpe = trades_df['pnl'].mean() / trades_df['pnl'].std()
        print(f"  Risk-adjusted return: {sharpe:.3f}")

    # Win rate required for breakeven
    if len(losses) > 0 and len(wins) > 0:
        avg_win = wins['pnl'].mean()
        avg_loss = abs(losses['pnl'].mean())
        breakeven_winrate = avg_loss / (avg_win + avg_loss) * 100
        print(f"  Breakeven win rate needed: {breakeven_winrate:.1f}%")

    return trades_df


def generate_recommendations(trades_df, signals_df):
    """Generate recommendations for real money trading"""
    print("\n" + "=" * 80)
    print("RECOMMENDATIONS FOR REAL MONEY TRADING")
    print("=" * 80)

    issues = []

    if trades_df is not None and not trades_df.empty:
        trades_df['pnl'] = pd.to_numeric(trades_df['pnl'], errors='coerce')
        trades_df['pnl_pct'] = pd.to_numeric(trades_df['pnl_pct'], errors='coerce')
        trades_df['hold_duration_sec'] = pd.to_numeric(trades_df['hold_duration_sec'], errors='coerce')

        # Check for extreme losses
        extreme_losses = trades_df[trades_df['pnl_pct'] < -30]
        if len(extreme_losses) > 0:
            issues.append(f"[CRITICAL] {len(extreme_losses)} trades with >30% losses")

        # Check win rate
        win_rate = len(trades_df[trades_df['pnl'] > 0]) / len(trades_df) * 100
        if win_rate < 40:
            issues.append(f"[CRITICAL] Win rate too low ({win_rate:.1f}%)")

        # Check profit factor
        wins = trades_df[trades_df['pnl'] > 0]['pnl'].sum()
        losses = abs(trades_df[trades_df['pnl'] <= 0]['pnl'].sum())
        pf = wins / losses if losses > 0 else 0
        if pf < 1:
            issues.append(f"[CRITICAL] Profit factor < 1 ({pf:.2f})")

        # Check for sub-second holds
        short_holds = trades_df[trades_df['hold_duration_sec'] < 1]
        if len(short_holds) > len(trades_df) * 0.1:
            issues.append(f"[WARNING] {len(short_holds)} trades with sub-second holds")

        # Check total P&L
        total_pnl = trades_df['pnl'].sum()
        if total_pnl < 0:
            issues.append(f"[CRITICAL] Overall losing strategy (${total_pnl:.2f})")

    if signals_df is not None and not signals_df.empty:
        signals_df['price_change_pct'] = pd.to_numeric(signals_df['price_change_pct'], errors='coerce')

        # Check for false signals
        false_signals = signals_df[signals_df['price_change_pct'].abs() > 50]
        if len(false_signals) > 0:
            issues.append(f"[WARNING] {len(false_signals)} potential false signals (>50% change)")

    if issues:
        print("\n*** ISSUES FOUND - DO NOT TRADE REAL MONEY YET:")
        for issue in issues:
            print(f"  {issue}")

        print("\n[REQUIRED FIXES]:")
        print("  1. Implement warmup period to filter false signals (DONE)")
        print("  2. Add realistic price change cap (max 50%)")
        print("  3. Extend observation period before signal detection")
        print("  4. Add minimum hold time requirement")
        print("  5. Verify signals against actual game state changes")
        print("  6. Run for at least 24 hours with various events")
    else:
        print("\n[OK] No critical issues found. Review paper trading results carefully.")

    print("\n" + "=" * 80)
    print("MINIMUM REQUIREMENTS FOR REAL MONEY:")
    print("=" * 80)
    print("  • Win rate > 50%")
    print("  • Profit factor > 1.5")
    print("  • No trades with >20% loss")
    print("  • Consistent performance over 24+ hours")
    print("  • Test during multiple event types (LoL, CS, Dota, etc.)")
    print("  • Verify signals correlate with actual game events")


def main():
    print("=" * 80)
    print("TRADING LOG COMPREHENSIVE ANALYSIS")
    print("Critical Review for Real Money Implementation")
    print("=" * 80)

    # Load data
    result = load_latest_logs()
    if result is None:
        return

    files, session_id = result

    # Analyze each component
    volatility = None
    if 'prices' in files:
        volatility = analyze_price_data(files['prices'])

    if 'signals' in files:
        analyze_signals(files['signals'], files.get('prices'))

    trades_df = None
    if 'trades' in files:
        trades_df = analyze_trades(files['trades'])

    # Generate recommendations
    generate_recommendations(
        files.get('trades'),
        files.get('signals')
    )

    print("\n" + "=" * 80)
    print("ANALYSIS COMPLETE")
    print("=" * 80)


if __name__ == "__main__":
    main()
