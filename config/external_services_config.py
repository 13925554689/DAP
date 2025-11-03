"""
外部服务配置文件
External Services Configuration
"""

# 服务端口配置
EXTERNAL_SERVICES = {
    "asks": {
        "enabled": True,
        "host": "localhost",
        "port": 8000,  # ASKS 服务实际运行在端口 8000
        "name": "会计准则知识库",
        "description": "基于CASC的会计准则智能查询系统"
    },
    "taxkb": {
        "enabled": True,
        "host": "localhost",
        "port": 8002,
        "name": "税务知识库",
        "description": "税务法规和优惠政策智能查询系统"
    },
    "regkb": {
        "enabled": True,
        "host": "localhost",
        "port": 8003,
        "name": "证监会监管规则库",
        "description": "证监会、上交所、深交所监管规则查询系统"
    },
    "internal_control": {
        "enabled": True,
        "host": "localhost",
        "port": 8004,
        "name": "内控智能体(CIRA Lite)",
        "description": "企业内部控制风险评估系统"
    },
    "ipo": {
        "enabled": True,
        "host": "localhost",
        "port": 8005,
        "name": "IPO智能体(CIRA Lite)",
        "description": "IPO准备度评估和障碍检查系统"
    }
}

# 服务启动路径配置
SERVICE_PATHS = {
    "asks": r"d:\DAP",  # 使用包装脚本
    "taxkb": r"d:\TAXKB",
    "regkb": r"d:\REGKB",
    "internal_control": r"d:\REGKB\internal_control_agent",
    "ipo": r"d:\REGKB\ipo_agent"
}

# 服务启动命令
SERVICE_START_COMMANDS = {
    "asks": "python launch_asks_service.py --port 8000",  # 更新为实际端口
    "taxkb": "python simple_main.py",
    "regkb": "python main.py --mode web --port 8003",
    "internal_control": "python main.py --port 8004",
    "ipo": "python main.py --port 8005"
}