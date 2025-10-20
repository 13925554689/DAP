"""
自适应科目映射器 - Layer 3
使用NLP的智能科目映射

核心功能：
1. 智能科目映射和标准化
2. 语义相似性计算
3. 机器学习驱动的映射建议
4. 多系统科目统一
5. 映射质量评估和优化
"""

import asyncio
import logging
import json
import sqlite3
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple, Set, Union
from pathlib import Path
from dataclasses import dataclass, asdict
from concurrent.futures import ThreadPoolExecutor
import threading
from collections import defaultdict, Counter
import pickle
import hashlib
from difflib import SequenceMatcher
import re

from utils.async_utils import schedule_async_task

# NLP和文本处理
try:
    import jieba
    import jieba.analyse

    JIEBA_AVAILABLE = True
except ImportError:
    JIEBA_AVAILABLE = False

# 机器学习库
try:
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.metrics.pairwise import cosine_similarity
    from sklearn.cluster import KMeans
    from sklearn.decomposition import TruncatedSVD

    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False

# 向量数据库
try:
    import chromadb

    CHROMADB_AVAILABLE = True
except ImportError:
    CHROMADB_AVAILABLE = False

# 深度学习词向量（可选）
try:
    import gensim
    from gensim.models import Word2Vec

    GENSIM_AVAILABLE = True
except ImportError:
    GENSIM_AVAILABLE = False

# Sentence Transformers（可选）
try:
    from sentence_transformers import SentenceTransformer

    SENTENCE_TRANSFORMERS_AVAILABLE = True
except ImportError:
    SENTENCE_TRANSFORMERS_AVAILABLE = False


@dataclass
class AccountMapping:
    """科目映射记录"""

    mapping_id: str
    source_account: str
    source_system: str
    target_account: str
    target_system: str
    confidence: float
    mapping_type: str  # manual, automatic, suggested
    created_at: datetime
    updated_at: datetime
    created_by: str
    validation_status: str
    feedback_score: Optional[float]


@dataclass
class AccountSimilarity:
    """科目相似性"""

    account1: str
    account2: str
    similarity_score: float
    similarity_type: str  # semantic, lexical, structural
    features_matched: List[str]
    confidence: float


@dataclass
class MappingFeedback:
    """映射反馈"""

    feedback_id: str
    mapping_id: str
    feedback_type: str  # correct, incorrect, partial
    feedback_score: float
    expert_name: str
    feedback_time: datetime
    comments: str


