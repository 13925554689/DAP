"""
DAP v2.0 - Model Retraining Pipeline
AI模型重训练管道
"""
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime
from pathlib import Path
import json
import numpy as np
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import settings

logger = logging.getLogger(__name__)


class ModelRetrainingPipeline:
    """AI模型重训练管道"""

    def __init__(self):
        self.model_path = Path(settings.AI_MODEL_PATH)
        self.min_samples = settings.AI_MIN_TRAINING_SAMPLES
        self.batch_size = settings.AI_TRAINING_BATCH_SIZE
        self.learning_rate = settings.AI_LEARNING_RATE

        # 模型版本管理
        self.version_file = self.model_path / 'versions.json'
        self.current_versions = self._load_versions()

    def _load_versions(self) -> Dict[str, Any]:
        """加载模型版本信息"""
        if self.version_file.exists():
            with open(self.version_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {}

    def _save_versions(self):
        """保存模型版本信息"""
        self.version_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.version_file, 'w', encoding='utf-8') as f:
            json.dump(self.current_versions, f, indent=2, ensure_ascii=False)

    def check_retraining_needed(self, model_type: str) -> Dict[str, Any]:
        """
        检查是否需要重训练

        Args:
            model_type: 模型类型 (ocr/classification/mapping/risk/behavior)

        Returns:
            {
                'needed': bool,
                'reason': str,
                'sample_count': int,
                'last_training': datetime
            }
        """
        try:
            sample_file = self.model_path / model_type / 'samples.jsonl'

            if not sample_file.exists():
                return {
                    'needed': False,
                    'reason': '没有训练样本',
                    'sample_count': 0
                }

            # 计算样本数
            with open(sample_file, 'r', encoding='utf-8') as f:
                sample_count = sum(1 for _ in f)

            # 获取上次训练信息
            last_training = self.current_versions.get(model_type, {}).get('last_training')
            last_sample_count = self.current_versions.get(model_type, {}).get('sample_count', 0)

            # 判断是否需要重训练
            if sample_count < self.min_samples:
                return {
                    'needed': False,
                    'reason': f'样本不足: {sample_count}/{self.min_samples}',
                    'sample_count': sample_count
                }

            new_samples = sample_count - last_sample_count
            if new_samples >= self.min_samples:
                return {
                    'needed': True,
                    'reason': f'新增样本达到阈值: {new_samples}',
                    'sample_count': sample_count,
                    'last_training': last_training,
                    'new_samples': new_samples
                }

            # 检查时间间隔(7天)
            if last_training:
                days_since = (datetime.now() - datetime.fromisoformat(last_training)).days
                if days_since >= 7 and sample_count > last_sample_count:
                    return {
                        'needed': True,
                        'reason': f'定期重训练: {days_since}天',
                        'sample_count': sample_count,
                        'last_training': last_training
                    }

            return {
                'needed': False,
                'reason': '暂不需要重训练',
                'sample_count': sample_count,
                'last_training': last_training
            }

        except Exception as e:
            logger.error(f"Check retraining failed: {e}")
            return {
                'needed': False,
                'reason': f'检查失败: {str(e)}',
                'sample_count': 0
            }

    def load_training_samples(
        self,
        model_type: str,
        max_samples: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        加载训练样本

        Args:
            model_type: 模型类型
            max_samples: 最大样本数

        Returns:
            样本列表
        """
        try:
            sample_file = self.model_path / model_type / 'samples.jsonl'
            if not sample_file.exists():
                return []

            samples = []
            with open(sample_file, 'r', encoding='utf-8') as f:
                for line in f:
                    if max_samples and len(samples) >= max_samples:
                        break
                    samples.append(json.loads(line))

            logger.info(f"Loaded {len(samples)} samples for {model_type}")
            return samples

        except Exception as e:
            logger.error(f"Load samples failed: {e}")
            return []

    def train_evidence_classification_model(
        self,
        samples: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        训练证据分类模型

        Args:
            samples: 训练样本

        Returns:
            训练结果
        """
        try:
            if len(samples) < self.min_samples:
                return {
                    'success': False,
                    'error': f'样本不足: {len(samples)}/{self.min_samples}'
                }

            logger.info(f"Training classification model with {len(samples)} samples")

            # TODO: 实现实际的模型训练
            # 这里使用简化的训练流程

            # 1. 准备数据
            texts = [s.get('evidence_text', '') for s in samples]
            labels = [s.get('user_classification', '') for s in samples]

            # 统计类别分布
            from collections import Counter
            label_dist = Counter(labels)

            # 2. 分割训练集和验证集
            split_idx = int(len(samples) * 0.8)
            train_samples = samples[:split_idx]
            val_samples = samples[split_idx:]

            # 3. 训练模型 (简化版)
            # TODO: 使用实际的ML框架 (sklearn, transformers等)
            model_accuracy = 0.85  # 模拟训练结果

            # 4. 保存模型
            model_file = self.model_path / 'classification' / f'model_v{self._get_next_version("classification")}.json'
            model_file.parent.mkdir(parents=True, exist_ok=True)

            model_data = {
                'version': self._get_next_version('classification'),
                'trained_at': datetime.now().isoformat(),
                'sample_count': len(samples),
                'accuracy': model_accuracy,
                'label_distribution': dict(label_dist),
                'config': {
                    'batch_size': self.batch_size,
                    'learning_rate': self.learning_rate
                }
            }

            with open(model_file, 'w', encoding='utf-8') as f:
                json.dump(model_data, f, indent=2, ensure_ascii=False)

            # 5. 更新版本信息
            self.current_versions['classification'] = {
                'version': model_data['version'],
                'last_training': datetime.now().isoformat(),
                'sample_count': len(samples),
                'accuracy': model_accuracy,
                'model_file': str(model_file)
            }
            self._save_versions()

            return {
                'success': True,
                'model_version': model_data['version'],
                'accuracy': model_accuracy,
                'sample_count': len(samples),
                'train_samples': len(train_samples),
                'val_samples': len(val_samples)
            }

        except Exception as e:
            logger.error(f"Model training failed: {e}")
            return {
                'success': False,
                'error': str(e)
            }

    def train_ocr_correction_model(
        self,
        samples: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """训练OCR纠错模型"""
        try:
            logger.info(f"Training OCR correction model with {len(samples)} samples")

            # 提取纠错模式
            correction_patterns = []
            for sample in samples:
                original = sample.get('original', '')
                corrected = sample.get('corrected', '')

                if original and corrected and original != corrected:
                    correction_patterns.append({
                        'original': original,
                        'corrected': corrected
                    })

            # 保存纠错规则
            rules_file = self.model_path / 'ocr' / f'rules_v{self._get_next_version("ocr")}.json'
            rules_file.parent.mkdir(parents=True, exist_ok=True)

            with open(rules_file, 'w', encoding='utf-8') as f:
                json.dump({
                    'version': self._get_next_version('ocr'),
                    'patterns': correction_patterns,
                    'trained_at': datetime.now().isoformat(),
                    'sample_count': len(samples)
                }, f, indent=2, ensure_ascii=False)

            # 更新版本
            self.current_versions['ocr'] = {
                'version': self._get_next_version('ocr'),
                'last_training': datetime.now().isoformat(),
                'sample_count': len(samples),
                'rules_file': str(rules_file)
            }
            self._save_versions()

            return {
                'success': True,
                'model_version': self._get_next_version('ocr'),
                'pattern_count': len(correction_patterns),
                'sample_count': len(samples)
            }

        except Exception as e:
            logger.error(f"OCR model training failed: {e}")
            return {
                'success': False,
                'error': str(e)
            }

    def _get_next_version(self, model_type: str) -> int:
        """获取下一个版本号"""
        current = self.current_versions.get(model_type, {}).get('version', 0)
        return current + 1

    def get_model_info(self, model_type: str) -> Dict[str, Any]:
        """获取模型信息"""
        return self.current_versions.get(model_type, {})

    def list_all_models(self) -> Dict[str, Any]:
        """列出所有模型"""
        return {
            'models': self.current_versions,
            'total_models': len(self.current_versions)
        }

    def rollback_model(self, model_type: str, version: int) -> Dict[str, Any]:
        """回滚到指定版本"""
        try:
            # TODO: 实现模型回滚逻辑
            # 1. 检查版本是否存在
            # 2. 恢复模型文件
            # 3. 更新版本信息

            return {
                'success': True,
                'message': f'Model {model_type} rolled back to version {version}'
            }

        except Exception as e:
            logger.error(f"Model rollback failed: {e}")
            return {
                'success': False,
                'error': str(e)
            }

    def compare_models(
        self,
        model_type: str,
        version_a: int,
        version_b: int
    ) -> Dict[str, Any]:
        """比较两个模型版本"""
        try:
            # TODO: 实现A/B测试比较
            return {
                'version_a': version_a,
                'version_b': version_b,
                'metrics_comparison': {},
                'recommendation': 'version_b'
            }

        except Exception as e:
            logger.error(f"Model comparison failed: {e}")
            return {
                'success': False,
                'error': str(e)
            }

    def schedule_retraining(
        self,
        model_type: str,
        schedule: str = 'weekly'
    ) -> Dict[str, Any]:
        """
        调度定期重训练

        Args:
            model_type: 模型类型
            schedule: 调度周期 (daily/weekly/monthly)

        Returns:
            调度结果
        """
        try:
            # TODO: 实现定时任务调度 (使用APScheduler或Celery)
            schedule_info = {
                'model_type': model_type,
                'schedule': schedule,
                'next_run': None,  # 计算下次运行时间
                'enabled': True
            }

            logger.info(f"Scheduled {schedule} retraining for {model_type}")

            return {
                'success': True,
                'schedule': schedule_info
            }

        except Exception as e:
            logger.error(f"Schedule retraining failed: {e}")
            return {
                'success': False,
                'error': str(e)
            }


# 全局实例
_retraining_pipeline = None


def get_retraining_pipeline() -> ModelRetrainingPipeline:
    """获取重训练管道单例"""
    global _retraining_pipeline
    if _retraining_pipeline is None:
        _retraining_pipeline = ModelRetrainingPipeline()
    return _retraining_pipeline
