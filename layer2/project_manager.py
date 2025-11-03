"""
DAP - 项目管理模块
提供完整的项目生命周期管理功能
"""

import sqlite3
import uuid
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime
import json

logger = logging.getLogger(__name__)

class ProjectManager:
    """项目管理器 - DAP核心项目管理模块"""
    
    def __init__(self, db_path: str = 'data/dap_data.db'):
        """初始化项目管理器
        
        Args:
            db_path: 数据库文件路径
        """
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        
        # 添加线程锁以确保线程安全
        import threading
        self._lock = threading.RLock()
        
        # 确保项目表存在
        self._ensure_project_tables()
        
        logger.info("项目管理器初始化完成")
    
    def _ensure_project_tables(self):
        """确保项目管理相关表存在"""
        try:
            cursor = self.conn.cursor()
            
            # 1. 项目主表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS dap_projects (
                    project_id TEXT PRIMARY KEY,
                    project_code TEXT UNIQUE NOT NULL,
                    project_name TEXT NOT NULL,
                    project_type TEXT DEFAULT 'general',
                    client_name TEXT,
                    client_code TEXT,
                    industry TEXT,
                    fiscal_year INTEGER,
                    fiscal_period INTEGER,
                    start_date TEXT,
                    end_date TEXT,
                    status TEXT DEFAULT 'active',
                    description TEXT,
                    tags TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    created_by TEXT,
                    updated_by TEXT,
                    metadata TEXT
                )
            """)
            
            # 检查并添加缺失的列（如果表已存在）
            existing_columns = [row[1] for row in cursor.execute("PRAGMA table_info(dap_projects)").fetchall()]
            
            columns_to_add = [
                ('project_type', 'TEXT DEFAULT \'general\''),
                ('client_name', 'TEXT'),
                ('client_code', 'TEXT'),
                ('industry', 'TEXT'),
                ('fiscal_year', 'INTEGER'),
                ('fiscal_period', 'INTEGER'),
                ('start_date', 'TEXT'),
                ('end_date', 'TEXT'),
                ('description', 'TEXT'),
                ('tags', 'TEXT'),
                ('created_by', 'TEXT'),
                ('updated_by', 'TEXT'),
                ('metadata', 'TEXT')
            ]
            
            for col_name, col_type in columns_to_add:
                if col_name not in existing_columns:
                    try:
                        cursor.execute(f"ALTER TABLE dap_projects ADD COLUMN {col_name} {col_type}")
                        logger.info(f"添加列: {col_name}")
                    except sqlite3.OperationalError as e:
                        logger.debug(f"添加列{col_name}失败: {e}")
            
            # 2. 项目成员表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS dap_project_members (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    project_id TEXT NOT NULL,
                    user_id TEXT NOT NULL,
                    user_name TEXT,
                    role TEXT DEFAULT 'member',
                    permissions TEXT,
                    joined_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (project_id) REFERENCES dap_projects(project_id) ON DELETE CASCADE,
                    UNIQUE(project_id, user_id)
                )
            """)
            
            # 3. 项目文件关联表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS dap_project_files (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    project_id TEXT NOT NULL,
                    file_name TEXT NOT NULL,
                    file_path TEXT NOT NULL,
                    file_type TEXT,
                    file_size INTEGER,
                    table_name TEXT,
                    uploaded_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    uploaded_by TEXT,
                    status TEXT DEFAULT 'active',
                    FOREIGN KEY (project_id) REFERENCES dap_projects(project_id) ON DELETE CASCADE
                )
            """)
            
            # 4. 项目活动日志表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS dap_project_activities (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    project_id TEXT NOT NULL,
                    activity_type TEXT NOT NULL,
                    activity_desc TEXT,
                    user_id TEXT,
                    user_name TEXT,
                    activity_data TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (project_id) REFERENCES dap_projects(project_id) ON DELETE CASCADE
                )
            """)
            
            # 5. 项目配置表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS dap_project_config (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    project_id TEXT NOT NULL,
                    config_key TEXT NOT NULL,
                    config_value TEXT,
                    config_type TEXT,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (project_id) REFERENCES dap_projects(project_id) ON DELETE CASCADE,
                    UNIQUE(project_id, config_key)
                )
            """)
            
            # 创建索引（使用IF NOT EXISTS，避免重复创建）
            try:
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_projects_code ON dap_projects(project_code)")
            except sqlite3.OperationalError:
                pass  # 索引可能已存在
            
            try:
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_projects_status ON dap_projects(status)")
            except sqlite3.OperationalError:
                pass
            
            try:
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_projects_client ON dap_projects(client_code)")
            except sqlite3.OperationalError:
                pass  # 如果client_code列不存在，跳过此索引
            
            try:
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_project_members_user ON dap_project_members(user_id)")
            except sqlite3.OperationalError:
                pass
            
            try:
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_project_files_project ON dap_project_files(project_id)")
            except sqlite3.OperationalError:
                pass
            
            try:
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_project_activities_project ON dap_project_activities(project_id)")
            except sqlite3.OperationalError:
                pass
            
            self.conn.commit()
            logger.info("项目管理表结构检查完成")
            
        except Exception as e:
            logger.error(f"创建项目管理表失败: {e}")
            raise
    
    def create_project(self, project_data: Dict[str, Any]) -> Dict[str, Any]:
        """创建新项目
        
        Args:
            project_data: 项目数据字典，必须包含project_name
            
        Returns:
            包含project_id和创建状态的字典
        """
        try:
            # 验证必填字段
            if not project_data.get("project_name"):
                return {
                    "success": False,
                    "error": "项目名称(project_name)是必填项"
                }
            
            # 生成项目ID和编码
            project_id = project_data.get("project_id") or f"PRJ_{uuid.uuid4().hex[:12].upper()}"
            project_code = project_data.get("project_code") or f"P{datetime.now().strftime('%Y%m%d%H%M%S')}"
            
            # 检查项目编码是否重复
            cursor = self.conn.cursor()
            existing = cursor.execute(
                "SELECT project_id FROM dap_projects WHERE project_code = ?",
                (project_code,)
            ).fetchone()
            
            if existing:
                return {
                    "success": False,
                    "error": f"项目编码 {project_code} 已存在"
                }
            
            # 准备插入数据
            now = datetime.now().isoformat()
            metadata = project_data.get("metadata", {})
            if isinstance(metadata, dict):
                metadata = json.dumps(metadata, ensure_ascii=False)
            
            tags = project_data.get("tags", [])
            if isinstance(tags, list):
                tags = json.dumps(tags, ensure_ascii=False)
            
            # 插入项目记录（使用线程锁保护）
            with self._lock:
                cursor.execute("""
                    INSERT INTO dap_projects (
                        project_id, project_code, project_name, project_type,
                        client_name, client_code, industry,
                        fiscal_year, fiscal_period,
                        start_date, end_date, status,
                        description, tags, metadata,
                        created_at, updated_at, created_by
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    project_id,
                    project_code,
                    project_data["project_name"],
                    project_data.get("project_type", "general"),
                    project_data.get("client_name"),
                    project_data.get("client_code"),
                    project_data.get("industry"),
                    project_data.get("fiscal_year"),
                    project_data.get("fiscal_period"),
                    project_data.get("start_date"),
                    project_data.get("end_date"),
                    project_data.get("status", "active"),
                    project_data.get("description"),
                    tags,
                    metadata,
                    now,
                    now,
                    project_data.get("created_by", "system")
                ))
                
                self.conn.commit()
            
            # 记录活动日志
            self._log_activity(
                project_id=project_id,
                activity_type="project_created",
                activity_desc=f"创建项目: {project_data['project_name']}",
                user_name=project_data.get("created_by", "system")
            )
            
            logger.info(f"项目创建成功: {project_id} - {project_data['project_name']}")
            
            return {
                "success": True,
                "project_id": project_id,
                "project_code": project_code,
                "message": f"项目 '{project_data['project_name']}' 创建成功"
            }
            
        except sqlite3.IntegrityError as e:
            logger.error(f"项目创建失败(完整性约束): {e}")
            with self._lock:
                self.conn.rollback()
            return {
                "success": False,
                "error": f"项目创建失败: 数据冲突 - {str(e)}"
            }
        except Exception as e:
            logger.error(f"项目创建失败: {e}")
            with self._lock:
                self.conn.rollback()
            return {
                "success": False,
                "error": f"项目创建失败: {str(e)}"
            }
    
    def get_project(self, project_id: Optional[str] = None, 
                   project_code: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """获取项目详情
        
        Args:
            project_id: 项目ID
            project_code: 项目编码
            
        Returns:
            项目详情字典，未找到返回None
        """
        try:
            cursor = self.conn.cursor()
            
            if project_id:
                row = cursor.execute(
                    "SELECT * FROM dap_projects WHERE project_id = ?",
                    (project_id,)
                ).fetchone()
            elif project_code:
                row = cursor.execute(
                    "SELECT * FROM dap_projects WHERE project_code = ?",
                    (project_code,)
                ).fetchone()
            else:
                return None
            
            if not row:
                return None
            
            # 转换为字典
            project = dict(row)
            
            # 解析JSON字段
            if project.get("metadata"):
                try:
                    project["metadata"] = json.loads(project["metadata"])
                except:
                    pass
            
            if project.get("tags"):
                try:
                    project["tags"] = json.loads(project["tags"])
                except:
                    pass
            
            return project
            
        except Exception as e:
            logger.error(f"获取项目失败: {e}")
            return None
    
    def list_projects(self, filters: Optional[Dict[str, Any]] = None,
                     limit: int = 100, offset: int = 0) -> Dict[str, Any]:
        """列出项目
        
        Args:
            filters: 过滤条件 (status, client_code, project_type等)
            limit: 返回数量限制
            offset: 偏移量
            
        Returns:
            包含projects列表和总数的字典
        """
        try:
            cursor = self.conn.cursor()
            
            # 构建查询
            where_clauses = []
            params = []
            
            if filters:
                if filters.get("status"):
                    where_clauses.append("status = ?")
                    params.append(filters["status"])
                
                if filters.get("client_code"):
                    where_clauses.append("client_code = ?")
                    params.append(filters["client_code"])
                
                if filters.get("project_type"):
                    where_clauses.append("project_type = ?")
                    params.append(filters["project_type"])
                
                if filters.get("fiscal_year"):
                    where_clauses.append("fiscal_year = ?")
                    params.append(filters["fiscal_year"])
            
            where_sql = " AND ".join(where_clauses) if where_clauses else "1=1"
            
            # 获取总数
            count_sql = f"SELECT COUNT(*) FROM dap_projects WHERE {where_sql}"
            total = cursor.execute(count_sql, params).fetchone()[0]
            
            # 获取项目列表
            list_sql = f"""
                SELECT * FROM dap_projects 
                WHERE {where_sql}
                ORDER BY created_at DESC
                LIMIT ? OFFSET ?
            """
            params.extend([limit, offset])
            
            rows = cursor.execute(list_sql, params).fetchall()
            
            projects = []
            for row in rows:
                project = dict(row)
                # 解析JSON字段
                if project.get("metadata"):
                    try:
                        project["metadata"] = json.loads(project["metadata"])
                    except:
                        pass
                if project.get("tags"):
                    try:
                        project["tags"] = json.loads(project["tags"])
                    except:
                        pass
                projects.append(project)
            
            return {
                "success": True,
                "projects": projects,
                "total": total,
                "limit": limit,
                "offset": offset
            }
            
        except Exception as e:
            logger.error(f"列出项目失败: {e}")
            return {
                "success": False,
                "error": str(e),
                "projects": [],
                "total": 0
            }
    
    def update_project(self, project_id: str, updates: Dict[str, Any]) -> Dict[str, Any]:
        """更新项目信息
        
        Args:
            project_id: 项目ID
            updates: 要更新的字段字典
            
        Returns:
            更新结果字典
        """
        try:
            # 检查项目是否存在
            existing = self.get_project(project_id=project_id)
            if not existing:
                return {
                    "success": False,
                    "error": f"项目 {project_id} 不存在"
                }
            
            # 过滤允许更新的字段
            allowed_fields = [
                "project_name", "project_type", "client_name", "client_code",
                "industry", "fiscal_year", "fiscal_period", "start_date", "end_date",
                "status", "description", "tags", "metadata", "updated_by"
            ]
            
            update_fields = []
            params = []
            
            for field in allowed_fields:
                if field in updates:
                    value = updates[field]
                    # 处理JSON字段
                    if field in ["metadata", "tags"] and isinstance(value, (dict, list)):
                        value = json.dumps(value, ensure_ascii=False)
                    update_fields.append(f"{field} = ?")
                    params.append(value)
            
            if not update_fields:
                return {
                    "success": False,
                    "error": "没有可更新的字段"
                }
            
            # 添加更新时间
            update_fields.append("updated_at = ?")
            params.append(datetime.now().isoformat())
            
            # 添加项目ID
            params.append(project_id)
            
            # 执行更新（使用线程锁和事务保护）
            cursor = self.conn.cursor()
            update_sql = f"""
                UPDATE dap_projects 
                SET {', '.join(update_fields)}
                WHERE project_id = ?
            """
            with self._lock:
                cursor.execute(update_sql, params)
                self.conn.commit()
            
            # 记录活动日志
            self._log_activity(
                project_id=project_id,
                activity_type="project_updated",
                activity_desc=f"更新项目信息: {', '.join(update_fields)}",
                user_name=updates.get("updated_by", "system")
            )
            
            logger.info(f"项目更新成功: {project_id}")
            
            return {
                "success": True,
                "message": "项目更新成功",
                "updated_fields": len(update_fields)
            }
            
        except Exception as e:
            logger.error(f"项目更新失败: {e}")
            with self._lock:
                self.conn.rollback()
            return {
                "success": False,
                "error": str(e)
            }
    
    def delete_project(self, project_id: str, soft_delete: bool = True) -> Dict[str, Any]:
        """删除项目
        
        Args:
            project_id: 项目ID
            soft_delete: 是否软删除(仅标记状态为deleted)
            
        Returns:
            删除结果字典
        """
        try:
            # 检查项目是否存在
            existing = self.get_project(project_id=project_id)
            if not existing:
                return {
                    "success": False,
                    "error": f"项目 {project_id} 不存在"
                }
            
            cursor = self.conn.cursor()
            
            with self._lock:
                if soft_delete:
                    # 软删除：标记状态
                    cursor.execute("""
                        UPDATE dap_projects 
                        SET status = 'deleted', updated_at = ?
                        WHERE project_id = ?
                    """, (datetime.now().isoformat(), project_id))
                    
                    message = f"项目 '{existing['project_name']}' 已标记为删除"
                    
                else:
                    # 硬删除：实际删除记录（会级联删除关联数据）
                    cursor.execute("DELETE FROM dap_projects WHERE project_id = ?", (project_id,))
                    message = f"项目 '{existing['project_name']}' 已永久删除"
                
                self.conn.commit()
            
            # 记录活动日志
            self._log_activity(
                project_id=project_id,
                activity_type="project_deleted",
                activity_desc=message,
                user_name="system"
            )
            
            logger.info(message)
            
            return {
                "success": True,
                "message": message
            }
            
        except Exception as e:
            logger.error(f"项目删除失败: {e}")
            with self._lock:
                self.conn.rollback()
            return {
                "success": False,
                "error": str(e)
            }
    
    def add_project_member(self, project_id: str, user_id: str, 
                          user_name: Optional[str] = None,
                          role: str = "member") -> Dict[str, Any]:
        """添加项目成员
        
        Args:
            project_id: 项目ID
            user_id: 用户ID
            user_name: 用户名称
            role: 角色 (owner/admin/member/viewer)
            
        Returns:
            操作结果字典
        """
        try:
            cursor = self.conn.cursor()
            with self._lock:
                cursor.execute("""
                    INSERT OR REPLACE INTO dap_project_members
                    (project_id, user_id, user_name, role)
                    VALUES (?, ?, ?, ?)
                """, (project_id, user_id, user_name, role))
                
                self.conn.commit()
            
            self._log_activity(
                project_id=project_id,
                activity_type="member_added",
                activity_desc=f"添加成员: {user_name or user_id} ({role})",
                user_name="system"
            )
            
            return {
                "success": True,
                "message": "成员添加成功"
            }
            
        except Exception as e:
            logger.error(f"添加项目成员失败: {e}")
            with self._lock:
                self.conn.rollback()
            return {
                "success": False,
                "error": str(e)
            }
    
    def _log_activity(self, project_id: str, activity_type: str,
                     activity_desc: str, user_name: str = "system",
                     activity_data: Optional[Dict] = None):
        """记录项目活动日志"""
        try:
            cursor = self.conn.cursor()
            
            data_json = None
            if activity_data:
                data_json = json.dumps(activity_data, ensure_ascii=False)
            
            with self._lock:
                cursor.execute("""
                    INSERT INTO dap_project_activities
                    (project_id, activity_type, activity_desc, user_name, activity_data)
                    VALUES (?, ?, ?, ?, ?)
                """, (project_id, activity_type, activity_desc, user_name, data_json))
                
                self.conn.commit()
            
        except Exception as e:
            logger.warning(f"记录活动日志失败: {e}")
    
    def get_project_activities(self, project_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        """获取项目活动日志
        
        Args:
            project_id: 项目ID
            limit: 返回数量限制
            
        Returns:
            活动日志列表
        """
        try:
            cursor = self.conn.cursor()
            rows = cursor.execute("""
                SELECT * FROM dap_project_activities
                WHERE project_id = ?
                ORDER BY created_at DESC
                LIMIT ?
            """, (project_id, limit)).fetchall()
            
            activities = []
            for row in rows:
                activity = dict(row)
                if activity.get("activity_data"):
                    try:
                        activity["activity_data"] = json.loads(activity["activity_data"])
                    except:
                        pass
                activities.append(activity)
            
            return activities
            
        except Exception as e:
            logger.error(f"获取项目活动日志失败: {e}")
            return []
    
    def get_project_statistics(self, project_id: str) -> Dict[str, Any]:
        """获取项目统计信息
        
        Args:
            project_id: 项目ID
            
        Returns:
            统计信息字典
        """
        try:
            cursor = self.conn.cursor()
            
            stats = {
                "project_id": project_id,
                "member_count": 0,
                "file_count": 0,
                "activity_count": 0
            }
            
            # 成员数量
            result = cursor.execute(
                "SELECT COUNT(*) FROM dap_project_members WHERE project_id = ?",
                (project_id,)
            ).fetchone()
            stats["member_count"] = result[0] if result else 0
            
            # 文件数量
            result = cursor.execute(
                "SELECT COUNT(*) FROM dap_project_files WHERE project_id = ? AND status = 'active'",
                (project_id,)
            ).fetchone()
            stats["file_count"] = result[0] if result else 0
            
            # 活动数量
            result = cursor.execute(
                "SELECT COUNT(*) FROM dap_project_activities WHERE project_id = ?",
                (project_id,)
            ).fetchone()
            stats["activity_count"] = result[0] if result else 0
            
            return stats
            
        except Exception as e:
            logger.error(f"获取项目统计失败: {e}")
            return {}
    
    def close(self):
        """关闭数据库连接"""
        if self.conn:
            self.conn.close()


# 测试代码
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    # 创建项目管理器
    pm = ProjectManager()
    
    # 测试创建项目
    result = pm.create_project({
        "project_name": "测试项目2024",
        "client_name": "示例客户有限公司",
        "client_code": "CLIENT001",
        "industry": "制造业",
        "fiscal_year": 2024,
        "description": "这是一个测试项目"
    })
    
    print("创建项目结果:", json.dumps(result, ensure_ascii=False, indent=2))
    
    if result["success"]:
        project_id = result["project_id"]
        
        # 测试获取项目
        project = pm.get_project(project_id=project_id)
        print("\n项目详情:", json.dumps(project, ensure_ascii=False, indent=2))
        
        # 测试列出项目
        projects = pm.list_projects()
        print(f"\n项目列表 (共{projects['total']}个):")
        for p in projects["projects"]:
            print(f"  - {p['project_code']}: {p['project_name']}")
    
    pm.close()
