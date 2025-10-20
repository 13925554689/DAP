"""
DAP - 数据接入模块
智能识别和处理各种数据源
"""

import os
import zipfile
import sqlite3
import pandas as pd
from pathlib import Path
import subprocess
import tempfile
import shutil
from typing import Dict, Any, List
import logging
from datetime import datetime

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class DataIngestor:
    """智能数据接入器"""
    
    def __init__(self):
        self.handlers = {
            'sql_backup': SQLBackupHandler(),
            'excel_file': ExcelHandler(),
            'csv_file': CSVHandler(),
            'database_file': DatabaseHandler(),
            'archive_file': ArchiveHandler(),
            'ais_database': AISHandler(),  # 新增AIS处理器
            'database_folder': DatabaseFolderHandler()  # 新增数据库文件夹处理器
        }
        
        # 扩展名到类型的映射
        self.ext_to_type = {
            '.bak': 'sql_backup',
            '.sql': 'sql_backup',
            '.xlsx': 'excel_file',
            '.xls': 'excel_file',
            '.csv': 'csv_file',
            '.zip': 'archive_file',
            '.rar': 'archive_file',
            '.7z': 'archive_file',
            '.mdb': 'database_file',
            '.accdb': 'database_file',
            '.db': 'database_file',
            '.sqlite': 'database_file',
            '.ais': 'ais_database'  # 新增AIS文件支持
        }
        
        # 数据库文件夹批量导入配置
        self.batch_import_config = {
            'max_files_per_batch': 100,
            'supported_db_extensions': ['.db', '.sqlite', '.mdb', '.accdb', '.ais'],
            'parallel_processing': True,
            'max_workers': 4
        }
    
    def ingest(self, file_path: str) -> Dict[str, pd.DataFrame]:
        """智能识别并接入数据"""
        logger.info(f"开始处理数据源: {file_path}")
        
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"文件不存在: {file_path}")
        
        if os.path.isdir(file_path):
            # 检查是否为数据库文件夹（包含多个数据库文件）
            if self._is_database_folder(file_path):
                return self._ingest_database_folder(file_path)
            else:
                return self._ingest_directory(file_path)
        
        file_type = self.detect_file_type(file_path)
        handler = self.handlers.get(file_type)
        
        if not handler:
            raise ValueError(f"不支持的文件类型: {file_type}")
        
        logger.info(f"使用处理器: {file_type}")
        return handler.process(file_path)
    
    def detect_file_type(self, file_path: str) -> str:
        """智能文件类型检测"""
        # 1. 扩展名检测
        ext = Path(file_path).suffix.lower()
        
        # 2. 对于备份文件进行内容检测
        if ext == '.bak':
            return self._detect_backup_type(file_path)
        
        # 3. 魔术字节检测
        try:
            with open(file_path, 'rb') as f:
                header = f.read(16)
                if header.startswith(b'PK'):  # ZIP格式
                    return 'archive_file'
                if header.startswith(b'\x50\x4b'):  # 另一种ZIP标识
                    return 'archive_file'
        except (OSError, IOError) as e:
            logger.debug(f"文件魔术字节检测失败: {e}")
        
        return self.ext_to_type.get(ext, 'unknown')
    
    def _detect_backup_type(self, file_path: str) -> str:
        """检测备份文件类型"""
        try:
            with open(file_path, 'rb') as f:
                header = f.read(256)
                # SQL Server备份文件特征
                if b'TAPE' in header or b'DISK' in header:
                    return 'sql_backup'
        except (OSError, IOError) as e:
            logger.debug(f"备份文件类型检测失败: {e}")
        return 'sql_backup'  # 默认作为SQL备份处理
    
    def _ingest_directory(self, dir_path: str) -> Dict[str, pd.DataFrame]:
        """处理文件夹中的多个文件"""
        logger.info(f"处理文件夹: {dir_path}")
        all_data = {}
        
        for root, dirs, files in os.walk(dir_path):
            for file in files:
                file_path = os.path.join(root, file)
                try:
                    file_data = self.ingest(file_path)
                    # 添加文件名前缀避免表名冲突
                    file_prefix = Path(file).stem
                    for table_name, data in file_data.items():
                        new_table_name = f"{file_prefix}_{table_name}"
                        all_data[new_table_name] = data
                except Exception as e:
                    logger.warning(f"处理文件失败 {file_path}: {e}")
                    continue
        
        return all_data
    
    def _is_database_folder(self, dir_path: str) -> bool:
        """检查文件夹是否为数据库文件夹"""
        db_file_count = 0
        total_files = 0
        
        for root, dirs, files in os.walk(dir_path):
            for file in files:
                total_files += 1
                file_ext = Path(file).suffix.lower()
                if file_ext in self.batch_import_config['supported_db_extensions']:
                    db_file_count += 1
        
        # 如果数据库文件占比超过50%，认为是数据库文件夹
        if total_files > 0:
            db_ratio = db_file_count / total_files
            return db_ratio > 0.5 and db_file_count >= 2
        
        return False
    
    def _ingest_database_folder(self, dir_path: str) -> Dict[str, pd.DataFrame]:
        """批量处理数据库文件夹"""
        logger.info(f"开始批量处理数据库文件夹: {dir_path}")
        
        # 收集所有数据库文件
        db_files = []
        for root, dirs, files in os.walk(dir_path):
            for file in files:
                file_ext = Path(file).suffix.lower()
                if file_ext in self.batch_import_config['supported_db_extensions']:
                    file_path = os.path.join(root, file)
                    db_files.append(file_path)
        
        logger.info(f"发现 {len(db_files)} 个数据库文件")
        
        # 检查文件数量限制
        if len(db_files) > self.batch_import_config['max_files_per_batch']:
            logger.warning(f"数据库文件数量 ({len(db_files)}) 超过限制 ({self.batch_import_config['max_files_per_batch']})")
            db_files = db_files[:self.batch_import_config['max_files_per_batch']]
        
        all_data = {}
        
        if self.batch_import_config['parallel_processing'] and len(db_files) > 1:
            # 并行处理
            all_data = self._parallel_process_databases(db_files)
        else:
            # 串行处理
            all_data = self._serial_process_databases(db_files)
        
        logger.info(f"批量导入完成，共处理 {len(all_data)} 个数据表")
        return all_data
    
    def _parallel_process_databases(self, db_files: List[str]) -> Dict[str, pd.DataFrame]:
        """并行处理数据库文件"""
        from concurrent.futures import ThreadPoolExecutor, as_completed
        
        all_data = {}
        max_workers = min(self.batch_import_config['max_workers'], len(db_files))
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # 提交任务
            future_to_file = {
                executor.submit(self._process_single_database, file_path): file_path 
                for file_path in db_files
            }
            
            # 收集结果
            for future in as_completed(future_to_file):
                file_path = future_to_file[future]
                try:
                    file_data = future.result()
                    if file_data:
                        # 添加文件名前缀避免表名冲突
                        file_prefix = Path(file_path).stem
                        for table_name, data in file_data.items():
                            new_table_name = f"{file_prefix}_{table_name}"
                            all_data[new_table_name] = data
                except Exception as e:
                    logger.error(f"并行处理数据库文件失败 {file_path}: {e}")
        
        return all_data
    
    def _serial_process_databases(self, db_files: List[str]) -> Dict[str, pd.DataFrame]:
        """串行处理数据库文件"""
        all_data = {}
        
        for file_path in db_files:
            try:
                file_data = self._process_single_database(file_path)
                if file_data:
                    # 添加文件名前缀避免表名冲突
                    file_prefix = Path(file_path).stem
                    for table_name, data in file_data.items():
                        new_table_name = f"{file_prefix}_{table_name}"
                        all_data[new_table_name] = data
            except Exception as e:
                logger.error(f"串行处理数据库文件失败 {file_path}: {e}")
                continue
        
        return all_data
    
    def _process_single_database(self, file_path: str) -> Dict[str, pd.DataFrame]:
        """处理单个数据库文件"""
        try:
            file_type = self.detect_file_type(file_path)
            handler = self.handlers.get(file_type)
            
            if handler:
                logger.info(f"处理数据库文件: {Path(file_path).name}")
                return handler.process(file_path)
            else:
                logger.warning(f"不支持的数据库文件类型: {file_path}")
                return {}
        except Exception as e:
            logger.error(f"处理数据库文件失败 {file_path}: {e}")
            return {}


