# FIXED: Live Sports Event Filtering

## The Problem

The original code was showing **all active sports betting markets** as "live", including events like:
- "Super Bowl Champion 2026" (runs May 2025 - Feb 2026)
- "NBA MVP 2025" (runs for entire season)
- Long-term futures markets

These are technically "active" but not actual live games happening right now.

## The Solution

The updated code now properly filters for **truly live sporting events** using these criteria:

### What Counts as "Live":

1. **Short-duration events currently happening** (< 7 days duration)
   - Example: "Patriots vs Chiefs - Who wins?" (single game, 3 hours)

2. **Events starting very soon** (within configurable hours window, default 48h)
   - Example: "Tonight's NBA game" (starts in 6 hours)

3. **Events ending very soon** (within hours window, currently in progress)
   - Example: "Tennis match - Djokovic vs Nadal" (ends in 2 hours)

### What Does NOT Count:

- Long-duration futures markets (> 7 days)
- Events starting more than 48 hours away (unless you increase `--hours`)
- Closed or inactive events

## Usage

### Basic usage (default: 48 hour window)
```bash
python fetch_live_sports.py
```

### Looking for games happening today only (24 hour window)
```bash
python fetch_live_sports.py --hours 24
```

### Looking ahead 3 days (72 hour window)
```bash
python fetch_live_sports.py --hours 72
```

### Looking ahead a full week (168 hours)
```bash
python fetch_live_sports.py --hours 168
```

### Save results and show upcoming events
```bash
python fetch_live_sports.py --hours 48 --save --upcoming 7
```

## New Display Features

The output now shows:
- ⏰ **Countdown timers** for events starting soon
- 🔴 **LIVE indicator** for events currently happening
- 🏁 **Ended status** for completed events
- **Time remaining** in minutes/hours/days

Example output:
```
1. Warriors vs Lakers - Who wins?
   🔴 LIVE - Ends in 2.5 hours
   ID: 12345
   Start: 2026-01-22 19:00
   End: 2026-01-22 22:00
   Volume: $1,234,567.89
   Markets: 15
   Market Questions:
     - Warriors win by 10+ points?
     - Total points over 220.5?
```

## Understanding the Time Window

The `--hours` parameter controls how far ahead to look:

| Hours | Use Case |
|-------|----------|
| 6     | Only games starting in next 6 hours or currently playing |
| 24    | Games today |
| 48    | Games today and tomorrow (default) |
| 72    | Games in next 3 days |
| 168   | Games this week |

## Why This Matters

**Before the fix:**
- Showed 200+ "live" events (mostly long-term futures)
- Hard to find actual games happening now
- Mixed futures markets with live games

**After the fix:**
- Shows only 5-15 truly live events (depending on time window)
- Easy to find games happening now or very soon
- Clear separation between live games and futures markets

## For Upcoming Events

If no live events are found, use the `--upcoming` parameter to see future sports events:

```bash
python fetch_live_sports.py --upcoming 7
```

This shows sports events starting within the next 7 days, regardless of duration.

## Technical Details

The new `is_live_event()` method:
1. Calculates event duration (end_date - start_date)
2. Checks if event duration < 168 hours (7 days) - typical for actual games
3. Checks if event is happening now OR starting/ending within hours_window
4. Filters out long-duration futures/championship markets

This ensures you only see actual sporting events (games, matches, fights) that are happening now or very soon, not season-long prediction markets.
