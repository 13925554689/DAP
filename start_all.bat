@echo off
title DAP Complete System Startup

echo.
echo ============================================
echo   DAP Complete System - One-Click Startup
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
echo ============================================
echo   Choose Startup Mode:
echo ============================================
echo.
echo 1. GUI Mode (Recommended for users)
echo 2. AI Agent Interactive Mode
echo 3. API Server Mode (For developers)
echo 4. Performance Monitor Dashboard
echo 5. AI Learning System
echo 6. CLI Development Mode
echo 7. Start All Services (Advanced)
echo 0. Exit
echo.

set /p choice="Enter your choice (0-7): "

if "%choice%"=="1" goto GUI_MODE
if "%choice%"=="2" goto AI_AGENT_MODE
if "%choice%"=="3" goto API_MODE
if "%choice%"=="4" goto MONITOR_MODE
if "%choice%"=="5" goto LEARNING_MODE
if "%choice%"=="6" goto CLI_MODE
if "%choice%"=="7" goto ALL_SERVICES
if "%choice%"=="0" goto EXIT

echo Invalid choice. Please try again.
pause
goto :eof

:GUI_MODE
echo.
echo Starting DAP GUI Mode...
call start_gui.bat
goto :eof

:AI_AGENT_MODE
echo.
echo Starting AI Audit Agent...
call start_ai_agent.bat
goto :eof

:API_MODE
echo.
echo Starting API Server...
call start_api.bat
goto :eof

:MONITOR_MODE
echo.
echo Starting Performance Monitor...
call start_monitor.bat
goto :eof

:LEARNING_MODE
echo.
echo Starting AI Learning System...
call start_learning.bat
goto :eof

:CLI_MODE
echo.
echo Starting CLI Development Mode...
call start_cli.bat
goto :eof

:ALL_SERVICES
echo.
echo ============================================
echo   Starting All DAP Services
echo ============================================
echo.
echo This will start multiple services in parallel:
echo - Enhanced API Server (Port 8000)
echo - Performance Monitor (Port 8080)
echo - AI Learning System
echo.
echo Press any key to continue or Ctrl+C to cancel...
pause

echo.
echo Starting Enhanced API Server...
start "DAP API Server" cmd /c "call dap_env\Scripts\activate.bat && python -c \"from layer5.enhanced_api_server import start_api_server; start_api_server(host='127.0.0.1', port=8000, ai_enabled=True)\""

timeout /t 3 /nobreak > nul

echo Starting Performance Monitor Dashboard...
start "DAP Monitor" cmd /c "call dap_env\Scripts\activate.bat && python performance_monitor.py --start --dashboard --port 8080"

timeout /t 3 /nobreak > nul

echo Starting AI Learning System...
start "DAP Learning" cmd /c "call dap_env\Scripts\activate.bat && python self_learning_manager.py --start-worker"

timeout /t 3 /nobreak > nul

echo.
echo ============================================
echo   All Services Started Successfully!
echo ============================================
echo.
echo Available endpoints:
echo.
echo 🌐 Enhanced API Server:
echo   - Main API: http://127.0.0.1:8000
echo   - API Docs: http://127.0.0.1:8000/docs
echo   - Health Check: http://127.0.0.1:8000/health
echo.
echo 📊 Performance Monitor:
echo   - Dashboard: http://127.0.0.1:8080
echo   - Metrics: http://127.0.0.1:8080/metrics
echo   - Reports: http://127.0.0.1:8080/report
echo.
echo 🧠 AI Learning System:
echo   - Background training active
echo   - Model management running
echo.
echo To use the AI Audit Agent interactively:
echo   python ai_audit_agent.py --interactive
echo.
echo To start the GUI:
echo   python dap_launcher.py
echo.
echo Press any key to open API documentation in browser...
pause

start http://127.0.0.1:8000/docs

echo.
echo All services are running in background windows.
echo Close those windows to stop individual services.
echo.
pause

goto :eof

:EXIT
echo.
echo Exiting DAP startup...
echo.
pause
goto :eof