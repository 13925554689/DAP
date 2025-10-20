@echo off
title DAP Service Shutdown

echo.
echo ============================================
echo   Stopping All DAP Services
echo ============================================
echo.

echo Stopping DAP API Server...
taskkill /f /im python.exe /fi "WINDOWTITLE eq DAP API Server*" 2>nul

echo Stopping DAP Performance Monitor...
taskkill /f /im python.exe /fi "WINDOWTITLE eq DAP Monitor*" 2>nul

echo Stopping DAP AI Learning System...
taskkill /f /im python.exe /fi "WINDOWTITLE eq DAP Learning*" 2>nul

echo Stopping any remaining DAP processes...
for /f "tokens=2" %%i in ('tasklist /fi "imagename eq python.exe" ^| findstr dap') do (
    taskkill /f /pid %%i 2>nul
)

echo.
echo ============================================
echo   All DAP Services Stopped
echo ============================================
echo.

timeout /t 3 /nobreak > nul