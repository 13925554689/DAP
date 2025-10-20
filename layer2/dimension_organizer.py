"""
DAP - 维度组织器
多维度数据组织和分析视图创建
"""

import sqlite3
import pandas as pd
import json
from typing import Dict, Any, List, Optional
import logging
from datetime import datetime
import re

logger = logging.getLogger(__name__)

class DimensionOrganizer:
    """多维度数据组织器"""
    
    def __init__(self, db_path: str = 'data/dap_data.db'):
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        
        # 维度配置
        self.dimensions = {
            'temporal': {
                'name': '时间维度',
                'types': ['年度', '季度', '月度', '周', '日'],
                'patterns': ['*日期*', '*date*', '*time*', '*时间*']
            },
            'business': {
                'name': '业务维度',
                'types': ['销售', '采购', '生产', '财务', '人力'],
                'patterns': ['*业务*', '*business*', '*部门*', '*department*']
            },
            'geographical': {
                'name': '地理维度',
                'types': ['总部', '分公司', '办事处', '区域'],
                'patterns': ['*地区*', '*区域*', '*location*', '*region*']
            },
            'functional': {
                'name': '功能维度',
                'types': ['资产', '负债', '权益', '收入', '费用'],
                'patterns': ['*科目*', '*account*', '*类型*', '*type*']
            },
            'analytical': {
                'name': '分析维度',
                'types': ['正常', '异常', '高风险', '低风险'],
                'patterns': ['*风险*', '*risk*', '*异常*', '*状态*']
            }
        }
        
        # 组织统计
        self.organization_stats = {
            'views_created': 0,
            'dimensions_processed': 0,
            'tables_analyzed': 0
        }
        
        logger.info("维度组织器初始化完成")
    
    def organize_by_all_dimensions(self) -> Dict[str, Any]:
        """按所有维度组织数据"""
        logger.info("开始多维度数据组织")
        
        start_time = datetime.now()
        
        # 获取所有原始数据表
        raw_tables = self._get_raw_clean_tables()
        self.organization_stats['tables_analyzed'] = len(raw_tables)
        
        # 为每个维度创建视图
        for dimension_name, dimension_config in self.dimensions.items():
            logger.info(f"处理维度: {dimension_config['name']}")
            
            try:
                if dimension_name == 'temporal':
                    self._organize_temporal_dimension(raw_tables)
                elif dimension_name == 'business':
                    self._organize_business_dimension(raw_tables)
                elif dimension_name == 'geographical':
                    self._organize_geographical_dimension(raw_tables)
                elif dimension_name == 'functional':
                    self._organize_functional_dimension(raw_tables)
                elif dimension_name == 'analytical':
                    self._organize_analytical_dimension(raw_tables)
                
                self.organization_stats['dimensions_processed'] += 1
                
            except Exception as e:
                logger.error(f"维度组织失败 {dimension_name}: {e}")
                continue
        
        # 创建综合分析视图
        self._create_comprehensive_views(raw_tables)
        
        # 计算执行时间
        end_time = datetime.now()
        execution_time = (end_time - start_time).total_seconds()
        
        # 保存组织统计
        self._save_organization_stats(execution_time)
        
        logger.info(f"多维度数据组织完成，创建视图: {self.organization_stats['views_created']}")
        
        return {
            'success': True,
            'stats': self.organization_stats,
            'execution_time': execution_time
        }
    
    def _get_raw_clean_tables(self) -> List[str]:
        """获取所有raw_clean表"""
        try:
            query = '''
                SELECT name FROM sqlite_master 
                WHERE type='table' AND name LIKE 'raw_clean_%'
                ORDER BY name
            '''
            
            results = self.conn.execute(query).fetchall()
            tables = [row[0] for row in results]
            
            logger.info(f"找到原始数据表: {len(tables)} 个")
            return tables
            
        except Exception as e:
            logger.error(f"获取原始数据表失败: {e}")
            return []
    
    def _organize_temporal_dimension(self, tables: List[str]):
        """组织时间维度"""
        logger.info("组织时间维度")
        
        for table_name in tables:
            try:
                # 查找日期字段
                date_columns = self._find_date_columns(table_name)
                
                for date_column in date_columns:
                    # 创建年度视图
                    self._create_annual_view(table_name, date_column)
                    
                    # 创建季度视图
                    self._create_quarterly_view(table_name, date_column)
                    
                    # 创建月度视图
                    self._create_monthly_view(table_name, date_column)
                    
                    # 创建周视图
                    self._create_weekly_view(table_name, date_column)
                    
                    # 只处理第一个日期字段
                    break
                    
            except Exception as e:
                logger.warning(f"时间维度组织失败 {table_name}: {e}")
                continue
    
    def _create_annual_view(self, table_name: str, date_column: str):
        """创建年度视图"""
        try:
            # 提取表的简短名称
            short_name = table_name.replace('raw_clean_', '')
            view_name = f"temporal_annual_{short_name}"
            
            # 查找金额字段
            amount_columns = self._find_amount_columns(table_name)
            
            # 构建SELECT字段
            select_fields = [
                f"strftime('%Y', \"{date_column}\") as year",
                f"COUNT(*) as record_count"
            ]
            
            # 添加金额汇总
            for amount_col in amount_columns[:3]:  # 最多处理3个金额字段
                select_fields.append(f"SUM(\"{amount_col}\") as total_{amount_col}")
                select_fields.append(f"AVG(\"{amount_col}\") as avg_{amount_col}")
            
            # 添加其他统计字段
            select_fields.extend([
                f"MIN(\"{date_column}\") as first_date",
                f"MAX(\"{date_column}\") as last_date"
            ])
            
            select_clause = ', '.join(select_fields)
            
            # 删除已存在的视图
            self.conn.execute(f"DROP VIEW IF EXISTS {view_name}")
            
            # 创建新视图
            create_sql = f'''
                CREATE VIEW {view_name} AS
                SELECT {select_clause}
                FROM {table_name}
                WHERE "{date_column}" IS NOT NULL
                GROUP BY strftime('%Y', "{date_column}")
                ORDER BY year
            '''
            
            self.conn.execute(create_sql)
            self.organization_stats['views_created'] += 1
            
            # 记录视图元数据
            self._record_dimension_view(view_name, 'temporal_annual', table_name, 
                                      date_column, 'year')
            
            logger.info(f"创建年度视图: {view_name}")
            
        except Exception as e:
            logger.warning(f"创建年度视图失败 {table_name}: {e}")
    
    def _create_quarterly_view(self, table_name: str, date_column: str):
        """创建季度视图"""
        try:
            short_name = table_name.replace('raw_clean_', '')
            view_name = f"temporal_quarterly_{short_name}"
            
            amount_columns = self._find_amount_columns(table_name)
            
            select_fields = [
                f"strftime('%Y', \"{date_column}\") as year",
                f"CASE CAST(strftime('%m', \"{date_column}\") AS INTEGER) " +
                f"WHEN 1 THEN 'Q1' WHEN 2 THEN 'Q1' WHEN 3 THEN 'Q1' " +
                f"WHEN 4 THEN 'Q2' WHEN 5 THEN 'Q2' WHEN 6 THEN 'Q2' " +
                f"WHEN 7 THEN 'Q3' WHEN 8 THEN 'Q3' WHEN 9 THEN 'Q3' " +
                f"WHEN 10 THEN 'Q4' WHEN 11 THEN 'Q4' WHEN 12 THEN 'Q4' " +
                f"ELSE 'Q1' END as quarter",
                f"COUNT(*) as record_count"
            ]
            
            for amount_col in amount_columns[:2]:
                select_fields.append(f"SUM(\"{amount_col}\") as total_{amount_col}")
            
            select_clause = ', '.join(select_fields)
            
            self.conn.execute(f"DROP VIEW IF EXISTS {view_name}")
            
            create_sql = f'''
                CREATE VIEW {view_name} AS
                SELECT {select_clause}
                FROM {table_name}
                WHERE "{date_column}" IS NOT NULL
                GROUP BY year, quarter
                ORDER BY year, quarter
            '''
            
            self.conn.execute(create_sql)
            self.organization_stats['views_created'] += 1
            
            self._record_dimension_view(view_name, 'temporal_quarterly', table_name, 
                                      date_column, 'quarter')
            
            logger.info(f"创建季度视图: {view_name}")
            
        except Exception as e:
            logger.warning(f"创建季度视图失败 {table_name}: {e}")
    
    def _create_monthly_view(self, table_name: str, date_column: str):
        """创建月度视图"""
        try:
            short_name = table_name.replace('raw_clean_', '')
            view_name = f"temporal_monthly_{short_name}"
            
            amount_columns = self._find_amount_columns(table_name)
            
            select_fields = [
                f"strftime('%Y-%m', \"{date_column}\") as month",
                f"COUNT(*) as record_count"
            ]
            
            for amount_col in amount_columns[:2]:
                select_fields.append(f"SUM(\"{amount_col}\") as total_{amount_col}")
                select_fields.append(f"AVG(\"{amount_col}\") as avg_{amount_col}")
            
            select_clause = ', '.join(select_fields)
            
            self.conn.execute(f"DROP VIEW IF EXISTS {view_name}")
            
            create_sql = f'''
                CREATE VIEW {view_name} AS
                SELECT {select_clause}
                FROM {table_name}
                WHERE "{date_column}" IS NOT NULL
                GROUP BY strftime('%Y-%m', "{date_column}")
                ORDER BY month
            '''
            
            self.conn.execute(create_sql)
            self.organization_stats['views_created'] += 1
            
            self._record_dimension_view(view_name, 'temporal_monthly', table_name, 
                                      date_column, 'month')
            
        except Exception as e:
            logger.warning(f"创建月度视图失败 {table_name}: {e}")
    
    def _create_weekly_view(self, table_name: str, date_column: str):
        """创建周视图"""
        try:
            short_name = table_name.replace('raw_clean_', '')
            view_name = f"temporal_weekly_{short_name}"
            
            amount_columns = self._find_amount_columns(table_name)
            
            select_fields = [
                f"strftime('%Y-%W', \"{date_column}\") as week",
                f"COUNT(*) as record_count"
            ]
            
            if amount_columns:
                select_fields.append(f"SUM(\"{amount_columns[0]}\") as total_amount")
            
            select_clause = ', '.join(select_fields)
            
            self.conn.execute(f"DROP VIEW IF EXISTS {view_name}")
            
            create_sql = f'''
                CREATE VIEW {view_name} AS
                SELECT {select_clause}
                FROM {table_name}
                WHERE "{date_column}" IS NOT NULL
                GROUP BY strftime('%Y-%W', "{date_column}")
                ORDER BY week
            '''
            
            self.conn.execute(create_sql)
            self.organization_stats['views_created'] += 1
            
            self._record_dimension_view(view_name, 'temporal_weekly', table_name, 
                                      date_column, 'week')
            
        except Exception as e:
            logger.warning(f"创建周视图失败 {table_name}: {e}")
    
    def _organize_business_dimension(self, tables: List[str]):
        """组织业务维度"""
        logger.info("组织业务维度")
        
        for table_name in tables:
            try:
                # 根据表名和内容推断业务类型
                business_type = self._infer_business_type(table_name)
                
                if business_type:
                    self._create_business_view(table_name, business_type)
                
                # 创建业务流程视图
                self._create_business_process_view(table_name)
                
            except Exception as e:
                logger.warning(f"业务维度组织失败 {table_name}: {e}")
                continue
    
    def _infer_business_type(self, table_name: str) -> Optional[str]:
        """推断业务类型"""
        business_patterns = {
            'sales': ['销售', 'sales', '订单', 'order', '客户', 'customer'],
            'procurement': ['采购', 'purchase', '供应商', 'vendor', '供货'],
            'finance': ['财务', 'finance', '会计', 'account', '总账', 'ledger'],
            'inventory': ['库存', 'inventory', '仓库', 'warehouse', '物料'],
            'hr': ['人力', 'hr', '员工', 'employee', '薪资', 'salary']
        }
        
        table_lower = table_name.lower()
        
        for business_type, patterns in business_patterns.items():
            if any(pattern in table_lower for pattern in patterns):
                return business_type
        
        return None
    
    def _create_business_view(self, table_name: str, business_type: str):
        """创建业务类型视图"""
        try:
            short_name = table_name.replace('raw_clean_', '')
            view_name = f"business_{business_type}_{short_name}"
            
            # 根据业务类型选择关键字段
            key_fields = self._get_business_key_fields(table_name, business_type)
            
            if key_fields:
                select_clause = ', '.join([f'"{field}"' for field in key_fields])
                
                self.conn.execute(f"DROP VIEW IF EXISTS {view_name}")
                
                create_sql = f'''
                    CREATE VIEW {view_name} AS
                    SELECT {select_clause}, COUNT(*) as record_count
                    FROM {table_name}
                    GROUP BY {select_clause}
                    ORDER BY record_count DESC
                '''
                
                self.conn.execute(create_sql)
                self.organization_stats['views_created'] += 1
                
                self._record_dimension_view(view_name, f'business_{business_type}', 
                                          table_name, 'business_type', business_type)
                
        except Exception as e:
            logger.warning(f"创建业务视图失败 {table_name}: {e}")
    
    def _get_business_key_fields(self, table_name: str, business_type: str) -> List[str]:
        """获取业务关键字段"""
        try:
            # 获取表的所有列
            columns_query = f"PRAGMA table_info({table_name})"
            columns_info = self.conn.execute(columns_query).fetchall()
            column_names = [col[1] for col in columns_info]
            
            # 根据业务类型选择关键字段
            key_patterns = {
                'sales': ['客户', 'customer', '产品', 'product', '销售员'],
                'procurement': ['供应商', 'vendor', '采购员', '物料'],
                'finance': ['科目', 'account', '部门', 'department'],
                'inventory': ['仓库', 'warehouse', '物料', 'material'],
                'hr': ['部门', 'department', '岗位', 'position']
            }
            
            patterns = key_patterns.get(business_type, [])
            key_fields = []
            
            for column in column_names:
                column_lower = column.lower()
                if any(pattern in column_lower for pattern in patterns):
                    key_fields.append(column)
                    if len(key_fields) >= 3:  # 最多选择3个关键字段
                        break
            
            return key_fields
            
        except Exception as e:
            logger.warning(f"获取业务关键字段失败: {e}")
            return []
    
    def _create_business_process_view(self, table_name: str):
        """创建业务流程视图"""
        try:
            # 查找状态字段
            status_columns = self._find_status_columns(table_name)
            
            if status_columns:
                status_column = status_columns[0]
                short_name = table_name.replace('raw_clean_', '')
                view_name = f"business_process_{short_name}"
                
                self.conn.execute(f"DROP VIEW IF EXISTS {view_name}")
                
                create_sql = f'''
                    CREATE VIEW {view_name} AS
                    SELECT 
                        "{status_column}" as process_status,
                        COUNT(*) as count,
                        COUNT(*) * 100.0 / SUM(COUNT(*)) OVER() as percentage
                    FROM {table_name}
                    WHERE "{status_column}" IS NOT NULL
                    GROUP BY "{status_column}"
                    ORDER BY count DESC
                '''
                
                self.conn.execute(create_sql)
                self.organization_stats['views_created'] += 1
                
                self._record_dimension_view(view_name, 'business_process', 
                                          table_name, status_column, 'process')
                
        except Exception as e:
            logger.warning(f"创建业务流程视图失败 {table_name}: {e}")
    
    def _organize_geographical_dimension(self, tables: List[str]):
        """组织地理维度"""
        logger.info("组织地理维度")
        
        for table_name in tables:
            try:
                # 查找地理字段
                geo_columns = self._find_geographical_columns(table_name)
                
                for geo_column in geo_columns:
                    self._create_geographical_view(table_name, geo_column)
                    
            except Exception as e:
                logger.warning(f"地理维度组织失败 {table_name}: {e}")
                continue
    
    def _create_geographical_view(self, table_name: str, geo_column: str):
        """创建地理维度视图"""
        try:
            short_name = table_name.replace('raw_clean_', '')
            view_name = f"geographical_{short_name}"
            
            amount_columns = self._find_amount_columns(table_name)
            
            select_fields = [
                f'"{geo_column}" as region',
                'COUNT(*) as record_count'
            ]
            
            if amount_columns:
                select_fields.append(f'SUM("{amount_columns[0]}") as total_amount')
                select_fields.append(f'AVG("{amount_columns[0]}") as avg_amount')
            
            select_clause = ', '.join(select_fields)
            
            self.conn.execute(f"DROP VIEW IF EXISTS {view_name}")
            
            create_sql = f'''
                CREATE VIEW {view_name} AS
                SELECT {select_clause}
                FROM {table_name}
                WHERE "{geo_column}" IS NOT NULL
                GROUP BY "{geo_column}"
                ORDER BY record_count DESC
            '''
            
            self.conn.execute(create_sql)
            self.organization_stats['views_created'] += 1
            
            self._record_dimension_view(view_name, 'geographical', table_name, 
                                      geo_column, 'region')
            
        except Exception as e:
            logger.warning(f"创建地理视图失败 {table_name}: {e}")
    
    def _organize_functional_dimension(self, tables: List[str]):
        """组织功能维度"""
        logger.info("组织功能维度")
        
        for table_name in tables:
            try:
                # 查找科目或功能字段
                functional_columns = self._find_functional_columns(table_name)
                
                for func_column in functional_columns:
                    self._create_functional_view(table_name, func_column)
                    
            except Exception as e:
                logger.warning(f"功能维度组织失败 {table_name}: {e}")
                continue
    
    def _create_functional_view(self, table_name: str, func_column: str):
        """创建功能维度视图"""
        try:
            short_name = table_name.replace('raw_clean_', '')
            view_name = f"functional_{short_name}"
            
            # 根据科目编码分类
            self.conn.execute(f"DROP VIEW IF EXISTS {view_name}")
            
            create_sql = f'''
                CREATE VIEW {view_name} AS
                SELECT 
                    CASE 
                        WHEN "{func_column}" LIKE '1%' THEN '资产'
                        WHEN "{func_column}" LIKE '2%' THEN '负债'
                        WHEN "{func_column}" LIKE '3%' THEN '权益'
                        WHEN "{func_column}" LIKE '4%' THEN '收入'
                        WHEN "{func_column}" LIKE '5%' THEN '费用'
                        WHEN "{func_column}" LIKE '6%' THEN '收入'
                        ELSE '其他'
                    END as functional_category,
                    COUNT(*) as record_count
                FROM {table_name}
                WHERE "{func_column}" IS NOT NULL
                GROUP BY functional_category
                ORDER BY record_count DESC
            '''
            
            self.conn.execute(create_sql)
            self.organization_stats['views_created'] += 1
            
            self._record_dimension_view(view_name, 'functional', table_name, 
                                      func_column, 'category')
            
        except Exception as e:
            logger.warning(f"创建功能视图失败 {table_name}: {e}")
    
    def _organize_analytical_dimension(self, tables: List[str]):
        """组织分析维度"""
        logger.info("组织分析维度")
        
        for table_name in tables:
            try:
                # 创建异常分析视图
                self._create_anomaly_analysis_view(table_name)
                
                # 创建风险分析视图
                self._create_risk_analysis_view(table_name)
                
            except Exception as e:
                logger.warning(f"分析维度组织失败 {table_name}: {e}")
                continue
    
    def _create_anomaly_analysis_view(self, table_name: str):
        """创建异常分析视图"""
        try:
            amount_columns = self._find_amount_columns(table_name)
            date_columns = self._find_date_columns(table_name)
            
            if not amount_columns:
                return
            
            amount_column = amount_columns[0]
            short_name = table_name.replace('raw_clean_', '')
            view_name = f"analytical_anomaly_{short_name}"
            
            # 构建异常检测逻辑
            anomaly_conditions = [
                f'"{amount_column}" > (SELECT AVG("{amount_column}") * 3 FROM {table_name})',
                f'"{amount_column}" < 0'
            ]
            
            # 如果有日期字段，添加时间异常检测
            if date_columns:
                date_column = date_columns[0]
                anomaly_conditions.append(
                    f'strftime("%w", "{date_column}") IN ("0", "6")'  # 周末交易
                )
            
            anomaly_clause = ' OR '.join(f'({condition})' for condition in anomaly_conditions)
            
            self.conn.execute(f"DROP VIEW IF EXISTS {view_name}")
            
            create_sql = f'''
                CREATE VIEW {view_name} AS
                SELECT *,
                    CASE 
                        WHEN {anomaly_clause} THEN '异常'
                        ELSE '正常'
                    END as anomaly_flag
                FROM {table_name}
                WHERE anomaly_flag = '异常'
            '''
            
            self.conn.execute(create_sql)
            self.organization_stats['views_created'] += 1
            
            self._record_dimension_view(view_name, 'analytical_anomaly', table_name, 
                                      amount_column, 'anomaly')
            
        except Exception as e:
            logger.warning(f"创建异常分析视图失败 {table_name}: {e}")
    
    def _create_risk_analysis_view(self, table_name: str):
        """创建风险分析视图"""
        try:
            amount_columns = self._find_amount_columns(table_name)
            
            if not amount_columns:
                return
            
            amount_column = amount_columns[0]
            short_name = table_name.replace('raw_clean_', '')
            view_name = f"analytical_risk_{short_name}"
            
            self.conn.execute(f"DROP VIEW IF EXISTS {view_name}")
            
            create_sql = f'''
                CREATE VIEW {view_name} AS
                SELECT *,
                    CASE 
                        WHEN "{amount_column}" > (SELECT PERCENTILE_90("{amount_column}") FROM {table_name}) THEN '高风险'
                        WHEN "{amount_column}" > (SELECT PERCENTILE_75("{amount_column}") FROM {table_name}) THEN '中风险'
                        ELSE '低风险'
                    END as risk_level
                FROM {table_name}
                ORDER BY "{amount_column}" DESC
            '''
            
            # 由于SQLite没有内置PERCENTILE函数，使用替代方案
            alternative_sql = f'''
                CREATE VIEW {view_name} AS
                SELECT *,
                    CASE 
                        WHEN "{amount_column}" > (
                            SELECT "{amount_column}" FROM {table_name} 
                            ORDER BY "{amount_column}" DESC 
                            LIMIT 1 OFFSET (SELECT COUNT(*) * 0.1 FROM {table_name})
                        ) THEN '高风险'
                        WHEN "{amount_column}" > (
                            SELECT "{amount_column}" FROM {table_name} 
                            ORDER BY "{amount_column}" DESC 
                            LIMIT 1 OFFSET (SELECT COUNT(*) * 0.25 FROM {table_name})
                        ) THEN '中风险'
                        ELSE '低风险'
                    END as risk_level
                FROM {table_name}
                ORDER BY "{amount_column}" DESC
            '''
            
            self.conn.execute(alternative_sql)
            self.organization_stats['views_created'] += 1
            
            self._record_dimension_view(view_name, 'analytical_risk', table_name, 
                                      amount_column, 'risk')
            
        except Exception as e:
            logger.warning(f"创建风险分析视图失败 {table_name}: {e}")
    
    def _create_comprehensive_views(self, tables: List[str]):
        """创建综合分析视图"""
        logger.info("创建综合分析视图")
        
        try:
            # 创建数据质量概览视图
            self._create_data_quality_overview()
            
            # 创建业务概览视图
            self._create_business_overview(tables)
            
            # 创建审计焦点视图
            self._create_audit_focus_view(tables)
            
        except Exception as e:
            logger.warning(f"创建综合视图失败: {e}")
    
    def _create_data_quality_overview(self):
        """创建数据质量概览视图"""
        try:
            view_name = "comprehensive_data_quality"
            
            self.conn.execute(f"DROP VIEW IF EXISTS {view_name}")
            
            create_sql = '''
                CREATE VIEW comprehensive_data_quality AS
                SELECT 
                    table_name,
                    table_type,
                    business_domain,
                    row_count,
                    column_count,
                    data_quality_score,
                    CASE 
                        WHEN data_quality_score >= 0.9 THEN '优秀'
                        WHEN data_quality_score >= 0.8 THEN '良好'
                        WHEN data_quality_score >= 0.7 THEN '一般'
                        ELSE '需改进'
                    END as quality_level
                FROM meta_tables
                ORDER BY data_quality_score DESC
            '''
            
            self.conn.execute(create_sql)
            self.organization_stats['views_created'] += 1
            
        except Exception as e:
            logger.warning(f"创建数据质量概览失败: {e}")
    
    def _create_business_overview(self, tables: List[str]):
        """创建业务概览视图"""
        try:
            # 寻找包含金额的主要业务表
            main_tables = []
            for table in tables:
                amount_cols = self._find_amount_columns(table)
                if amount_cols:
                    main_tables.append(table)
            
            if not main_tables:
                return
            
            view_name = "comprehensive_business_overview"
            self.conn.execute(f"DROP VIEW IF EXISTS {view_name}")
            
            # 构建联合查询
            union_parts = []
            for table in main_tables[:5]:  # 最多处理5个表
                amount_col = self._find_amount_columns(table)[0]
                table_type = table.replace('raw_clean_', '')
                
                union_parts.append(f'''
                    SELECT 
                        '{table_type}' as business_type,
                        COUNT(*) as transaction_count,
                        SUM("{amount_col}") as total_amount,
                        AVG("{amount_col}") as avg_amount
                    FROM {table}
                ''')
            
            if union_parts:
                create_sql = f'''
                    CREATE VIEW {view_name} AS
                    {' UNION ALL '.join(union_parts)}
                    ORDER BY total_amount DESC
                '''
                
                self.conn.execute(create_sql)
                self.organization_stats['views_created'] += 1
                
        except Exception as e:
            logger.warning(f"创建业务概览失败: {e}")
    
    def _create_audit_focus_view(self, tables: List[str]):
        """创建审计焦点视图"""
        try:
            view_name = "comprehensive_audit_focus"
            
            # 查找包含审计相关标记的表
            audit_tables = []
            for table in tables:
                # 检查是否有审计标记列
                columns_query = f"PRAGMA table_info({table})"
                columns_info = self.conn.execute(columns_query).fetchall()
                column_names = [col[1] for col in columns_info]
                
                if any('flag' in col.lower() or 'risk' in col.lower() for col in column_names):
                    audit_tables.append(table)
            
            if audit_tables:
                self.conn.execute(f"DROP VIEW IF EXISTS {view_name}")
                
                # 创建审计焦点汇总
                create_sql = f'''
                    CREATE VIEW {view_name} AS
                    SELECT 
                        'High Priority Items' as focus_area,
                        COUNT(*) as item_count,
                        'Review Required' as status
                    FROM {audit_tables[0]}
                    WHERE 1=1  -- 这里可以添加具体的高优先级条件
                '''
                
                self.conn.execute(create_sql)
                self.organization_stats['views_created'] += 1
                
        except Exception as e:
            logger.warning(f"创建审计焦点视图失败: {e}")
    
    # 辅助方法
    def _find_date_columns(self, table_name: str) -> List[str]:
        """查找日期列"""
        try:
            columns_query = f"PRAGMA table_info({table_name})"
            columns_info = self.conn.execute(columns_query).fetchall()
            
            date_columns = []
            for col_info in columns_info:
                col_name = col_info[1]
                col_lower = col_name.lower()
                
                if any(pattern in col_lower for pattern in ['日期', 'date', 'time', '时间']):
                    date_columns.append(col_name)
            
            return date_columns
            
        except Exception as e:
            logger.warning(f"查找日期列失败: {e}")
            return []
    
    def _find_amount_columns(self, table_name: str) -> List[str]:
        """查找金额列"""
        try:
            columns_query = f"PRAGMA table_info({table_name})"
            columns_info = self.conn.execute(columns_query).fetchall()
            
            amount_columns = []
            for col_info in columns_info:
                col_name = col_info[1]
                col_lower = col_name.lower()
                
                if any(pattern in col_lower for pattern in ['金额', 'amount', 'money', '价格', 'price']):
                    amount_columns.append(col_name)
            
            return amount_columns
            
        except Exception as e:
            logger.warning(f"查找金额列失败: {e}")
            return []
    
    def _find_status_columns(self, table_name: str) -> List[str]:
        """查找状态列"""
        try:
            columns_query = f"PRAGMA table_info({table_name})"
            columns_info = self.conn.execute(columns_query).fetchall()
            
            status_columns = []
            for col_info in columns_info:
                col_name = col_info[1]
                col_lower = col_name.lower()
                
                if any(pattern in col_lower for pattern in ['状态', 'status', '流程', 'process']):
                    status_columns.append(col_name)
            
            return status_columns
            
        except Exception as e:
            logger.warning(f"查找状态列失败: {e}")
            return []
    
    def _find_geographical_columns(self, table_name: str) -> List[str]:
        """查找地理列"""
        try:
            columns_query = f"PRAGMA table_info({table_name})"
            columns_info = self.conn.execute(columns_query).fetchall()
            
            geo_columns = []
            for col_info in columns_info:
                col_name = col_info[1]
                col_lower = col_name.lower()
                
                if any(pattern in col_lower for pattern in ['地区', '区域', 'region', 'location', '城市']):
                    geo_columns.append(col_name)
            
            return geo_columns
            
        except Exception as e:
            logger.warning(f"查找地理列失败: {e}")
            return []
    
    def _find_functional_columns(self, table_name: str) -> List[str]:
        """查找功能列"""
        try:
            columns_query = f"PRAGMA table_info({table_name})"
            columns_info = self.conn.execute(columns_query).fetchall()
            
            func_columns = []
            for col_info in columns_info:
                col_name = col_info[1]
                col_lower = col_name.lower()
                
                if any(pattern in col_lower for pattern in ['科目', 'account', '类型', 'type', '分类']):
                    func_columns.append(col_name)
            
            return func_columns
            
        except Exception as e:
            logger.warning(f"查找功能列失败: {e}")
            return []
    
    def _record_dimension_view(self, view_name: str, dimension_type: str, 
                              base_table: str, dimension_key: str, dimension_value: str):
        """记录维度视图元数据"""
        try:
            # 确保meta_views表存在
            create_table_sql = '''
                CREATE TABLE IF NOT EXISTS meta_views (
                    view_name TEXT PRIMARY KEY,
                    view_type TEXT,
                    base_tables TEXT,
                    dimension_key TEXT,
                    dimension_value TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_refreshed TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            '''
            
            self.conn.execute(create_table_sql)
            
            # 插入视图记录
            insert_sql = '''
                INSERT OR REPLACE INTO meta_views
                (view_name, view_type, base_tables, dimension_key, dimension_value, last_refreshed)
                VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            '''
            
            self.conn.execute(insert_sql, (
                view_name,
                dimension_type,
                json.dumps([base_table]),
                dimension_key,
                dimension_value
            ))
            
            self.conn.commit()
            
        except Exception as e:
            logger.warning(f"记录维度视图元数据失败: {e}")
    
    def _save_organization_stats(self, execution_time: float):
        """保存组织统计"""
        try:
            create_table_sql = '''
                CREATE TABLE IF NOT EXISTS dimension_organization_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    execution_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    tables_analyzed INTEGER,
                    dimensions_processed INTEGER,
                    views_created INTEGER,
                    duration_seconds REAL
                )
            '''
            
            self.conn.execute(create_table_sql)
            
            insert_sql = '''
                INSERT INTO dimension_organization_log
                (tables_analyzed, dimensions_processed, views_created, duration_seconds)
                VALUES (?, ?, ?, ?)
            '''
            
            self.conn.execute(insert_sql, (
                self.organization_stats['tables_analyzed'],
                self.organization_stats['dimensions_processed'],
                self.organization_stats['views_created'],
                execution_time
            ))
            
            self.conn.commit()
            
        except Exception as e:
            logger.warning(f"保存组织统计失败: {e}")
    
    def get_dimension_summary(self) -> Dict[str, Any]:
        """获取维度组织摘要"""
        try:
            # 获取各类型视图数量
            view_type_query = '''
                SELECT view_type, COUNT(*) as count
                FROM meta_views
                GROUP BY view_type
                ORDER BY count DESC
            '''
            
            view_types = self.conn.execute(view_type_query).fetchall()
            
            # 获取最近的组织统计
            recent_stats_query = '''
                SELECT tables_analyzed, dimensions_processed, views_created, duration_seconds
                FROM dimension_organization_log
                ORDER BY execution_time DESC
                LIMIT 1
            '''
            
            recent_stats = self.conn.execute(recent_stats_query).fetchone()
            
            return {
                'view_types': [{'type': row[0], 'count': row[1]} for row in view_types],
                'recent_organization': {
                    'tables_analyzed': recent_stats[0] if recent_stats else 0,
                    'dimensions_processed': recent_stats[1] if recent_stats else 0,
                    'views_created': recent_stats[2] if recent_stats else 0,
                    'duration_seconds': recent_stats[3] if recent_stats else 0
                } if recent_stats else None,
                'total_views': sum(row[1] for row in view_types)
            }
            
        except Exception as e:
            logger.error(f"获取维度摘要失败: {e}")
            return {}
    
    def close(self):
        """关闭数据库连接"""
        if self.conn:
            self.conn.close()
            logger.info("维度组织器数据库连接已关闭")