class SQLBackupHandler:
    """SQL Server备份文件处理器"""
    
    def process(self, backup_path: str) -> Dict[str, pd.DataFrame]:
        """处理SQL Server备份文件"""
        logger.info("处理SQL Server备份文件")
        
        # 创建临时工作目录
        temp_dir = tempfile.mkdtemp()
        temp_db_name = f"dap_temp_{os.getpid()}"
        
        try:
            # 1. 尝试恢复备份
            if self._has_sqlcmd():
                return self._restore_with_sqlcmd(backup_path, temp_db_name)
            else:
                # 如果没有sqlcmd，尝试其他方法
                return self._fallback_sql_processing(backup_path)
        
        finally:
            # 清理临时文件
            if os.path.exists(temp_dir):
                shutil.rmtree(temp_dir)
    
    def _has_sqlcmd(self) -> bool:
        """检查是否有sqlcmd工具"""
        try:
            subprocess.run(['sqlcmd', '-?'], capture_output=True, check=False)
            return True
        except FileNotFoundError:
            return False
    
    def _restore_with_sqlcmd(self, backup_path: str, temp_db_name: str) -> Dict[str, pd.DataFrame]:
        """使用sqlcmd恢复备份"""
        try:
            # 恢复数据库
            restore_cmd = f'''
            sqlcmd -S localhost -Q "
            RESTORE DATABASE {temp_db_name} 
            FROM DISK = '{backup_path}' 
            WITH REPLACE, 
            MOVE 'DataFile' TO 'C:\\temp\\{temp_db_name}_data.mdf',
            MOVE 'LogFile' TO 'C:\\temp\\{temp_db_name}_log.ldf'"
            '''
            
            result = subprocess.run(restore_cmd, shell=True, capture_output=True, text=True)
            if result.returncode != 0:
                raise Exception(f"数据库恢复失败: {result.stderr}")
            
            # 导出表数据
            return self._export_tables_from_database(temp_db_name)
            
        finally:
            # 清理临时数据库
            self._cleanup_database(temp_db_name)
    
    def _fallback_sql_processing(self, backup_path: str) -> Dict[str, pd.DataFrame]:
        """备用SQL处理方法"""
        logger.warning("无法使用sqlcmd，尝试备用解析方法")
        
        # 如果是.sql文件，直接读取SQL语句
        if backup_path.endswith('.sql'):
            return self._parse_sql_file(backup_path)
        
        # 对于.bak文件，尝试备用解析方法
        if backup_path.endswith('.bak'):
            return self._parse_bak_file_fallback(backup_path)
        
        logger.error("不支持的备份文件格式")
        return {}
    
    def _parse_bak_file_fallback(self, backup_path: str) -> Dict[str, pd.DataFrame]:
        """备用BAK文件解析方法"""
        try:
            import struct
            file_info = {
                'file_name': [Path(backup_path).name],
                'file_path': [backup_path],
                'file_size': [os.path.getsize(backup_path)],
                'file_type': ['SQL Server Backup'],
                'status': ['解析受限 - 需要SQL Server环境进行完整解析'],
                'recommendation': ['请使用SQL Server Management Studio导出为.sql文件'],
                'last_modified': [datetime.fromtimestamp(os.path.getmtime(backup_path))]
            }
            
            # 尝试读取BAK文件头部信息
            try:
                with open(backup_path, 'rb') as f:
                    header = f.read(1024)
                    # 检查BAK文件标识
                    if b'TAPE' in header or b'DISK' in header:
                        file_info['backup_type'] = ['SQL Server Native Backup']
                    else:
                        file_info['backup_type'] = ['Unknown Backup Format']
                        
                    # 尝试提取数据库名称
                    try:
                        db_name_start = header.find(b'master') 
                        if db_name_start > 0:
                            file_info['database_hint'] = ['Contains master database reference']
                    except:
                        pass
                        
            except Exception as e:
                logger.warning(f"BAK文件头部读取失败: {e}")
                file_info['header_status'] = ['Header read failed']
            
            df = pd.DataFrame(file_info)
            return {'bak_file_info': df}
            
        except Exception as e:
            logger.error(f"BAK文件备用解析失败: {e}")
            # 返回基本文件信息
            return self._create_file_info_fallback(backup_path, 'BAK Backup File')
    
    def _parse_sql_file(self, sql_path: str) -> Dict[str, pd.DataFrame]:
        """解析SQL文件"""
        tables_data = {}
        
        try:
            # 尝试多种编码
            encodings = ['utf-8', 'gbk', 'gb2312', 'latin-1']
            sql_content = None
            
            for encoding in encodings:
                try:
                    with open(sql_path, 'r', encoding=encoding) as f:
                        sql_content = f.read()
                        break
                except UnicodeDecodeError:
                    continue
            
            if not sql_content:
                raise Exception("无法使用任何编码读取SQL文件")
            
            # 尝试提取CREATE TABLE语句
            import re
            
            # 查找CREATE TABLE语句
            create_table_pattern = r'CREATE\s+TABLE\s+(\[?)(\w+)\1?\s*\((.*?)\);'
            tables = re.findall(create_table_pattern, sql_content, re.IGNORECASE | re.DOTALL)
            
            # 查找INSERT语句
            insert_pattern = r'INSERT\s+INTO\s+(\[?)(\w+)\1?\s*(?:\(([^)]+)\))?\s*VALUES\s*\((.*?)\);'
            inserts = re.findall(insert_pattern, sql_content, re.IGNORECASE | re.DOTALL)
            
            # 处理找到的表
            if tables:
                for _, table_name, columns_def in tables:
                    # 解析列定义
                    columns = self._parse_table_columns(columns_def)
                    
                    # 查找对应的INSERT数据
                    table_inserts = [ins for ins in inserts if ins[1].lower() == table_name.lower()]
                    
                    if table_inserts:
                        # 解析INSERT数据
                        table_data = self._parse_insert_data(table_inserts, columns)
                        if not table_data.empty:
                            tables_data[table_name] = table_data
                    else:
                        # 创建空表结构
                        empty_data = {col['name']: [] for col in columns}
                        tables_data[f"{table_name}_structure"] = pd.DataFrame(empty_data)
            
            # 如果没有找到表结构，至少返回基本信息
            if not tables_data:
                file_info = {
                    'file_name': [Path(sql_path).name],
                    'file_size': [os.path.getsize(sql_path)],
                    'tables_found': [len(tables)],
                    'inserts_found': [len(inserts)],
                    'content_length': [len(sql_content)],
                    'status': ['SQL文件已解析，但未找到完整的表结构数据']
                }
                tables_data['sql_file_info'] = pd.DataFrame(file_info)
                
            logger.info(f"SQL文件解析完成，找到 {len(tables_data)} 个数据表")
            
        except Exception as e:
            logger.error(f"SQL文件解析失败: {e}")
            # 返回错误信息
            error_info = {
                'file_name': [Path(sql_path).name],
                'error': [str(e)],
                'status': ['SQL解析失败'],
                'recommendation': ['请检查SQL文件格式和编码']
            }
            tables_data['sql_parse_error'] = pd.DataFrame(error_info)
        
        return tables_data
    
    def _parse_table_columns(self, columns_def: str) -> list:
        """解析表列定义"""
        columns = []
        try:
            # 简单的列解析
            import re
            col_pattern = r'(\w+)\s+([^,\n]+?)(?:,|\s*$)'
            matches = re.findall(col_pattern, columns_def.replace('\n', ' '), re.IGNORECASE)
            
            for col_name, col_type in matches:
                columns.append({
                    'name': col_name.strip(),
                    'type': col_type.strip()
                })
        except Exception as e:
            logger.warning(f"列定义解析失败: {e}")
            
        return columns or [{'name': 'data', 'type': 'text'}]
    
    def _parse_insert_data(self, inserts: list, columns: list) -> pd.DataFrame:
        """解析INSERT数据"""
        try:
            all_data = []
            col_names = [col['name'] for col in columns]
            
            for _, table_name, col_spec, values_part in inserts:
                # 解析VALUES中的数据
                import re
                # 查找所有的值组
                value_groups = re.findall(r'\((.*?)\)', values_part)
                
                for value_group in value_groups:
                    # 简单的值解析（需要处理引号、逗号等）
                    values = [v.strip().strip("'\"") for v in value_group.split(',')]
                    
                    # 确保值的数量与列匹配
                    if len(values) == len(col_names):
                        row_data = dict(zip(col_names, values))
                        all_data.append(row_data)
                    elif len(values) < len(col_names):
                        # 补齐缺失的列
                        row_data = dict(zip(col_names, values + [''] * (len(col_names) - len(values))))
                        all_data.append(row_data)
            
            return pd.DataFrame(all_data)
            
        except Exception as e:
            logger.warning(f"INSERT数据解析失败: {e}")
            return pd.DataFrame()
    
    def _create_file_info_fallback(self, file_path: str, file_type: str) -> Dict[str, pd.DataFrame]:
        """创建文件信息回退数据"""
        file_info = {
            'file_name': [Path(file_path).name],
            'file_path': [file_path],
            'file_size': [os.path.getsize(file_path)],
            'file_type': [file_type],
            'status': ['Parse Failed - Basic Info Only'],
            'last_modified': [datetime.fromtimestamp(os.path.getmtime(file_path))]
        }
        
        df = pd.DataFrame(file_info)
        return {'file_info': df}
    
    def _export_tables_from_database(self, db_name: str) -> Dict[str, pd.DataFrame]:
        """从数据库导出表数据"""
        # 这里需要实现数据库连接和表导出逻辑
        # 简化实现
        return {}
    
    def _cleanup_database(self, db_name: str):
        """清理临时数据库"""
        try:
            cleanup_cmd = f'sqlcmd -S localhost -Q "DROP DATABASE {db_name}"'
            subprocess.run(cleanup_cmd, shell=True, capture_output=True)
        except Exception:
            pass


