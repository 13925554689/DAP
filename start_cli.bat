@echo off
title DAP CLI Mode

echo.
echo ============================================
echo   DAP CLI Mode
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
echo DAP CLI Mode ready
echo.
echo Available commands:
echo   python main_engine.py          - Test main engine
echo   python dap_launcher.py         - Start GUI
echo   python layer3/api_server.py    - Start API server
echo.
echo Important directories:
echo   data/        - Data files
echo   exports/     - Export files
echo   config/      - Configuration files
echo   logs/        - Log files
echo.
echo Common Python commands:
echo   from main_engine import get_dap_engine
echo   engine = get_dap_engine()
echo   result = engine.process('your_data_file.xlsx')
echo.

python -i -c "import sys; import os; sys.path.append('.'); from main_engine import get_dap_engine; print('DAP引擎已导入，使用 get_dap_engine() 获取实例'); print('输入 exit() 退出Python')"

echo.
echo DAP CLI mode exited
pause