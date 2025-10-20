"""
自然语言审计智能体 - Layer 4
复杂审计查询的自然语言AI智能体

核心功能：
1. 自然语言查询理解
2. 智能SQL生成
3. 审计知识推理
4. 多轮对话支持
5. 审计报告生成
"""

import asyncio
import logging
import json
import sqlite3
import re
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple, Set, Union
from pathlib import Path
from dataclasses import dataclass, asdict
from concurrent.futures import ThreadPoolExecutor
import threading
from collections import defaultdict, deque
import hashlib
import uuid
from enum import Enum

# NLP处理
try:
    import jieba
    import jieba.analyse
    JIEBA_AVAILABLE = True
except ImportError:
    JIEBA_AVAILABLE = False

# 机器学习
try:
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.metrics.pairwise import cosine_similarity
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False

# OpenAI API（可选）
try:
    import openai
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False

# 本地LLM（可选）
try:
    from transformers import pipeline, AutoTokenizer, AutoModel
    TRANSFORMERS_AVAILABLE = True
except ImportError:
    TRANSFORMERS_AVAILABLE = False

class QueryType(Enum):
    """查询类型"""
    DATA_RETRIEVAL = "data_retrieval"    # 数据检索
    ANALYSIS = "analysis"                # 分析查询
    COMPARISON = "comparison"            # 对比查询
    TREND = "trend"                      # 趋势查询
    AGGREGATION = "aggregation"          # 聚合查询
    EXCEPTION = "exception"              # 异常查询
    COMPLIANCE = "compliance"            # 合规查询

class IntentType(Enum):
    """意图类型"""
    QUESTION = "question"                # 问题询问
    COMMAND = "command"                  # 命令执行
    REQUEST = "request"                  # 请求操作
    CLARIFICATION = "clarification"      # 澄清说明

@dataclass
class QueryContext:
    """查询上下文"""
    session_id: str
    user_id: str
    query_text: str
    intent: IntentType
    entities: Dict[str, Any]
    time_period: Optional[Dict[str, str]]
    data_scope: List[str]
    previous_queries: List[str]

@dataclass
class QueryResult:
    """查询结果"""
    result_id: str
    query_text: str
    sql_generated: str
    data_results: Any
    explanation: str
    confidence: float
    execution_time: float
    created_at: datetime

@dataclass
class ConversationTurn:
    """对话回合"""
    turn_id: str
    user_input: str
    agent_response: str
    query_context: QueryContext
    query_result: Optional[QueryResult]
    timestamp: datetime

