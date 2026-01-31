"""
Sports WebSocket Test Script
Based on official Polymarket documentation

This script connects to the Sports WebSocket API and saves data to Excel.
Sports WebSocket broadcasts live sports updates when game state changes.

IMPORTANT:
- Updates only come when game scores/status change (not continuous)
- Covers ALL sports including esports (LoL, CS2, etc.)
- Requires browser headers to receive data

Usage: python test_sports_websocket.py
"""

import asyncio
import websockets
import json
import time
from datetime import datetime
from collections import defaultdict
import pandas as pd
import os

# Check websockets version for correct parameter name
try:
    import websockets.version
    WS_VERSION = websockets.version.version
    print(f"[Info] websockets library version: {WS_VERSION}")
except:
    WS_VERSION = "unknown"

# Sports WebSocket URL (from official docs)
SPORTS_WS_URL = "wss://sports-api.polymarket.com/ws"

# Store sports data
sports_data = {}
update_count = 0


def save_to_excel(data: dict, filename: str = "sports_data.xlsx"):
    """Save sports data to Excel file"""
    if not data:
        print("[Excel] No data to save")
        return

    # Convert to DataFrame
    rows = []
    for slug, game in data.items():
        rows.append({
            'Slug': slug,
            'Game ID': game.get('gameId', ''),
            'League': game.get('leagueAbbreviation', '').upper(),
            'Home Team': game.get('homeTeam', ''),
            'Away Team': game.get('awayTeam', ''),
            'Score': game.get('score', ''),
            'Status': game.get('status', ''),
            'Period': game.get('period', ''),
            'Elapsed': game.get('elapsed', ''),
            'Live': game.get('live', False),
            'Ended': game.get('ended', False),
            'Turn': game.get('turn', ''),
            'Last Update': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        })

    df = pd.DataFrame(rows)

    # Sort by league, then by live status
    df = df.sort_values(['Live', 'League', 'Slug'], ascending=[False, True, True])

    # Save to Excel
    df.to_excel(filename, index=False, sheet_name='Sports Data')
    print(f"[Excel] Saved {len(rows)} games to {filename}")


async def handle_sports_message(message: str):
    """Handle incoming sports message"""
    global update_count

    try:
        data = json.loads(message)
        slug = data.get('slug', '')

        if slug:
            sports_data[slug] = data
            update_count += 1

            # Print update
            status = data.get('status', 'Unknown')
            score = data.get('score', 'N/A')
            league = data.get('leagueAbbreviation', '').upper()
            home = data.get('homeTeam', '')
            away = data.get('awayTeam', '')
            period = data.get('period', '')
            live = data.get('live', False)

            live_indicator = "[LIVE]" if live else "[----]"
            print(f"{live_indicator} [{league}] {away} @ {home}: {score} | {status} {period}")

            # Save to Excel every 10 updates
            if update_count % 10 == 0:
                save_to_excel(sports_data)

    except json.JSONDecodeError:
        print(f"[Error] Failed to parse JSON: {message[:100]}")
    except Exception as e:
        print(f"[Error] {e}")


async def connect_sports_websocket():
    """Connect to Sports WebSocket and receive data"""
    global sports_data, update_count

    print("=" * 60)
    print("POLYMARKET SPORTS WEBSOCKET TEST")
    print("=" * 60)
    print(f"Connecting to: {SPORTS_WS_URL}")
    print("Press Ctrl+C to stop and save final data")
    print("=" * 60)
    print()

    reconnect_delay = 1

    # Browser headers required for Sports WebSocket
    # Use list of tuples format for websockets library
    headers = [
        ('User-Agent', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'),
        ('Origin', 'https://polymarket.com'),
        ('Accept-Language', 'en-US,en;q=0.9'),
    ]

    while True:
        try:
            print(f"[Debug] Attempting connection (no custom headers first)...")
            # Test basic connection without custom headers
            async with websockets.connect(SPORTS_WS_URL) as ws:
                print("[Connected] Sports WebSocket connected!")
                print("[Info] Waiting for sports updates (only sent when game state changes)...")
                print("[Info] This may take several minutes if no games are currently in action")
                print()
                reconnect_delay = 1  # Reset on successful connection
                message_count = 0

                while True:
                    try:
                        # Wait for message with timeout
                        message = await asyncio.wait_for(ws.recv(), timeout=30)
                        message_count += 1

                        # Log raw message for debugging (first few only)
                        if message_count <= 5:
                            print(f"[Debug] Raw message #{message_count}: {message[:200]}...")

                        # Handle PING/PONG (critical - must respond within 10 seconds)
                        if message == 'ping':
                            await ws.send('pong')
                            print("[Heartbeat] PING received, PONG sent")
                            continue

                        # Handle sports data
                        await handle_sports_message(message)

                    except asyncio.TimeoutError:
                        # No message for 30 seconds - log status
                        print(f"[Heartbeat] No messages for 30s (total received: {message_count}), connection still active")
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
    try:
        asyncio.run(connect_sports_websocket())
    except KeyboardInterrupt:
        print()
        print("=" * 60)
        print("STOPPING - Saving final data...")
        print("=" * 60)

        # Save final data
        save_to_excel(sports_data, "sports_data_final.xlsx")

        # Print summary
        print()
        print(f"Total games tracked: {len(sports_data)}")
        print(f"Total updates received: {update_count}")

        # Show live games
        live_games = [g for g in sports_data.values() if g.get('live')]
        print(f"Currently live games: {len(live_games)}")

        if live_games:
            print()
            print("Live Games:")
            for game in live_games:
                league = game.get('leagueAbbreviation', '').upper()
                home = game.get('homeTeam', '')
                away = game.get('awayTeam', '')
                score = game.get('score', '')
                print(f"  [{league}] {away} @ {home}: {score}")

        print()
        print("Data saved to: sports_data_final.xlsx")
        print("=" * 60)


if __name__ == "__main__":
    main()
