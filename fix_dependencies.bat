@echo off
echo ===================================
echo DAP - 修复依赖包
echo ===================================
echo.

echo 正在安装缺失的依赖包...
echo.

REM 激活虚拟环境(如果存在)
if exist dap_env\Scripts\activate.bat (
    echo 检测到虚拟环境,正在激活...
    call dap_env\Scripts\activate.bat
)

echo 安装 rarfile...
pip install rarfile

echo.
echo 安装 openpyxl (用于Excel导出)...
pip install openpyxl

echo.
echo 安装 pandas (数据处理)...
pip install pandas

echo.
echo 安装 pydantic (数据验证)...
pip install pydantic

echo.
echo ===================================
echo 依赖包安装完成!
echo ===================================
echo.
echo 现在可以运行:
echo   start_gui.bat
echo.
pause
