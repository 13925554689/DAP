#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DAP 自动 Git + GitHub 双备份系统
实时监控文件变化，自动提交到本地Git和推送到GitHub
"""

import os
import sys
import time
import logging
from pathlib import Path
from datetime import datetime
from threading import Thread, Lock, Event
from collections import defaultdict

# 设置UTF-8编码
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from git import Repo, GitCommandError
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/auto_git_backup.log', encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)


class GitAutoBackup:
    """Git自动备份管理器"""

    def __init__(self, repo_path: str, debounce_seconds: int = 30):
        """
        初始化自动备份管理器

        Args:
            repo_path: Git仓库路径
            debounce_seconds: 防抖时间（秒），相同文件在此时间内的多次修改只触发一次备份
        """
        self.repo_path = Path(repo_path)
        self.debounce_seconds = debounce_seconds
        self.pending_files = defaultdict(float)
        self.lock = Lock()
        self.stop_event = Event()
        self.commit_thread = None

        # 初始化Git仓库
        try:
            self.repo = Repo(repo_path)
            logger.info(f"Git仓库已加载: {repo_path}")
        except Exception as e:
            logger.error(f"Git仓库加载失败: {e}")
            raise

        # 忽略的文件和目录
        self.ignore_patterns = {
            '.git', '__pycache__', '.pyc', '.log',
            'dap_env', 'venv', 'node_modules',
            '.tmp', '.swp', '.swo', '~',
            'data/github_backups'  # 避免递归备份
        }

    def should_ignore(self, path: str) -> bool:
        """检查文件是否应该被忽略"""
        path_obj = Path(path)

        # 检查路径中是否包含忽略的模式
        for ignore in self.ignore_patterns:
            if ignore in path_obj.parts or path.endswith(ignore):
                return True

        # 检查是否在.gitignore中
        try:
            # 相对路径
            rel_path = path_obj.relative_to(self.repo_path)
            # 使用git check-ignore检查
            try:
                self.repo.git.check_ignore(str(rel_path))
                return True  # 在.gitignore中
            except GitCommandError:
                return False  # 不在.gitignore中
        except (ValueError, GitCommandError):
            return False

    def add_pending_file(self, file_path: str):
        """添加待提交的文件"""
        if self.should_ignore(file_path):
            return

        with self.lock:
            self.pending_files[file_path] = time.time()
            logger.debug(f"文件变化: {file_path}")

    def commit_and_push(self):
        """提交并推送更改"""
        while not self.stop_event.is_set():
            time.sleep(5)  # 每5秒检查一次

            with self.lock:
                current_time = time.time()
                ready_files = []

                # 找出已经过了防抖时间的文件
                for file_path, change_time in list(self.pending_files.items()):
                    if current_time - change_time >= self.debounce_seconds:
                        ready_files.append(file_path)

                if not ready_files:
                    continue

                # 清除已处理的文件
                for file_path in ready_files:
                    del self.pending_files[file_path]

            # 执行提交和推送
            try:
                self._perform_backup(ready_files)
            except Exception as e:
                logger.error(f"备份失败: {e}", exc_info=True)

    def _perform_backup(self, files: list):
        """执行实际的备份操作"""
        if not files:
            return

        try:
            # 1. 添加文件到暂存区
            logger.info(f"添加 {len(files)} 个文件到Git暂存区...")

            # 添加所有变化的文件
            self.repo.git.add('--all')

            # 检查是否有变化
            if not self.repo.is_dirty() and not self.repo.untracked_files:
                logger.debug("没有需要提交的变化")
                return

            # 2. 创建提交
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            # 获取变化统计
            stats = self.repo.index.diff(self.repo.head.commit)
            added = len([d for d in stats if d.new_file])
            modified = len([d for d in stats if not d.new_file and not d.deleted_file])
            deleted = len([d for d in stats if d.deleted_file])
            untracked = len(self.repo.untracked_files)

            commit_msg = f"""自动备份: {timestamp}

变更统计:
- 新增文件: {added + untracked}
- 修改文件: {modified}
- 删除文件: {deleted}

