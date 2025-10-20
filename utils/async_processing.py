"""
DAP - 异步处理模块
提供异步数据处理和并发管理功能
"""

import asyncio
import concurrent.futures
import threading
import time
from typing import Dict, Any, List, Optional, Callable, Awaitable, Union
from dataclasses import dataclass
from enum import Enum
import logging
from contextlib import asynccontextmanager
import queue
import weakref

from .exceptions import ProcessingError
from .monitoring import performance_monitor

logger = logging.getLogger(__name__)


class TaskStatus(Enum):
    """任务状态枚举"""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class AsyncTask:
    """异步任务"""

    task_id: str
    name: str
    func: Callable
    args: tuple
    kwargs: dict
    status: TaskStatus = TaskStatus.PENDING
    result: Any = None
    error: Optional[Exception] = None
    start_time: Optional[float] = None
    end_time: Optional[float] = None
    progress: float = 0.0

    @property
    def duration(self) -> Optional[float]:
        """获取任务执行时间"""
        if self.start_time and self.end_time:
            return self.end_time - self.start_time
        return None

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "task_id": self.task_id,
            "name": self.name,
            "status": self.status.value,
            "progress": self.progress,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "duration": self.duration,
            "error": str(self.error) if self.error else None,
        }


class AsyncTaskManager:
    """异步任务管理器"""

    def __init__(self, max_workers: int = 4):
        self.max_workers = max_workers
        self.tasks: Dict[str, AsyncTask] = {}
        self.executor = concurrent.futures.ThreadPoolExecutor(max_workers=max_workers)
        self._task_counter = 0
        self._lock = threading.Lock()

    def create_task(
        self, func: Callable, *args, name: str = None, task_id: str = None, **kwargs
    ) -> str:
        """创建异步任务"""
        with self._lock:
            if task_id is None:
                self._task_counter += 1
                task_id = f"task_{self._task_counter}"

            if task_id in self.tasks:
                raise ValueError(f"任务ID已存在: {task_id}")

            if name is None:
                name = func.__name__ if hasattr(func, "__name__") else str(func)

            task = AsyncTask(
                task_id=task_id, name=name, func=func, args=args, kwargs=kwargs
            )

            self.tasks[task_id] = task
            return task_id

    def submit_task(self, task_id: str) -> concurrent.futures.Future:
        """提交任务执行"""
        if task_id not in self.tasks:
            raise ValueError(f"任务不存在: {task_id}")

        task = self.tasks[task_id]
        if task.status != TaskStatus.PENDING:
            raise ValueError(f"任务状态不正确: {task.status}")

        future = self.executor.submit(self._execute_task, task_id)
        return future

    def _execute_task(self, task_id: str) -> Any:
        """执行任务"""
        task = self.tasks[task_id]

        try:
            task.status = TaskStatus.RUNNING
            task.start_time = time.time()

            with performance_monitor(f"async_task_{task.name}"):
                result = task.func(*task.args, **task.kwargs)

            task.result = result
            task.status = TaskStatus.COMPLETED
            task.progress = 1.0

            logger.info(f"异步任务完成: {task_id} ({task.name})")
            return result

        except Exception as e:
            task.error = e
            task.status = TaskStatus.FAILED
            logger.error(f"异步任务失败: {task_id} ({task.name}) - {e}")
            raise
        finally:
            task.end_time = time.time()

    def get_task(self, task_id: str) -> Optional[AsyncTask]:
        """获取任务"""
        return self.tasks.get(task_id)

    def get_task_status(self, task_id: str) -> Dict[str, Any]:
        """获取任务状态"""
        task = self.get_task(task_id)
        if not task:
            return {"error": "任务不存在"}
        return task.to_dict()

    def list_tasks(self, status: TaskStatus = None) -> List[Dict[str, Any]]:
        """列出任务"""
        tasks = self.tasks.values()
        if status:
            tasks = [t for t in tasks if t.status == status]
        return [task.to_dict() for task in tasks]

    def cancel_task(self, task_id: str) -> bool:
        """取消任务"""
        task = self.get_task(task_id)
        if not task:
            return False

        if task.status == TaskStatus.PENDING:
            task.status = TaskStatus.CANCELLED
            return True
        return False

    def cleanup_completed_tasks(self, max_age_hours: int = 24):
        """清理已完成的任务"""
        current_time = time.time()
        cutoff_time = current_time - (max_age_hours * 3600)

        with self._lock:
            to_remove = []
            for task_id, task in self.tasks.items():
                if (
                    task.status
                    in [TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED]
                    and task.end_time
                    and task.end_time < cutoff_time
                ):
                    to_remove.append(task_id)

            for task_id in to_remove:
                del self.tasks[task_id]

            logger.info(f"清理了 {len(to_remove)} 个过期任务")

    def shutdown(self, wait: bool = True):
        """关闭任务管理器"""
        logger.info("正在关闭异步任务管理器...")
        self.executor.shutdown(wait=wait)


