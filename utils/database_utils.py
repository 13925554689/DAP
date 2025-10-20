"""
DAP - 数据库工具模块
提供数据库操作的通用工具和优化函数
"""

import sqlite3
import pandas as pd
import os
import logging
from typing import Dict, Any, List, Optional, Tuple
from pathlib import Path
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
import time

logger = logging.getLogger(__name__)

class DatabaseOptimizer:
    """数据库性能优化器"""
    
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self._lock = threading.Lock()
        
    def optimize_database(self) -> Dict[str, Any]:
        """优化数据库性能"""
        try:
            optimization_results = {
                'vacuum_result': False,
                'analyze_result': False,
                'index_result': False,
                'pragma_result': False
            }
            
            with self._lock:
                # 1. VACUUM - 重组数据库文件
                logger.info("执行VACUUM优化...")
                self.conn.execute("VACUUM")
                optimization_results['vacuum_result'] = True
                
                # 2. ANALYZE - 更新查询优化器统计信息
                logger.info("执行ANALYZE优化...")
                self.conn.execute("ANALYZE")
                optimization_results['analyze_result'] = True
                
                # 3. 创建关键索引
                logger.info("创建关键索引...")
                self._create_key_indexes()
                optimization_results['index_result'] = True
                
                # 4. 设置性能相关的PRAGMA
                logger.info("优化PRAGMA设置...")
                self._optimize_pragma_settings()
                optimization_results['pragma_result'] = True
                
                self.conn.commit()
                
            logger.info("数据库优化完成")
            return {
                'success': True,
                'optimizations': optimization_results,
                'message': '数据库性能优化完成'
            }
            
        except Exception as e:
            logger.error(f"数据库优化失败: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def _create_key_indexes(self):
        """创建关键索引"""
        try:
            # 获取所有表名
            tables = self._get_table_names()
            
            for table_name in tables:
                if table_name.startswith('raw_clean_'):
                    # 为清理后的数据表创建索引
                    self._create_table_indexes(table_name)
                    
        except Exception as e:
            logger.warning(f"创建索引失败: {e}")
    
    def _create_table_indexes(self, table_name: str):
        """为表创建索引"""
        try:
            # 获取表列信息
            columns_info = self.conn.execute(f"PRAGMA table_info({table_name})").fetchall()
            columns = [col[1] for col in columns_info]
            
            # 为常用的列创建索引
            index_candidates = []
            
            for col in columns:
                col_lower = col.lower()
                # 科目编码索引
                if '科目' in col and ('编码' in col or 'code' in col_lower):
                    index_candidates.append(col)
                # 日期索引
                elif '日期' in col or 'date' in col_lower:
                    index_candidates.append(col)
                # ID索引
                elif col_lower.endswith('id') or '编号' in col:
                    index_candidates.append(col)
            
            # 创建单列索引
            for col in index_candidates:
                try:
                    index_name = f"idx_{table_name}_{col.replace(' ', '_')}"
                    sql = f"CREATE INDEX IF NOT EXISTS {index_name} ON {table_name} ({col})"
                    self.conn.execute(sql)
                except Exception as e:
                    logger.debug(f"创建索引 {index_name} 失败: {e}")
                    
        except Exception as e:
            logger.warning(f"为表 {table_name} 创建索引失败: {e}")
    
    def _optimize_pragma_settings(self):
        """优化PRAGMA设置"""
        pragma_settings = [
            "PRAGMA synchronous = NORMAL",  # 平衡性能和安全性
            "PRAGMA journal_mode = WAL",    # 使用WAL模式提升并发性能
            "PRAGMA cache_size = -64000",   # 缓存大小64MB
            "PRAGMA temp_store = MEMORY",   # 临时表存储在内存中
            "PRAGMA mmap_size = 268435456", # 内存映射大小256MB
            "PRAGMA optimize"               # 自动优化
        ]
        
        for pragma in pragma_settings:
            try:
                self.conn.execute(pragma)
            except Exception as e:
                logger.debug(f"执行PRAGMA失败 {pragma}: {e}")
    
    def _get_table_names(self) -> List[str]:
        """获取所有表名"""
        try:
            cursor = self.conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
            )
            return [row[0] for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"获取表名失败: {e}")
            return []
    
    def get_database_stats(self) -> Dict[str, Any]:
        """获取数据库统计信息"""
        try:
            stats = {}
            
            # 数据库文件大小
            stats['file_size'] = os.path.getsize(self.db_path)
            
            # 表数量
            tables = self._get_table_names()
            stats['table_count'] = len(tables)
            
            # 总记录数
            total_records = 0
            for table_name in tables:
                try:
                    cursor = self.conn.execute(f"SELECT COUNT(*) FROM {table_name}")
                    count = cursor.fetchone()[0]
                    total_records += count
                except:
                    pass
            
            stats['total_records'] = total_records
            
            # 索引数量
            cursor = self.conn.execute(
                "SELECT COUNT(*) FROM sqlite_master WHERE type='index' AND name NOT LIKE 'sqlite_%'"
            )
            stats['index_count'] = cursor.fetchone()[0]
            
            # 视图数量
            cursor = self.conn.execute(
                "SELECT COUNT(*) FROM sqlite_master WHERE type='view'"
            )
            stats['view_count'] = cursor.fetchone()[0]
            
            return stats
            
        except Exception as e:
            logger.error(f"获取数据库统计失败: {e}")
            return {}
    
    def close(self):
        """关闭数据库连接"""
        if self.conn:
            self.conn.close()


