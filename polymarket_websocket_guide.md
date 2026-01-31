# Polymarket WebSocket Documentation

Complete guide to using Polymarket's WebSocket APIs for real-time market data and sports updates.

---

## Table of Contents

1. [Overview](#overview)
2. [CLOB WebSocket API](#clob-websocket-api)
   - [Connection Details](#clob-connection-details)
   - [Authentication](#authentication)
   - [Market Channel](#market-channel)
   - [User Channel](#user-channel)
   - [Code Examples](#clob-code-examples)
3. [Sports WebSocket API](#sports-websocket-api)
   - [Connection Details](#sports-connection-details)
   - [Message Format](#sports-message-format)
   - [Code Examples](#sports-code-examples)
4. [Best Practices](#best-practices)
5. [Troubleshooting](#troubleshooting)

---

## Overview

Polymarket provides two main WebSocket services for real-time data streaming:

1. **CLOB WebSocket** - For order book, trading data, and market updates
2. **Sports WebSocket** - For real-time sports results and game updates

Both services use WebSocket protocol for low-latency, bidirectional communication.

---

## CLOB WebSocket API

The Central Limit Order Book (CLOB) WebSocket provides real-time updates for market data, orders, and trades.

### CLOB Connection Details

**Base URL:** `wss://ws-subscriptions-clob.polymarket.com`

**Available Channels:**
- **Market Channel:** `wss://ws-subscriptions-clob.polymarket.com/ws/market`
- **User Channel:** `wss://ws-subscriptions-clob.polymarket.com/ws/user`

### Authentication

Authentication is required **only for the User Channel**. The Market Channel is public and requires no authentication.

#### Getting API Credentials

To use the User Channel, you need API credentials (key, secret, passphrase). Generate them using the Polymarket Python client:

```python
from py_clob_client.client import ClobClient
import os

host = "https://clob.polymarket.com"
private_key = os.getenv("PRIVATE_KEY")  # Your wallet private key
chain_id = 137  # Polygon mainnet

client = ClobClient(host, key=private_key, chain_id=chain_id)
api_creds = client.create_or_derive_api_creds()

print(f"API Key: {api_creds.api_key}")
print(f"Secret: {api_creds.api_secret}")
print(f"Passphrase: {api_creds.api_passphrase}")
```

#### Auth Object Structure

```typescript
interface Auth {
  apiKey: string;
  secret: string;
  passphrase: string;
}
```

### Market Channel

The Market Channel provides public updates for market data including price changes, order book updates, and trades.

#### Subscription Message Format

```json
{
  "assets_ids": ["asset_id_1", "asset_id_2"],
  "type": "market"
}
```

**Fields:**
- `assets_ids` (string[]): Array of asset IDs (token IDs) to monitor
- `type` (string): Channel type - must be "market"

#### Event Types

##### 1. Book Event
Triggered when the order book changes (new orders, cancellations).

```json
{
  "event_type": "book",
  "asset_id": "76043073756653678226373981964075...",
  "market": "0xbd31dc8a20211944f6b70f31557f1001...",
  "timestamp": "1672290687",
  "hash": "abc123...",
  "bids": [
    {
      "price": "0.55",
      "size": "100"
    }
  ],
  "asks": [
    {
      "price": "0.56",
      "size": "150"
    }
  ]
}
```

##### 2. Price Change Event
Emitted when best bid/ask prices change.

```json
{
  "event_type": "price_change",
  "asset_id": "76043073756653678226373981964075...",
  "market": "0xbd31dc8a20211944f6b70f31557f1001...",
  "price": "0.55",
  "timestamp": "1672290687"
}
```

##### 3. Last Trade Price Event
Triggered when a trade is executed.

```json
{
  "asset_id": "114122071509644379678018727908709...",
  "event_type": "last_trade_price",
  "fee_rate_bps": "0",
  "market": "0x6a67b9d828d53862160e470329ffea52...",
  "price": "0.456",
  "side": "BUY",
  "size": "219.217767",
  "timestamp": "1750428146322"
}
```

##### 4. Tick Size Change Event
Emitted when market tick size changes (happens at price > 0.96 or < 0.04).

```json
{
  "event_type": "tick_size_change",
  "asset_id": "65818619657568813474341868652308...",
  "market": "0xbd31dc8a20211944f6b70f31557f1001...",
  "old_tick_size": "0.01",
  "new_tick_size": "0.001",
  "timestamp": "100000000"
}
```

### User Channel

The User Channel provides authenticated updates for user-specific activities including orders and trades.

#### Subscription Message Format

```json
{
  "auth": {
    "apiKey": "your_api_key",
    "secret": "your_secret",
    "passphrase": "your_passphrase"
  },
  "markets": ["market_id_1", "market_id_2"],
  "type": "user"
}
```

**Fields:**
- `auth` (Auth): Authentication credentials
- `markets` (string[]): Array of market IDs (condition IDs) to monitor
- `type` (string): Channel type - must be "user"

#### Event Types

##### 1. Trade Message
Emitted when:
- A market order is matched ("MATCHED")
- A limit order is included in a trade ("MATCHED")
- Trade status changes ("MINED", "CONFIRMED", "RETRYING", "FAILED")

```json
{
  "asset_id": "52114319501245915516055106046884...",
  "event_type": "trade",
  "id": "28c4d2eb-bbea-40e7-a9f0-b2fdb56b2c2e",
  "last_update": "1672290701",
  "maker_orders": [
    {
      "asset_id": "52114319501245915516055106046884...",
      "matched_amount": "10",
      "order_id": "0xff354cd7ca7539dfa9c28d90943ab5779...",
      "outcome": "YES",
      "owner": "9180014b-33c8-9240-a14b-bdca11c0a465",
      "price": "0.57"
    }
  ],
  "market": "0xbd31dc8a20211944f6b70f31557f1001...",
  "matchtime": "1672290701",
  "outcome": "YES",
  "owner": "9180014b-33c8-9240-a14b-bdca11c0a465",
  "price": "0.57",
  "side": "BUY",
  "size": "10",
  "status": "MATCHED",
  "taker_order_id": "0x06bc63e346ed4ceddce9efd6b3af37c8...",
  "timestamp": "1672290701"
}
```

##### 2. Order Message
Emitted for order lifecycle events (placement, cancellation, etc.).

```json
{
  "asset_id": "52114319501245915516055106046884...",
  "associate_trades": null,
  "event_type": "order",
  "id": "0xff354cd7ca7539dfa9c28d90943ab5779...",
  "market": "0xbd31dc8a20211944f6b70f31557f1001...",
  "order_owner": "9180014b-33c8-9240-a14b-bdca11c0a465",
  "original_size": "10",
  "outcome": "YES",
  "owner": "9180014b-33c8-9240-a14b-bdca11c0a465",
  "price": "0.57",
  "side": "SELL",
  "size_matched": "0",
  "timestamp": "1672290687",
  "type": "PLACEMENT"
}
```

### Dynamic Subscription Management

After connecting, you can subscribe/unsubscribe to additional assets without reconnecting:

```json
{
  "assets_ids": ["new_asset_id_1", "new_asset_id_2"],
  "markets": ["new_market_id_1"],
  "operation": "subscribe",
  "custom_feature_enabled": false
}
```

**Operations:**
- `"subscribe"` - Add new assets/markets to monitor
- `"unsubscribe"` - Remove assets/markets from monitoring

### CLOB Code Examples

#### JavaScript/TypeScript - Market Channel

```javascript
const WebSocket = require('ws');

const MARKET_CHANNEL_URL = 'wss://ws-subscriptions-clob.polymarket.com/ws/market';
const assetIds = [
  '76043073756653678226373981964075...',
  '114122071509644379678018727908709...'
];

const ws = new WebSocket(MARKET_CHANNEL_URL);

ws.on('open', () => {
  console.log('Connected to Market Channel');
  
  // Subscribe to assets
  const subscribeMessage = {
    assets_ids: assetIds,
    type: 'market'
  };
  
  ws.send(JSON.stringify(subscribeMessage));
});

ws.on('message', (data) => {
  const message = JSON.parse(data.toString());
  
  switch(message.event_type) {
    case 'book':
      console.log('Order book update:', message);
      break;
    case 'price_change':
      console.log('Price changed:', message.price);
      break;
    case 'last_trade_price':
      console.log('Trade executed:', message.price, message.size);
      break;
    case 'tick_size_change':
      console.log('Tick size changed:', message.old_tick_size, '->', message.new_tick_size);
      break;
  }
});

ws.on('error', (error) => {
  console.error('WebSocket error:', error);
});

ws.on('close', () => {
  console.log('Disconnected from Market Channel');
});
```

#### Python - User Channel

```python
from websocket import WebSocketApp
import json

USER_CHANNEL_URL = 'wss://ws-subscriptions-clob.polymarket.com/ws/user'

class PolymarketUserWebSocket:
    def __init__(self, api_key, secret, passphrase, markets):
        self.api_key = api_key
        self.secret = secret
        self.passphrase = passphrase
        self.markets = markets
        self.ws = None
    
    def on_open(self, ws):
        print("Connected to User Channel")
        
        subscribe_message = {
            "auth": {
                "apiKey": self.api_key,
                "secret": self.secret,
                "passphrase": self.passphrase
            },
            "markets": self.markets,
            "type": "user"
        }
        
        ws.send(json.dumps(subscribe_message))
    
    def on_message(self, ws, message):
        data = json.loads(message)
        
        if data.get('event_type') == 'trade':
            print(f"Trade Update: {data['status']} - {data['size']} @ {data['price']}")
        elif data.get('event_type') == 'order':
            print(f"Order Update: {data['type']} - {data['side']} {data['outcome']}")
    
    def on_error(self, ws, error):
        print(f"Error: {error}")
    
    def on_close(self, ws, close_status_code, close_msg):
        print("Disconnected from User Channel")
    
    def connect(self):
        self.ws = WebSocketApp(
            USER_CHANNEL_URL,
            on_open=self.on_open,
            on_message=self.on_message,
            on_error=self.on_error,
            on_close=self.on_close
        )
        self.ws.run_forever()

# Usage
markets = ["0xbd31dc8a20211944f6b70f31557f1001..."]
ws_client = PolymarketUserWebSocket(
    api_key="your_api_key",
    secret="your_secret",
    passphrase="your_passphrase",
    markets=markets
)
ws_client.connect()
```

---

## Sports WebSocket API

The Sports WebSocket provides real-time updates for sports events including scores, periods, and game status.

### Sports Connection Details

**Endpoint:** `wss://sports-api.polymarket.com/ws`

**Key Features:**
- No authentication required (public broadcast)
- Automatic updates for all active sports events
- No subscription message needed - just connect and receive data

### Connection Management

#### Ping/Pong Heartbeat

The server sends PING messages every 5 seconds. **You must respond with PONG within 10 seconds** or the connection will be terminated.

| Parameter | Value | Description |
|-----------|-------|-------------|
| PING Interval | 5 seconds | How often server sends PING |
| PONG Timeout | 10 seconds | Response time limit |

#### Session Affinity

The server uses cookie-based session affinity (`sports-results` cookie) to maintain connection to the same backend. This is handled automatically by browsers.

### Sports Message Format

#### sport_result Message Structure

```typescript
interface SportResult {
  gameId: number;           // Unique game identifier
  leagueAbbreviation: string; // League code (e.g., "nfl", "nba")
  homeTeam: string;         // Home team abbreviation
  awayTeam: string;         // Away team abbreviation
  status: string;           // Game status (see below)
  score: string;            // Current score
  period: string;           // Current period/quarter
  elapsed?: string;         // Time elapsed in period
  live: boolean;            // Whether game is live
  ended: boolean;           // Whether game has ended
  turn?: string;            // (NFL/CFB only) Team with possession
  slug: string;             // Unique identifier for the game
}
```

#### Game Status Values

- `"Scheduled"` - Game hasn't started yet
- `"InProgress"` - Game is currently being played
- `"Halftime"` - Game is at halftime
- `"Finished"` - Game has completed
- `"Postponed"` - Game has been postponed
- `"Canceled"` - Game has been canceled

#### Period Values by Sport

Different sports use different period formats:

- **NFL/CFB:** `"Q1"`, `"Q2"`, `"Q3"`, `"Q4"`, `"OT"`
- **NBA/NCAA Basketball:** `"Q1"`, `"Q2"`, `"Q3"`, `"Q4"`, `"OT"`
- **NHL:** `"1"`, `"2"`, `"3"`, `"OT"`, `"SO"`
- **MLB:** `"1"`, `"2"`, `"3"`, ... `"9"`, `"Extra"`
- **Soccer:** `"1H"`, `"2H"`, `"ET"`, `"Pens"`
- **Esports (CS2):** `"1/3"`, `"2/3"`, etc. (Best of N format)

#### Score Format

Score format varies by sport:

- **Most Sports:** `"home-away"` (e.g., `"3-16"`)
- **Esports:** `"map_scores|game_score|format"` (e.g., `"000-000|2-0|Bo3"`)

### Example Messages

#### NFL Game In Progress

```json
{
  "gameId": 19439,
  "leagueAbbreviation": "nfl",
  "homeTeam": "LAC",
  "awayTeam": "BUF",
  "status": "InProgress",
  "score": "3-16",
  "period": "Q4",
  "elapsed": "5:18",
  "live": true,
  "ended": false,
  "turn": "lac",
  "slug": "nfl-buf-lac-2024-01-29"
}
```

#### Esports (CS2) Match Finished

```json
{
  "gameId": 1317359,
  "leagueAbbreviation": "cs2",
  "homeTeam": "ARCRED",
  "awayTeam": "The glecs",
  "status": "Finished",
  "score": "000-000|2-0|Bo3",
  "period": "2/3",
  "live": false,
  "ended": true,
  "slug": "cs2-theglecs-arcred-2024-01-29"
}
```

#### NBA Game at Halftime

```json
{
  "gameId": 55678,
  "leagueAbbreviation": "nba",
  "homeTeam": "LAL",
  "awayTeam": "GSW",
  "status": "Halftime",
  "score": "58-52",
  "period": "Q2",
  "elapsed": "0:00",
  "live": true,
  "ended": false,
  "slug": "nba-gsw-lal-2024-01-29"
}
```

### Slug Format

The `slug` field is a unique identifier following this pattern:

```
{league}-{away_team}-{home_team}-{date}
```

Examples:
- `"nfl-buf-lac-2024-01-29"`
- `"nba-gsw-lal-2024-01-29"`
- `"cs2-theglecs-arcred-2024-01-29"`

**Use the slug as a unique key** when updating your application state.

### Sports Code Examples

#### JavaScript/TypeScript - Basic Connection

```javascript
const ws = new WebSocket('wss://sports-api.polymarket.com/ws');

ws.onopen = () => {
  console.log('Connected to Sports WebSocket');
};

ws.onmessage = (event) => {
  // Handle PING/PONG
  if (event.data === 'ping') {
    ws.send('pong');
    return;
  }
  
  // Parse sports update
  const data = JSON.parse(event.data);
  console.log(`${data.slug}: ${data.score} - ${data.status} (${data.period})`);
};

ws.onclose = () => {
  console.log('Disconnected from Sports WebSocket');
  // Implement reconnection logic
  setTimeout(() => {
    console.log('Reconnecting...');
    // Recreate connection
  }, 1000);
};

ws.onerror = (error) => {
  console.error('WebSocket error:', error);
};
```

#### JavaScript/TypeScript - Complete Implementation with State Management

```javascript
class SportsWebSocketClient {
  constructor() {
    this.ws = null;
    this.reconnectDelay = 1000;
    this.maxReconnectDelay = 30000;
    this.sportsData = new Map(); // Store by slug
  }
  
  connect() {
    this.ws = new WebSocket('wss://sports-api.polymarket.com/ws');
    
    this.ws.onopen = () => {
      console.log('Connected to Sports WebSocket');
      this.reconnectDelay = 1000; // Reset reconnect delay
    };
    
    this.ws.onmessage = (event) => {
      // Handle PING
      if (event.data === 'ping') {
        if (this.ws.readyState === WebSocket.OPEN) {
          this.ws.send('pong');
        }
        return;
      }
      
      try {
        const data = JSON.parse(event.data);
        this.handleSportsUpdate(data);
      } catch (error) {
        console.error('Error parsing message:', error);
      }
    };
    
    this.ws.onclose = (event) => {
      console.log(`Disconnected: ${event.code} - ${event.reason}`);
      this.handleReconnect();
    };
    
    this.ws.onerror = (error) => {
      console.error('WebSocket error:', error);
    };
  }
  
  handleSportsUpdate(data) {
    const { slug, gameId, status, score, period, live, ended } = data;
    
    // Update or insert based on slug (unique identifier)
    this.sportsData.set(slug, data);
    
    // Your application logic here
    console.log(`Update: ${slug}`);
    console.log(`  Status: ${status}`);
    console.log(`  Score: ${score}`);
    console.log(`  Period: ${period}`);
    console.log(`  Live: ${live}`);
    
    // Emit event for UI update
    this.onUpdate?.(data);
  }
  
  handleReconnect() {
    console.log(`Reconnecting in ${this.reconnectDelay}ms...`);
    
    setTimeout(() => {
      this.connect();
    }, this.reconnectDelay);
    
    // Exponential backoff
    this.reconnectDelay = Math.min(
      this.reconnectDelay * 2,
      this.maxReconnectDelay
    );
  }
  
  disconnect() {
    if (this.ws) {
      this.ws.close();
      this.ws = null;
    }
  }
  
  getGameBySlug(slug) {
    return this.sportsData.get(slug);
  }
  
  getAllGames() {
    return Array.from(this.sportsData.values());
  }
  
  getLiveGames() {
    return this.getAllGames().filter(game => game.live);
  }
}

// Usage
const client = new SportsWebSocketClient();

client.onUpdate = (data) => {
  // Update your UI here
  console.log('Game updated:', data);
};

client.connect();
```

#### Python - Sports WebSocket Client

```python
import websocket
import json
import time
import threading

class SportsWebSocketClient:
    def __init__(self, on_update=None):
        self.url = 'wss://sports-api.polymarket.com/ws'
        self.ws = None
        self.sports_data = {}
        self.on_update = on_update
        self.running = False
    
    def on_open(self, ws):
        print("Connected to Sports WebSocket")
        self.running = True
    
    def on_message(self, ws, message):
        # Handle PING/PONG
        if message == 'ping':
            ws.send('pong')
            return
        
        try:
            data = json.loads(message)
            self.handle_sports_update(data)
        except json.JSONDecodeError as e:
            print(f"Error parsing message: {e}")
    
    def handle_sports_update(self, data):
        slug = data.get('slug')
        if slug:
            self.sports_data[slug] = data
            
            print(f"Update: {slug}")
            print(f"  Status: {data['status']}")
            print(f"  Score: {data['score']}")
            print(f"  Period: {data['period']}")
            
            if self.on_update:
                self.on_update(data)
    
    def on_error(self, ws, error):
        print(f"Error: {error}")
    
    def on_close(self, ws, close_status_code, close_msg):
        print(f"Disconnected: {close_status_code} - {close_msg}")
        self.running = False
        
        # Auto-reconnect after 1 second
        if self.running:
            time.sleep(1)
            self.connect()
    
    def connect(self):
        self.ws = websocket.WebSocketApp(
            self.url,
            on_open=self.on_open,
            on_message=self.on_message,
            on_error=self.on_error,
            on_close=self.on_close
        )
        
        # Run in separate thread
        ws_thread = threading.Thread(target=self.ws.run_forever)
        ws_thread.daemon = True
        ws_thread.start()
    
    def disconnect(self):
        self.running = False
        if self.ws:
            self.ws.close()
    
    def get_game_by_slug(self, slug):
        return self.sports_data.get(slug)
    
    def get_all_games(self):
        return list(self.sports_data.values())
    
    def get_live_games(self):
        return [game for game in self.sports_data.values() if game.get('live')]

# Usage
def on_game_update(data):
    print(f"Game updated: {data['slug']}")

client = SportsWebSocketClient(on_update=on_game_update)
client.connect()

# Keep the program running
try:
    while True:
        time.sleep(1)
except KeyboardInterrupt:
    client.disconnect()
```

#### React Hook - Sports WebSocket

```typescript
import { useEffect, useState } from 'react';

interface SportResult {
  gameId: number;
  slug: string;
  leagueAbbreviation: string;
  homeTeam: string;
  awayTeam: string;
  status: string;
  score: string;
  period: string;
  elapsed?: string;
  live: boolean;
  ended: boolean;
  turn?: string;
}

export function useSportsWebSocket() {
  const [games, setGames] = useState<Map<string, SportResult>>(new Map());
  const [connected, setConnected] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let ws: WebSocket | null = null;
    let reconnectTimeout: NodeJS.Timeout;

    const connect = () => {
      ws = new WebSocket('wss://sports-api.polymarket.com/ws');

      ws.onopen = () => {
        console.log('Sports WebSocket connected');
        setConnected(true);
        setError(null);
      };

      ws.onmessage = (event) => {
        // Handle PING/PONG
        if (event.data === 'ping') {
          ws?.send('pong');
          return;
        }

        try {
          const data: SportResult = JSON.parse(event.data);
          
          setGames(prev => {
            const updated = new Map(prev);
            updated.set(data.slug, data);
            return updated;
          });
        } catch (err) {
          console.error('Error parsing sports update:', err);
        }
      };

      ws.onerror = (err) => {
        console.error('Sports WebSocket error:', err);
        setError('WebSocket connection error');
      };

      ws.onclose = () => {
        console.log('Sports WebSocket disconnected');
        setConnected(false);
        
        // Reconnect after 1 second
        reconnectTimeout = setTimeout(connect, 1000);
      };
    };

    connect();

    // Cleanup
    return () => {
      if (ws) {
        ws.close();
      }
      if (reconnectTimeout) {
        clearTimeout(reconnectTimeout);
      }
    };
  }, []);

  const getLiveGames = () => {
    return Array.from(games.values()).filter(game => game.live);
  };

  const getGameBySlug = (slug: string) => {
    return games.get(slug);
  };

  return {
    games: Array.from(games.values()),
    liveGames: getLiveGames(),
    connected,
    error,
    getGameBySlug
  };
}

// Usage in component
function SportsTracker() {
  const { games, liveGames, connected } = useSportsWebSocket();

  return (
    <div>
      <h2>Sports Tracker {connected ? '🟢' : '🔴'}</h2>
      <h3>Live Games ({liveGames.length})</h3>
      {liveGames.map(game => (
        <div key={game.slug}>
          {game.awayTeam} @ {game.homeTeam}: {game.score} - {game.period}
        </div>
      ))}
    </div>
  );
}
```

---

## Best Practices

### General WebSocket Best Practices

1. **Always Handle Reconnection**
   - Implement exponential backoff for reconnection attempts
   - Start with 1 second delay, double each time, cap at 30 seconds
   - Track connection state to avoid multiple simultaneous connections

2. **Manage Message Processing**
   - Parse messages in try-catch blocks
   - Log unknown message types for debugging
   - Use async processing for heavy operations

3. **Monitor Connection Health**
   - Track last message timestamp
   - Implement connection timeout detection
   - Log connection events for debugging

4. **Handle Browser Tab Visibility**
   - Browsers may throttle inactive tabs
   - Reconnect when tab becomes visible again
   - Consider using Page Visibility API

### CLOB-Specific Best Practices

1. **Efficient Asset Subscription**
   - Start with fewer assets, add more as needed
   - Use dynamic subscription for adding/removing assets
   - Group related assets together

2. **Order Book Management**
   - Maintain local order book state
   - Apply book updates incrementally
   - Validate book integrity periodically

3. **Authentication Security**
   - Never expose API credentials in client-side code
   - Store credentials securely (environment variables)
   - Rotate credentials regularly
   - Use separate credentials for testing

4. **Rate Limiting**
   - Be mindful of subscription limits
   - Don't rapidly subscribe/unsubscribe
   - Batch subscription changes when possible

### Sports-Specific Best Practices

1. **PING/PONG Handling**
   - Always respond to PING immediately
   - Check WebSocket state before sending PONG
   - Log missed PONG attempts

2. **State Management**
   - Use slug as unique identifier, not gameId
   - Store games in a Map/Dictionary for O(1) lookup
   - Clean up ended games periodically

3. **UI Updates**
   - Debounce rapid updates for the same game
   - Use React.memo or similar for performance
   - Only re-render affected components

4. **Data Validation**
   - Validate message structure before processing
   - Handle missing optional fields gracefully
   - Log unexpected data formats

---

## Troubleshooting

### CLOB WebSocket Issues

#### Connection Refused
**Problem:** Cannot connect to WebSocket

**Solutions:**
- Verify URL is correct: `wss://ws-subscriptions-clob.polymarket.com/ws/market` or `/ws/user`
- Check network connectivity
- Verify geographic restrictions (some regions may be blocked)
- Check if your IP is rate-limited

#### Authentication Failed (User Channel)
**Problem:** Connection closes immediately after subscribing

**Solutions:**
- Verify API credentials are correct
- Ensure credentials are for Polygon mainnet (chain_id=137)
- Check that credentials haven't expired
- Regenerate credentials if necessary

#### No Messages Received
**Problem:** Connected but not receiving updates

**Solutions:**
- Verify subscription message is sent correctly
- Check asset IDs / market IDs are valid
- Ensure markets are active (not resolved)
- Check for errors in browser console / logs

#### Frequent Disconnections
**Problem:** WebSocket keeps disconnecting

**Solutions:**
- Implement proper reconnection logic
- Check for network instability
- Verify you're not exceeding rate limits
- Reduce number of subscribed assets

### Sports WebSocket Issues

#### Connection Drops
**Problem:** Sports WebSocket disconnects frequently

**Solutions:**
- **Implement PING/PONG:** Most common issue - you MUST respond to PING
- Check connection timeout (10 seconds)
- Verify your PONG response is sent correctly
- Monitor network stability

#### Missing PONG Response
**Problem:** Connection terminated after 10 seconds

**Solution:**
```javascript
ws.onmessage = (event) => {
  if (event.data === 'ping') {
    console.log('Received PING, sending PONG');
    ws.send('pong');
    return;
  }
  // Handle other messages...
};
```

#### Duplicate Game Updates
**Problem:** Receiving multiple updates for the same game

**Solutions:**
- Use slug (not gameId) as unique identifier
- Update state by slug, don't append
- Implement proper state merging logic

#### Browser Tab Issues
**Problem:** Connection drops when tab is inactive

**Solutions:**
```javascript
document.addEventListener('visibilitychange', () => {
  if (!document.hidden && ws.readyState !== WebSocket.OPEN) {
    console.log('Tab active, reconnecting...');
    connect();
  }
});
```

### Common Issues (Both APIs)

#### Memory Leaks
**Problem:** Application memory grows over time

**Solutions:**
- Clean up old/ended games/orders
- Implement data pruning strategy
- Remove event listeners on disconnect
- Clear intervals/timeouts

#### Parse Errors
**Problem:** JSON.parse() fails

**Solutions:**
- Wrap parsing in try-catch
- Log raw message for debugging
- Check for non-JSON messages (like "ping")
- Validate message structure

#### Rate Limiting
**Problem:** Too many requests/connections

**Solutions:**
- Limit concurrent connections
- Use dynamic subscriptions instead of reconnecting
- Batch subscription changes
- Implement request queuing

---

## Additional Resources

### Official Documentation
- [Polymarket CLOB Documentation](https://docs.polymarket.com/developers/CLOB/introduction)
- [Sports WebSocket Documentation](https://docs.polymarket.com/developers/sports-websocket/overview)
- [Polymarket GitHub](https://github.com/polymarket)

### Community Libraries

#### TypeScript/JavaScript
- [@nevuamarkets/poly-websockets](https://www.npmjs.com/package/@nevuamarkets/poly-websockets) - Production-ready CLOB WebSocket client
- [Polymarket Real-Time Data Client](https://github.com/Polymarket/real-time-data-client) - Official TypeScript client

#### Python
- [py-clob-client](https://github.com/Polymarket/py-clob-client) - Official Python CLOB client

#### Rust
- [polymarket-api](https://lib.rs/crates/polymarket-api) - Rust WebSocket client

#### Go
- [go-polymarket-real-time-data-client](https://github.com/Matthew17-21/go-polymarket-real-time-data-client)
- [polymarket-go-real-time-data-client](https://github.com/ivanzzeth/polymarket-go-real-time-data-client)

### Support
- [Polymarket Discord](https://discord.gg/polymarket) - #devs channel
- [Twitter/X](https://x.com/polymarket)

---

## Conclusion

This guide covers both Polymarket WebSocket APIs comprehensively. The CLOB WebSocket is ideal for trading applications requiring real-time market data, while the Sports WebSocket provides live sports results for betting and tracking applications.

Key takeaways:
- **CLOB WebSocket:** Requires authentication for user data, provides detailed market/trade updates
- **Sports WebSocket:** Public access, simple connection, MUST handle PING/PONG
- **Both:** Implement proper reconnection, error handling, and state management

For production applications, consider using community libraries which handle many edge cases and provide robust implementations.
