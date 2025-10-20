@echo off
REM 启动 DAP 自动 Git + GitHub 双备份系统
echo ============================================================
echo DAP 自动 Git + GitHub 双备份系统
echo ============================================================
echo.
echo 正在启动自动备份服务...
echo.

call dap_env\Scripts\activate.bat
python auto_git_backup.py

pause
