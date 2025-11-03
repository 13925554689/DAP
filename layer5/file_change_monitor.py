"""
文件变更监控器
监控系统程序文件的修改，自动触发GitHub备份
"""

import logging
import os
import time
import threading
from pathlib import Path
from typing import Dict, Set, Optional, Callable
from datetime import datetime, timedelta

LOGGER = logging.getLogger(__name__)


class FileChangeMonitor:
    """监控文件变更并触发回调"""

    def __init__(
        self,
        watch_paths: list,
        callback: Callable,
        extensions: Optional[Set[str]] = None,
        check_interval: int = 5,
        debounce_seconds: int = 10,
    ):
        """
        初始化文件变更监控器
        
        Args:
            watch_paths: 要监控的路径列表
            callback: 检测到变更时调用的回调函数
            extensions: 要监控的文件扩展名集合，None表示监控所有文件
            check_interval: 检查间隔（秒）
            debounce_seconds: 防抖延迟（秒），避免频繁触发
        """
        self.watch_paths = [Path(p) for p in watch_paths]
        self.callback = callback
        self.extensions = extensions or {'.py', '.yaml', '.yml', '.json', '.env'}
        self.check_interval = check_interval
        self.debounce_seconds = debounce_seconds
        
        self._file_mtimes: Dict[Path, float] = {}
        self._last_trigger_time: Optional[datetime] = None
        self._stop_event = threading.Event()
        self._worker_thread: Optional[threading.Thread] = None
        self._running = False
        
        self.logger = LOGGER.getChild("FileChangeMonitor")
        
    def start(self) -> None:
        """启动文件监控"""
        if self._running:
            self.logger.warning("文件监控已在运行中")
            return
            
        self._stop_event.clear()
        self._running = True
        
        # 初始化文件修改时间
        self._scan_files()
        
        # 启动监控线程
        self._worker_thread = threading.Thread(
            target=self._monitor_loop,
            name="FileChangeMonitor",
            daemon=True
        )
        self._worker_thread.start()
        
        self.logger.info(
            f"文件监控已启动，监控 {len(self.watch_paths)} 个路径，"
            f"检查间隔 {self.check_interval}秒，防抖延迟 {self.debounce_seconds}秒"
        )
    
    def stop(self) -> None:
        """停止文件监控"""
        if not self._running:
            return
            
        self._stop_event.set()
        self._running = False
        
        if self._worker_thread and self._worker_thread.is_alive():
            self._worker_thread.join(timeout=10)
            
            # 如果线程仍未停止，记录警告
            if self._worker_thread.is_alive():
                self.logger.warning("文件监控线程未能在规定时间内停止，已设置为daemon模式")
        
        self._worker_thread = None
        self.logger.info("文件监控已停止")
    
    def _monitor_loop(self) -> None:
        """监控循环"""
        while not self._stop_event.wait(self.check_interval):
            try:
                changed_files = self._check_changes()
                
                if changed_files:
                    self.logger.info(f"检测到 {len(changed_files)} 个文件变更")
                    
                    # 防抖处理
                    if self._should_trigger():
                        self.logger.info(f"触发备份回调（变更文件: {list(changed_files)[:5]}...）")
                        try:
                            self.callback(changed_files=changed_files)
                            self._last_trigger_time = datetime.now()
                        except Exception as e:
                            self.logger.error(f"备份回调执行失败: {e}", exc_info=True)
                    else:
                        if self._last_trigger_time:
                            remaining = self.debounce_seconds - (
                                datetime.now() - self._last_trigger_time
                            ).total_seconds()
                            self.logger.debug(
                                f"防抖延迟中，{remaining:.1f}秒后可再次触发"
                            )
                        
            except Exception as e:
                self.logger.error(f"文件监控异常: {e}", exc_info=True)
    
    def _scan_files(self) -> None:
        """扫描所有监控的文件并记录修改时间"""
        self._file_mtimes.clear()
        
        for watch_path in self.watch_paths:
            if not watch_path.exists():
                self.logger.debug(f"跳过不存在的路径: {watch_path}")
                continue
            
            if watch_path.is_file():
                if self._should_monitor_file(watch_path):
                    try:
                        mtime = watch_path.stat().st_mtime
                        self._file_mtimes[watch_path] = mtime
                    except OSError as e:
                        self.logger.debug(f"无法获取文件状态 {watch_path}: {e}")
            else:
                # 递归扫描目录
                for file_path in watch_path.rglob("*"):
                    if file_path.is_file() and self._should_monitor_file(file_path):
                        try:
                            mtime = file_path.stat().st_mtime
                            self._file_mtimes[file_path] = mtime
                        except OSError as e:
                            self.logger.debug(f"无法获取文件状态 {file_path}: {e}")
        
        self.logger.info(f"初始扫描完成，监控 {len(self._file_mtimes)} 个文件")
    
    def _check_changes(self) -> Set[Path]:
        """检查文件变更，返回变更的文件集合"""
        changed_files = set()
        current_files = {}
        
        # 扫描当前文件
        for watch_path in self.watch_paths:
            if not watch_path.exists():
                continue
            
            if watch_path.is_file():
                if self._should_monitor_file(watch_path):
                    try:
                        mtime = watch_path.stat().st_mtime
                        current_files[watch_path] = mtime
                    except OSError:
                        pass
            else:
                for file_path in watch_path.rglob("*"):
                    if file_path.is_file() and self._should_monitor_file(file_path):
                        try:
                            mtime = file_path.stat().st_mtime
                            current_files[file_path] = mtime
                        except OSError:
                            pass
        
        # 检测新增或修改的文件
        for file_path, mtime in current_files.items():
            if file_path not in self._file_mtimes:
                # 新文件
                changed_files.add(file_path)
                self.logger.debug(f"新增文件: {file_path}")
            elif abs(mtime - self._file_mtimes[file_path]) > 0.001:
                # 文件已修改
                changed_files.add(file_path)
                self.logger.debug(f"修改文件: {file_path}")
        
        # 检测删除的文件
        deleted_files = set(self._file_mtimes.keys()) - set(current_files.keys())
        if deleted_files:
            changed_files.update(deleted_files)
            for file_path in deleted_files:
                self.logger.debug(f"删除文件: {file_path}")
        
        # 更新文件修改时间缓存
        self._file_mtimes = current_files
        
        return changed_files
    
    def _should_monitor_file(self, file_path: Path) -> bool:
        """判断是否应该监控该文件"""
        # 跳过隐藏文件和临时文件
        if file_path.name.startswith('.') or file_path.name.startswith('~'):
            return False
        
        # 跳过__pycache__和其他缓存目录
        if '__pycache__' in file_path.parts:
            return False
        
        # 跳过备份目录
        if 'github_backups' in file_path.parts or 'backups' in file_path.parts:
            return False
        
        # 检查文件扩展名
        if self.extensions:
            return file_path.suffix.lower() in self.extensions
        
        return True
    
    def _should_trigger(self) -> bool:
        """判断是否应该触发回调（防抖）"""
        if self._last_trigger_time is None:
            return True
        
        elapsed = (datetime.now() - self._last_trigger_time).total_seconds()
        return elapsed >= self.debounce_seconds
    
    def get_status(self) -> Dict:
        """获取监控状态"""
        return {
            "running": self._running,
            "watched_files": len(self._file_mtimes),
            "watched_paths": [str(p) for p in self.watch_paths],
            "check_interval": self.check_interval,
            "debounce_seconds": self.debounce_seconds,
            "last_trigger": (
                self._last_trigger_time.isoformat() 
                if self._last_trigger_time else None
            )
        }
