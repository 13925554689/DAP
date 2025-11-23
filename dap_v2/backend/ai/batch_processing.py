"""
DAP v2.0 - Batch Processing Service
批量处理服务 (使用后台任务)
"""
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime
import uuid
import asyncio
from enum import Enum
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logger = logging.getLogger(__name__)


class TaskStatus(Enum):
    """任务状态"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class BatchTask:
    """批量任务"""

    def __init__(self, task_id: str, task_type: str, total_items: int):
        self.task_id = task_id
        self.task_type = task_type
        self.status = TaskStatus.PENDING
        self.total_items = total_items
        self.processed_items = 0
        self.failed_items = 0
        self.results = []
        self.errors = []
        self.created_at = datetime.now()
        self.started_at = None
        self.completed_at = None

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'task_id': self.task_id,
            'task_type': self.task_type,
            'status': self.status.value,
            'total_items': self.total_items,
            'processed_items': self.processed_items,
            'failed_items': self.failed_items,
            'progress': self.processed_items / self.total_items if self.total_items > 0 else 0,
            'results': self.results,
            'errors': self.errors,
            'created_at': self.created_at.isoformat(),
            'started_at': self.started_at.isoformat() if self.started_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None
        }


class BatchProcessingService:
    """批量处理服务"""

    def __init__(self):
        self.tasks: Dict[str, BatchTask] = {}
        self.max_concurrent_tasks = 5
        self.running_tasks = 0

    def create_task(self, task_type: str, total_items: int) -> str:
        """
        创建批量任务

        Args:
            task_type: 任务类型 (ocr_batch/classification_batch/export_batch)
            total_items: 总项目数

        Returns:
            task_id
        """
        task_id = f"{task_type}_{uuid.uuid4().hex[:8]}"
        task = BatchTask(task_id, task_type, total_items)
        self.tasks[task_id] = task

        logger.info(f"Created batch task: {task_id} ({total_items} items)")
        return task_id

    async def process_batch_ocr(
        self,
        task_id: str,
        evidence_ids: List[str],
        ocr_service,
        db_session
    ) -> Dict[str, Any]:
        """
        批量OCR处理

        Args:
            task_id: 任务ID
            evidence_ids: 证据ID列表
            ocr_service: OCR服务实例
            db_session: 数据库会话

        Returns:
            处理结果
        """
        task = self.tasks.get(task_id)
        if not task:
            return {'error': 'Task not found'}

        task.status = TaskStatus.RUNNING
        task.started_at = datetime.now()
        self.running_tasks += 1

        try:
            from models import Evidence

            for idx, evidence_id in enumerate(evidence_ids):
                try:
                    # 获取证据
                    evidence = db_session.query(Evidence).filter(
                        Evidence.id == evidence_id
                    ).first()

                    if not evidence or not evidence.file_path:
                        task.failed_items += 1
                        task.errors.append({
                            'evidence_id': evidence_id,
                            'error': '文件不存在'
                        })
                        continue

                    # OCR处理
                    ocr_result = ocr_service.extract_text(evidence.file_path)

                    if 'error' in ocr_result:
                        task.failed_items += 1
                        task.errors.append({
                            'evidence_id': evidence_id,
                            'error': ocr_result['error']
                        })
                    else:
                        # 更新证据
                        evidence.ocr_text = ocr_result['text']
                        evidence.ocr_confidence = ocr_result['confidence']
                        evidence.content_text = ocr_result['text']

                        task.results.append({
                            'evidence_id': evidence_id,
                            'status': 'success',
                            'confidence': ocr_result['confidence']
                        })

                    task.processed_items += 1

                    # 定期提交
                    if (idx + 1) % 10 == 0:
                        db_session.commit()

                except Exception as e:
                    logger.error(f"OCR processing failed for {evidence_id}: {e}")
                    task.failed_items += 1
                    task.errors.append({
                        'evidence_id': evidence_id,
                        'error': str(e)
                    })

                # 模拟短暂延迟
                await asyncio.sleep(0.1)

            # 最终提交
            db_session.commit()

            task.status = TaskStatus.COMPLETED
            task.completed_at = datetime.now()

        except Exception as e:
            logger.error(f"Batch OCR task failed: {e}")
            task.status = TaskStatus.FAILED
            task.errors.append({'error': str(e)})

        finally:
            self.running_tasks -= 1

        return task.to_dict()

    async def process_batch_classification(
        self,
        task_id: str,
        evidence_ids: List[str],
        deepseek_client,
        db_session
    ) -> Dict[str, Any]:
        """批量证据分类"""
        task = self.tasks.get(task_id)
        if not task:
            return {'error': 'Task not found'}

        task.status = TaskStatus.RUNNING
        task.started_at = datetime.now()
        self.running_tasks += 1

        try:
            from models import Evidence

            categories = ["银行对账单", "发票", "合同", "凭证", "报表", "说明", "其他"]

            for idx, evidence_id in enumerate(evidence_ids):
                try:
                    evidence = db_session.query(Evidence).filter(
                        Evidence.id == evidence_id
                    ).first()

                    if not evidence:
                        task.failed_items += 1
                        continue

                    # AI分类
                    content = evidence.content_text or evidence.ocr_text or ""
                    if content:
                        result = await deepseek_client.classify_evidence(
                            content,
                            categories
                        )

                        # TODO: 解析AI返回结果并更新
                        evidence.ai_classification = "其他"  # 占位

                    task.processed_items += 1
                    task.results.append({
                        'evidence_id': evidence_id,
                        'status': 'success'
                    })

                except Exception as e:
                    logger.error(f"Classification failed for {evidence_id}: {e}")
                    task.failed_items += 1
                    task.errors.append({
                        'evidence_id': evidence_id,
                        'error': str(e)
                    })

                await asyncio.sleep(0.1)

            db_session.commit()
            task.status = TaskStatus.COMPLETED
            task.completed_at = datetime.now()

        except Exception as e:
            logger.error(f"Batch classification task failed: {e}")
            task.status = TaskStatus.FAILED
            task.errors.append({'error': str(e)})

        finally:
            self.running_tasks -= 1

        return task.to_dict()

    def get_task_status(self, task_id: str) -> Optional[Dict[str, Any]]:
        """获取任务状态"""
        task = self.tasks.get(task_id)
        if not task:
            return None
        return task.to_dict()

    def cancel_task(self, task_id: str) -> bool:
        """取消任务"""
        task = self.tasks.get(task_id)
        if not task:
            return False

        if task.status in [TaskStatus.PENDING, TaskStatus.RUNNING]:
            task.status = TaskStatus.CANCELLED
            logger.info(f"Task cancelled: {task_id}")
            return True

        return False

    def list_tasks(
        self,
        status: Optional[TaskStatus] = None,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """列出任务"""
        tasks = list(self.tasks.values())

        if status:
            tasks = [t for t in tasks if t.status == status]

        # 按创建时间倒序
        tasks.sort(key=lambda t: t.created_at, reverse=True)

        return [t.to_dict() for t in tasks[:limit]]

    def cleanup_old_tasks(self, days: int = 7):
        """清理旧任务"""
        cutoff = datetime.now().timestamp() - (days * 86400)
        to_remove = []

        for task_id, task in self.tasks.items():
            if task.created_at.timestamp() < cutoff:
                if task.status in [TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED]:
                    to_remove.append(task_id)

        for task_id in to_remove:
            del self.tasks[task_id]

        logger.info(f"Cleaned up {len(to_remove)} old tasks")
        return len(to_remove)


# 全局实例
_batch_service = None


def get_batch_service() -> BatchProcessingService:
    """获取批量处理服务单例"""
    global _batch_service
    if _batch_service is None:
        _batch_service = BatchProcessingService()
    return _batch_service
