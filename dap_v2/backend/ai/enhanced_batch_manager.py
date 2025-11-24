"""
DAP v2.0 - Enhanced Batch Processing Manager
增强的批量处理管理器 - 任务队列、进度跟踪、失败重试
"""
import logging
from typing import Dict, List, Optional, Any, Callable
from datetime import datetime, timedelta
from enum import Enum
import uuid
import asyncio
import threading
from pathlib import Path
import json
from collections import deque
import time
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import settings

logger = logging.getLogger(__name__)


class TaskStatus(Enum):
    """任务状态"""
    PENDING = "pending"
    QUEUED = "queued"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    RETRYING = "retrying"


class TaskPriority(Enum):
    """任务优先级"""
    LOW = 1
    NORMAL = 2
    HIGH = 3
    URGENT = 4


class BatchTask:
    """批量任务"""

    def __init__(
        self,
        task_id: str,
        task_type: str,
        total_items: int,
        priority: TaskPriority = TaskPriority.NORMAL,
        retry_on_failure: bool = True,
        max_retries: int = 3
    ):
        self.task_id = task_id
        self.task_type = task_type
        self.status = TaskStatus.PENDING
        self.priority = priority
        self.total_items = total_items
        self.processed_items = 0
        self.successful_items = 0
        self.failed_items = 0
        self.skipped_items = 0

        # 结果和错误
        self.results = []
        self.errors = []
        self.warnings = []

        # 重试相关
        self.retry_on_failure = retry_on_failure
        self.max_retries = max_retries
        self.current_retry = 0
        self.failed_item_ids = []

        # 时间戳
        self.created_at = datetime.now()
        self.started_at = None
        self.completed_at = None
        self.last_updated_at = datetime.now()

        # 性能指标
        self.processing_rate = 0.0  # 每秒处理项数
        self.estimated_time_remaining = None

        # 回调
        self.on_progress_callback = None
        self.on_complete_callback = None

    @property
    def progress(self) -> float:
        """进度百分比"""
        if self.total_items == 0:
            return 0.0
        return self.processed_items / self.total_items

    @property
    def success_rate(self) -> float:
        """成功率"""
        if self.processed_items == 0:
            return 0.0
        return self.successful_items / self.processed_items

    def update_progress(self, success: bool = True):
        """更新进度"""
        self.processed_items += 1
        if success:
            self.successful_items += 1
        else:
            self.failed_items += 1

        self.last_updated_at = datetime.now()

        # 计算处理速率
        if self.started_at:
            elapsed = (datetime.now() - self.started_at).total_seconds()
            if elapsed > 0:
                self.processing_rate = self.processed_items / elapsed

                # 估算剩余时间
                remaining_items = self.total_items - self.processed_items
                if self.processing_rate > 0:
                    self.estimated_time_remaining = remaining_items / self.processing_rate

        # 触发进度回调
        if self.on_progress_callback:
            try:
                self.on_progress_callback(self)
            except Exception as e:
                logger.error(f"Progress callback failed: {e}")

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'task_id': self.task_id,
            'task_type': self.task_type,
            'status': self.status.value,
            'priority': self.priority.value,
            'total_items': self.total_items,
            'processed_items': self.processed_items,
            'successful_items': self.successful_items,
            'failed_items': self.failed_items,
            'skipped_items': self.skipped_items,
            'progress': self.progress,
            'success_rate': self.success_rate,
            'processing_rate': self.processing_rate,
            'estimated_time_remaining': self.estimated_time_remaining,
            'current_retry': self.current_retry,
            'max_retries': self.max_retries,
            'results_count': len(self.results),
            'errors_count': len(self.errors),
            'warnings_count': len(self.warnings),
            'created_at': self.created_at.isoformat(),
            'started_at': self.started_at.isoformat() if self.started_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'last_updated_at': self.last_updated_at.isoformat()
        }