class ExcelHandler:
    """Excel文件处理器"""
    
    def process(self, file_path: str) -> Dict[str, pd.DataFrame]:
        """处理Excel文件"""
        logger.info(f"处理Excel文件: {file_path}")
        
        try:
            # 读取所有工作表
            excel_file = pd.ExcelFile(file_path)
            tables_data = {}
            
            for sheet_name in excel_file.sheet_names:
                try:
                    # 读取工作表数据
                    df = pd.read_excel(file_path, sheet_name=sheet_name)
                    
                    # 跳过空表
                    if df.empty:
                        continue
                    
                    # 清理列名
                    df.columns = [str(col).strip() for col in df.columns]
                    
                    # 移除完全空白的行
                    df = df.dropna(how='all')
                    
                    if not df.empty:
                        tables_data[sheet_name] = df
                        logger.info(f"成功读取工作表: {sheet_name}, 行数: {len(df)}")
                
                except Exception as e:
                    logger.warning(f"读取工作表失败 {sheet_name}: {e}")
                    continue
            
            return tables_data
            
        except Exception as e:
            logger.error(f"Excel文件处理失败: {e}")
            raise


class CSVHandler:
    """CSV文件处理器"""
    
    def process(self, file_path: str) -> Dict[str, pd.DataFrame]:
        """处理CSV文件"""
        logger.info(f"处理CSV文件: {file_path}")
        
        try:
            # 自动检测编码
            encoding = self._detect_encoding(file_path)
            
            # 自动检测分隔符
            separator = self._detect_separator(file_path, encoding)
            
            # 读取CSV数据
            df = pd.read_csv(file_path, encoding=encoding, sep=separator)
            
            # 清理数据
            df.columns = [str(col).strip() for col in df.columns]
            df = df.dropna(how='all')
            
            # 使用文件名作为表名
            table_name = Path(file_path).stem
            
            logger.info(f"成功读取CSV文件, 行数: {len(df)}")
            return {table_name: df}
            
        except Exception as e:
            logger.error(f"CSV文件处理失败: {e}")
            raise
    
    def _detect_encoding(self, file_path: str) -> str:
        """检测文件编码"""
        encodings = ['utf-8', 'gbk', 'gb2312', 'utf-16', 'ascii']
        
        for encoding in encodings:
            try:
                with open(file_path, 'r', encoding=encoding) as f:
                    f.read(1000)  # 读取前1000字符测试
                return encoding
            except Exception:
                continue
        
        return 'utf-8'  # 默认编码
    
    def _detect_separator(self, file_path: str, encoding: str) -> str:
        """检测分隔符"""
        separators = [',', ';', '\t', '|']
        
        try:
            with open(file_path, 'r', encoding=encoding) as f:
                first_line = f.readline()
            
            # 统计各分隔符出现次数
            sep_counts = {sep: first_line.count(sep) for sep in separators}
            
            # 返回出现次数最多的分隔符
            return max(sep_counts, key=sep_counts.get)
            
        except Exception:
            return ','  # 默认逗号分隔