# 测试函数
def test_dimension_organizer():
    """测试维度组织器"""
    import os
    
    # 创建测试数据库
    test_db = 'test_dimension.db'
    conn = sqlite3.connect(test_db)
    
    # 创建测试表
    test_tables = [
        ('raw_clean_sales_orders', '''
            CREATE TABLE raw_clean_sales_orders (
                order_id INTEGER PRIMARY KEY,
                customer_name TEXT,
                order_date TEXT,
                order_amount REAL,
                region TEXT,
                status TEXT
            )
        '''),
        ('raw_clean_general_ledger', '''
            CREATE TABLE raw_clean_general_ledger (
                id INTEGER PRIMARY KEY,
                account_code TEXT,
                transaction_date TEXT,
                amount REAL,
                description TEXT
            )
        ''')
    ]
    
    # 创建表并插入测试数据
    for table_name, create_sql in test_tables:
        conn.execute(create_sql)
        
        if 'sales_orders' in table_name:
            test_data = [
                (1, '客户A', '2023-01-15', 50000, '华东', '已完成'),
                (2, '客户B', '2023-02-20', 75000, '华南', '进行中'),
                (3, '客户C', '2023-03-10', 30000, '华北', '已完成'),
                (4, '客户D', '2023-04-05', 90000, '华东', '已取消')
            ]
            
            conn.executemany(f'''
                INSERT INTO {table_name} 
                (order_id, customer_name, order_date, order_amount, region, status)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', test_data)
            
        elif 'general_ledger' in table_name:
            test_data = [
                (1, '1001', '2023-01-01', 100000, '银行存款'),
                (2, '1002', '2023-01-02', 80000, '应收账款'),
                (3, '2001', '2023-01-03', 60000, '应付账款'),
                (4, '6001', '2023-01-04', 120000, '销售收入')
            ]
            
            conn.executemany(f'''
                INSERT INTO {table_name} 
                (id, account_code, transaction_date, amount, description)
                VALUES (?, ?, ?, ?, ?)
            ''', test_data)
    
    conn.commit()
    conn.close()
    
    # 测试维度组织器
    organizer = DimensionOrganizer(test_db)
    
    # 执行维度组织
    result = organizer.organize_by_all_dimensions()
    
    print("维度组织结果:")
    print(f"成功: {result['success']}")
    print(f"统计: {result['stats']}")
    print(f"执行时间: {result['execution_time']:.2f}秒")
    
    # 获取维度摘要
    summary = organizer.get_dimension_summary()
    print(f"\n维度摘要:")
    print(f"总视图数: {summary.get('total_views', 0)}")
    print(f"视图类型: {summary.get('view_types', [])}")
    
    organizer.close()
    
    # 清理测试文件
    if os.path.exists(test_db):
        os.remove(test_db)


if __name__ == "__main__":
    test_dimension_organizer()