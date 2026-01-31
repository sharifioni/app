"""
CLOB WebSocket Test Script
Based on official Polymarket documentation

This script connects to the CLOB Market WebSocket and saves price data to Excel.
CLOB WebSocket requires subscribing to specific asset IDs (token IDs).

Usage: python test_clob_websocket.py
"""

import asyncio
import websockets
import json
import time
from datetime import datetime
from collections import defaultdict
import pandas as pd
import requests
import os

# CLOB WebSocket URL (from official docs)
CLOB_WS_URL = "wss://ws-subscriptions-clob.polymarket.com/ws/market"

# Gamma API for getting live events and token IDs
GAMMA_API_URL = "https://gamma-api.polymarket.com"

# Store price data
price_data = defaultdict(list)  # token_id -> [(timestamp, price), ...]
token_info = {}  # token_id -> {event_title, market_question}
update_count = 0


def get_live_token_ids():
    """Fetch live events and extract token IDs"""
    print("[API] Fetching live events from Gamma API...")

    try:
        response = requests.get(
            f"{GAMMA_API_URL}/events",
            params={'active': 'true', 'closed': 'false', 'limit': 20},
            timeout=30
        )
        response.raise_for_status()
        events = response.json()

        token_ids = []
        for event in events:
            event_title = event.get('title', 'Unknown')
            markets = event.get('markets', [])

            for market in markets:
                clob_ids_raw = market.get('clobTokenIds', '[]')
                question = market.get('question', 'Unknown')

                # Parse JSON string to list if needed
                try:
                    clob_ids = json.loads(clob_ids_raw) if isinstance(clob_ids_raw, str) else clob_ids_raw
                except json.JSONDecodeError:
                    continue

                if not clob_ids:
                    continue

                for token_id in clob_ids:
                    if token_id and len(str(token_id)) > 10:
                        token_ids.append(str(token_id))
                        token_info[str(token_id)] = {
                            'event': event_title[:50],
                            'question': question[:50]
                        }

        print(f"[API] Found {len(events)} events with {len(token_ids)} tokens")
        return token_ids

    except Exception as e:
        print(f"[API Error] {e}")
        return []


def save_to_excel(data: dict, filename: str = "clob_price_data.xlsx"):
    """Save price data to Excel file"""
    if not data:
        print("[Excel] No data to save")
        return

    # Convert to DataFrame
    rows = []
    for token_id, prices in data.items():
        info = token_info.get(token_id, {})
        for timestamp, price in prices[-100:]:  # Last 100 prices
            rows.append({
                'Token ID': token_id[:20] + '...',
                'Event': info.get('event', 'Unknown'),
                'Question': info.get('question', 'Unknown'),
                'Price': price,
                'Timestamp': datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M:%S')
            })

    if not rows:
        print("[Excel] No price data to save")
        return

    df = pd.DataFrame(rows)
    df = df.sort_values(['Token ID', 'Timestamp'])

    # Save to Excel
    df.to_excel(filename, index=False, sheet_name='Price Data')
    print(f"[Excel] Saved {len(rows)} price records to {filename}")


async def handle_clob_message(data: dict):
    """Handle incoming CLOB message"""
    global update_count

    event_type = data.get('event_type', '')

    # Handle price_change with nested price_changes array (actual Polymarket format)
    if event_type == 'price_change' and 'price_changes' in data:
        for price_change in data['price_changes']:
            token_id = price_change.get('asset_id', '')
            price_str = price_change.get('price', '0')

            try:
                price = float(price_str)
            except (ValueError, TypeError):
                continue

            if token_id and price:
                price_data[token_id].append((time.time(), price))
                update_count += 1

                # Get token info
                info = token_info.get(token_id, {})
                event = info.get('event', 'Unknown')[:30]
                question = info.get('question', '')[:20]

                print(f"[price] {event} - {question}: ${price:.4f}")

                # Keep only last 300 prices per token
                if len(price_data[token_id]) > 300:
                    price_data[token_id] = price_data[token_id][-300:]

                # Save every 20 updates
                if update_count % 20 == 0:
                    save_to_excel(dict(price_data))
        return

    # Handle last_trade_price (direct format)
    if event_type == 'last_trade_price':
        token_id = data.get('asset_id', '')
        price_str = data.get('price', '0')
        size = data.get('size', 'N/A')

        try:
            price = float(price_str)
        except (ValueError, TypeError):
            return

        if token_id and price:
            price_data[token_id].append((time.time(), price))
            update_count += 1

            info = token_info.get(token_id, {})
            event = info.get('event', 'Unknown')[:30]

            print(f"[trade] {event}: ${price:.4f} (size: {size})")

            if len(price_data[token_id]) > 300:
                price_data[token_id] = price_data[token_id][-300:]

            if update_count % 20 == 0:
                save_to_excel(dict(price_data))
        return

    # Handle book updates
    if event_type == 'book':
        token_id = data.get('asset_id', '')
        bids = data.get('bids', [])
        asks = data.get('asks', [])
        if bids and asks and token_id:
            best_bid = float(bids[0].get('price', 0))
            best_ask = float(asks[0].get('price', 0))
            mid_price = (best_bid + best_ask) / 2

            price_data[token_id].append((time.time(), mid_price))
            update_count += 1

            info = token_info.get(token_id, {})
            event = info.get('event', 'Unknown')[:30]
            print(f"[book] {event}: bid=${best_bid:.4f} ask=${best_ask:.4f} mid=${mid_price:.4f}")
        return

    # Handle tick size changes
    if event_type == 'tick_size_change':
        token_id = data.get('asset_id', '')
        old_tick = data.get('old_tick_size', '')
        new_tick = data.get('new_tick_size', '')
        print(f"[tick_size] {token_id[:20]}...: {old_tick} -> {new_tick}")