class DatabaseHandler:
    """数据库文件处理器"""
    
    def process(self, file_path: str) -> Dict[str, pd.DataFrame]:
        """处理数据库文件"""
        logger.info(f"处理数据库文件: {file_path}")
        
        ext = Path(file_path).suffix.lower()
        
        if ext in ['.db', '.sqlite']:
            return self._process_sqlite(file_path)
        elif ext in ['.mdb', '.accdb']:
            return self._process_access(file_path)
        else:
            raise ValueError(f"不支持的数据库格式: {ext}")
    
    def _process_sqlite(self, file_path: str) -> Dict[str, pd.DataFrame]:
        """处理SQLite数据库"""
        tables_data = {}
        
        try:
            conn = sqlite3.connect(file_path)
            
            # 获取所有表名
            tables = pd.read_sql_query(
                "SELECT name FROM sqlite_master WHERE type='table'", 
                conn
            )
            
            for table_name in tables['name']:
                try:
                    df = pd.read_sql_query(f"SELECT * FROM {table_name}", conn)
                    if not df.empty:
                        tables_data[table_name] = df
                        logger.info(f"读取表: {table_name}, 行数: {len(df)}")
                except Exception as e:
                    logger.warning(f"读取表失败 {table_name}: {e}")
            
            conn.close()
            return tables_data
            
        except Exception as e:
            logger.error(f"SQLite处理失败: {e}")
            raise
    
    def _process_access(self, file_path: str) -> Dict[str, pd.DataFrame]:
        """处理Access数据库"""
        # Access数据库需要特殊的驱动，这里提供简化实现
        logger.warning("Access数据库处理需要额外的驱动支持")
        return {}


