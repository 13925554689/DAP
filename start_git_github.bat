@echo off
chcp 65001 >nul
echo.
echo ============================================================
echo            DAP Git + GitHub 功能一键启动
echo ============================================================
echo.

echo 📁 当前目录: %cd%
echo.

echo 🔍 检查Git状态...
git status --porcelain >nul 2>&1
if %errorlevel% neq 0 (
    echo ❌ Git未安装或未初始化
    echo    请先安装Git并初始化仓库
    pause
    exit /b 1
)

echo ✅ Git已就绪
echo.

echo 📝 提交所有更改...
git add .
git commit -m "Auto commit: Update DAP system" >nul 2>&1
if %errorlevel% equ 0 (
    echo ✅ 更改已提交
) else (
    echo ⚠️ 无更改需要提交或提交失败
)

echo.
echo 🚀 推送代码到GitHub...
echo    注意: 如果有安全限制，推送可能需要手动处理
git push origin master
if %errorlevel% neq 0 (
    echo ❌ 推送失败，可能由于GitHub安全机制
    echo    请手动检查并处理敏感信息
)

echo.
echo 💾 触发GitHub备份...
python trigger_github_backup.py

echo.
echo ============================================================
echo 🎉 Git + GitHub 功能启动完成!
echo ============================================================
echo.
pause