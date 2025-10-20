@echo off
REM 测试 GitHub 备份功能
call dap_env\Scripts\activate.bat
python test_github_backup.py
pause
