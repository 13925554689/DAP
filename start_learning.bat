@echo off
title DAP AI Learning Mode

echo.
echo ============================================
echo   Starting DAP AI Learning Mode
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
echo Starting AI Self-Learning Manager...
echo.
echo This will start the AI model training and continuous learning system
echo Available at: http://127.0.0.1:8080 (if dashboard enabled)
echo.
echo Press Ctrl+C to stop the learning system
echo.

python self_learning_manager.py --start-worker

echo.
echo DAP AI Learning system stopped
pause