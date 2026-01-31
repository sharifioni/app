import csv
import os

os.chdir(r"c:\Users\shahj\Downloads\Project\trading_logs")

with open('trades_20260131_234113.csv', 'r') as f:
    reader = csv.DictReader(f)
    trades = list(reader)

print('=== PRICE MOVEMENT ANALYSIS ===')
print()

# Analyze entry vs exit prices
price_drops = []
for t in trades:
    entry = float(t['entry_price'])
    exit_p = float(t['exit_price'])
    if entry > 0:
        change_pct = (exit_p - entry) / entry * 100
        price_drops.append(change_pct)

print(f'Average price change: {sum(price_drops)/len(price_drops):.2f}%')
print(f'Median price change: {sorted(price_drops)[len(price_drops)//2]:.2f}%')
print()

# Show some examples of big losses
print('=== EXAMPLES OF LARGE LOSSES ===')
big_losses = sorted(trades, key=lambda x: float(x['pnl']))[:10]
for t in big_losses:
    entry = float(t['entry_price'])
    exit_p = float(t['exit_price'])
    pnl = float(t['pnl'])
    hold = float(t['hold_duration_sec'])
    print(f"Entry: ${entry:.3f} -> Exit: ${exit_p:.3f} | P&L: ${pnl:.2f} | Hold: {hold:.2f}s")

print()
print('=== EXAMPLES OF WINS ===')
big_wins = sorted(trades, key=lambda x: float(x['pnl']), reverse=True)[:10]
for t in big_wins:
    entry = float(t['entry_price'])
    exit_p = float(t['exit_price'])
    pnl = float(t['pnl'])
    hold = float(t['hold_duration_sec'])
    print(f"Entry: ${entry:.3f} -> Exit: ${exit_p:.3f} | P&L: ${pnl:.2f} | Hold: {hold:.2f}s")

print()
print('=== HOLD TIME DISTRIBUTION ===')
under_1s = sum(1 for t in trades if float(t['hold_duration_sec']) < 1)
under_5s = sum(1 for t in trades if 1 <= float(t['hold_duration_sec']) < 5)
under_30s = sum(1 for t in trades if 5 <= float(t['hold_duration_sec']) < 30)
over_30s = sum(1 for t in trades if float(t['hold_duration_sec']) >= 30)
print(f"< 1 second: {under_1s} trades ({under_1s/len(trades)*100:.1f}%)")
print(f"1-5 seconds: {under_5s} trades ({under_5s/len(trades)*100:.1f}%)")
print(f"5-30 seconds: {under_30s} trades ({under_30s/len(trades)*100:.1f}%)")
print(f"> 30 seconds: {over_30s} trades ({over_30s/len(trades)*100:.1f}%)")

print()
print('=== WHAT IS HAPPENING? ===')
print()
# Check if prices are dropping immediately after entry
immediate_drops = sum(1 for t in trades if float(t['hold_duration_sec']) < 1 and float(t['pnl']) < 0)
print(f"Trades that lost money in < 1 second: {immediate_drops}")
print(f"This suggests the 'entry price' recorded is NOT the actual execution price!")
print()
print("The system is detecting a 2%+ price RISE as a signal,")
print("but by the time it 'enters', the price has already moved.")
print("The 'entry_price' in the log is the price AFTER the rise,")
print("and then the price immediately drops back down (mean reversion).")
