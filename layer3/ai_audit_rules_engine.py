"""
AI增强的审计规则引擎 - Layer 3
自学习审计规则与ML能力

核心功能：
1. 自学习审计规则引擎
2. 机器学习驱动的规则发现
3. 审计专家知识图谱
4. 规则优化和演进
5. 智能风险评估
"""

import asyncio
import logging
import json
import sqlite3
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple, Set, Union
from pathlib import Path
from dataclasses import dataclass, asdict
from concurrent.futures import ThreadPoolExecutor
import threading
from collections import defaultdict, Counter
import pickle
import hashlib
from enum import Enum

from utils.async_utils import schedule_async_task

# 机器学习库
try:
    from sklearn.ensemble import IsolationForest, RandomForestClassifier
    from sklearn.cluster import DBSCAN
    from sklearn.preprocessing import StandardScaler
    from sklearn.model_selection import train_test_split
    from sklearn.metrics import classification_report, precision_recall_fscore_support

    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False

try:
    import xgboost as xgb

    XGBOOST_AVAILABLE = True
except ImportError:
    XGBOOST_AVAILABLE = False

# NLP和文本处理
try:
    import jieba
    import jieba.analyse

    JIEBA_AVAILABLE = True
except ImportError:
    JIEBA_AVAILABLE = False

# 规则引擎
try:
    import rule_engine

    RULE_ENGINE_AVAILABLE = True
except ImportError:
    RULE_ENGINE_AVAILABLE = False

# 向量数据库
try:
    import chromadb

    CHROMADB_AVAILABLE = True
except ImportError:
    CHROMADB_AVAILABLE = False


class RuleType(Enum):
    """规则类型"""

    VALIDATION = "validation"  # 数据验证规则
    BUSINESS = "business"  # 业务逻辑规则
    ANOMALY = "anomaly"  # 异常检测规则
    COMPLIANCE = "compliance"  # 合规性规则
    RISK = "risk"  # 风险评估规则


class RuleSeverity(Enum):
    """规则严重性"""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class RuleStatus(Enum):
    """规则状态"""

    ACTIVE = "active"
    INACTIVE = "inactive"
    TESTING = "testing"
    DEPRECATED = "deprecated"


@dataclass
class AuditRule:
    """审计规则"""

    rule_id: str
    rule_name: str
    rule_type: RuleType
    condition: str
    action: str
    severity: RuleSeverity
    confidence: float
    created_at: datetime
    updated_at: datetime
    created_by: str
    description: str
    metadata: Dict[str, Any]
    status: RuleStatus
    execution_count: int
    success_rate: float


@dataclass
class RuleViolation:
    """规则违反记录"""

    violation_id: str
    rule_id: str
    data_record: Dict[str, Any]
    violation_details: Dict[str, Any]
    severity: RuleSeverity
    detected_at: datetime
    resolved: bool
    resolution_notes: str


@dataclass
class AuditPattern:
    """审计模式"""

    pattern_id: str
    pattern_name: str
    pattern_type: str
    conditions: List[str]
    support: float
    confidence: float
    discovered_at: datetime
    instances: List[Dict[str, Any]]


