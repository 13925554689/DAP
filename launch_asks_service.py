#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ASKS 服务启动包装脚本
"""

import os
import sys
import subprocess
import argparse
import time

def main():
    # 解析命令行参数
    parser = argparse.ArgumentParser(description='ASKS 服务启动器')
    parser.add_argument('--port', type=int, default=8001, help='指定服务端口 (默认: 8001)')
    args = parser.parse_args()
    
    # 设置环境变量
    env = os.environ.copy()
    env['SERVER_PORT'] = str(args.port)
    
    # 切换到 ASKS 目录并启动服务
    asks_path = r"d:\ASKS"
    if not os.path.exists(asks_path):
        print(f"错误: ASKS 目录不存在: {asks_path}")
        sys.exit(1)
    
    # 构建启动命令，直接指定端口
    cmd = f"python start_web_gui.py"
    
    print(f"启动 ASKS 服务 (端口: {args.port})...")
    print(f"命令: {cmd}")
    
    try:
        # 启动服务
        process = subprocess.Popen(
            cmd,
            cwd=asks_path,
            shell=True,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        
        print(f"ASKS 服务已启动 (PID: {process.pid})")
        print(f"访问地址: http://localhost:{args.port}")
        
        # 等待几秒钟让服务启动
        time.sleep(3)
        
        # 检查进程是否仍在运行
        if process.poll() is None:
            print("✅ ASKS 服务启动成功")
        else:
            stdout, stderr = process.communicate()
            print("❌ ASKS 服务启动失败")
            print(f"错误输出: {stderr.decode('utf-8', errors='ignore')}")
            
    except Exception as e:
        print(f"❌ 启动 ASKS 服务时发生错误: {e}")

if __name__ == "__main__":
    main()