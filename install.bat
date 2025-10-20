@echo off
title DAP Install

echo.
echo ============================================
echo   DAP Installation Script
echo ============================================
echo.

echo [1/5] Checking Python...
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python not found
    echo Please install Python 3.8 or higher
    pause
    exit /b 1
)
python --version

echo.
echo [2/5] Creating virtual environment...
if exist "dap_env" (
    echo Virtual environment already exists
) else (
    python -m venv dap_env
    if errorlevel 1 (
        echo Failed to create virtual environment
        pause
        exit /b 1
    )
    echo Virtual environment created
)

echo.
echo [3/5] Activating virtual environment...
call dap_env\Scripts\activate.bat

echo.
echo [4/5] Installing dependencies...
echo Installing core packages, please wait...
python -m pip install --upgrade pip
python -m pip install pandas numpy openpyxl fastapi uvicorn pydantic requests PyYAML python-dateutil colorlog tqdm tkinterdnd2

echo.
echo [5/5] Creating directories...
if not exist "data" mkdir data
if not exist "exports" mkdir exports  
if not exist "logs" mkdir logs

echo.
echo ============================================
echo   Installation Complete!
echo ============================================
echo.
echo To start DAP:
echo   GUI Mode: start_gui.bat
echo   API Mode: start_api.bat  
echo   CLI Mode: start_cli.bat
echo.

pause