@echo off
title DAP GUI

echo.
echo ============================================
echo   Starting DAP GUI
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

echo Starting DAP GUI...
python dap_launcher.py

echo.
echo DAP GUI closed
pause