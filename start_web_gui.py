"""
DAP Web GUI 启动脚本 (Python版)
跨平台支持
"""

import sys
import os
import subprocess
import webbrowser
import threading
import time

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def check_dependencies():
    """检查并安装依赖"""
    required_packages = ['flask', 'flask-cors']
    
    for package in required_packages:
        try:
            __import__(package.replace('-', '_'))
            print(f"✓ {package} 已安装")
        except ImportError:
            print(f"✗ {package} 未安装，正在安装...")
            subprocess.check_call([sys.executable, '-m', 'pip', 'install', package])

def start_server():
    """启动Web服务器"""
    print("\n" + "="*50)
    print("DAP Web GUI - 启动中...")
    print("="*50)
    
    # 设置环境变量
    os.environ['FLASK_APP'] = 'web_gui.app'
    os.environ['FLASK_ENV'] = 'development'
    
    # 导入并启动应用
    try:
        from web_gui.app import app
        
        print("\n🚀 服务器启动成功！")
        print("📍 访问地址: http://localhost:5000")
        print("💡 按 Ctrl+C 停止服务器")
        print("\n⏳ 正在自动打开浏览器...\n")
        
        # 延迟1秒后自动打开浏览器
        def open_browser():
            time.sleep(1.5)
            webbrowser.open('http://localhost:5000')
        
        browser_thread = threading.Thread(target=open_browser, daemon=True)
        browser_thread.start()
        
        # 排除备份文件目录，避免反复重载
        app.run(
            host='127.0.0.1',
            port=5000,
            debug=True,
            use_reloader=False,  # 禁用重载器以避免watchdog问题
            exclude_patterns=[
                '*/data/github_backups/*',
                '*/backups/*',
                '*.zip',
                '*.log'
            ]
        )
    except Exception as e:
        print(f"\n❌ 启动失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == '__main__':
    print("检查依赖...")
    check_dependencies()
    start_server()