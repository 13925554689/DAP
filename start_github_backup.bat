@echo off
REM 启动 DAP GitHub 自动备份服务
echo 正在启动 DAP GitHub 自动备份服务...

call dap_env\Scripts\activate.bat
python start_github_backup.py

pause