class AdaptiveAccountMapper:
    """自适应科目映射器"""

    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        self.logger = logging.getLogger(__name__)

        # 数据库配置
        self.mapping_db_path = self.config.get(
            "mapping_db_path", "data/account_mapping.db"
        )
        self.models_path = self.config.get("models_path", "data/models/mapping/")

        # 映射配置
        self.similarity_threshold = self.config.get("similarity_threshold", 0.8)
        self.min_confidence = self.config.get("min_confidence", 0.7)
        self.auto_mapping_threshold = self.config.get("auto_mapping_threshold", 0.95)

        # 缓存
        self.mapping_cache = {}
        self.similarity_cache = {}
        self.account_vectors = {}

        # 标准科目表
        self.standard_accounts = {}
        self.account_categories = {}

        # ML模型
        self.tfidf_vectorizer = None
        self.similarity_model = None
        self.word2vec_model = None
        self.sentence_transformer = None

        # 并发控制
        self.max_workers = self.config.get("max_workers", 4)
        self.executor = ThreadPoolExecutor(max_workers=self.max_workers)
        self._lock = threading.RLock()

        # 向量数据库（可选）
        if CHROMADB_AVAILABLE:
            try:
                self.chroma_client = chromadb.Client()
                self.accounts_collection = self.chroma_client.get_or_create_collection(
                    "account_mappings"
                )
            except:
                self.chroma_client = None
                self.accounts_collection = None
        else:
            self.chroma_client = None
            self.accounts_collection = None

        # 中文分词支持
        if JIEBA_AVAILABLE:
            self._init_chinese_nlp()

        # 确保模型目录存在
        Path(self.models_path).mkdir(parents=True, exist_ok=True)

        # 初始化数据库
        self._init_database()

        # 加载标准科目表和模型
        schedule_async_task(
            self._load_standard_accounts,
            logger=self.logger,
            task_name="load_standard_accounts",
        )
        schedule_async_task(
            self._load_mapping_models,
            logger=self.logger,
            task_name="load_mapping_models",
        )

    def _init_chinese_nlp(self):
        """初始化中文NLP"""
        try:
            # 加载财务会计专业词典
            financial_terms = [
                # 资产类
                "库存现金",
                "银行存款",
                "其他货币资金",
                "应收票据",
                "应收账款",
                "预付账款",
                "其他应收款",
                "存货",
                "固定资产",
                "累计折旧",
                "无形资产",
                "长期股权投资",
                "可供出售金融资产",
                # 负债类
                "应付票据",
                "应付账款",
                "预收账款",
                "应付职工薪酬",
                "应交税费",
                "其他应付款",
                "短期借款",
                "长期借款",
                "应付债券",
                # 所有者权益类
                "实收资本",
                "资本公积",
                "盈余公积",
                "未分配利润",
                # 收入类
                "主营业务收入",
                "其他业务收入",
                "营业外收入",
                "投资收益",
                # 费用类
                "主营业务成本",
                "其他业务成本",
                "销售费用",
                "管理费用",
                "财务费用",
                "营业外支出",
                "所得税费用",
                # 系统相关
                "金蝶",
                "用友",
                "SAP",
                "ERP",
                "AIS",
                "K3",
                "U8",
                "NC",
            ]

            for term in financial_terms:
                jieba.add_word(term, freq=1000)

            # 设置关键词提取
            jieba.analyse.set_stop_words(self.config.get("stop_words_file"))

            self.logger.info("中文NLP初始化完成")

        except Exception as e:
            self.logger.error(f"中文NLP初始化失败: {e}")

    def _init_database(self):
        """初始化映射数据库"""
        try:
            Path(self.mapping_db_path).parent.mkdir(parents=True, exist_ok=True)

            with sqlite3.connect(self.mapping_db_path) as conn:
                cursor = conn.cursor()

                # 科目映射表
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS account_mappings (
                        mapping_id TEXT PRIMARY KEY,
                        source_account TEXT NOT NULL,
                        source_system TEXT NOT NULL,
                        target_account TEXT NOT NULL,
                        target_system TEXT NOT NULL,
                        confidence REAL NOT NULL,
                        mapping_type TEXT NOT NULL,
                        created_at TEXT NOT NULL,
                        updated_at TEXT NOT NULL,
                        created_by TEXT NOT NULL,
                        validation_status TEXT DEFAULT 'pending',
                        feedback_score REAL
                    )
                """
                )

                # 标准科目表
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS standard_accounts (
                        account_code TEXT PRIMARY KEY,
                        account_name TEXT NOT NULL,
                        category TEXT NOT NULL,
                        subcategory TEXT,
                        description TEXT,
                        keywords TEXT,
                        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                        updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                    )
                """
                )

                # 科目相似性表
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS account_similarities (
                        similarity_id TEXT PRIMARY KEY,
                        account1 TEXT NOT NULL,
                        account2 TEXT NOT NULL,
                        similarity_score REAL NOT NULL,
                        similarity_type TEXT NOT NULL,
                        features_matched TEXT,
                        confidence REAL DEFAULT 1.0,
                        computed_at TEXT NOT NULL
                    )
                """
                )

                # 映射反馈表
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS mapping_feedback (
                        feedback_id TEXT PRIMARY KEY,
                        mapping_id TEXT NOT NULL,
                        feedback_type TEXT NOT NULL,
                        feedback_score REAL NOT NULL,
                        expert_name TEXT NOT NULL,
                        feedback_time TEXT NOT NULL,
                        comments TEXT,
                        FOREIGN KEY (mapping_id) REFERENCES account_mappings (mapping_id)
                    )
                """
                )

                # 映射统计表
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS mapping_statistics (
                        stat_id TEXT PRIMARY KEY,
                        source_system TEXT NOT NULL,
                        target_system TEXT NOT NULL,
                        total_mappings INTEGER DEFAULT 0,
                        automatic_mappings INTEGER DEFAULT 0,
                        manual_mappings INTEGER DEFAULT 0,
                        avg_confidence REAL DEFAULT 0,
                        success_rate REAL DEFAULT 0,
                        last_updated TEXT DEFAULT CURRENT_TIMESTAMP
                    )
                """
                )

                # 索引
                cursor.execute(
                    "CREATE INDEX IF NOT EXISTS idx_mappings_source ON account_mappings (source_account, source_system)"
                )
                cursor.execute(
                    "CREATE INDEX IF NOT EXISTS idx_mappings_target ON account_mappings (target_account, target_system)"
                )
                cursor.execute(
                    "CREATE INDEX IF NOT EXISTS idx_standard_category ON standard_accounts (category)"
                )
                cursor.execute(
                    "CREATE INDEX IF NOT EXISTS idx_similarities_accounts ON account_similarities (account1, account2)"
                )
                cursor.execute(
                    "CREATE INDEX IF NOT EXISTS idx_feedback_mapping ON mapping_feedback (mapping_id)"
                )

                conn.commit()

            self.logger.info("科目映射数据库初始化完成")

        except Exception as e:
            self.logger.error(f"科目映射数据库初始化失败: {e}")
            raise

    async def _load_standard_accounts(self):
        """加载标准科目表"""
        try:
            # 加载标准科目（中国企业会计准则）
            standard_accounts_data = [
                # 资产类 (1xxx)
                ("1001", "库存现金", "流动资产", "货币资金", "企业库存的现金", "现金,库存,货币"),
                ("1002", "银行存款", "流动资产", "货币资金", "企业在银行的存款", "银行,存款,货币"),
                ("1012", "其他货币资金", "流动资产", "货币资金", "其他形式的货币资金", "其他,货币,资金"),
                ("1101", "应收票据", "流动资产", "应收项目", "企业持有的商业汇票", "应收,票据,汇票"),
                ("1122", "应收账款", "流动资产", "应收项目", "销售商品提供服务应收款项", "应收,账款,销售"),
                ("1123", "预付账款", "流动资产", "应收项目", "预先付给供应商的款项", "预付,账款,预付款"),
                ("1221", "其他应收款", "流动资产", "应收项目", "除应收账款外的其他应收款", "其他,应收"),
                ("1401", "材料采购", "流动资产", "存货", "采购材料的成本", "材料,采购,存货"),
                ("1402", "在途物资", "流动资产", "存货", "运输途中的物资", "在途,物资,运输"),
                ("1403", "原材料", "流动资产", "存货", "生产用原材料", "原材料,材料,生产"),
                ("1601", "固定资产", "非流动资产", "固定资产", "使用期超过一年的有形资产", "固定资产,设备,房屋"),
                ("1602", "累计折旧", "非流动资产", "固定资产", "固定资产的累计折旧", "累计折旧,折旧,摊销"),
                ("1701", "无形资产", "非流动资产", "无形资产", "没有实物形态的资产", "无形资产,专利,商标"),
                # 负债类 (2xxx)
                ("2101", "应付票据", "流动负债", "应付项目", "开出的商业汇票", "应付,票据,汇票"),
                ("2202", "应付账款", "流动负债", "应付项目", "购买商品接受服务应付款项", "应付,账款,采购"),
                ("2203", "预收账款", "流动负债", "应付项目", "预先收到客户的款项", "预收,账款,预收款"),
                ("2211", "应付职工薪酬", "流动负债", "应付项目", "应付给职工的薪酬", "应付,职工,薪酬,工资"),
                ("2221", "应交税费", "流动负债", "应付项目", "应缴纳的各种税费", "应交,税费,税金"),
                ("2241", "其他应付款", "流动负债", "应付项目", "除应付账款外的其他应付款", "其他,应付"),
                ("2501", "短期借款", "流动负债", "借款", "期限在一年以内的借款", "短期,借款,贷款"),
                ("2701", "长期借款", "非流动负债", "借款", "期限在一年以上的借款", "长期,借款,贷款"),
                # 所有者权益类 (3xxx)
                ("3101", "实收资本", "所有者权益", "资本", "投资者实际投入的资本", "实收,资本,投资"),
                ("3103", "资本公积", "所有者权益", "资本", "资本溢价等形成的公积", "资本,公积,溢价"),
                ("3104", "盈余公积", "所有者权益", "公积", "从净利润中提取的公积", "盈余,公积,提取"),
                ("3201", "未分配利润", "所有者权益", "利润", "未向投资者分配的利润", "未分配,利润,留存"),
                # 收入类 (4xxx)
                ("4001", "主营业务收入", "收入", "营业收入", "主要经营活动的收入", "主营,业务,收入,销售"),
                ("4051", "其他业务收入", "收入", "营业收入", "除主营业务外的收入", "其他,业务,收入"),
                ("4301", "营业外收入", "收入", "营业外收入", "非日常活动产生的收入", "营业外,收入,非经常"),
                # 成本费用类 (5xxx)
                ("5001", "主营业务成本", "成本", "营业成本", "主要经营活动的成本", "主营,业务,成本"),
                ("5051", "其他业务成本", "成本", "营业成本", "除主营业务外的成本", "其他,业务,成本"),
                ("5201", "销售费用", "费用", "期间费用", "销售商品发生的费用", "销售,费用,营销"),
                ("5202", "管理费用", "费用", "期间费用", "管理活动发生的费用", "管理,费用,行政"),
                ("5203", "财务费用", "费用", "期间费用", "筹资活动发生的费用", "财务,费用,利息"),
                ("5301", "营业外支出", "费用", "营业外支出", "非日常活动产生的支出", "营业外,支出,非经常"),
                ("5401", "所得税费用", "费用", "所得税", "按规定计算的所得税", "所得税,税费"),
            ]

            # 保存到数据库
            with sqlite3.connect(self.mapping_db_path) as conn:
                cursor = conn.cursor()

                for (
                    account_code,
                    account_name,
                    category,
                    subcategory,
                    description,
                    keywords,
                ) in standard_accounts_data:
                    cursor.execute(
                        """
                        INSERT OR REPLACE INTO standard_accounts
                        (account_code, account_name, category, subcategory, description, keywords)
                        VALUES (?, ?, ?, ?, ?, ?)
                    """,
                        (
                            account_code,
                            account_name,
                            category,
                            subcategory,
                            description,
                            keywords,
                        ),
                    )

                conn.commit()

            # 加载到内存
            with sqlite3.connect(self.mapping_db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT account_code, account_name, category, subcategory, description, keywords FROM standard_accounts"
                )

                for row in cursor.fetchall():
                    (
                        account_code,
                        account_name,
                        category,
                        subcategory,
                        description,
                        keywords,
                    ) = row

                    self.standard_accounts[account_code] = {
                        "name": account_name,
                        "category": category,
                        "subcategory": subcategory,
                        "description": description,
                        "keywords": keywords.split(",") if keywords else [],
                    }

                    if category not in self.account_categories:
                        self.account_categories[category] = []
                    self.account_categories[category].append(account_code)

            self.logger.info(f"标准科目表加载完成: {len(self.standard_accounts)} 个科目")

        except Exception as e:
            self.logger.error(f"加载标准科目表失败: {e}")

    async def _load_mapping_models(self):
        """加载映射模型"""
        try:
            if not SKLEARN_AVAILABLE:
                self.logger.warning("sklearn不可用，跳过ML模型加载")
                return

            # 加载TF-IDF向量化器
            tfidf_path = Path(self.models_path) / "tfidf_vectorizer.pkl"
            if tfidf_path.exists():
                with open(tfidf_path, "rb") as f:
                    self.tfidf_vectorizer = pickle.load(f)
                self.logger.info("TF-IDF向量化器加载成功")
            else:
                # 创建新的TF-IDF向量化器
                self.tfidf_vectorizer = TfidfVectorizer(
                    max_features=1000, ngram_range=(1, 2), stop_words=None  # 中文不使用默认停用词
                )

            # 加载Word2Vec模型（如果可用）
            if GENSIM_AVAILABLE:
                w2v_path = Path(self.models_path) / "word2vec_model.pkl"
                if w2v_path.exists():
                    self.word2vec_model = Word2Vec.load(str(w2v_path))
                    self.logger.info("Word2Vec模型加载成功")

            # 加载Sentence Transformer（如果可用）
            if SENTENCE_TRANSFORMERS_AVAILABLE:
                try:
                    model_name = self.config.get(
                        "sentence_transformer_model",
                        "paraphrase-multilingual-MiniLM-L12-v2",
                    )
                    self.sentence_transformer = SentenceTransformer(model_name)
                    self.logger.info("Sentence Transformer模型加载成功")
                except:
                    self.logger.warning("Sentence Transformer模型加载失败")

            # 初始化科目向量
            await self._initialize_account_vectors()

        except Exception as e:
            self.logger.error(f"加载映射模型失败: {e}")

    async def _initialize_account_vectors(self):
        """初始化科目向量"""
        try:
            if not self.standard_accounts:
                return

            # 准备科目文本
            account_texts = []
            account_codes = []

            for code, info in self.standard_accounts.items():
                # 组合科目文本：名称 + 关键词 + 描述
                text_parts = [info["name"]]
                text_parts.extend(info["keywords"])
                if info["description"]:
                    text_parts.append(info["description"])

                account_text = " ".join(text_parts)
                account_texts.append(account_text)
                account_codes.append(code)

            # 使用TF-IDF向量化
            if self.tfidf_vectorizer and account_texts:
                try:
                    tfidf_matrix = self.tfidf_vectorizer.fit_transform(account_texts)

                    for i, code in enumerate(account_codes):
                        self.account_vectors[code] = tfidf_matrix[i].toarray().flatten()

                    self.logger.info(
                        f"TF-IDF科目向量初始化完成: {len(self.account_vectors)} 个向量"
                    )
                except Exception as e:
                    self.logger.error(f"TF-IDF向量化失败: {e}")

            # 使用Sentence Transformer（如果可用）
            if self.sentence_transformer:
                try:
                    sentence_embeddings = self.sentence_transformer.encode(
                        account_texts
                    )

                    for i, code in enumerate(account_codes):
                        vector_key = f"{code}_st"
                        self.account_vectors[vector_key] = sentence_embeddings[i]

                    self.logger.info(f"Sentence Transformer向量初始化完成")
                except Exception as e:
                    self.logger.error(f"Sentence Transformer向量化失败: {e}")

        except Exception as e:
            self.logger.error(f"初始化科目向量失败: {e}")

    async def map_accounts(
        self,
        source_accounts: List[str],
        source_system: str,
        target_system: str = "standard",
    ) -> Dict[str, Any]:
        """映射科目"""
        try:
            mapping_id = f"mapping_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{hashlib.md5(str(datetime.now()).encode()).hexdigest()[:8]}"

            result = {
                "mapping_id": mapping_id,
                "source_system": source_system,
                "target_system": target_system,
                "started_at": datetime.now().isoformat(),
                "total_accounts": len(source_accounts),
                "mapped_accounts": 0,
                "auto_mapped": 0,
                "manual_required": 0,
                "mappings": {},
                "suggestions": {},
                "unmapped": [],
                "confidence_distribution": {},
                "status": "success",
            }

            # 并行处理科目映射
            tasks = []
            for source_account in source_accounts:
                task = asyncio.create_task(
                    self._map_single_account(
                        source_account, source_system, target_system
                    )
                )
                tasks.append((source_account, task))

            # 收集映射结果
            confidence_scores = []

            for source_account, task in tasks:
                try:
                    mapping_result = await task

                    if mapping_result["success"]:
                        result["mappings"][source_account] = mapping_result
                        result["mapped_accounts"] += 1

                        confidence = mapping_result["confidence"]
                        confidence_scores.append(confidence)

                        if confidence >= self.auto_mapping_threshold:
                            result["auto_mapped"] += 1
                            # 自动保存高置信度映射
                            await self._save_mapping(mapping_result, "automatic")
                        else:
                            result["manual_required"] += 1
                            result["suggestions"][source_account] = mapping_result

                    else:
                        result["unmapped"].append(source_account)

                except Exception as e:
                    self.logger.error(f"映射科目 {source_account} 失败: {e}")
                    result["unmapped"].append(source_account)

            # 计算置信度分布
            if confidence_scores:
                result["confidence_distribution"] = {
                    "avg_confidence": float(np.mean(confidence_scores)),
                    "min_confidence": float(np.min(confidence_scores)),
                    "max_confidence": float(np.max(confidence_scores)),
                    "std_confidence": float(np.std(confidence_scores)),
                }

            result["completed_at"] = datetime.now().isoformat()

            # 更新映射统计
            await self._update_mapping_statistics(source_system, target_system, result)

            self.logger.info(
                f"科目映射完成: {result['mapped_accounts']}/{result['total_accounts']} 映射成功, {result['auto_mapped']} 自动映射"
            )

            return result

        except Exception as e:
            self.logger.error(f"科目映射失败: {e}")
            return {
                "status": "error",
                "error": str(e),
                "started_at": datetime.now().isoformat(),
            }

    async def _map_single_account(
        self, source_account: str, source_system: str, target_system: str
    ) -> Dict[str, Any]:
        """映射单个科目"""
        try:
            # 检查缓存
            cache_key = f"{source_account}:{source_system}:{target_system}"
            with self._lock:
                if cache_key in self.mapping_cache:
                    cached_result = self.mapping_cache[cache_key]
                    if datetime.now() - cached_result["cached_at"] < timedelta(hours=1):
                        return cached_result["result"]

            # 多策略映射
            mapping_strategies = [
                self._exact_match_mapping,
                self._semantic_similarity_mapping,
                self._keyword_based_mapping,
                self._pattern_based_mapping,
                self._ml_based_mapping,
            ]

            best_mapping = None
            best_confidence = 0.0

            for strategy in mapping_strategies:
                try:
                    mapping_result = await strategy(
                        source_account, source_system, target_system
                    )

                    if (
                        mapping_result
                        and mapping_result.get("confidence", 0) > best_confidence
                    ):
                        best_mapping = mapping_result
                        best_confidence = mapping_result["confidence"]

                    # 如果找到高置信度映射，提前结束
                    if best_confidence >= self.auto_mapping_threshold:
                        break

                except Exception as e:
                    self.logger.error(f"映射策略 {strategy.__name__} 失败: {e}")

            if best_mapping:
                result = {
                    "success": True,
                    "source_account": source_account,
                    "source_system": source_system,
                    "target_account": best_mapping["target_account"],
                    "target_system": target_system,
                    "confidence": best_mapping["confidence"],
                    "mapping_method": best_mapping["method"],
                    "similarity_details": best_mapping.get("details", {}),
                    "alternatives": best_mapping.get("alternatives", []),
                }
            else:
                result = {
                    "success": False,
                    "source_account": source_account,
                    "source_system": source_system,
                    "target_system": target_system,
                    "reason": "未找到合适的映射",
                }

            # 缓存结果
            with self._lock:
                self.mapping_cache[cache_key] = {
                    "result": result,
                    "cached_at": datetime.now(),
                }

            return result

        except Exception as e:
            self.logger.error(f"映射单个科目失败: {e}")
            return {"success": False, "source_account": source_account, "error": str(e)}

    async def _exact_match_mapping(
        self, source_account: str, source_system: str, target_system: str
    ) -> Optional[Dict[str, Any]]:
        """精确匹配映射"""
        try:
            # 标准化科目名称
            normalized_source = self._normalize_account_name(source_account)

            for code, info in self.standard_accounts.items():
                normalized_target = self._normalize_account_name(info["name"])

                if normalized_source == normalized_target:
                    return {
                        "target_account": code,
                        "confidence": 1.0,
                        "method": "exact_match",
                        "details": {
                            "normalized_source": normalized_source,
                            "normalized_target": normalized_target,
                        },
                    }

            return None

        except Exception as e:
            self.logger.error(f"精确匹配失败: {e}")
            return None

    def _normalize_account_name(self, account_name: str) -> str:
        """标准化科目名称"""
        try:
            # 移除常见的系统特定前缀/后缀
            normalized = account_name.strip()

            # 移除数字编码
            normalized = re.sub(r"^\d+[-.]?\s*", "", normalized)

            # 移除括号内容
            normalized = re.sub(r"\([^)]*\)", "", normalized)

            # 移除常见后缀
            suffixes_to_remove = ["科目", "账户", "明细", "总账", "辅助"]
            for suffix in suffixes_to_remove:
                if normalized.endswith(suffix):
                    normalized = normalized[: -len(suffix)]

            # 标准化空白字符
            normalized = re.sub(r"\s+", "", normalized)

            return normalized.lower()

        except Exception as e:
            self.logger.error(f"标准化科目名称失败: {e}")
            return account_name

    async def _semantic_similarity_mapping(
        self, source_account: str, source_system: str, target_system: str
    ) -> Optional[Dict[str, Any]]:
        """语义相似性映射"""
        try:
            if not self.tfidf_vectorizer:
                return None

            # 向量化源科目
            source_text = self._prepare_account_text(source_account)
            source_vector = (
                self.tfidf_vectorizer.transform([source_text]).toarray().flatten()
            )

            best_similarity = 0.0
            best_target = None
            similarities = {}

            # 计算与所有标准科目的相似性
            for code, target_vector in self.account_vectors.items():
                if "_st" in code:  # 跳过Sentence Transformer向量
                    continue

                similarity = cosine_similarity([source_vector], [target_vector])[0][0]
                similarities[code] = similarity

                if similarity > best_similarity:
                    best_similarity = similarity
                    best_target = code

            if best_similarity >= self.similarity_threshold:
                # 获取备选方案
                sorted_similarities = sorted(
                    similarities.items(), key=lambda x: x[1], reverse=True
                )
                alternatives = [
                    {
                        "target_account": code,
                        "confidence": float(sim),
                        "account_name": self.standard_accounts[code]["name"],
                    }
                    for code, sim in sorted_similarities[1:6]  # 前5个备选
                    if sim >= self.min_confidence
                ]

                return {
                    "target_account": best_target,
                    "confidence": float(best_similarity),
                    "method": "semantic_similarity",
                    "details": {
                        "similarity_score": float(best_similarity),
                        "vectorization_method": "tfidf",
                    },
                    "alternatives": alternatives,
                }

            return None

        except Exception as e:
            self.logger.error(f"语义相似性映射失败: {e}")
            return None

    def _prepare_account_text(self, account_name: str) -> str:
        """准备科目文本用于向量化"""
        try:
            # 分词（如果有jieba）
            if JIEBA_AVAILABLE:
                words = jieba.lcut(account_name)
                return " ".join(words)
            else:
                return account_name

        except Exception as e:
            self.logger.error(f"准备科目文本失败: {e}")
            return account_name

    async def _keyword_based_mapping(
        self, source_account: str, source_system: str, target_system: str
    ) -> Optional[Dict[str, Any]]:
        """基于关键词的映射"""
        try:
            # 提取源科目关键词
            source_keywords = self._extract_keywords(source_account)

            if not source_keywords:
                return None

            best_score = 0.0
            best_target = None
            keyword_matches = {}

            for code, info in self.standard_accounts.items():
                target_keywords = info["keywords"]

                # 计算关键词匹配分数
                match_score = self._calculate_keyword_match_score(
                    source_keywords, target_keywords
                )
                keyword_matches[code] = match_score

                if match_score > best_score:
                    best_score = match_score
                    best_target = code

            if best_score >= self.min_confidence:
                return {
                    "target_account": best_target,
                    "confidence": float(best_score),
                    "method": "keyword_based",
                    "details": {
                        "source_keywords": source_keywords,
                        "target_keywords": self.standard_accounts[best_target][
                            "keywords"
                        ],
                        "match_score": float(best_score),
                    },
                }

            return None

        except Exception as e:
            self.logger.error(f"关键词映射失败: {e}")
            return None

    def _extract_keywords(self, text: str) -> List[str]:
        """提取关键词"""
        try:
            if JIEBA_AVAILABLE:
                # 使用jieba提取关键词
                keywords = jieba.analyse.extract_tags(text, topK=10, withWeight=False)
                return keywords
            else:
                # 简单的关键词提取
                words = re.findall(r"[\u4e00-\u9fa5a-zA-Z]+", text)
                return words

        except Exception as e:
            self.logger.error(f"提取关键词失败: {e}")
            return []

    def _calculate_keyword_match_score(
        self, source_keywords: List[str], target_keywords: List[str]
    ) -> float:
        """计算关键词匹配分数"""
        try:
            if not source_keywords or not target_keywords:
                return 0.0

            # 计算交集
            source_set = set(source_keywords)
            target_set = set(target_keywords)
            intersection = source_set.intersection(target_set)

            # Jaccard相似性
            union = source_set.union(target_set)
            jaccard_score = len(intersection) / len(union) if union else 0.0

            # 加权计算（给予更高权重给重要关键词）
            important_keywords = {"现金", "银行", "应收", "应付", "收入", "费用", "资产", "负债"}
            weighted_score = jaccard_score

            for keyword in intersection:
                if keyword in important_keywords:
                    weighted_score += 0.1

            return min(weighted_score, 1.0)

        except Exception as e:
            self.logger.error(f"计算关键词匹配分数失败: {e}")
            return 0.0

    async def _pattern_based_mapping(
        self, source_account: str, source_system: str, target_system: str
    ) -> Optional[Dict[str, Any]]:
        """基于模式的映射"""
        try:
            # 定义常见的科目名称模式
            patterns = {
                r"现金|库存现金": "1001",
                r"银行|银行存款": "1002",
                r"应收账款|应收款": "1122",
                r"预付|预付账款": "1123",
                r"原材料|材料": "1403",
                r"固定资产|设备|房屋": "1601",
                r"累计折旧|折旧": "1602",
                r"应付账款|应付款": "2202",
                r"预收|预收账款": "2203",
                r"应付职工薪酬|工资|薪酬": "2211",
                r"应交税费|税费|税金": "2221",
                r"短期借款|短期贷款": "2501",
                r"实收资本|注册资本": "3101",
                r"主营业务收入|销售收入|营业收入": "4001",
                r"主营业务成本|销售成本|营业成本": "5001",
                r"管理费用|行政费用": "5202",
                r"销售费用|营销费用": "5201",
                r"财务费用|利息": "5203",
            }

            for pattern, target_code in patterns.items():
                if re.search(pattern, source_account):
                    confidence = 0.8  # 模式匹配的基础置信度

                    # 根据匹配精度调整置信度
                    if re.fullmatch(pattern, source_account):
                        confidence = 0.95

                    return {
                        "target_account": target_code,
                        "confidence": confidence,
                        "method": "pattern_based",
                        "details": {
                            "matched_pattern": pattern,
                            "pattern_type": "regex",
                        },
                    }

            return None

        except Exception as e:
            self.logger.error(f"模式映射失败: {e}")
            return None

    async def _ml_based_mapping(
        self, source_account: str, source_system: str, target_system: str
    ) -> Optional[Dict[str, Any]]:
        """基于机器学习的映射"""
        try:
            # 如果有训练好的分类器，使用ML进行映射
            if not self.rule_classifier:
                return None

            # 特征提取
            features = self._extract_ml_features(source_account, source_system)

            if not features:
                return None

            # 预测
            try:
                prediction = self.rule_classifier.predict([features])[0]
                prediction_proba = self.rule_classifier.predict_proba([features])[0]
                confidence = float(max(prediction_proba))

                if confidence >= self.min_confidence:
                    return {
                        "target_account": prediction,
                        "confidence": confidence,
                        "method": "ml_based",
                        "details": {
                            "model_type": type(self.rule_classifier).__name__,
                            "prediction_probability": confidence,
                        },
                    }

            except Exception as e:
                self.logger.error(f"ML预测失败: {e}")

            return None

        except Exception as e:
            self.logger.error(f"ML映射失败: {e}")
            return None

    def _extract_ml_features(
        self, account_name: str, system_name: str
    ) -> Optional[List[float]]:
        """提取ML特征"""
        try:
            # 这里应该实现复杂的特征提取逻辑
            # 包括文本特征、系统特征、上下文特征等

            features = []

            # 文本长度特征
            features.append(len(account_name))

            # 是否包含数字
            features.append(1.0 if re.search(r"\d", account_name) else 0.0)

            # 系统类型特征
            system_features = {"金蝶": [1, 0, 0], "用友": [0, 1, 0], "SAP": [0, 0, 1]}
            features.extend(system_features.get(system_name, [0, 0, 0]))

            # TF-IDF特征
            if self.tfidf_vectorizer:
                try:
                    tfidf_features = (
                        self.tfidf_vectorizer.transform([account_name])
                        .toarray()
                        .flatten()
                    )
                    features.extend(tfidf_features[:50])  # 取前50个TF-IDF特征
                except:
                    features.extend([0.0] * 50)

            return features

        except Exception as e:
            self.logger.error(f"提取ML特征失败: {e}")
            return None

    async def _save_mapping(self, mapping_result: Dict[str, Any], mapping_type: str):
        """保存映射结果"""
        try:
            mapping_id = f"map_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{hashlib.md5(str(datetime.now()).encode()).hexdigest()[:8]}"

            mapping = AccountMapping(
                mapping_id=mapping_id,
                source_account=mapping_result["source_account"],
                source_system=mapping_result["source_system"],
                target_account=mapping_result["target_account"],
                target_system=mapping_result["target_system"],
                confidence=mapping_result["confidence"],
                mapping_type=mapping_type,
                created_at=datetime.now(),
                updated_at=datetime.now(),
                created_by=mapping_result.get("created_by", "system"),
                validation_status="pending",
                feedback_score=None,
            )

            with sqlite3.connect(self.mapping_db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    INSERT INTO account_mappings
                    (mapping_id, source_account, source_system, target_account, target_system,
                     confidence, mapping_type, created_at, updated_at, created_by, validation_status)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                    (
                        mapping.mapping_id,
                        mapping.source_account,
                        mapping.source_system,
                        mapping.target_account,
                        mapping.target_system,
                        mapping.confidence,
                        mapping.mapping_type,
                        mapping.created_at.isoformat(),
                        mapping.updated_at.isoformat(),
                        mapping.created_by,
                        mapping.validation_status,
                    ),
                )
                conn.commit()

            self.logger.info(f"映射保存成功: {mapping_id}")

        except Exception as e:
            self.logger.error(f"保存映射失败: {e}")

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
            await self._save_mapping_models()

            self.logger.info("自适应科目映射器资源清理完成")

        except Exception as e:
            self.logger.error(f"资源清理失败: {e}")

    async def _save_mapping_models(self):
        """保存映射模型"""
        try:
            if self.tfidf_vectorizer:
                tfidf_path = Path(self.models_path) / "tfidf_vectorizer.pkl"
                with open(tfidf_path, "wb") as f:
                    pickle.dump(self.tfidf_vectorizer, f)

            if self.word2vec_model:
                w2v_path = Path(self.models_path) / "word2vec_model.pkl"
                self.word2vec_model.save(str(w2v_path))

            self.logger.info("映射模型保存完成")

        except Exception as e:
            self.logger.error(f"保存映射模型失败: {e}")


async def main():
    """测试主函数"""
    config = {
        "mapping_db_path": "data/test_account_mapping.db",
        "models_path": "data/test_models/mapping/",
        "similarity_threshold": 0.8,
        "min_confidence": 0.7,
        "auto_mapping_threshold": 0.95,
    }

    async with AdaptiveAccountMapper(config) as mapper:
        # 测试科目映射
        source_accounts = [
            "1001-库存现金",
            "银行存款-工商银行",
            "应收账款",
            "固定资产-机器设备",
            "主营业务收入",
            "管理费用-办公费",
        ]

        mapping_result = await mapper.map_accounts(
            source_accounts=source_accounts,
            source_system="金蝶K3",
            target_system="standard",
        )

        print(f"科目映射结果: {json.dumps(mapping_result, indent=2, ensure_ascii=False)}")


if __name__ == "__main__":
    asyncio.run(main())
