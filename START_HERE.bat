@echo off
REM Quick Start Script for Windows
REM Double-click this file to run the quick start

echo ============================================================
echo POLYMARKET MOMENTUM TRADER - QUICK START
echo ============================================================
echo.

cd /d "%~dp0"

echo Checking Python installation...
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python not found!
    echo Please install Python 3.10 or higher from python.org
    pause
    exit /b 1
)

echo Python found!
echo.

python quickstart.py

pause
