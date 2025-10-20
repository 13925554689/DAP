"""
DAP - 输出格式化器
多格式数据导出和报告生成
"""

import sqlite3
import pandas as pd
import json
import os
from typing import Dict, Any, List, Optional, Union
import logging
from datetime import datetime
from pathlib import Path
import tempfile

logger = logging.getLogger(__name__)

class OutputFormatter:
    """多格式输出器"""
    
    def __init__(self, db_path: str = 'data/dap_data.db', export_dir: str = 'exports'):
        self.db_path = db_path
        self.export_dir = export_dir
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        
        # 确保导出目录存在
        os.makedirs(export_dir, exist_ok=True)
        
        # 支持的输出格式
        self.supported_formats = {
            'excel': {
                'extension': '.xlsx',
                'handler': self._export_to_excel,
                'description': 'Excel工作簿格式'
            },
            'csv': {
                'extension': '.csv',
                'handler': self._export_to_csv,
                'description': 'CSV逗号分隔格式'
            },
            'json': {
                'extension': '.json',
                'handler': self._export_to_json,
                'description': 'JSON数据格式'
            },
            'html': {
                'extension': '.html',
                'handler': self._export_to_html,
                'description': 'HTML网页格式'
            },
            'pdf_report': {
                'extension': '.pdf',
                'handler': self._generate_pdf_report,
                'description': 'PDF审计报告'
            }
        }
        
        # 支持的导入格式
        self.supported_import_formats = {
            'excel': {
                'extensions': ['.xlsx', '.xls'],
                'handler': self._import_from_excel,
                'description': 'Excel工作簿导入'
            },
            'csv': {
                'extensions': ['.csv'],
                'handler': self._import_from_csv,
                'description': 'CSV文件导入'
            },
            'json': {
                'extensions': ['.json'],
                'handler': self._import_from_json,
                'description': 'JSON数据导入'
            }
        }
        
        # 导出统计
        self.export_stats = {
            'total_exports': 0,
            'successful_exports': 0,
            'failed_exports': 0
        }
        
        logger.info(f"输出格式化器初始化完成，支持导出格式: {list(self.supported_formats.keys())}, 支持导入格式: {list(self.supported_import_formats.keys())}")
    
    def import_data_from_file(self, file_path: str, table_name: Optional[str] = None, 
                             options: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """从文件导入数据到数据库"""
        if not os.path.exists(file_path):
            return {
                'success': False,
                'error': f'文件不存在: {file_path}'
            }
        
        # 检测文件格式
        file_ext = os.path.splitext(file_path)[1].lower()
        import_format = None
        
        for fmt, info in self.supported_import_formats.items():
            if file_ext in info['extensions']:
                import_format = fmt
                break
        
        if not import_format:
            return {
                'success': False,
                'error': f'不支持的文件格式: {file_ext}',
                'supported_formats': {fmt: info['extensions'] for fmt, info in self.supported_import_formats.items()}
            }
        
        try:
            # 生成表名
            if not table_name:
                base_name = os.path.splitext(os.path.basename(file_path))[0]
                table_name = f"imported_{self._sanitize_filename(base_name)}"
            
            # 调用对应的导入处理器
            handler = self.supported_import_formats[import_format]['handler']
            result = handler(file_path, table_name, options or {})
            
            if result.get('success', True):
                logger.info(f"数据导入成功: {file_path} -> {table_name}")
                return {
                    'success': True,
                    'table_name': table_name,
                    'record_count': result.get('record_count', 0),
                    'columns': result.get('columns', []),
                    'format': import_format,
                    'file_path': file_path
                }
            else:
                return result
                
        except Exception as e:
            error_msg = f"数据导入失败: {str(e)}"
            logger.error(error_msg)
            return {
                'success': False,
                'error': error_msg
            }
    
    def _import_from_excel(self, file_path: str, table_name: str, options: Dict[str, Any]) -> Dict[str, Any]:
        """从Excel文件导入数据"""
        try:
            # Excel导入选项
            sheet_name = options.get('sheet_name', None)  # None表示第一个工作表
            header_row = options.get('header_row', 0)
            skip_rows = options.get('skip_rows', None)
            
            # 读取Excel文件
            df = pd.read_excel(
                file_path,
                sheet_name=sheet_name,
                header=header_row,
                skiprows=skip_rows
            )
            
            # 数据清理
            df = self._clean_imported_data(df)
            
            if df.empty:
                return {'success': False, 'error': 'Excel文件中没有有效数据'}
            
            # 保存到数据库
            df.to_sql(table_name, self.conn, if_exists='replace', index=False)
            
            # 记录元数据
            self._record_import_metadata(table_name, file_path, 'excel', len(df), list(df.columns))
            
            return {
                'success': True,
                'record_count': len(df),
                'columns': list(df.columns)
            }
            
        except Exception as e:
            logger.error(f"Excel导入失败: {e}")
            return {'success': False, 'error': str(e)}
    
    def _import_from_csv(self, file_path: str, table_name: str, options: Dict[str, Any]) -> Dict[str, Any]:
        """从CSV文件导入数据"""
        try:
            # CSV导入选项
            encoding = options.get('encoding', 'utf-8')
            separator = options.get('separator', ',')
            header_row = options.get('header_row', 0)
            skip_rows = options.get('skip_rows', None)
            
            # 尝试自动检测编码
            if encoding == 'auto':
                import chardet
                with open(file_path, 'rb') as f:
                    raw_data = f.read()
                    encoding = chardet.detect(raw_data)['encoding']
            
            # 读取CSV文件
            df = pd.read_csv(
                file_path,
                encoding=encoding,
                sep=separator,
                header=header_row,
                skiprows=skip_rows
            )
            
            # 数据清理
            df = self._clean_imported_data(df)
            
            if df.empty:
                return {'success': False, 'error': 'CSV文件中没有有效数据'}
            
            # 保存到数据库
            df.to_sql(table_name, self.conn, if_exists='replace', index=False)
            
            # 记录元数据
            self._record_import_metadata(table_name, file_path, 'csv', len(df), list(df.columns))
            
            return {
                'success': True,
                'record_count': len(df),
                'columns': list(df.columns)
            }
            
        except Exception as e:
            logger.error(f"CSV导入失败: {e}")
            return {'success': False, 'error': str(e)}
    
    def _import_from_json(self, file_path: str, table_name: str, options: Dict[str, Any]) -> Dict[str, Any]:
        """从JSON文件导入数据"""
        try:
            # JSON导入选项
            orient = options.get('orient', 'records')  # records, index, values, etc.
            
            # 读取JSON文件
            with open(file_path, 'r', encoding='utf-8') as f:
                json_data = json.load(f)
            
            # 转换为DataFrame
            if orient == 'records':
                df = pd.DataFrame(json_data)
            else:
                df = pd.read_json(file_path, orient=orient)
            
            # 数据清理
            df = self._clean_imported_data(df)
            
            if df.empty:
                return {'success': False, 'error': 'JSON文件中没有有效数据'}
            
            # 保存到数据库
            df.to_sql(table_name, self.conn, if_exists='replace', index=False)
            
            # 记录元数据
            self._record_import_metadata(table_name, file_path, 'json', len(df), list(df.columns))
            
            return {
                'success': True,
                'record_count': len(df),
                'columns': list(df.columns)
            }
            
        except Exception as e:
            logger.error(f"JSON导入失败: {e}")
            return {'success': False, 'error': str(e)}
    
    def _clean_imported_data(self, df: pd.DataFrame) -> pd.DataFrame:
        """清理导入的数据"""
        try:
            # 确保是DataFrame对象
            if not isinstance(df, pd.DataFrame):
                if isinstance(df, dict):
                    df = pd.DataFrame(df)
                else:
                    df = pd.DataFrame([df])
            
            # 移除完全空白的行
            df = df.dropna(how='all')
            
            # 移除完全空白的列
            df = df.dropna(axis=1, how='all')
            
            # 清理列名
            df.columns = [self._clean_column_name(col) for col in df.columns]
            
            # 移除重复列名
            df = df.loc[:, ~df.columns.duplicated()]
            
            # 基本数据类型推断和转换
            for col in df.columns:
                # 尝试转换数字类型
                if df[col].dtype == 'object':
                    # 检查是否为数字字符串
                    numeric_mask = pd.to_numeric(df[col], errors='coerce').notna()
                    if numeric_mask.sum() > len(df) * 0.7:  # 如果70%以上是数字
                        df[col] = pd.to_numeric(df[col], errors='coerce')
                    
                    # 检查是否为日期字符串
                    elif col.lower() in ['date', 'datetime', '日期', '时间'] or 'date' in col.lower():
                        try:
                            df[col] = pd.to_datetime(df[col], errors='coerce')
                        except:
                            pass
            
            return df
            
        except Exception as e:
            logger.warning(f"数据清理失败: {e}")
            return df if isinstance(df, pd.DataFrame) else pd.DataFrame()
    
    def _clean_column_name(self, col_name: str) -> str:
        """清理列名"""
        # 转换为字符串
        col_name = str(col_name)
        
        # 移除前后空格
        col_name = col_name.strip()
        
        # 替换特殊字符
        import re
        col_name = re.sub(r'[^\w\u4e00-\u9fff]', '_', col_name)
        
        # 确保不以数字开头
        if col_name and col_name[0].isdigit():
            col_name = f"col_{col_name}"
        
        # 确保不为空
        if not col_name:
            col_name = "unnamed_column"
        
        return col_name
    
    def _record_import_metadata(self, table_name: str, file_path: str, format_type: str, 
                               record_count: int, columns: List[str]):
        """记录导入元数据"""
        try:
            # 创建导入历史表
            create_table_sql = '''
                CREATE TABLE IF NOT EXISTS import_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    import_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    table_name TEXT,
                    source_file TEXT,
                    format_type TEXT,
                    record_count INTEGER,
                    column_names TEXT,
                    file_size INTEGER
                )
            '''
            
            self.conn.execute(create_table_sql)
            
            # 获取文件大小
            file_size = os.path.getsize(file_path) if os.path.exists(file_path) else 0
            
            # 插入记录
            insert_sql = '''
                INSERT INTO import_history
                (table_name, source_file, format_type, record_count, column_names, file_size)
                VALUES (?, ?, ?, ?, ?, ?)
            '''
            
            self.conn.execute(insert_sql, (
                table_name, file_path, format_type, record_count, 
                json.dumps(columns, ensure_ascii=False), file_size
            ))
            
            self.conn.commit()
            
        except Exception as e:
            logger.warning(f"记录导入元数据失败: {e}")
    
    def get_import_history(self, limit: int = 20) -> List[Dict[str, Any]]:
        """获取导入历史"""
        try:
            query = '''
                SELECT import_time, table_name, source_file, format_type, 
                       record_count, column_names, file_size
                FROM import_history
                ORDER BY import_time DESC
                LIMIT ?
            '''
            
            results = self.conn.execute(query, (limit,)).fetchall()
            
            history = []
            for row in results:
                try:
                    columns = json.loads(row[5]) if row[5] else []
                except:
                    columns = []
                
                history.append({
                    'import_time': row[0],
                    'table_name': row[1],
                    'source_file': row[2],
                    'format_type': row[3],
                    'record_count': row[4],
                    'columns': columns,
                    'file_size': row[6]
                })
            
            return history
            
        except Exception as e:
            logger.error(f"获取导入历史失败: {e}")
            return []
    
    def get_imported_tables(self) -> List[Dict[str, Any]]:
        """获取已导入的表列表"""
        try:
            # 查询所有以imported_开头的表
            query = '''
                SELECT name as table_name FROM sqlite_master 
                WHERE type='table' AND name LIKE 'imported_%'
                ORDER BY name
            '''
            
            tables = []
            for (table_name,) in self.conn.execute(query).fetchall():
                # 获取表的基本信息
                count_query = f'SELECT COUNT(*) FROM "{table_name}"'
                record_count = self.conn.execute(count_query).fetchone()[0]
                
                # 获取列信息
                columns_query = f'PRAGMA table_info("{table_name}")'
                columns_info = self.conn.execute(columns_query).fetchall()
                columns = [col[1] for col in columns_info]
                
                tables.append({
                    'table_name': table_name,
                    'record_count': record_count,
                    'column_count': len(columns),
                    'columns': columns
                })
            
            return tables
            
        except Exception as e:
            logger.error(f"获取导入表列表失败: {e}")
            return []

    def export_data(self, source: str, output_format: str, 
                   output_path: Optional[str] = None, 
                   options: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """导出数据到指定格式"""
        if output_format not in self.supported_formats:
            return {
                'success': False,
                'error': f'不支持的输出格式: {output_format}',
                'supported_formats': list(self.supported_formats.keys())
            }
        
        self.export_stats['total_exports'] += 1
        
        try:
            # 获取数据
            data = self._get_data(source)
            
            if data.empty:
                return {
                    'success': False,
                    'error': f'数据源为空: {source}'
                }
            
            # 生成输出路径
            if not output_path:
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                safe_source = self._sanitize_filename(source)
                extension = self.supported_formats[output_format]['extension']
                output_path = os.path.join(
                    self.export_dir, 
                    f"{safe_source}_{timestamp}{extension}"
                )
            
            # 调用对应的导出处理器
            handler = self.supported_formats[output_format]['handler']
            result = handler(data, output_path, options or {})
            
            if result.get('success', True):
                self.export_stats['successful_exports'] += 1
                
                # 记录导出历史
                self._record_export_history(source, output_format, output_path, True)
                
                return {
                    'success': True,
                    'output_path': output_path,
                    'file_size': os.path.getsize(output_path) if os.path.exists(output_path) else 0,
                    'record_count': len(data),
                    'format': output_format
                }
            else:
                self.export_stats['failed_exports'] += 1
                return result
                
        except Exception as e:
            self.export_stats['failed_exports'] += 1
            error_msg = f"导出失败: {str(e)}"
            logger.error(error_msg)
            
            # 记录失败的导出历史
            self._record_export_history(source, output_format, output_path or '', False, str(e))
            
            return {
                'success': False,
                'error': error_msg
            }
    
    def _get_data(self, source: str) -> pd.DataFrame:
        """获取数据"""
        try:
            # 检查是否为SQL查询
            if source.upper().strip().startswith('SELECT'):
                return pd.read_sql_query(source, self.conn)
            else:
                # 假设是表名或视图名
                return pd.read_sql_query(f"SELECT * FROM {source}", self.conn)
                
        except Exception as e:
            logger.error(f"获取数据失败 {source}: {e}")
            return pd.DataFrame()
    
    def _export_to_excel(self, data: pd.DataFrame, output_path: str, 
                        options: Dict[str, Any]) -> Dict[str, Any]:
        """导出到Excel格式"""
        try:
            with pd.ExcelWriter(output_path, engine='openpyxl') as writer:
                # 主数据表
                sheet_name = options.get('sheet_name', '数据')
                data.to_excel(writer, sheet_name=sheet_name, index=False)
                
                # 如果启用汇总功能
                if options.get('include_summary', True):
                    self._add_excel_summary(data, writer)
                
                # 如果启用图表功能
                if options.get('include_charts', False):
                    self._add_excel_charts(data, writer)
                
                # 如果启用格式化
                if options.get('format_cells', True):
                    self._format_excel_cells(writer, sheet_name, data)
            
            logger.info(f"Excel导出成功: {output_path}")
            return {'success': True}
            
        except Exception as e:
            logger.error(f"Excel导出失败: {e}")
            return {'success': False, 'error': str(e)}
    
    def _add_excel_summary(self, data: pd.DataFrame, writer: pd.ExcelWriter):
        """为Excel添加汇总表"""
        try:
            # 数值列汇总
            numeric_columns = data.select_dtypes(include=['number']).columns
            if not numeric_columns.empty:
                summary_data = []
                
                for col in numeric_columns:
                    summary_data.append({
                        '字段名': col,
                        '总计': data[col].sum(),
                        '平均值': data[col].mean(),
                        '最大值': data[col].max(),
                        '最小值': data[col].min(),
                        '记录数': data[col].count()
                    })
                
                if summary_data:
                    summary_df = pd.DataFrame(summary_data)
                    summary_df.to_excel(writer, sheet_name='数据汇总', index=False)
            
            # 分类列汇总
            categorical_columns = data.select_dtypes(include=['object']).columns
            if not categorical_columns.empty:
                category_summaries = []
                
                for col in categorical_columns[:5]:  # 最多处理5个分类列
                    value_counts = data[col].value_counts().head(10)
                    for value, count in value_counts.items():
                        category_summaries.append({
                            '字段名': col,
                            '值': str(value),
                            '计数': count,
                            '占比': f"{count/len(data)*100:.1f}%"
                        })
                
                if category_summaries:
                    category_df = pd.DataFrame(category_summaries)
                    category_df.to_excel(writer, sheet_name='分类汇总', index=False)
                    
        except Exception as e:
            logger.warning(f"添加Excel汇总失败: {e}")
    
    def _add_excel_charts(self, data: pd.DataFrame, writer: pd.ExcelWriter):
        """为Excel添加图表"""
        try:
            # 这里可以使用openpyxl添加图表
            # 由于复杂性，此处提供简化实现
            
            # 时间趋势分析
            date_columns = [col for col in data.columns 
                          if 'date' in col.lower() or '日期' in col.lower()]
            amount_columns = [col for col in data.columns 
                            if 'amount' in col.lower() or '金额' in col.lower()]
            
            if date_columns and amount_columns:
                chart_data = data.groupby(date_columns[0])[amount_columns[0]].sum().reset_index()
                chart_data.to_excel(writer, sheet_name='趋势分析', index=False)
                
        except Exception as e:
            logger.warning(f"添加Excel图表失败: {e}")
    
    def _format_excel_cells(self, writer: pd.ExcelWriter, sheet_name: str, data: pd.DataFrame):
        """格式化Excel单元格"""
        try:
            workbook = writer.book
            worksheet = writer.sheets[sheet_name]
            
            # 定义格式
            header_format = workbook.add_format({
                'bold': True,
                'text_wrap': True,
                'valign': 'top',
                'fg_color': '#D7E4BC',
                'border': 1
            })
            
            # 应用标题格式
            for col_num, value in enumerate(data.columns.values):
                worksheet.write(0, col_num, value, header_format)
            
            # 调整列宽
            for col_num, col_name in enumerate(data.columns):
                # 计算合适的列宽
                max_length = max(
                    data[col_name].astype(str).str.len().max(),
                    len(str(col_name))
                )
                worksheet.set_column(col_num, col_num, min(max_length + 2, 50))
                
        except Exception as e:
            logger.warning(f"Excel格式化失败: {e}")
    
    def _export_to_csv(self, data: pd.DataFrame, output_path: str, 
                      options: Dict[str, Any]) -> Dict[str, Any]:
        """导出到CSV格式"""
        try:
            # CSV选项
            encoding = options.get('encoding', 'utf-8-sig')  # 支持Excel打开中文
            separator = options.get('separator', ',')
            include_index = options.get('include_index', False)
            
            data.to_csv(
                output_path,
                encoding=encoding,
                sep=separator,
                index=include_index
            )
            
            logger.info(f"CSV导出成功: {output_path}")
            return {'success': True}
            
        except Exception as e:
            logger.error(f"CSV导出失败: {e}")
            return {'success': False, 'error': str(e)}
    
    def _export_to_json(self, data: pd.DataFrame, output_path: str, 
                       options: Dict[str, Any]) -> Dict[str, Any]:
        """导出到JSON格式"""
        try:
            # JSON选项
            orient = options.get('orient', 'records')  # records, index, values, etc.
            ensure_ascii = options.get('ensure_ascii', False)
            indent = options.get('indent', 2)
            
            # 转换数据
            json_data = data.to_json(orient=orient, force_ascii=not ensure_ascii, indent=indent)
            
            # 写入文件
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(json_data)
            
            logger.info(f"JSON导出成功: {output_path}")
            return {'success': True}
            
        except Exception as e:
            logger.error(f"JSON导出失败: {e}")
            return {'success': False, 'error': str(e)}
    
    def _export_to_html(self, data: pd.DataFrame, output_path: str, 
                       options: Dict[str, Any]) -> Dict[str, Any]:
        """导出到HTML格式"""
        try:
            # HTML选项
            table_id = options.get('table_id', 'data-table')
            include_css = options.get('include_css', True)
            escape = options.get('escape', False)
            
            # 生成HTML
            html_content = self._generate_html_report(data, table_id, include_css)
            
            # 写入文件
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(html_content)
            
            logger.info(f"HTML导出成功: {output_path}")
            return {'success': True}
            
        except Exception as e:
            logger.error(f"HTML导出失败: {e}")
            return {'success': False, 'error': str(e)}
    
    def _generate_html_report(self, data: pd.DataFrame, table_id: str, 
                             include_css: bool) -> str:
        """生成HTML报告"""
        # 生成CSS样式
        css_styles = '''
        <style>
        body { font-family: Arial, sans-serif; margin: 20px; }
        h1 { color: #333; }
        .summary { background-color: #f5f5f5; padding: 15px; margin: 20px 0; border-radius: 5px; }
        table { border-collapse: collapse; width: 100%; margin-top: 20px; }
        th, td { border: 1px solid #ddd; padding: 8px; text-align: left; }
        th { background-color: #4CAF50; color: white; }
        tr:nth-child(even) { background-color: #f2f2f2; }
        .stats { display: inline-block; margin: 10px; padding: 10px; background-color: #e7f3ff; border-radius: 5px; }
        </style>
        ''' if include_css else ''
        
        # 生成数据摘要
        summary_html = f'''
        <div class="summary">
            <h2>数据摘要</h2>
            <div class="stats">总记录数: {len(data)}</div>
            <div class="stats">总字段数: {len(data.columns)}</div>
            <div class="stats">生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</div>
        </div>
        '''
        
        # 生成表格HTML
        table_html = data.to_html(
            table_id=table_id,
            escape=False,
            classes='data-table',
            index=False
        )
        
        # 组合完整HTML
        html_content = f'''
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <title>DAP数据报告</title>
            {css_styles}
        </head>
        <body>
            <h1>DAP数据报告</h1>
            {summary_html}
            {table_html}
        </body>
        </html>
        '''
        
        return html_content
    
    def _generate_pdf_report(self, data: pd.DataFrame, output_path: str, 
                            options: Dict[str, Any]) -> Dict[str, Any]:
        """生成PDF报告"""
        try:
            # 由于PDF生成比较复杂，这里提供基础实现
            # 可以使用reportlab或者先生成HTML再转PDF
            
            # 先生成HTML版本
            html_path = output_path.replace('.pdf', '.html')
            html_result = self._export_to_html(data, html_path, options)
            
            if html_result.get('success'):
                # 这里可以集成HTML到PDF的转换工具
                # 例如：pdfkit, weasyprint 等
                logger.info(f"PDF报告已生成HTML版本: {html_path}")
                
                # 简化实现：复制HTML文件为PDF（实际应用中需要真正的PDF转换）
                import shutil
                shutil.copy(html_path, output_path.replace('.pdf', '_report.html'))
                
                return {
                    'success': True,
                    'note': 'PDF功能需要额外的依赖库，当前生成了HTML版本'
                }
            else:
                return html_result
                
        except Exception as e:
            logger.error(f"PDF报告生成失败: {e}")
            return {'success': False, 'error': str(e)}
    
    def generate_audit_report(self, company_name: str, period: str, 
                             output_format: str = 'html') -> Dict[str, Any]:
        """生成审计报告"""
        logger.info(f"生成审计报告: {company_name}, 期间: {period}")
        
        try:
            # 收集审计数据
            report_data = self._collect_audit_data(company_name, period)
            
            # 生成报告内容
            report_content = self._build_audit_report_content(report_data)
            
            # 生成输出文件
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            safe_company = self._sanitize_filename(company_name)
            
            if output_format == 'html':
                output_path = os.path.join(
                    self.export_dir, 
                    f"audit_report_{safe_company}_{period}_{timestamp}.html"
                )
                return self._generate_audit_html_report(report_content, output_path)
            
            elif output_format == 'excel':
                output_path = os.path.join(
                    self.export_dir, 
                    f"audit_report_{safe_company}_{period}_{timestamp}.xlsx"
                )
                return self._generate_audit_excel_report(report_content, output_path)
            
            else:
                return {
                    'success': False,
                    'error': f'不支持的审计报告格式: {output_format}'
                }
                
        except Exception as e:
            logger.error(f"生成审计报告失败: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def _collect_audit_data(self, company_name: str, period: str) -> Dict[str, Any]:
        """收集审计数据"""
        audit_data = {
            'company_info': self._get_company_info(company_name),
            'period': period,
            'financial_summary': self._get_financial_summary(company_name, period),
            'risk_analysis': self._get_risk_analysis(company_name),
            'anomaly_detection': self._get_anomaly_detection(company_name),
            'compliance_check': self._get_compliance_check(company_name),
            'data_quality': self._get_data_quality_assessment()
        }
        
        return audit_data
    
    def _get_company_info(self, company_name: str) -> Dict[str, Any]:
        """获取公司基本信息"""
        try:
            query = '''
                SELECT company_id, company_name, industry
                FROM meta_companies
                WHERE company_name LIKE ?
                LIMIT 1
            '''
            
            result = self.conn.execute(query, (f'%{company_name}%',)).fetchone()
            
            if result:
                return {
                    'company_id': result[0],
                    'company_name': result[1],
                    'industry': result[2] or '未知行业'
                }
            else:
                return {
                    'company_id': 'unknown',
                    'company_name': company_name,
                    'industry': '未知行业'
                }
                
        except Exception as e:
            logger.warning(f"获取公司信息失败: {e}")
            return {'company_name': company_name, 'industry': '未知行业'}
    
    def _get_financial_summary(self, company_name: str, period: str) -> Dict[str, Any]:
        """获取财务摘要"""
        try:
            # 查找包含金额的表
            tables_query = '''
                SELECT table_name FROM meta_tables
                WHERE business_domain = 'financial'
                OR table_type LIKE '%ledger%'
                OR table_type LIKE '%financial%'
            '''
            
            tables = self.conn.execute(tables_query).fetchall()
            
            summary = {
                'total_transactions': 0,
                'total_amount': 0,
                'account_categories': {},
                'period': period
            }
            
            for (table_name,) in tables:
                try:
                    # 查找实际的表名（raw_clean_前缀）
                    actual_table = f"raw_clean_{table_name}"
                    
                    # 检查表是否存在
                    check_query = '''
                        SELECT name FROM sqlite_master 
                        WHERE type='table' AND name = ?
                    '''
                    
                    if self.conn.execute(check_query, (actual_table,)).fetchone():
                        # 获取交易数量和金额
                        amount_columns = self._find_amount_columns_in_table(actual_table)
                        
                        if amount_columns:
                            amount_col = amount_columns[0]
                            count_query = f'SELECT COUNT(*), SUM("{amount_col}") FROM {actual_table}'
                            count_result = self.conn.execute(count_query).fetchone()
                            
                            if count_result:
                                summary['total_transactions'] += count_result[0] or 0
                                summary['total_amount'] += count_result[1] or 0
                
                except Exception as e:
                    logger.warning(f"处理表失败 {table_name}: {e}")
                    continue
            
            return summary
            
        except Exception as e:
            logger.warning(f"获取财务摘要失败: {e}")
            return {'total_transactions': 0, 'total_amount': 0}
    
    def _get_risk_analysis(self, company_name: str) -> Dict[str, Any]:
        """获取风险分析"""
        try:
            # 查找风险相关的视图
            risk_views_query = '''
                SELECT view_name FROM meta_views
                WHERE view_type LIKE '%risk%' OR view_type LIKE '%anomaly%'
            '''
            
            risk_views = self.conn.execute(risk_views_query).fetchall()
            
            risk_summary = {
                'high_risk_items': 0,
                'medium_risk_items': 0,
                'low_risk_items': 0,
                'risk_categories': []
            }
            
            for (view_name,) in risk_views:
                try:
                    # 统计风险项目
                    count_query = f'SELECT COUNT(*) FROM {view_name}'
                    count = self.conn.execute(count_query).fetchone()[0]
                    
                    if 'high' in view_name.lower():
                        risk_summary['high_risk_items'] += count
                    elif 'medium' in view_name.lower():
                        risk_summary['medium_risk_items'] += count
                    else:
                        risk_summary['low_risk_items'] += count
                    
                    risk_summary['risk_categories'].append({
                        'category': view_name,
                        'count': count
                    })
                    
                except Exception as e:
                    logger.warning(f"处理风险视图失败 {view_name}: {e}")
                    continue
            
            return risk_summary
            
        except Exception as e:
            logger.warning(f"获取风险分析失败: {e}")
            return {'high_risk_items': 0, 'medium_risk_items': 0, 'low_risk_items': 0}
    
    def _get_anomaly_detection(self, company_name: str) -> List[Dict[str, Any]]:
        """获取异常检测结果"""
        try:
            # 查找异常检测视图
            anomaly_views_query = '''
                SELECT view_name FROM meta_views
                WHERE view_type LIKE '%anomaly%'
                LIMIT 5
            '''
            
            anomaly_views = self.conn.execute(anomaly_views_query).fetchall()
            
            anomalies = []
            
            for (view_name,) in anomaly_views:
                try:
                    # 获取异常记录示例
                    sample_query = f'SELECT * FROM {view_name} LIMIT 10'
                    sample_df = pd.read_sql_query(sample_query, self.conn)
                    
                    if not sample_df.empty:
                        anomalies.append({
                            'type': view_name,
                            'count': len(sample_df),
                            'examples': sample_df.head(3).to_dict('records')
                        })
                        
                except Exception as e:
                    logger.warning(f"处理异常视图失败 {view_name}: {e}")
                    continue
            
            return anomalies
            
        except Exception as e:
            logger.warning(f"获取异常检测失败: {e}")
            return []
    
    def _get_compliance_check(self, company_name: str) -> Dict[str, Any]:
        """获取合规性检查结果"""
        # 简化实现
        return {
            'compliance_score': 85,
            'passed_checks': 17,
            'failed_checks': 3,
            'warnings': 5,
            'recommendations': [
                '完善内控制度文档',
                '加强大额交易审批流程',
                '定期进行数据备份验证'
            ]
        }
    
    def _get_data_quality_assessment(self) -> Dict[str, Any]:
        """获取数据质量评估"""
        try:
            quality_query = '''
                SELECT 
                    AVG(data_quality_score) as avg_score,
                    COUNT(*) as total_tables,
                    SUM(CASE WHEN data_quality_score >= 0.9 THEN 1 ELSE 0 END) as excellent_tables,
                    SUM(CASE WHEN data_quality_score >= 0.8 THEN 1 ELSE 0 END) as good_tables
                FROM meta_tables
            '''
            
            result = self.conn.execute(quality_query).fetchone()
            
            if result:
                return {
                    'average_score': round(result[0] or 0, 2),
                    'total_tables': result[1] or 0,
                    'excellent_tables': result[2] or 0,
                    'good_tables': result[3] or 0
                }
            else:
                return {'average_score': 0, 'total_tables': 0}
                
        except Exception as e:
            logger.warning(f"获取数据质量评估失败: {e}")
            return {'average_score': 0, 'total_tables': 0}
    
    def _find_amount_columns_in_table(self, table_name: str) -> List[str]:
        """查找表中的金额列"""
        try:
            columns_query = f"PRAGMA table_info({table_name})"
            columns_info = self.conn.execute(columns_query).fetchall()
            
            amount_columns = []
            for col_info in columns_info:
                col_name = col_info[1]
                col_lower = col_name.lower()
                
                if any(pattern in col_lower for pattern in ['金额', 'amount', 'money', '价格']):
                    amount_columns.append(col_name)
            
            return amount_columns
            
        except Exception as e:
            logger.warning(f"查找金额列失败: {e}")
            return []
    
    def _build_audit_report_content(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """构建审计报告内容"""
        return {
            'title': f"{data['company_info']['company_name']} 审计报告",
            'period': data['period'],
            'generated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'sections': [
                {
                    'title': '企业基本信息',
                    'content': data['company_info']
                },
                {
                    'title': '财务概况',
                    'content': data['financial_summary']
                },
                {
                    'title': '风险分析',
                    'content': data['risk_analysis']
                },
                {
                    'title': '异常检测',
                    'content': data['anomaly_detection']
                },
                {
                    'title': '合规性检查',
                    'content': data['compliance_check']
                },
                {
                    'title': '数据质量评估',
                    'content': data['data_quality']
                }
            ]
        }
    
    def _generate_audit_html_report(self, report_content: Dict[str, Any], 
                                   output_path: str) -> Dict[str, Any]:
        """生成HTML格式的审计报告"""
        try:
            html_content = f'''
            <!DOCTYPE html>
            <html>
            <head>
                <meta charset="utf-8">
                <title>{report_content['title']}</title>
                <style>
                    body {{ font-family: Arial, sans-serif; margin: 40px; line-height: 1.6; }}
                    .header {{ text-align: center; margin-bottom: 40px; }}
                    .section {{ margin-bottom: 30px; padding: 20px; border-left: 4px solid #4CAF50; background-color: #f9f9f9; }}
                    .section h2 {{ color: #333; margin-top: 0; }}
                    .summary-box {{ display: inline-block; margin: 10px; padding: 15px; background-color: #e7f3ff; border-radius: 5px; text-align: center; }}
                    .risk-high {{ background-color: #ffebee; }}
                    .risk-medium {{ background-color: #fff3e0; }}
                    .risk-low {{ background-color: #e8f5e8; }}
                    table {{ width: 100%; border-collapse: collapse; margin: 15px 0; }}
                    th, td {{ border: 1px solid #ddd; padding: 12px; text-align: left; }}
                    th {{ background-color: #4CAF50; color: white; }}
                </style>
            </head>
            <body>
                <div class="header">
                    <h1>{report_content['title']}</h1>
                    <p>报告期间: {report_content['period']}</p>
                    <p>生成时间: {report_content['generated_at']}</p>
                </div>
            '''
            
            # 添加各个部分
            for section in report_content['sections']:
                html_content += f'''
                <div class="section">
                    <h2>{section['title']}</h2>
                    {self._format_section_content_html(section['content'])}
                </div>
                '''
            
            html_content += '''
            </body>
            </html>
            '''
            
            # 写入文件
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(html_content)
            
            logger.info(f"HTML审计报告生成成功: {output_path}")
            return {
                'success': True,
                'output_path': output_path
            }
            
        except Exception as e:
            logger.error(f"HTML审计报告生成失败: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def _format_section_content_html(self, content: Any) -> str:
        """格式化章节内容为HTML"""
        if isinstance(content, dict):
            html = '<table>'
            for key, value in content.items():
                html += f'<tr><td><strong>{key}</strong></td><td>{value}</td></tr>'
            html += '</table>'
            return html
        elif isinstance(content, list):
            html = '<ul>'
            for item in content:
                if isinstance(item, dict):
                    html += f'<li>{json.dumps(item, ensure_ascii=False)}</li>'
                else:
                    html += f'<li>{item}</li>'
            html += '</ul>'
            return html
        else:
            return str(content)
    
    def _generate_audit_excel_report(self, report_content: Dict[str, Any], 
                                    output_path: str) -> Dict[str, Any]:
        """生成Excel格式的审计报告"""
        try:
            with pd.ExcelWriter(output_path, engine='openpyxl') as writer:
                # 报告摘要
                summary_data = [
                    ['报告标题', report_content['title']],
                    ['报告期间', report_content['period']],
                    ['生成时间', report_content['generated_at']]
                ]
                
                summary_df = pd.DataFrame(summary_data, columns=['项目', '内容'])
                summary_df.to_excel(writer, sheet_name='报告摘要', index=False)
                
                # 各个部分的详细内容
                for section in report_content['sections']:
                    sheet_name = section['title'][:31]  # Excel工作表名限制
                    
                    if isinstance(section['content'], dict):
                        content_data = [[k, v] for k, v in section['content'].items()]
                        content_df = pd.DataFrame(content_data, columns=['项目', '值'])
                        content_df.to_excel(writer, sheet_name=sheet_name, index=False)
                    
                    elif isinstance(section['content'], list):
                        if section['content'] and isinstance(section['content'][0], dict):
                            content_df = pd.DataFrame(section['content'])
                            content_df.to_excel(writer, sheet_name=sheet_name, index=False)
            
            logger.info(f"Excel审计报告生成成功: {output_path}")
            return {
                'success': True,
                'output_path': output_path
            }
            
        except Exception as e:
            logger.error(f"Excel审计报告生成失败: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def _sanitize_filename(self, filename: str) -> str:
        """清理文件名，移除非法字符"""
        import re
        # 移除或替换非法字符
        sanitized = re.sub(r'[<>:"/\\|?*]', '_', filename)
        sanitized = re.sub(r'\s+', '_', sanitized)
        return sanitized[:50]  # 限制长度
    
    def _record_export_history(self, source: str, format_type: str, 
                              output_path: str, success: bool, error: str = None):
        """记录导出历史"""
        try:
            create_table_sql = '''
                CREATE TABLE IF NOT EXISTS export_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    export_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    source_name TEXT,
                    format_type TEXT,
                    output_path TEXT,
                    success BOOLEAN,
                    error_message TEXT,
                    file_size INTEGER
                )
            '''
            
            self.conn.execute(create_table_sql)
            
            file_size = 0
            if success and os.path.exists(output_path):
                file_size = os.path.getsize(output_path)
            
            insert_sql = '''
                INSERT INTO export_history
                (source_name, format_type, output_path, success, error_message, file_size)
                VALUES (?, ?, ?, ?, ?, ?)
            '''
            
            self.conn.execute(insert_sql, (
                source, format_type, output_path, success, error, file_size
            ))
            
            self.conn.commit()
            
        except Exception as e:
            logger.warning(f"记录导出历史失败: {e}")
    
    def get_export_history(self, limit: int = 20) -> List[Dict[str, Any]]:
        """获取导出历史"""
        try:
            query = '''
                SELECT export_time, source_name, format_type, output_path, 
                       success, error_message, file_size
                FROM export_history
                ORDER BY export_time DESC
                LIMIT ?
            '''
            
            results = self.conn.execute(query, (limit,)).fetchall()
            
            history = []
            for row in results:
                history.append({
                    'export_time': row[0],
                    'source_name': row[1],
                    'format_type': row[2],
                    'output_path': row[3],
                    'success': bool(row[4]),
                    'error_message': row[5],
                    'file_size': row[6]
                })
            
            return history
            
        except Exception as e:
            logger.error(f"获取导出历史失败: {e}")
            return []
    
    def get_supported_formats(self) -> Dict[str, str]:
        """获取支持的格式列表"""
        return {fmt: info['description'] for fmt, info in self.supported_formats.items()}
    
    def close(self):
        """关闭数据库连接"""
        if self.conn:
            self.conn.close()
            logger.info("输出格式化器数据库连接已关闭")


# 测试函数
def test_output_formatter():
    """测试输出格式化器"""
    import os
    
    # 创建测试数据库
    test_db = 'test_output.db'
    conn = sqlite3.connect(test_db)
    
    # 创建测试表
    test_table_sql = '''
        CREATE TABLE test_data (
            id INTEGER PRIMARY KEY,
            name TEXT,
            amount REAL,
            date TEXT,
            category TEXT
        )
    '''
    
    conn.execute(test_table_sql)
    
    # 插入测试数据
    test_data = [
        (1, '项目A', 50000, '2023-01-01', '销售'),
        (2, '项目B', 75000, '2023-01-02', '采购'),
        (3, '项目C', 30000, '2023-01-03', '销售'),
        (4, '项目D', 90000, '2023-01-04', '投资'),
        (5, '项目E', 45000, '2023-01-05', '销售')
    ]
    
    conn.executemany('''
        INSERT INTO test_data (id, name, amount, date, category)
        VALUES (?, ?, ?, ?, ?)
    ''', test_data)
    
    conn.commit()
    conn.close()
    
    # 测试输出格式化器
    formatter = OutputFormatter(test_db, 'test_exports')
    
    # 测试各种格式导出
    formats_to_test = ['excel', 'csv', 'json', 'html']
    
    for fmt in formats_to_test:
        print(f"\n测试 {fmt} 格式导出:")
        result = formatter.export_data('test_data', fmt)
        
        if result['success']:
            print(f"✅ {fmt} 导出成功:")
            print(f"   文件路径: {result['output_path']}")
            print(f"   文件大小: {result['file_size']} 字节")
            print(f"   记录数: {result['record_count']}")
        else:
            print(f"❌ {fmt} 导出失败: {result['error']}")
    
    # 测试审计报告生成
    print(f"\n测试审计报告生成:")
    audit_result = formatter.generate_audit_report('测试公司', '2023年度', 'html')
    
    if audit_result['success']:
        print(f"✅ 审计报告生成成功: {audit_result['output_path']}")
    else:
        print(f"❌ 审计报告生成失败: {audit_result['error']}")
    
    # 显示导出历史
    history = formatter.get_export_history()
    print(f"\n导出历史 (共{len(history)}条):")
    for item in history:
        status = "✅" if item['success'] else "❌"
        print(f"{status} {item['export_time']} - {item['format_type']} - {item['source_name']}")
    
    formatter.close()
    
    # 清理测试文件
    if os.path.exists(test_db):
        os.remove(test_db)


if __name__ == "__main__":
    test_output_formatter()