@echo off
title DAP System Status Check

echo.
echo ============================================
echo   DAP System Status Check
echo ============================================
echo.

if not exist "dap_env\Scripts\activate.bat" (
    echo ❌ Virtual environment not found
    echo Please run install.bat first
    echo.
    pause
    exit /b 1
)

echo ✅ Virtual environment found

echo.
echo Activating virtual environment...
call dap_env\Scripts\activate.bat

echo.
echo ============================================
echo   Checking System Components
echo ============================================
echo.

echo 🔍 Checking Python modules...
python -c "
try:
    import sys
    import os
    sys.path.append('.')

    print('✅ Core Python modules: OK')

    # Check main components
    try:
        from main_engine import DAPEngine
        print('✅ Main Engine: Available')
    except Exception as e:
        print(f'❌ Main Engine: {e}')

    try:
        from ai_audit_agent import AIAuditAgent
        print('✅ AI Audit Agent: Available')
    except Exception as e:
        print(f'❌ AI Audit Agent: {e}')

    try:
        from performance_monitor import PerformanceMonitor
        print('✅ Performance Monitor: Available')
    except Exception as e:
        print(f'❌ Performance Monitor: {e}')

    try:
        from self_learning_manager import SelfLearningManager
        print('✅ Self Learning Manager: Available')
    except Exception as e:
        print(f'❌ Self Learning Manager: {e}')

    # Check layer components
    layers_status = []
    for layer in range(1, 6):
        try:
            layer_path = f'layer{layer}'
            if os.path.exists(layer_path):
                layer_files = [f for f in os.listdir(layer_path) if f.endswith('.py')]
                layers_status.append(f'✅ Layer {layer}: {len(layer_files)} components')
            else:
                layers_status.append(f'❌ Layer {layer}: Not found')
        except Exception as e:
            layers_status.append(f'❌ Layer {layer}: {e}')

    for status in layers_status:
        print(status)

    print()
    print('🔍 Checking optional dependencies...')

    # Check optional dependencies
    optional_deps = [
        ('pandas', 'Data processing'),
        ('sklearn', 'Machine learning'),
        ('fastapi', 'API server'),
        ('asyncio', 'Async operations'),
        ('sqlite3', 'Database'),
        ('psutil', 'System monitoring')
    ]

    for dep, desc in optional_deps:
        try:
            __import__(dep)
            print(f'✅ {dep}: Available ({desc})')
        except ImportError:
            print(f'⚠️  {dep}: Not available ({desc})')

except Exception as e:
    print(f'❌ Critical error: {e}')
"

echo.
echo ============================================
echo   Checking Network Ports
echo ============================================
echo.

echo 🔍 Checking if default ports are available...

netstat -an | findstr ":8000" >nul
if %errorlevel%==0 (
    echo ⚠️  Port 8000: In use (API Server may be running)
) else (
    echo ✅ Port 8000: Available (API Server)
)

netstat -an | findstr ":8080" >nul
if %errorlevel%==0 (
    echo ⚠️  Port 8080: In use (Monitor may be running)
) else (
    echo ✅ Port 8080: Available (Performance Monitor)
)

echo.
echo ============================================
echo   Checking Directory Structure
echo ============================================
echo.

echo 🔍 Checking required directories...

for %%d in (data exports logs config temp models) do (
    if exist %%d (
        echo ✅ %%d/: Exists
    ) else (
        echo ⚠️  %%d/: Missing (will be created automatically)
        mkdir %%d 2>nul
    )
)

echo.
echo ============================================
echo   System Status Summary
echo ============================================
echo.

python -c "
import os
import sys
sys.path.append('.')

total_files = 0
python_files = 0

# Count Python files
for root, dirs, files in os.walk('.'):
    if 'dap_env' in root or '__pycache__' in root:
        continue
    for file in files:
        total_files += 1
        if file.endswith('.py'):
            python_files += 1

print(f'📊 Total files: {total_files}')
print(f'🐍 Python files: {python_files}')

# Check startup scripts
startup_scripts = ['start_gui.bat', 'start_api.bat', 'start_ai_agent.bat', 'start_monitor.bat', 'start_learning.bat', 'start_all.bat']
available_scripts = sum(1 for script in startup_scripts if os.path.exists(script))
print(f'🚀 Startup scripts: {available_scripts}/{len(startup_scripts)}')

print()
print('🎯 System Ready Status:')
if python_files >= 20:
    print('✅ Core system: Fully implemented')
else:
    print('⚠️  Core system: Partially implemented')

if available_scripts >= 5:
    print('✅ One-click startup: Available')
else:
    print('⚠️  One-click startup: Limited')

print()
print('🚀 Quick Start Commands:')
print('  start_all.bat       - Choose startup mode')
print('  start_gui.bat       - GUI interface')
print('  start_ai_agent.bat  - AI assistant')
print('  start_api.bat       - API server')
print('  start_monitor.bat   - Performance monitor')
"

echo.
echo ============================================
echo   Status Check Complete
echo ============================================
echo.
pause