class ParallelDataProcessor:
    """并行数据处理器"""
    
    def __init__(self, max_workers: int = 4):
        self.max_workers = max_workers
        
    def process_files_parallel(self, file_paths: List[str], 
                             process_func, **kwargs) -> Dict[str, Any]:
        """并行处理多个文件"""
        try:
            results = {}
            failed_files = []
            
            with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                # 提交所有任务
                future_to_file = {
                    executor.submit(process_func, file_path, **kwargs): file_path 
                    for file_path in file_paths
                }
                
                # 收集结果
                for future in as_completed(future_to_file):
                    file_path = future_to_file[future]
                    try:
                        result = future.result()
                        if result:
                            results[file_path] = result
                        else:
                            failed_files.append(file_path)
                    except Exception as e:
                        logger.error(f"处理文件失败 {file_path}: {e}")
                        failed_files.append(file_path)
            
            return {
                'success': True,
                'results': results,
                'failed_files': failed_files,
                'processed_count': len(results),
                'failed_count': len(failed_files)
            }
            
        except Exception as e:
            logger.error(f"并行处理失败: {e}")
            return {
                'success': False,
                'error': str(e)
            }


class DataValidator:
    """数据验证器"""
    
    def __init__(self):
        self.validation_rules = {
            'required_fields': ['科目编码', '金额', '日期'],
            'numeric_fields': ['金额', '数量', '单价'],
            'date_fields': ['日期', '交易日期', '凭证日期'],
            'max_length': {
                '科目编码': 20,
                '科目名称': 100,
                '摘要': 200
            }
        }
    
    def validate_dataframe(self, df: pd.DataFrame, 
                          table_name: str = None) -> Dict[str, Any]:
        """验证DataFrame数据质量"""
        try:
            validation_result = {
                'valid': True,
                'warnings': [],
                'errors': [],
                'quality_score': 1.0,
                'statistics': {}
            }
            
            # 基本统计
            validation_result['statistics'] = {
                'row_count': len(df),
                'column_count': len(df.columns),
                'null_count': df.isnull().sum().sum(),
                'duplicate_count': df.duplicated().sum()
            }
            
            # 1. 检查必填字段
            missing_required = []
            for field in self.validation_rules['required_fields']:
                matching_cols = [col for col in df.columns if field in col]
                if not matching_cols:
                    missing_required.append(field)
            
            if missing_required:
                validation_result['warnings'].append(
                    f"缺少建议字段: {', '.join(missing_required)}"
                )
                validation_result['quality_score'] -= 0.1
            
            # 2. 检查数值字段
            for field in self.validation_rules['numeric_fields']:
                matching_cols = [col for col in df.columns if field in col]
                for col in matching_cols:
                    if col in df.columns:
                        non_numeric = pd.to_numeric(df[col], errors='coerce').isnull().sum()
                        if non_numeric > 0:
                            validation_result['warnings'].append(
                                f"列 {col} 包含 {non_numeric} 个非数值项"
                            )
                            validation_result['quality_score'] -= 0.05
            
            # 3. 检查日期字段
            for field in self.validation_rules['date_fields']:
                matching_cols = [col for col in df.columns if field in col]
                for col in matching_cols:
                    if col in df.columns:
                        try:
                            pd.to_datetime(df[col], errors='coerce')
                        except:
                            validation_result['warnings'].append(
                                f"列 {col} 日期格式可能有问题"
                            )
                            validation_result['quality_score'] -= 0.05
            
            # 4. 检查数据完整性
            null_percentage = (df.isnull().sum().sum() / (len(df) * len(df.columns))) * 100
            if null_percentage > 20:
                validation_result['warnings'].append(
                    f"数据缺失率较高: {null_percentage:.1f}%"
                )
                validation_result['quality_score'] -= 0.15
            elif null_percentage > 10:
                validation_result['warnings'].append(
                    f"存在数据缺失: {null_percentage:.1f}%"
                )
                validation_result['quality_score'] -= 0.05
            
            # 5. 检查重复数据
            duplicate_percentage = (df.duplicated().sum() / len(df)) * 100
            if duplicate_percentage > 10:
                validation_result['warnings'].append(
                    f"重复数据较多: {duplicate_percentage:.1f}%"
                )
                validation_result['quality_score'] -= 0.1
            elif duplicate_percentage > 0:
                validation_result['warnings'].append(
                    f"存在重复数据: {duplicate_percentage:.1f}%"
                )
                validation_result['quality_score'] -= 0.02
            
            # 6. 确定整体质量等级
            if validation_result['quality_score'] >= 0.9:
                validation_result['quality_level'] = '优秀'
            elif validation_result['quality_score'] >= 0.8:
                validation_result['quality_level'] = '良好'
            elif validation_result['quality_score'] >= 0.7:
                validation_result['quality_level'] = '一般'
            else:
                validation_result['quality_level'] = '较差'
                validation_result['valid'] = False
            
            return validation_result
            
        except Exception as e:
            logger.error(f"数据验证失败: {e}")
            return {
                'valid': False,
                'error': str(e),
                'quality_score': 0.0
            }


