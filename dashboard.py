"""
Simple Dashboard Launcher
Run: python dashboard.py
"""

import sys
import os
import subprocess

# Set up paths
project_root = os.path.dirname(os.path.abspath(__file__))
os.environ['PYTHONPATH'] = project_root

dashboard_path = os.path.join(project_root, 'momentum_trader', 'dashboard', 'realtime_dashboard.py')

print("\n" + "="*80)
print("LAUNCHING REAL-TIME DASHBOARD")
print("="*80)
print(f"\nProject root: {project_root}")
print(f"Dashboard: {dashboard_path}")
print("\nStarting Streamlit...")
print("Dashboard will open in your browser automatically.")
print("\nPress Ctrl+C to stop the dashboard.")
print("="*80 + "\n")

# Run streamlit
subprocess.run(['streamlit', 'run', dashboard_path])
