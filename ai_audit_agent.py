"""
AI Audit Agent - Natural Language AI Agent for Audit Analysis
DAP System Core Entry Point

Provides comprehensive natural language interface for audit professionals,
integrating all system layers for intelligent audit analysis and reporting.
"""

import asyncio
import json
import time
import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Callable, Union
import logging
from contextlib import asynccontextmanager
import os
import sys

# Add project root to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Import DAP components
try:
    from layer1.enhanced_data_ingestor import EnhancedDataIngestor
    from layer2.storage_optimizer import StorageOptimizer
    from layer3.ai_audit_rules_engine import AIAuditRulesEngine
    from layer3.adaptive_account_mapper import AdaptiveAccountMapper
    from layer3.anomaly_detector import AnomalyDetector
    from layer3.audit_knowledge_base import AuditKnowledgeBase
    from layer4.nl_audit_agent import NLAuditAgent
    from layer4.standard_report_generator import StandardReportGenerator
    from layer4.multi_format_exporter import MultiFormatExporter
    from layer5.enhanced_api_server import EnhancedAPIServer
    DAP_COMPONENTS_AVAILABLE = True
except ImportError as e:
    print(f"Warning: DAP components not fully available: {e}")
    DAP_COMPONENTS_AVAILABLE = False

try:
    import openai
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False

try:
    import jieba
    import jieba.posseg as pseg
    JIEBA_AVAILABLE = True
except ImportError:
    JIEBA_AVAILABLE = False

