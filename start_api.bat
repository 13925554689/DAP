@echo off
title DAP API Server

echo.
echo ============================================
echo   Starting DAP API Server
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

echo Starting API server...
echo.
echo Server will be available at:
echo   API: http://127.0.0.1:8000
echo   Docs: http://127.0.0.1:8000/docs
echo   Health: http://127.0.0.1:8000/api/health
echo.
echo Press Ctrl+C to stop the server
echo.

python -c "import sys; import os; sys.path.append('.'); from layer5.enhanced_api_server import start_api_server; start_api_server(host='127.0.0.1', port=8000, ai_enabled=True)"

echo.
echo DAP API server stopped
pause