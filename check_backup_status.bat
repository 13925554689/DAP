@echo off
echo ============================================================
echo DAP 自动备份服务状态检查
echo ============================================================
echo.

echo [1] 检查Python进程...
tasklist | findstr "python.exe pythonw.exe"
if errorlevel 1 (
    echo [✗] 服务未运行
) else (
    echo [✓] 服务正在运行
)

echo.
echo [2] 检查最新日志...
if exist logs\auto_git_backup.log (
    echo 最后10行日志:
    echo ------------------------------------------------------------
    powershell -Command "Get-Content logs\auto_git_backup.log -Tail 10"
) else (
    echo [!] 日志文件不存在
)

echo.
echo [3] 检查Git状态...
git status --short

echo.
echo ============================================================
pause