🤖 由 DAP 自动备份系统生成"""

            commit = self.repo.index.commit(commit_msg)
            logger.info(f"✓ Git提交成功: {commit.hexsha[:8]}")

            # 3. 推送到GitHub
            logger.info("推送到GitHub...")
            origin = self.repo.remote('origin')

            # 设置推送选项（禁用SSL验证）
            with self.repo.git.custom_environment(GIT_SSL_NO_VERIFY='1'):
                push_info = origin.push()[0]

            if push_info.flags & push_info.ERROR:
                logger.error(f"✗ GitHub推送失败: {push_info.summary}")
            else:
                logger.info(f"✓ GitHub推送成功: {push_info.summary}")

            # 4. 显示变化摘要
            logger.info("-" * 60)
            logger.info(f"备份完成 | 提交: {commit.hexsha[:8]} | "
                       f"新增:{added+untracked} 修改:{modified} 删除:{deleted}")
            logger.info("-" * 60)

        except GitCommandError as e:
            logger.error(f"Git操作失败: {e}")
        except Exception as e:
            logger.error(f"备份异常: {e}", exc_info=True)

    def start(self):
        """启动自动备份服务"""
        self.stop_event.clear()
        self.commit_thread = Thread(target=self.commit_and_push, daemon=True)
        self.commit_thread.start()
        logger.info("自动提交线程已启动")

    def stop(self):
        """停止自动备份服务"""
        self.stop_event.set()
        if self.commit_thread:
            self.commit_thread.join(timeout=10)
        logger.info("自动提交线程已停止")


class FileChangeHandler(FileSystemEventHandler):
    """文件变化监听器"""

    def __init__(self, backup_manager: GitAutoBackup):
        self.backup = backup_manager

    def on_modified(self, event):
        if not event.is_directory:
            self.backup.add_pending_file(event.src_path)

    def on_created(self, event):
        if not event.is_directory:
            self.backup.add_pending_file(event.src_path)

    def on_deleted(self, event):
        if not event.is_directory:
            self.backup.add_pending_file(event.src_path)

    def on_moved(self, event):
        if not event.is_directory:
            self.backup.add_pending_file(event.dest_path)


def main():
    """主函数"""
    logger.info("=" * 60)
    logger.info("DAP 自动 Git + GitHub 双备份系统")
    logger.info("=" * 60)
    logger.info("")

    # 确保日志目录存在
    os.makedirs('logs', exist_ok=True)

    # 当前目录
    repo_path = os.getcwd()

    # 配置参数
    debounce_seconds = int(os.getenv('DAP_GIT_DEBOUNCE_SECONDS', '30'))

    logger.info(f"监控路径: {repo_path}")
    logger.info(f"防抖时间: {debounce_seconds} 秒")
    logger.info(f"GitHub仓库: 13925554689/DAP")
    logger.info("-" * 60)

    try:
        # 创建备份管理器
        backup_manager = GitAutoBackup(repo_path, debounce_seconds)
        backup_manager.start()

        # 创建文件监听器
        event_handler = FileChangeHandler(backup_manager)
        observer = Observer()

        # 监控整个项目目录
        observer.schedule(event_handler, repo_path, recursive=True)
        observer.start()

        logger.info("✓ 文件监控已启动")
        logger.info("✓ 自动备份服务运行中...")
        logger.info("")
        logger.info("监控以下变化:")
        logger.info("  - 文件创建/修改/删除")
        logger.info("  - 自动Git提交（防抖30秒）")
        logger.info("  - 自动推送到GitHub")
        logger.info("")
        logger.info("按 Ctrl+C 停止服务")
        logger.info("=" * 60)

        # 保持运行
        while True:
            time.sleep(1)

    except KeyboardInterrupt:
        logger.info("")
        logger.info("收到停止信号，正在关闭...")
        observer.stop()
        backup_manager.stop()
        observer.join()
        logger.info("服务已停止")

    except Exception as e:
        logger.error(f"服务异常: {e}", exc_info=True)
        return 1

    return 0


if __name__ == '__main__':
    sys.exit(main())
