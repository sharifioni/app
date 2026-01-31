"""
Quick launcher for real-time data collector
Run this from the Project root directory
"""

import sys
import os

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Import and run
from momentum_trader.data.realtime_collector import main
import asyncio

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\nStopped by user.")
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
