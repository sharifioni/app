# How to Fetch Live Sports Events on Polymarket

## Overview

This guide explains how to fetch only live sports events from Polymarket using the updated scripts.

## What is a "Live" Sports Event?

A **live** sports event is one where:
1. The current time is between the event's start date and end date
2. The event is active (not closed or archived)
3. The event is sports-related (NFL, NBA, Soccer, UFC, etc.)

## Methods to Fetch Sports Events

### Method 1: Using the Live Sports Filter (Recommended)

The `fetch_live_sports.py` script provides the most comprehensive filtering:

```bash
# Fetch all live sports events
python fetch_live_sports.py

# With proxy
python fetch_live_sports.py --proxy http://127.0.0.1:7890

# Save to JSON file
python fetch_live_sports.py --save

# Also show upcoming events (next 7 days)
python fetch_live_sports.py --upcoming 7
```

**What it does:**
- Fetches all active events from Polymarket
- Filters for sports-related events using keyword matching
- Checks if events are currently "live" (happening now)
- Displays detailed information about each live event

**Output includes:**
- Event title, ID, and slug
- Start and end dates
- Volume and liquidity
- Number of markets
- Market questions

### Method 2: Using the Updated PolymarketAPI Class

The updated `polymarket_fetcher.py` now has a `get_sports_events()` method:

```python
from polymarket_fetcher import PolymarketAPI

# Initialize API
api = PolymarketAPI()

# Get sports events grouped by sport type
sports_events = api.get_sports_events(active_only=True)

# Access events by sport
for sport_name, events in sports_events.items():
    print(f"{sport_name}: {len(events)} events")
    for event in events:
        print(f"  - {event['title']}")
```

**What it does:**
- Fetches all available sports categories from Polymarket
- Retrieves events for each sport using tag filtering
- Returns a dictionary organized by sport type (NFL, NBA, etc.)

### Method 3: Manual Filtering with Tag IDs

You can also filter events by specific sport tags:

```python
from polymarket_fetcher import PolymarketAPI

api = PolymarketAPI()

# Get all sports tags first
sports_tags = api.get_sports_tags()

# Find the sport you want (e.g., NFL)
nfl_tag = next((tag for tag in sports_tags if tag['label'] == 'NFL'), None)

if nfl_tag:
    # Fetch events with that tag
    nfl_events = api.get_events(
        active=True,
        tag_id=nfl_tag['id'],
        limit=100
    )
```

## Common Sports Keywords Detected

The `fetch_live_sports.py` script detects these sports keywords in event titles/descriptions:

- **American Sports**: NFL, NBA, MLB, NHL, Super Bowl
- **International Sports**: Soccer, Football (European), Cricket, Rugby
- **Combat Sports**: UFC, MMA, Boxing
- **Individual Sports**: Tennis, Golf, F1, Formula 1
- **Events**: World Cup, Champions League, Premier League, Playoffs, Tournament

## Understanding the Data

### Event Structure
```json
{
  "id": "12345",
  "title": "Super Bowl Champion 2026",
  "startDate": "2025-05-01T20:30:33Z",
  "endDate": "2026-02-08T12:00:00Z",
  "active": true,
  "closed": false,
  "volume": 1234567.89,
  "liquidity": 123456.78,
  "markets": [
    {
      "question": "Will the Chiefs win?",
      "outcomes": "[\"Yes\", \"No\"]",
      "outcomePrices": "[\"0.45\", \"0.55\"]"
    }
  ]
}
```

### Determining "Live" Status

```python
from datetime import datetime, timezone

def is_live(event):
    now = datetime.now(timezone.utc)
    start = datetime.fromisoformat(event['startDate'].replace('Z', '+00:00'))
    end = datetime.fromisoformat(event['endDate'].replace('Z', '+00:00'))

    return (start <= now <= end) and event['active'] and not event['closed']
```

## Examples

### Example 1: Get All Live Sports Events

```python
from polymarket_fetcher import PolymarketAPI
from fetch_live_sports import LiveSportsFilter

# Initialize
api = PolymarketAPI()
filter = LiveSportsFilter(api)

# Get live sports
live_events = filter.get_live_sports_events()

print(f"Found {len(live_events)} live sports events")
for event in live_events:
    print(f"- {event['title']}")
```

### Example 2: Get Upcoming NFL Events

```python
from polymarket_fetcher import PolymarketAPI

api = PolymarketAPI()

# Get all sports events
sports_events = api.get_sports_events(active_only=True)

# Get NFL events
nfl_events = sports_events.get('NFL', [])

print(f"Found {len(nfl_events)} NFL events")
for event in nfl_events:
    print(f"- {event['title']}")
    print(f"  Starts: {event['startDate']}")
```

### Example 3: Export Live Sports to CSV

```python
from polymarket_fetcher import PolymarketAPI
from fetch_live_sports import LiveSportsFilter
import json

# Get live sports events
api = PolymarketAPI()
filter = LiveSportsFilter(api)
live_events = filter.get_live_sports_events()

# Save to JSON
with open('live_sports_events.json', 'w') as f:
    json.dump(live_events, f, indent=2)

# Then use export_to_csv.py to convert to CSV
# (You'll need to modify export_to_csv.py to read live_sports_events.json)
```

## Available Sports on Polymarket

Run this to see all available sports:

```python
from polymarket_fetcher import PolymarketAPI

api = PolymarketAPI()
sports = api.get_sports_tags()

for sport in sports:
    print(f"- {sport.get('label', 'Unknown')} (ID: {sport.get('id', 'N/A')})")
```

## Tips

1. **Live vs Active**: An "active" event is open for betting but may not have started yet. A "live" event is currently happening.

2. **Proxy Required**: Depending on your location, you may need a VPN or proxy to access Polymarket API.

3. **Rate Limiting**: The API may have rate limits. Add delays between requests if needed.

4. **Time Zones**: All dates are in UTC. Convert to your local timezone for display if needed.

5. **Filtering Accuracy**: The keyword-based sports detection is very comprehensive but may occasionally miss events with unusual naming or include non-sports events.

## Troubleshooting

**No live events found:**
- Sports events may not always be "live" - check upcoming events instead
- Verify your system clock is accurate (affects date comparisons)
- Some events may have already ended

**Connection errors:**
- Use a VPN or proxy: `python fetch_live_sports.py --proxy http://127.0.0.1:7890`
- Check if `gamma-api.polymarket.com` is accessible from your network

**Empty sports categories:**
- Not all sports have active events at all times
- Try fetching all events without sport filtering first
