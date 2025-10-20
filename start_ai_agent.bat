@echo off
title DAP AI Audit Agent

echo.
echo ============================================
echo   Starting DAP AI Audit Agent
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
echo Starting AI Audit Agent Interactive Session...
echo.
echo This will start the natural language AI audit assistant
echo You can ask questions like:
echo   - "分析公司财务状况"
echo   - "检测异常交易"
echo   - "生成审计报告"
echo.
echo Type 'help' for available commands, 'quit' to exit
echo.

python ai_audit_agent.py --interactive

echo.
echo DAP AI Audit Agent session ended
pause