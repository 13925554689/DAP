"""GUI Consolidation Tabs - 合并报表相关界面模块

This module provides GUI components for:
1. Enhanced project management with entity hierarchy
2. Consolidation report generation
3. Natural language query interface
"""

import tkinter as tk
from tkinter import ttk, messagebox, simpledialog, filedialog
from typing import Any, Dict, List, Optional
import logging
import pandas as pd
from datetime import datetime

from layer2.group_hierarchy_manager import GroupHierarchyManager
from layer2.consolidation_engine import ConsolidationEngine
from layer4.nl_query_engine import NLQueryEngine

logger = logging.getLogger(__name__)


class EnhancedProjectManagementTab:
    """Enhanced project management tab with entity hierarchy support."""

    def __init__(self, parent, dap_engine):
        """Initialize enhanced project management tab.

        Args:
            parent: Parent notebook widget
            dap_engine: DAP engine instance
        """
        self.dap_engine = dap_engine
        self.hierarchy_manager: Optional[GroupHierarchyManager] = None

        # Create main frame
        self.frame = ttk.Frame(parent, padding="10")
        parent.add(self.frame, text="📊 项目与实体管理")

        # Initialize hierarchy manager
        self._init_hierarchy_manager()

        # Build widgets
        self._build_widgets()

    def _init_hierarchy_manager(self):
        """Initialize hierarchy manager."""
        try:
            db_path = self.dap_engine.storage_manager.db_path
            self.hierarchy_manager = GroupHierarchyManager(db_path)
            logger.info("Hierarchy manager initialized")
        except Exception as e:
            logger.error(f"Failed to initialize hierarchy manager: {e}")
            self.hierarchy_manager = None

    def _build_widgets(self):
        """Build tab widgets."""
        # Configure grid
        self.frame.columnconfigure(0, weight=1)
        self.frame.columnconfigure(1, weight=2)
        self.frame.rowconfigure(1, weight=1)

        # Title
        title_label = ttk.Label(
            self.frame,
            text="项目与公司实体管理",
            font=("Arial", 14, "bold")
        )
        title_label.grid(row=0, column=0, columnspan=2, pady=(0, 10), sticky=tk.W)

        # Left panel - Project list
        self._create_project_panel()

        # Right panel - Entity hierarchy
        self._create_entity_panel()

        # Bottom panel - Actions
        self._create_action_panel()

    def _create_project_panel(self):
        """Create project list panel."""
        # Project list frame
        project_frame = ttk.LabelFrame(self.frame, text="项目列表", padding="10")
        project_frame.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), padx=(0, 5))

        # Project listbox with scrollbar
        list_frame = ttk.Frame(project_frame)
        list_frame.pack(fill=tk.BOTH, expand=True)

        scrollbar = ttk.Scrollbar(list_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.project_listbox = tk.Listbox(
            list_frame,
            yscrollcommand=scrollbar.set,
            font=("Arial", 10)
        )
        self.project_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.config(command=self.project_listbox.yview)

        # Project buttons
        btn_frame = ttk.Frame(project_frame)
        btn_frame.pack(fill=tk.X, pady=(10, 0))

        ttk.Button(
            btn_frame,
            text="➕ 新建项目",
            command=self._create_project
        ).pack(side=tk.LEFT, padx=2)

        ttk.Button(
            btn_frame,
            text="📝 编辑",
            command=self._edit_project
        ).pack(side=tk.LEFT, padx=2)

        ttk.Button(
            btn_frame,
            text="🗑️ 删除",
            command=self._delete_project
        ).pack(side=tk.LEFT, padx=2)

        # Bind selection event
        self.project_listbox.bind('<<ListboxSelect>>', self._on_project_selected)

        # Load projects
        self._refresh_project_list()

    def _create_entity_panel(self):
        """Create entity hierarchy panel."""
        # Entity hierarchy frame
        entity_frame = ttk.LabelFrame(self.frame, text="公司实体层级", padding="10")
        entity_frame.grid(row=1, column=1, sticky=(tk.W, tk.E, tk.N, tk.S), padx=(5, 0))

        # Entity tree with scrollbar
        tree_frame = ttk.Frame(entity_frame)
        tree_frame.pack(fill=tk.BOTH, expand=True)

        # Scrollbars
        y_scrollbar = ttk.Scrollbar(tree_frame)
        y_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        x_scrollbar = ttk.Scrollbar(tree_frame, orient=tk.HORIZONTAL)
        x_scrollbar.pack(side=tk.BOTTOM, fill=tk.X)

        # Tree widget
        self.entity_tree = ttk.Treeview(
            tree_frame,
            columns=("编码", "类型", "持股比例", "层级"),
            show="tree headings",
            yscrollcommand=y_scrollbar.set,
            xscrollcommand=x_scrollbar.set
        )

        # Configure columns
        self.entity_tree.heading("#0", text="公司名称")
        self.entity_tree.heading("编码", text="编码")
        self.entity_tree.heading("类型", text="类型")
        self.entity_tree.heading("持股比例", text="持股比例")
        self.entity_tree.heading("层级", text="层级")

        self.entity_tree.column("#0", width=200)
        self.entity_tree.column("编码", width=100)
        self.entity_tree.column("类型", width=80)
        self.entity_tree.column("持股比例", width=80)
        self.entity_tree.column("层级", width=60)

        self.entity_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        y_scrollbar.config(command=self.entity_tree.yview)
        x_scrollbar.config(command=self.entity_tree.xview)

        # Entity buttons
        btn_frame = ttk.Frame(entity_frame)
        btn_frame.pack(fill=tk.X, pady=(10, 0))

        ttk.Button(
            btn_frame,
            text="➕ 添加公司",
            command=self._add_entity
        ).pack(side=tk.LEFT, padx=2)

        ttk.Button(
            btn_frame,
            text="➕ 添加子公司",
            command=self._add_subsidiary
        ).pack(side=tk.LEFT, padx=2)

        ttk.Button(
            btn_frame,
            text="📝 编辑",
            command=self._edit_entity
        ).pack(side=tk.LEFT, padx=2)

        ttk.Button(
            btn_frame,
            text="🗑️ 删除",
            command=self._delete_entity
        ).pack(side=tk.LEFT, padx=2)

        ttk.Button(
            btn_frame,
            text="🔄 刷新",
            command=self._refresh_entity_tree
        ).pack(side=tk.LEFT, padx=2)

    def _create_action_panel(self):
        """Create action buttons panel."""
        action_frame = ttk.Frame(self.frame)
        action_frame.grid(row=2, column=0, columnspan=2, pady=(10, 0), sticky=tk.W)

        ttk.Label(action_frame, text="快捷操作:").pack(side=tk.LEFT, padx=5)

        ttk.Button(
            action_frame,
            text="📊 查看层级统计",
            command=self._show_statistics
        ).pack(side=tk.LEFT, padx=2)

        ttk.Button(
            action_frame,
            text="📁 导出实体列表",
            command=self._export_entities
        ).pack(side=tk.LEFT, padx=2)

    def _refresh_project_list(self):
        """Refresh project list."""
        try:
            self.project_listbox.delete(0, tk.END)
            projects = self.dap_engine.storage_manager.list_projects()

            for project in projects:
                display_text = f"{project.get('project_name', 'Unknown')} ({project.get('project_code', 'N/A')})"
                self.project_listbox.insert(tk.END, display_text)

        except Exception as e:
            logger.error(f"Failed to refresh project list: {e}")
            messagebox.showerror("错误", f"刷新项目列表失败: {e}")

    def _on_project_selected(self, event):
        """Handle project selection."""
        selection = self.project_listbox.curselection()
        if not selection:
            return

        # Clear and refresh entity tree
        self._refresh_entity_tree()

    def _refresh_entity_tree(self):
        """Refresh entity hierarchy tree."""
        # Clear tree
        for item in self.entity_tree.get_children():
            self.entity_tree.delete(item)

        if not self.hierarchy_manager:
            return

        try:
            # Get current project
            selection = self.project_listbox.curselection()
            if not selection:
                return

            projects = self.dap_engine.storage_manager.list_projects()
            project = projects[selection[0]]
            project_id = project["project_id"]

            # Get all entities for this project
            self.hierarchy_manager.connect()
            entities = self.hierarchy_manager.list_entities(project_id)
            self.hierarchy_manager.disconnect()

            # Build tree hierarchy
            entity_map = {e["entity_id"]: e for e in entities}
            roots = [e for e in entities if e["parent_entity_id"] is None]

            for root in roots:
                self._insert_entity_node("", root, entity_map)

        except Exception as e:
            logger.error(f"Failed to refresh entity tree: {e}")

    def _insert_entity_node(self, parent, entity, entity_map):
        """Insert entity node and its children recursively."""
        node_id = self.entity_tree.insert(
            parent,
            "end",
            text=entity["entity_name"],
            values=(
                entity["entity_code"],
                entity["entity_type"],
                f"{entity['ownership_percentage']:.1f}%",
                entity["level"]
            )
        )

        # Insert children
        children = [e for e in entity_map.values()
                   if e["parent_entity_id"] == entity["entity_id"]]
        for child in children:
            self._insert_entity_node(node_id, child, entity_map)

    def _create_project(self):
        """Create new project."""
        # Simple dialog for project creation
        dialog = tk.Toplevel(self.frame)
        dialog.title("创建新项目")
        dialog.geometry("400x300")
        dialog.transient(self.frame)
        dialog.grab_set()

        # Project name
        ttk.Label(dialog, text="项目名称:").grid(row=0, column=0, padx=10, pady=10, sticky=tk.W)
        name_entry = ttk.Entry(dialog, width=30)
        name_entry.grid(row=0, column=1, padx=10, pady=10)

        # Project code
        ttk.Label(dialog, text="项目编码:").grid(row=1, column=0, padx=10, pady=10, sticky=tk.W)
        code_entry = ttk.Entry(dialog, width=30)
        code_entry.grid(row=1, column=1, padx=10, pady=10)

        # Client name
        ttk.Label(dialog, text="客户名称:").grid(row=2, column=0, padx=10, pady=10, sticky=tk.W)
        client_entry = ttk.Entry(dialog, width=30)
        client_entry.grid(row=2, column=1, padx=10, pady=10)

        # Fiscal year
        ttk.Label(dialog, text="会计年度:").grid(row=3, column=0, padx=10, pady=10, sticky=tk.W)
        year_entry = ttk.Entry(dialog, width=30)
        year_entry.insert(0, datetime.now().strftime("%Y"))
        year_entry.grid(row=3, column=1, padx=10, pady=10)

        def save_project():
            name = name_entry.get().strip()
            if not name:
                messagebox.showerror("错误", "请输入项目名称")
                return

            try:
                project_id = self.dap_engine.storage_manager.create_project(
                    project_name=name,
                    project_code=code_entry.get().strip() or None,
                    client_name=client_entry.get().strip() or None,
                    fiscal_year=year_entry.get().strip() or None
                )
                messagebox.showinfo("成功", f"项目创建成功! ID: {project_id}")
                self._refresh_project_list()
                dialog.destroy()
            except Exception as e:
                messagebox.showerror("错误", f"创建项目失败: {e}")

        # Buttons
        btn_frame = ttk.Frame(dialog)
        btn_frame.grid(row=4, column=0, columnspan=2, pady=20)

        ttk.Button(btn_frame, text="保存", command=save_project).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="取消", command=dialog.destroy).pack(side=tk.LEFT, padx=5)

    def _edit_project(self):
        """Edit selected project."""
        messagebox.showinfo("提示", "项目编辑功能开发中...")

    def _delete_project(self):
        """Delete selected project."""
        messagebox.showinfo("提示", "项目删除功能开发中...")

    def _add_entity(self):
        """Add new entity (root level company)."""
        if not self.hierarchy_manager:
            messagebox.showerror("错误", "层级管理器未初始化")
            return

        # Get current project
        selection = self.project_listbox.curselection()
        if not selection:
            messagebox.showwarning("提示", "请先选择一个项目")
            return

        projects = self.dap_engine.storage_manager.list_projects()
        project = projects[selection[0]]

        # Create entity dialog (simplified)
        dialog = tk.Toplevel(self.frame)
        dialog.title("添加公司实体")
        dialog.geometry("400x400")
        dialog.transient(self.frame)
        dialog.grab_set()

        fields = {}

        # Entity code
        ttk.Label(dialog, text="公司编码*:").grid(row=0, column=0, padx=10, pady=5, sticky=tk.W)
        fields["code"] = ttk.Entry(dialog, width=30)
        fields["code"].grid(row=0, column=1, padx=10, pady=5)

        # Entity name
        ttk.Label(dialog, text="公司名称*:").grid(row=1, column=0, padx=10, pady=5, sticky=tk.W)
        fields["name"] = ttk.Entry(dialog, width=30)
        fields["name"].grid(row=1, column=1, padx=10, pady=5)

        # Entity type
        ttk.Label(dialog, text="实体类型*:").grid(row=2, column=0, padx=10, pady=5, sticky=tk.W)
        fields["type"] = ttk.Combobox(
            dialog,
            values=["母公司", "子公司", "孙公司", "联营公司", "合营公司"],
            width=28,
            state="readonly"
        )
        fields["type"].set("母公司")
        fields["type"].grid(row=2, column=1, padx=10, pady=5)

        def save_entity():
            code = fields["code"].get().strip()
            name = fields["name"].get().strip()

            if not code or not name:
                messagebox.showerror("错误", "请填写必填字段")
                return

            try:
                self.hierarchy_manager.connect()
                entity_id = self.hierarchy_manager.create_entity(
                    project_id=project["project_id"],
                    entity_code=code,
                    entity_name=name,
                    entity_type=fields["type"].get()
                )
                self.hierarchy_manager.disconnect()

                messagebox.showinfo("成功", f"公司实体创建成功! ID: {entity_id}")
                self._refresh_entity_tree()
                dialog.destroy()
            except Exception as e:
                messagebox.showerror("错误", f"创建实体失败: {e}")

        # Buttons
        btn_frame = ttk.Frame(dialog)
        btn_frame.grid(row=10, column=0, columnspan=2, pady=20)

        ttk.Button(btn_frame, text="保存", command=save_entity).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="取消", command=dialog.destroy).pack(side=tk.LEFT, padx=5)

    def _add_subsidiary(self):
        """Add subsidiary to selected entity."""
        messagebox.showinfo("提示", "添加子公司功能开发中...")

    def _edit_entity(self):
        """Edit selected entity."""
        messagebox.showinfo("提示", "编辑实体功能开发中...")

    def _delete_entity(self):
        """Delete selected entity."""
        messagebox.showinfo("提示", "删除实体功能开发中...")

    def _show_statistics(self):
        """Show hierarchy statistics."""
        if not self.hierarchy_manager:
            return

        selection = self.project_listbox.curselection()
        if not selection:
            messagebox.showwarning("提示", "请先选择一个项目")
            return

        projects = self.dap_engine.storage_manager.list_projects()
        project = projects[selection[0]]

        try:
            self.hierarchy_manager.connect()
            stats = self.hierarchy_manager.get_statistics(project["project_id"])
            self.hierarchy_manager.disconnect()

            message = f"""层级统计信息:

总实体数: {stats.get('total_entities', 0)}
最大层级深度: {stats.get('max_depth', 0)}

按层级分布:
"""
            for level, count in stats.get('by_level', {}).items():
                message += f"  第{level}层: {count}个\n"

            message += "\n按类型分布:\n"
            for entity_type, count in stats.get('by_type', {}).items():
                message += f"  {entity_type}: {count}个\n"

            messagebox.showinfo("层级统计", message)
        except Exception as e:
            messagebox.showerror("错误", f"获取统计信息失败: {e}")

    def _export_entities(self):
        """Export entity list to Excel."""
        messagebox.showinfo("提示", "导出实体列表功能开发中...")


