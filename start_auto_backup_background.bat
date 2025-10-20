@echo off
REM 后台启动自动备份服务（最小化窗口）
start "DAP Auto Backup" /min cmd /c "cd /d %~dp0 && call dap_env\Scripts\activate.bat && python auto_git_backup.py"
echo DAP 自动备份服务已在后台启动
echo 查看状态: tasklist | findstr python
echo 查看日志: type logs\auto_git_backup.log
timeout /t 3
