#!/usr/bin/env bash

# DAP 一键启动脚本（Unix）
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# 默认开启轻量模式
export DAP_PREFER_LIGHTWEIGHT="${DAP_PREFER_LIGHTWEIGHT:-1}"

# 激活虚拟环境（如果存在）
if [ -f "$SCRIPT_DIR/dap_env/bin/activate" ]; then
    # shellcheck disable=SC1090
    source "$SCRIPT_DIR/dap_env/bin/activate"
fi

python "$SCRIPT_DIR/dap_launcher.py"
