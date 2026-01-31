# Polymarket Data Export Guide

## Overview

This project fetches prediction market data from Polymarket and exports it to CSV and Excel formats for detailed analysis.

## Files

- **[polymarket_fetcher.py](polymarket_fetcher.py)** - Fetches data from Polymarket API
- **[export_to_csv.py](export_to_csv.py)** - Exports JSON data to CSV/Excel files

## Understanding Events vs Markets

### Events
- **What it is**: The main prediction topic or question (parent container)
- **Example**: "How many people will Trump deport in 2025?"
- **Contains**: Multiple markets, metadata like description, dates, volume
- **Attributes**: id, title, slug, description, liquidity, volume, startDate, endDate, featured, restricted, etc.

### Markets
- **What it is**: Specific betting options within an event (child items)
- **Example**: "Will Trump deport less than 250,000?" (Yes/No)
- **Contains**: Outcomes, prices, trading volumes, liquidity data
- **Attributes**: question, outcomes, outcomePrices, volume, liquidity, spread, active, closed, endDate, etc.

**Relationship**: One Event can have multiple Markets. For example, an event about "How many people will Trump deport?" might have 5 different markets for different number ranges.

## Installation

```bash
# Install required packages
pip install requests pandas openpyxl
```

## Usage

### Step 1: Fetch Data from Polymarket

```bash
# Basic usage (may require VPN or proxy depending on your location)
python polymarket_fetcher.py

# With proxy (if needed)
python polymarket_fetcher.py --proxy http://127.0.0.1:7890

# Test connection only
python polymarket_fetcher.py --test-only
```

This creates:
- `open_events.json` - All active events
- `open_markets.json` - All active markets

### Step 2: Export to CSV/Excel

```bash
python export_to_csv.py
```

This creates:
- `markets_export.csv` - All markets with all attributes in CSV format
- `events_export.csv` - All events with all attributes in CSV format
- `polymarket_data.xlsx` - Excel file with two sheets (Markets and Events)

## Output Files

### CSV Files
- **markets_export.csv**: Contains all market attributes in flat format
  - All columns are at the root level
  - Nested data (like events array) is stored as JSON strings
  - Easy to open in Excel, Google Sheets, or any CSV viewer

- **events_export.csv**: Contains all event attributes in flat format
  - All columns are at the root level
  - Nested data (like markets array) is stored as JSON strings
  - Includes `markets_count` column showing number of markets per event

### Excel File
- **polymarket_data.xlsx**: Single file with multiple sheets
  - **Markets sheet**: All markets data
  - **Events sheet**: All events data
  - Better formatting and easier to work with than CSV
  - Can analyze both datasets in one file

## Key Attributes

### Markets
- `question` - The market question
- `volume` - Total trading volume
- `liquidity` - Current liquidity
- `outcomes` - Possible outcomes (usually ["Yes", "No"])
- `outcomePrices` - Current prices for each outcome
- `active` - Whether market is currently active
- `closed` - Whether market is closed
- `endDate` - When the market ends
- `spread` - Bid-ask spread
- `volume24hr`, `volume1wk`, `volume1mo` - Trading volumes over time

### Events
- `title` - Event title/question
- `description` - Detailed description
- `volume` - Total volume across all markets in event
- `liquidity` - Total liquidity
- `markets_count` - Number of markets in this event
- `featured` - Whether event is featured
- `restricted` - Whether event is restricted
- `commentCount` - Number of comments
- `competitive` - Competitiveness score

## Example Analysis

Once you have the CSV/Excel files, you can:

1. **Sort by volume** to find most popular markets/events
2. **Filter by date** to see upcoming events
3. **Analyze liquidity** to find well-funded markets
4. **Compare prices** to identify trading opportunities
5. **Track volume trends** (24hr, 1 week, 1 month)

## Notes

- The script flattens nested data structures for CSV compatibility
- Complex nested objects (arrays, nested dicts) are stored as JSON strings
- All attributes from the API are preserved in the export
- Excel format is recommended for better readability
