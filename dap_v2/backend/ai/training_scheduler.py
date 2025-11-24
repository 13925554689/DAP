"""
DAP v2.0 - Model Training Scheduler
模型训练调度器 - 基于APScheduler
"""
import logging
from typing import Dict, List, Optional, Any, Callable
from datetime import datetime, timedelta
from pathlib import Path
import json
import threading
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import settings

logger = logging.getLogger(__name__)

# 尝试导入APScheduler
try:
    from apscheduler.schedulers.background import BackgroundScheduler
    from apscheduler.triggers.cron import CronTrigger
    from apscheduler.triggers.interval import IntervalTrigger
    from apscheduler.events import EVENT_JOB_EXECUTED, EVENT_JOB_ERROR
    SCHEDULER_AVAILABLE = True
except ImportError:
    logger.warning("APScheduler not installed. Scheduler functionality will be limited.")
    SCHEDULER_AVAILABLE = False


class ModelTrainingScheduler:
    """模型训练调度器"""

    def __init__(self, model_path: Optional[Path] = None):
        self.model_path = model_path or Path(settings.AI_MODEL_PATH)
        self.schedule_config_file = self.model_path / 'scheduler_config.json'

        # 调度器配置
        self.schedules = self._load_schedules()

        # 训练历史
        self.training_history = []
        self.max_history = 100

        # 线程锁
        self._lock = threading.Lock()

        # 初始化调度器
        if SCHEDULER_AVAILABLE:
            self.scheduler = BackgroundScheduler()
            self.scheduler.add_listener(
                self._job_listener,
                EVENT_JOB_EXECUTED | EVENT_JOB_ERROR
            )
            self._scheduler_started = False
        else:
            self.scheduler = None
            logger.warning("Scheduler not available - APScheduler not installed")

    def _load_schedules(self) -> Dict[str, Any]:
        """加载调度配置"""
        if self.schedule_config_file.exists():
            try:
                with open(self.schedule_config_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Failed to load schedules: {e}")
        return {}

    def _save_schedules(self):
        """保存调度配置"""
        try:
            self.schedule_config_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.schedule_config_file, 'w', encoding='utf-8') as f:
                json.dump(self.schedules, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Failed to save schedules: {e}")

    def schedule_retraining(
        self,
        model_type: str,
        schedule_type: str = 'weekly',
        custom_cron: Optional[str] = None,
        callback: Optional[Callable] = None,
        enabled: bool = True
    ) -> Dict[str, Any]:
        """
        调度模型重训练

        Args:
            model_type: 模型类型 (ocr/classification/mapping/risk/behavior)
            schedule_type: 调度类型 (hourly/daily/weekly/monthly/custom)
            custom_cron: 自定义cron表达式
            callback: 训练完成回调函数
            enabled: 是否启用

        Returns:
            调度结果
        """
        try:
            if not SCHEDULER_AVAILABLE:
                return {
                    'success': False,
                    'error': 'APScheduler not installed'
                }

            # 生成job_id
            job_id = f"retrain_{model_type}"

            # 移除已存在的job
            if self.scheduler.get_job(job_id):
                self.scheduler.remove_job(job_id)

            # 创建trigger
            trigger = self._create_trigger(schedule_type, custom_cron)
            if not trigger:
                return {
                    'success': False,
                    'error': f'Invalid schedule type: {schedule_type}'
                }

            # 添加job
            self.scheduler.add_job(
                func=self._execute_training,
                trigger=trigger,
                id=job_id,
                args=[model_type, callback],
                name=f"Retrain {model_type} model",
                replace_existing=True
            )

            # 保存配置
            self.schedules[model_type] = {
                'schedule_type': schedule_type,
                'custom_cron': custom_cron,
                'enabled': enabled,
                'created_at': datetime.now().isoformat(),
                'job_id': job_id
            }
            self._save_schedules()

            # 启动调度器
            if not self._scheduler_started:
                self.scheduler.start()
                self._scheduler_started = True
                logger.info("Scheduler started")

            # 计算下次运行时间
            next_run = self.scheduler.get_job(job_id).next_run_time

            logger.info(f"Scheduled {schedule_type} retraining for {model_type}")

            return {
                'success': True,
                'job_id': job_id,
                'model_type': model_type,
                'schedule_type': schedule_type,
                'next_run': next_run.isoformat() if next_run else None,
                'enabled': enabled
            }

        except Exception as e:
            logger.error(f"Schedule retraining failed: {e}")
            return {
                'success': False,
                'error': str(e)
            }

    def _create_trigger(
        self,
        schedule_type: str,
        custom_cron: Optional[str] = None
    ):
        """创建调度触发器"""
        if schedule_type == 'custom' and custom_cron:
            # 自定义cron表达式
            return CronTrigger.from_crontab(custom_cron)

        elif schedule_type == 'hourly':
            # 每小时
            return IntervalTrigger(hours=1)

        elif schedule_type == 'daily':
            # 每天凌晨2点
            return CronTrigger(hour=2, minute=0)

        elif schedule_type == 'weekly':
            # 每周日凌晨2点
            return CronTrigger(day_of_week='sun', hour=2, minute=0)

        elif schedule_type == 'monthly':
            # 每月1号凌晨2点
            return CronTrigger(day=1, hour=2, minute=0)

        else:
            return None

    def _execute_training(self, model_type: str, callback: Optional[Callable] = None):
        """执行训练任务"""
        with self._lock:
            start_time = datetime.now()

            try:
                logger.info(f"Starting scheduled training for {model_type}")

                # 导入重训练pipeline
                from ai.retraining_pipeline import get_retraining_pipeline
                pipeline = get_retraining_pipeline()

                # 检查是否需要重训练
                check_result = pipeline.check_retraining_needed(model_type)

                if not check_result['needed']:
                    logger.info(f"Retraining not needed for {model_type}: {check_result['reason']}")
                    self._record_training_history(
                        model_type=model_type,
                        status='skipped',
                        reason=check_result['reason'],
                        start_time=start_time,
                        end_time=datetime.now()
                    )
                    return

                # 加载训练样本
                samples = pipeline.load_training_samples(model_type)

                if not samples:
                    logger.warning(f"No training samples found for {model_type}")
                    self._record_training_history(
                        model_type=model_type,
                        status='failed',
                        error='No training samples',
                        start_time=start_time,
                        end_time=datetime.now()
                    )
                    return

                # 执行训练
                if model_type == 'classification':
                    result = pipeline.train_evidence_classification_model(samples)
                elif model_type == 'ocr':
                    result = pipeline.train_ocr_correction_model(samples)
                else:
                    logger.warning(f"Training not implemented for {model_type}")
                    result = {'success': False, 'error': 'Not implemented'}

                end_time = datetime.now()
                duration = (end_time - start_time).total_seconds()

                # 记录训练历史
                self._record_training_history(
                    model_type=model_type,
                    status='success' if result.get('success') else 'failed',
                    result=result,
                    start_time=start_time,
                    end_time=end_time,
                    duration=duration
                )

                logger.info(f"Training completed for {model_type} in {duration:.1f}s")

                # 执行回调
                if callback and result.get('success'):
                    callback(model_type, result)

            except Exception as e:
                logger.error(f"Training execution failed: {e}", exc_info=True)
                self._record_training_history(
                    model_type=model_type,
                    status='error',
                    error=str(e),
                    start_time=start_time,
                    end_time=datetime.now()
                )

    def _job_listener(self, event):
        """Job执行监听器"""
        if event.exception:
            logger.error(f"Job {event.job_id} failed: {event.exception}")
        else:
            logger.info(f"Job {event.job_id} executed successfully")

    def _record_training_history(
        self,
        model_type: str,
        status: str,
        start_time: datetime,
        end_time: datetime,
        result: Optional[Dict] = None,
        error: Optional[str] = None,
        reason: Optional[str] = None,
        duration: Optional[float] = None
    ):
        """记录训练历史"""
        history_entry = {
            'model_type': model_type,
            'status': status,
            'start_time': start_time.isoformat(),
            'end_time': end_time.isoformat(),
            'duration': duration or (end_time - start_time).total_seconds(),
            'result': result,
            'error': error,
            'reason': reason
        }

        self.training_history.append(history_entry)

        # 限制历史记录数量
        if len(self.training_history) > self.max_history:
            self.training_history = self.training_history[-self.max_history:]

        # 保存到文件
        self._save_training_history()

    def _save_training_history(self):
        """保存训练历史"""
        try:
            history_file = self.model_path / 'training_history.jsonl'
            history_file.parent.mkdir(parents=True, exist_ok=True)

            with open(history_file, 'a', encoding='utf-8') as f:
                # 只保存最新的记录
                if self.training_history:
                    latest = self.training_history[-1]
                    f.write(json.dumps(latest, ensure_ascii=False) + '\n')

        except Exception as e:
            logger.error(f"Failed to save training history: {e}")

    def get_schedule_status(self, model_type: Optional[str] = None) -> Dict[str, Any]:
        """获取调度状态"""
        if not SCHEDULER_AVAILABLE:
            return {'error': 'Scheduler not available'}

        if model_type:
            # 单个模型状态
            schedule = self.schedules.get(model_type)
            if not schedule:
                return {'error': f'No schedule found for {model_type}'}

            job_id = schedule.get('job_id')
            job = self.scheduler.get_job(job_id) if job_id else None

            return {
                'model_type': model_type,
                'schedule': schedule,
                'is_running': job is not None,
                'next_run': job.next_run_time.isoformat() if job and job.next_run_time else None
            }
        else:
            # 所有模型状态
            statuses = {}
            for model_type in self.schedules.keys():
                statuses[model_type] = self.get_schedule_status(model_type)

            return {
                'scheduler_running': self._scheduler_started,
                'total_schedules': len(self.schedules),
                'schedules': statuses
            }

    def pause_schedule(self, model_type: str) -> Dict[str, Any]:
        """暂停调度"""
        try:
            if not SCHEDULER_AVAILABLE:
                return {'success': False, 'error': 'Scheduler not available'}

            schedule = self.schedules.get(model_type)
            if not schedule:
                return {'success': False, 'error': f'No schedule found for {model_type}'}

            job_id = schedule['job_id']
            job = self.scheduler.get_job(job_id)

            if job:
                self.scheduler.pause_job(job_id)
                schedule['enabled'] = False
                self._save_schedules()

                logger.info(f"Paused schedule for {model_type}")
                return {'success': True, 'status': 'paused'}
            else:
                return {'success': False, 'error': 'Job not found'}

        except Exception as e:
            logger.error(f"Failed to pause schedule: {e}")
            return {'success': False, 'error': str(e)}

    def resume_schedule(self, model_type: str) -> Dict[str, Any]:
        """恢复调度"""
        try:
            if not SCHEDULER_AVAILABLE:
                return {'success': False, 'error': 'Scheduler not available'}

            schedule = self.schedules.get(model_type)
            if not schedule:
                return {'success': False, 'error': f'No schedule found for {model_type}'}

            job_id = schedule['job_id']
            job = self.scheduler.get_job(job_id)

            if job:
                self.scheduler.resume_job(job_id)
                schedule['enabled'] = True
                self._save_schedules()

                logger.info(f"Resumed schedule for {model_type}")
                return {'success': True, 'status': 'running'}
            else:
                return {'success': False, 'error': 'Job not found'}

        except Exception as e:
            logger.error(f"Failed to resume schedule: {e}")
            return {'success': False, 'error': str(e)}

    def remove_schedule(self, model_type: str) -> Dict[str, Any]:
        """移除调度"""
        try:
            if not SCHEDULER_AVAILABLE:
                return {'success': False, 'error': 'Scheduler not available'}

            schedule = self.schedules.get(model_type)
            if not schedule:
                return {'success': False, 'error': f'No schedule found for {model_type}'}

            job_id = schedule['job_id']
            if self.scheduler.get_job(job_id):
                self.scheduler.remove_job(job_id)

            del self.schedules[model_type]
            self._save_schedules()

            logger.info(f"Removed schedule for {model_type}")
            return {'success': True}

        except Exception as e:
            logger.error(f"Failed to remove schedule: {e}")
            return {'success': False, 'error': str(e)}

    def get_training_history(
        self,
        model_type: Optional[str] = None,
        limit: int = 20
    ) -> List[Dict[str, Any]]:
        """获取训练历史"""
        history = self.training_history

        if model_type:
            history = [h for h in history if h['model_type'] == model_type]

        # 返回最近的N条
        return history[-limit:]

    def trigger_immediate_training(
        self,
        model_type: str,
        force: bool = False
    ) -> Dict[str, Any]:
        """立即触发训练（不等待调度）"""
        try:
            logger.info(f"Triggering immediate training for {model_type}")

            # 在新线程中执行
            thread = threading.Thread(
                target=self._execute_training,
                args=[model_type, None]
            )
            thread.daemon = True
            thread.start()

            return {
                'success': True,
                'message': f'Training triggered for {model_type}',
                'async': True
            }

        except Exception as e:
            logger.error(f"Failed to trigger training: {e}")
            return {
                'success': False,
                'error': str(e)
            }

    def shutdown(self):
        """关闭调度器"""
        if SCHEDULER_AVAILABLE and self._scheduler_started:
            self.scheduler.shutdown()
            self._scheduler_started = False
            logger.info("Scheduler shut down")


# 全局实例
_training_scheduler = None


def get_training_scheduler() -> ModelTrainingScheduler:
    """获取训练调度器单例"""
    global _training_scheduler
    if _training_scheduler is None:
        _training_scheduler = ModelTrainingScheduler()
    return _training_scheduler
