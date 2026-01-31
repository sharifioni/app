@echo off
REM Launch Streamlit Dashboard with proper Python paths
REM Double-click this file to start the dashboard

echo ============================================================
echo POLYMARKET MOMENTUM TRADER - DASHBOARD LAUNCHER
echo ============================================================
echo.

cd /d "%~dp0"

REM Set Python path to include project root
set PYTHONPATH=%CD%

echo Setting up environment...
echo Project root: %CD%
echo.

echo Starting Streamlit dashboard...
echo Press Ctrl+C to stop the dashboard
echo.
echo ============================================================
echo.

streamlit run momentum_trader\dashboard\realtime_dashboard.py

pause
