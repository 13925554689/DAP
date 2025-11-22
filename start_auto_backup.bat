@echo off
echo ========================================
echo DAP v2.0 Auto Git Backup Daemon
echo ========================================
echo.
echo Starting backup daemon...
echo Monitoring: dap_v2/ directory
echo Check interval: 30 seconds
echo.
echo Press Ctrl+C to stop
echo.

python auto_git_backup.py

pause
