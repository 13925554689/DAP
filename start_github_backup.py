#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DAP GitHub 自动备份服务启动脚本
持续运行，按照配置的间隔自动备份到 GitHub
"""

import os
import sys
import time
import signal
import logging
from pathlib import Path

# 确保可以导入项目模块
sys.path.insert(0, str(Path(__file__).parent))

from layer5.github_backup_manager import GitHubBackupManager
from config.settings import get_config

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/github_backup.log'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

# 全局管理器实例
manager = None


def signal_handler(sig, frame):
    """处理中断信号"""
    logger.info("收到停止信号，正在关闭备份服务...")
    if manager:
        manager.stop()
    sys.exit(0)


def main():
    """主函数"""
    global manager

    # 确保日志目录存在
    os.makedirs('logs', exist_ok=True)

    logger.info("="*60)
    logger.info("DAP GitHub 自动备份服务")
    logger.info("="*60)

    # 加载配置
    config = get_config()
    github_config = config.github_backup

    # 检查配置
    if not github_config.enabled:
        logger.error("GitHub 备份未启用，请在 .env 文件中设置 DAP_GITHUB_BACKUP_ENABLED=true")
        return 1

    if not github_config.repository:
        logger.error("未配置 GitHub 仓库，请在 .env 文件中设置 DAP_GITHUB_BACKUP_REPO")
        return 1

    token = os.getenv(github_config.token_env_var)
    if not token:
        logger.error(f"未找到 GitHub Token，请设置环境变量 {github_config.token_env_var}")
        logger.error("获取 Token 的步骤：")
        logger.error("1. 访问 https://github.com/settings/tokens")
        logger.error("2. 生成新的 classic token")
        logger.error("3. 授予 repo 权限")
        logger.error("4. 将 token 添加到 .env 文件")
        return 1

    # 显示配置信息
    logger.info(f"目标仓库: {github_config.repository}")
    logger.info(f"分支: {github_config.branch}")
    logger.info(f"备份间隔: {github_config.interval_minutes} 分钟")
    logger.info(f"备份路径: {', '.join(github_config.backup_paths)}")
    logger.info(f"远程路径: {github_config.remote_path}")
    logger.info("-"*60)

    # 注册信号处理器
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # 创建管理器
    manager = GitHubBackupManager(github_config)

    # 首次备份
    logger.info("执行首次备份...")
    success = manager.run_backup(triggered_by="startup")

    if success:
        logger.info("✓ 首次备份成功!")
    else:
        logger.warning("✗ 首次备份失败，但服务将继续运行")
        status = manager.get_status()
        logger.warning(f"失败原因: {status.get('message', '未知')}")

    logger.info("-"*60)
    logger.info(f"自动备份服务已启动，每 {github_config.interval_minutes} 分钟执行一次备份")
    logger.info("按 Ctrl+C 停止服务")
    logger.info("="*60)

    # 启动定时备份
    manager.start()

    # 保持服务运行
    try:
        while True:
            time.sleep(60)  # 每分钟检查一次

            # 显示状态
            status = manager.get_status()
            if status.get('last_run'):
                logger.debug(f"上次备份: {status['last_run']}, 状态: {'成功' if status.get('success') else '失败'}")

    except KeyboardInterrupt:
        logger.info("\n收到中断信号，正在停止...")
        manager.stop()
        logger.info("服务已停止")
        return 0

    except Exception as e:
        logger.exception(f"服务异常: {e}")
        if manager:
            manager.stop()
        return 1


if __name__ == "__main__":
    sys.exit(main())
