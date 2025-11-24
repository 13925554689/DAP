"""
DAP v2.0 - A/B Testing Framework
A/B测试框架 - 用于比较不同模型版本
"""
import logging
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta
from pathlib import Path
import json
import random
import hashlib
from collections import defaultdict
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import settings

logger = logging.getLogger(__name__)


class ABTestManager:
    """A/B测试管理器"""

    def __init__(self, model_path: Optional[Path] = None):
        self.model_path = model_path or Path(settings.AI_MODEL_PATH)
        self.ab_tests_file = self.model_path / 'ab_tests.json'
        self.ab_results_file = self.model_path / 'ab_results.jsonl'

        # 加载测试配置
        self.tests = self._load_tests()

        # 测试结果统计
        self.results_cache = defaultdict(lambda: defaultdict(list))

    def _load_tests(self) -> Dict[str, Any]:
        """加载A/B测试配置"""
        if self.ab_tests_file.exists():
            try:
                with open(self.ab_tests_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Failed to load AB tests: {e}")
        return {}

    def _save_tests(self):
        """保存A/B测试配置"""
        try:
            self.ab_tests_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.ab_tests_file, 'w', encoding='utf-8') as f:
                json.dump(self.tests, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Failed to save AB tests: {e}")

    def create_ab_test(
        self,
        test_id: str,
        model_type: str,
        version_a: int,
        version_b: int,
        traffic_split: float = 0.5,
        duration_days: int = 7,
        min_samples: int = 100,
        metrics: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        创建A/B测试

        Args:
            test_id: 测试ID
            model_type: 模型类型
            version_a: 版本A (通常是当前版本)
            version_b: 版本B (新版本)
            traffic_split: 流量分配比例 (0.5=50/50, 0.9=10/90)
            duration_days: 测试持续天数
            min_samples: 最小样本数
            metrics: 评估指标列表

        Returns:
            测试配置
        """
        try:
            if test_id in self.tests:
                return {
                    'success': False,
                    'error': f'Test {test_id} already exists'
                }

            # 默认指标
            if metrics is None:
                metrics = ['accuracy', 'precision', 'recall', 'f1_score', 'latency']

            test_config = {
                'test_id': test_id,
                'model_type': model_type,
                'version_a': version_a,
                'version_b': version_b,
                'traffic_split': traffic_split,
                'start_time': datetime.now().isoformat(),
                'end_time': (datetime.now() + timedelta(days=duration_days)).isoformat(),
                'min_samples': min_samples,
                'metrics': metrics,
                'status': 'running',
                'results': {
                    'version_a': {
                        'sample_count': 0,
                        'metrics': {}
                    },
                    'version_b': {
                        'sample_count': 0,
                        'metrics': {}
                    }
                }
            }

            self.tests[test_id] = test_config
            self._save_tests()

            logger.info(f"Created AB test: {test_id}")

            return {
                'success': True,
                'test_config': test_config
            }

        except Exception as e:
            logger.error(f"Failed to create AB test: {e}")
            return {
                'success': False,
                'error': str(e)
            }

    def assign_variant(
        self,
        test_id: str,
        user_id: Optional[str] = None,
        request_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        分配测试变体 (A或B)

        Args:
            test_id: 测试ID
            user_id: 用户ID (用于一致性哈希)
            request_id: 请求ID

        Returns:
            分配的变体
        """
        try:
            if test_id not in self.tests:
                return {
                    'error': f'Test {test_id} not found'
                }

            test_config = self.tests[test_id]

            # 检查测试是否还在运行
            if test_config['status'] != 'running':
                return {
                    'error': f'Test {test_id} is not running (status: {test_config["status"]})'
                }

            # 使用一致性哈希分配(如果有user_id)
            if user_id:
                hash_value = int(hashlib.md5(f"{test_id}:{user_id}".encode()).hexdigest(), 16)
                assigned_to_a = (hash_value % 100) / 100.0 < test_config['traffic_split']
            else:
                # 随机分配
                assigned_to_a = random.random() < test_config['traffic_split']

            variant = 'version_a' if assigned_to_a else 'version_b'
            version = test_config['version_a'] if assigned_to_a else test_config['version_b']

            return {
                'test_id': test_id,
                'variant': variant,
                'version': version,
                'model_type': test_config['model_type']
            }

        except Exception as e:
            logger.error(f"Failed to assign variant: {e}")
            return {
                'error': str(e)
            }

    def record_result(
        self,
        test_id: str,
        variant: str,
        metrics: Dict[str, float],
        latency_ms: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        记录测试结果

        Args:
            test_id: 测试ID
            variant: 变体 (version_a/version_b)
            metrics: 指标字典
            latency_ms: 延迟(毫秒)

        Returns:
            记录结果
        """
        try:
            if test_id not in self.tests:
                return {
                    'success': False,
                    'error': f'Test {test_id} not found'
                }

            test_config = self.tests[test_id]

            # 更新样本数
            test_config['results'][variant]['sample_count'] += 1

            # 更新指标(累积平均)
            for metric_name, metric_value in metrics.items():
                if metric_name not in test_config['results'][variant]['metrics']:
                    test_config['results'][variant]['metrics'][metric_name] = metric_value
                else:
                    # 计算滚动平均
                    count = test_config['results'][variant]['sample_count']
                    old_avg = test_config['results'][variant]['metrics'][metric_name]
                    new_avg = old_avg + (metric_value - old_avg) / count
                    test_config['results'][variant]['metrics'][metric_name] = new_avg

            # 记录延迟
            if latency_ms is not None:
                if 'latency' not in test_config['results'][variant]['metrics']:
                    test_config['results'][variant]['metrics']['latency'] = latency_ms
                else:
                    count = test_config['results'][variant]['sample_count']
                    old_avg = test_config['results'][variant]['metrics']['latency']
                    new_avg = old_avg + (latency_ms - old_avg) / count
                    test_config['results'][variant]['metrics']['latency'] = new_avg

            # 保存详细结果
            result_entry = {
                'test_id': test_id,
                'variant': variant,
                'metrics': metrics,
                'latency_ms': latency_ms,
                'timestamp': datetime.now().isoformat()
            }

            with open(self.ab_results_file, 'a', encoding='utf-8') as f:
                f.write(json.dumps(result_entry, ensure_ascii=False) + '\n')

            self._save_tests()

            return {
                'success': True,
                'sample_count': test_config['results'][variant]['sample_count']
            }

        except Exception as e:
            logger.error(f"Failed to record result: {e}")
            return {
                'success': False,
                'error': str(e)
            }

    def get_test_results(
        self,
        test_id: str,
        detailed: bool = False
    ) -> Dict[str, Any]:
        """
        获取测试结果

        Args:
            test_id: 测试ID
            detailed: 是否返回详细统计

        Returns:
            测试结果
        """
        try:
            if test_id not in self.tests:
                return {
                    'error': f'Test {test_id} not found'
                }

            test_config = self.tests[test_id]

            result = {
                'test_id': test_id,
                'model_type': test_config['model_type'],
                'status': test_config['status'],
                'start_time': test_config['start_time'],
                'end_time': test_config['end_time'],
                'version_a': {
                    'version': test_config['version_a'],
                    'sample_count': test_config['results']['version_a']['sample_count'],
                    'metrics': test_config['results']['version_a']['metrics']
                },
                'version_b': {
                    'version': test_config['version_b'],
                    'sample_count': test_config['results']['version_b']['sample_count'],
                    'metrics': test_config['results']['version_b']['metrics']
                }
            }

            # 计算统计显著性和推荐
            if detailed:
                result['analysis'] = self._analyze_results(test_config)

            return result

        except Exception as e:
            logger.error(f"Failed to get test results: {e}")
            return {
                'error': str(e)
            }

    def _analyze_results(self, test_config: Dict[str, Any]) -> Dict[str, Any]:
        """分析测试结果"""
        analysis = {
            'ready_for_decision': False,
            'recommendation': None,
            'confidence': None,
            'reasons': []
        }

        results_a = test_config['results']['version_a']
        results_b = test_config['results']['version_b']

        # 检查是否有足够样本
        min_samples = test_config['min_samples']
        if results_a['sample_count'] < min_samples or results_b['sample_count'] < min_samples:
            analysis['reasons'].append(
                f"Insufficient samples: A={results_a['sample_count']}, "
                f"B={results_b['sample_count']} (min={min_samples})"
            )
            return analysis

        analysis['ready_for_decision'] = True

        # 比较主要指标 (accuracy)
        metrics_a = results_a['metrics']
        metrics_b = results_b['metrics']

        if 'accuracy' in metrics_a and 'accuracy' in metrics_b:
            acc_diff = metrics_b['accuracy'] - metrics_a['accuracy']
            acc_improvement = (acc_diff / metrics_a['accuracy'] * 100) if metrics_a['accuracy'] > 0 else 0

            if abs(acc_improvement) > 2:  # 超过2%被认为是显著差异
                if acc_improvement > 0:
                    analysis['recommendation'] = 'version_b'
                    analysis['confidence'] = min(abs(acc_improvement) / 10, 1.0)
                    analysis['reasons'].append(
                        f"Version B has {acc_improvement:.1f}% better accuracy"
                    )
                else:
                    analysis['recommendation'] = 'version_a'
                    analysis['confidence'] = min(abs(acc_improvement) / 10, 1.0)
                    analysis['reasons'].append(
                        f"Version A has {abs(acc_improvement):.1f}% better accuracy"
                    )
            else:
                analysis['recommendation'] = 'no_significant_difference'
                analysis['confidence'] = 0.5
                analysis['reasons'].append("No significant difference in accuracy")

        # 比较延迟
        if 'latency' in metrics_a and 'latency' in metrics_b:
            latency_diff = metrics_b['latency'] - metrics_a['latency']
            if latency_diff > 100:  # 超过100ms
                analysis['reasons'].append(
                    f"Version B is {latency_diff:.0f}ms slower"
                )
            elif latency_diff < -100:
                analysis['reasons'].append(
                    f"Version B is {abs(latency_diff):.0f}ms faster"
                )

        return analysis

    def stop_test(
        self,
        test_id: str,
        reason: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        停止A/B测试

        Args:
            test_id: 测试ID
            reason: 停止原因

        Returns:
            停止结果
        """
        try:
            if test_id not in self.tests:
                return {
                    'success': False,
                    'error': f'Test {test_id} not found'
                }

            test_config = self.tests[test_id]
            test_config['status'] = 'stopped'
            test_config['stopped_at'] = datetime.now().isoformat()
            test_config['stop_reason'] = reason

            self._save_tests()

            logger.info(f"Stopped AB test: {test_id}")

            return {
                'success': True,
                'final_results': self.get_test_results(test_id, detailed=True)
            }

        except Exception as e:
            logger.error(f"Failed to stop test: {e}")
            return {
                'success': False,
                'error': str(e)
            }

    def list_tests(
        self,
        status: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        列出所有测试

        Args:
            status: 过滤状态 (running/stopped/completed)

        Returns:
            测试列表
        """
        tests = []

        for test_id, config in self.tests.items():
            if status is None or config['status'] == status:
                tests.append({
                    'test_id': test_id,
                    'model_type': config['model_type'],
                    'versions': f"v{config['version_a']} vs v{config['version_b']}",
                    'status': config['status'],
                    'start_time': config['start_time'],
                    'samples_a': config['results']['version_a']['sample_count'],
                    'samples_b': config['results']['version_b']['sample_count']
                })

        return tests


# 全局实例
_ab_test_manager = None


def get_ab_test_manager() -> ABTestManager:
    """获取A/B测试管理器单例"""
    global _ab_test_manager
    if _ab_test_manager is None:
        _ab_test_manager = ABTestManager()
    return _ab_test_manager