async def connect_clob_websocket(token_ids: list):
    """Connect to CLOB WebSocket and receive market data"""
    global update_count

    if not token_ids:
        print("[Error] No token IDs to subscribe to")
        return

    print()
    print("=" * 60)
    print("POLYMARKET CLOB WEBSOCKET TEST")
    print("=" * 60)
    print(f"Connecting to: {CLOB_WS_URL}")
    print(f"Subscribing to: {len(token_ids)} tokens")
    print("Press Ctrl+C to stop and save final data")
    print("=" * 60)
    print()

    reconnect_delay = 1

    while True:
        try:
            async with websockets.connect(
                CLOB_WS_URL,
                ping_interval=30,
                ping_timeout=10
            ) as ws:
                print("[Connected] CLOB WebSocket connected!")

                # Subscribe to all tokens at once (correct Polymarket format)
                subscribe_msg = {
                    "assets_ids": token_ids,
                    "type": "market"
                }
                await ws.send(json.dumps(subscribe_msg))
                print(f"[Subscribed] Sent subscription for {len(token_ids)} tokens")
                print("[Info] Waiting for price updates...")
                print()

                reconnect_delay = 1  # Reset on successful connection

                while True:
                    try:
                        # Wait for message
                        message = await asyncio.wait_for(ws.recv(), timeout=60)

                        # Parse message
                        try:
                            data = json.loads(message)

                            # Handle different message types
                            if isinstance(data, dict):
                                await handle_clob_message(data)
                            elif isinstance(data, list):
                                # Subscription confirmation - list of asset IDs
                                print(f"[Confirmed] Subscription confirmed for {len(data)} assets")
                            else:
                                print(f"[Unknown] Received: {type(data)}")

                        except json.JSONDecodeError:
                            print(f"[Parse Error] Invalid JSON: {message[:50]}...")

                    except asyncio.TimeoutError:
                        print("[Heartbeat] No messages for 60s, connection still active")
                        continue

        except websockets.ConnectionClosed as e:
            print(f"[Disconnected] Connection closed: {e}")
            print(f"[Reconnecting] Waiting {reconnect_delay}s...")
            await asyncio.sleep(reconnect_delay)
            reconnect_delay = min(reconnect_delay * 2, 30)

        except Exception as e:
            print(f"[Error] Connection error: {e}")
            print(f"[Reconnecting] Waiting {reconnect_delay}s...")
            await asyncio.sleep(reconnect_delay)
            reconnect_delay = min(reconnect_delay * 2, 30)


def main():
    """Main entry point"""
    # First, get token IDs from live events
    token_ids = get_live_token_ids()

    if not token_ids:
        print("[Error] No live tokens found. Try again later.")
        return

    # Print some token info
    print()
    print("Sample tokens to monitor:")
    for token_id in token_ids[:5]:
        info = token_info.get(token_id, {})
        print(f"  - {info.get('event', 'Unknown')[:40]}")
    print()

    try:
        asyncio.run(connect_clob_websocket(token_ids))
    except KeyboardInterrupt:
        print()
        print("=" * 60)
        print("STOPPING - Saving final data...")
        print("=" * 60)

        # Save final data
        save_to_excel(dict(price_data), "clob_price_data_final.xlsx")

        # Print summary
        print()
        print(f"Tokens with data: {len(price_data)}")
        print(f"Total updates received: {update_count}")

        # Show tokens with most updates
        if price_data:
            print()
            print("Tokens with most updates:")
            sorted_tokens = sorted(price_data.items(), key=lambda x: len(x[1]), reverse=True)
            for token_id, prices in sorted_tokens[:5]:
                info = token_info.get(token_id, {})
                print(f"  - {info.get('event', 'Unknown')[:40]}: {len(prices)} prices")

        print()
        print("Data saved to: clob_price_data_final.xlsx")
        print("=" * 60)


if __name__ == "__main__":
    main()