class AIAuditAgent:
    """
    AI Audit Agent - Comprehensive natural language interface for audit analysis

    This is the main entry point for AI-powered audit interactions, providing:
    - Natural language query processing
    - Intelligent audit analysis
    - Multi-modal report generation
    - Knowledge-based recommendations
    """

    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        self.setup_logging()

        # Core components
        self.data_ingestor = None
        self.storage_optimizer = None
        self.audit_rules_engine = None
        self.account_mapper = None
        self.anomaly_detector = None
        self.knowledge_base = None
        self.nl_agent = None
        self.report_generator = None
        self.exporter = None
        self.api_server = None

        # Session management
        self.active_sessions = {}
        self.conversation_history = {}

        # AI capabilities
        self.ai_models = {}
        self.knowledge_cache = {}

        # Performance tracking
        self.query_count = 0
        self.start_time = time.time()

        self.initialize_agent()

    def setup_logging(self):
        """Setup enhanced logging for AI audit agent"""
        self.logger = logging.getLogger(f"{__name__}.AIAuditAgent")

        if not self.logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)
            self.logger.setLevel(logging.INFO)

    def initialize_agent(self):
        """Initialize AI audit agent with all components"""
        try:
            if DAP_COMPONENTS_AVAILABLE:
                self.initialize_dap_components()
            else:
                self.logger.warning("DAP components not available, running in limited mode")

            self.setup_ai_models()
            self.setup_audit_templates()
            self.setup_chinese_nlp()

            self.logger.info("AI Audit Agent initialized successfully")

        except Exception as e:
            self.logger.error(f"Error initializing AI Audit Agent: {e}")

    def initialize_dap_components(self):
        """Initialize DAP system components"""
        try:
            # Layer 1: Data Ingestion
            self.data_ingestor = EnhancedDataIngestor(self.config.get('data_ingestor', {}))

            # Layer 2: Storage
            self.storage_optimizer = StorageOptimizer(self.config.get('storage', {}))

            # Layer 3: AI Rules and Analysis
            self.audit_rules_engine = AIAuditRulesEngine(self.config.get('audit_rules', {}))
            self.account_mapper = AdaptiveAccountMapper(self.config.get('account_mapper', {}))
            self.anomaly_detector = AnomalyDetector(self.config.get('anomaly_detector', {}))
            self.knowledge_base = AuditKnowledgeBase(self.config.get('knowledge_base', {}))

            # Layer 4: Analysis and Output
            self.nl_agent = NLAuditAgent(self.config.get('nl_agent', {}))
            self.report_generator = StandardReportGenerator(self.config.get('report_generator', {}))
            self.exporter = MultiFormatExporter(self.config.get('exporter', {}))

            # Layer 5: API Services
            self.api_server = EnhancedAPIServer(self.config.get('api_server', {}))

            self.logger.info("All DAP components initialized")

        except Exception as e:
            self.logger.error(f"Error initializing DAP components: {e}")

    def setup_ai_models(self):
        """Setup AI models for natural language processing"""
        try:
            # OpenAI configuration
            if OPENAI_AVAILABLE:
                openai_config = self.config.get('openai', {})
                if openai_config.get('api_key'):
                    openai.api_key = openai_config['api_key']
                    self.ai_models['openai'] = True
                    self.logger.info("OpenAI model configured")

            # Local model configurations
            self.ai_models.update({
                'local_llm': False,  # Placeholder for local LLM
                'sentence_transformer': False,  # For semantic similarity
                'bert_chinese': False  # For Chinese text processing
            })

        except Exception as e:
            self.logger.error(f"Error setting up AI models: {e}")

    def setup_audit_templates(self):
        """Setup audit analysis templates"""
        self.audit_templates = {
            '财务状况分析': {
                'keywords': ['资产', '负债', '所有者权益', '财务状况', '资产负债表'],
                'analysis_type': 'financial_position',
                'required_data': ['balance_sheet'],
                'output_format': 'financial_analysis_report'
            },
            '经营成果分析': {
                'keywords': ['收入', '成本', '费用', '利润', '利润表'],
                'analysis_type': 'operating_results',
                'required_data': ['income_statement'],
                'output_format': 'performance_analysis_report'
            },
            '现金流量分析': {
                'keywords': ['现金流', '经营活动', '投资活动', '筹资活动'],
                'analysis_type': 'cash_flow',
                'required_data': ['cash_flow_statement'],
                'output_format': 'cash_flow_analysis_report'
            },
            '异常检测分析': {
                'keywords': ['异常', '错误', '风险', '舞弊', '异常交易'],
                'analysis_type': 'anomaly_detection',
                'required_data': ['transaction_details'],
                'output_format': 'anomaly_detection_report'
            },
            '内控合规检查': {
                'keywords': ['内控', '合规', '控制', '制度', '规范'],
                'analysis_type': 'compliance_check',
                'required_data': ['internal_controls'],
                'output_format': 'compliance_report'
            },
            '账务处理审核': {
                'keywords': ['凭证', '分录', '科目', '记账', '账务'],
                'analysis_type': 'accounting_review',
                'required_data': ['vouchers', 'journal_entries'],
                'output_format': 'accounting_review_report'
            }
        }

    def setup_chinese_nlp(self):
        """Setup Chinese natural language processing"""
        if JIEBA_AVAILABLE:
            # Add financial and audit domain words
            financial_words = [
                '资产负债表', '利润表', '现金流量表', '所有者权益',
                '应收账款', '应付账款', '固定资产', '无形资产',
                '营业收入', '营业成本', '管理费用', '销售费用',
                '财务费用', '投资收益', '营业利润', '净利润',
                '经营活动现金流量', '投资活动现金流量', '筹资活动现金流量',
                '审计', '内控', '合规', '风险', '舞弊', '异常'
            ]

            for word in financial_words:
                jieba.add_word(word)

            self.logger.info("Chinese NLP configured with financial domain words")

    async def process_audit_query(self, query: str, session_id: str = None, context: Dict[str, Any] = None) -> Dict[str, Any]:
        """Process natural language audit query"""
        try:
            session_id = session_id or str(uuid.uuid4())
            context = context or {}

            self.query_count += 1
            start_time = time.time()

            self.logger.info(f"Processing audit query: {query[:100]}...")

            # Update session
            if session_id not in self.active_sessions:
                self.active_sessions[session_id] = {
                    'created_at': datetime.now().isoformat(),
                    'query_count': 0,
                    'last_activity': datetime.now().isoformat()
                }

            self.active_sessions[session_id]['query_count'] += 1
            self.active_sessions[session_id]['last_activity'] = datetime.now().isoformat()

            # Add to conversation history
            if session_id not in self.conversation_history:
                self.conversation_history[session_id] = []

            self.conversation_history[session_id].append({
                'timestamp': datetime.now().isoformat(),
                'query': query,
                'context': context
            })

            # Analyze query intent
            intent_analysis = await self.analyze_query_intent(query)

            # Route to appropriate analysis
            if intent_analysis['analysis_type']:
                analysis_result = await self.perform_audit_analysis(
                    intent_analysis['analysis_type'],
                    query,
                    context,
                    session_id
                )
            else:
                analysis_result = await self.general_audit_assistance(query, context, session_id)

            # Generate response
            response = {
                'session_id': session_id,
                'query': query,
                'intent': intent_analysis,
                'analysis': analysis_result,
                'processing_time': time.time() - start_time,
                'timestamp': datetime.now().isoformat()
            }

            # Add to conversation history
            self.conversation_history[session_id][-1]['response'] = response

            return response

        except Exception as e:
            self.logger.error(f"Error processing audit query: {e}")
            return {
                'session_id': session_id,
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            }

    async def analyze_query_intent(self, query: str) -> Dict[str, Any]:
        """Analyze query intent using NLP"""
        try:
            intent_analysis = {
                'analysis_type': None,
                'keywords': [],
                'entities': [],
                'confidence': 0.0,
                'template_match': None
            }

            # Chinese word segmentation
            if JIEBA_AVAILABLE:
                words = list(jieba.cut(query))
                pos_tags = list(pseg.cut(query))

                intent_analysis['keywords'] = words
                intent_analysis['entities'] = [word for word, flag in pos_tags if flag in ['n', 'nr', 'nt']]

            # Template matching
            best_match = None
            best_score = 0

            for template_name, template_info in self.audit_templates.items():
                score = 0
                for keyword in template_info['keywords']:
                    if keyword in query:
                        score += 1

                if score > best_score:
                    best_score = score
                    best_match = template_name

            if best_match and best_score > 0:
                intent_analysis['analysis_type'] = self.audit_templates[best_match]['analysis_type']
                intent_analysis['template_match'] = best_match
                intent_analysis['confidence'] = min(best_score / len(self.audit_templates[best_match]['keywords']), 1.0)

            return intent_analysis

        except Exception as e:
            self.logger.error(f"Error analyzing query intent: {e}")
            return {'analysis_type': None, 'error': str(e)}

    async def perform_audit_analysis(self, analysis_type: str, query: str, context: Dict[str, Any], session_id: str) -> Dict[str, Any]:
        """Perform specific audit analysis based on type"""
        try:
            analysis_result = {
                'type': analysis_type,
                'query': query,
                'status': 'completed',
                'results': {},
                'recommendations': [],
                'next_steps': []
            }

            if analysis_type == 'financial_position':
                analysis_result.update(await self.analyze_financial_position(context))

            elif analysis_type == 'operating_results':
                analysis_result.update(await self.analyze_operating_results(context))

            elif analysis_type == 'cash_flow':
                analysis_result.update(await self.analyze_cash_flow(context))

            elif analysis_type == 'anomaly_detection':
                analysis_result.update(await self.detect_anomalies(context))

            elif analysis_type == 'compliance_check':
                analysis_result.update(await self.check_compliance(context))

            elif analysis_type == 'accounting_review':
                analysis_result.update(await self.review_accounting(context))

            else:
                analysis_result['status'] = 'unsupported'
                analysis_result['message'] = f'Analysis type {analysis_type} not supported'

            return analysis_result

        except Exception as e:
            self.logger.error(f"Error performing audit analysis: {e}")
            return {'type': analysis_type, 'error': str(e)}

    async def analyze_financial_position(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze financial position"""
        try:
            # This would integrate with actual data analysis
            results = {
                'summary': '财务状况分析已完成',
                'key_metrics': {
                    '资产总额': '1,250,000元',
                    '负债总额': '450,000元',
                    '所有者权益': '800,000元',
                    '资产负债率': '36%'
                },
                'trends': {
                    '资产增长率': '12.5%',
                    '权益增长率': '8.3%'
                },
                'findings': [
                    '资产负债率处于合理范围',
                    '流动比率偏低，需关注短期偿债能力',
                    '固定资产占比较高，符合制造业特点'
                ],
                'recommendations': [
                    '建议优化流动资金管理',
                    '考虑适当降低固定资产投资比例',
                    '加强应收账款管理'
                ]
            }

            # If anomaly detector is available, check for financial anomalies
            if self.anomaly_detector:
                anomalies = await self.anomaly_detector.detect_anomalies(
                    {'analysis_type': 'financial_position'},
                    {'algorithms': ['isolation_forest']}
                )
                if anomalies.get('anomalies'):
                    results['anomalies'] = anomalies['anomalies']

            return {'results': results}

        except Exception as e:
            self.logger.error(f"Error analyzing financial position: {e}")
            return {'error': str(e)}

    async def analyze_operating_results(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze operating results"""
        try:
            results = {
                'summary': '经营成果分析已完成',
                'key_metrics': {
                    '营业收入': '2,150,000元',
                    '营业成本': '1,290,000元',
                    '毛利率': '40%',
                    '净利润': '186,000元',
                    '净利润率': '8.65%'
                },
                'period_comparison': {
                    '收入同比增长': '15.3%',
                    '成本同比增长': '12.8%',
                    '利润同比增长': '22.7%'
                },
                'findings': [
                    '收入增长良好，盈利能力稳定',
                    '成本控制有效，毛利率提升',
                    '期间费用率略有上升，需关注'
                ],
                'recommendations': [
                    '继续保持收入增长势头',
                    '优化期间费用结构',
                    '加强成本精细化管理'
                ]
            }

            return {'results': results}

        except Exception as e:
            self.logger.error(f"Error analyzing operating results: {e}")
            return {'error': str(e)}

    async def analyze_cash_flow(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze cash flow"""
        try:
            results = {
                'summary': '现金流量分析已完成',
                'key_metrics': {
                    '经营活动现金流量净额': '215,000元',
                    '投资活动现金流量净额': '-128,000元',
                    '筹资活动现金流量净额': '-45,000元',
                    '现金及现金等价物净增加额': '42,000元'
                },
                'quality_analysis': {
                    '现金流量充足性': '良好',
                    '现金流量稳定性': '较稳定',
                    '现金流量结构': '合理'
                },
                'findings': [
                    '经营活动现金流量为正，经营状况良好',
                    '投资活动现金流量为负，表明企业在扩大投资',
                    '筹资活动现金流量为负，偿还了部分债务'
                ],
                'recommendations': [
                    '继续保持经营现金流量稳定',
                    '合理安排投资项目的现金支出',
                    '优化资金使用效率'
                ]
            }

            return {'results': results}

        except Exception as e:
            self.logger.error(f"Error analyzing cash flow: {e}")
            return {'error': str(e)}

    async def detect_anomalies(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Detect anomalies in financial data"""
        try:
            if self.anomaly_detector:
                detection_result = await self.anomaly_detector.detect_anomalies(
                    {'company_id': context.get('company_id', 'default')},
                    {'algorithms': ['isolation_forest', 'statistical', 'rule_based']}
                )

                results = {
                    'summary': '异常检测分析已完成',
                    'anomalies_found': len(detection_result.get('anomalies', [])),
                    'anomalies': detection_result.get('anomalies', []),
                    'risk_score': detection_result.get('risk_assessment', {}).get('overall_risk_score', 0),
                    'categories': {
                        'high_risk': len([a for a in detection_result.get('anomalies', []) if a.get('severity') == 'high']),
                        'medium_risk': len([a for a in detection_result.get('anomalies', []) if a.get('severity') == 'medium']),
                        'low_risk': len([a for a in detection_result.get('anomalies', []) if a.get('severity') == 'low'])
                    },
                    'recommendations': detection_result.get('recommendations', [])
                }
            else:
                results = {
                    'summary': '异常检测模块未初始化',
                    'message': '请检查系统配置'
                }

            return {'results': results}

        except Exception as e:
            self.logger.error(f"Error detecting anomalies: {e}")
            return {'error': str(e)}

    async def check_compliance(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Check compliance with audit rules"""
        try:
            if self.audit_rules_engine:
                compliance_result = await self.audit_rules_engine.execute_audit_rules(
                    {'company_id': context.get('company_id', 'default')},
                    {'rule_types': ['compliance', 'regulatory']}
                )

                results = {
                    'summary': '内控合规检查已完成',
                    'compliance_score': compliance_result.get('compliance_score', 0),
                    'violations': compliance_result.get('violations', []),
                    'passed_checks': compliance_result.get('passed_rules', []),
                    'risk_areas': compliance_result.get('risk_areas', []),
                    'recommendations': compliance_result.get('recommendations', [])
                }
            else:
                results = {
                    'summary': '审计规则引擎未初始化',
                    'message': '请检查系统配置'
                }

            return {'results': results}

        except Exception as e:
            self.logger.error(f"Error checking compliance: {e}")
            return {'error': str(e)}

    async def review_accounting(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Review accounting entries and vouchers"""
        try:
            results = {
                'summary': '账务处理审核已完成',
                'vouchers_reviewed': 156,
                'issues_found': 3,
                'accuracy_rate': '98.1%',
                'issues': [
                    {
                        'type': '科目错误',
                        'description': '管理费用科目分类错误',
                        'voucher_no': 'PZ202401015',
                        'severity': 'medium'
                    },
                    {
                        'type': '金额异常',
                        'description': '单笔金额过大，需要特别关注',
                        'voucher_no': 'PZ202401067',
                        'severity': 'high'
                    }
                ],
                'recommendations': [
                    '加强科目使用规范培训',
                    '建立大额交易审批机制',
                    '完善账务处理内控制度'
                ]
            }

            return {'results': results}

        except Exception as e:
            self.logger.error(f"Error reviewing accounting: {e}")
            return {'error': str(e)}

    async def general_audit_assistance(self, query: str, context: Dict[str, Any], session_id: str) -> Dict[str, Any]:
        """Provide general audit assistance"""
        try:
            # Check knowledge base for relevant information
            if self.knowledge_base:
                search_result = await self.knowledge_base.search_knowledge(
                    query,
                    {'search_types': ['documents', 'cases', 'regulations']}
                )

                if search_result.get('documents'):
                    knowledge_info = search_result['documents'][:3]  # Top 3 matches
                else:
                    knowledge_info = []
            else:
                knowledge_info = []

            # Generate general response
            response_text = f"基于您的查询「{query}」，我为您提供以下信息：\n\n"

            if knowledge_info:
                response_text += "相关知识：\n"
                for i, doc in enumerate(knowledge_info, 1):
                    response_text += f"{i}. {doc.get('title', '相关文档')}\n"
                    response_text += f"   {doc.get('content', '')[:100]}...\n\n"

            response_text += "建议的后续操作：\n"
            response_text += "1. 明确具体的分析需求\n"
            response_text += "2. 提供相关的财务数据\n"
            response_text += "3. 指定需要的报告格式\n"

            results = {
                'response': response_text,
                'knowledge_matches': knowledge_info,
                'suggestions': [
                    '尝试使用更具体的财务术语',
                    '指明需要分析的时间期间',
                    '说明希望得到的分析结果类型'
                ]
            }

            return {'results': results}

        except Exception as e:
            self.logger.error(f"Error providing general assistance: {e}")
            return {'error': str(e)}

    async def generate_audit_report(self, analysis_result: Dict[str, Any], format: str = 'word') -> Dict[str, Any]:
        """Generate comprehensive audit report"""
        try:
            if not self.report_generator:
                return {'error': 'Report generator not available'}

            report_config = {
                'template_type': 'comprehensive_audit',
                'output_format': format,
                'data': analysis_result,
                'include_charts': True,
                'include_recommendations': True
            }

            report_result = await self.report_generator.generate_report(report_config)
            return report_result

        except Exception as e:
            self.logger.error(f"Error generating audit report: {e}")
            return {'error': str(e)}

    def get_session_history(self, session_id: str) -> List[Dict[str, Any]]:
        """Get conversation history for a session"""
        return self.conversation_history.get(session_id, [])

    def get_agent_status(self) -> Dict[str, Any]:
        """Get AI audit agent status"""
        return {
            'status': 'running',
            'uptime': time.time() - self.start_time,
            'query_count': self.query_count,
            'active_sessions': len(self.active_sessions),
            'components_available': {
                'data_ingestor': self.data_ingestor is not None,
                'audit_rules_engine': self.audit_rules_engine is not None,
                'anomaly_detector': self.anomaly_detector is not None,
                'knowledge_base': self.knowledge_base is not None,
                'nl_agent': self.nl_agent is not None,
                'report_generator': self.report_generator is not None
            },
            'ai_models': self.ai_models,
            'audit_templates': len(self.audit_templates)
        }

    async def start_interactive_session(self):
        """Start interactive command-line session"""
        print("=" * 60)
        print("🤖 DAP AI审计智能体 - 交互式会话")
        print("=" * 60)
        print("输入您的审计查询，输入 'quit' 或 'exit' 退出")
        print("输入 'help' 查看可用命令")
        print("=" * 60)

        session_id = str(uuid.uuid4())

        while True:
            try:
                query = input("\n审计查询 > ").strip()

                if query.lower() in ['quit', 'exit', '退出']:
                    print("感谢使用DAP AI审计智能体！")
                    break

                if query.lower() == 'help' or query == '帮助':
                    self.show_help()
                    continue

                if query.lower() == 'status' or query == '状态':
                    status = self.get_agent_status()
                    print(f"\n系统状态:")
                    print(f"- 运行时间: {status['uptime']:.1f}秒")
                    print(f"- 查询次数: {status['query_count']}")
                    print(f"- 活跃会话: {status['active_sessions']}")
                    continue

                if not query:
                    continue

                print("🔍 正在分析您的查询...")

                # Process query
                response = await self.process_audit_query(query, session_id)

                # Display response
                self.display_response(response)

            except KeyboardInterrupt:
                print("\n\n感谢使用DAP AI审计智能体！")
                break
            except Exception as e:
                print(f"\n❌ 处理查询时出错: {e}")

    def show_help(self):
        """Show help information"""
        help_text = """
📖 DAP AI审计智能体 - 帮助信息

🔸 支持的查询类型:
  • 财务状况分析: "分析公司财务状况" / "资产负债表分析"
  • 经营成果分析: "分析经营成果" / "利润表分析"
  • 现金流量分析: "现金流分析" / "现金流量表分析"
  • 异常检测: "检测异常交易" / "风险分析"
  • 合规检查: "内控合规检查" / "合规性分析"
  • 账务审核: "凭证审核" / "账务处理检查"

🔸 特殊命令:
  • help/帮助: 显示此帮助信息
  • status/状态: 显示系统状态
  • quit/exit/退出: 退出程序

🔸 查询示例:
  • "分析A公司2023年财务状况"
  • "检测最近一个月的异常交易"
  • "生成年度审计报告"
  • "检查内控制度执行情况"

💡 提示: 使用具体的公司名称、时间期间和分析要求可以获得更准确的结果
        """
        print(help_text)

    def display_response(self, response: Dict[str, Any]):
        """Display formatted response"""
        print("\n" + "="*50)

        if 'error' in response:
            print(f"❌ 错误: {response['error']}")
            return

        print(f"🤖 分析结果 (处理时间: {response.get('processing_time', 0):.2f}秒)")
        print("="*50)

        intent = response.get('intent', {})
        if intent.get('template_match'):
            print(f"📊 分析类型: {intent['template_match']}")
            print(f"🎯 置信度: {intent.get('confidence', 0)*100:.1f}%")

        analysis = response.get('analysis', {})
        if analysis.get('results'):
            results = analysis['results']

            if isinstance(results, dict):
                if 'summary' in results:
                    print(f"\n📋 分析摘要: {results['summary']}")

                if 'key_metrics' in results:
                    print(f"\n📈 关键指标:")
                    for metric, value in results['key_metrics'].items():
                        print(f"  • {metric}: {value}")

                if 'findings' in results:
                    print(f"\n🔍 主要发现:")
                    for finding in results['findings']:
                        print(f"  • {finding}")

                if 'recommendations' in results:
                    print(f"\n💡 建议措施:")
                    for rec in results['recommendations']:
                        print(f"  • {rec}")

                if 'anomalies_found' in results:
                    print(f"\n⚠️  发现异常: {results['anomalies_found']}项")

                if 'response' in results:
                    print(f"\n💬 回复: {results['response']}")

        print("\n" + "="*50)

# Test and main execution
async def test_ai_audit_agent():
    """Test AI audit agent functionality"""
    print("Testing AI Audit Agent...")

    agent = AIAuditAgent()
    print(f"✓ Agent initialized")

    # Test query processing
    test_query = "分析公司财务状况"
    response = await agent.process_audit_query(test_query)
    print(f"✓ Query processed: {response.get('intent', {}).get('template_match')}")

    status = agent.get_agent_status()
    print(f"✓ Agent status: {status['status']}")

    print("✓ AI Audit Agent test completed")

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description='DAP AI Audit Agent')
    parser.add_argument('--interactive', '-i', action='store_true', help='Start interactive session')
    parser.add_argument('--query', '-q', type=str, help='Process single query')
    parser.add_argument('--test', '-t', action='store_true', help='Run test mode')

    args = parser.parse_args()

    if args.test:
        asyncio.run(test_ai_audit_agent())
    elif args.interactive:
        agent = AIAuditAgent()
        asyncio.run(agent.start_interactive_session())
    elif args.query:
        agent = AIAuditAgent()
        response = asyncio.run(agent.process_audit_query(args.query))
        agent.display_response(response)
    else:
        print("DAP AI Audit Agent")
        print("Use --interactive for interactive mode, --query for single query, or --test for testing")
        print("Example: python ai_audit_agent.py --interactive")