class ArchiveHandler:
    """压缩文件处理器"""
    
    def process(self, file_path: str) -> Dict[str, pd.DataFrame]:
        """处理压缩文件"""
        logger.info(f"处理压缩文件: {file_path}")
        
        # 创建临时解压目录
        temp_dir = tempfile.mkdtemp()
        
        try:
            # 解压文件
            if file_path.endswith('.zip'):
                with zipfile.ZipFile(file_path, 'r') as zip_ref:
                    zip_ref.extractall(temp_dir)
            else:
                # 其他压缩格式需要额外处理
                logger.warning(f"暂不支持的压缩格式: {Path(file_path).suffix}")
                return {}
            
            # 处理解压后的文件
            ingestor = DataIngestor()
            return ingestor._ingest_directory(temp_dir)
            
        finally:
            # 清理临时目录
            if os.path.exists(temp_dir):
                shutil.rmtree(temp_dir)


class AISHandler:
    """AIS数据库文件处理器（河南泰田重工机械制造有限公司专用格式）"""
    
    def process(self, file_path: str) -> Dict[str, pd.DataFrame]:
        """处理AIS数据库文件"""
        logger.info(f"处理AIS数据库文件: {file_path}")
        
        try:
            # AIS文件通常是一种专有的数据库格式
            # 先尝试作为SQLite数据库打开
            tables_data = self._try_sqlite_format(file_path)
            
            if not tables_data:
                # 如果SQLite格式失败，尝试其他方法
                tables_data = self._try_binary_format(file_path)
            
            if not tables_data:
                # 如果都失败，尝试文本格式解析
                tables_data = self._try_text_format(file_path)
            
            # 为AIS文件添加特殊的元数据标记
            for table_name, data in tables_data.items():
                if isinstance(data, pd.DataFrame) and not data.empty:
                    # 添加数据源标记
                    data.attrs['source_type'] = 'AIS'
                    data.attrs['source_file'] = Path(file_path).name
                    data.attrs['company'] = self._extract_company_name(file_path)
                    data.attrs['year'] = self._extract_year(file_path)
            
            return tables_data
            
        except Exception as e:
            logger.error(f"AIS文件处理失败: {e}")
            # 返回基本信息，即使解析失败
            return self._create_fallback_data(file_path)
    
    def _try_sqlite_format(self, file_path: str) -> Dict[str, pd.DataFrame]:
        """尝试以SQLite格式读取AIS文件"""
        try:
            conn = sqlite3.connect(file_path)
            
            # 获取所有表名
            tables = pd.read_sql_query(
                "SELECT name FROM sqlite_master WHERE type='table'", 
                conn
            )
            
            tables_data = {}
            for table_name in tables['name']:
                try:
                    df = pd.read_sql_query(f"SELECT * FROM {table_name}", conn)
                    if not df.empty:
                        tables_data[table_name] = df
                        logger.info(f"AIS-SQLite读取表: {table_name}, 行数: {len(df)}")
                except Exception as e:
                    logger.warning(f"读取AIS表失败 {table_name}: {e}")
            
            conn.close()
            return tables_data
            
        except Exception as e:
            logger.debug(f"AIS文件非SQLite格式: {e}")
            return {}
    
    def _try_binary_format(self, file_path: str) -> Dict[str, pd.DataFrame]:
        """尝试解析AIS二进制格式"""
        try:
            # 读取文件头部信息
            with open(file_path, 'rb') as f:
                header = f.read(1024)
                
                # 检查是否有已知的AIS文件特征
                if self._is_ais_binary_format(header):
                    # 这里需要根据AIS文件的具体格式进行解析
                    # 由于没有具体的格式规范，这里提供一个框架
                    return self._parse_ais_binary(file_path)
                
        except Exception as e:
            logger.debug(f"AIS二进制格式解析失败: {e}")
            
        return {}
    
    def _try_text_format(self, file_path: str) -> Dict[str, pd.DataFrame]:
        """尝试以文本格式读取AIS文件"""
        try:
            # 尝试不同编码
            encodings = ['utf-8', 'gbk', 'gb2312', 'ascii']
            
            for encoding in encodings:
                try:
                    # 检查是否为分隔符格式
                    data = pd.read_csv(file_path, encoding=encoding, sep=None, engine='python')
                    if not data.empty:
                        table_name = f"ais_data_{Path(file_path).stem}"
                        return {table_name: data}
                except Exception:
                    continue
                    
        except Exception as e:
            logger.debug(f"AIS文本格式解析失败: {e}")
            
        return {}
    
    def _is_ais_binary_format(self, header: bytes) -> bool:
        """检查是否为AIS二进制格式"""
        # 这里需要根据实际的AIS文件特征来判断
        # 可能的特征包括：特定的魔术字节、版本信息等
        
        # 示例：检查是否包含特定标识
        ais_signatures = [
            b'AIS',  # 可能的文件标识
            b'TAITAIN',  # 泰田重工的标识
            b'\x00\x01\x00\x00',  # 可能的版本标识
        ]
        
        for signature in ais_signatures:
            if signature in header:
                return True
                
        return False
    
    def _parse_ais_binary(self, file_path: str) -> Dict[str, pd.DataFrame]:
        """解析AIS二进制文件"""
        # 这里是AIS二进制格式的具体解析逻辑
        # 需要根据实际文件格式实现
        
        logger.warning("AIS二进制格式解析需要具体的格式规范")
        
        # 返回文件基本信息
        return self._create_fallback_data(file_path)
    
    def _extract_company_name(self, file_path: str) -> str:
        """从文件名中提取公司名称"""
        file_name = Path(file_path).stem
        
        # 从文件名中提取公司信息
        if '河南泰田重工机械制造有限公司' in file_name:
            return '河南泰田重工机械制造有限公司'
        elif 'taitain' in file_name.lower():
            return 'TaiTain Heavy Industry'
        elif '泰田' in file_name:
            return '泰田重工'
        
        # 尝试从路径中提取
        path_parts = Path(file_path).parts
        for part in path_parts:
            if '泰田' in part or 'taitain' in part.lower():
                return part
                
        return 'Unknown Company'
    
    def _sanitize_table_name(self, name: str) -> str:
        """清理表名，确保SQL兼容"""
        import re
        
        # 创建公司名称映射
        name_mapping = {
            '河南泰田重工机械制造有限公司': 'henan_taitain_heavy_industry',
            '泰田重工': 'taitain_heavy_industry',
            'TaiTain Heavy Industry': 'taitain_heavy_industry'
        }
        
        # 如果是已知公司名称，使用映射
        if name in name_mapping:
            return name_mapping[name]
        
        # 通用清理规则
        # 1. 移除或替换特殊字符
        cleaned = re.sub(r'[^\w\s]', '_', name)
        # 2. 替换空格和连续下划线
        cleaned = re.sub(r'\s+', '_', cleaned)
        cleaned = re.sub(r'_+', '_', cleaned)
        # 3. 移除开头和结尾的下划线
        cleaned = cleaned.strip('_')
        # 4. 转换为小写
        cleaned = cleaned.lower()
        # 5. 限制长度
        if len(cleaned) > 50:
            cleaned = cleaned[:50]
        
        # 确保不为空
        if not cleaned:
            cleaned = 'unknown_company'
            
        return cleaned
    
    def _extract_year(self, file_path: str) -> str:
        """从文件名中提取年份"""
        import re
        
        file_name = Path(file_path).stem
        
        # 查找4位数年份
        year_pattern = r'20\d{2}'
        matches = re.findall(year_pattern, file_name)
        
        if matches:
            return matches[0]
        
        # 查找2位数年份
        year_pattern_2 = r'_(\d{2})(?=\.|_|$)'
        matches = re.findall(year_pattern_2, file_name)
        
        if matches:
            year_2digit = int(matches[0])
            # 假设00-30为20xx年，31-99为19xx年
            if year_2digit <= 30:
                return f"20{year_2digit:02d}"
            else:
                return f"19{year_2digit:02d}"
                
        return 'Unknown Year'
    
    def _create_fallback_data(self, file_path: str) -> Dict[str, pd.DataFrame]:
        """创建回退数据（当解析失败时）"""
        # 创建一个包含文件信息的DataFrame
        file_info = {
            'file_name': [Path(file_path).name],
            'file_path': [file_path],
            'file_size': [os.path.getsize(file_path)],
            'company': [self._extract_company_name(file_path)],
            'year': [self._extract_year(file_path)],
            'status': ['Parse Failed - Manual Review Required'],
            'last_modified': [datetime.fromtimestamp(os.path.getmtime(file_path))]
        }
        
        df = pd.DataFrame(file_info)
        return {'ais_file_info': df}