class QueryBuilder:
    """SQL查询构建器"""
    
    def __init__(self):
        self.query_templates = {}
        self._load_query_templates()
    
    def _load_query_templates(self):
        """加载查询模板"""
        self.query_templates = {
            'account_balance': '''
                SELECT 
                    科目编码,
                    科目名称,
                    科目类型,
                    SUM(CASE WHEN 方向 = '借' THEN 金额 ELSE 0 END) as 借方发生额,
                    SUM(CASE WHEN 方向 = '贷' THEN 金额 ELSE 0 END) as 贷方发生额,
                    SUM(CASE WHEN 方向 = '借' THEN 金额 ELSE -金额 END) as 余额
                FROM {table_name}
                WHERE 科目编码 IS NOT NULL
                GROUP BY 科目编码, 科目名称, 科目类型
                ORDER BY 科目编码
            ''',
            'account_detail': '''
                SELECT 
                    日期,
                    凭证号,
                    摘要,
                    科目编码,
                    科目名称,
                    借方金额,
                    贷方金额,
                    余额
                FROM {table_name}
                WHERE 科目编码 = '{account_code}'
                ORDER BY 日期, 凭证号
            ''',
            'balance_sheet_assets': '''
                SELECT 
                    科目名称 as 项目,
                    SUM(余额) as 金额
                FROM {table_name}
                WHERE 科目类型 = '资产' AND 科目编码 LIKE '{code_prefix}%'
                GROUP BY 科目名称
                ORDER BY 科目编码
            ''',
            'income_statement': '''
                SELECT 
                    科目名称 as 项目,
                    SUM(CASE WHEN 科目类型 = '收入' THEN 金额 ELSE -金额 END) as 金额
                FROM {table_name}
                WHERE 科目类型 IN ('收入', '费用')
                GROUP BY 科目名称, 科目类型
                ORDER BY 科目类型, 科目编码
            '''
        }
    
    def build_query(self, template_name: str, **params) -> str:
        """构建查询"""
        try:
            template = self.query_templates.get(template_name)
            if not template:
                raise ValueError(f"未找到查询模板: {template_name}")
            
            return template.format(**params)
            
        except Exception as e:
            logger.error(f"构建查询失败: {e}")
            return ""
    
    def get_available_templates(self) -> List[str]:
        """获取可用的查询模板"""
        return list(self.query_templates.keys())


# 测试函数
def test_database_utils():
    """测试数据库工具"""
    print("测试数据库工具...")
    
    # 测试数据验证器
    validator = DataValidator()
    test_data = pd.DataFrame({
        '科目编码': ['1001', '1002', None],
        '金额': [100, 'abc', 200],
        '日期': ['2024-01-01', '2024-01-02', '2024-01-03']
    })
    
    result = validator.validate_dataframe(test_data)
    print(f"数据验证结果: {result}")
    
    # 测试查询构建器
    builder = QueryBuilder()
    query = builder.build_query('account_balance', table_name='test_table')
    print(f"构建的查询: {query}")


if __name__ == "__main__":
    test_database_utils()