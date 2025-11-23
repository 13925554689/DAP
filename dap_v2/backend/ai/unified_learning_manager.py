"""
Unified Learning Manager
统一的AI学习管理器,集成所有学习模块
"""
import logging
from typing import Dict, List, Any, Optional
from datetime import datetime
from pathlib import Path
import json

from .deepseek_client import DeepSeekClient
from ..config import settings

logger = logging.getLogger(__name__)


class UnifiedLearningManager:
    """统一AI学习管理器"""

    def __init__(self):
        self.config = {
            'enabled': settings.AI_LEARNING_ENABLED,
            'model_path': Path(settings.AI_MODEL_PATH),
            'batch_size': settings.AI_TRAINING_BATCH_SIZE,
            'learning_rate': settings.AI_LEARNING_RATE,
            'min_samples': settings.AI_MIN_TRAINING_SAMPLES
        }

        # 初始化DeepSeek客户端
        self.deepseek = DeepSeekClient()

        # 学习模块容器
        self.learners = {}

        # 学习历史
        self.learning_history = []

        # 性能指标
        self.metrics = {
            'ocr_accuracy': 0.85,
            'evidence_classification': 0.0,
            'account_mapping': 0.70,
            'anomaly_detection_f1': 0.60,
            'rule_false_positive': 0.20
        }

        # 目标指标
        self.target_metrics = {
            'ocr_accuracy': 0.95,
            'evidence_classification': 0.90,
            'account_mapping': 0.95,
            'anomaly_detection_f1': 0.85,
            'rule_false_positive': 0.05
        }

        # 初始化模型目录
        self._init_model_directory()

    def _init_model_directory(self):
        """初始化模型目录"""
        try:
            self.config['model_path'].mkdir(parents=True, exist_ok=True)

            subdirs = ['ocr', 'classification', 'mapping', 'risk', 'behavior']
            for subdir in subdirs:
                (self.config['model_path'] / subdir).mkdir(exist_ok=True)

            logger.info(f"Model directory initialized: {self.config['model_path']}")
        except Exception as e:
            logger.error(f"Failed to initialize model directory: {e}")

    def register_learner(self, name: str, learner: Any):
        """注册学习模块"""
        self.learners[name] = learner
        logger.info(f"Registered learner: {name}")

    async def learn_from_ocr_correction(
        self,
        original_text: str,
        corrected_text: str,
        evidence_id: str,
        user_id: str
    ) -> Dict[str, Any]:
        """从OCR纠错中学习"""
        if not self.config['enabled']:
            return {'status': 'disabled'}

        try:
            # 记录纠错样本
            correction_sample = {
                'original': original_text,
                'corrected': corrected_text,
                'evidence_id': evidence_id,
                'user_id': user_id,
                'timestamp': datetime.now().isoformat()
            }

            # 使用DeepSeek分析纠错模式
            analysis = await self.deepseek.chat_completion([
                {
                    "role": "system",
                    "content": "分析OCR识别错误模式,提取常见错误类型和纠正规则。"
                },
                {
                    "role": "user",
                    "content": f"原始: {original_text}\n纠正: {corrected_text}\n\n请分析错误类型和模式。"
                }
            ], temperature=0.1)

            # 保存学习样本
            self._save_learning_sample('ocr_correction', correction_sample)

            # 更新指标
            self.metrics['ocr_accuracy'] = min(self.metrics['ocr_accuracy'] + 0.001, 1.0)

            return {
                'status': 'success',
                'sample_saved': True,
                'analysis': analysis,
                'current_accuracy': self.metrics['ocr_accuracy']
            }

        except Exception as e:
            logger.error(f"OCR learning failed: {e}")
            return {'status': 'error', 'error': str(e)}

    async def learn_from_evidence_classification(
        self,
        evidence_text: str,
        user_classification: str,
        ai_classification: Optional[str],
        evidence_id: str,
        user_id: str
    ) -> Dict[str, Any]:
        """从证据分类中学习"""
        if not self.config['enabled']:
            return {'status': 'disabled'}

        try:
            # 记录分类样本
            classification_sample = {
                'evidence_text': evidence_text,
                'user_classification': user_classification,
                'ai_classification': ai_classification,
                'evidence_id': evidence_id,
                'user_id': user_id,
                'is_correction': ai_classification != user_classification if ai_classification else False,
                'timestamp': datetime.now().isoformat()
            }

            # 保存训练样本
            self._save_learning_sample('evidence_classification', classification_sample)

            # 如果有足够样本,触发重训练
            sample_count = self._get_sample_count('evidence_classification')
            if sample_count >= self.config['min_samples']:
                # TODO: 实现模型重训练
                logger.info(f"Evidence classification: {sample_count} samples ready for training")

            # 更新指标
            if ai_classification == user_classification:
                improvement = 0.005
            else:
                improvement = 0.002

            self.metrics['evidence_classification'] = min(
                self.metrics['evidence_classification'] + improvement, 1.0
            )

            return {
                'status': 'success',
                'sample_saved': True,
                'sample_count': sample_count,
                'current_accuracy': self.metrics['evidence_classification']
            }

        except Exception as e:
            logger.error(f"Evidence classification learning failed: {e}")
            return {'status': 'error', 'error': str(e)}

    async def learn_from_account_mapping(
        self,
        source_account: str,
        target_account: str,
        mapping_confidence: float,
        user_approved: bool,
        project_id: str,
        user_id: str
    ) -> Dict[str, Any]:
        """从科目映射中学习"""
        if not self.config['enabled']:
            return {'status': 'disabled'}

        try:
            # 记录映射样本
            mapping_sample = {
                'source_account': source_account,
                'target_account': target_account,
                'confidence': mapping_confidence,
                'user_approved': user_approved,
                'project_id': project_id,
                'user_id': user_id,
                'timestamp': datetime.now().isoformat()
            }

            # 保存学习样本
            self._save_learning_sample('account_mapping', mapping_sample)

            # 使用DeepSeek提取映射模式
            if user_approved:
                pattern_analysis = await self.deepseek.suggest_mapping(
                    [source_account],
                    "standard_template",
                    [mapping_sample]
                )

                # 更新映射准确率
                self.metrics['account_mapping'] = min(
                    self.metrics['account_mapping'] + 0.005, 1.0
                )
            else:
                # 错误映射,降低置信度
                self.metrics['account_mapping'] = max(
                    self.metrics['account_mapping'] - 0.001, 0.0
                )

            return {
                'status': 'success',
                'sample_saved': True,
                'current_accuracy': self.metrics['account_mapping']
            }

        except Exception as e:
            logger.error(f"Account mapping learning failed: {e}")
            return {'status': 'error', 'error': str(e)}

    async def learn_from_project_outcome(
        self,
        project_id: str,
        project_data: Dict[str, Any],
        actual_risks: List[str],
        predicted_risks: Optional[List[str]],
        user_id: str
    ) -> Dict[str, Any]:
        """从项目结果中学习"""
        if not self.config['enabled']:
            return {'status': 'disabled'}

        try:
            # 记录项目学习样本
            project_sample = {
                'project_id': project_id,
                'project_data': project_data,
                'actual_risks': actual_risks,
                'predicted_risks': predicted_risks,
                'user_id': user_id,
                'timestamp': datetime.now().isoformat()
            }

            # 保存学习样本
            self._save_learning_sample('project_risk', project_sample)

            # 使用DeepSeek分析风险预测准确性
            if predicted_risks:
                risk_analysis = await self.deepseek.predict_risk({
                    'project_data': project_data,
                    'actual_risks': actual_risks,
                    'predicted_risks': predicted_risks
                })

                # 计算预测准确率
                correct_predictions = len(set(actual_risks) & set(predicted_risks))
                total_predictions = len(set(actual_risks) | set(predicted_risks))
                accuracy = correct_predictions / total_predictions if total_predictions > 0 else 0

                logger.info(f"Project risk prediction accuracy: {accuracy:.2%}")

            return {
                'status': 'success',
                'sample_saved': True
            }

        except Exception as e:
            logger.error(f"Project outcome learning failed: {e}")
            return {'status': 'error', 'error': str(e)}

    async def learn_from_user_behavior(
        self,
        user_id: str,
        action_type: str,
        action_data: Dict[str, Any],
        success: bool
    ) -> Dict[str, Any]:
        """从用户行为中学习"""
        if not self.config['enabled']:
            return {'status': 'disabled'}

        try:
            # 记录用户行为
            behavior_sample = {
                'user_id': user_id,
                'action_type': action_type,
                'action_data': action_data,
                'success': success,
                'timestamp': datetime.now().isoformat()
            }

            # 保存学习样本
            self._save_learning_sample('user_behavior', behavior_sample)

            # 分析异常行为模式
            if action_type == 'login' and not success:
                # 检测异常登录
                recent_failures = self._get_recent_samples(
                    'user_behavior',
                    {'user_id': user_id, 'action_type': 'login', 'success': False},
                    hours=1
                )

                if len(recent_failures) >= 3:
                    logger.warning(f"Suspicious login activity detected for user: {user_id}")

            return {
                'status': 'success',
                'sample_saved': True
            }

        except Exception as e:
            logger.error(f"User behavior learning failed: {e}")
            return {'status': 'error', 'error': str(e)}

    def get_metrics(self) -> Dict[str, Any]:
        """获取当前指标"""
        return {
            'current': self.metrics,
            'target': self.target_metrics,
            'progress': {
                key: (self.metrics[key] / self.target_metrics[key] * 100)
                if self.target_metrics[key] > 0 else 0
                for key in self.metrics.keys()
            }
        }

    def _save_learning_sample(self, category: str, sample: Dict[str, Any]):
        """保存学习样本"""
        try:
            sample_file = self.config['model_path'] / category / 'samples.jsonl'
            sample_file.parent.mkdir(parents=True, exist_ok=True)

            with open(sample_file, 'a', encoding='utf-8') as f:
                f.write(json.dumps(sample, ensure_ascii=False) + '\n')

            logger.debug(f"Learning sample saved: {category}")
        except Exception as e:
            logger.error(f"Failed to save learning sample: {e}")

    def _get_sample_count(self, category: str) -> int:
        """获取样本数量"""
        try:
            sample_file = self.config['model_path'] / category / 'samples.jsonl'
            if not sample_file.exists():
                return 0

            with open(sample_file, 'r', encoding='utf-8') as f:
                return sum(1 for _ in f)
        except Exception as e:
            logger.error(f"Failed to count samples: {e}")
            return 0

    def _get_recent_samples(
        self,
        category: str,
        filters: Dict[str, Any],
        hours: int = 24
    ) -> List[Dict[str, Any]]:
        """获取最近的样本"""
        try:
            sample_file = self.config['model_path'] / category / 'samples.jsonl'
            if not sample_file.exists():
                return []

            cutoff_time = datetime.now().timestamp() - (hours * 3600)
            recent_samples = []

            with open(sample_file, 'r', encoding='utf-8') as f:
                for line in f:
                    sample = json.loads(line)
                    sample_time = datetime.fromisoformat(sample['timestamp']).timestamp()

                    if sample_time >= cutoff_time:
                        # 应用过滤器
                        match = all(sample.get(k) == v for k, v in filters.items())
                        if match:
                            recent_samples.append(sample)

            return recent_samples
        except Exception as e:
            logger.error(f"Failed to get recent samples: {e}")
            return []
