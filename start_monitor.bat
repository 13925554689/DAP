@echo off
title DAP Performance Monitor

echo.
echo ============================================
echo   Starting DAP Performance Monitor
echo ============================================
echo.

if not exist "dap_env\Scripts\activate.bat" (
    echo ERROR: Virtual environment not found
    echo Please run install.bat first
    pause
    exit /b 1
)

echo Activating virtual environment...
call dap_env\Scripts\activate.bat

echo.
echo Starting Performance Monitor with Dashboard...
echo.
echo Dashboard will be available at:
echo   Monitor: http://127.0.0.1:8080
echo   Metrics: http://127.0.0.1:8080/metrics
echo   Report: http://127.0.0.1:8080/report
echo.
echo Press Ctrl+C to stop the monitor
echo.

python performance_monitor.py --start --dashboard --port 8080

echo.
echo DAP Performance Monitor stopped
pause