class BatchProcessor:
    """批量处理器"""

    def __init__(
        self, batch_size: int = 100, max_workers: int = 4, timeout: float = 300.0
    ):
        self.batch_size = batch_size
        self.max_workers = max_workers
        self.timeout = timeout
        self.task_manager = AsyncTaskManager(max_workers)

    def process_batch(
        self,
        items: List[Any],
        processor_func: Callable[[Any], Any],
        callback: Callable[[List[Any]], None] = None,
    ) -> str:
        """批量处理项目"""

        def batch_worker(batch_items):
            results = []
            for item in batch_items:
                try:
                    result = processor_func(item)
                    results.append(result)
                except Exception as e:
                    logger.error(f"批量处理项目失败: {item} - {e}")
                    results.append(None)

            if callback:
                callback(results)

            return results

        # 分批处理
        batches = [
            items[i : i + self.batch_size]
            for i in range(0, len(items), self.batch_size)
        ]

        # 创建并提交任务
        futures = []
        for i, batch in enumerate(batches):
            task_id = self.task_manager.create_task(
                batch_worker, batch, name=f"batch_process_{i}"
            )
            future = self.task_manager.submit_task(task_id)
            futures.append((task_id, future))

        return futures

    def wait_for_completion(
        self, futures: List[tuple], timeout: float = None
    ) -> List[Any]:
        """等待批量处理完成"""
        if timeout is None:
            timeout = self.timeout

        all_results = []
        for task_id, future in futures:
            try:
                results = future.result(timeout=timeout)
                all_results.extend(results)
            except concurrent.futures.TimeoutError:
                logger.error(f"批量处理任务超时: {task_id}")
                self.task_manager.cancel_task(task_id)
            except Exception as e:
                logger.error(f"批量处理任务失败: {task_id} - {e}")

        return all_results


class ProgressTracker:
    """进度跟踪器"""

    def __init__(self):
        self.progress_data: Dict[str, Dict[str, Any]] = {}
        self._lock = threading.Lock()

    def create_progress(
        self, operation_id: str, total_steps: int, description: str = ""
    ):
        """创建进度跟踪"""
        with self._lock:
            self.progress_data[operation_id] = {
                "total_steps": total_steps,
                "current_step": 0,
                "description": description,
                "start_time": time.time(),
                "last_update": time.time(),
                "status": "running",
            }

    def update_progress(self, operation_id: str, current_step: int, message: str = ""):
        """更新进度"""
        with self._lock:
            if operation_id in self.progress_data:
                data = self.progress_data[operation_id]
                data["current_step"] = current_step
                data["last_update"] = time.time()
                data["message"] = message

                # 计算百分比
                total_steps = data.get("total_steps", 0)
                if total_steps > 0:
                    progress_percent = (current_step / total_steps) * 100
                else:
                    progress_percent = 100 if current_step else 0
                data["progress_percent"] = min(100, progress_percent)

                # 估算剩余时间
                elapsed = time.time() - data["start_time"]
                if current_step > 0 and elapsed > 0:
                    rate = current_step / elapsed
                    remaining_steps = data["total_steps"] - current_step
                    if rate > 0:
                        eta = remaining_steps / rate
                        data["eta_seconds"] = eta

    def complete_progress(self, operation_id: str, message: str = "完成"):
        """完成进度跟踪"""
        with self._lock:
            if operation_id in self.progress_data:
                data = self.progress_data[operation_id]
                data["current_step"] = data["total_steps"]
                data["progress_percent"] = 100
                data["status"] = "completed"
                data["message"] = message
                data["end_time"] = time.time()

    def fail_progress(self, operation_id: str, error_message: str):
        """标记进度失败"""
        with self._lock:
            if operation_id in self.progress_data:
                data = self.progress_data[operation_id]
                data["status"] = "failed"
                data["error_message"] = error_message
                data["end_time"] = time.time()

    def get_progress(self, operation_id: str) -> Optional[Dict[str, Any]]:
        """获取进度信息"""
        return self.progress_data.get(operation_id)

    def list_progress(self) -> Dict[str, Dict[str, Any]]:
        """列出所有进度"""
        return self.progress_data.copy()


