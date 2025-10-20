#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Enhanced Data Ingestor - 增强版数据接入器
智能识别和处理多种财务系统数据源

支持系统：
- 金蝶 (Kingdee): K/3 Cloud, K/3 WISE, KIS系列
- 用友 (UFIDA): U8+, NC, YonBIP系列
- SAP: ERP, S/4HANA
- 其他ERP: 浪潮、博科、速达等
- AIS系统: 特殊格式支持
"""

import asyncio
import logging
import os
import time
from pathlib import Path
from typing import Dict, Any, List, Optional, Union
import pandas as pd
import json
import zipfile
import rarfile
import py7zr
from concurrent.futures import ThreadPoolExecutor
import threading

# 导入现有数据接入器作为基础
try:
    from .data_ingestor import DataIngestor
except ImportError:
    from data_ingestor import DataIngestor

# AI和ML相关导入
try:
    import numpy as np
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.metrics.pairwise import cosine_similarity
    ML_AVAILABLE = True
except ImportError:
    ML_AVAILABLE = False

logger = logging.getLogger(__name__)

class FinancialSystemDetector:
    """财务系统智能检测器"""

    def __init__(self):
        self.system_signatures = {
            'kingdee': {
                'keywords': ['金蝶', 'kingdee', 'k3', 'kis', 'cloud', '云'],
                'file_patterns': ['*.k3', '*.kis', '*kingdee*'],
                'table_patterns': ['t_bd_account', 't_gl_voucher', 't_ar_receivable'],
                'backup_patterns': ['KDBackup', 'K3Backup']
            },
            'ufida': {
                'keywords': ['用友', 'ufida', 'u8', 'nc', 'yonbip'],
                'file_patterns': ['*.acc', '*.u8', '*ufida*'],
                'table_patterns': ['code', 'ua_account', 'gl_accvouch'],
                'backup_patterns': ['UFBackup', 'U8Backup']
            },
            'sap': {
                'keywords': ['sap', 's4hana', 'hana', 'abap'],
                'file_patterns': ['*sap*', '*.rfc'],
                'table_patterns': ['bkpf', 'bseg', 'ska1', 'skb1'],
                'backup_patterns': ['SAPBackup']
            },
            'ais': {
                'keywords': ['ais', '泰田', 'taitain', 'audit'],
                'file_patterns': ['*.ais', '*泰田*'],
                'table_patterns': ['audit_', 'ais_'],
                'backup_patterns': ['AISBackup']
            }
        }

        if ML_AVAILABLE:
            self.vectorizer = TfidfVectorizer(stop_words='english')
            self._train_detector()

    def _train_detector(self):
        """训练系统检测模型"""
        if not ML_AVAILABLE:
            return

        # 准备训练文本
        training_texts = []
        training_labels = []

        for system, info in self.system_signatures.items():
            text = ' '.join(info['keywords'] + info['file_patterns'] + info['table_patterns'])
            training_texts.append(text)
            training_labels.append(system)

        try:
            self.training_vectors = self.vectorizer.fit_transform(training_texts)
            self.labels = training_labels
            logger.info("System detector model trained successfully")
        except Exception as e:
            logger.warning(f"Failed to train detector model: {e}")

    def detect_system_type(self, file_path: str, file_content: str = None,
                          table_names: List[str] = None) -> Dict[str, Any]:
        """
        智能检测财务系统类型

        Args:
            file_path: 文件路径
            file_content: 文件内容样例
            table_names: 表名列表

        Returns:
            检测结果字典
        """
        result = {
            'detected_system': 'unknown',
            'confidence': 0.0,
            'evidence': [],
            'recommendations': []
        }

        # 特征提取
        features = self._extract_features(file_path, file_content, table_names)

        # 规则基检测
        rule_result = self._rule_based_detection(features)

        # AI模型检测 (如果可用)
        if ML_AVAILABLE and hasattr(self, 'training_vectors'):
            ml_result = self._ml_based_detection(features)

            # 结合规则和ML结果
            if rule_result['confidence'] > 0.7:
                result = rule_result
            elif ml_result['confidence'] > 0.6:
                result = ml_result
            else:
                result = rule_result if rule_result['confidence'] > ml_result['confidence'] else ml_result
        else:
            result = rule_result

        return result

    def _extract_features(self, file_path: str, file_content: str = None,
                         table_names: List[str] = None) -> Dict[str, Any]:
        """提取文件特征"""
        features = {
            'filename': Path(file_path).name.lower(),
            'extension': Path(file_path).suffix.lower(),
            'content_sample': file_content[:1000] if file_content else "",
            'table_names': table_names or [],
            'file_size': 0
        }

        try:
            if os.path.exists(file_path):
                features['file_size'] = os.path.getsize(file_path)
        except:
            pass

        return features

    def _rule_based_detection(self, features: Dict[str, Any]) -> Dict[str, Any]:
        """基于规则的系统检测"""
        scores = {}
        evidence = []

        for system, signatures in self.system_signatures.items():
            score = 0
            system_evidence = []

            # 关键词匹配
            text_to_check = f"{features['filename']} {features['content_sample']}"
            for keyword in signatures['keywords']:
                if keyword in text_to_check.lower():
                    score += 2
                    system_evidence.append(f"Keyword match: {keyword}")

            # 文件模式匹配
            import fnmatch
            for pattern in signatures['file_patterns']:
                if fnmatch.fnmatch(features['filename'], pattern.lower()):
                    score += 3
                    system_evidence.append(f"File pattern match: {pattern}")

            # 表名模式匹配
            for table_name in features['table_names']:
                for pattern in signatures['table_patterns']:
                    if pattern.lower() in table_name.lower():
                        score += 4
                        system_evidence.append(f"Table pattern match: {pattern}")

            scores[system] = score
            if score > 0:
                evidence.extend(system_evidence)

        if not scores or max(scores.values()) == 0:
            return {
                'detected_system': 'unknown',
                'confidence': 0.0,
                'evidence': [],
                'recommendations': ['Manual system type specification recommended']
            }

        best_system = max(scores, key=scores.get)
        max_score = scores[best_system]
        confidence = min(1.0, max_score / 10.0)  # 归一化到0-1

        return {
            'detected_system': best_system,
            'confidence': confidence,
            'evidence': evidence,
            'recommendations': self._get_recommendations(best_system, confidence)
        }

    def _ml_based_detection(self, features: Dict[str, Any]) -> Dict[str, Any]:
        """基于机器学习的系统检测"""
        if not ML_AVAILABLE or not hasattr(self, 'training_vectors'):
            return {'detected_system': 'unknown', 'confidence': 0.0, 'evidence': [], 'recommendations': []}

        try:
            # 构建查询文本
            query_text = f"{features['filename']} {features['content_sample']} {' '.join(features['table_names'])}"
            query_vector = self.vectorizer.transform([query_text])

            # 计算相似度
            similarities = cosine_similarity(query_vector, self.training_vectors)[0]

            best_idx = np.argmax(similarities)
            best_similarity = similarities[best_idx]
            best_system = self.labels[best_idx]

            return {
                'detected_system': best_system,
                'confidence': float(best_similarity),
                'evidence': [f"ML similarity score: {best_similarity:.3f}"],
                'recommendations': self._get_recommendations(best_system, best_similarity)
            }

        except Exception as e:
            logger.warning(f"ML detection failed: {e}")
            return {'detected_system': 'unknown', 'confidence': 0.0, 'evidence': [], 'recommendations': []}

    def _get_recommendations(self, system: str, confidence: float) -> List[str]:
        """获取处理建议"""
        recommendations = []

        if confidence < 0.5:
            recommendations.append("Low confidence detection - manual verification recommended")

        if system == 'kingdee':
            recommendations.append("Use Kingdee-specific parsers for optimal results")
        elif system == 'ufida':
            recommendations.append("Apply UFIDA data structure parsing")
        elif system == 'sap':
            recommendations.append("Use SAP RFC connection if available")
        elif system == 'ais':
            recommendations.append("Apply AIS-specific data extraction methods")

        return recommendations

class EnhancedDataIngestor:
    """增强版数据接入器"""

    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        self.logger = logging.getLogger(__name__)

        # 系统检测器
        self.system_detector = FinancialSystemDetector()

        # 基础数据接入器
        self.base_ingestor = DataIngestor()

        # 并发处理配置
        self.max_workers = self.config.get('max_workers', 4)
        self.max_files_per_batch = self.config.get('max_files_per_batch', 100)

        # 支持的文件类型
        self.supported_extensions = {
            '.xlsx', '.xls',  # Excel
            '.csv',           # CSV
            '.bak', '.sql',   # SQL备份
            '.db', '.sqlite', '.mdb', '.accdb',  # 数据库文件
            '.ais',           # AIS特殊格式
            '.zip', '.rar', '.7z'  # 压缩文件
        }

        self.logger.info("Enhanced Data Ingestor initialized")

    async def ingest_intelligent(self, data_source: str, options: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        智能数据接入主入口

        Args:
            data_source: 数据源路径
            options: 处理选项

        Returns:
            接入结果
        """
        options = options or {}

        self.logger.info(f"Starting intelligent ingestion for: {data_source}")

        try:
            # 检测数据源类型
            source_info = await self._analyze_data_source(data_source)

            # 选择最佳处理策略
            strategy = self._select_processing_strategy(source_info)

            # 执行数据接入
            if strategy == 'single_file':
                result = await self._process_single_file(data_source, source_info, options)
            elif strategy == 'batch_files':
                result = await self._process_batch_files(data_source, source_info, options)
            elif strategy == 'archive_file':
                result = await self._process_archive_file(data_source, source_info, options)
            elif strategy == 'database_connection':
                result = await self._process_database_connection(data_source, source_info, options)
            else:
                raise ValueError(f"Unknown processing strategy: {strategy}")

            # 后处理
            result = await self._post_process_results(result, source_info, options)

            self.logger.info(f"Intelligent ingestion completed successfully")
            return result

        except Exception as e:
            self.logger.error(f"Intelligent ingestion failed: {e}")
            raise

    async def _analyze_data_source(self, data_source: str) -> Dict[str, Any]:
        """分析数据源"""
        source_path = Path(data_source)

        info = {
            'path': data_source,
            'exists': source_path.exists(),
            'is_file': source_path.is_file() if source_path.exists() else False,
            'is_directory': source_path.is_dir() if source_path.exists() else False,
            'extension': source_path.suffix.lower() if source_path.is_file() else '',
            'size': source_path.stat().st_size if source_path.exists() and source_path.is_file() else 0,
            'system_detection': None,
            'content_preview': None
        }

        if info['is_file']:
            # 检测财务系统类型
            content_preview = await self._get_content_preview(data_source)
            info['content_preview'] = content_preview

            system_detection = self.system_detector.detect_system_type(
                data_source, content_preview
            )
            info['system_detection'] = system_detection

        elif info['is_directory']:
            # 分析目录内容
            files = list(source_path.glob('**/*'))
            info['file_count'] = len([f for f in files if f.is_file()])
            info['supported_files'] = [
                str(f) for f in files
                if f.is_file() and f.suffix.lower() in self.supported_extensions
            ]

        return info

    async def _get_content_preview(self, file_path: str, max_size: int = 1024) -> str:
        """获取文件内容预览"""
        try:
            with open(file_path, 'rb') as f:
                content = f.read(max_size)

            # 尝试解码为文本
            for encoding in ['utf-8', 'gbk', 'gb2312', 'latin1']:
                try:
                    return content.decode(encoding)
                except UnicodeDecodeError:
                    continue

            # 如果都失败，返回十六进制表示
            return content.hex()[:200]

        except Exception as e:
            self.logger.warning(f"Failed to get content preview for {file_path}: {e}")
            return ""

    def _select_processing_strategy(self, source_info: Dict[str, Any]) -> str:
        """选择最佳处理策略"""
        if not source_info['exists']:
            raise FileNotFoundError(f"Data source not found: {source_info['path']}")

        if source_info['is_file']:
            ext = source_info['extension']

            if ext in ['.zip', '.rar', '.7z']:
                return 'archive_file'
            elif ext in ['.db', '.sqlite', '.mdb', '.accdb']:
                return 'database_connection'
            else:
                return 'single_file'

        elif source_info['is_directory']:
            if len(source_info.get('supported_files', [])) > 1:
                return 'batch_files'
            elif len(source_info.get('supported_files', [])) == 1:
                return 'single_file'
            else:
                raise ValueError("No supported files found in directory")

        raise ValueError(f"Cannot determine processing strategy for: {source_info['path']}")

    async def _process_single_file(self, file_path: str, source_info: Dict[str, Any],
                                 options: Dict[str, Any]) -> Dict[str, Any]:
        """处理单个文件"""
        self.logger.info(f"Processing single file: {file_path}")

        # 使用基础接入器处理
        try:
            data = self.base_ingestor.ingest(file_path)

            return {
                'strategy': 'single_file',
                'source_info': source_info,
                'data': data,
                'statistics': {
                    'files_processed': 1,
                    'tables_found': len(data) if isinstance(data, dict) else 0,
                    'total_records': sum(len(table) for table in data.values()) if isinstance(data, dict) else 0
                }
            }

        except Exception as e:
            self.logger.error(f"Failed to process single file {file_path}: {e}")
            raise

    async def _process_batch_files(self, directory: str, source_info: Dict[str, Any],
                                 options: Dict[str, Any]) -> Dict[str, Any]:
        """批量处理文件"""
        self.logger.info(f"Processing batch files in: {directory}")

        supported_files = source_info.get('supported_files', [])

        if len(supported_files) > self.max_files_per_batch:
            self.logger.warning(f"Too many files ({len(supported_files)}), limiting to {self.max_files_per_batch}")
            supported_files = supported_files[:self.max_files_per_batch]

        # 并行处理文件
        results = {}
        failed_files = []

        async def process_file(file_path: str) -> tuple:
            try:
                loop = asyncio.get_event_loop()
                data = await loop.run_in_executor(None, self.base_ingestor.ingest, file_path)
                return file_path, data, None
            except Exception as e:
                return file_path, None, str(e)

        # 创建并发任务
        tasks = [process_file(file_path) for file_path in supported_files]

        # 执行并收集结果
        completed_tasks = await asyncio.gather(*tasks, return_exceptions=True)

        for result in completed_tasks:
            if isinstance(result, Exception):
                self.logger.error(f"Task failed with exception: {result}")
                continue

            file_path, data, error = result

            if error:
                failed_files.append({'file': file_path, 'error': error})
                self.logger.error(f"Failed to process {file_path}: {error}")
            else:
                results[file_path] = data

        return {
            'strategy': 'batch_files',
            'source_info': source_info,
            'data': results,
            'failed_files': failed_files,
            'statistics': {
                'files_processed': len(results),
                'files_failed': len(failed_files),
                'total_files': len(supported_files),
                'success_rate': len(results) / len(supported_files) if supported_files else 0
            }
        }

    async def _process_archive_file(self, archive_path: str, source_info: Dict[str, Any],
                                  options: Dict[str, Any]) -> Dict[str, Any]:
        """处理压缩文件"""
        self.logger.info(f"Processing archive file: {archive_path}")

        extract_dir = Path("temp/extracted") / f"archive_{int(time.time())}"
        extract_dir.mkdir(parents=True, exist_ok=True)

        try:
            # 提取压缩文件
            await self._extract_archive(archive_path, str(extract_dir))

            # 递归处理提取的文件
            extracted_source_info = await self._analyze_data_source(str(extract_dir))

            if extracted_source_info['is_directory'] and extracted_source_info.get('supported_files'):
                return await self._process_batch_files(str(extract_dir), extracted_source_info, options)
            else:
                raise ValueError("No supported files found in archive")

        finally:
            # 清理临时文件
            import shutil
            try:
                shutil.rmtree(extract_dir)
            except Exception as e:
                self.logger.warning(f"Failed to cleanup temporary directory {extract_dir}: {e}")

    async def _extract_archive(self, archive_path: str, extract_dir: str):
        """提取压缩文件"""
        ext = Path(archive_path).suffix.lower()

        if ext == '.zip':
            with zipfile.ZipFile(archive_path, 'r') as zip_ref:
                zip_ref.extractall(extract_dir)
        elif ext == '.rar':
            with rarfile.RarFile(archive_path, 'r') as rar_ref:
                rar_ref.extractall(extract_dir)
        elif ext == '.7z':
            with py7zr.SevenZipFile(archive_path, 'r') as sevenz_ref:
                sevenz_ref.extractall(extract_dir)
        else:
            raise ValueError(f"Unsupported archive format: {ext}")

    async def _process_database_connection(self, db_path: str, source_info: Dict[str, Any],
                                         options: Dict[str, Any]) -> Dict[str, Any]:
        """处理数据库连接"""
        self.logger.info(f"Processing database connection: {db_path}")

        # 使用基础接入器的数据库处理功能
        try:
            data = self.base_ingestor.ingest(db_path)

            return {
                'strategy': 'database_connection',
                'source_info': source_info,
                'data': data,
                'statistics': {
                    'tables_found': len(data) if isinstance(data, dict) else 0,
                    'total_records': sum(len(table) for table in data.values()) if isinstance(data, dict) else 0
                }
            }

        except Exception as e:
            self.logger.error(f"Failed to process database {db_path}: {e}")
            raise

    async def _post_process_results(self, result: Dict[str, Any], source_info: Dict[str, Any],
                                  options: Dict[str, Any]) -> Dict[str, Any]:
        """后处理结果"""
        # 添加元数据
        result['metadata'] = {
            'ingestion_time': time.time(),
            'system_detection': source_info.get('system_detection'),
            'processing_options': options,
            'data_quality_score': self._calculate_data_quality_score(result.get('data', {}))
        }

        return result

    def _calculate_data_quality_score(self, data: Dict[str, Any]) -> float:
        """计算数据质量分数"""
        if not isinstance(data, dict) or not data:
            return 0.0

        total_score = 0
        total_weight = 0

        for table_name, table_data in data.items():
            if isinstance(table_data, pd.DataFrame):
                # 计算表的质量分数
                table_score = 0
                weight = len(table_data)

                # 非空率
                non_null_ratio = 1 - table_data.isnull().sum().sum() / (table_data.shape[0] * table_data.shape[1])
                table_score += non_null_ratio * 0.4

                # 数据类型一致性
                consistency_score = 1.0  # 简化实现
                table_score += consistency_score * 0.3

                # 记录数量合理性
                record_score = min(1.0, len(table_data) / 1000)  # 假设1000条记录为满分
                table_score += record_score * 0.3

                total_score += table_score * weight
                total_weight += weight

        return total_score / total_weight if total_weight > 0 else 0.0

# 测试函数
async def test_enhanced_ingestor():
    """测试增强版数据接入器"""
    print("Testing Enhanced Data Ingestor...")

    ingestor = EnhancedDataIngestor()

    # 测试系统检测
    detector = FinancialSystemDetector()
    test_result = detector.detect_system_type("test_kingdee_backup.bak", "金蝶K3备份文件")
    print(f"System Detection Test: {test_result}")

if __name__ == "__main__":
    asyncio.run(test_enhanced_ingestor())