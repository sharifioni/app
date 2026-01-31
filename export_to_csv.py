"""
Export Polymarket events and markets to CSV/Excel files
This script reads the JSON files and exports all attributes to structured CSV files
"""

import json
import csv
import pandas as pd
from typing import List, Dict, Any
import os


def flatten_dict(d: Dict[str, Any], parent_key: str = '', sep: str = '_') -> Dict[str, Any]:
    """
    Flatten a nested dictionary

    Args:
        d: Dictionary to flatten
        parent_key: Parent key for nested items
        sep: Separator between parent and child keys

    Returns:
        Flattened dictionary
    """
    items = []
    for k, v in d.items():
        new_key = f"{parent_key}{sep}{k}" if parent_key else k

        if isinstance(v, dict):
            items.extend(flatten_dict(v, new_key, sep=sep).items())
        elif isinstance(v, list):
            # Convert lists to JSON strings for CSV compatibility
            items.append((new_key, json.dumps(v)))
        else:
            items.append((new_key, v))

    return dict(items)


def export_markets_to_csv(markets: List[Dict], filename: str = 'markets_export.csv'):
    """
    Export markets data to CSV file

    Args:
        markets: List of market dictionaries
        filename: Output CSV filename
    """
    if not markets:
        print(f"No markets data to export")
        return

    # Flatten all markets
    flattened_markets = []
    for market in markets:
        # Create a copy to avoid modifying original
        market_copy = market.copy()

        # Handle nested 'events' field separately if it exists
        if 'events' in market_copy:
            market_copy['events_json'] = json.dumps(market_copy.pop('events'))

        flattened = flatten_dict(market_copy)
        flattened_markets.append(flattened)

    # Get all unique keys across all markets
    all_keys = set()
    for market in flattened_markets:
        all_keys.update(market.keys())

    all_keys = sorted(list(all_keys))

    # Write to CSV
    with open(filename, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=all_keys)
        writer.writeheader()
        writer.writerows(flattened_markets)

    print(f"✓ Exported {len(markets)} markets to: {filename}")
    print(f"  Columns: {len(all_keys)}")


def export_events_to_csv(events: List[Dict], filename: str = 'events_export.csv'):
    """
    Export events data to CSV file

    Args:
        events: List of event dictionaries
        filename: Output CSV filename
    """
    if not events:
        print(f"No events data to export")
        return

    # Flatten all events
    flattened_events = []
    for event in events:
        # Create a copy to avoid modifying original
        event_copy = event.copy()

        # Handle nested 'markets' field separately
        if 'markets' in event_copy:
            event_copy['markets_json'] = json.dumps(event_copy.pop('markets'))
            event_copy['markets_count'] = len(json.loads(event_copy['markets_json']))

        # Handle nested 'series' field if it exists
        if 'series' in event_copy:
            event_copy['series_json'] = json.dumps(event_copy.pop('series'))

        flattened = flatten_dict(event_copy)
        flattened_events.append(flattened)

    # Get all unique keys across all events
    all_keys = set()
    for event in flattened_events:
        all_keys.update(event.keys())

    all_keys = sorted(list(all_keys))

    # Write to CSV
    with open(filename, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=all_keys)
        writer.writeheader()
        writer.writerows(flattened_events)

    print(f"✓ Exported {len(events)} events to: {filename}")
    print(f"  Columns: {len(all_keys)}")


def export_to_excel(markets: List[Dict], events: List[Dict], filename: str = 'polymarket_data.xlsx'):
    """
    Export both markets and events to a single Excel file with separate sheets
    Requires pandas and openpyxl

    Args:
        markets: List of market dictionaries
        events: List of event dictionaries
        filename: Output Excel filename
    """
    try:
        with pd.ExcelWriter(filename, engine='openpyxl') as writer:

            # Export markets
            if markets:
                markets_data = []
                for market in markets:
                    market_copy = market.copy()

                    # Handle nested 'events' field
                    if 'events' in market_copy:
                        market_copy['events_json'] = json.dumps(market_copy.pop('events'))

                    flattened = flatten_dict(market_copy)
                    markets_data.append(flattened)

                df_markets = pd.DataFrame(markets_data)
                df_markets.to_excel(writer, sheet_name='Markets', index=False)
                print(f"✓ Added {len(markets)} markets to Excel (sheet: Markets)")

            # Export events
            if events:
                events_data = []
                for event in events:
                    event_copy = event.copy()

                    # Handle nested 'markets' field
                    if 'markets' in event_copy:
                        event_copy['markets_json'] = json.dumps(event_copy.pop('markets'))
                        event_copy['markets_count'] = len(json.loads(event_copy['markets_json']))

                    # Handle nested 'series' field
                    if 'series' in event_copy:
                        event_copy['series_json'] = json.dumps(event_copy.pop('series'))

                    flattened = flatten_dict(event_copy)
                    events_data.append(flattened)

                df_events = pd.DataFrame(events_data)
                df_events.to_excel(writer, sheet_name='Events', index=False)
                print(f"✓ Added {len(events)} events to Excel (sheet: Events)")

        print(f"\n✓ Excel file created: {filename}")

    except ImportError as e:
        print(f"Error: {e}")
        print("\nTo export to Excel, install required packages:")
        print("  pip install pandas openpyxl")
        return False

    return True


def main():
    """Main function to export Polymarket data to CSV/Excel"""

    print("=" * 60)
    print("POLYMARKET DATA EXPORT")
    print("=" * 60)

    # Load markets data
    markets = []
    if os.path.exists('open_markets.json'):
        with open('open_markets.json', 'r', encoding='utf-8') as f:
            markets = json.load(f)
        print(f"Loaded {len(markets)} markets from open_markets.json")
    else:
        print("Warning: open_markets.json not found")

    # Load events data
    events = []
    if os.path.exists('open_events.json'):
        with open('open_events.json', 'r', encoding='utf-8') as f:
            events = json.load(f)
        print(f"Loaded {len(events)} events from open_events.json")
    else:
        print("Warning: open_events.json not found")

    if not markets and not events:
        print("\nNo data found to export. Run polymarket_fetcher.py first.")
        return

    print("\n" + "=" * 60)
    print("EXPORTING TO CSV")
    print("=" * 60)

    # Export to CSV
    if markets:
        export_markets_to_csv(markets, 'markets_export.csv')

    if events:
        export_events_to_csv(events, 'events_export.csv')

    print("\n" + "=" * 60)
    print("EXPORTING TO EXCEL")
    print("=" * 60)

    # Export to Excel (single file with multiple sheets)
    excel_success = export_to_excel(markets, events, 'polymarket_data.xlsx')

    print("\n" + "=" * 60)
    print("EXPORT SUMMARY")
    print("=" * 60)

    if markets:
        print(f"\nMarkets:")
        print(f"  - CSV: markets_export.csv ({len(markets)} records)")
        if excel_success:
            print(f"  - Excel: polymarket_data.xlsx (sheet: Markets)")

    if events:
        print(f"\nEvents:")
        print(f"  - CSV: events_export.csv ({len(events)} records)")
        if excel_success:
            print(f"  - Excel: polymarket_data.xlsx (sheet: Events)")

    print("\n✓ Export complete!")


if __name__ == "__main__":
    main()