class AsyncDataProcessor:
    """异步数据处理器"""

    def __init__(self, max_workers: int = 4):
        self.task_manager = AsyncTaskManager(max_workers)
        self.batch_processor = BatchProcessor(max_workers=max_workers)
        self.progress_tracker = ProgressTracker()

    async def process_data_async(
        self, data_source: str, options: Dict[str, Any] = None
    ) -> str:
        """异步处理数据"""
        operation_id = f"data_process_{int(time.time())}"

        # 创建进度跟踪
        self.progress_tracker.create_progress(operation_id, 4, f"异步处理数据: {data_source}")

        try:
            # 模拟异步数据处理步骤
            self.progress_tracker.update_progress(operation_id, 1, "数据接入中...")
            await asyncio.sleep(0.1)  # 模拟IO操作

            self.progress_tracker.update_progress(operation_id, 2, "数据清洗中...")
            await asyncio.sleep(0.1)

            self.progress_tracker.update_progress(operation_id, 3, "数据存储中...")
            await asyncio.sleep(0.1)

            self.progress_tracker.update_progress(operation_id, 4, "数据分析中...")
            await asyncio.sleep(0.1)

            self.progress_tracker.complete_progress(operation_id, "数据处理完成")

            return operation_id

        except Exception as e:
            self.progress_tracker.fail_progress(operation_id, str(e))
            raise ProcessingError(f"异步数据处理失败: {e}")

    def process_data_background(
        self, data_source: str, options: Dict[str, Any] = None
    ) -> str:
        """后台处理数据"""
        from main_engine import get_dap_engine

        def background_task():
            engine = get_dap_engine()
            return engine.process(data_source, options)

        task_id = self.task_manager.create_task(
            background_task, name=f"background_process_{data_source}"
        )

        self.task_manager.submit_task(task_id)
        return task_id

    def get_processing_status(self, operation_id: str) -> Dict[str, Any]:
        """获取处理状态"""
        # 检查是否是任务ID
        task_status = self.task_manager.get_task_status(operation_id)
        if "error" not in task_status:
            return task_status

        # 检查是否是进度ID
        progress = self.progress_tracker.get_progress(operation_id)
        if progress:
            return progress

        return {"error": "操作不存在"}

    def cancel_processing(self, operation_id: str) -> bool:
        """取消处理"""
        return self.task_manager.cancel_task(operation_id)


# 全局异步处理器实例
global_async_processor = AsyncDataProcessor()


@asynccontextmanager
async def async_processing_context(operation_name: str):
    """异步处理上下文管理器"""
    start_time = time.time()
    logger.info(f"开始异步操作: {operation_name}")

    try:
        yield
    except Exception as e:
        logger.error(f"异步操作失败: {operation_name} - {e}")
        raise
    finally:
        duration = time.time() - start_time
        logger.info(f"异步操作完成: {operation_name}, 耗时: {duration:.3f}s")


def run_async_task(coro: Awaitable) -> Any:
    """运行异步任务"""
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    if loop.is_running():
        # 如果事件循环正在运行，使用线程池
        with concurrent.futures.ThreadPoolExecutor() as executor:
            future = executor.submit(asyncio.run, coro)
            return future.result()
    else:
        # 否则直接运行
        return loop.run_until_complete(coro)
