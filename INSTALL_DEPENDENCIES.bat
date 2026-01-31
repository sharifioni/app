@echo off
REM Install all dependencies for Momentum Trader
REM Installs to the Python version that has Streamlit

echo ============================================================
echo INSTALLING DEPENDENCIES FOR MOMENTUM TRADER
echo ============================================================
echo.

cd /d "%~dp0"

echo Detecting Python installation...
echo.

REM Check if streamlit is available
where streamlit >nul 2>&1
if %errorlevel%==0 (
    echo Streamlit found! Installing to the same Python...

    REM Get the Python path that has streamlit
    for /f "tokens=*" %%i in ('where streamlit') do set STREAMLIT_PATH=%%i
    for %%i in ("%STREAMLIT_PATH%") do set PYTHON_DIR=%%~dpi
    set PYTHON_EXE=%PYTHON_DIR%python.exe

    echo Using Python: %PYTHON_EXE%
    echo.
) else (
    echo Streamlit not found. Using default Python...
    set PYTHON_EXE=python
)

echo Installing dependencies from requirements.txt...
echo.

%PYTHON_EXE% -m pip install --upgrade pip
%PYTHON_EXE% -m pip install -r requirements.txt

echo.
echo ============================================================
echo INSTALLATION COMPLETE
echo ============================================================
echo.

echo Installed packages:
%PYTHON_EXE% -m pip list | findstr /i "requests pandas streamlit websockets openpyxl plotly"

echo.
echo ============================================================
echo You can now run the dashboard with:
echo   python dashboard.py
echo.
echo Or double-click: START_DASHBOARD.bat
echo ============================================================
echo.

pause