class EnhancedBatchProcessingManager:
    """增强的批量处理管理器"""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        # 配置
        self.config = config or {
            'max_concurrent_tasks': 3,
            'max_workers_per_task': 5,
            'task_timeout': 3600,  # 1小时
            'retry_delay': 5,  # 5秒
            'checkpoint_interval': 100,  # 每100项保存一次检查点
            'cleanup_after_days': 7
        }

        # 任务存储
        self.tasks: Dict[str, BatchTask] = {}
        self.task_queue: deque = deque()  # 任务队列

        # 运行状态
        self.running_tasks: Dict[str, asyncio.Task] = {}
        self.paused_tasks: set = set()

        # 统计
        self.total_tasks_created = 0
        self.total_tasks_completed = 0
        self.total_items_processed = 0

        # 线程锁
        self._lock = threading.Lock()

        # 持久化
        self.state_file = Path(settings.AI_MODEL_PATH) / 'batch_tasks_state.json'

        # 加载已保存的任务
        self._load_state()

    def create_task(
        self,
        task_type: str,
        total_items: int,
        priority: TaskPriority = TaskPriority.NORMAL,
        retry_on_failure: bool = True,
        max_retries: int = 3,
        on_progress: Optional[Callable] = None,
        on_complete: Optional[Callable] = None
    ) -> str:
        """
        创建批量任务

        Args:
            task_type: 任务类型
            total_items: 总项目数
            priority: 优先级
            retry_on_failure: 失败时是否重试
            max_retries: 最大重试次数
            on_progress: 进度回调
            on_complete: 完成回调

        Returns:
            task_id
        """
        with self._lock:
            task_id = f"{task_type}_{uuid.uuid4().hex[:12]}"

            task = BatchTask(
                task_id=task_id,
                task_type=task_type,
                total_items=total_items,
                priority=priority,
                retry_on_failure=retry_on_failure,
                max_retries=max_retries
            )

            task.on_progress_callback = on_progress
            task.on_complete_callback = on_complete

            self.tasks[task_id] = task
            self.total_tasks_created += 1

            logger.info(
                f"Created task {task_id}: {task_type} "
                f"({total_items} items, priority={priority.name})"
            )

            return task_id

    def enqueue_task(self, task_id: str) -> bool:
        """将任务加入队列"""
        with self._lock:
            task = self.tasks.get(task_id)
            if not task:
                return False

            if task.status != TaskStatus.PENDING:
                logger.warning(f"Task {task_id} is not pending (status={task.status})")
                return False

            task.status = TaskStatus.QUEUED
            self.task_queue.append(task_id)

            # 按优先级排序队列
            self.task_queue = deque(sorted(
                self.task_queue,
                key=lambda tid: self.tasks[tid].priority.value,
                reverse=True
            ))

            logger.info(f"Task {task_id} enqueued (queue size: {len(self.task_queue)})")
            return True

    async def process_queue(self):
        """处理任务队列"""
        while True:
            # 检查是否可以启动新任务
            if len(self.running_tasks) < self.config['max_concurrent_tasks']:
                with self._lock:
                    if self.task_queue:
                        task_id = self.task_queue.popleft()
                        task = self.tasks.get(task_id)

                        if task and task.status == TaskStatus.QUEUED:
                            # 启动任务
                            asyncio.create_task(self._execute_task(task_id))

            await asyncio.sleep(1)

    async def _execute_task(self, task_id: str):
        """执行任务"""
        task = self.tasks.get(task_id)
        if not task:
            return

        task.status = TaskStatus.RUNNING
        task.started_at = datetime.now()
        self.running_tasks[task_id] = asyncio.current_task()

        logger.info(f"Starting task {task_id}")

        try:
            # 根据任务类型调用相应的处理函数
            # 这里是占位，实际处理逻辑需要外部注入
            await asyncio.sleep(0.1)  # 模拟处理

            task.status = TaskStatus.COMPLETED
            task.completed_at = datetime.now()
            self.total_tasks_completed += 1
            self.total_items_processed += task.total_items

            # 触发完成回调
            if task.on_complete_callback:
                try:
                    task.on_complete_callback(task)
                except Exception as e:
                    logger.error(f"Complete callback failed: {e}")

            logger.info(
                f"Task {task_id} completed: "
                f"{task.successful_items}/{task.total_items} successful"
            )

        except Exception as e:
            logger.error(f"Task {task_id} failed: {e}")
            task.status = TaskStatus.FAILED
            task.errors.append({'type': 'task_error', 'error': str(e)})

            # 检查是否需要重试
            if task.retry_on_failure and task.current_retry < task.max_retries:
                task.current_retry += 1
                task.status = TaskStatus.RETRYING
                logger.info(f"Retrying task {task_id} (attempt {task.current_retry})")

                # 延迟后重新入队
                await asyncio.sleep(self.config['retry_delay'])
                self.enqueue_task(task_id)

        finally:
            if task_id in self.running_tasks:
                del self.running_tasks[task_id]

            # 保存状态
            self._save_state()

    def pause_task(self, task_id: str) -> bool:
        """暂停任务"""
        with self._lock:
            task = self.tasks.get(task_id)
            if not task:
                return False

            if task.status == TaskStatus.RUNNING:
                task.status = TaskStatus.PAUSED
                self.paused_tasks.add(task_id)
                logger.info(f"Task {task_id} paused")
                return True

            return False

    def resume_task(self, task_id: str) -> bool:
        """恢复任务"""
        with self._lock:
            task = self.tasks.get(task_id)
            if not task:
                return False

            if task.status == TaskStatus.PAUSED:
                task.status = TaskStatus.QUEUED
                self.paused_tasks.discard(task_id)
                self.enqueue_task(task_id)
                logger.info(f"Task {task_id} resumed")
                return True

            return False

    def cancel_task(self, task_id: str) -> bool:
        """取消任务"""
        with self._lock:
            task = self.tasks.get(task_id)
            if not task:
                return False

            if task.status in [TaskStatus.PENDING, TaskStatus.QUEUED, TaskStatus.RUNNING, TaskStatus.PAUSED]:
                task.status = TaskStatus.CANCELLED
                task.completed_at = datetime.now()

                # 从队列中移除
                if task_id in self.task_queue:
                    self.task_queue.remove(task_id)

                # 取消运行中的任务
                if task_id in self.running_tasks:
                    self.running_tasks[task_id].cancel()

                logger.info(f"Task {task_id} cancelled")
                return True

            return False

    def get_task_status(self, task_id: str) -> Optional[Dict[str, Any]]:
        """获取任务状态"""
        task = self.tasks.get(task_id)
        if not task:
            return None
        return task.to_dict()

    def get_detailed_task_info(self, task_id: str, include_results: bool = False) -> Optional[Dict[str, Any]]:
        """获取详细任务信息"""
        task = self.tasks.get(task_id)
        if not task:
            return None

        info = task.to_dict()

        if include_results:
            info['results'] = task.results[-100:]  # 最近100个结果
            info['errors'] = task.errors[-50:]  # 最近50个错误
            info['warnings'] = task.warnings[-50:]  # 最近50个警告

        return info

    def list_tasks(
        self,
        status: Optional[TaskStatus] = None,
        task_type: Optional[str] = None,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """列出任务"""
        with self._lock:
            tasks = list(self.tasks.values())

            if status:
                tasks = [t for t in tasks if t.status == status]

            if task_type:
                tasks = [t for t in tasks if t.task_type == task_type]

            # 按创建时间倒序
            tasks.sort(key=lambda t: t.created_at, reverse=True)

            return [t.to_dict() for t in tasks[:limit]]

    def get_queue_status(self) -> Dict[str, Any]:
        """获取队列状态"""
        with self._lock:
            return {
                'queue_size': len(self.task_queue),
                'running_tasks': len(self.running_tasks),
                'paused_tasks': len(self.paused_tasks),
                'max_concurrent': self.config['max_concurrent_tasks'],
                'queued_task_ids': list(self.task_queue)[:10],  # 前10个
                'running_task_ids': list(self.running_tasks.keys())
            }

    def get_statistics(self) -> Dict[str, Any]:
        """获取统计信息"""
        with self._lock:
            status_counts = {}
            for status in TaskStatus:
                status_counts[status.value] = sum(
                    1 for t in self.tasks.values() if t.status == status
                )

            return {
                'total_tasks_created': self.total_tasks_created,
                'total_tasks_completed': self.total_tasks_completed,
                'total_items_processed': self.total_items_processed,
                'active_tasks': len(self.tasks),
                'status_distribution': status_counts,
                'queue_status': self.get_queue_status()
            }

    def cleanup_old_tasks(self, days: int = None) -> int:
        """清理旧任务"""
        days = days or self.config['cleanup_after_days']
        cutoff = datetime.now() - timedelta(days=days)

        with self._lock:
            to_remove = []

            for task_id, task in self.tasks.items():
                if task.created_at < cutoff:
                    if task.status in [TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED]:
                        to_remove.append(task_id)

            for task_id in to_remove:
                del self.tasks[task_id]

            logger.info(f"Cleaned up {len(to_remove)} old tasks")
            return len(to_remove)

    def _save_state(self):
        """保存任务状态"""
        try:
            self.state_file.parent.mkdir(parents=True, exist_ok=True)

            # 只保存需要持久化的任务
            persist_tasks = {}
            for task_id, task in self.tasks.items():
                if task.status in [TaskStatus.RUNNING, TaskStatus.QUEUED, TaskStatus.PAUSED]:
                    persist_tasks[task_id] = {
                        'task_type': task.task_type,
                        'status': task.status.value,
                        'total_items': task.total_items,
                        'processed_items': task.processed_items,
                        'created_at': task.created_at.isoformat()
                    }

            with open(self.state_file, 'w', encoding='utf-8') as f:
                json.dump(persist_tasks, f, indent=2)

        except Exception as e:
            logger.error(f"Failed to save state: {e}")

    def _load_state(self):
        """加载任务状态"""
        try:
            if self.state_file.exists():
                with open(self.state_file, 'r', encoding='utf-8') as f:
                    persist_tasks = json.load(f)

                logger.info(f"Loaded {len(persist_tasks)} persisted tasks")

        except Exception as e:
            logger.error(f"Failed to load state: {e}")


# 全局实例
_batch_manager = None


def get_batch_manager() -> EnhancedBatchProcessingManager:
    """获取批量处理管理器单例"""
    global _batch_manager
    if _batch_manager is None:
        _batch_manager = EnhancedBatchProcessingManager()
    return _batch_manager
