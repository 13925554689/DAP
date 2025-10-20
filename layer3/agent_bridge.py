"""
DAP - 智能体通信桥
与外部AI智能体的通信接口
"""

import json
import requests
import pandas as pd
from typing import Dict, Any, List, Optional, Union
import logging
from datetime import datetime
import sqlite3
import os
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)

class AIClient(ABC):
    """AI客户端抽象基类"""
    
    @abstractmethod
    def analyze(self, prompt: str, data: Any = None) -> Dict[str, Any]:
        """分析数据"""
        pass
    
    @abstractmethod
    def is_available(self) -> bool:
        """检查是否可用"""
        pass

class OpenAIClient(AIClient):
    """OpenAI客户端"""
    
    def __init__(self, api_key: str, model: str = "gpt-3.5-turbo", base_url: str = None):
        self.api_key = api_key
        self.model = model
        self.base_url = base_url or "https://api.openai.com/v1"
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
    
    def analyze(self, prompt: str, data: Any = None) -> Dict[str, Any]:
        """使用OpenAI进行分析"""
        try:
            # 构建消息
            messages = [
                {
                    "role": "system",
                    "content": """你是一个专业的财务审计分析助手。请基于提供的财务数据，
                    进行专业的审计分析，识别潜在的风险点和异常情况。
                    
                    分析要求：
                    1. 数据完整性检查
                    2. 异常交易识别
                    3. 财务指标分析
                    4. 风险点评估
                    5. 审计建议
                    
                    请提供结构化的分析结果。"""
                },
                {
                    "role": "user",
                    "content": self._build_analysis_prompt(prompt, data)
                }
            ]
            
            # 调用API
            response = requests.post(
                f"{self.base_url}/chat/completions",
                headers=self.headers,
                json={
                    "model": self.model,
                    "messages": messages,
                    "max_tokens": 2000,
                    "temperature": 0.7
                },
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                content = result["choices"][0]["message"]["content"]
                
                return {
                    "success": True,
                    "analysis": content,
                    "model": self.model,
                    "tokens_used": result.get("usage", {}).get("total_tokens", 0)
                }
            else:
                return {
                    "success": False,
                    "error": f"API调用失败: {response.status_code} - {response.text}"
                }
                
        except Exception as e:
            return {
                "success": False,
                "error": f"OpenAI分析失败: {str(e)}"
            }
    
    def is_available(self) -> bool:
        """检查OpenAI API是否可用"""
        try:
            response = requests.get(
                f"{self.base_url}/models",
                headers=self.headers,
                timeout=10
            )
            return response.status_code == 200
        except:
            return False
    
    def _build_analysis_prompt(self, user_prompt: str, data: Any) -> str:
        """构建分析提示词"""
        prompt_parts = [user_prompt]
        
        if data is not None:
            if isinstance(data, pd.DataFrame):
                # 处理DataFrame数据
                data_summary = self._summarize_dataframe(data)
                prompt_parts.append(f"\n数据摘要：\n{data_summary}")
            elif isinstance(data, dict):
                # 处理字典数据
                prompt_parts.append(f"\n数据内容：\n{json.dumps(data, ensure_ascii=False, indent=2)}")
            else:
                prompt_parts.append(f"\n数据：\n{str(data)}")
        
        return "\n".join(prompt_parts)
    
    def _summarize_dataframe(self, df: pd.DataFrame) -> str:
        """汇总DataFrame信息"""
        summary_parts = [
            f"数据形状: {df.shape[0]}行 x {df.shape[1]}列",
            f"列名: {', '.join(df.columns.tolist())}",
        ]
        
        # 数值列统计
        numeric_cols = df.select_dtypes(include=['number']).columns
        if not numeric_cols.empty:
            numeric_summary = df[numeric_cols].describe()
            summary_parts.append(f"数值列统计:\n{numeric_summary.to_string()}")
        
        # 分类列信息
        categorical_cols = df.select_dtypes(include=['object']).columns
        if not categorical_cols.empty:
            cat_info = []
            for col in categorical_cols[:3]:  # 最多显示3个分类列
                unique_count = df[col].nunique()
                cat_info.append(f"{col}: {unique_count}个唯一值")
            summary_parts.append(f"分类列信息: {', '.join(cat_info)}")
        
        # 样本数据
        if len(df) > 0:
            sample_data = df.head(3).to_dict('records')
            summary_parts.append(f"样本数据（前3行）:\n{json.dumps(sample_data, ensure_ascii=False, indent=2)}")
        
        return "\n".join(summary_parts)

class LocalLLMClient(AIClient):
    """本地大语言模型客户端"""
    
    def __init__(self, base_url: str = "http://localhost:11434", model: str = "llama2"):
        self.base_url = base_url
        self.model = model
    
    def analyze(self, prompt: str, data: Any = None) -> Dict[str, Any]:
        """使用本地LLM进行分析"""
        try:
            # 构建完整提示词
            full_prompt = self._build_analysis_prompt(prompt, data)
            
            # 调用本地API（例如Ollama）
            response = requests.post(
                f"{self.base_url}/api/generate",
                json={
                    "model": self.model,
                    "prompt": full_prompt,
                    "stream": False
                },
                timeout=60
            )
            
            if response.status_code == 200:
                result = response.json()
                
                return {
                    "success": True,
                    "analysis": result.get("response", ""),
                    "model": self.model,
                    "local": True
                }
            else:
                return {
                    "success": False,
                    "error": f"本地LLM调用失败: {response.status_code}"
                }
                
        except Exception as e:
            return {
                "success": False,
                "error": f"本地LLM分析失败: {str(e)}"
            }
    
    def is_available(self) -> bool:
        """检查本地LLM是否可用"""
        try:
            response = requests.get(f"{self.base_url}/api/tags", timeout=5)
            return response.status_code == 200
        except:
            return False
    
    def _build_analysis_prompt(self, user_prompt: str, data: Any) -> str:
        """构建分析提示词"""
        system_prompt = """
        你是一个专业的财务数据分析师。请根据提供的数据进行详细分析，
        重点关注以下方面：
        1. 数据质量问题
        2. 异常模式识别
        3. 财务风险评估
        4. 改进建议
        
        请提供简洁而专业的分析结果。
        """
        
        prompt_parts = [system_prompt, user_prompt]
        
        if data is not None:
            data_str = self._format_data_for_prompt(data)
            prompt_parts.append(f"数据内容：\n{data_str}")
        
        return "\n\n".join(prompt_parts)
    
    def _format_data_for_prompt(self, data: Any) -> str:
        """格式化数据用于提示词"""
        if isinstance(data, pd.DataFrame):
            # 简化DataFrame表示
            return f"数据表格（{data.shape[0]}行x{data.shape[1]}列）:\n{data.head().to_string()}"
        elif isinstance(data, dict):
            return json.dumps(data, ensure_ascii=False, indent=2)
        else:
            return str(data)

class MockAIClient(AIClient):
    """模拟AI客户端（用于测试）"""
    
    def __init__(self):
        self.call_count = 0
    
    def analyze(self, prompt: str, data: Any = None) -> Dict[str, Any]:
        """模拟AI分析"""
        self.call_count += 1
        
        # 根据提示词内容生成不同的模拟响应
        if "风险" in prompt or "risk" in prompt.lower():
            analysis = """
            基于数据分析，发现以下风险点：
            1. 高风险交易：检测到5笔异常大额交易，建议重点关注
            2. 数据完整性：约2%的记录存在空值，需要补充
            3. 时间异常：发现3笔周末交易，可能存在内控问题
            
            建议：
            - 加强大额交易审批流程
            - 完善数据录入验证
            - 审查非工作时间交易权限
            """
        elif "财务" in prompt or "financial" in prompt.lower():
            analysis = """
            财务数据分析结果：
            1. 收入趋势：总体呈上升趋势，增长率12%
            2. 成本控制：成本率稳定在65%左右
            3. 现金流：经营性现金流为正，财务状况良好
            4. 盈利能力：净利润率8.5%，处于行业平均水平
            
            关注点：
            - 应收账款周转率略低，需关注回款情况
            - 库存周转率有所下降，建议优化库存管理
            """
        else:
            analysis = """
            数据分析完成，主要发现：
            1. 数据质量总体良好，完整性达到98%
            2. 未发现明显的异常模式
            3. 数据分布符合预期
            
            建议：
            - 继续保持当前的数据管理水平
            - 定期进行数据质量检查
            """
        
        return {
            "success": True,
            "analysis": analysis,
            "model": "mock-ai",
            "call_count": self.call_count
        }
    
    def is_available(self) -> bool:
        """模拟客户端总是可用"""
        return True

class AgentBridge:
    """外部智能体通信桥"""
    
    def __init__(self, db_path: str = 'data/dap_data.db'):
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        
        # 初始化AI客户端
        self.ai_clients = {}
        self._init_ai_clients()
        
        # 分析历史
        self.analysis_history = []
        
        logger.info("智能体通信桥初始化完成")
    
    def _init_ai_clients(self):
        """初始化AI客户端"""
        # OpenAI客户端（需要API密钥）
        openai_api_key = os.getenv('OPENAI_API_KEY')
        if openai_api_key:
            self.ai_clients['openai'] = OpenAIClient(openai_api_key)
            logger.info("OpenAI客户端已配置")
        
        # 本地LLM客户端
        self.ai_clients['local_llm'] = LocalLLMClient()
        
        # 模拟客户端（总是可用，用于测试）
        self.ai_clients['mock'] = MockAIClient()
        
        logger.info(f"AI客户端初始化完成，可用客户端: {list(self.ai_clients.keys())}")
    
    def get_available_clients(self) -> List[str]:
        """获取可用的AI客户端"""
        available = []
        for name, client in self.ai_clients.items():
            if client.is_available():
                available.append(name)
        return available
    
    def call_ai_analysis(self, prompt: str, data: Any = None, 
                        model: str = 'auto') -> Dict[str, Any]:
        """调用AI进行数据分析"""
        try:
            # 选择AI客户端
            if model == 'auto':
                # 自动选择可用的客户端
                available_clients = self.get_available_clients()
                if not available_clients:
                    return {
                        "success": False,
                        "error": "没有可用的AI客户端"
                    }
                
                # 优先级：OpenAI > Local LLM > Mock
                if 'openai' in available_clients:
                    selected_client = 'openai'
                elif 'local_llm' in available_clients:
                    selected_client = 'local_llm'
                else:
                    selected_client = available_clients[0]
            else:
                selected_client = model
            
            if selected_client not in self.ai_clients:
                return {
                    "success": False,
                    "error": f"未知的AI客户端: {selected_client}"
                }
            
            client = self.ai_clients[selected_client]
            
            if not client.is_available():
                return {
                    "success": False,
                    "error": f"AI客户端不可用: {selected_client}"
                }
            
            # 预处理数据
            processed_data = self._prepare_data_for_ai(data)
            
            # 调用AI分析
            logger.info(f"使用 {selected_client} 进行AI分析")
            result = client.analyze(prompt, processed_data)
            
            # 添加元信息
            result['client'] = selected_client
            result['timestamp'] = datetime.now().isoformat()
            
            # 保存分析历史
            self._save_analysis_history(prompt, selected_client, result)
            
            return result
            
        except Exception as e:
            logger.error(f"AI分析调用失败: {e}")
            return {
                "success": False,
                "error": f"AI分析调用失败: {str(e)}"
            }
    
    def _prepare_data_for_ai(self, data: Any) -> Any:
        """为AI准备数据"""
        if data is None:
            return None
        
        if isinstance(data, pd.DataFrame):
            # 对于大数据集，进行采样和汇总
            if len(data) > 1000:
                # 采样前100行用于分析
                sample_data = data.head(100)
                
                # 生成数据摘要
                summary = {
                    'total_rows': len(data),
                    'total_columns': len(data.columns),
                    'columns': data.columns.tolist(),
                    'dtypes': data.dtypes.to_dict(),
                    'sample_data': sample_data.to_dict('records'),
                    'numeric_summary': data.describe().to_dict() if not data.select_dtypes(include=['number']).empty else {},
                    'missing_values': data.isnull().sum().to_dict()
                }
                return summary
            else:
                # 小数据集直接返回
                return data.to_dict('records')
        
        elif isinstance(data, dict):
            return data
        
        elif isinstance(data, str):
            # 如果是表名，从数据库获取数据
            try:
                query_data = pd.read_sql_query(f"SELECT * FROM {data} LIMIT 100", self.conn)
                return self._prepare_data_for_ai(query_data)
            except:
                return data
        
        else:
            return str(data)
    
    def detect_anomalies_with_ai(self, table_name: str) -> Dict[str, Any]:
        """使用AI检测异常"""
        try:
            # 获取数据
            query = f"SELECT * FROM {table_name} LIMIT 1000"
            data = pd.read_sql_query(query, self.conn)
            
            if data.empty:
                return {
                    "success": False,
                    "error": f"表 {table_name} 没有数据"
                }
            
            prompt = f"""
            请分析表 {table_name} 的数据，识别以下类型的异常：
            1. 异常金额（过大或过小的数值）
            2. 异常时间（非工作时间、节假日的交易）
            3. 异常频率（过于频繁或稀少的交易）
            4. 数据质量问题（空值、重复值、格式问题）
            5. 业务逻辑异常（不符合业务规则的记录）
            
            对于每个异常，请提供：
            - 异常类型和具体描述
            - 影响程度（高/中/低）
            - 可能的原因分析
            - 建议的处理方式
            
            请以结构化的方式提供分析结果。
            """
            
            result = self.call_ai_analysis(prompt, data)
            
            if result['success']:
                # 解析AI响应，提取异常信息
                anomalies = self._parse_anomaly_analysis(result['analysis'])
                result['anomalies'] = anomalies
                result['table_name'] = table_name
                result['data_summary'] = {
                    'total_records': len(data),
                    'columns': data.columns.tolist(),
                    'analysis_date': datetime.now().isoformat()
                }
            
            return result
            
        except Exception as e:
            logger.error(f"AI异常检测失败: {e}")
            return {
                "success": False,
                "error": f"AI异常检测失败: {str(e)}"
            }
    
    def generate_audit_insights(self, company_name: str) -> Dict[str, Any]:
        """生成审计洞察"""
        try:
            # 收集公司相关数据
            company_data = self._collect_company_data(company_name)
            
            if not company_data:
                return {
                    "success": False,
                    "error": f"未找到公司 {company_name} 的相关数据"
                }
            
            prompt = f"""
            基于公司 {company_name} 的完整财务数据，请生成审计洞察报告，包括：
            
            1. 财务健康状况评估
               - 收入和盈利能力分析
               - 现金流状况评估
               - 资产负债结构分析
            
            2. 关键风险点识别
               - 财务风险（流动性、偿债能力等）
               - 操作风险（内控缺陷、流程问题等）
               - 合规风险（政策法规遵循情况）
            
            3. 内控缺陷分析
               - 授权控制缺陷
               - 记录保持问题
               - 职责分离不当
            
            4. 合规性检查结果
               - 会计准则遵循情况
               - 税务合规性
               - 监管要求符合性
            
            5. 审计重点领域建议
               - 需要重点关注的业务流程
               - 建议的审计程序
               - 风险应对措施
            
            请提供具体的数据支撑和专业的审计意见。
            """
            
            result = self.call_ai_analysis(prompt, company_data)
            
            if result['success']:
                # 解析审计洞察
                insights = self._parse_audit_insights(result['analysis'])
                result['insights'] = insights
                result['company_name'] = company_name
                result['data_scope'] = {
                    'tables_analyzed': len(company_data.get('tables', [])),
                    'total_records': company_data.get('total_records', 0),
                    'analysis_date': datetime.now().isoformat()
                }
            
            return result
            
        except Exception as e:
            logger.error(f"审计洞察生成失败: {e}")
            return {
                "success": False,
                "error": f"审计洞察生成失败: {str(e)}"
            }
    
    def analyze_financial_trends(self, table_name: str, 
                                period: str = 'monthly') -> Dict[str, Any]:
        """分析财务趋势"""
        try:
            # 获取时间序列数据
            trend_view = f"temporal_{period}_{table_name.replace('raw_clean_', '')}"
            
            try:
                trend_data = pd.read_sql_query(f"SELECT * FROM {trend_view}", self.conn)
            except:
                # 如果视图不存在，使用原表数据
                trend_data = pd.read_sql_query(f"SELECT * FROM {table_name} LIMIT 500", self.conn)
            
            if trend_data.empty:
                return {
                    "success": False,
                    "error": f"没有可用的趋势数据"
                }
            
            prompt = f"""
            请分析 {table_name} 的财务趋势数据（{period}维度），重点关注：
            
            1. 趋势模式识别
               - 增长趋势（上升、下降、稳定）
               - 周期性模式
               - 季节性变化
            
            2. 异常点分析
               - 突然的增长或下降
               - 异常波动
               - 趋势变化点
            
            3. 预测性分析
               - 未来趋势预测
               - 风险预警
               - 机会识别
            
            4. 业务影响评估
               - 对公司运营的影响
               - 对财务状况的影响
               - 对决策的建议
            
            请提供详细的趋势分析和预测建议。
            """
            
            result = self.call_ai_analysis(prompt, trend_data)
            
            if result['success']:
                # 解析趋势分析
                trends = self._parse_trend_analysis(result['analysis'])
                result['trends'] = trends
                result['table_name'] = table_name
                result['period'] = period
                result['data_summary'] = {
                    'records_analyzed': len(trend_data),
                    'time_range': self._get_time_range(trend_data),
                    'analysis_date': datetime.now().isoformat()
                }
            
            return result
            
        except Exception as e:
            logger.error(f"财务趋势分析失败: {e}")
            return {
                "success": False,
                "error": f"财务趋势分析失败: {str(e)}"
            }
    
    def _collect_company_data(self, company_name: str) -> Optional[Dict[str, Any]]:
        """收集公司相关数据"""
        try:
            # 查找公司相关的表和视图
            company_tables_query = '''
                SELECT view_name FROM meta_views
                WHERE dimension_value LIKE ?
                OR view_name LIKE ?
            '''
            
            company_tables = self.conn.execute(
                company_tables_query, 
                (f'%{company_name}%', f'%{company_name}%')
            ).fetchall()
            
            if not company_tables:
                return None
            
            # 收集数据
            company_data = {
                'company_name': company_name,
                'tables': [],
                'total_records': 0
            }
            
            for (table_name,) in company_tables[:10]:  # 最多处理10个表
                try:
                    # 获取表数据概要
                    data_query = f"SELECT * FROM {table_name} LIMIT 100"
                    table_data = pd.read_sql_query(data_query, self.conn)
                    
                    if not table_data.empty:
                        company_data['tables'].append({
                            'name': table_name,
                            'records': len(table_data),
                            'columns': table_data.columns.tolist(),
                            'sample': table_data.head(5).to_dict('records')
                        })
                        company_data['total_records'] += len(table_data)
                        
                except Exception as e:
                    logger.warning(f"处理表失败 {table_name}: {e}")
                    continue
            
            return company_data if company_data['tables'] else None
            
        except Exception as e:
            logger.error(f"收集公司数据失败: {e}")
            return None
    
    def _parse_anomaly_analysis(self, analysis_text: str) -> List[Dict[str, Any]]:
        """解析异常分析结果"""
        # 简化实现：提取关键信息
        anomalies = []
        
        # 这里可以实现更复杂的文本解析逻辑
        # 目前返回示例结构
        if "异常" in analysis_text or "风险" in analysis_text:
            anomalies.append({
                "type": "AI检测异常",
                "description": "基于AI分析发现的异常模式",
                "severity": "中",
                "recommendation": "需要进一步人工审查"
            })
        
        return anomalies
    
    def _parse_audit_insights(self, analysis_text: str) -> Dict[str, Any]:
        """解析审计洞察结果"""
        # 简化实现：返回结构化的洞察信息
        return {
            "financial_health": "基于AI分析的财务健康状况",
            "key_risks": ["AI识别的主要风险点"],
            "control_weaknesses": ["内控缺陷分析"],
            "compliance_status": "合规性评估结果",
            "audit_focus_areas": ["建议的审计重点领域"]
        }
    
    def _parse_trend_analysis(self, analysis_text: str) -> Dict[str, Any]:
        """解析趋势分析结果"""
        # 简化实现：返回趋势信息
        return {
            "trend_direction": "上升/下降/稳定",
            "key_patterns": ["识别的关键模式"],
            "anomalies": ["异常点"],
            "predictions": ["未来趋势预测"],
            "recommendations": ["业务建议"]
        }
    
    def _get_time_range(self, data: pd.DataFrame) -> Dict[str, str]:
        """获取数据时间范围"""
        # 查找日期列
        date_columns = []
        for col in data.columns:
            if 'date' in col.lower() or '日期' in col.lower() or 'time' in col.lower():
                date_columns.append(col)
        
        if date_columns and not data.empty:
            date_col = date_columns[0]
            try:
                dates = pd.to_datetime(data[date_col], errors='coerce')
                return {
                    "start_date": dates.min().strftime('%Y-%m-%d'),
                    "end_date": dates.max().strftime('%Y-%m-%d')
                }
            except:
                pass
        
        return {"start_date": "未知", "end_date": "未知"}
    
    def _save_analysis_history(self, prompt: str, client: str, result: Dict[str, Any]):
        """保存分析历史"""
        try:
            # 创建分析历史表
            create_table_sql = '''
                CREATE TABLE IF NOT EXISTS ai_analysis_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    analysis_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    prompt TEXT,
                    client_used TEXT,
                    success BOOLEAN,
                    analysis_result TEXT,
                    error_message TEXT
                )
            '''
            
            self.conn.execute(create_table_sql)
            
            # 插入记录
            insert_sql = '''
                INSERT INTO ai_analysis_history
                (prompt, client_used, success, analysis_result, error_message)
                VALUES (?, ?, ?, ?, ?)
            '''
            
            self.conn.execute(insert_sql, (
                prompt[:500],  # 限制提示词长度
                client,
                result.get('success', False),
                json.dumps(result, ensure_ascii=False) if result.get('success') else None,
                result.get('error') if not result.get('success') else None
            ))
            
            self.conn.commit()
            
        except Exception as e:
            logger.warning(f"保存分析历史失败: {e}")
    
    def get_analysis_history(self, limit: int = 20) -> List[Dict[str, Any]]:
        """获取分析历史"""
        try:
            query = '''
                SELECT analysis_time, prompt, client_used, success, error_message
                FROM ai_analysis_history
                ORDER BY analysis_time DESC
                LIMIT ?
            '''
            
            results = self.conn.execute(query, (limit,)).fetchall()
            
            history = []
            for row in results:
                history.append({
                    'analysis_time': row[0],
                    'prompt': row[1],
                    'client_used': row[2],
                    'success': bool(row[3]),
                    'error_message': row[4]
                })
            
            return history
            
        except Exception as e:
            logger.error(f"获取分析历史失败: {e}")
            return []
    
    def close(self):
        """关闭连接"""
        if self.conn:
            self.conn.close()
            logger.info("智能体通信桥连接已关闭")


# 测试函数
def test_agent_bridge():
    """测试智能体通信桥"""
    import os
    
    # 创建测试数据库
    test_db = 'test_agent_bridge.db'
    conn = sqlite3.connect(test_db)
    
    # 创建测试表
    test_table_sql = '''
        CREATE TABLE test_financial_data (
            id INTEGER PRIMARY KEY,
            transaction_date TEXT,
            amount REAL,
            account_type TEXT,
            description TEXT
        )
    '''
    
    conn.execute(test_table_sql)
    
    # 插入测试数据
    test_data = [
        (1, '2023-01-01', 50000, '收入', '销售收入'),
        (2, '2023-01-02', -30000, '费用', '采购成本'),
        (3, '2023-01-03', 100000, '收入', '大额销售'),
        (4, '2023-01-04', -5000, '费用', '办公费用'),
        (5, '2023-01-05', 75000, '收入', '服务收入')
    ]
    
    conn.executemany('''
        INSERT INTO test_financial_data 
        (id, transaction_date, amount, account_type, description)
        VALUES (?, ?, ?, ?, ?)
    ''', test_data)
    
    conn.commit()
    conn.close()
    
    # 测试智能体通信桥
    bridge = AgentBridge(test_db)
    
    print("智能体通信桥测试:")
    
    # 测试可用客户端
    available_clients = bridge.get_available_clients()
    print(f"可用AI客户端: {available_clients}")
    
    # 测试AI分析
    print(f"\n测试AI分析:")
    test_data_df = pd.DataFrame([
        {'date': '2023-01-01', 'amount': 50000, 'type': '收入'},
        {'date': '2023-01-02', 'amount': -30000, 'type': '费用'},
        {'date': '2023-01-03', 'amount': 100000, 'type': '收入'}
    ])
    
    analysis_result = bridge.call_ai_analysis(
        "请分析这些财务数据的特点和风险",
        test_data_df
    )
    
    if analysis_result['success']:
        print(f"✅ AI分析成功 (客户端: {analysis_result['client']})")
        print(f"分析结果: {analysis_result['analysis'][:200]}...")
    else:
        print(f"❌ AI分析失败: {analysis_result['error']}")
    
    # 测试异常检测
    print(f"\n测试异常检测:")
    anomaly_result = bridge.detect_anomalies_with_ai('test_financial_data')
    
    if anomaly_result['success']:
        print(f"✅ 异常检测成功")
        print(f"检测到异常: {len(anomaly_result.get('anomalies', []))}")
    else:
        print(f"❌ 异常检测失败: {anomaly_result['error']}")
    
    # 获取分析历史
    history = bridge.get_analysis_history(5)
    print(f"\n分析历史 (共{len(history)}条):")
    for item in history:
        status = "✅" if item['success'] else "❌"
        print(f"{status} {item['analysis_time']} - {item['client_used']} - {item['prompt'][:50]}...")
    
    bridge.close()
    
    # 清理测试文件
    if os.path.exists(test_db):
        os.remove(test_db)


if __name__ == "__main__":
    test_agent_bridge()