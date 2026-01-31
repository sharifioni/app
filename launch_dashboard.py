"""
Dashboard Launcher - Properly sets up paths for Streamlit
"""

import sys
import os

# Add project root to Python path
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

# Now we can import momentum_trader
print("Setting up paths...")
print(f"Project root: {project_root}")
print(f"Python path includes: {project_root}")

# Import streamlit and run the dashboard
import subprocess

dashboard_path = os.path.join(project_root, 'momentum_trader', 'dashboard', 'realtime_dashboard.py')

print(f"\nLaunching dashboard from: {dashboard_path}")
print("="*80)

# Set environment variable so the dashboard can find modules
env = os.environ.copy()
env['PYTHONPATH'] = project_root

# Run streamlit with proper environment
subprocess.run(['streamlit', 'run', dashboard_path], env=env)
