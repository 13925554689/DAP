#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DAP 自动备份服务 - 守护进程版本（无窗口）
使用 .pyw 扩展名，双击运行时不显示终端窗口
"""

import sys
import subprocess
from pathlib import Path

# 获取当前目录
current_dir = Path(__file__).parent

# Python解释器路径
python_exe = current_dir / "dap_env" / "Scripts" / "python.exe"

# 脚本路径
script_path = current_dir / "auto_git_backup.py"

# 使用 pythonw 运行（无窗口）
pythonw_exe = current_dir / "dap_env" / "Scripts" / "pythonw.exe"

# 启动服务
if pythonw_exe.exists():
    subprocess.Popen(
        [str(pythonw_exe), str(script_path)],
        cwd=str(current_dir),
        creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0
    )
else:
    # 备用方案：使用 python.exe
    subprocess.Popen(
        [str(python_exe), str(script_path)],
        cwd=str(current_dir),
        creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0
    )
