@echo off
REM DAP GitHub 自动备份部署脚本
echo ======================================
echo DAP GitHub 自动备份部署工具
echo ======================================
echo.

REM 检查 .env 文件是否存在
if not exist .env (
    echo [错误] 未找到 .env 文件
    echo 请执行以下步骤：
    echo 1. 复制 .env.example 为 .env
    echo 2. 编辑 .env 文件，填入您的 GitHub Token
    echo 3. 再次运行此脚本
    echo.
    echo 获取 GitHub Token 的步骤：
    echo 1. 访问 https://github.com/settings/tokens
    echo 2. 点击 "Generate new token (classic)"
    echo 3. 选择权限: repo (完整仓库访问权限)
    echo 4. 生成并复制 token 到 .env 文件
    pause
    exit /b 1
)

REM 检查虚拟环境
if not exist dap_env (
    echo [错误] 虚拟环境不存在，请先运行 install.bat
    pause
    exit /b 1
)

echo [1/5] 激活虚拟环境...
call dap_env\Scripts\activate.bat

echo [2/5] 检查依赖包...
pip show requests >nul 2>&1
if errorlevel 1 (
    echo 安装 requests 包...
    pip install requests
)

echo [3/5] 测试 GitHub 备份配置...
python -c "from config.settings import get_config; cfg = get_config(); print(f'GitHub备份状态: {'启用' if cfg.github_backup.enabled else '禁用'}'); print(f'目标仓库: {cfg.github_backup.repository}'); print(f'备份间隔: {cfg.github_backup.interval_minutes} 分钟')"

echo.
echo [4/5] 运行首次备份测试...
python -c "import os; os.environ['DAP_GITHUB_BACKUP_ENABLED'] = 'true'; from layer5.github_backup_manager import GitHubBackupManager; from config.settings import get_config; cfg = get_config(); manager = GitHubBackupManager(cfg.github_backup); success = manager.run_backup('manual'); print('备份成功!' if success else '备份失败，请检查配置'); import sys; sys.exit(0 if success else 1)"

if errorlevel 1 (
    echo.
    echo [错误] 备份测试失败，请检查：
    echo 1. GitHub Token 是否正确
    echo 2. 仓库名称是否正确 (格式: username/repo)
    echo 3. Token 是否有 repo 权限
    echo 4. 网络连接是否正常
    pause
    exit /b 1
)

echo.
echo [5/5] 创建自动备份服务...
echo 您可以选择以下方式启用自动备份：
echo.
echo 方式1: 后台定时任务 (推荐)
echo   - 运行: python start_github_backup.py
echo   - 自动每 2 小时备份一次
echo.
echo 方式2: Windows 计划任务
echo   - 打开 "任务计划程序"
echo   - 创建基本任务
echo   - 程序: %CD%\start_github_backup.bat
echo   - 触发器: 每天或每 2 小时
echo.
echo ======================================
echo 部署完成！
echo ======================================
echo.
echo 后续步骤：
echo 1. 访问 https://github.com/13925554689/DAP 查看备份
echo 2. 运行 start_github_backup.bat 启动自动备份服务
echo 3. 查看日志: logs/dap.log
echo.
pause
