"""
DAP v2.0 - Training Data Preparation Module
训练数据准备和预处理模块
"""
import logging
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta
from pathlib import Path
import json
import random
import hashlib
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import settings

logger = logging.getLogger(__name__)


class TrainingDataPreparer:
    """训练数据准备器"""

    def __init__(self, model_path: Optional[Path] = None):
        self.model_path = model_path or Path(settings.AI_MODEL_PATH)
        self.validation_ratio = 0.2  # 验证集比例
        self.test_ratio = 0.1  # 测试集比例
        self.random_seed = 42

    def prepare_classification_data(
        self,
        samples: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        准备证据分类训练数据

        Args:
            samples: 原始样本列表

        Returns:
            {
                'train': [...],
                'validation': [...],
                'test': [...],
                'label_stats': {...},
                'quality_metrics': {...}
            }
        """
        try:
            # 1. 数据清洗
            cleaned_samples = self._clean_classification_samples(samples)

            if not cleaned_samples:
                return {'error': '没有有效样本'}

            # 2. 数据验证
            validation_result = self._validate_samples(cleaned_samples)
            if not validation_result['valid']:
                logger.warning(f"Data validation issues: {validation_result['issues']}")

            # 3. 标签统计
            label_stats = self._calculate_label_distribution(cleaned_samples)

            # 4. 数据增强 (可选)
            augmented_samples = self._augment_samples_if_needed(
                cleaned_samples,
                label_stats
            )

            # 5. 分割数据集
            train, val, test = self._split_dataset(augmented_samples)

            # 6. 质量指标
            quality_metrics = {
                'total_samples': len(cleaned_samples),
                'augmented_samples': len(augmented_samples) - len(cleaned_samples),
                'train_size': len(train),
                'val_size': len(val),
                'test_size': len(test),
                'label_balance_score': self._calculate_balance_score(label_stats),
                'avg_text_length': sum(len(s.get('evidence_text', '')) for s in cleaned_samples) / len(cleaned_samples),
                'unique_labels': len(label_stats)
            }

            logger.info(f"Training data prepared: {quality_metrics}")

            return {
                'train': train,
                'validation': val,
                'test': test,
                'label_stats': label_stats,
                'quality_metrics': quality_metrics,
                'preparation_time': datetime.now().isoformat()
            }

        except Exception as e:
            logger.error(f"Data preparation failed: {e}")
            return {'error': str(e)}

    def prepare_ocr_data(
        self,
        samples: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """准备OCR纠错训练数据"""
        try:
            # 清洗纠错样本
            cleaned_samples = []
            for sample in samples:
                original = sample.get('original', '')
                corrected = sample.get('corrected', '')

                if original and corrected and original != corrected:
                    cleaned_samples.append({
                        'original': original,
                        'corrected': corrected,
                        'evidence_id': sample.get('evidence_id'),
                        'timestamp': sample.get('timestamp')
                    })

            # 提取纠错模式
            patterns = self._extract_correction_patterns(cleaned_samples)

            # 分割数据集
            train, val, test = self._split_dataset(cleaned_samples)

            return {
                'train': train,
                'validation': val,
                'test': test,
                'correction_patterns': patterns,
                'pattern_count': len(patterns),
                'sample_count': len(cleaned_samples)
            }

        except Exception as e:
            logger.error(f"OCR data preparation failed: {e}")
            return {'error': str(e)}

    def prepare_mapping_data(
        self,
        samples: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """准备账户映射训练数据"""
        try:
            # 过滤有效映射
            valid_mappings = [
                s for s in samples
                if s.get('source_account') and s.get('target_account')
            ]

            # 统计映射模式
            mapping_stats = {}
            for sample in valid_mappings:
                source = sample['source_account']
                target = sample['target_account']
                key = f"{source}->{target}"

                if key not in mapping_stats:
                    mapping_stats[key] = {
                        'count': 0,
                        'approved_count': 0,
                        'avg_confidence': 0.0
                    }

                mapping_stats[key]['count'] += 1
                if sample.get('user_approved'):
                    mapping_stats[key]['approved_count'] += 1

                confidence = sample.get('confidence', 0.0)
                mapping_stats[key]['avg_confidence'] = (
                    (mapping_stats[key]['avg_confidence'] * (mapping_stats[key]['count'] - 1) + confidence)
                    / mapping_stats[key]['count']
                )

            # 分割数据集
            train, val, test = self._split_dataset(valid_mappings)

            return {
                'train': train,
                'validation': val,
                'test': test,
                'mapping_stats': mapping_stats,
                'unique_mappings': len(mapping_stats),
                'sample_count': len(valid_mappings)
            }

        except Exception as e:
            logger.error(f"Mapping data preparation failed: {e}")
            return {'error': str(e)}

    def _clean_classification_samples(
        self,
        samples: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """清洗分类样本"""
        cleaned = []

        for sample in samples:
            # 必须字段
            if not sample.get('evidence_text') or not sample.get('user_classification'):
                continue

            # 去除过短文本
            text = sample['evidence_text'].strip()
            if len(text) < 5:
                continue

            # 标准化标签
            label = sample['user_classification'].strip().lower()

            cleaned.append({
                'evidence_text': text,
                'user_classification': label,
                'evidence_id': sample.get('evidence_id'),
                'timestamp': sample.get('timestamp'),
                'ai_classification': sample.get('ai_classification')
            })

        return cleaned

    def _validate_samples(
        self,
        samples: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """验证样本质量"""
        issues = []

        # 检查样本数量
        if len(samples) < 10:
            issues.append(f"样本数量过少: {len(samples)}")

        # 检查重复样本
        unique_texts = set()
        duplicates = 0
        for sample in samples:
            text_hash = hashlib.md5(sample['evidence_text'].encode()).hexdigest()
            if text_hash in unique_texts:
                duplicates += 1
            unique_texts.add(text_hash)

        if duplicates > len(samples) * 0.3:
            issues.append(f"重复样本比例过高: {duplicates/len(samples):.1%}")

        # 检查标签分布
        from collections import Counter
        label_counts = Counter(s['user_classification'] for s in samples)
        if len(label_counts) < 2:
            issues.append("标签种类不足")

        return {
            'valid': len(issues) == 0,
            'issues': issues,
            'duplicate_rate': duplicates / len(samples) if samples else 0,
            'unique_labels': len(label_counts)
        }

    def _calculate_label_distribution(
        self,
        samples: List[Dict[str, Any]]
    ) -> Dict[str, int]:
        """计算标签分布"""
        from collections import Counter
        labels = [s['user_classification'] for s in samples]
        return dict(Counter(labels))

    def _augment_samples_if_needed(
        self,
        samples: List[Dict[str, Any]],
        label_stats: Dict[str, int]
    ) -> List[Dict[str, Any]]:
        """数据增强(如果需要)"""
        # 如果标签不平衡,进行过采样
        max_count = max(label_stats.values()) if label_stats else 0
        min_count = min(label_stats.values()) if label_stats else 0

        # 如果最大和最小差异超过3倍,进行增强
        if max_count > 3 * min_count:
            logger.info("Applying data augmentation for imbalanced labels")

            augmented = samples.copy()

            for label, count in label_stats.items():
                if count < max_count * 0.5:
                    # 找到该标签的所有样本
                    label_samples = [s for s in samples if s['user_classification'] == label]

                    # 过采样到目标数量
                    target_count = int(max_count * 0.5)
                    needed = target_count - count

                    if needed > 0:
                        # 重复采样
                        additional = random.choices(label_samples, k=needed)
                        augmented.extend(additional)

            logger.info(f"Augmented {len(augmented) - len(samples)} samples")
            return augmented

        return samples

    def _split_dataset(
        self,
        samples: List[Dict[str, Any]]
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, Any]]]:
        """分割数据集为训练/验证/测试"""
        # 设置随机种子确保可重现
        random.seed(self.random_seed)

        # 打乱数据
        shuffled = samples.copy()
        random.shuffle(shuffled)

        # 计算分割点
        total = len(shuffled)
        test_size = int(total * self.test_ratio)
        val_size = int(total * self.validation_ratio)

        test = shuffled[:test_size]
        val = shuffled[test_size:test_size + val_size]
        train = shuffled[test_size + val_size:]

        return train, val, test

    def _calculate_balance_score(
        self,
        label_stats: Dict[str, int]
    ) -> float:
        """
        计算标签平衡度分数(0-1)
        1.0表示完全平衡, 0.0表示极度不平衡
        """
        if not label_stats:
            return 0.0

        counts = list(label_stats.values())
        max_count = max(counts)
        min_count = min(counts)

        if max_count == 0:
            return 0.0

        # 使用最小/最大比例作为平衡度
        return min_count / max_count

    def _extract_correction_patterns(
        self,
        samples: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """提取常见纠错模式"""
        from collections import Counter

        # 统计字符级别的纠错
        char_corrections = Counter()

        for sample in samples:
            original = sample['original']
            corrected = sample['corrected']

            # 简单的字符差异检测
            if len(original) == len(corrected):
                for i, (o_char, c_char) in enumerate(zip(original, corrected)):
                    if o_char != c_char:
                        char_corrections[(o_char, c_char)] += 1

        # 提取top N模式
        top_patterns = []
        for (orig_char, corr_char), count in char_corrections.most_common(50):
            top_patterns.append({
                'original': orig_char,
                'corrected': corr_char,
                'frequency': count,
                'confidence': min(count / 10, 1.0)  # 基于频率计算置信度
            })

        return top_patterns

    def export_prepared_data(
        self,
        prepared_data: Dict[str, Any],
        output_path: Path,
        format: str = 'jsonl'
    ) -> bool:
        """导出准备好的数据"""
        try:
            output_path.mkdir(parents=True, exist_ok=True)

            if format == 'jsonl':
                # 导出为JSONL格式
                for split in ['train', 'validation', 'test']:
                    if split in prepared_data:
                        file_path = output_path / f"{split}.jsonl"
                        with open(file_path, 'w', encoding='utf-8') as f:
                            for sample in prepared_data[split]:
                                f.write(json.dumps(sample, ensure_ascii=False) + '\n')

                # 导出元数据
                metadata = {
                    'label_stats': prepared_data.get('label_stats', {}),
                    'quality_metrics': prepared_data.get('quality_metrics', {}),
                    'preparation_time': prepared_data.get('preparation_time')
                }

                with open(output_path / 'metadata.json', 'w', encoding='utf-8') as f:
                    json.dump(metadata, f, indent=2, ensure_ascii=False)

            logger.info(f"Data exported to {output_path}")
            return True

        except Exception as e:
            logger.error(f"Export failed: {e}")
            return False

    def load_prepared_data(
        self,
        input_path: Path
    ) -> Dict[str, Any]:
        """加载准备好的数据"""
        try:
            result = {}

            # 加载各个分割
            for split in ['train', 'validation', 'test']:
                file_path = input_path / f"{split}.jsonl"
                if file_path.exists():
                    samples = []
                    with open(file_path, 'r', encoding='utf-8') as f:
                        for line in f:
                            samples.append(json.loads(line))
                    result[split] = samples

            # 加载元数据
            metadata_path = input_path / 'metadata.json'
            if metadata_path.exists():
                with open(metadata_path, 'r', encoding='utf-8') as f:
                    metadata = json.load(f)
                    result.update(metadata)

            logger.info(f"Data loaded from {input_path}")
            return result

        except Exception as e:
            logger.error(f"Load failed: {e}")
            return {}


# 全局实例
_data_preparer = None


def get_data_preparer() -> TrainingDataPreparer:
    """获取数据准备器单例"""
    global _data_preparer
    if _data_preparer is None:
        _data_preparer = TrainingDataPreparer()
    return _data_preparer
