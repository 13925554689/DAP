"""
异常检测器 - Layer 3
ML驱动的异常检测（无监督+有监督）

核心功能：
1. 多算法异常检测（孤立森林、自编码器、XGBoost）
2. 审计特定的异常模式识别
3. 自适应阈值调整
4. 异常解释和可视化
5. 专家反馈学习
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
import statistics
from enum import Enum

from utils.async_utils import schedule_async_task

# 机器学习库
try:
    from sklearn.ensemble import IsolationForest
    from sklearn.preprocessing import StandardScaler, RobustScaler
    from sklearn.decomposition import PCA
    from sklearn.cluster import DBSCAN
    from sklearn.metrics import classification_report, precision_recall_fscore_support
    from sklearn.model_selection import train_test_split

    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False

try:
    import xgboost as xgb

    XGBOOST_AVAILABLE = True
except ImportError:
    XGBOOST_AVAILABLE = False

# 深度学习（可选）
try:
    import tensorflow as tf
    from tensorflow.keras.models import Model, Sequential
    from tensorflow.keras.layers import Dense, Input, Dropout
    from tensorflow.keras.optimizers import Adam

    TENSORFLOW_AVAILABLE = True
except ImportError:
    TENSORFLOW_AVAILABLE = False

# 时间序列分析
try:
    from statsmodels.tsa.seasonal import seasonal_decompose
    from statsmodels.stats.diagnostic import acorr_ljungbox

    STATSMODELS_AVAILABLE = True
except ImportError:
    STATSMODELS_AVAILABLE = False

# 可视化
try:
    import plotly.graph_objects as go
    import plotly.express as px
    from plotly.subplots import make_subplots

    PLOTLY_AVAILABLE = True
except ImportError:
    PLOTLY_AVAILABLE = False


class AnomalyType(Enum):
    """异常类型"""

    STATISTICAL = "statistical"  # 统计异常
    PATTERN = "pattern"  # 模式异常
    BUSINESS = "business"  # 业务异常
    TEMPORAL = "temporal"  # 时间异常
    CONTEXTUAL = "contextual"  # 上下文异常


class AnomalySeverity(Enum):
    """异常严重程度"""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class AnomalyResult:
    """异常检测结果"""

    anomaly_id: str
    record_id: str
    anomaly_type: AnomalyType
    severity: AnomalySeverity
    confidence: float
    anomaly_score: float
    detected_at: datetime
    detector_name: str
    features_involved: List[str]
    explanation: str
    context: Dict[str, Any]


@dataclass
class DetectorConfig:
    """检测器配置"""

    detector_name: str
    detector_type: str
    parameters: Dict[str, Any]
    enabled: bool
    threshold: float
    weight: float


class AnomalyDetector:
    """ML驱动的异常检测器"""

    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        self.logger = logging.getLogger(__name__)

        # 数据库配置
        self.anomaly_db_path = self.config.get(
            "anomaly_db_path", "data/anomaly_detection.db"
        )
        self.models_path = self.config.get("models_path", "data/models/anomaly/")

        # 检测配置
        self.contamination = self.config.get("contamination", 0.1)
        self.min_confidence = self.config.get("min_confidence", 0.7)
        self.ensemble_weights = self.config.get(
            "ensemble_weights",
            {"isolation_forest": 0.3, "autoencoder": 0.3, "xgboost": 0.4},
        )

        # 检测器集合
        self.detectors = {}
        self.scalers = {}
        self.feature_selectors = {}

        # 缓存
        self.anomaly_cache = {}
        self.feature_cache = {}

        # 并发控制
        self.max_workers = self.config.get("max_workers", 4)
        self.executor = ThreadPoolExecutor(max_workers=self.max_workers)
        self._lock = threading.RLock()

        # 审计特定阈值
        self.audit_thresholds = {
            "amount_variance": self.config.get("amount_variance_threshold", 3.0),
            "frequency_deviation": self.config.get(
                "frequency_deviation_threshold", 2.5
            ),
            "temporal_gap": self.config.get("temporal_gap_threshold", 30),  # 天
            "ratio_anomaly": self.config.get("ratio_anomaly_threshold", 2.0),
        }

        # 确保模型目录存在
        Path(self.models_path).mkdir(parents=True, exist_ok=True)

        # 初始化数据库
        self._init_database()

        # 初始化检测器
        schedule_async_task(
            self._initialize_detectors,
            logger=self.logger,
            task_name="initialize_anomaly_detectors",
        )

    def _init_database(self):
        """初始化异常检测数据库"""
        try:
            Path(self.anomaly_db_path).parent.mkdir(parents=True, exist_ok=True)

            with sqlite3.connect(self.anomaly_db_path) as conn:
                cursor = conn.cursor()

                # 异常检测结果表
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS anomaly_results (
                        anomaly_id TEXT PRIMARY KEY,
                        record_id TEXT NOT NULL,
                        anomaly_type TEXT NOT NULL,
                        severity TEXT NOT NULL,
                        confidence REAL NOT NULL,
                        anomaly_score REAL NOT NULL,
                        detected_at TEXT NOT NULL,
                        detector_name TEXT NOT NULL,
                        features_involved TEXT,
                        explanation TEXT,
                        context TEXT,
                        validated BOOLEAN DEFAULT 0,
                        validation_feedback TEXT,
                        false_positive BOOLEAN DEFAULT 0
                    )
                """
                )

                # 检测器配置表
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS detector_configs (
                        config_id TEXT PRIMARY KEY,
                        detector_name TEXT NOT NULL,
                        detector_type TEXT NOT NULL,
                        parameters TEXT NOT NULL,
                        enabled BOOLEAN DEFAULT 1,
                        threshold REAL DEFAULT 0.5,
                        weight REAL DEFAULT 1.0,
                        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                        updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                    )
                """
                )

                # 特征重要性表
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS feature_importance (
                        feature_id TEXT PRIMARY KEY,
                        feature_name TEXT NOT NULL,
                        detector_name TEXT NOT NULL,
                        importance_score REAL NOT NULL,
                        data_type TEXT,
                        business_meaning TEXT,
                        computed_at TEXT NOT NULL
                    )
                """
                )

                # 异常反馈表
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS anomaly_feedback (
                        feedback_id TEXT PRIMARY KEY,
                        anomaly_id TEXT NOT NULL,
                        feedback_type TEXT NOT NULL,
                        feedback_value TEXT NOT NULL,
                        expert_name TEXT,
                        feedback_time TEXT NOT NULL,
                        comments TEXT,
                        FOREIGN KEY (anomaly_id) REFERENCES anomaly_results (anomaly_id)
                    )
                """
                )

                # 检测性能表
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS detection_performance (
                        performance_id TEXT PRIMARY KEY,
                        detector_name TEXT NOT NULL,
                        dataset_size INTEGER,
                        detection_time REAL,
                        anomalies_found INTEGER,
                        precision_score REAL,
                        recall_score REAL,
                        f1_score REAL,
                        evaluated_at TEXT NOT NULL
                    )
                """
                )

                # 索引
                cursor.execute(
                    "CREATE INDEX IF NOT EXISTS idx_anomalies_type ON anomaly_results (anomaly_type)"
                )
                cursor.execute(
                    "CREATE INDEX IF NOT EXISTS idx_anomalies_detector ON anomaly_results (detector_name)"
                )
                cursor.execute(
                    "CREATE INDEX IF NOT EXISTS idx_anomalies_time ON anomaly_results (detected_at)"
                )
                cursor.execute(
                    "CREATE INDEX IF NOT EXISTS idx_feedback_anomaly ON anomaly_feedback (anomaly_id)"
                )
                cursor.execute(
                    "CREATE INDEX IF NOT EXISTS idx_performance_detector ON detection_performance (detector_name)"
                )

                conn.commit()

            self.logger.info("异常检测数据库初始化完成")

        except Exception as e:
            self.logger.error(f"异常检测数据库初始化失败: {e}")
            raise

    async def _initialize_detectors(self):
        """初始化检测器"""
        try:
            # 孤立森林检测器
            if SKLEARN_AVAILABLE:
                self.detectors["isolation_forest"] = IsolationForest(
                    contamination=self.contamination, random_state=42, n_jobs=-1
                )

                # DBSCAN聚类异常检测
                self.detectors["dbscan"] = DBSCAN(
                    eps=self.config.get("dbscan_eps", 0.5),
                    min_samples=self.config.get("dbscan_min_samples", 5),
                )

                # 数据预处理器
                self.scalers["standard"] = StandardScaler()
                self.scalers["robust"] = RobustScaler()

            # XGBoost异常检测器
            if XGBOOST_AVAILABLE:
                self.detectors["xgboost"] = xgb.XGBClassifier(
                    n_estimators=100, max_depth=6, learning_rate=0.1, random_state=42
                )

            # 自编码器（如果有TensorFlow）
            if TENSORFLOW_AVAILABLE:
                await self._create_autoencoder()

            # 加载已训练的模型
            await self._load_trained_models()

            self.logger.info(f"异常检测器初始化完成: {len(self.detectors)} 个检测器")

        except Exception as e:
            self.logger.error(f"初始化检测器失败: {e}")

    async def _create_autoencoder(self):
        """创建自编码器"""
        try:
            # 自编码器架构
            def create_autoencoder(input_dim: int):
                input_layer = Input(shape=(input_dim,))

                # 编码器
                encoded = Dense(64, activation="relu")(input_layer)
                encoded = Dropout(0.2)(encoded)
                encoded = Dense(32, activation="relu")(encoded)
                encoded = Dropout(0.2)(encoded)
                encoded = Dense(16, activation="relu")(encoded)

                # 解码器
                decoded = Dense(32, activation="relu")(encoded)
                decoded = Dropout(0.2)(decoded)
                decoded = Dense(64, activation="relu")(decoded)
                decoded = Dropout(0.2)(decoded)
                decoded = Dense(input_dim, activation="linear")(decoded)

                autoencoder = Model(input_layer, decoded)
                autoencoder.compile(optimizer=Adam(learning_rate=0.001), loss="mse")

                return autoencoder

            # 存储自编码器创建函数
            self.detectors["autoencoder_factory"] = create_autoencoder

        except Exception as e:
            self.logger.error(f"创建自编码器失败: {e}")

    async def _load_trained_models(self):
        """加载已训练的模型"""
        try:
            models_to_load = ["isolation_forest", "xgboost", "autoencoder"]

            for model_name in models_to_load:
                model_path = Path(self.models_path) / f"{model_name}.pkl"
                if model_path.exists():
                    try:
                        with open(model_path, "rb") as f:
                            self.detectors[model_name] = pickle.load(f)
                        self.logger.info(f"模型 {model_name} 加载成功")
                    except Exception as e:
                        self.logger.warning(f"加载模型 {model_name} 失败: {e}")

            # 加载标准化器
            scaler_path = Path(self.models_path) / "scalers.pkl"
            if scaler_path.exists():
                try:
                    with open(scaler_path, "rb") as f:
                        self.scalers = pickle.load(f)
                    self.logger.info("数据标准化器加载成功")
                except Exception as e:
                    self.logger.warning(f"加载标准化器失败: {e}")

        except Exception as e:
            self.logger.error(f"加载训练模型失败: {e}")

    async def detect_anomalies(
        self, data: Dict[str, Any], detection_config: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """检测异常"""
        try:
            config = detection_config or {}
            detection_id = f"detect_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{hashlib.md5(str(datetime.now()).encode()).hexdigest()[:8]}"

            result = {
                "detection_id": detection_id,
                "started_at": datetime.now().isoformat(),
                "total_records": 0,
                "anomalies_found": 0,
                "anomalies": [],
                "detector_results": {},
                "performance_metrics": {},
                "feature_importance": {},
                "status": "success",
            }

            # 数据预处理
            processed_data = await self._preprocess_data(data)
            result["total_records"] = (
                len(processed_data)
                if isinstance(processed_data, list)
                else processed_data.shape[0]
            )

            # 特征工程
            features_df = await self._extract_features(processed_data)
            if features_df.empty:
                return {
                    "status": "error",
                    "error": "无法提取有效特征",
                    "started_at": datetime.now().isoformat(),
                }

            # 选择要使用的检测器
            detectors_to_use = config.get("detectors", list(self.detectors.keys()))
            enabled_detectors = [d for d in detectors_to_use if d in self.detectors]

            if not enabled_detectors:
                return {
                    "status": "error",
                    "error": "没有可用的检测器",
                    "started_at": datetime.now().isoformat(),
                }

            detection_start_time = datetime.now()

            # 并行执行检测器
            detection_tasks = []
            for detector_name in enabled_detectors:
                task = asyncio.create_task(
                    self._run_single_detector(detector_name, features_df, detection_id)
                )
                detection_tasks.append((detector_name, task))

            # 收集检测结果
            detector_anomalies = {}
            for detector_name, task in detection_tasks:
                try:
                    detector_result = await task
                    result["detector_results"][detector_name] = detector_result
                    detector_anomalies[detector_name] = detector_result.get(
                        "anomalies", []
                    )

                except Exception as e:
                    self.logger.error(f"检测器 {detector_name} 执行失败: {e}")
                    result["detector_results"][detector_name] = {
                        "status": "error",
                        "error": str(e),
                    }

            # 集成多检测器结果
            if config.get("use_ensemble", True):
                integrated_anomalies = await self._integrate_detector_results(
                    detector_anomalies, features_df
                )
            else:
                # 简单合并
                integrated_anomalies = []
                for anomalies in detector_anomalies.values():
                    integrated_anomalies.extend(anomalies)

            # 后处理和排序
            final_anomalies = await self._postprocess_anomalies(
                integrated_anomalies, features_df
            )

            result["anomalies"] = final_anomalies
            result["anomalies_found"] = len(final_anomalies)

            # 计算性能指标
            detection_time = (datetime.now() - detection_start_time).total_seconds()
            result["performance_metrics"] = {
                "detection_time": detection_time,
                "records_per_second": result["total_records"]
                / max(detection_time, 0.001),
                "anomaly_rate": result["anomalies_found"]
                / max(result["total_records"], 1),
            }

            # 特征重要性分析
            if config.get("analyze_features", True):
                result["feature_importance"] = await self._analyze_feature_importance(
                    features_df, final_anomalies
                )

            result["completed_at"] = datetime.now().isoformat()

            # 保存结果
            if config.get("save_results", True):
                await self._save_detection_results(result)

            self.logger.info(
                f"异常检测完成: {result['anomalies_found']}/{result['total_records']} 异常"
            )

            return result

        except Exception as e:
            self.logger.error(f"异常检测失败: {e}")
            return {
                "status": "error",
                "error": str(e),
                "started_at": datetime.now().isoformat(),
            }

    async def _preprocess_data(self, data: Dict[str, Any]) -> pd.DataFrame:
        """数据预处理"""
        try:
            # 将数据转换为DataFrame
            if isinstance(data, dict):
                # 假设数据是以表名为键的字典
                all_records = []
                for table_name, records in data.items():
                    if isinstance(records, list):
                        for record in records:
                            record["_table"] = table_name
                            all_records.append(record)

                df = pd.DataFrame(all_records)
            elif isinstance(data, list):
                df = pd.DataFrame(data)
            else:
                df = pd.DataFrame([data])

            if df.empty:
                return df

            # 数据清洗
            # 处理缺失值
            numeric_columns = df.select_dtypes(include=[np.number]).columns
            df[numeric_columns] = df[numeric_columns].fillna(
                df[numeric_columns].median()
            )

            categorical_columns = df.select_dtypes(include=["object"]).columns
            df[categorical_columns] = df[categorical_columns].fillna("unknown")

            # 处理异常值（使用IQR方法）
            for col in numeric_columns:
                Q1 = df[col].quantile(0.25)
                Q3 = df[col].quantile(0.75)
                IQR = Q3 - Q1
                lower_bound = Q1 - 1.5 * IQR
                upper_bound = Q3 + 1.5 * IQR

                # 标记但不移除异常值
                df[f"{col}_outlier"] = (df[col] < lower_bound) | (df[col] > upper_bound)

            return df

        except Exception as e:
            self.logger.error(f"数据预处理失败: {e}")
            return pd.DataFrame()

    async def _extract_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """特征工程"""
        try:
            if df.empty:
                return df

            features_df = df.copy()

            # 基础数值特征
            numeric_columns = df.select_dtypes(include=[np.number]).columns
            numeric_features = df[numeric_columns]

            # 审计特定特征
            audit_features = pd.DataFrame()

            # 金额相关特征
            amount_columns = [
                col
                for col in df.columns
                if any(
                    keyword in col.lower()
                    for keyword in ["amount", "money", "value", "金额", "余额"]
                )
            ]

            if amount_columns:
                for col in amount_columns:
                    if col in numeric_columns:
                        # 金额的对数变换
                        audit_features[f"{col}_log"] = np.log1p(np.abs(df[col]))

                        # 金额的Z分数
                        mean_val = df[col].mean()
                        std_val = df[col].std()
                        if std_val > 0:
                            audit_features[f"{col}_zscore"] = np.abs(
                                (df[col] - mean_val) / std_val
                            )

                        # 金额的分位数
                        audit_features[f"{col}_percentile"] = df[col].rank(pct=True)

            # 时间特征
            date_columns = [
                col
                for col in df.columns
                if any(
                    keyword in col.lower() for keyword in ["date", "time", "日期", "时间"]
                )
            ]

            for col in date_columns:
                try:
                    dates = pd.to_datetime(df[col], errors="coerce")
                    if not dates.isna().all():
                        audit_features[f"{col}_year"] = dates.dt.year
                        audit_features[f"{col}_month"] = dates.dt.month
                        audit_features[f"{col}_day"] = dates.dt.day
                        audit_features[f"{col}_weekday"] = dates.dt.weekday
                        audit_features[f"{col}_quarter"] = dates.dt.quarter

                        # 时间间隔特征
                        if len(dates) > 1:
                            time_diffs = dates.diff().dt.days
                            audit_features[f"{col}_time_diff"] = time_diffs.fillna(0)

                except Exception as e:
                    self.logger.warning(f"处理日期列 {col} 失败: {e}")

            # 分类特征编码
            categorical_columns = df.select_dtypes(include=["object"]).columns
            categorical_features = pd.DataFrame()

            for col in categorical_columns:
                if col.startswith("_"):  # 跳过内部列
                    continue

                # 频率编码
                value_counts = df[col].value_counts()
                categorical_features[f"{col}_frequency"] = df[col].map(value_counts)

                # 标签编码（简单）
                unique_values = df[col].unique()
                label_map = {val: idx for idx, val in enumerate(unique_values)}
                categorical_features[f"{col}_label"] = df[col].map(label_map)

            # 合并所有特征
            final_features = pd.concat(
                [numeric_features, audit_features, categorical_features], axis=1
            )

            # 移除无穷大和NaN值
            final_features = final_features.replace([np.inf, -np.inf], np.nan)
            final_features = final_features.fillna(0)

            return final_features

        except Exception as e:
            self.logger.error(f"特征工程失败: {e}")
            return pd.DataFrame()

    async def _run_single_detector(
        self, detector_name: str, features_df: pd.DataFrame, detection_id: str
    ) -> Dict[str, Any]:
        """运行单个检测器"""
        try:
            detector = self.detectors.get(detector_name)
            if not detector:
                return {"status": "error", "error": f"检测器 {detector_name} 不存在"}

            start_time = datetime.now()

            # 数据标准化
            if detector_name in ["isolation_forest", "autoencoder", "dbscan"]:
                scaler = self.scalers.get("robust", RobustScaler())
                try:
                    scaled_features = scaler.fit_transform(features_df)
                except:
                    scaled_features = features_df.values
            else:
                scaled_features = features_df.values

            anomalies = []

            if detector_name == "isolation_forest":
                anomalies = await self._run_isolation_forest(
                    detector, scaled_features, features_df
                )

            elif detector_name == "dbscan":
                anomalies = await self._run_dbscan(
                    detector, scaled_features, features_df
                )

            elif detector_name == "xgboost":
                anomalies = await self._run_xgboost(detector, features_df)

            elif detector_name == "autoencoder":
                anomalies = await self._run_autoencoder(
                    detector, scaled_features, features_df
                )

            elif detector_name.startswith("custom_"):
                anomalies = await self._run_custom_detector(detector_name, features_df)

            execution_time = (datetime.now() - start_time).total_seconds()

            result = {
                "status": "success",
                "detector_name": detector_name,
                "anomalies": anomalies,
                "execution_time": execution_time,
                "anomalies_count": len(anomalies),
            }

            # 保存性能指标
            await self._save_detector_performance(
                detector_name, len(features_df), execution_time, len(anomalies)
            )

            return result

        except Exception as e:
            self.logger.error(f"运行检测器 {detector_name} 失败: {e}")
            return {
                "status": "error",
                "detector_name": detector_name,
                "error": str(e),
                "anomalies": [],
            }

    async def _run_isolation_forest(
        self, detector, scaled_features, features_df
    ) -> List[Dict[str, Any]]:
        """运行孤立森林检测"""
        try:
            # 训练或预测
            if not hasattr(detector, "n_estimators_"):
                detector.fit(scaled_features)

            # 预测异常
            anomaly_predictions = detector.predict(scaled_features)
            anomaly_scores = detector.decision_function(scaled_features)

            anomalies = []
            for i, (prediction, score) in enumerate(
                zip(anomaly_predictions, anomaly_scores)
            ):
                if prediction == -1:  # 异常
                    anomaly = {
                        "anomaly_id": f"iso_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{i}",
                        "record_index": i,
                        "anomaly_type": AnomalyType.STATISTICAL.value,
                        "confidence": float(1 / (1 + np.exp(score))),  # sigmoid转换
                        "anomaly_score": float(score),
                        "detector_name": "isolation_forest",
                        "explanation": f"孤立森林检测到统计异常，异常分数: {score:.3f}",
                    }
                    anomalies.append(anomaly)

            return anomalies

        except Exception as e:
            self.logger.error(f"孤立森林检测失败: {e}")
            return []

    async def _run_dbscan(
        self, detector, scaled_features, features_df
    ) -> List[Dict[str, Any]]:
        """运行DBSCAN聚类异常检测"""
        try:
            cluster_labels = detector.fit_predict(scaled_features)

            anomalies = []
            for i, label in enumerate(cluster_labels):
                if label == -1:  # 噪声点（异常）
                    anomaly = {
                        "anomaly_id": f"dbscan_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{i}",
                        "record_index": i,
                        "anomaly_type": AnomalyType.PATTERN.value,
                        "confidence": 0.8,  # DBSCAN的固定置信度
                        "anomaly_score": 1.0,
                        "detector_name": "dbscan",
                        "explanation": "DBSCAN聚类检测到模式异常（噪声点）",
                    }
                    anomalies.append(anomaly)

            return anomalies

        except Exception as e:
            self.logger.error(f"DBSCAN检测失败: {e}")
            return []

    async def _run_xgboost(self, detector, features_df) -> List[Dict[str, Any]]:
        """运行XGBoost异常检测"""
        try:
            # XGBoost需要有标签的数据进行训练
            # 这里假设已经训练好，或者使用半监督方法

            if hasattr(detector, "predict_proba"):
                # 如果模型已训练，进行预测
                probabilities = detector.predict_proba(features_df)
                anomaly_probs = (
                    probabilities[:, 1]
                    if probabilities.shape[1] > 1
                    else probabilities[:, 0]
                )

                anomalies = []
                threshold = self.config.get("xgboost_threshold", 0.7)

                for i, prob in enumerate(anomaly_probs):
                    if prob > threshold:
                        anomaly = {
                            "anomaly_id": f"xgb_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{i}",
                            "record_index": i,
                            "anomaly_type": AnomalyType.BUSINESS.value,
                            "confidence": float(prob),
                            "anomaly_score": float(prob),
                            "detector_name": "xgboost",
                            "explanation": f"XGBoost检测到业务异常，置信度: {prob:.3f}",
                        }
                        anomalies.append(anomaly)

                return anomalies
            else:
                self.logger.warning("XGBoost模型未训练，跳过检测")
                return []

        except Exception as e:
            self.logger.error(f"XGBoost检测失败: {e}")
            return []

    async def _run_autoencoder(
        self, detector, scaled_features, features_df
    ) -> List[Dict[str, Any]]:
        """运行自编码器异常检测"""
        try:
            if not TENSORFLOW_AVAILABLE:
                return []

            # 如果是工厂函数，创建模型
            if callable(detector) and detector.__name__ == "create_autoencoder":
                input_dim = scaled_features.shape[1]
                autoencoder = detector(input_dim)

                # 训练自编码器
                autoencoder.fit(
                    scaled_features,
                    scaled_features,
                    epochs=50,
                    batch_size=32,
                    validation_split=0.2,
                    verbose=0,
                )

                # 保存训练好的模型
                self.detectors["autoencoder"] = autoencoder
            else:
                autoencoder = detector

            # 预测和计算重构误差
            reconstructed = autoencoder.predict(scaled_features, verbose=0)
            mse = np.mean(np.power(scaled_features - reconstructed, 2), axis=1)

            # 确定异常阈值
            threshold = np.percentile(mse, 100 * (1 - self.contamination))

            anomalies = []
            for i, error in enumerate(mse):
                if error > threshold:
                    # 计算置信度
                    confidence = min(error / threshold, 3.0) / 3.0  # 归一化到[0,1]

                    anomaly = {
                        "anomaly_id": f"ae_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{i}",
                        "record_index": i,
                        "anomaly_type": AnomalyType.PATTERN.value,
                        "confidence": float(confidence),
                        "anomaly_score": float(error),
                        "detector_name": "autoencoder",
                        "explanation": f"自编码器检测到重构异常，误差: {error:.3f}",
                    }
                    anomalies.append(anomaly)

            return anomalies

        except Exception as e:
            self.logger.error(f"自编码器检测失败: {e}")
            return []

    async def _run_custom_detector(
        self, detector_name: str, features_df: pd.DataFrame
    ) -> List[Dict[str, Any]]:
        """运行自定义检测器"""
        try:
            anomalies = []

            if detector_name == "custom_audit_rules":
                anomalies = await self._run_audit_rules_detector(features_df)
            elif detector_name == "custom_temporal":
                anomalies = await self._run_temporal_detector(features_df)
            elif detector_name == "custom_ratio":
                anomalies = await self._run_ratio_detector(features_df)

            return anomalies

        except Exception as e:
            self.logger.error(f"自定义检测器 {detector_name} 失败: {e}")
            return []

    async def _run_audit_rules_detector(
        self, features_df: pd.DataFrame
    ) -> List[Dict[str, Any]]:
        """运行审计规则检测器"""
        anomalies = []

        try:
            # 审计特定的异常规则
            for i, row in features_df.iterrows():
                violation_reasons = []

                # 金额异常检查
                amount_cols = [
                    col for col in features_df.columns if "amount" in col.lower()
                ]
                for col in amount_cols:
                    if col in row and pd.notna(row[col]):
                        # 检查零金额
                        if row[col] == 0:
                            violation_reasons.append(f"{col}为零")

                        # 检查负金额（在不应该为负的科目中）
                        if row[col] < 0 and "应收" in col:
                            violation_reasons.append(f"{col}为负值")

                        # 检查异常大的金额
                        if abs(row[col]) > 10000000:  # 1000万
                            violation_reasons.append(f"{col}金额异常大")

                # 如果有违反规则
                if violation_reasons:
                    anomaly = {
                        "anomaly_id": f"audit_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{i}",
                        "record_index": i,
                        "anomaly_type": AnomalyType.BUSINESS.value,
                        "confidence": 0.9,
                        "anomaly_score": len(violation_reasons),
                        "detector_name": "custom_audit_rules",
                        "explanation": f'审计规则违反: {"; ".join(violation_reasons)}',
                    }
                    anomalies.append(anomaly)

        except Exception as e:
            self.logger.error(f"审计规则检测失败: {e}")

        return anomalies

    async def _integrate_detector_results(
        self, detector_anomalies: Dict[str, List], features_df: pd.DataFrame
    ) -> List[Dict[str, Any]]:
        """集成多检测器结果"""
        try:
            # 按记录索引分组异常
            record_anomalies = defaultdict(list)

            for detector_name, anomalies in detector_anomalies.items():
                weight = self.ensemble_weights.get(detector_name, 1.0)

                for anomaly in anomalies:
                    record_idx = anomaly.get("record_index")
                    if record_idx is not None:
                        anomaly["weight"] = weight
                        record_anomalies[record_idx].append(anomaly)

            # 集成决策
            integrated_anomalies = []

            for record_idx, anomalies in record_anomalies.items():
                if not anomalies:
                    continue

                # 计算加权平均置信度
                total_weight = sum(a["weight"] for a in anomalies)
                weighted_confidence = (
                    sum(a["confidence"] * a["weight"] for a in anomalies) / total_weight
                )

                # 计算综合异常分数
                combined_score = (
                    sum(a["anomaly_score"] * a["weight"] for a in anomalies)
                    / total_weight
                )

                # 确定最终异常类型
                anomaly_types = [a["anomaly_type"] for a in anomalies]
                final_type = Counter(anomaly_types).most_common(1)[0][0]

                # 生成解释
                detector_names = [a["detector_name"] for a in anomalies]
                explanation_parts = [a["explanation"] for a in anomalies]
                combined_explanation = f"多检测器发现({','.join(detector_names)}): {'; '.join(explanation_parts)}"

                # 只有当置信度足够高时才认为是异常
                if weighted_confidence >= self.min_confidence:
                    integrated_anomaly = {
                        "anomaly_id": f"integrated_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{record_idx}",
                        "record_index": record_idx,
                        "anomaly_type": final_type,
                        "confidence": float(weighted_confidence),
                        "anomaly_score": float(combined_score),
                        "detector_name": "ensemble",
                        "explanation": combined_explanation,
                        "contributing_detectors": detector_names,
                        "detector_count": len(anomalies),
                    }
                    integrated_anomalies.append(integrated_anomaly)

            return integrated_anomalies

        except Exception as e:
            self.logger.error(f"集成检测器结果失败: {e}")
            return []

    async def _postprocess_anomalies(
        self, anomalies: List[Dict[str, Any]], features_df: pd.DataFrame
    ) -> List[Dict[str, Any]]:
        """后处理异常结果"""
        try:
            if not anomalies:
                return []

            # 去重（基于记录索引）
            unique_anomalies = {}
            for anomaly in anomalies:
                record_idx = anomaly.get("record_index")
                if (
                    record_idx not in unique_anomalies
                    or anomaly["confidence"]
                    > unique_anomalies[record_idx]["confidence"]
                ):
                    unique_anomalies[record_idx] = anomaly

            # 排序（按置信度降序）
            sorted_anomalies = sorted(
                unique_anomalies.values(), key=lambda x: x["confidence"], reverse=True
            )

            # 添加严重程度
            for anomaly in sorted_anomalies:
                confidence = anomaly["confidence"]
                score = anomaly["anomaly_score"]

                if confidence >= 0.9 or score >= 3.0:
                    severity = AnomalySeverity.CRITICAL
                elif confidence >= 0.8 or score >= 2.0:
                    severity = AnomalySeverity.HIGH
                elif confidence >= 0.7 or score >= 1.0:
                    severity = AnomalySeverity.MEDIUM
                else:
                    severity = AnomalySeverity.LOW

                anomaly["severity"] = severity.value

            # 添加上下文信息
            for anomaly in sorted_anomalies:
                record_idx = anomaly.get("record_index")
                if record_idx is not None and record_idx < len(features_df):
                    # 添加原始记录信息
                    anomaly["context"] = {
                        "record_data": features_df.iloc[record_idx].to_dict(),
                        "feature_count": len(features_df.columns),
                        "detected_at": datetime.now().isoformat(),
                    }

            return sorted_anomalies

        except Exception as e:
            self.logger.error(f"后处理异常失败: {e}")
            return anomalies

    async def _analyze_feature_importance(
        self, features_df: pd.DataFrame, anomalies: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """分析特征重要性"""
        try:
            if not anomalies or features_df.empty:
                return {}

            # 创建异常标签
            anomaly_indices = set(
                a.get("record_index")
                for a in anomalies
                if a.get("record_index") is not None
            )
            labels = [1 if i in anomaly_indices else 0 for i in range(len(features_df))]

            if sum(labels) == 0:
                return {}

            # 使用随机森林计算特征重要性
            if SKLEARN_AVAILABLE:
                from sklearn.ensemble import RandomForestClassifier

                rf = RandomForestClassifier(n_estimators=100, random_state=42)
                rf.fit(features_df, labels)

                feature_importance = dict(
                    zip(features_df.columns, rf.feature_importances_)
                )

                # 排序特征重要性
                sorted_features = sorted(
                    feature_importance.items(), key=lambda x: x[1], reverse=True
                )

                return {
                    "top_features": sorted_features[:20],
                    "importance_scores": feature_importance,
                    "analysis_method": "random_forest",
                }

            return {}

        except Exception as e:
            self.logger.error(f"特征重要性分析失败: {e}")
            return {}

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

            # 保存模型
            await self._save_trained_models()

            self.logger.info("异常检测器资源清理完成")

        except Exception as e:
            self.logger.error(f"资源清理失败: {e}")

    async def _save_trained_models(self):
        """保存训练模型"""
        try:
            # 保存sklearn模型
            models_to_save = ["isolation_forest", "xgboost"]

            for model_name in models_to_save:
                if model_name in self.detectors:
                    model_path = Path(self.models_path) / f"{model_name}.pkl"
                    with open(model_path, "wb") as f:
                        pickle.dump(self.detectors[model_name], f)

            # 保存标准化器
            if self.scalers:
                scaler_path = Path(self.models_path) / "scalers.pkl"
                with open(scaler_path, "wb") as f:
                    pickle.dump(self.scalers, f)

            # 保存TensorFlow模型
            if "autoencoder" in self.detectors and TENSORFLOW_AVAILABLE:
                try:
                    model_path = Path(self.models_path) / "autoencoder.h5"
                    self.detectors["autoencoder"].save(str(model_path))
                except:
                    pass

            self.logger.info("训练模型保存完成")

        except Exception as e:
            self.logger.error(f"保存训练模型失败: {e}")


async def main():
    """测试主函数"""
    config = {
        "anomaly_db_path": "data/test_anomaly_detection.db",
        "models_path": "data/test_models/anomaly/",
        "contamination": 0.1,
        "min_confidence": 0.7,
        "ensemble_weights": {
            "isolation_forest": 0.4,
            "dbscan": 0.3,
            "custom_audit_rules": 0.3,
        },
    }

    async with AnomalyDetector(config) as detector:
        # 测试数据
        test_data = {
            "financial_records": [
                {"id": 1, "amount": 50000, "account": "1001", "date": "2024-01-01"},
                {
                    "id": 2,
                    "amount": 15000000,
                    "account": "1002",
                    "date": "2024-01-02",
                },  # 异常大金额
                {"id": 3, "amount": 20000, "account": "1003", "date": "2024-01-03"},
                {"id": 4, "amount": 0, "account": "1001", "date": "2024-01-04"},  # 零金额
                {
                    "id": 5,
                    "amount": -5000,
                    "account": "应收账款",
                    "date": "2024-01-05",
                },  # 负的应收账款
            ]
        }

        # 执行异常检测
        detection_result = await detector.detect_anomalies(
            data=test_data,
            detection_config={
                "detectors": ["isolation_forest", "custom_audit_rules"],
                "use_ensemble": True,
                "analyze_features": True,
                "save_results": True,
            },
        )

        print(f"异常检测结果: {json.dumps(detection_result, indent=2, ensure_ascii=False)}")


if __name__ == "__main__":
    asyncio.run(main())