class ConsolidationReportTab:
    """Consolidation report generation tab."""

    def __init__(self, parent, dap_engine):
        """Initialize consolidation report tab.

        Args:
            parent: Parent notebook widget
            dap_engine: DAP engine instance
        """
        self.dap_engine = dap_engine
        self.consolidation_engine: Optional[ConsolidationEngine] = None
        self.hierarchy_manager: Optional[GroupHierarchyManager] = None

        # Create main frame
        self.frame = ttk.Frame(parent, padding="10")
        parent.add(self.frame, text="📊 合并报表")

        # Initialize engines
        self._init_engines()

        # Build widgets
        self._build_widgets()

    def _init_engines(self):
        """Initialize consolidation engines."""
        try:
            db_path = self.dap_engine.storage_manager.db_path
            self.consolidation_engine = ConsolidationEngine(db_path)
            self.hierarchy_manager = GroupHierarchyManager(db_path)
            logger.info("Consolidation engines initialized")
        except Exception as e:
            logger.error(f"Failed to initialize engines: {e}")

    def _build_widgets(self):
        """Build tab widgets."""
        # Configure grid
        self.frame.columnconfigure(0, weight=1)
        self.frame.rowconfigure(3, weight=1)

        # Title
        title_label = ttk.Label(
            self.frame,
            text="集团合并报表生成",
            font=("Arial", 14, "bold")
        )
        title_label.grid(row=0, column=0, pady=(0, 10), sticky=tk.W)

        # Parameters frame
        self._create_parameters_panel()

        # Actions frame
        self._create_actions_panel()

        # Progress frame
        self._create_progress_panel()

        # Results frame
        self._create_results_panel()

    def _create_parameters_panel(self):
        """Create consolidation parameters panel."""
        param_frame = ttk.LabelFrame(self.frame, text="合并参数设置", padding="10")
        param_frame.grid(row=1, column=0, sticky=(tk.W, tk.E), pady=(0, 10))

        # Parent entity selection
        ttk.Label(param_frame, text="母公司实体:").grid(row=0, column=0, padx=5, pady=5, sticky=tk.W)
        self.parent_entity_combo = ttk.Combobox(param_frame, width=40, state="readonly")
        self.parent_entity_combo.grid(row=0, column=1, padx=5, pady=5, sticky=tk.W)
        ttk.Button(param_frame, text="🔄 刷新", command=self._refresh_entities).grid(row=0, column=2, padx=5, pady=5)

        # Period selection
        ttk.Label(param_frame, text="合并期间:").grid(row=1, column=0, padx=5, pady=5, sticky=tk.W)
        self.period_entry = ttk.Entry(param_frame, width=20)
        self.period_entry.insert(0, datetime.now().strftime("%Y-%m"))
        self.period_entry.grid(row=1, column=1, padx=5, pady=5, sticky=tk.W)
        ttk.Label(param_frame, text="(格式: YYYY-MM)").grid(row=1, column=2, padx=5, pady=5, sticky=tk.W)

        # Report type selection
        ttk.Label(param_frame, text="报表类型:").grid(row=2, column=0, padx=5, pady=5, sticky=tk.W)
        self.report_type_combo = ttk.Combobox(
            param_frame,
            values=["资产负债表", "利润表", "现金流量表"],
            width=20,
            state="readonly"
        )
        self.report_type_combo.set("资产负债表")
        self.report_type_combo.grid(row=2, column=1, padx=5, pady=5, sticky=tk.W)

        # Min ownership percentage
        ttk.Label(param_frame, text="最低持股比例:").grid(row=3, column=0, padx=5, pady=5, sticky=tk.W)
        self.min_ownership_spin = ttk.Spinbox(param_frame, from_=0, to=100, width=18)
        self.min_ownership_spin.set(20)
        self.min_ownership_spin.grid(row=3, column=1, padx=5, pady=5, sticky=tk.W)
        ttk.Label(param_frame, text="%").grid(row=3, column=2, padx=5, pady=5, sticky=tk.W)

        # Consolidation method
        ttk.Label(param_frame, text="合并方法:").grid(row=4, column=0, padx=5, pady=5, sticky=tk.W)
        method_frame = ttk.Frame(param_frame)
        method_frame.grid(row=4, column=1, padx=5, pady=5, sticky=tk.W)

        self.method_vars = {}
        for method in ["全额合并", "比例合并", "权益法"]:
            var = tk.BooleanVar(value=(method == "全额合并"))
            self.method_vars[method] = var
            ttk.Checkbutton(method_frame, text=method, variable=var).pack(side=tk.LEFT, padx=5)

        # Refresh entities
        self._refresh_entities()

    def _create_actions_panel(self):
        """Create action buttons panel."""
        action_frame = ttk.Frame(self.frame)
        action_frame.grid(row=2, column=0, pady=(0, 10), sticky=tk.W)

        ttk.Button(
            action_frame,
            text="🚀 生成合并报表",
            command=self._generate_consolidation,
            style="Accent.TButton"
        ).pack(side=tk.LEFT, padx=5)

        ttk.Button(
            action_frame,
            text="📋 查看抵销分录",
            command=self._view_eliminations
        ).pack(side=tk.LEFT, padx=5)

        ttk.Button(
            action_frame,
            text="💾 导出报表",
            command=self._export_report
        ).pack(side=tk.LEFT, padx=5)

        ttk.Button(
            action_frame,
            text="📊 查看少数股东权益",
            command=self._view_minority_interest
        ).pack(side=tk.LEFT, padx=5)

    def _create_progress_panel(self):
        """Create progress display panel."""
        progress_frame = ttk.LabelFrame(self.frame, text="处理进度", padding="10")
        progress_frame.grid(row=3, column=0, sticky=(tk.W, tk.E), pady=(0, 10))

        self.progress_text = tk.Text(progress_frame, height=6, width=80, state='disabled')
        self.progress_text.pack(fill=tk.BOTH, expand=True)

    def _create_results_panel(self):
        """Create results display panel."""
        results_frame = ttk.LabelFrame(self.frame, text="合并结果", padding="10")
        results_frame.grid(row=4, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(0, 10))

        # Results tree with scrollbar
        tree_frame = ttk.Frame(results_frame)
        tree_frame.pack(fill=tk.BOTH, expand=True)

        y_scrollbar = ttk.Scrollbar(tree_frame)
        y_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        x_scrollbar = ttk.Scrollbar(tree_frame, orient=tk.HORIZONTAL)
        x_scrollbar.pack(side=tk.BOTTOM, fill=tk.X)

        self.results_tree = ttk.Treeview(
            tree_frame,
            columns=("科目编码", "科目名称", "借方金额", "贷方金额", "余额"),
            show="headings",
            yscrollcommand=y_scrollbar.set,
            xscrollcommand=x_scrollbar.set
        )

        self.results_tree.heading("科目编码", text="科目编码")
        self.results_tree.heading("科目名称", text="科目名称")
        self.results_tree.heading("借方金额", text="借方金额")
        self.results_tree.heading("贷方金额", text="贷方金额")
        self.results_tree.heading("余额", text="余额")

        self.results_tree.column("科目编码", width=100)
        self.results_tree.column("科目名称", width=200)
        self.results_tree.column("借方金额", width=120)
        self.results_tree.column("贷方金额", width=120)
        self.results_tree.column("余额", width=120)

        self.results_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        y_scrollbar.config(command=self.results_tree.yview)
        x_scrollbar.config(command=self.results_tree.xview)

    def _refresh_entities(self):
        """Refresh parent entity list."""
        if not self.hierarchy_manager:
            return

        try:
            # Get current project
            projects = self.dap_engine.storage_manager.list_projects()
            if not projects:
                return

            # Use first project for now
            project = projects[0]

            self.hierarchy_manager.connect()
            entities = self.hierarchy_manager.list_entities(project["project_id"])
            self.hierarchy_manager.disconnect()

            # Populate combobox
            entity_list = [f"{e['entity_name']} ({e['entity_code']})" for e in entities]
            self.parent_entity_combo['values'] = entity_list

            if entity_list:
                self.parent_entity_combo.current(0)

            # Store entity mapping
            self.entity_map = {f"{e['entity_name']} ({e['entity_code']})": e for e in entities}

        except Exception as e:
            logger.error(f"Failed to refresh entities: {e}")

    def _generate_consolidation(self):
        """Generate consolidated report."""
        if not self.consolidation_engine:
            messagebox.showerror("错误", "合并引擎未初始化")
            return

        # Get parameters
        selected = self.parent_entity_combo.get()
        if not selected:
            messagebox.showwarning("提示", "请选择母公司实体")
            return

        entity = self.entity_map.get(selected)
        if not entity:
            messagebox.showerror("错误", "无法找到选中的实体")
            return

        period = self.period_entry.get().strip()
        if not period:
            messagebox.showwarning("提示", "请输入合并期间")
            return

        # Build include criteria
        methods = [k for k, v in self.method_vars.items() if v.get()]
        criteria = {
            "min_ownership": float(self.min_ownership_spin.get()),
            "consolidation_methods": methods
        }

        # Map report type
        report_type_map = {
            "资产负债表": "balance_sheet",
            "利润表": "income_statement",
            "现金流量表": "cash_flow"
        }
        report_type = report_type_map[self.report_type_combo.get()]

        # Log progress
        self._log_progress("开始生成合并报表...")
        self._log_progress(f"母公司: {entity['entity_name']}")
        self._log_progress(f"期间: {period}")
        self._log_progress(f"报表类型: {self.report_type_combo.get()}")

        # Generate in thread
        def generate():
            try:
                result = self.consolidation_engine.generate_consolidated_report(
                    parent_entity_id=entity["entity_id"],
                    period=period,
                    report_type=report_type,
                    include_criteria=criteria
                )

                if result.get("success"):
                    self._log_progress(f"✅ 合并完成!")
                    self._log_progress(f"合并范围: {result['scope_entity_count']}个实体")
                    self._log_progress(f"内部交易: {result['interco_transaction_count']}笔")
                    self._log_progress(f"抵销分录: {result['elimination_count']}条")

                    # Display results
                    self._display_results(result['consolidated_data'])
                else:
                    self._log_progress(f"❌ 合并失败: {result.get('error', 'Unknown error')}")
                    messagebox.showerror("错误", f"合并失败: {result.get('error')}")

            except Exception as e:
                self._log_progress(f"❌ 异常: {str(e)}")
                messagebox.showerror("错误", f"生成合并报表时出错: {e}")

        threading.Thread(target=generate, daemon=True).start()

    def _display_results(self, data: pd.DataFrame):
        """Display consolidation results in tree."""
        # Clear existing
        for item in self.results_tree.get_children():
            self.results_tree.delete(item)

        if data.empty:
            return

        # Insert rows
        for _, row in data.iterrows():
            self.results_tree.insert(
                "",
                "end",
                values=(
                    row.get("account_code", ""),
                    row.get("account_name", ""),
                    f"{row.get('debit', 0):,.2f}",
                    f"{row.get('credit', 0):,.2f}",
                    f"{row.get('balance', 0):,.2f}"
                )
            )

    def _log_progress(self, message: str):
        """Log progress message."""
        self.progress_text.config(state='normal')
        self.progress_text.insert(tk.END, f"{message}\n")
        self.progress_text.see(tk.END)
        self.progress_text.config(state='disabled')

    def _view_eliminations(self):
        """View elimination entries."""
        messagebox.showinfo("提示", "查看抵销分录功能开发中...")

    def _view_minority_interest(self):
        """View minority interest details."""
        messagebox.showinfo("提示", "查看少数股东权益功能开发中...")

    def _export_report(self):
        """Export consolidated report to Excel."""
        # Get data from tree
        data = []
        for item in self.results_tree.get_children():
            values = self.results_tree.item(item)['values']
            data.append(values)

        if not data:
            messagebox.showwarning("提示", "没有数据可导出")
            return

        # Ask for save location
        filename = filedialog.asksaveasfilename(
            defaultextension=".xlsx",
            filetypes=[("Excel files", "*.xlsx"), ("All files", "*.*")],
            initialfile=f"合并报表_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        )

        if not filename:
            return

        try:
            df = pd.DataFrame(data, columns=["科目编码", "科目名称", "借方金额", "贷方金额", "余额"])
            df.to_excel(filename, index=False)
            messagebox.showinfo("成功", f"报表已导出到: {filename}")
        except Exception as e:
            messagebox.showerror("错误", f"导出失败: {e}")


class NLQueryTab:
    """Natural language query interface tab."""

    def __init__(self, parent, dap_engine):
        """Initialize NL query tab.

        Args:
            parent: Parent notebook widget
            dap_engine: DAP engine instance
        """
        self.dap_engine = dap_engine
        self.nl_engine: Optional[NLQueryEngine] = None

        # Create main frame
        self.frame = ttk.Frame(parent, padding="10")
        parent.add(self.frame, text="💬 自然语言查询")

        # Initialize NL engine
        self._init_nl_engine()

        # Build widgets
        self._build_widgets()

    def _init_nl_engine(self):
        """Initialize NL query engine."""
        try:
            db_path = self.dap_engine.storage_manager.db_path
            self.nl_engine = NLQueryEngine(db_path)
            logger.info("NL query engine initialized")
        except Exception as e:
            logger.error(f"Failed to initialize NL engine: {e}")

    def _build_widgets(self):
        """Build tab widgets."""
        # Configure grid
        self.frame.columnconfigure(0, weight=1)
        self.frame.rowconfigure(3, weight=1)

        # Title
        title_label = ttk.Label(
            self.frame,
            text="自然语言查询 - 用自然语言提问财务数据",
            font=("Arial", 14, "bold")
        )
        title_label.grid(row=0, column=0, pady=(0, 10), sticky=tk.W)

        # Query input panel
        self._create_query_panel()

        # Quick queries panel
        self._create_quick_queries_panel()

        # Results panel
        self._create_results_panel()

        # History panel
        self._create_history_panel()

    def _create_query_panel(self):
        """Create query input panel."""
        query_frame = ttk.LabelFrame(self.frame, text="查询输入", padding="10")
        query_frame.grid(row=1, column=0, sticky=(tk.W, tk.E), pady=(0, 10))

        # Query text input
        input_frame = ttk.Frame(query_frame)
        input_frame.pack(fill=tk.X)

        ttk.Label(input_frame, text="请输入您的查询:").pack(side=tk.LEFT, padx=(0, 10))

        self.query_entry = ttk.Entry(input_frame, width=60, font=("Arial", 11))
        self.query_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 10))
        self.query_entry.bind("<Return>", lambda e: self._execute_query())

        ttk.Button(
            input_frame,
            text="🔍 查询",
            command=self._execute_query
        ).pack(side=tk.LEFT)

        # Example
        ttk.Label(
            query_frame,
            text="示例: \"查询2024年12月的全部凭证\" 或 \"查询主营业务收入科目余额\" 或 \"查询超过10万元的凭证\"",
            font=("Arial", 9),
            foreground="gray"
        ).pack(pady=(5, 0))

    def _create_quick_queries_panel(self):
        """Create quick query buttons panel."""
        quick_frame = ttk.LabelFrame(self.frame, text="快捷查询", padding="10")
        quick_frame.grid(row=2, column=0, sticky=(tk.W, tk.E), pady=(0, 10))

        queries = [
            "查询本月全部凭证",
            "查询主营业务收入余额",
            "查询管理费用明细",
            "查询应收账款汇总",
            "查询现金和银行存款",
            "查询固定资产明细"
        ]

        for i, query in enumerate(queries):
            btn = ttk.Button(
                quick_frame,
                text=query,
                command=lambda q=query: self._quick_query(q)
            )
            btn.grid(row=i // 3, column=i % 3, padx=5, pady=5, sticky=(tk.W, tk.E))

    def _create_results_panel(self):
        """Create results display panel."""
        results_frame = ttk.LabelFrame(self.frame, text="查询结果", padding="10")
        results_frame.grid(row=3, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(0, 10))

        # Results info
        self.results_info_label = ttk.Label(results_frame, text="", font=("Arial", 10))
        self.results_info_label.pack(anchor=tk.W, pady=(0, 5))

        # Results tree with scrollbar
        tree_frame = ttk.Frame(results_frame)
        tree_frame.pack(fill=tk.BOTH, expand=True)

        y_scrollbar = ttk.Scrollbar(tree_frame)
        y_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        x_scrollbar = ttk.Scrollbar(tree_frame, orient=tk.HORIZONTAL)
        x_scrollbar.pack(side=tk.BOTTOM, fill=tk.X)

        self.results_tree = ttk.Treeview(
            tree_frame,
            yscrollcommand=y_scrollbar.set,
            xscrollcommand=x_scrollbar.set
        )
        self.results_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        y_scrollbar.config(command=self.results_tree.yview)
        x_scrollbar.config(command=self.results_tree.xview)

        # Export button
        ttk.Button(
            results_frame,
            text="💾 导出结果",
            command=self._export_results
        ).pack(pady=(5, 0))

    def _create_history_panel(self):
        """Create query history panel."""
        history_frame = ttk.LabelFrame(self.frame, text="查询历史", padding="10")
        history_frame.grid(row=4, column=0, sticky=(tk.W, tk.E), pady=(0, 10))

        # History listbox with scrollbar
        list_frame = ttk.Frame(history_frame)
        list_frame.pack(fill=tk.BOTH, expand=True)

        scrollbar = ttk.Scrollbar(list_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.history_listbox = tk.Listbox(
            list_frame,
            height=4,
            yscrollcommand=scrollbar.set,
            font=("Arial", 9)
        )
        self.history_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.config(command=self.history_listbox.yview)

        # Bind double-click to re-execute
        self.history_listbox.bind("<Double-Button-1>", self._reexecute_from_history)

    def _execute_query(self):
        """Execute natural language query."""
        if not self.nl_engine:
            messagebox.showerror("错误", "查询引擎未初始化")
            return

        query_text = self.query_entry.get().strip()
        if not query_text:
            messagebox.showwarning("提示", "请输入查询内容")
            return

        # Get context
        projects = self.dap_engine.storage_manager.list_projects()
        context = {
            "current_project": projects[0]["project_id"] if projects else None,
            "current_period": datetime.now().strftime("%Y-%m")
        }

        # Execute query
        try:
            result = self.nl_engine.process_query(query_text, context)

            if result.get("success"):
                # Update info label
                intent = result.get("intent", "未知")
                row_count = result.get("row_count", 0)
                self.results_info_label.config(
                    text=f"查询意图: {intent} | 结果数量: {row_count} 条"
                )

                # Display results
                self._display_nl_results(result["results"])

                # Add to history
                self.history_listbox.insert(0, f"{query_text} ({row_count}条)")

            else:
                messagebox.showerror("查询失败", f"错误: {result.get('error', 'Unknown error')}")

        except Exception as e:
            messagebox.showerror("错误", f"查询执行失败: {e}")

    def _quick_query(self, query: str):
        """Execute quick query."""
        self.query_entry.delete(0, tk.END)
        self.query_entry.insert(0, query)
        self._execute_query()

    def _display_nl_results(self, results: List[Dict[str, Any]]):
        """Display NL query results."""
        # Clear existing tree
        self.results_tree.delete(*self.results_tree.get_children())

        if not results:
            return

        # Get columns from first result
        columns = list(results[0].keys())

        # Configure tree columns
        self.results_tree["columns"] = columns
        self.results_tree["show"] = "headings"

        for col in columns:
            self.results_tree.heading(col, text=col)
            self.results_tree.column(col, width=120)

        # Insert data
        for row in results:
            values = [row.get(col, "") for col in columns]
            self.results_tree.insert("", "end", values=values)

    def _reexecute_from_history(self, event):
        """Re-execute query from history."""
        selection = self.history_listbox.curselection()
        if not selection:
            return

        history_text = self.history_listbox.get(selection[0])
        # Extract query (before the count)
        query = history_text.split(" (")[0]

        self.query_entry.delete(0, tk.END)
        self.query_entry.insert(0, query)
        self._execute_query()

    def _export_results(self):
        """Export query results to Excel."""
        # Get data from tree
        if not self.results_tree.get_children():
            messagebox.showwarning("提示", "没有数据可导出")
            return

        columns = self.results_tree["columns"]
        data = []

        for item in self.results_tree.get_children():
            values = self.results_tree.item(item)['values']
            data.append(values)

        # Ask for save location
        filename = filedialog.asksaveasfilename(
            defaultextension=".xlsx",
            filetypes=[("Excel files", "*.xlsx"), ("All files", "*.*")],
            initialfile=f"查询结果_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        )

        if not filename:
            return

        try:
            df = pd.DataFrame(data, columns=columns)
            df.to_excel(filename, index=False)
            messagebox.showinfo("成功", f"结果已导出到: {filename}")
        except Exception as e:
            messagebox.showerror("错误", f"导出失败: {e}")
