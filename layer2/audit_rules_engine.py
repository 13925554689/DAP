"""
DAP - 审计规则引擎
基于YAML配置的智能审计规则处理
"""

import os
import sqlite3
import pandas as pd
import yaml
import re
from typing import Dict, Any, List, Optional, Union
import logging
from datetime import datetime
import json

logger = logging.getLogger(__name__)

class AuditRulesEngine:
    """审计规则引擎"""
    
    def __init__(self, db_path: str = 'data/dap_data.db', rules_file: str = 'config/audit_rules.yaml'):
        self.db_path = db_path
        self.rules_file = rules_file
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        
        # 加载审计规则
        self.rules = self.load_rules()
        
        # 规则执行统计
        self.execution_stats = {
            'total_rules': 0,
            'successful_rules': 0,
            'failed_rules': 0,
            'execution_time': 0
        }
        
        logger.info(f"审计规则引擎初始化完成，加载规则: {len(self.rules.get('rules', []))}")
    
    def load_rules(self) -> Dict[str, Any]:
        """加载审计规则"""
        try:
            if os.path.exists(self.rules_file):
                with open(self.rules_file, 'r', encoding='utf-8') as f:
                    rules = yaml.safe_load(f)
                    logger.info(f"从文件加载审计规则: {self.rules_file}")
                    return rules
            else:
                # 如果规则文件不存在，返回默认规则
                logger.warning(f"规则文件不存在: {self.rules_file}，使用默认规则")
                return self.get_default_rules()
                
        except Exception as e:
            logger.error(f"加载审计规则失败: {e}")
            return self.get_default_rules()
    
    def get_default_rules(self) -> Dict[str, Any]:
        """获取默认审计规则"""
        return {
            'version': '1.0',
            'description': 'DAP默认审计规则',
            'rules': [
                {
                    'rule_id': 'GL_ASSET_CLASSIFICATION',
                    'type': 'classification',
                    'description': '总账科目资产分类',
                    'enabled': True,
                    'target_pattern': 'raw_clean_*',
                    'conditions': [
                        {
                            'field_pattern': '*科目*|*account*',
                            'operator': 'prefix',
                            'value': '1'
                        }
                    ],
                    'action': {
                        'type': 'add_column',
                        'column_name': 'account_type',
                        'value': 'ASSET'
                    }
                },
                {
                    'rule_id': 'LARGE_AMOUNT_FLAG',
                    'type': 'validation',
                    'description': '大额交易标记',
                    'enabled': True,
                    'target_pattern': 'raw_clean_*',
                    'conditions': [
                        {
                            'field_pattern': '*金额*|*amount*|*money*',
                            'operator': 'greater_than',
                            'value': 100000
                        }
                    ],
                    'action': {
                        'type': 'add_column',
                        'column_name': 'large_amount_flag',
                        'value': True
                    }
                },
                {
                    'rule_id': 'DATE_VALIDATION',
                    'type': 'validation',
                    'description': '日期有效性验证',
                    'enabled': True,
                    'target_pattern': 'raw_clean_*',
                    'conditions': [
                        {
                            'field_pattern': '*日期*|*date*|*time*',
                            'operator': 'is_null',
                            'value': True
                        }
                    ],
                    'action': {
                        'type': 'add_column',
                        'column_name': 'date_missing_flag',
                        'value': True
                    }
                }
            ]
        }
    
    def apply_all_rules(self) -> Dict[str, Any]:
        """应用所有审计规则"""
        start_time = datetime.now()
        logger.info("开始应用审计规则")
        
        self.execution_stats = {
            'total_rules': 0,
            'successful_rules': 0,
            'failed_rules': 0,
            'execution_time': 0,
            'rule_results': []
        }
        
        rules_list = self.rules.get('rules', [])
        self.execution_stats['total_rules'] = len(rules_list)
        
        for rule in rules_list:
            if not rule.get('enabled', True):
                logger.info(f"跳过禁用规则: {rule.get('rule_id', 'unknown')}")
                continue
            
            try:
                result = self.apply_rule(rule)
                if result['success']:
                    self.execution_stats['successful_rules'] += 1
                    logger.info(f"✅ 规则应用成功: {rule['description']}")
                else:
                    self.execution_stats['failed_rules'] += 1
                    logger.warning(f"❌ 规则应用失败: {rule['description']} - {result.get('error', 'Unknown error')}")
                
                self.execution_stats['rule_results'].append(result)
                
            except Exception as e:
                self.execution_stats['failed_rules'] += 1
                error_result = {
                    'rule_id': rule.get('rule_id', 'unknown'),
                    'success': False,
                    'error': str(e),
                    'affected_records': 0
                }
                self.execution_stats['rule_results'].append(error_result)
                logger.error(f"❌ 规则执行异常: {rule.get('description', 'unknown')} - {e}")
        
        # 计算执行时间
        end_time = datetime.now()
        self.execution_stats['execution_time'] = (end_time - start_time).total_seconds()
        
        # 保存执行结果
        self._save_execution_stats()
        
        logger.info(f"审计规则应用完成，成功: {self.execution_stats['successful_rules']}, 失败: {self.execution_stats['failed_rules']}")
        return self.execution_stats
    
    def apply_rule(self, rule: Dict[str, Any]) -> Dict[str, Any]:
        """应用单个规则"""
        rule_id = rule.get('rule_id', 'unknown')
        rule_type = rule.get('type', 'unknown')
        
        logger.info(f"应用规则: {rule_id}")
        
        # 查找目标表
        target_tables = self._find_target_tables(rule.get('target_pattern', ''))
        
        if not target_tables:
            return {
                'rule_id': rule_id,
                'success': False,
                'error': '未找到匹配的目标表',
                'affected_records': 0
            }
        
        total_affected = 0
        
        for table_name in target_tables:
            try:
                # 查找匹配的字段
                matching_fields = self._find_matching_fields(table_name, rule.get('conditions', []))
                
                if not matching_fields:
                    continue
                
                # 应用规则逻辑
                affected_count = 0
                if rule_type == 'classification':
                    affected_count = self._apply_classification_rule(table_name, rule, matching_fields)
                elif rule_type == 'validation':
                    affected_count = self._apply_validation_rule(table_name, rule, matching_fields)
                elif rule_type == 'aggregation':
                    affected_count = self._apply_aggregation_rule(table_name, rule, matching_fields)
                else:
                    logger.warning(f"未知的规则类型: {rule_type}")
                
                total_affected += affected_count
                
            except Exception as e:
                logger.error(f"规则应用失败，表: {table_name}, 错误: {e}")
                continue
        
        return {
            'rule_id': rule_id,
            'success': True,
            'affected_records': total_affected,
            'target_tables': target_tables
        }
    
    def _find_target_tables(self, pattern: str) -> List[str]:
        """查找目标表"""
        try:
            # 获取所有表名
            query = "SELECT name FROM sqlite_master WHERE type='table' AND name LIKE ?"
            
            # 将通配符模式转换为SQL LIKE模式
            sql_pattern = pattern.replace('*', '%')
            
            results = self.conn.execute(query, (sql_pattern,)).fetchall()
            tables = [row[0] for row in results]
            
            logger.info(f"找到匹配表 '{pattern}': {tables}")
            return tables
            
        except Exception as e:
            logger.error(f"查找目标表失败: {e}")
            return []
    
    def _find_matching_fields(self, table_name: str, conditions: List[Dict[str, Any]]) -> List[Dict[str, str]]:
        """查找匹配的字段"""
        try:
            # 获取表的列信息
            columns_query = f"PRAGMA table_info({table_name})"
            columns_info = self.conn.execute(columns_query).fetchall()
            column_names = [col[1] for col in columns_info]  # 列名在第二个位置
            
            matching_fields = []
            
            for condition in conditions:
                field_pattern = condition.get('field_pattern', '')
                
                # 将通配符模式转换为正则表达式
                regex_pattern = field_pattern.replace('*', '.*').lower()
                
                for column_name in column_names:
                    if re.search(regex_pattern, column_name.lower()):
                        matching_fields.append({
                            'field_name': column_name,
                            'condition': condition
                        })
                        break  # 每个条件只匹配第一个符合的字段
            
            return matching_fields
            
        except Exception as e:
            logger.error(f"查找匹配字段失败 {table_name}: {e}")
            return []
    
    def _apply_classification_rule(self, table_name: str, rule: Dict[str, Any], 
                                 matching_fields: List[Dict[str, str]]) -> int:
        """应用分类规则"""
        action = rule.get('action', {})
        action_type = action.get('type')
        
        if action_type == 'add_column':
            return self._add_classification_column(table_name, rule, matching_fields)
        elif action_type == 'create_view':
            return self._create_classification_view(table_name, rule, matching_fields)
        else:
            logger.warning(f"未知的分类动作类型: {action_type}")
            return 0
    
    def _add_classification_column(self, table_name: str, rule: Dict[str, Any], 
                                  matching_fields: List[Dict[str, str]]) -> int:
        """添加分类列"""
        action = rule.get('action', {})
        column_name = action.get('column_name', 'classification')
        default_value = action.get('value', 'UNKNOWN')
        
        try:
            # 检查列是否已存在
            columns_query = f"PRAGMA table_info({table_name})"
            columns_info = self.conn.execute(columns_query).fetchall()
            existing_columns = [col[1] for col in columns_info]
            
            if column_name not in existing_columns:
                # 添加新列
                alter_sql = f"ALTER TABLE {table_name} ADD COLUMN {column_name} TEXT"
                self.conn.execute(alter_sql)
            
            # 构建WHERE条件
            where_conditions = []
            for field_info in matching_fields:
                field_name = field_info['field_name']
                condition = field_info['condition']
                
                condition_sql = self._build_condition_sql(field_name, condition)
                if condition_sql:
                    where_conditions.append(condition_sql)
            
            if where_conditions:
                where_clause = ' AND '.join(where_conditions)
                
                # 更新匹配记录
                update_sql = f"""
                    UPDATE {table_name} 
                    SET {column_name} = ? 
                    WHERE {where_clause}
                """
                
                cursor = self.conn.execute(update_sql, (default_value,))
                affected_count = cursor.rowcount
                
                self.conn.commit()
                return affected_count
            
            return 0
            
        except Exception as e:
            logger.error(f"添加分类列失败 {table_name}: {e}")
            return 0
    
    def _apply_validation_rule(self, table_name: str, rule: Dict[str, Any], 
                              matching_fields: List[Dict[str, str]]) -> int:
        """应用验证规则"""
        action = rule.get('action', {})
        action_type = action.get('type')
        
        if action_type == 'add_column':
            return self._add_validation_column(table_name, rule, matching_fields)
        elif action_type == 'create_alert':
            return self._create_validation_alert(table_name, rule, matching_fields)
        else:
            logger.warning(f"未知的验证动作类型: {action_type}")
            return 0
    
    def _add_validation_column(self, table_name: str, rule: Dict[str, Any], 
                              matching_fields: List[Dict[str, str]]) -> int:
        """添加验证标记列"""
        action = rule.get('action', {})
        column_name = action.get('column_name', 'validation_flag')
        flag_value = action.get('value', True)
        
        try:
            # 检查列是否已存在
            columns_query = f"PRAGMA table_info({table_name})"
            columns_info = self.conn.execute(columns_query).fetchall()
            existing_columns = [col[1] for col in columns_info]
            
            if column_name not in existing_columns:
                # 添加新列
                column_type = 'INTEGER' if isinstance(flag_value, bool) else 'TEXT'
                alter_sql = f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type}"
                self.conn.execute(alter_sql)
            
            # 构建WHERE条件
            where_conditions = []
            for field_info in matching_fields:
                field_name = field_info['field_name']
                condition = field_info['condition']
                
                condition_sql = self._build_condition_sql(field_name, condition)
                if condition_sql:
                    where_conditions.append(condition_sql)
            
            if where_conditions:
                where_clause = ' AND '.join(where_conditions)
                
                # 更新匹配记录
                update_sql = f"""
                    UPDATE {table_name} 
                    SET {column_name} = ? 
                    WHERE {where_clause}
                """
                
                cursor = self.conn.execute(update_sql, (flag_value,))
                affected_count = cursor.rowcount
                
                self.conn.commit()
                return affected_count
            
            return 0
            
        except Exception as e:
            logger.error(f"添加验证列失败 {table_name}: {e}")
            return 0
    
    def _apply_aggregation_rule(self, table_name: str, rule: Dict[str, Any], 
                               matching_fields: List[Dict[str, str]]) -> int:
        """应用聚合规则"""
        action = rule.get('action', {})
        action_type = action.get('type')
        
        if action_type == 'create_view':
            return self._create_aggregation_view(table_name, rule, matching_fields)
        elif action_type == 'create_table':
            return self._create_aggregation_table(table_name, rule, matching_fields)
        else:
            logger.warning(f"未知的聚合动作类型: {action_type}")
            return 0
    
    def _build_condition_sql(self, field_name: str, condition: Dict[str, Any]) -> Optional[str]:
        """构建SQL条件"""
        operator = condition.get('operator', '')
        value = condition.get('value')
        
        # 字段名加引号以处理包含空格的列名
        quoted_field = f'"{field_name}"'
        
        if operator == 'equals':
            return f"{quoted_field} = '{value}'"
        elif operator == 'prefix':
            return f"{quoted_field} LIKE '{value}%'"
        elif operator == 'suffix':
            return f"{quoted_field} LIKE '%{value}'"
        elif operator == 'contains':
            return f"{quoted_field} LIKE '%{value}%'"
        elif operator == 'greater_than':
            return f"{quoted_field} > {value}"
        elif operator == 'less_than':
            return f"{quoted_field} < {value}"
        elif operator == 'greater_equal':
            return f"{quoted_field} >= {value}"
        elif operator == 'less_equal':
            return f"{quoted_field} <= {value}"
        elif operator == 'is_null':
            return f"{quoted_field} IS NULL" if value else f"{quoted_field} IS NOT NULL"
        elif operator == 'in':
            if isinstance(value, list):
                value_list = "','".join(str(v) for v in value)
                return f"{quoted_field} IN ('{value_list}')"
        elif operator == 'between':
            if isinstance(value, dict) and 'min' in value and 'max' in value:
                return f"{quoted_field} BETWEEN {value['min']} AND {value['max']}"
        elif operator == 'regex':
            # SQLite的正则表达式支持（需要启用）
            return f"{quoted_field} REGEXP '{value}'"
        else:
            logger.warning(f"未知的操作符: {operator}")
            return None
    
    def _create_aggregation_view(self, table_name: str, rule: Dict[str, Any], 
                                matching_fields: List[Dict[str, str]]) -> int:
        """创建聚合视图"""
        action = rule.get('action', {})
        view_name = action.get('output_name', f"agg_{rule.get('rule_id', 'unknown')}")
        
        try:
            # 构建聚合SQL
            group_by = rule.get('group_by', [])
            aggregates = rule.get('aggregate', [])
            
            select_parts = []
            
            # 添加分组字段
            for field in group_by:
                select_parts.append(f'"{field}"')
            
            # 添加聚合字段
            for agg in aggregates:
                field = agg.get('field')
                function = agg.get('function', 'sum')
                alias = agg.get('alias', f"{function}_{field}")
                
                select_parts.append(f'{function.upper()}("{field}") as {alias}')
            
            if not select_parts:
                logger.warning(f"聚合规则缺少选择字段: {rule.get('rule_id')}")
                return 0
            
            select_clause = ', '.join(select_parts)
            group_clause = ', '.join(f'"{field}"' for field in group_by)
            
            # 删除已存在的视图
            drop_sql = f"DROP VIEW IF EXISTS {view_name}"
            self.conn.execute(drop_sql)
            
            # 创建新视图
            create_sql = f"""
                CREATE VIEW {view_name} AS
                SELECT {select_clause}
                FROM {table_name}
                {f'GROUP BY {group_clause}' if group_clause else ''}
            """
            
            self.conn.execute(create_sql)
            self.conn.commit()
            
            # 记录视图元数据
            self._record_rule_view(view_name, rule, table_name)
            
            logger.info(f"创建聚合视图: {view_name}")
            return 1  # 返回创建的视图数量
            
        except Exception as e:
            logger.error(f"创建聚合视图失败: {e}")
            return 0
    
    def _record_rule_view(self, view_name: str, rule: Dict[str, Any], base_table: str):
        """记录规则生成的视图"""
        try:
            # 检查meta_views表是否存在
            check_table_sql = """
                SELECT name FROM sqlite_master 
                WHERE type='table' AND name='meta_views'
            """
            
            result = self.conn.execute(check_table_sql).fetchone()
            if not result:
                # 创建meta_views表
                create_table_sql = '''
                    CREATE TABLE meta_views (
                        view_name TEXT PRIMARY KEY,
                        view_type TEXT,
                        base_tables TEXT,
                        rule_id TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                '''
                self.conn.execute(create_table_sql)
            
            # 插入视图记录
            insert_sql = '''
                INSERT OR REPLACE INTO meta_views
                (view_name, view_type, base_tables, rule_id)
                VALUES (?, ?, ?, ?)
            '''
            
            self.conn.execute(insert_sql, (
                view_name,
                'audit_rule',
                json.dumps([base_table]),
                rule.get('rule_id', 'unknown')
            ))
            
            self.conn.commit()
            
        except Exception as e:
            logger.warning(f"记录规则视图失败: {e}")
    
    def _save_execution_stats(self):
        """保存执行统计"""
        try:
            # 创建审计执行记录表
            create_table_sql = '''
                CREATE TABLE IF NOT EXISTS audit_execution_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    execution_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    total_rules INTEGER,
                    successful_rules INTEGER,
                    failed_rules INTEGER,
                    duration_seconds REAL,
                    details TEXT
                )
            '''
            
            self.conn.execute(create_table_sql)
            
            # 插入执行记录
            insert_sql = '''
                INSERT INTO audit_execution_log
                (total_rules, successful_rules, failed_rules, duration_seconds, details)
                VALUES (?, ?, ?, ?, ?)
            '''
            
            self.conn.execute(insert_sql, (
                self.execution_stats['total_rules'],
                self.execution_stats['successful_rules'],
                self.execution_stats['failed_rules'],
                self.execution_stats['execution_time'],
                json.dumps(self.execution_stats['rule_results'], ensure_ascii=False)
            ))
            
            self.conn.commit()
            
        except Exception as e:
            logger.warning(f"保存执行统计失败: {e}")
    
    def get_execution_history(self, limit: int = 10) -> List[Dict[str, Any]]:
        """获取执行历史"""
        try:
            query = '''
                SELECT execution_time, total_rules, successful_rules, failed_rules, 
                       duration_seconds
                FROM audit_execution_log
                ORDER BY execution_time DESC
                LIMIT ?
            '''
            
            results = self.conn.execute(query, (limit,)).fetchall()
            
            history = []
            for row in results:
                history.append({
                    'execution_time': row[0],
                    'total_rules': row[1],
                    'successful_rules': row[2],
                    'failed_rules': row[3],
                    'duration_seconds': row[4]
                })
            
            return history
            
        except Exception as e:
            logger.error(f"获取执行历史失败: {e}")
            return []
    
    def validate_rules(self) -> Dict[str, Any]:
        """验证规则配置的有效性"""
        validation_result = {
            'is_valid': True,
            'errors': [],
            'warnings': []
        }
        
        rules_list = self.rules.get('rules', [])
        
        for i, rule in enumerate(rules_list):
            rule_id = rule.get('rule_id', f'rule_{i}')
            
            # 检查必需字段
            required_fields = ['rule_id', 'type', 'description', 'conditions', 'action']
            for field in required_fields:
                if field not in rule:
                    validation_result['errors'].append(f"规则 {rule_id} 缺少必需字段: {field}")
                    validation_result['is_valid'] = False
            
            # 检查规则类型
            valid_types = ['classification', 'validation', 'aggregation']
            if rule.get('type') not in valid_types:
                validation_result['errors'].append(f"规则 {rule_id} 类型无效: {rule.get('type')}")
                validation_result['is_valid'] = False
            
            # 检查条件格式
            conditions = rule.get('conditions', [])
            if not isinstance(conditions, list) or not conditions:
                validation_result['errors'].append(f"规则 {rule_id} 条件配置无效")
                validation_result['is_valid'] = False
        
        return validation_result
    
    def close(self):
        """关闭数据库连接"""
        if self.conn:
            self.conn.close()
            logger.info("审计规则引擎数据库连接已关闭")