class NLAuditAgent:
    """自然语言审计智能体"""

    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        self.logger = logging.getLogger(__name__)

        # 数据库配置
        self.agent_db_path = self.config.get('agent_db_path', 'data/nl_audit_agent.db')

        # AI配置
        self.llm_provider = self.config.get('llm_provider', 'local')  # local, openai
        self.openai_api_key = self.config.get('openai_api_key')
        self.model_name = self.config.get('model_name', 'gpt-3.5-turbo')

        # 会话管理
        self.active_conversations = {}
        self.conversation_history = deque(maxlen=1000)

        # 知识库
        self.audit_knowledge = {}
        self.sql_templates = {}
        self.entity_patterns = {}

        # NLP模型
        self.intent_classifier = None
        self.entity_extractor = None
        self.query_generator = None

        # 并发控制
        self.max_workers = self.config.get('max_workers', 4)
        self.executor = ThreadPoolExecutor(max_workers=self.max_workers)
        self._lock = threading.RLock()

        # 初始化
        self._init_database()
        self._init_nlp_models()
        self._load_audit_knowledge()
        self._load_sql_templates()

    def _init_database(self):
        """初始化智能体数据库"""
        try:
            Path(self.agent_db_path).parent.mkdir(parents=True, exist_ok=True)

            with sqlite3.connect(self.agent_db_path) as conn:
                cursor = conn.cursor()

                # 对话会话表
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS conversation_sessions (
                        session_id TEXT PRIMARY KEY,
                        user_id TEXT NOT NULL,
                        started_at TEXT NOT NULL,
                        last_activity TEXT NOT NULL,
                        conversation_context TEXT,
                        session_summary TEXT,
                        is_active BOOLEAN DEFAULT 1
                    )
                ''')

                # 对话回合表
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS conversation_turns (
                        turn_id TEXT PRIMARY KEY,
                        session_id TEXT NOT NULL,
                        turn_number INTEGER NOT NULL,
                        user_input TEXT NOT NULL,
                        agent_response TEXT NOT NULL,
                        query_context TEXT,
                        query_result TEXT,
                        timestamp TEXT NOT NULL,
                        FOREIGN KEY (session_id) REFERENCES conversation_sessions (session_id)
                    )
                ''')

                # 查询结果表
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS query_results (
                        result_id TEXT PRIMARY KEY,
                        session_id TEXT NOT NULL,
                        query_text TEXT NOT NULL,
                        sql_generated TEXT,
                        data_results TEXT,
                        explanation TEXT,
                        confidence REAL DEFAULT 0,
                        execution_time REAL DEFAULT 0,
                        created_at TEXT NOT NULL,
                        user_feedback INTEGER DEFAULT 0,
                        FOREIGN KEY (session_id) REFERENCES conversation_sessions (session_id)
                    )
                ''')

                # 意图训练数据表
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS intent_training_data (
                        training_id TEXT PRIMARY KEY,
                        text TEXT NOT NULL,
                        intent TEXT NOT NULL,
                        entities TEXT,
                        confidence REAL DEFAULT 1.0,
                        created_at TEXT DEFAULT CURRENT_TIMESTAMP
                    )
                ''')

                # SQL模板表
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS sql_templates (
                        template_id TEXT PRIMARY KEY,
                        template_name TEXT NOT NULL,
                        query_pattern TEXT NOT NULL,
                        sql_template TEXT NOT NULL,
                        parameters TEXT,
                        usage_count INTEGER DEFAULT 0,
                        success_rate REAL DEFAULT 100,
                        created_at TEXT DEFAULT CURRENT_TIMESTAMP
                    )
                ''')

                # 索引
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_sessions_user ON conversation_sessions (user_id)')
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_turns_session ON conversation_turns (session_id)')
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_results_session ON query_results (session_id)')
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_training_intent ON intent_training_data (intent)')

                conn.commit()

            self.logger.info("自然语言审计智能体数据库初始化完成")

        except Exception as e:
            self.logger.error(f"自然语言审计智能体数据库初始化失败: {e}")
            raise

    def _init_nlp_models(self):
        """初始化NLP模型"""
        try:
            # 初始化中文分词
            if JIEBA_AVAILABLE:
                # 加载审计专业词典
                audit_terms = [
                    '审计', '内控', '风险', '合规', '资产', '负债', '收入', '费用',
                    '现金流', '利润', '应收账款', '应付账款', '存货', '固定资产',
                    '主营业务', '营业外', '管理费用', '销售费用', '财务费用',
                    '毛利率', '净利率', '资产负债率', '流动比率', '速动比率'
                ]

                for term in audit_terms:
                    jieba.add_word(term, freq=1000)

                # 设置关键词提取
                jieba.analyse.set_stop_words(None)

            # 初始化意图分类器
            if SKLEARN_AVAILABLE:
                self.intent_classifier = TfidfVectorizer(
                    max_features=1000,
                    ngram_range=(1, 3),
                    stop_words=None
                )

            # 初始化OpenAI
            if self.llm_provider == 'openai' and OPENAI_AVAILABLE and self.openai_api_key:
                openai.api_key = self.openai_api_key

            self.logger.info("NLP模型初始化完成")

        except Exception as e:
            self.logger.error(f"NLP模型初始化失败: {e}")

    def _load_audit_knowledge(self):
        """加载审计知识"""
        try:
            # 审计领域知识
            self.audit_knowledge = {
                '会计科目': {
                    '资产类': ['1001-库存现金', '1002-银行存款', '1122-应收账款', '1403-原材料', '1601-固定资产'],
                    '负债类': ['2202-应付账款', '2211-应付职工薪酬', '2221-应交税费', '2501-短期借款'],
                    '权益类': ['3101-实收资本', '3103-资本公积', '3201-未分配利润'],
                    '收入类': ['4001-主营业务收入', '4051-其他业务收入', '4301-营业外收入'],
                    '费用类': ['5001-主营业务成本', '5201-销售费用', '5202-管理费用', '5203-财务费用']
                },
                '财务指标': {
                    '盈利能力': ['毛利率', '净利率', '资产收益率', '净资产收益率'],
                    '偿债能力': ['流动比率', '速动比率', '资产负债率', '利息保障倍数'],
                    '运营能力': ['应收账款周转率', '存货周转率', '总资产周转率'],
                    '成长能力': ['营业收入增长率', '净利润增长率', '总资产增长率']
                },
                '审计程序': {
                    '风险评估': ['了解被审计单位', '识别重大错报风险', '评估内部控制'],
                    '控制测试': ['控制设计有效性', '控制运行有效性'],
                    '实质性程序': ['分析性程序', '细节测试', '函证程序']
                }
            }

            # 实体识别模式
            self.entity_patterns = {
                '金额': r'(\d+(?:\.\d+)?)\s*(?:元|万元|亿元)',
                '日期': r'(\d{4}年(?:\d{1,2}月(?:\d{1,2}日)?)?|\d{4}-\d{1,2}-\d{1,2})',
                '期间': r'(\d{4}年[上下]半年|\d{4}年第[一二三四]季度|\d{4}年)',
                '科目代码': r'(\d{4})',
                '比率': r'(\d+(?:\.\d+)?%)',
                '公司': r'([A-Za-z\u4e00-\u9fa5]+(?:公司|集团|企业|有限|股份))'
            }

            self.logger.info("审计知识加载完成")

        except Exception as e:
            self.logger.error(f"审计知识加载失败: {e}")

    def _load_sql_templates(self):
        """加载SQL模板"""
        try:
            # SQL查询模板
            self.sql_templates = {
                '余额查询': {
                    'pattern': r'(?:查询|显示|获取).*?(?:余额|金额)',
                    'template': '''
                        SELECT account_code, account_name, balance
                        FROM accounts
                        WHERE {conditions}
                        ORDER BY balance DESC
                    ''',
                    'parameters': ['account_filter', 'date_filter']
                },
                '趋势分析': {
                    'pattern': r'(?:趋势|变化|增长|下降).*?(?:分析|情况)',
                    'template': '''
                        SELECT period, account_name, amount,
                               LAG(amount) OVER (ORDER BY period) as prev_amount,
                               (amount - LAG(amount) OVER (ORDER BY period)) / LAG(amount) OVER (ORDER BY period) * 100 as growth_rate
                        FROM financial_data
                        WHERE {conditions}
                        ORDER BY period, account_name
                    ''',
                    'parameters': ['account_filter', 'period_filter']
                },
                '异常检测': {
                    'pattern': r'(?:异常|异常值|异常交易|可疑)',
                    'template': '''
                        SELECT *,
                               ABS(amount - AVG(amount) OVER (PARTITION BY account_code)) / STDDEV(amount) OVER (PARTITION BY account_code) as z_score
                        FROM transactions
                        WHERE {conditions}
                        HAVING ABS(z_score) > 2
                        ORDER BY z_score DESC
                    ''',
                    'parameters': ['amount_threshold', 'date_filter']
                },
                '对比分析': {
                    'pattern': r'(?:对比|比较|差异)',
                    'template': '''
                        SELECT
                            t1.account_name,
                            t1.amount as current_amount,
                            t2.amount as previous_amount,
                            (t1.amount - t2.amount) as difference,
                            CASE WHEN t2.amount > 0 THEN (t1.amount - t2.amount) / t2.amount * 100 ELSE 0 END as change_percent
                        FROM financial_data t1
                        LEFT JOIN financial_data t2 ON t1.account_code = t2.account_code
                        WHERE {conditions}
                        ORDER BY ABS(change_percent) DESC
                    ''',
                    'parameters': ['current_period', 'previous_period']
                },
                '汇总统计': {
                    'pattern': r'(?:汇总|统计|合计|总计)',
                    'template': '''
                        SELECT
                            {group_by_fields},
                            COUNT(*) as record_count,
                            SUM(amount) as total_amount,
                            AVG(amount) as avg_amount,
                            MAX(amount) as max_amount,
                            MIN(amount) as min_amount
                        FROM {table_name}
                        WHERE {conditions}
                        GROUP BY {group_by_fields}
                        ORDER BY total_amount DESC
                    ''',
                    'parameters': ['group_by_fields', 'table_name', 'conditions']
                }
            }

            self.logger.info("SQL模板加载完成")

        except Exception as e:
            self.logger.error(f"SQL模板加载失败: {e}")

    async def process_query(self, user_input: str, session_id: str = None, user_id: str = 'default') -> Dict[str, Any]:
        """处理自然语言查询"""
        try:
            # 创建或获取会话
            if not session_id:
                session_id = await self._create_session(user_id)

            query_id = f"query_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"

            result = {
                'query_id': query_id,
                'session_id': session_id,
                'user_input': user_input,
                'started_at': datetime.now().isoformat(),
                'agent_response': '',
                'sql_generated': '',
                'data_results': None,
                'explanation': '',
                'confidence': 0.0,
                'suggestions': [],
                'status': 'success'
            }

            # 1. 查询理解
            query_context = await self._understand_query(user_input, session_id)

            # 2. 意图识别
            intent = await self._classify_intent(user_input, query_context)

            # 3. 实体提取
            entities = await self._extract_entities(user_input)

            # 4. 查询生成
            if intent == IntentType.QUESTION:
                sql_query, confidence = await self._generate_sql_query(user_input, entities, query_context)
                result['sql_generated'] = sql_query
                result['confidence'] = confidence

                if sql_query and confidence > 0.5:
                    # 5. 执行查询
                    data_results = await self._execute_query(sql_query)
                    result['data_results'] = data_results

                    # 6. 生成回答
                    response = await self._generate_response(user_input, data_results, query_context)
                    result['agent_response'] = response
                    result['explanation'] = await self._generate_explanation(sql_query, data_results)
                else:
                    result['agent_response'] = await self._generate_clarification_response(user_input, entities)

            elif intent == IntentType.CLARIFICATION:
                result['agent_response'] = await self._handle_clarification(user_input, session_id)

            else:
                result['agent_response'] = await self._generate_help_response(user_input)

            # 7. 生成建议
            result['suggestions'] = await self._generate_suggestions(user_input, query_context)

            # 8. 保存对话记录
            await self._save_conversation_turn(session_id, user_input, result)

            result['completed_at'] = datetime.now().isoformat()

            self.logger.info(f"查询处理完成: {query_id}")
            return result

        except Exception as e:
            self.logger.error(f"处理查询失败: {e}")
            return {
                'status': 'error',
                'error': str(e),
                'user_input': user_input,
                'started_at': datetime.now().isoformat()
            }

    async def _understand_query(self, user_input: str, session_id: str) -> QueryContext:
        """理解查询上下文"""
        try:
            # 获取会话历史
            previous_queries = await self._get_session_history(session_id)

            # 提取时间信息
            time_period = self._extract_time_period(user_input)

            # 确定数据范围
            data_scope = self._extract_data_scope(user_input)

            query_context = QueryContext(
                session_id=session_id,
                user_id='default',
                query_text=user_input,
                intent=IntentType.QUESTION,
                entities={},
                time_period=time_period,
                data_scope=data_scope,
                previous_queries=previous_queries
            )

            return query_context

        except Exception as e:
            self.logger.error(f"查询理解失败: {e}")
            return QueryContext(
                session_id=session_id,
                user_id='default',
                query_text=user_input,
                intent=IntentType.QUESTION,
                entities={},
                time_period=None,
                data_scope=[],
                previous_queries=[]
            )

    async def _classify_intent(self, user_input: str, context: QueryContext) -> IntentType:
        """分类用户意图"""
        try:
            # 简单的规则分类
            if any(word in user_input for word in ['什么', '哪些', '多少', '如何', '为什么']):
                return IntentType.QUESTION

            if any(word in user_input for word in ['请', '帮我', '能否', '可以']):
                return IntentType.REQUEST

            if any(word in user_input for word in ['是指', '意思', '解释']):
                return IntentType.CLARIFICATION

            if any(word in user_input for word in ['查询', '显示', '分析', '统计']):
                return IntentType.COMMAND

            return IntentType.QUESTION

        except Exception as e:
            self.logger.error(f"意图分类失败: {e}")
            return IntentType.QUESTION

    async def _extract_entities(self, user_input: str) -> Dict[str, Any]:
        """提取实体"""
        try:
            entities = {}

            # 使用正则表达式提取实体
            for entity_type, pattern in self.entity_patterns.items():
                matches = re.findall(pattern, user_input)
                if matches:
                    entities[entity_type] = matches

            # 提取会计科目
            account_names = []
            for category, accounts in self.audit_knowledge['会计科目'].items():
                for account in accounts:
                    account_name = account.split('-')[1] if '-' in account else account
                    if account_name in user_input:
                        account_names.append(account_name)

            if account_names:
                entities['会计科目'] = account_names

            # 提取财务指标
            indicators = []
            for category, indicator_list in self.audit_knowledge['财务指标'].items():
                for indicator in indicator_list:
                    if indicator in user_input:
                        indicators.append(indicator)

            if indicators:
                entities['财务指标'] = indicators

            return entities

        except Exception as e:
            self.logger.error(f"实体提取失败: {e}")
            return {}

    async def _generate_sql_query(self, user_input: str, entities: Dict[str, Any], context: QueryContext) -> Tuple[str, float]:
        """生成SQL查询"""
        try:
            # 匹配SQL模板
            best_template = None
            best_score = 0.0

            for template_name, template_info in self.sql_templates.items():
                pattern = template_info['pattern']
                if re.search(pattern, user_input):
                    # 计算匹配分数
                    score = len(re.findall(pattern, user_input)) / len(user_input.split())
                    if score > best_score:
                        best_score = score
                        best_template = template_info

            if not best_template or best_score < 0.1:
                return '', 0.0

            # 生成查询条件
            conditions = []
            parameters = {}

            # 时间条件
            if context.time_period:
                start_date = context.time_period.get('start_date')
                end_date = context.time_period.get('end_date')
                if start_date:
                    conditions.append(f"date >= '{start_date}'")
                if end_date:
                    conditions.append(f"date <= '{end_date}'")

            # 科目条件
            if '会计科目' in entities:
                account_names = entities['会计科目']
                account_condition = "account_name IN ('" + "', '".join(account_names) + "')"
                conditions.append(account_condition)

            # 金额条件
            if '金额' in entities:
                amounts = entities['金额']
                for amount in amounts:
                    # 简单处理，假设是最小金额
                    conditions.append(f"amount >= {amount}")

            # 替换模板参数
            sql_template = best_template['template']
            if conditions:
                sql_query = sql_template.replace('{conditions}', ' AND '.join(conditions))
            else:
                sql_query = sql_template.replace('{conditions}', '1=1')

            # 处理其他参数
            if '{group_by_fields}' in sql_query:
                sql_query = sql_query.replace('{group_by_fields}', 'account_name')

            if '{table_name}' in sql_query:
                sql_query = sql_query.replace('{table_name}', 'financial_data')

            # 清理SQL
            sql_query = re.sub(r'\s+', ' ', sql_query).strip()

            confidence = min(best_score * 2, 1.0)  # 调整置信度

            return sql_query, confidence

        except Exception as e:
            self.logger.error(f"SQL查询生成失败: {e}")
            return '', 0.0

    def _extract_time_period(self, user_input: str) -> Optional[Dict[str, str]]:
        """提取时间期间"""
        try:
            time_period = {}

            # 提取年份
            year_match = re.search(r'(\d{4})年', user_input)
            if year_match:
                year = year_match.group(1)
                time_period['year'] = year
                time_period['start_date'] = f"{year}-01-01"
                time_period['end_date'] = f"{year}-12-31"

            # 提取季度
            quarter_match = re.search(r'第([一二三四])季度', user_input)
            if quarter_match and 'year' in time_period:
                quarter_map = {'一': 1, '二': 2, '三': 3, '四': 4}
                quarter = quarter_map[quarter_match.group(1)]
                year = time_period['year']

                if quarter == 1:
                    time_period['start_date'] = f"{year}-01-01"
                    time_period['end_date'] = f"{year}-03-31"
                elif quarter == 2:
                    time_period['start_date'] = f"{year}-04-01"
                    time_period['end_date'] = f"{year}-06-30"
                elif quarter == 3:
                    time_period['start_date'] = f"{year}-07-01"
                    time_period['end_date'] = f"{year}-09-30"
                elif quarter == 4:
                    time_period['start_date'] = f"{year}-10-01"
                    time_period['end_date'] = f"{year}-12-31"

            # 提取月份
            month_match = re.search(r'(\d{1,2})月', user_input)
            if month_match and 'year' in time_period:
                month = month_match.group(1).zfill(2)
                year = time_period['year']
                time_period['start_date'] = f"{year}-{month}-01"
                # 计算月末日期
                if month in ['01', '03', '05', '07', '08', '10', '12']:
                    time_period['end_date'] = f"{year}-{month}-31"
                elif month in ['04', '06', '09', '11']:
                    time_period['end_date'] = f"{year}-{month}-30"
                else:  # 2月
                    time_period['end_date'] = f"{year}-{month}-28"

            return time_period if time_period else None

        except Exception as e:
            self.logger.error(f"时间期间提取失败: {e}")
            return None

    def _extract_data_scope(self, user_input: str) -> List[str]:
        """提取数据范围"""
        try:
            data_scope = []

            # 根据关键词确定数据范围
            if any(word in user_input for word in ['资产', '负债', '资产负债表']):
                data_scope.append('balance_sheet')

            if any(word in user_input for word in ['收入', '费用', '利润', '损益表']):
                data_scope.append('income_statement')

            if any(word in user_input for word in ['现金流', '现金流量表']):
                data_scope.append('cash_flow')

            if any(word in user_input for word in ['交易', '凭证', '明细']):
                data_scope.append('transactions')

            # 默认范围
            if not data_scope:
                data_scope = ['financial_data']

            return data_scope

        except Exception as e:
            self.logger.error(f"数据范围提取失败: {e}")
            return ['financial_data']

    async def _execute_query(self, sql_query: str) -> Any:
        """执行SQL查询"""
        try:
            # 这里应该连接到实际的数据库
            # 为了演示，返回模拟数据

            if 'balance' in sql_query.lower():
                return [
                    {'account_code': '1001', 'account_name': '库存现金', 'balance': 100000},
                    {'account_code': '1002', 'account_name': '银行存款', 'balance': 500000},
                    {'account_code': '1122', 'account_name': '应收账款', 'balance': 300000}
                ]

            elif 'trend' in sql_query.lower() or 'growth' in sql_query.lower():
                return [
                    {'period': '2023-Q1', 'account_name': '主营业务收入', 'amount': 1000000, 'growth_rate': 10.5},
                    {'period': '2023-Q2', 'account_name': '主营业务收入', 'amount': 1200000, 'growth_rate': 20.0},
                    {'period': '2023-Q3', 'account_name': '主营业务收入', 'amount': 1100000, 'growth_rate': -8.3}
                ]

            elif 'sum' in sql_query.lower() or 'total' in sql_query.lower():
                return [
                    {'category': '流动资产', 'total_amount': 2000000, 'record_count': 150},
                    {'category': '固定资产', 'total_amount': 5000000, 'record_count': 80},
                    {'category': '无形资产', 'total_amount': 800000, 'record_count': 20}
                ]

            else:
                return [
                    {'id': 1, 'description': '查询结果示例', 'value': 1000},
                    {'id': 2, 'description': '数据分析结果', 'value': 2000}
                ]

        except Exception as e:
            self.logger.error(f"执行查询失败: {e}")
            return None

    async def _generate_response(self, user_input: str, data_results: Any, context: QueryContext) -> str:
        """生成回答"""
        try:
            if not data_results:
                return "抱歉，没有找到相关数据。请检查查询条件或尝试其他查询方式。"

            # 根据查询类型生成不同的回答
            if isinstance(data_results, list) and len(data_results) > 0:
                first_record = data_results[0]

                if 'balance' in first_record:
                    # 余额查询回答
                    total_balance = sum(record['balance'] for record in data_results)
                    response = f"查询到 {len(data_results)} 个账户的余额信息，总金额为 {total_balance:,.2f} 元。\n\n主要账户包括：\n"
                    for record in data_results[:5]:
                        response += f"- {record['account_name']}: {record['balance']:,.2f} 元\n"

                elif 'growth_rate' in first_record:
                    # 趋势分析回答
                    avg_growth = sum(record['growth_rate'] for record in data_results) / len(data_results)
                    response = f"趋势分析显示，平均增长率为 {avg_growth:.1f}%。\n\n具体趋势：\n"
                    for record in data_results:
                        direction = "增长" if record['growth_rate'] > 0 else "下降"
                        response += f"- {record['period']}: {record['account_name']} {direction} {abs(record['growth_rate']):.1f}%\n"

                elif 'total_amount' in first_record:
                    # 汇总统计回答
                    grand_total = sum(record['total_amount'] for record in data_results)
                    response = f"统计汇总结果显示，总金额为 {grand_total:,.2f} 元。\n\n分类统计：\n"
                    for record in data_results:
                        response += f"- {record['category']}: {record['total_amount']:,.2f} 元 ({record['record_count']} 条记录)\n"

                else:
                    # 通用回答
                    response = f"查询完成，共找到 {len(data_results)} 条记录。\n\n"
                    if len(data_results) <= 10:
                        for i, record in enumerate(data_results, 1):
                            response += f"{i}. {record}\n"
                    else:
                        response += "数据较多，显示前5条：\n"
                        for i, record in enumerate(data_results[:5], 1):
                            response += f"{i}. {record}\n"

                return response
            else:
                return "查询执行成功，但没有返回数据。"

        except Exception as e:
            self.logger.error(f"生成回答失败: {e}")
            return "抱歉，在生成回答时遇到了问题。"

    async def _generate_explanation(self, sql_query: str, data_results: Any) -> str:
        """生成解释"""
        try:
            explanation = "查询分析：\n"

            # 分析SQL查询
            if 'WHERE' in sql_query.upper():
                explanation += "- 应用了筛选条件进行精确查询\n"

            if 'GROUP BY' in sql_query.upper():
                explanation += "- 按分组进行了数据聚合\n"

            if 'ORDER BY' in sql_query.upper():
                explanation += "- 对结果进行了排序\n"

            if 'JOIN' in sql_query.upper():
                explanation += "- 关联了多个数据表\n"

            # 分析结果
            if data_results:
                explanation += f"- 查询返回了 {len(data_results)} 条记录\n"

                if isinstance(data_results, list) and len(data_results) > 0:
                    first_record = data_results[0]
                    explanation += f"- 数据包含 {len(first_record)} 个字段\n"

            return explanation

        except Exception as e:
            self.logger.error(f"生成解释失败: {e}")
            return "无法生成查询解释。"

    async def _generate_suggestions(self, user_input: str, context: QueryContext) -> List[str]:
        """生成建议"""
        try:
            suggestions = []

            # 基于查询内容的建议
            if '趋势' in user_input:
                suggestions.extend([
                    "可以尝试分析不同时间段的趋势对比",
                    "建议查看同比和环比变化情况",
                    "可以深入分析趋势变化的原因"
                ])

            if '异常' in user_input:
                suggestions.extend([
                    "建议设置不同的异常检测阈值",
                    "可以分析异常数据的业务背景",
                    "建议查看异常数据的分布情况"
                ])

            if '对比' in user_input:
                suggestions.extend([
                    "可以尝试多维度的对比分析",
                    "建议查看绝对数值和相对比例的变化",
                    "可以分析对比差异的驱动因素"
                ])

            # 通用建议
            if not suggestions:
                suggestions = [
                    "可以尝试更具体的查询条件",
                    "建议指定明确的时间范围",
                    "可以询问相关的财务指标分析"
                ]

            return suggestions[:3]  # 最多返回3个建议

        except Exception as e:
            self.logger.error(f"生成建议失败: {e}")
            return []

    async def _create_session(self, user_id: str) -> str:
        """创建会话"""
        try:
            session_id = f"session_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"

            with sqlite3.connect(self.agent_db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO conversation_sessions
                    (session_id, user_id, started_at, last_activity, is_active)
                    VALUES (?, ?, ?, ?, ?)
                ''', (
                    session_id,
                    user_id,
                    datetime.now().isoformat(),
                    datetime.now().isoformat(),
                    True
                ))
                conn.commit()

            with self._lock:
                self.active_conversations[session_id] = {
                    'user_id': user_id,
                    'started_at': datetime.now(),
                    'turns': []
                }

            return session_id

        except Exception as e:
            self.logger.error(f"创建会话失败: {e}")
            return f"session_{uuid.uuid4().hex[:8]}"

    async def _save_conversation_turn(self, session_id: str, user_input: str, result: Dict[str, Any]):
        """保存对话回合"""
        try:
            turn_id = f"turn_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"

            with sqlite3.connect(self.agent_db_path) as conn:
                cursor = conn.cursor()

                # 获取回合号
                cursor.execute('''
                    SELECT COUNT(*) FROM conversation_turns WHERE session_id = ?
                ''', (session_id,))
                turn_number = cursor.fetchone()[0] + 1

                # 保存回合
                cursor.execute('''
                    INSERT INTO conversation_turns
                    (turn_id, session_id, turn_number, user_input, agent_response,
                     query_context, query_result, timestamp)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    turn_id,
                    session_id,
                    turn_number,
                    user_input,
                    result.get('agent_response', ''),
                    json.dumps({}),  # 简化
                    json.dumps(result),
                    datetime.now().isoformat()
                ))

                # 更新会话活动时间
                cursor.execute('''
                    UPDATE conversation_sessions
                    SET last_activity = ?
                    WHERE session_id = ?
                ''', (datetime.now().isoformat(), session_id))

                conn.commit()

        except Exception as e:
            self.logger.error(f"保存对话回合失败: {e}")

    async def _get_session_history(self, session_id: str) -> List[str]:
        """获取会话历史"""
        try:
            with sqlite3.connect(self.agent_db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT user_input FROM conversation_turns
                    WHERE session_id = ?
                    ORDER BY turn_number DESC
                    LIMIT 5
                ''', (session_id,))

                return [row[0] for row in cursor.fetchall()]

        except Exception as e:
            self.logger.error(f"获取会话历史失败: {e}")
            return []

    async def __aenter__(self):
        """异步上下文管理器入口"""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """异步上下文管理器出口"""
        await self.cleanup()

    async def cleanup(self):
        """清理资源"""
        try:
            if hasattr(self, 'executor'):
                self.executor.shutdown(wait=True)

            self.logger.info("自然语言审计智能体资源清理完成")

        except Exception as e:
            self.logger.error(f"资源清理失败: {e}")


async def main():
    """测试主函数"""
    config = {
        'agent_db_path': 'data/test_nl_audit_agent.db',
        'llm_provider': 'local'
    }

    async with NLAuditAgent(config) as agent:
        # 测试查询
        test_queries = [
            "查询2023年主营业务收入的情况",
            "分析应收账款的趋势变化",
            "统计各类资产的总金额",
            "找出金额异常的交易记录",
            "对比今年和去年的利润情况"
        ]

        for query in test_queries:
            print(f"\n用户查询: {query}")
            result = await agent.process_query(query)
            print(f"智能体回答: {result['agent_response']}")
            if result['sql_generated']:
                print(f"生成SQL: {result['sql_generated']}")
            print(f"置信度: {result['confidence']:.2f}")
            print("-" * 50)


if __name__ == "__main__":
    asyncio.run(main())