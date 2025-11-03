"""
DAP Web GUI - Flask后端应用
提供Web界面的REST API服务
"""

from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import os
import sys
import logging
from typing import Dict, Any
from datetime import datetime

# 添加DAP根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from layer2.project_manager import ProjectManager
from main_engine import DAPEngine
from layer3.external_services.service_manager import ExternalServiceManager
from layer4.enhanced_nl_query_engine import EnhancedNLQueryEngine

# 添加报表相关导入
try:
    from layer2.financial_reports import FinancialReportsGenerator
    from layer2.consolidation_engine import ConsolidationEngine
    REPORTING_AVAILABLE = True
except ImportError:
    REPORTING_AVAILABLE = False
    FinancialReportsGenerator = None
    ConsolidationEngine = None

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 创建Flask应用
app = Flask(__name__, static_folder='static', static_url_path='')
CORS(app)  # 启用跨域支持

# 初始化DAP组件
DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'dap_data.db')
project_manager = ProjectManager(db_path=DB_PATH)
dap_engine = DAPEngine(db_path=DB_PATH)
service_manager = ExternalServiceManager()
nl_query_engine = EnhancedNLQueryEngine(db_path=DB_PATH)

# ==================== 项目管理API ====================

@app.route('/api/projects', methods=['GET'])
def list_projects():
    """获取项目列表"""
    try:
        # 获取查询参数
        status = request.args.get('status')
        client_code = request.args.get('client_code')
        project_type = request.args.get('project_type')
        limit = int(request.args.get('limit', 100))
        offset = int(request.args.get('offset', 0))
        
        filters = {}
        if status:
            filters['status'] = status
        if client_code:
            filters['client_code'] = client_code
        if project_type:
            filters['project_type'] = project_type
        
        result = project_manager.list_projects(filters=filters, limit=limit, offset=offset)
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"获取项目列表失败: {e}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@app.route('/api/projects', methods=['POST'])
def create_project():
    """创建新项目"""
    try:
        data = request.get_json()
        
        # 输入验证
        if not data:
            logger.warning("创建项目请求缺少数据")
            return jsonify({
                "success": False,
                "error": "请求体不能为空"
            }), 400
            
        if not data.get('project_name'):
            logger.warning("创建项目缺少project_name")
            return jsonify({
                "success": False,
                "error": "缺少必填字段: project_name"
            }), 400
        
        # 字段长度验证
        if len(data['project_name']) > 200:
            logger.warning(f"project_name过长: {len(data['project_name'])}")
            return jsonify({
                "success": False,
                "error": "项目名称长度不能超过200字符"
            }), 400
        
        result = project_manager.create_project(data)
        
        if result['success']:
            logger.info(f"项目创建成功: {result.get('project_id')}")
            return jsonify(result), 201
        else:
            logger.warning(f"项目创建失败: {result.get('error')}")
            return jsonify(result), 400
            
    except Exception as e:
        logger.error(f"创建项目异常: {e}", exc_info=True)
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@app.route('/api/projects/<project_id>', methods=['GET'])
def get_project(project_id):
    """获取项目详情"""
    try:
        project = project_manager.get_project(project_id=project_id)
        
        if project:
            # 获取项目统计
            stats = project_manager.get_project_statistics(project_id)
            project['statistics'] = stats
            
            return jsonify({
                "success": True,
                "project": project
            })
        else:
            return jsonify({
                "success": False,
                "error": "项目不存在"
            }), 404
            
    except Exception as e:
        logger.error(f"获取项目详情失败: {e}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@app.route('/api/projects/<project_id>', methods=['PUT'])
def update_project(project_id):
    """更新项目信息"""
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({
                "success": False,
                "error": "请求体不能为空"
            }), 400
        
        result = project_manager.update_project(project_id, data)
        
        if result['success']:
            return jsonify(result)
        else:
            return jsonify(result), 400
            
    except Exception as e:
        logger.error(f"更新项目失败: {e}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@app.route('/api/projects/<project_id>', methods=['DELETE'])
def delete_project(project_id):
    """删除项目"""
    try:
        soft_delete = request.args.get('soft', 'true').lower() == 'true'
        result = project_manager.delete_project(project_id, soft_delete=soft_delete)
        
        if result['success']:
            return jsonify(result)
        else:
            return jsonify(result), 400
            
    except Exception as e:
        logger.error(f"删除项目失败: {e}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@app.route('/api/projects/<project_id>/activities', methods=['GET'])
def get_project_activities(project_id):
    """获取项目活动日志"""
    try:
        limit = int(request.args.get('limit', 50))
        activities = project_manager.get_project_activities(project_id, limit=limit)
        
        return jsonify({
            "success": True,
            "activities": activities
        })
        
    except Exception as e:
        logger.error(f"获取项目活动失败: {e}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


# ==================== 数据处理API ====================

@app.route('/api/data/process', methods=['POST'])
def process_data():
    """处理数据（上传、清洗、分析）"""
    try:
        data = request.get_json()
        
        # 输入验证
        if not data:
            logger.warning("数据处理请求缺少数据")
            return jsonify({
                "success": False,
                "error": "请求体不能为空"
            }), 400
        
        # 强制检查项目ID
        if not data.get('project_id') and not data.get('skip_project_check'):
            logger.warning("数据处理缺少project_id")
            return jsonify({
                "success": False,
                "error": "必须提供project_id或设置skip_project_check=true"
            }), 400
        
        logger.info(f"开始处理数据，项目: {data.get('project_id')}")
        result = dap_engine.process(data)
        
        if result.get('success'):
            logger.info(f"数据处理成功: {result.get('statistics')}")
        else:
            logger.warning(f"数据处理失败: {result.get('error')}")
        
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"数据处理异常: {e}", exc_info=True)
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


# ==================== 自然语言查询API ====================

@app.route('/api/query/nl', methods=['POST'])
def natural_language_query():
    """自然语言查询"""
    try:
        data = request.get_json()
        
        # 输入验证
        if not data:
            logger.warning("NL查询请求缺少数据")
            return jsonify({
                "success": False,
                "error": "请求体不能为空"
            }), 400
            
        query_text = data.get('query')
        if not query_text:
            logger.warning("NL查询缺少query字段")
            return jsonify({
                "success": False,
                "error": "缺少查询文本(query)"
            }), 400
        
        # 查询长度验证
        if len(query_text) > 1000:
            logger.warning(f"查询文本过长: {len(query_text)}")
            return jsonify({
                "success": False,
                "error": "查询文本长度不能超过1000字符"
            }), 400
        
        project_id = data.get('project_id')
        context = {
            'project_id': project_id
        }
        
        logger.info(f"NL查询: {query_text[:50]}...")
        result = nl_query_engine.process_query(query_text, context=context)
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"自然语言查询异常: {e}", exc_info=True)
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


# ==================== 外部服务API ====================

@app.route('/api/external/services/status', methods=['GET'])
def external_services_status():
    """获取外部服务状态"""
    try:
        status = service_manager.health_check_all()
        
        return jsonify({
            "success": True,
            "services": status
        })
        
    except Exception as e:
        logger.error(f"获取服务状态失败: {e}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@app.route('/api/external/query', methods=['POST'])
def external_service_query():
    """查询外部服务"""
    try:
        data = request.get_json()
        query = data.get('query')
        services = data.get('services')  # 可选，指定要查询的服务
        
        if not query:
            return jsonify({
                "success": False,
                "error": "缺少查询文本(query)"
            }), 400
        
        result = service_manager.comprehensive_query(
            query=query,
            services=services,
            parallel=True
        )
        
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"外部服务查询失败: {e}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


# ==================== 系统信息API ====================

@app.route('/api/system/info', methods=['GET'])
def system_info():
    """获取系统信息"""
    try:
        return jsonify({
            "success": True,
            "system": {
                "name": "DAP - Data Analytics Platform",
                "version": "2.0.0",
                "components": {
                    "project_manager": "enabled",
                    "dap_engine": "enabled",
                    "external_services": "enabled",
                    "nl_query": "enabled"
                }
            }
        })
        
    except Exception as e:
        logger.error(f"获取系统信息失败: {e}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


# ==================== 静态文件服务 ====================

@app.route('/')
def index():
    """返回前端页面"""
    if app.static_folder:
        return send_from_directory(app.static_folder, 'index.html')
    else:
        return "Static folder not configured", 500


@app.route('/<path:path>')
def static_files(path):
    """返回静态文件"""
    if app.static_folder:
        return send_from_directory(app.static_folder, path)
    else:
        return "Static folder not configured", 500


# ==================== 错误处理 ====================

@app.errorhandler(404)
def not_found(error):
    return jsonify({
        "success": False,
        "error": "API端点不存在"
    }), 404


@app.errorhandler(500)
def internal_error(error):
    return jsonify({
        "success": False,
        "error": "服务器内部错误"
    }), 500


# ==================== 财务报表API ====================

@app.route('/api/reports/account-balance', methods=['POST'])
def get_account_balance():
    """获取科目余额表数据"""
    try:
        if not REPORTING_AVAILABLE or FinancialReportsGenerator is None:
            return jsonify({
                "success": False,
                "error": "报表功能不可用"
            }), 500

        data = request.get_json()
        period = data.get('period')
        
        if not period:
            return jsonify({
                "success": False,
                "error": "缺少会计期间参数"
            }), 400

        # 初始化报表生成器
        report_generator = FinancialReportsGenerator(db_path=DB_PATH)
        
        # 获取科目余额数据
        balance_data = report_generator._get_account_balance_data(period)
        
        # 转换为字典列表
        records = []
        for _, row in balance_data.iterrows():
            records.append(row.to_dict())
        
        return jsonify({
            "success": True,
            "data": records,
            "period": period,
            "report_type": "account_balance"
        })
        
    except Exception as e:
        logger.error(f"获取科目余额表失败: {e}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@app.route('/api/reports/account-detail', methods=['POST'])
def get_account_detail():
    """获取科目明细账数据"""
    try:
        if not REPORTING_AVAILABLE or FinancialReportsGenerator is None:
            return jsonify({
                "success": False,
                "error": "报表功能不可用"
            }), 500

        data = request.get_json()
        period = data.get('period')
        account_code = data.get('account_code')
        
        if not period:
            return jsonify({
                "success": False,
                "error": "缺少会计期间参数"
            }), 400

        # 初始化报表生成器
        report_generator = FinancialReportsGenerator(db_path=DB_PATH)
        
        # 获取科目明细数据
        detail_data = report_generator._get_account_detail_data(period, account_code)
        
        # 转换为字典列表
        records = []
        for _, row in detail_data.iterrows():
            records.append(row.to_dict())
        
        return jsonify({
            "success": True,
            "data": records,
            "period": period,
            "account_code": account_code,
            "report_type": "account_detail"
        })
        
    except Exception as e:
        logger.error(f"获取科目明细账失败: {e}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@app.route('/api/reports/generate', methods=['POST'])
def generate_report():
    """生成财务报表"""
    try:
        if not REPORTING_AVAILABLE or FinancialReportsGenerator is None:
            return jsonify({
                "success": False,
                "error": "报表功能不可用"
            }), 500

        data = request.get_json()
        report_type = data.get('report_type')
        period = data.get('period')
        format_type = data.get('format', 'excel')
        
        if not report_type or not period:
            return jsonify({
                "success": False,
                "error": "缺少必要参数"
            }), 400

        # 初始化报表生成器
        report_generator = FinancialReportsGenerator(db_path=DB_PATH)
        
        # 根据报表类型生成报表
        result = None
        if report_type == 'account_balance':
            result = report_generator.generate_account_balance_report(period, format_type)
        elif report_type == 'account_detail':
            result = report_generator.generate_account_detail_report(period, format_type=format_type)
        elif report_type == 'balance_sheet':
            result = report_generator.generate_balance_sheet_report(period, format_type)
        elif report_type == 'income_statement':
            result = report_generator.generate_income_statement_report(period, format_type)
        elif report_type == 'cash_flow':
            result = report_generator.generate_cash_flow_report(period, format_type)
        else:
            return jsonify({
                "success": False,
                "error": f"不支持的报表类型: {report_type}"
            }), 400

        if result.get('success'):
            return jsonify({
                "success": True,
                "output_path": result.get('output_path'),
                "download_url": f"/api/reports/download/{report_type}/{period}",
                "report_type": report_type,
                "period": period
            })
        else:
            return jsonify({
                "success": False,
                "error": result.get('error')
            }), 400
            
    except Exception as e:
        logger.error(f"生成报表失败: {e}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

# ==================== 合并报表API ====================

@app.route('/api/consolidation/generate', methods=['POST'])
def generate_consolidation_report():
    """生成合并报表"""
    try:
        if not REPORTING_AVAILABLE or not ConsolidationEngine:
            return jsonify({
                "success": False,
                "error": "合并报表功能不可用"
            }), 500

        data = request.get_json()
        parent_entity_id = data.get('parent_entity_id')
        period = data.get('period')
        report_type = data.get('report_type', 'balance_sheet')
        
        if not parent_entity_id or not period:
            return jsonify({
                "success": False,
                "error": "缺少必要参数"
            }), 400

        # 初始化合并引擎
        with ConsolidationEngine(db_path=DB_PATH) as consolidation_engine:
            result = consolidation_engine.generate_consolidated_report(
                parent_entity_id=int(parent_entity_id),
                period=period,
                report_type=report_type
            )

        if result.get('success'):
            return jsonify({
                "success": True,
                "consolidation_id": result.get('consolidation_id'),
                "scope_entity_count": result.get('scope_entity_count'),
                "elimination_count": result.get('elimination_count'),
                "minority_interest": result.get('minority_interest'),
                "report_type": report_type,
                "period": period
            })
        else:
            return jsonify({
                "success": False,
                "error": result.get('error')
            }), 400
            
    except Exception as e:
        logger.error(f"生成合并报表失败: {e}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

# ==================== 审计底稿API ====================

@app.route('/api/audit/working-papers', methods=['POST'])
def get_working_papers():
    """获取审计底稿数据"""
    try:
        # 暂时返回模拟数据
        data = request.get_json()
        paper_type = data.get('paper_type')
        period = data.get('period')
        
        if not paper_type or not period:
            return jsonify({
                "success": False,
                "error": "缺少必要参数"
            }), 400

        # 模拟数据
        sample_data = []
        if paper_type == 'trial_balance':
            sample_data = [
                {"科目编码": "1001", "科目名称": "库存现金", "期初余额": 50000, "借方发生额": 20000, "贷方发生额": 15000, "期末余额": 55000},
                {"科目编码": "1002", "科目名称": "银行存款", "期初余额": 1200000, "借方发生额": 800000, "贷方发生额": 750000, "期末余额": 1250000}
            ]
        elif paper_type == 'adjustment':
            sample_data = [
                {"序号": 1, "摘要": "折旧费用计提", "借方科目": "管理费用", "借方金额": 50000, "贷方科目": "累计折旧", "贷方金额": 50000},
                {"序号": 2, "摘要": "坏账准备计提", "借方科目": "资产减值损失", "借方金额": 30000, "贷方科目": "坏账准备", "贷方金额": 30000}
            ]
        else:
            sample_data = [
                {"项目": f"项目{i}", "内容": f"这是第{i}个{paper_type}项目的示例数据", "金额": i * 10000}
                for i in range(1, 6)
            ]

        return jsonify({
            "success": True,
            "data": sample_data,
            "paper_type": paper_type,
            "period": period
        })
        
    except Exception as e:
        logger.error(f"获取审计底稿失败: {e}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@app.route('/api/audit/export', methods=['POST'])
def export_working_papers():
    """导出审计底稿"""
    try:
        data = request.get_json()
        paper_type = data.get('paper_type')
        period = data.get('period')
        format_type = data.get('format', 'excel')
        
        if not paper_type or not period:
            return jsonify({
                "success": False,
                "error": "缺少必要参数"
            }), 400

        # 生成文件名
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"审计底稿_{paper_type}_{period}_{timestamp}.{format_type}"
        output_path = os.path.join('exports', filename)
        
        # 确保导出目录存在
        os.makedirs('exports', exist_ok=True)
        
        # 创建简单文件作为示例
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(f"审计底稿 - {paper_type}\n")
            f.write(f"会计期间: {period}\n")
            f.write(f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write("\n这是一个示例审计底稿文件。\n")

        return jsonify({
            "success": True,
            "output_path": output_path,
            "download_url": f"/api/audit/download/{paper_type}/{period}",
            "paper_type": paper_type,
            "period": period
        })
        
    except Exception as e:
        logger.error(f"导出审计底稿失败: {e}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

# ==================== 启动应用 ====================

if __name__ == '__main__':
    # 开发模式
    app.run(
        host='127.0.0.1',
        port=5000,
        debug=False
    )