# 测试函数
def test_audit_rules_engine():
    """测试审计规则引擎"""
    import os
    
    # 创建测试数据库
    test_db = 'test_audit_rules.db'
    conn = sqlite3.connect(test_db)
    
    # 创建测试表
    test_table_sql = '''
        CREATE TABLE raw_clean_test_transactions (
            id INTEGER PRIMARY KEY,
            account_code TEXT,
            amount REAL,
            transaction_date TEXT,
            description TEXT
        )
    '''
    
    conn.execute(test_table_sql)
    
    # 插入测试数据
    test_data = [
        (1, '1001', 50000, '2023-01-01', '银行存款'),
        (2, '1002', 150000, '2023-01-02', '应收账款'),
        (3, '2001', 80000, '2023-01-03', '应付账款'),
        (4, '6001', 25000, '2023-01-04', '销售收入'),
        (5, '5001', 30000, '2023-01-05', '销售成本')
    ]
    
    conn.executemany('''
        INSERT INTO raw_clean_test_transactions 
        (id, account_code, amount, transaction_date, description)
        VALUES (?, ?, ?, ?, ?)
    ''', test_data)
    
    conn.commit()
    conn.close()
    
    # 测试规则引擎
    engine = AuditRulesEngine(test_db, 'config/test_audit_rules.yaml')
    
    # 应用规则
    stats = engine.apply_all_rules()
    
    print("规则执行统计:")
    print(f"总规则数: {stats['total_rules']}")
    print(f"成功规则数: {stats['successful_rules']}")
    print(f"失败规则数: {stats['failed_rules']}")
    print(f"执行时间: {stats['execution_time']:.2f}秒")
    
    # 查看结果
    conn = sqlite3.connect(test_db)
    result_df = pd.read_sql_query("SELECT * FROM raw_clean_test_transactions", conn)
    print("\n处理后的数据:")
    print(result_df)
    
    conn.close()
    engine.close()
    
    # 清理测试文件
    if os.path.exists(test_db):
        os.remove(test_db)


if __name__ == "__main__":
    import os
    test_audit_rules_engine()