class DatabaseFolderHandler:
    """数据库文件夹处理器（专门处理包含多个数据库的文件夹）"""
    
    def process(self, folder_path: str) -> Dict[str, pd.DataFrame]:
        """处理数据库文件夹"""
        logger.info(f"使用专门的数据库文件夹处理器: {folder_path}")
        
        # 这个处理器主要是为了标识，实际处理逻辑在DataIngestor中
        # 这里可以添加一些文件夹级别的特殊处理逻辑
        
        return {}


# 异常类定义
class UnsupportedFileType(Exception):
    """不支持的文件类型异常"""
    pass


# 测试函数
def test_data_ingestor():
    """测试数据接入模块"""
    ingestor = DataIngestor()
    
    # 测试文件类型检测
    print("文件类型检测测试:")
    test_files = [
        "test.xlsx", "test.csv", "test.bak", 
        "test.zip", "test.db", "河南泰田重工机械制造有限公司_2017.AIS"
    ]
    
    for file in test_files:
        file_type = ingestor.detect_file_type(file)
        print(f"{file} -> {file_type}")
    
    # 测试数据库文件夹检测
    print("\n数据库文件夹检测测试:")
    
    # 测试AIS文件处理
    print("\nAIS文件处理功能:")
    ais_handler = AISHandler()
    
    # 测试公司名称提取
    test_ais_files = [
        "河南泰田重工机械制造有限公司_2017.AIS",
        "taitain_heavy_industry_2020.ais",
        "泰田重工_财务数据_21.AIS",
        "unknown_company_data.ais"
    ]
    
    for file_name in test_ais_files:
        company = ais_handler._extract_company_name(file_name)
        year = ais_handler._extract_year(file_name)
        print(f"{file_name} -> 公司: {company}, 年份: {year}")


def test_database_folder_batch_import():
    """测试数据库文件夹批量导入功能"""
    print("\n=== 数据库文件夹批量导入测试 ===")
    
    ingestor = DataIngestor()
    
    # 创建测试文件夹结构
    test_folder = "test_db_folder"
    if not os.path.exists(test_folder):
        os.makedirs(test_folder)
    
    # 模拟数据库文件列表
    test_db_files = [
        "company_a.db",
        "company_b.sqlite", 
        "河南泰田重工机械制造有限公司_2017.AIS",
        "financial_data_2020.mdb",
        "backup_data.accdb"
    ]
    
    print(f"模拟数据库文件夹: {test_folder}")
    print(f"包含文件: {test_db_files}")
    
    # 检查是否为数据库文件夹
    print(f"批量导入配置: {ingestor.batch_import_config}")
    
    # 清理测试文件夹
    if os.path.exists(test_folder):
        try:
            os.rmdir(test_folder)
        except:
            pass


if __name__ == "__main__":
    test_data_ingestor()
    test_database_folder_batch_import()