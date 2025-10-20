@echo off
REM DAP GitHub 备份一键配置
call dap_env\Scripts\activate.bat
python setup_github_backup.py
pause