class AIAuditRulesEngine:
    """AI增强的审计规则引擎"""

    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        self.logger = logging.getLogger(__name__)

        # 数据库配置
        self.rules_db_path = self.config.get("rules_db_path", "data/audit_rules.db")
        self.models_path = self.config.get("models_path", "data/models/audit/")

        # ML配置
        self.anomaly_threshold = self.config.get("anomaly_threshold", 0.1)
        self.min_confidence = self.config.get("min_confidence", 0.7)
        self.learning_rate = self.config.get("learning_rate", 0.1)

        # 规则缓存
        self.active_rules = {}
        self.rule_cache = {}
        self.violation_cache = {}

        # ML模型
        self.anomaly_detector = None
        self.rule_classifier = None
        self.pattern_miner = None

        # 并发控制
        self.max_workers = self.config.get("max_workers", 4)
        self.executor = ThreadPoolExecutor(max_workers=self.max_workers)
        self._lock = threading.RLock()

        # 向量数据库（可选）
        if CHROMADB_AVAILABLE:
            try:
                self.chroma_client = chromadb.Client()
                self.rules_collection = self.chroma_client.get_or_create_collection(
                    "audit_rules"
                )
            except:
                self.chroma_client = None
                self.rules_collection = None
        else:
            self.chroma_client = None
            self.rules_collection = None

        # 中文NLP支持
        if JIEBA_AVAILABLE:
            # 加载审计专业词典
            self._load_audit_dictionary()

        # 确保模型目录存在
        Path(self.models_path).mkdir(parents=True, exist_ok=True)

        # 初始化数据库
        self._init_database()

        # 加载现有规则和模型
        schedule_async_task(
            self._load_existing_rules, logger=self.logger, task_name="load_audit_rules"
        )
        schedule_async_task(
            self._load_ml_models, logger=self.logger, task_name="load_audit_models"
        )

    def _load_audit_dictionary(self):
        """加载审计专业词典"""
        try:
            audit_terms = [
                "会计科目",
                "借贷方向",
                "凭证号",
                "摘要",
                "金额",
                "余额",
                "资产",
                "负债",
                "所有者权益",
                "收入",
                "费用",
                "利润",
                "现金流量",
                "应收账款",
                "应付账款",
                "存货",
                "固定资产",
                "累计折旧",
                "无形资产",
                "商誉",
                "预付账款",
                "预收账款",
                "主营业务收入",
                "营业外收入",
                "管理费用",
                "销售费用",
                "财务费用",
                "营业税金及附加",
                "所得税费用",
                "审计",
                "内控",
                "风险",
                "合规",
                "稽核",
                "检查",
            ]

            for term in audit_terms:
                jieba.add_word(term)

            self.logger.info("审计专业词典加载完成")

        except Exception as e:
            self.logger.error(f"加载审计词典失败: {e}")

    def _init_database(self):
        """初始化规则数据库"""
        try:
            Path(self.rules_db_path).parent.mkdir(parents=True, exist_ok=True)

            with sqlite3.connect(self.rules_db_path) as conn:
                cursor = conn.cursor()

                # 审计规则表
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS audit_rules (
                        rule_id TEXT PRIMARY KEY,
                        rule_name TEXT NOT NULL,
                        rule_type TEXT NOT NULL,
                        condition_text TEXT NOT NULL,
                        action_text TEXT NOT NULL,
                        severity TEXT NOT NULL,
                        confidence REAL DEFAULT 1.0,
                        created_at TEXT NOT NULL,
                        updated_at TEXT NOT NULL,
                        created_by TEXT NOT NULL,
                        description TEXT,
                        metadata TEXT,
                        status TEXT DEFAULT 'active',
                        execution_count INTEGER DEFAULT 0,
                        success_rate REAL DEFAULT 0.0
                    )
                """
                )

                # 规则违反表
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS rule_violations (
                        violation_id TEXT PRIMARY KEY,
                        rule_id TEXT NOT NULL,
                        data_record TEXT NOT NULL,
                        violation_details TEXT NOT NULL,
                        severity TEXT NOT NULL,
                        detected_at TEXT NOT NULL,
                        resolved BOOLEAN DEFAULT 0,
                        resolution_notes TEXT,
                        FOREIGN KEY (rule_id) REFERENCES audit_rules (rule_id)
                    )
                """
                )

                # 审计模式表
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS audit_patterns (
                        pattern_id TEXT PRIMARY KEY,
                        pattern_name TEXT NOT NULL,
                        pattern_type TEXT NOT NULL,
                        conditions TEXT NOT NULL,
                        support REAL NOT NULL,
                        confidence REAL NOT NULL,
                        discovered_at TEXT NOT NULL,
                        instances TEXT
                    )
                """
                )

                # 规则执行历史表
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS rule_execution_history (
                        execution_id TEXT PRIMARY KEY,
                        rule_id TEXT NOT NULL,
                        executed_at TEXT NOT NULL,
                        data_count INTEGER,
                        violations_found INTEGER,
                        execution_time REAL,
                        success BOOLEAN,
                        error_message TEXT,
                        FOREIGN KEY (rule_id) REFERENCES audit_rules (rule_id)
                    )
                """
                )

                # 专家反馈表
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS expert_feedback (
                        feedback_id TEXT PRIMARY KEY,
                        rule_id TEXT,
                        violation_id TEXT,
                        feedback_type TEXT NOT NULL,
                        feedback_value TEXT NOT NULL,
                        expert_name TEXT,
                        feedback_time TEXT NOT NULL,
                        notes TEXT
                    )
                """
                )

                # 索引
                cursor.execute(
                    "CREATE INDEX IF NOT EXISTS idx_rules_type ON audit_rules (rule_type)"
                )
                cursor.execute(
                    "CREATE INDEX IF NOT EXISTS idx_rules_status ON audit_rules (status)"
                )
                cursor.execute(
                    "CREATE INDEX IF NOT EXISTS idx_violations_rule ON rule_violations (rule_id)"
                )
                cursor.execute(
                    "CREATE INDEX IF NOT EXISTS idx_violations_time ON rule_violations (detected_at)"
                )
                cursor.execute(
                    "CREATE INDEX IF NOT EXISTS idx_patterns_type ON audit_patterns (pattern_type)"
                )
                cursor.execute(
                    "CREATE INDEX IF NOT EXISTS idx_execution_rule ON rule_execution_history (rule_id)"
                )
                cursor.execute(
                    "CREATE INDEX IF NOT EXISTS idx_feedback_rule ON expert_feedback (rule_id)"
                )

                conn.commit()

            self.logger.info("审计规则数据库初始化完成")

        except Exception as e:
            self.logger.error(f"审计规则数据库初始化失败: {e}")
            raise

    async def _load_existing_rules(self):
        """加载现有审计规则"""
        try:
            with sqlite3.connect(self.rules_db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    SELECT rule_id, rule_name, rule_type, condition_text, action_text,
                           severity, confidence, status, execution_count, success_rate,
                           metadata
                    FROM audit_rules
                    WHERE status = 'active'
                """
                )

                rules_loaded = 0
                for row in cursor.fetchall():
                    rule_id = row[0]
                    try:
                        metadata = json.loads(row[10]) if row[10] else {}
                    except:
                        metadata = {}

                    rule = AuditRule(
                        rule_id=rule_id,
                        rule_name=row[1],
                        rule_type=RuleType(row[2]),
                        condition=row[3],
                        action=row[4],
                        severity=RuleSeverity(row[5]),
                        confidence=row[6],
                        created_at=datetime.now(),  # 简化
                        updated_at=datetime.now(),  # 简化
                        created_by="system",
                        description="",
                        metadata=metadata,
                        status=RuleStatus(row[7]),
                        execution_count=row[8],
                        success_rate=row[9],
                    )

                    with self._lock:
                        self.active_rules[rule_id] = rule

                    rules_loaded += 1

            self.logger.info(f"加载现有审计规则: {rules_loaded} 条")

        except Exception as e:
            self.logger.error(f"加载现有规则失败: {e}")

    async def _load_ml_models(self):
        """加载ML模型"""
        try:
            if not SKLEARN_AVAILABLE:
                self.logger.warning("sklearn不可用，跳过ML模型加载")
                return

            # 加载异常检测模型
            anomaly_model_path = Path(self.models_path) / "anomaly_detector.pkl"
            if anomaly_model_path.exists():
                with open(anomaly_model_path, "rb") as f:
                    self.anomaly_detector = pickle.load(f)
                self.logger.info("异常检测模型加载成功")
            else:
                # 创建新的异常检测模型
                self.anomaly_detector = IsolationForest(
                    contamination=self.anomaly_threshold, random_state=42
                )

            # 加载规则分类器
            classifier_model_path = Path(self.models_path) / "rule_classifier.pkl"
            if classifier_model_path.exists():
                with open(classifier_model_path, "rb") as f:
                    self.rule_classifier = pickle.load(f)
                self.logger.info("规则分类器加载成功")
            else:
                # 创建新的规则分类器
                if XGBOOST_AVAILABLE:
                    self.rule_classifier = xgb.XGBClassifier(
                        n_estimators=100,
                        max_depth=6,
                        learning_rate=self.learning_rate,
                        random_state=42,
                    )
                else:
                    self.rule_classifier = RandomForestClassifier(
                        n_estimators=100, max_depth=10, random_state=42
                    )

        except Exception as e:
            self.logger.error(f"加载ML模型失败: {e}")

    async def execute_audit_rules(
        self, data: Dict[str, Any], rule_filter: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """执行审计规则"""
        try:
            filter_config = rule_filter or {}
            execution_id = f"exec_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{hashlib.md5(str(datetime.now()).encode()).hexdigest()[:8]}"

            result = {
                "execution_id": execution_id,
                "started_at": datetime.now().isoformat(),
                "total_rules": 0,
                "executed_rules": 0,
                "violations_found": 0,
                "violations": [],
                "rule_results": {},
                "performance_metrics": {},
                "status": "success",
            }

            # 获取要执行的规则
            rules_to_execute = await self._get_rules_to_execute(filter_config)
            result["total_rules"] = len(rules_to_execute)

            execution_start_time = datetime.now()

            # 并行执行规则
            tasks = []
            for rule_id, rule in rules_to_execute.items():
                task = asyncio.create_task(
                    self._execute_single_rule(rule, data, execution_id)
                )
                tasks.append((rule_id, task))

            # 收集结果
            for rule_id, task in tasks:
                try:
                    rule_result = await task
                    result["rule_results"][rule_id] = rule_result
                    result["executed_rules"] += 1

                    if rule_result["violations"]:
                        result["violations_found"] += len(rule_result["violations"])
                        result["violations"].extend(rule_result["violations"])

                except Exception as e:
                    self.logger.error(f"规则 {rule_id} 执行失败: {e}")
                    result["rule_results"][rule_id] = {
                        "status": "error",
                        "error": str(e),
                    }

            # AI增强分析
            if self.config.get("enable_ai_analysis", True):
                ai_analysis = await self._perform_ai_analysis(
                    data, result["violations"]
                )
                result["ai_analysis"] = ai_analysis

            # 计算性能指标
            execution_time = (datetime.now() - execution_start_time).total_seconds()
            result["performance_metrics"] = {
                "total_execution_time": execution_time,
                "avg_rule_time": execution_time / max(result["executed_rules"], 1),
                "violations_per_rule": result["violations_found"]
                / max(result["executed_rules"], 1),
            }

            result["completed_at"] = datetime.now().isoformat()

            # 学习和优化
            if self.config.get("enable_learning", True):
                await self._learn_from_execution(result)

            self.logger.info(
                f"审计规则执行完成: {result['executed_rules']}/{result['total_rules']} 规则, {result['violations_found']} 违反"
            )

            return result

        except Exception as e:
            self.logger.error(f"审计规则执行失败: {e}")
            return {
                "status": "error",
                "error": str(e),
                "started_at": datetime.now().isoformat(),
            }

    async def _get_rules_to_execute(
        self, filter_config: Dict[str, Any]
    ) -> Dict[str, AuditRule]:
        """获取要执行的规则"""
        rules_to_execute = {}

        try:
            with self._lock:
                for rule_id, rule in self.active_rules.items():
                    # 应用过滤条件
                    if (
                        filter_config.get("rule_types")
                        and rule.rule_type.value not in filter_config["rule_types"]
                    ):
                        continue

                    if (
                        filter_config.get("min_confidence")
                        and rule.confidence < filter_config["min_confidence"]
                    ):
                        continue

                    if (
                        filter_config.get("severity_levels")
                        and rule.severity.value not in filter_config["severity_levels"]
                    ):
                        continue

                    rules_to_execute[rule_id] = rule

        except Exception as e:
            self.logger.error(f"获取执行规则失败: {e}")

        return rules_to_execute

    async def _execute_single_rule(
        self, rule: AuditRule, data: Dict[str, Any], execution_id: str
    ) -> Dict[str, Any]:
        """执行单个审计规则"""
        try:
            rule_start_time = datetime.now()

            result = {
                "rule_id": rule.rule_id,
                "rule_name": rule.rule_name,
                "status": "success",
                "violations": [],
                "execution_time": 0,
                "records_checked": 0,
            }

            # 根据规则类型执行
            if rule.rule_type == RuleType.VALIDATION:
                violations = await self._execute_validation_rule(rule, data)
            elif rule.rule_type == RuleType.BUSINESS:
                violations = await self._execute_business_rule(rule, data)
            elif rule.rule_type == RuleType.ANOMALY:
                violations = await self._execute_anomaly_rule(rule, data)
            elif rule.rule_type == RuleType.COMPLIANCE:
                violations = await self._execute_compliance_rule(rule, data)
            elif rule.rule_type == RuleType.RISK:
                violations = await self._execute_risk_rule(rule, data)
            else:
                violations = []

            result["violations"] = violations
            result["records_checked"] = self._count_records(data)
            result["execution_time"] = (
                datetime.now() - rule_start_time
            ).total_seconds()

            # 记录执行历史
            await self._record_rule_execution(rule.rule_id, execution_id, result)

            # 更新规则统计
            await self._update_rule_statistics(rule.rule_id, len(violations) == 0)

            return result

        except Exception as e:
            self.logger.error(f"执行规则 {rule.rule_id} 失败: {e}")
            return {
                "rule_id": rule.rule_id,
                "status": "error",
                "error": str(e),
                "violations": [],
                "execution_time": 0,
                "records_checked": 0,
            }

    async def _execute_validation_rule(
        self, rule: AuditRule, data: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """执行数据验证规则"""
        violations = []

        try:
            # 解析规则条件
            condition = rule.condition

            # 遍历数据记录
            for table_name, records in data.items():
                if not isinstance(records, list):
                    continue

                for record_idx, record in enumerate(records):
                    if self._evaluate_condition(condition, record):
                        violation = {
                            "violation_id": f"viol_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{record_idx}",
                            "rule_id": rule.rule_id,
                            "table_name": table_name,
                            "record_index": record_idx,
                            "record_data": record,
                            "violation_type": "validation",
                            "severity": rule.severity.value,
                            "description": f"验证规则违反: {rule.rule_name}",
                            "detected_at": datetime.now().isoformat(),
                        }
                        violations.append(violation)

        except Exception as e:
            self.logger.error(f"执行验证规则失败: {e}")

        return violations

    async def _execute_business_rule(
        self, rule: AuditRule, data: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """执行业务逻辑规则"""
        violations = []

        try:
            # 业务规则通常涉及多表关联和复杂逻辑
            # 这里实现基础的业务规则检查

            condition = rule.condition

            # 如果规则涉及聚合或关联查询
            if "SUM" in condition or "COUNT" in condition or "AVG" in condition:
                violations.extend(await self._execute_aggregate_rule(rule, data))
            else:
                # 单记录业务规则
                for table_name, records in data.items():
                    if not isinstance(records, list):
                        continue

                    for record_idx, record in enumerate(records):
                        if self._evaluate_business_condition(condition, record, data):
                            violation = {
                                "violation_id": f"viol_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{record_idx}",
                                "rule_id": rule.rule_id,
                                "table_name": table_name,
                                "record_index": record_idx,
                                "record_data": record,
                                "violation_type": "business",
                                "severity": rule.severity.value,
                                "description": f"业务规则违反: {rule.rule_name}",
                                "detected_at": datetime.now().isoformat(),
                            }
                            violations.append(violation)

        except Exception as e:
            self.logger.error(f"执行业务规则失败: {e}")

        return violations

    async def _execute_anomaly_rule(
        self, rule: AuditRule, data: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """执行异常检测规则"""
        violations = []

        try:
            if not self.anomaly_detector or not SKLEARN_AVAILABLE:
                return violations

            # 准备异常检测数据
            for table_name, records in data.items():
                if not isinstance(records, list) or len(records) < 10:
                    continue

                # 提取数值特征
                numeric_features = self._extract_numeric_features(records)
                if len(numeric_features) == 0:
                    continue

                # 异常检测
                try:
                    anomaly_scores = self.anomaly_detector.decision_function(
                        numeric_features
                    )
                    anomaly_predictions = self.anomaly_detector.predict(
                        numeric_features
                    )

                    for idx, (score, prediction) in enumerate(
                        zip(anomaly_scores, anomaly_predictions)
                    ):
                        if prediction == -1:  # 异常点
                            violation = {
                                "violation_id": f"anom_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{idx}",
                                "rule_id": rule.rule_id,
                                "table_name": table_name,
                                "record_index": idx,
                                "record_data": records[idx],
                                "violation_type": "anomaly",
                                "severity": rule.severity.value,
                                "anomaly_score": float(score),
                                "description": f"异常检测: {rule.rule_name}",
                                "detected_at": datetime.now().isoformat(),
                            }
                            violations.append(violation)

                except Exception as e:
                    self.logger.error(f"异常检测失败: {e}")

        except Exception as e:
            self.logger.error(f"执行异常规则失败: {e}")

        return violations

    def _extract_numeric_features(
        self, records: List[Dict[str, Any]]
    ) -> List[List[float]]:
        """提取数值特征"""
        try:
            if not records:
                return []

            # 找出所有数值字段
            numeric_fields = []
            for record in records[:5]:  # 检查前5条记录
                for key, value in record.items():
                    if isinstance(value, (int, float)) and key not in numeric_fields:
                        numeric_fields.append(key)

            if not numeric_fields:
                return []

            # 提取特征矩阵
            features = []
            for record in records:
                feature_vector = []
                for field in numeric_fields:
                    value = record.get(field, 0)
                    if isinstance(value, (int, float)):
                        feature_vector.append(float(value))
                    else:
                        feature_vector.append(0.0)

                features.append(feature_vector)

            return features

        except Exception as e:
            self.logger.error(f"提取数值特征失败: {e}")
            return []

    async def _execute_compliance_rule(
        self, rule: AuditRule, data: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """执行合规性规则"""
        violations = []

        try:
            # 合规性规则通常涉及法规要求
            condition = rule.condition

            for table_name, records in data.items():
                if not isinstance(records, list):
                    continue

                for record_idx, record in enumerate(records):
                    if self._evaluate_compliance_condition(condition, record):
                        violation = {
                            "violation_id": f"comp_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{record_idx}",
                            "rule_id": rule.rule_id,
                            "table_name": table_name,
                            "record_index": record_idx,
                            "record_data": record,
                            "violation_type": "compliance",
                            "severity": rule.severity.value,
                            "description": f"合规性违反: {rule.rule_name}",
                            "detected_at": datetime.now().isoformat(),
                        }
                        violations.append(violation)

        except Exception as e:
            self.logger.error(f"执行合规规则失败: {e}")

        return violations

    async def _execute_risk_rule(
        self, rule: AuditRule, data: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """执行风险评估规则"""
        violations = []

        try:
            # 风险规则可能涉及复杂的风险评分计算
            condition = rule.condition

            for table_name, records in data.items():
                if not isinstance(records, list):
                    continue

                for record_idx, record in enumerate(records):
                    risk_score = self._calculate_risk_score(record, rule)

                    if risk_score > self.config.get("risk_threshold", 0.7):
                        violation = {
                            "violation_id": f"risk_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{record_idx}",
                            "rule_id": rule.rule_id,
                            "table_name": table_name,
                            "record_index": record_idx,
                            "record_data": record,
                            "violation_type": "risk",
                            "severity": rule.severity.value,
                            "risk_score": risk_score,
                            "description": f"风险评估: {rule.rule_name}",
                            "detected_at": datetime.now().isoformat(),
                        }
                        violations.append(violation)

        except Exception as e:
            self.logger.error(f"执行风险规则失败: {e}")

        return violations

    def _evaluate_condition(self, condition: str, record: Dict[str, Any]) -> bool:
        """评估规则条件"""
        try:
            # 简单的条件评估
            # 在实际实现中，应该使用更安全的表达式求值器

            # 替换记录字段
            eval_condition = condition
            for key, value in record.items():
                if isinstance(value, str):
                    eval_condition = eval_condition.replace(f"${key}", f"'{value}'")
                else:
                    eval_condition = eval_condition.replace(f"${key}", str(value))

            # 基本安全检查
            if any(
                dangerous in eval_condition
                for dangerous in ["import", "exec", "eval", "__"]
            ):
                return False

            # 评估条件
            return bool(eval(eval_condition))

        except Exception as e:
            self.logger.error(f"条件评估失败: {e}")
            return False

    def _evaluate_business_condition(
        self, condition: str, record: Dict[str, Any], all_data: Dict[str, Any]
    ) -> bool:
        """评估业务条件（可能涉及多表）"""
        try:
            # 业务条件可能需要访问其他表的数据
            # 这里实现基础的业务条件评估
            return self._evaluate_condition(condition, record)

        except Exception as e:
            self.logger.error(f"业务条件评估失败: {e}")
            return False

    def _evaluate_compliance_condition(
        self, condition: str, record: Dict[str, Any]
    ) -> bool:
        """评估合规条件"""
        try:
            # 合规条件通常涉及特定的法规要求
            return self._evaluate_condition(condition, record)

        except Exception as e:
            self.logger.error(f"合规条件评估失败: {e}")
            return False

    def _calculate_risk_score(self, record: Dict[str, Any], rule: AuditRule) -> float:
        """计算风险评分"""
        try:
            # 简单的风险评分计算
            # 在实际实现中，应该使用更复杂的风险模型

            risk_factors = rule.metadata.get("risk_factors", {})
            total_score = 0.0
            total_weight = 0.0

            for factor, weight in risk_factors.items():
                if factor in record:
                    value = record[factor]
                    if isinstance(value, (int, float)):
                        # 数值型风险因子
                        normalized_value = min(
                            value / risk_factors.get(f"{factor}_max", 100), 1.0
                        )
                        total_score += normalized_value * weight
                        total_weight += weight

            return total_score / total_weight if total_weight > 0 else 0.0

        except Exception as e:
            self.logger.error(f"风险评分计算失败: {e}")
            return 0.0

    def _count_records(self, data: Dict[str, Any]) -> int:
        """统计记录数"""
        count = 0
        for table_data in data.values():
            if isinstance(table_data, list):
                count += len(table_data)
        return count

    async def _perform_ai_analysis(
        self, data: Dict[str, Any], violations: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """执行AI增强分析"""
        try:
            analysis = {
                "pattern_analysis": {},
                "risk_assessment": {},
                "recommendations": [],
                "insights": [],
            }

            # 模式分析
            if len(violations) > 5:
                patterns = await self._discover_violation_patterns(violations)
                analysis["pattern_analysis"] = patterns

            # 风险评估
            risk_assessment = await self._assess_overall_risk(data, violations)
            analysis["risk_assessment"] = risk_assessment

            # 生成建议
            recommendations = await self._generate_ai_recommendations(violations)
            analysis["recommendations"] = recommendations

            return analysis

        except Exception as e:
            self.logger.error(f"AI分析失败: {e}")
            return {}

    async def _discover_violation_patterns(
        self, violations: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """发现违反模式"""
        try:
            patterns = {
                "frequent_violations": {},
                "time_patterns": {},
                "severity_distribution": {},
                "table_patterns": {},
            }

            # 频繁违反模式
            rule_counts = Counter([v["rule_id"] for v in violations])
            patterns["frequent_violations"] = dict(rule_counts.most_common(10))

            # 时间模式
            # 这里可以添加时间序列分析

            # 严重性分布
            severity_counts = Counter([v["severity"] for v in violations])
            patterns["severity_distribution"] = dict(severity_counts)

            # 表格模式
            table_counts = Counter([v.get("table_name", "unknown") for v in violations])
            patterns["table_patterns"] = dict(table_counts)

            return patterns

        except Exception as e:
            self.logger.error(f"发现违反模式失败: {e}")
            return {}

    async def create_rule(self, rule_info: Dict[str, Any]) -> Dict[str, Any]:
        """创建新的审计规则"""
        try:
            rule_id = (
                rule_info.get("rule_id")
                or f"rule_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{hashlib.md5(str(datetime.now()).encode()).hexdigest()[:8]}"
            )

            rule = AuditRule(
                rule_id=rule_id,
                rule_name=rule_info["rule_name"],
                rule_type=RuleType(rule_info.get("rule_type", "validation")),
                condition=rule_info["condition"],
                action=rule_info.get("action", "flag"),
                severity=RuleSeverity(rule_info.get("severity", "medium")),
                confidence=rule_info.get("confidence", 1.0),
                created_at=datetime.now(),
                updated_at=datetime.now(),
                created_by=rule_info.get("created_by", "system"),
                description=rule_info.get("description", ""),
                metadata=rule_info.get("metadata", {}),
                status=RuleStatus(rule_info.get("status", "active")),
                execution_count=0,
                success_rate=0.0,
            )

            # 保存到数据库
            await self._save_rule_to_db(rule)

            # 更新缓存
            with self._lock:
                self.active_rules[rule_id] = rule

            # 向量化规则（如果支持）
            if self.rules_collection:
                await self._vectorize_rule(rule)

            result = {
                "status": "success",
                "rule_id": rule_id,
                "message": f"规则 '{rule.rule_name}' 创建成功",
            }

            self.logger.info(f"审计规则创建成功: {rule_id}")
            return result

        except Exception as e:
            self.logger.error(f"创建审计规则失败: {e}")
            return {"status": "error", "error": str(e)}

    async def _save_rule_to_db(self, rule: AuditRule):
        """保存规则到数据库"""
        try:
            with sqlite3.connect(self.rules_db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    INSERT OR REPLACE INTO audit_rules
                    (rule_id, rule_name, rule_type, condition_text, action_text,
                     severity, confidence, created_at, updated_at, created_by,
                     description, metadata, status, execution_count, success_rate)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                    (
                        rule.rule_id,
                        rule.rule_name,
                        rule.rule_type.value,
                        rule.condition,
                        rule.action,
                        rule.severity.value,
                        rule.confidence,
                        rule.created_at.isoformat(),
                        rule.updated_at.isoformat(),
                        rule.created_by,
                        rule.description,
                        json.dumps(rule.metadata),
                        rule.status.value,
                        rule.execution_count,
                        rule.success_rate,
                    ),
                )
                conn.commit()

        except Exception as e:
            self.logger.error(f"保存规则到数据库失败: {e}")
            raise

    async def __aenter__(self):
        """异步上下文管理器入口"""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """异步上下文管理器出口"""
        await self.cleanup()

    async def cleanup(self):
        """清理资源"""
        try:
            if hasattr(self, "executor"):
                self.executor.shutdown(wait=True)

            # 保存ML模型
            await self._save_ml_models()

            self.logger.info("AI审计规则引擎资源清理完成")

        except Exception as e:
            self.logger.error(f"资源清理失败: {e}")

    async def _save_ml_models(self):
        """保存ML模型"""
        try:
            if self.anomaly_detector:
                anomaly_model_path = Path(self.models_path) / "anomaly_detector.pkl"
                with open(anomaly_model_path, "wb") as f:
                    pickle.dump(self.anomaly_detector, f)

            if self.rule_classifier:
                classifier_model_path = Path(self.models_path) / "rule_classifier.pkl"
                with open(classifier_model_path, "wb") as f:
                    pickle.dump(self.rule_classifier, f)

            self.logger.info("ML模型保存完成")

        except Exception as e:
            self.logger.error(f"保存ML模型失败: {e}")


async def main():
    """测试主函数"""
    config = {
        "rules_db_path": "data/test_audit_rules.db",
        "models_path": "data/test_models/audit/",
        "enable_ai_analysis": True,
        "enable_learning": True,
        "anomaly_threshold": 0.1,
        "min_confidence": 0.7,
    }

    async with AIAuditRulesEngine(config) as engine:
        # 创建测试规则
        test_rule = {
            "rule_name": "金额异常检查",
            "rule_type": "validation",
            "condition": "$amount > 1000000",
            "action": "flag",
            "severity": "high",
            "description": "检查超过100万的金额记录",
            "created_by": "test_user",
        }

        rule_result = await engine.create_rule(test_rule)
        print(f"规则创建结果: {json.dumps(rule_result, indent=2, ensure_ascii=False)}")

        # 测试数据
        test_data = {
            "financial_records": [
                {"id": 1, "amount": 500000, "account": "1001", "date": "2024-01-01"},
                {
                    "id": 2,
                    "amount": 1500000,
                    "account": "1002",
                    "date": "2024-01-02",
                },  # 会违反规则
                {"id": 3, "amount": 200000, "account": "1003", "date": "2024-01-03"},
            ]
        }

        # 执行审计规则
        execution_result = await engine.execute_audit_rules(test_data)
        print(f"规则执行结果: {json.dumps(execution_result, indent=2, ensure_ascii=False)}")


if __name__ == "__main__":
    asyncio.run(main())
