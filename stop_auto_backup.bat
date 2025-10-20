@echo off
echo 正在停止自动备份服务...
taskkill /F /FI "WINDOWTITLE eq DAP*" /FI "IMAGENAME eq python.exe"
taskkill /F /FI "CommandLine eq *auto_git_backup.py*"
echo 服务已停止
pause
