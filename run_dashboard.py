"""
Quick launcher for real-time dashboard
Run this from the Project root directory
"""

import sys
import os

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Note: This should be run with streamlit
print("="*80)
print("REAL-TIME DASHBOARD LAUNCHER")
print("="*80)
print("\nTo run the dashboard, use:")
print("  streamlit run run_dashboard.py")
print("\nOr from command line:")
print("  streamlit run momentum_trader\\dashboard\\realtime_dashboard.py")
print("="*80)
