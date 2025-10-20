"""
DAP - API服务器
提供RESTful API接口服务
"""

import sqlite3
import pandas as pd
import json
import os
from typing import Dict, Any, List, Optional
from datetime import datetime
import logging
from pathlib import Path

# FastAPI相关导入
from fastapi import FastAPI, HTTPException, Query, Path as APIPath, File, UploadFile
from fastapi.responses import JSONResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn

logger = logging.getLogger(__name__)

# Pydantic模型定义
class DataQueryRequest(BaseModel):
    query: str
    limit: Optional[int] = 1000

class AnalysisRequest(BaseModel):
    analysis_type: str
    company_id: Optional[str] = None
    table_name: Optional[str] = None
    parameters: Optional[Dict[str, Any]] = {}

class ExportRequest(BaseModel):
    source: str
    format: str
    options: Optional[Dict[str, Any]] = {}

class AuditReportRequest(BaseModel):
    company_name: str
    period: str
    format: Optional[str] = 'html'

# FastAPI应用实例
app = FastAPI(
    title="DAP API服务",
    description="数据处理审计智能体 API",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class DAPAPIServer:
    """DAP API服务器"""
    
    def __init__(self, db_path: str = 'data/dap_data.db', export_dir: str = 'exports'):
        self.db_path = db_path
        self.export_dir = export_dir
        
        # 确保目录存在
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        os.makedirs(export_dir, exist_ok=True)
        
        # 初始化组件
        from layer2.output_formatter import OutputFormatter
        self.output_formatter = OutputFormatter(db_path, export_dir)
        
        logger.info(f"DAP API服务器初始化完成")
    
    def get_db_connection(self):
        """获取数据库连接"""
        return sqlite3.connect(self.db_path, check_same_thread=False)
    
    def execute_query(self, query: str, params: tuple = ()) -> List[Dict[str, Any]]:
        """执行SQL查询"""
        try:
            conn = self.get_db_connection()
            cursor = conn.execute(query, params)
            
            # 获取列名
            columns = [description[0] for description in cursor.description]
            
            # 获取数据
            rows = cursor.fetchall()
            
            # 转换为字典列表
            result = []
            for row in rows:
                result.append(dict(zip(columns, row)))
            
            conn.close()
            return result
            
        except Exception as e:
            logger.error(f"查询执行失败: {e}")
            raise HTTPException(status_code=500, detail=f"查询执行失败: {str(e)}")
    
    def get_table_data(self, table_name: str, limit: int = 1000) -> pd.DataFrame:
        """获取表数据"""
        try:
            conn = self.get_db_connection()
            query = f"SELECT * FROM {table_name} LIMIT {limit}"
            df = pd.read_sql_query(query, conn)
            conn.close()
            return df
            
        except Exception as e:
            logger.error(f"获取表数据失败 {table_name}: {e}")
            raise HTTPException(status_code=404, detail=f"表不存在或查询失败: {table_name}")

# 创建API服务器实例
dap_server = DAPAPIServer()

# API路由定义

@app.get("/")
async def root():
    """根路径"""
    return {
        "message": "DAP - 数据处理审计智能体 API服务",
        "version": "1.0.0",
        "status": "运行中",
        "timestamp": datetime.now().isoformat()
    }

@app.get("/api/health")
async def health_check():
    """健康检查"""
    try:
        # 检查数据库连接
        conn = dap_server.get_db_connection()
        conn.execute("SELECT 1")
        conn.close()
        
        return {
            "status": "healthy",
            "database": "connected",
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "database": "disconnected",
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }

@app.get("/api/info")
async def get_system_info():
    """获取系统信息"""
    try:
        # 获取数据库统计
        stats_query = '''
            SELECT 
                (SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name LIKE 'raw_clean_%') as raw_tables,
                (SELECT COUNT(*) FROM sqlite_master WHERE type='view') as total_views,
                (SELECT COUNT(*) FROM meta_tables) as processed_tables
        '''
        
        stats_result = dap_server.execute_query(stats_query)
        stats = stats_result[0] if stats_result else {}
        
        return {
            "system": "DAP - 数据处理审计智能体",
            "version": "1.0.0",
            "database_path": dap_server.db_path,
            "statistics": {
                "raw_tables": stats.get('raw_tables', 0),
                "total_views": stats.get('total_views', 0),
                "processed_tables": stats.get('processed_tables', 0)
            },
            "supported_formats": dap_server.output_formatter.get_supported_formats()
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取系统信息失败: {str(e)}")

@app.get("/api/tables")
async def get_tables():
    """获取所有表列表"""
    try:
        query = '''
            SELECT table_name, table_type, business_domain, row_count, 
                   column_count, data_quality_score, created_at
            FROM meta_tables
            ORDER BY created_at DESC
        '''
        
        tables = dap_server.execute_query(query)
        
        return {
            "tables": tables,
            "count": len(tables)
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取表列表失败: {str(e)}")

@app.get("/api/tables/{table_name}")
async def get_table_info(table_name: str = APIPath(..., description="表名")):
    """获取表详细信息"""
    try:
        # 获取表基本信息
        table_query = '''
            SELECT table_name, table_type, business_domain, row_count, 
                   column_count, data_quality_score, schema_info
            FROM meta_tables
            WHERE table_name = ?
        '''
        
        table_info = dap_server.execute_query(table_query, (table_name,))
        
        if not table_info:
            raise HTTPException(status_code=404, detail=f"表不存在: {table_name}")
        
        # 获取列信息
        columns_query = '''
            SELECT column_name, column_type, data_type, business_meaning,
                   null_ratio, unique_ratio, is_primary_key
            FROM meta_columns
            WHERE table_name = ?
        '''
        
        columns_info = dap_server.execute_query(columns_query, (table_name,))
        
        # 获取关系信息
        relationships_query = '''
            SELECT from_column, to_table, to_column, relationship_type, confidence
            FROM meta_relationships
            WHERE from_table = ?
        '''
        
        relationships = dap_server.execute_query(relationships_query, (table_name,))
        
        return {
            "table_info": table_info[0],
            "columns": columns_info,
            "relationships": relationships
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取表信息失败: {str(e)}")

@app.get("/api/views")
async def get_views():
    """获取所有视图列表"""
    try:
        query = '''
            SELECT view_name, view_type, dimension_key, dimension_value, 
                   created_at, last_refreshed
            FROM meta_views
            ORDER BY view_type, dimension_value
        '''
        
        views = dap_server.execute_query(query)
        
        # 按类型分组
        views_by_type = {}
        for view in views:
            view_type = view['view_type']
            if view_type not in views_by_type:
                views_by_type[view_type] = []
            views_by_type[view_type].append(view)
        
        return {
            "views": views,
            "views_by_type": views_by_type,
            "total_count": len(views)
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取视图列表失败: {str(e)}")

@app.get("/api/companies")
async def get_companies():
    """获取所有公司列表"""
    try:
        query = '''
            SELECT company_id, company_name, industry, created_at
            FROM meta_companies
            ORDER BY company_name
        '''
        
        companies = dap_server.execute_query(query)
        
        return {
            "companies": companies,
            "count": len(companies)
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取公司列表失败: {str(e)}")

@app.get("/api/data/{table_or_view}")
async def get_data(
    table_or_view: str = APIPath(..., description="表名或视图名"),
    limit: int = Query(1000, description="返回记录数限制"),
    offset: int = Query(0, description="偏移量")
):
    """获取表或视图数据"""
    try:
        # 验证限制
        if limit > 10000:
            limit = 10000
        if offset < 0:
            offset = 0
        
        query = f"SELECT * FROM {table_or_view} LIMIT {limit} OFFSET {offset}"
        data = dap_server.execute_query(query)
        
        # 获取总记录数
        count_query = f"SELECT COUNT(*) as total FROM {table_or_view}"
        count_result = dap_server.execute_query(count_query)
        total_count = count_result[0]['total'] if count_result else 0
        
        return {
            "data": data,
            "pagination": {
                "limit": limit,
                "offset": offset,
                "count": len(data),
                "total": total_count,
                "has_more": offset + len(data) < total_count
            }
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取数据失败: {str(e)}")

@app.post("/api/query")
async def execute_custom_query(request: DataQueryRequest):
    """执行自定义SQL查询"""
    try:
        # 安全检查：只允许SELECT查询
        query_upper = request.query.upper().strip()
        if not query_upper.startswith('SELECT'):
            raise HTTPException(status_code=400, detail="只允许SELECT查询")
        
        # 禁止某些危险操作
        dangerous_keywords = ['DROP', 'DELETE', 'UPDATE', 'INSERT', 'ALTER', 'CREATE']
        if any(keyword in query_upper for keyword in dangerous_keywords):
            raise HTTPException(status_code=400, detail="查询包含不被允许的操作")
        
        # 添加LIMIT限制
        if 'LIMIT' not in query_upper and request.limit:
            query = f"{request.query} LIMIT {request.limit}"
        else:
            query = request.query
        
        data = dap_server.execute_query(query)
        
        return {
            "query": request.query,
            "data": data,
            "count": len(data)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"查询执行失败: {str(e)}")

@app.post("/api/analyze")
async def analyze_data(request: AnalysisRequest):
    """数据分析接口"""
    try:
        analysis_type = request.analysis_type
        
        if analysis_type == 'financial_summary':
            return await get_financial_summary(request.company_id, request.parameters)
        elif analysis_type == 'risk_analysis':
            return await get_risk_analysis(request.company_id)
        elif analysis_type == 'trend_analysis':
            return await get_trend_analysis(request.table_name, request.parameters)
        elif analysis_type == 'anomaly_detection':
            return await get_anomaly_detection(request.table_name)
        elif analysis_type == 'data_quality':
            return await get_data_quality_analysis()
        else:
            raise HTTPException(status_code=400, detail=f"不支持的分析类型: {analysis_type}")
            
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"数据分析失败: {str(e)}")

async def get_financial_summary(company_id: Optional[str], parameters: Dict[str, Any]):
    """获取财务摘要"""
    try:
        # 查找财务相关表
        financial_tables_query = '''
            SELECT table_name FROM meta_tables
            WHERE business_domain = 'financial' 
            OR table_type LIKE '%ledger%'
            OR table_type LIKE '%financial%'
        '''
        
        tables = dap_server.execute_query(financial_tables_query)
        
        summary = {
            'total_transactions': 0,
            'total_amount': 0,
            'tables_analyzed': len(tables),
            'period': parameters.get('period', '全部'),
            'company_id': company_id
        }
        
        for table_info in tables:
            table_name = f"raw_clean_{table_info['table_name']}"
            
            try:
                # 获取交易统计
                stats_query = f'''
                    SELECT COUNT(*) as count, 
                           COALESCE(SUM(amount), 0) as total_amount
                    FROM {table_name}
                '''
                
                stats = dap_server.execute_query(stats_query)
                if stats:
                    summary['total_transactions'] += stats[0]['count']
                    summary['total_amount'] += stats[0]['total_amount']
                    
            except Exception as e:
                logger.warning(f"处理表失败 {table_name}: {e}")
                continue
        
        return {
            'analysis_type': 'financial_summary',
            'result': summary
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"财务摘要分析失败: {str(e)}")

async def get_risk_analysis(company_id: Optional[str]):
    """获取风险分析"""
    try:
        # 查找风险相关视图
        risk_views_query = '''
            SELECT view_name, view_type FROM meta_views
            WHERE view_type LIKE '%risk%' OR view_type LIKE '%anomaly%'
        '''
        
        risk_views = dap_server.execute_query(risk_views_query)
        
        risk_summary = {
            'high_risk_items': 0,
            'medium_risk_items': 0,
            'low_risk_items': 0,
            'risk_categories': [],
            'company_id': company_id
        }
        
        for view_info in risk_views:
            view_name = view_info['view_name']
            
            try:
                count_query = f'SELECT COUNT(*) as count FROM {view_name}'
                count_result = dap_server.execute_query(count_query)
                
                if count_result:
                    count = count_result[0]['count']
                    
                    # 根据视图类型分类风险级别
                    if 'high' in view_name.lower() or 'anomaly' in view_name.lower():
                        risk_summary['high_risk_items'] += count
                    elif 'medium' in view_name.lower():
                        risk_summary['medium_risk_items'] += count
                    else:
                        risk_summary['low_risk_items'] += count
                    
                    risk_summary['risk_categories'].append({
                        'category': view_name,
                        'type': view_info['view_type'],
                        'count': count
                    })
                    
            except Exception as e:
                logger.warning(f"处理风险视图失败 {view_name}: {e}")
                continue
        
        return {
            'analysis_type': 'risk_analysis',
            'result': risk_summary
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"风险分析失败: {str(e)}")

async def get_trend_analysis(table_name: Optional[str], parameters: Dict[str, Any]):
    """获取趋势分析"""
    try:
        if not table_name:
            raise HTTPException(status_code=400, detail="趋势分析需要指定表名")
        
        # 查找时间维度视图
        trend_views_query = '''
            SELECT view_name FROM meta_views
            WHERE view_type LIKE 'temporal_%'
            AND base_tables LIKE ?
        '''
        
        trend_views = dap_server.execute_query(trend_views_query, (f'%{table_name}%',))
        
        trend_data = []
        
        for view_info in trend_views:
            view_name = view_info['view_name']
            
            try:
                # 获取趋势数据
                trend_query = f'SELECT * FROM {view_name} ORDER BY 1'
                data = dap_server.execute_query(trend_query)
                
                trend_data.append({
                    'view_name': view_name,
                    'data': data
                })
                
            except Exception as e:
                logger.warning(f"处理趋势视图失败 {view_name}: {e}")
                continue
        
        return {
            'analysis_type': 'trend_analysis',
            'table_name': table_name,
            'result': trend_data
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"趋势分析失败: {str(e)}")

async def get_anomaly_detection(table_name: Optional[str]):
    """获取异常检测结果"""
    try:
        # 查找异常检测视图
        anomaly_views_query = '''
            SELECT view_name FROM meta_views
            WHERE view_type LIKE '%anomaly%'
        '''
        
        if table_name:
            anomaly_views_query += ' AND base_tables LIKE ?'
            anomaly_views = dap_server.execute_query(anomaly_views_query, (f'%{table_name}%',))
        else:
            anomaly_views = dap_server.execute_query(anomaly_views_query)
        
        anomalies = []
        
        for view_info in anomaly_views:
            view_name = view_info['view_name']
            
            try:
                # 获取异常数据样本
                anomaly_query = f'SELECT * FROM {view_name} LIMIT 20'
                data = dap_server.execute_query(anomaly_query)
                
                # 获取异常总数
                count_query = f'SELECT COUNT(*) as count FROM {view_name}'
                count_result = dap_server.execute_query(count_query)
                total_count = count_result[0]['count'] if count_result else 0
                
                anomalies.append({
                    'view_name': view_name,
                    'total_count': total_count,
                    'sample_data': data[:10]  # 只返回前10条样本
                })
                
            except Exception as e:
                logger.warning(f"处理异常视图失败 {view_name}: {e}")
                continue
        
        return {
            'analysis_type': 'anomaly_detection',
            'table_name': table_name,
            'result': anomalies
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"异常检测失败: {str(e)}")

async def get_data_quality_analysis():
    """获取数据质量分析"""
    try:
        # 获取整体数据质量
        quality_query = '''
            SELECT 
                COUNT(*) as total_tables,
                AVG(data_quality_score) as avg_score,
                MIN(data_quality_score) as min_score,
                MAX(data_quality_score) as max_score,
                SUM(CASE WHEN data_quality_score >= 0.9 THEN 1 ELSE 0 END) as excellent_tables,
                SUM(CASE WHEN data_quality_score >= 0.8 THEN 1 ELSE 0 END) as good_tables,
                SUM(CASE WHEN data_quality_score < 0.7 THEN 1 ELSE 0 END) as poor_tables
            FROM meta_tables
        '''
        
        quality_result = dap_server.execute_query(quality_query)
        
        # 获取各表详细质量信息
        tables_quality_query = '''
            SELECT table_name, table_type, data_quality_score, row_count
            FROM meta_tables
            ORDER BY data_quality_score DESC
        '''
        
        tables_quality = dap_server.execute_query(tables_quality_query)
        
        return {
            'analysis_type': 'data_quality',
            'result': {
                'summary': quality_result[0] if quality_result else {},
                'tables_detail': tables_quality
            }
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"数据质量分析失败: {str(e)}")

@app.post("/api/export")
async def export_data(request: ExportRequest):
    """数据导出接口"""
    try:
        result = dap_server.output_formatter.export_data(
            request.source,
            request.format,
            options=request.options
        )
        
        if result['success']:
            return {
                'success': True,
                'file_path': result['output_path'],
                'file_size': result['file_size'],
                'record_count': result['record_count'],
                'format': result['format']
            }
        else:
            raise HTTPException(status_code=500, detail=result['error'])
            
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"数据导出失败: {str(e)}")

@app.get("/api/export/{file_name}")
async def download_export_file(file_name: str = APIPath(..., description="导出文件名")):
    """下载导出文件"""
    try:
        file_path = os.path.join(dap_server.export_dir, file_name)
        
        if not os.path.exists(file_path):
            raise HTTPException(status_code=404, detail="文件不存在")
        
        # 检查文件是否在允许的导出目录内（安全检查）
        abs_file_path = os.path.abspath(file_path)
        abs_export_dir = os.path.abspath(dap_server.export_dir)
        
        if not abs_file_path.startswith(abs_export_dir):
            raise HTTPException(status_code=403, detail="访问被拒绝")
        
        return FileResponse(
            path=file_path,
            filename=file_name,
            media_type='application/octet-stream'
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"文件下载失败: {str(e)}")

@app.post("/api/reports/audit")
async def generate_audit_report(request: AuditReportRequest):
    """生成审计报告"""
    try:
        result = dap_server.output_formatter.generate_audit_report(
            request.company_name,
            request.period,
            request.format
        )
        
        if result['success']:
            return {
                'success': True,
                'report_path': result['output_path']
            }
        else:
            raise HTTPException(status_code=500, detail=result['error'])
            
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"审计报告生成失败: {str(e)}")

@app.get("/api/history/exports")
async def get_export_history(limit: int = Query(20, description="返回记录数限制")):
    """获取导出历史"""
    try:
        history = dap_server.output_formatter.get_export_history(limit)
        
        return {
            'history': history,
            'count': len(history)
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取导出历史失败: {str(e)}")

@app.get("/api/stats")
async def get_statistics():
    """获取系统统计信息"""
    try:
        # 数据库统计
        db_stats_query = '''
            SELECT 
                (SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name LIKE 'raw_clean_%') as raw_tables,
                (SELECT COUNT(*) FROM sqlite_master WHERE type='view') as total_views,
                (SELECT COUNT(*) FROM meta_tables) as processed_tables,
                (SELECT COUNT(*) FROM meta_companies) as companies,
                (SELECT COUNT(*) FROM meta_views) as meta_views
        '''
        
        db_stats = dap_server.execute_query(db_stats_query)
        
        # 导出统计
        export_stats = dap_server.output_formatter.export_stats
        
        return {
            'database_statistics': db_stats[0] if db_stats else {},
            'export_statistics': export_stats,
            'last_updated': datetime.now().isoformat()
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取统计信息失败: {str(e)}")

# 启动函数
def start_api_server(host: str = "127.0.0.1", port: int = 8000, 
                    reload: bool = False, log_level: str = "info"):
    """启动API服务器"""
    logger.info(f"启动DAP API服务器: http://{host}:{port}")
    
    uvicorn.run(
        "layer3.api_server:app",
        host=host,
        port=port,
        reload=reload,
        log_level=log_level,
        access_log=True
    )

# 测试函数
if __name__ == "__main__":
    # Start the API server when this file is run directly
    start_api_server()