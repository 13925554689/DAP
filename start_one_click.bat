@echo off
setlocal
pushd "%~dp0" >nul 2>&1

if not defined DAP_PREFER_LIGHTWEIGHT (
    set "DAP_PREFER_LIGHTWEIGHT=0"
)

set "DAP_ACTIVATE=dap_env\Scripts\activate.bat"
if exist "%DAP_ACTIVATE%" (
    call "%DAP_ACTIVATE%"
)

set "ENV_PYTHON=dap_env\Scripts\python.exe"
set "LAUNCHER=dap_launcher.py"

if exist "%ENV_PYTHON%" (
    "%ENV_PYTHON%" "%LAUNCHER%"
) else (
    python "%LAUNCHER%"
)

if errorlevel 1 (
    echo Failed to start DAP GUI. Press any key to close.
    pause >nul
)

popd >nul 2>&1
endlocal

