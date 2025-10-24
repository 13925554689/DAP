"""GUI Project Management Tab - 项目与实体层级管理界面

This module provides enhanced project-entity relationship management with:
1. Tree view hierarchy (Project -> Entities)
2. Relationship visualization
3. Quick filtering and search
4. Entity management operations
"""

import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
from typing import Any, Dict, List, Optional
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


class ProjectManagementTab:
    """增强版项目-实体管理Tab"""

    def __init__(self, parent, dap_engine):
        """Initialize project management tab.

        Args:
            parent: Parent notebook widget
            dap_engine: DAP engine instance
        """
        self.dap_engine = dap_engine
        self.storage_manager = getattr(dap_engine, 'storage_manager', None)

        # Create main frame
        self.frame = ttk.Frame(parent, padding="10")
        parent.add(self.frame, text="📁 项目管理")

        # Current selections
        self.selected_project_id = None
        self.selected_entity_id = None

        # Build widgets
        self._build_widgets()

        # Load initial data
        self._refresh_project_tree()

    def _build_widgets(self):
        """Build tab widgets."""
        # Configure grid
        self.frame.columnconfigure(0, weight=1)
        self.frame.columnconfigure(1, weight=2)
        self.frame.rowconfigure(1, weight=1)

        # Title
        title_label = ttk.Label(
            self.frame,
            text="项目与实体层级管理",
            font=("Arial", 14, "bold")
        )
        title_label.grid(row=0, column=0, columnspan=2, pady=(0, 10), sticky=tk.W)

        # Left panel - Tree view
        self._create_tree_panel()

        # Right panel - Details and operations
        self._create_details_panel()

        # Bottom panel - Actions
        self._create_actions_panel()

    def _create_tree_panel(self):
        """Create project-entity tree view panel."""
        tree_frame = ttk.LabelFrame(self.frame, text="项目-实体层级结构", padding="10")
        tree_frame.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), padx=(0, 5))
        tree_frame.columnconfigure(0, weight=1)
        tree_frame.rowconfigure(1, weight=1)

        # Search/Filter bar
        filter_frame = ttk.Frame(tree_frame)
        filter_frame.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=(0, 5))

        ttk.Label(filter_frame, text="搜索:").pack(side=tk.LEFT, padx=(0, 5))
        self.search_var = tk.StringVar()
        self.search_var.trace('w', lambda *args: self._filter_tree())
        search_entry = ttk.Entry(filter_frame, textvariable=self.search_var, width=20)
        search_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)

        ttk.Button(
            filter_frame,
            text="🔄",
            width=3,
            command=self._refresh_project_tree
        ).pack(side=tk.LEFT, padx=(5, 0))

        # Tree view with scrollbar
        tree_container = ttk.Frame(tree_frame)
        tree_container.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        tree_container.columnconfigure(0, weight=1)
        tree_container.rowconfigure(0, weight=1)

        # Scrollbars
        y_scrollbar = ttk.Scrollbar(tree_container)
        y_scrollbar.grid(row=0, column=1, sticky=(tk.N, tk.S))

        x_scrollbar = ttk.Scrollbar(tree_container, orient=tk.HORIZONTAL)
        x_scrollbar.grid(row=1, column=0, sticky=(tk.W, tk.E))

        # Tree widget
        self.project_tree = ttk.Treeview(
            tree_container,
            columns=("type", "code", "info"),
            yscrollcommand=y_scrollbar.set,
            xscrollcommand=x_scrollbar.set,
            selectmode='browse'
        )

        # Configure columns
        self.project_tree.heading("#0", text="名称")
        self.project_tree.heading("type", text="类型")
        self.project_tree.heading("code", text="代码")
        self.project_tree.heading("info", text="信息")

        self.project_tree.column("#0", width=200, minwidth=150)
        self.project_tree.column("type", width=80, minwidth=60)
        self.project_tree.column("code", width=100, minwidth=80)
        self.project_tree.column("info", width=150, minwidth=100)

        self.project_tree.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        y_scrollbar.config(command=self.project_tree.yview)
        x_scrollbar.config(command=self.project_tree.xview)

        # Bind selection event
        self.project_tree.bind("<<TreeviewSelect>>", self._on_tree_select)

        # Context menu
        self.project_tree.bind("<Button-3>", self._show_tree_context_menu)

    def _create_details_panel(self):
        """Create details and operations panel."""
        details_frame = ttk.LabelFrame(self.frame, text="详细信息", padding="10")
        details_frame.grid(row=1, column=1, sticky=(tk.W, tk.E, tk.N, tk.S), padx=(5, 0))
        details_frame.columnconfigure(0, weight=1)
        details_frame.rowconfigure(1, weight=1)

        # Info display area
        info_text_frame = ttk.Frame(details_frame)
        info_text_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(0, 10))
        info_text_frame.columnconfigure(0, weight=1)
        info_text_frame.rowconfigure(0, weight=1)

        info_scrollbar = ttk.Scrollbar(info_text_frame)
        info_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.info_text = tk.Text(
            info_text_frame,
            height=10,
            wrap=tk.WORD,
            state='disabled',
            yscrollcommand=info_scrollbar.set
        )
        self.info_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        info_scrollbar.config(command=self.info_text.yview)

        # Relationship visualization (if entity selected)
        self.relationship_frame = ttk.LabelFrame(details_frame, text="实体关系", padding="10")
        self.relationship_frame.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        self.relationship_frame.columnconfigure(0, weight=1)
        self.relationship_frame.rowconfigure(0, weight=1)

        # Relationship tree
        rel_scrollbar = ttk.Scrollbar(self.relationship_frame)
        rel_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.relationship_tree = ttk.Treeview(
            self.relationship_frame,
            columns=("relation", "percentage"),
            show="tree headings",
            yscrollcommand=rel_scrollbar.set,
            height=8
        )
        self.relationship_tree.heading("relation", text="关系")
        self.relationship_tree.heading("percentage", text="持股比例")
        self.relationship_tree.column("relation", width=120)
        self.relationship_tree.column("percentage", width=100)

        self.relationship_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        rel_scrollbar.config(command=self.relationship_tree.yview)

    def _create_actions_panel(self):
        """Create action buttons panel."""
        action_frame = ttk.Frame(self.frame)
        action_frame.grid(row=2, column=0, columnspan=2, pady=(10, 0), sticky=tk.W)

        # Project operations
        project_btn_frame = ttk.LabelFrame(action_frame, text="项目操作", padding="5")
        project_btn_frame.pack(side=tk.LEFT, padx=(0, 10))

        ttk.Button(
            project_btn_frame,
            text="➕ 新建项目",
            command=self._create_project
        ).pack(side=tk.LEFT, padx=2)

        ttk.Button(
            project_btn_frame,
            text="✏️ 编辑项目",
            command=self._edit_project
        ).pack(side=tk.LEFT, padx=2)

        ttk.Button(
            project_btn_frame,
            text="🗑️ 删除项目",
            command=self._delete_project
        ).pack(side=tk.LEFT, padx=2)

        # Entity operations
        entity_btn_frame = ttk.LabelFrame(action_frame, text="实体操作", padding="5")
        entity_btn_frame.pack(side=tk.LEFT, padx=(0, 10))

        ttk.Button(
            entity_btn_frame,
            text="➕ 添加实体",
            command=self._add_entity
        ).pack(side=tk.LEFT, padx=2)

        ttk.Button(
            entity_btn_frame,
            text="✏️ 编辑实体",
            command=self._edit_entity
        ).pack(side=tk.LEFT, padx=2)

        ttk.Button(
            entity_btn_frame,
            text="🔗 设置关系",
            command=self._set_entity_relationship
        ).pack(side=tk.LEFT, padx=2)

        ttk.Button(
            entity_btn_frame,
            text="🗑️ 删除实体",
            command=self._delete_entity
        ).pack(side=tk.LEFT, padx=2)

        # Utility operations
        util_btn_frame = ttk.LabelFrame(action_frame, text="工具", padding="5")
        util_btn_frame.pack(side=tk.LEFT)

        ttk.Button(
            util_btn_frame,
            text="📊 统计报告",
            command=self._generate_statistics_report
        ).pack(side=tk.LEFT, padx=2)

        ttk.Button(
            util_btn_frame,
            text="💾 导出结构",
            command=self._export_structure
        ).pack(side=tk.LEFT, padx=2)

    def _refresh_project_tree(self):
        """Refresh the project-entity tree view."""
        try:
            # Clear existing items
            for item in self.project_tree.get_children():
                self.project_tree.delete(item)

            if not self.storage_manager:
                self.project_tree.insert("", "end", text="⚠️ 存储管理器未初始化", values=("", "", ""))
                return

            # Get all projects
            projects = self.storage_manager.list_projects()

            for project in projects:
                project_id = project.get('project_id')
                project_name = project.get('project_name', '未命名项目')
                project_code = project.get('project_code', '-')
                client_name = project.get('client_name', '-')

                # Insert project node
                project_node = self.project_tree.insert(
                    "",
                    "end",
                    text=f"📁 {project_name}",
                    values=("项目", project_code, f"客户: {client_name}"),
                    tags=('project',)
                )

                # Store project_id in item for later retrieval
                self.project_tree.set(project_node, "#0", f"📁 {project_name}")

                # Get entities for this project
                entities = self.storage_manager.list_entities(project_id)

                for entity in entities:
                    entity_name = entity.get('entity_name', '未命名实体')
                    entity_code = entity.get('entity_code', '-')
                    entity_type = entity.get('entity_type', '子公司')
                    ownership = entity.get('ownership_percentage', 100.0)

                    # Insert entity node
                    self.project_tree.insert(
                        project_node,
                        "end",
                        text=f"🏢 {entity_name}",
                        values=(entity_type, entity_code, f"持股: {ownership}%"),
                        tags=('entity',)
                    )

            logger.info(f"项目树刷新完成: {len(projects)} 个项目")

        except Exception as e:
            logger.error(f"刷新项目树失败: {e}", exc_info=True)
            messagebox.showerror("错误", f"刷新失败: {e}")

    def _filter_tree(self):
        """Filter tree based on search text."""
        search_text = self.search_var.get().lower()

        if not search_text:
            # Show all items
            for item in self.project_tree.get_children():
                self._show_tree_item(item)
            return

        # Hide items that don't match
        for item in self.project_tree.get_children():
            self._filter_tree_item(item, search_text)

    def _filter_tree_item(self, item, search_text):
        """Recursively filter tree items."""
        item_text = self.project_tree.item(item, 'text').lower()
        item_values = ' '.join(str(v).lower() for v in self.project_tree.item(item, 'values'))

        matches = search_text in item_text or search_text in item_values

        # Check children
        children = self.project_tree.get_children(item)
        child_matches = False
        for child in children:
            if self._filter_tree_item(child, search_text):
                child_matches = True

        if matches or child_matches:
            self._show_tree_item(item)
            return True
        else:
            self.project_tree.detach(item)
            return False

    def _show_tree_item(self, item):
        """Show a tree item."""
        parent = self.project_tree.parent(item)
        if parent:
            self.project_tree.move(item, parent, 'end')
        else:
            self.project_tree.move(item, '', 'end')

        # Recursively show children
        for child in self.project_tree.get_children(item):
            self._show_tree_item(child)

    def _on_tree_select(self, event):
        """Handle tree selection event."""
        selection = self.project_tree.selection()
        if not selection:
            return

        item = selection[0]
        tags = self.project_tree.item(item, 'tags')

        if 'project' in tags:
            self._display_project_details(item)
        elif 'entity' in tags:
            self._display_entity_details(item)

    def _display_project_details(self, item):
        """Display project details."""
        try:
            project_text = self.project_tree.item(item, 'text')
            project_name = project_text.replace('📁 ', '')
            values = self.project_tree.item(item, 'values')

            # Get project from storage
            if self.storage_manager:
                project = self.storage_manager.get_project(project_name)
                if project:
                    self.selected_project_id = project.get('project_id')
                    self.selected_entity_id = None

                    # Display info
                    self.info_text.config(state='normal')
                    self.info_text.delete('1.0', tk.END)

                    self.info_text.insert(tk.END, "【项目信息】\n\n", 'title')
                    self.info_text.insert(tk.END, f"项目ID: {project.get('project_id')}\n")
                    self.info_text.insert(tk.END, f"项目名称: {project.get('project_name')}\n")
                    self.info_text.insert(tk.END, f"项目代码: {project.get('project_code', '-')}\n")
                    self.info_text.insert(tk.END, f"客户名称: {project.get('client_name', '-')}\n")
                    self.info_text.insert(tk.END, f"会计年度: {project.get('fiscal_year', '-')}\n")
                    self.info_text.insert(tk.END, f"会计期间: {project.get('fiscal_period', '-')}\n")

                    # Count entities
                    entities = self.storage_manager.list_entities(self.selected_project_id)
                    self.info_text.insert(tk.END, f"\n实体数量: {len(entities)} 个\n")

                    self.info_text.config(state='disabled')

                    # Clear relationship view
                    for rel_item in self.relationship_tree.get_children():
                        self.relationship_tree.delete(rel_item)

        except Exception as e:
            logger.error(f"显示项目详情失败: {e}", exc_info=True)

    def _display_entity_details(self, item):
        """Display entity details and relationships."""
        try:
            entity_text = self.project_tree.item(item, 'text')
            entity_name = entity_text.replace('🏢 ', '')

            # Get parent project
            parent_item = self.project_tree.parent(item)
            if not parent_item:
                return

            project_text = self.project_tree.item(parent_item, 'text')
            project_name = project_text.replace('📁 ', '')

            if self.storage_manager:
                project = self.storage_manager.get_project(project_name)
                if not project:
                    return

                self.selected_project_id = project.get('project_id')

                # Find entity
                entities = self.storage_manager.list_entities(self.selected_project_id)
                entity = next((e for e in entities if e.get('entity_name') == entity_name), None)

                if entity:
                    self.selected_entity_id = entity.get('entity_id')

                    # Display entity info
                    self.info_text.config(state='normal')
                    self.info_text.delete('1.0', tk.END)

                    self.info_text.insert(tk.END, "【实体信息】\n\n", 'title')
                    self.info_text.insert(tk.END, f"实体ID: {entity.get('entity_id')}\n")
                    self.info_text.insert(tk.END, f"实体名称: {entity.get('entity_name')}\n")
                    self.info_text.insert(tk.END, f"实体代码: {entity.get('entity_code', '-')}\n")
                    self.info_text.insert(tk.END, f"实体类型: {entity.get('entity_type', '子公司')}\n")
                    self.info_text.insert(tk.END, f"持股比例: {entity.get('ownership_percentage', 100.0)}%\n")

                    parent_id = entity.get('parent_entity_id')
                    if parent_id:
                        parent_entity = self.storage_manager.get_entity(parent_id)
                        if parent_entity:
                            self.info_text.insert(tk.END, f"母公司: {parent_entity.get('entity_name')}\n")

                    self.info_text.config(state='disabled')

                    # Display relationship hierarchy
                    self._display_entity_relationships(entity)

        except Exception as e:
            logger.error(f"显示实体详情失败: {e}", exc_info=True)

    def _display_entity_relationships(self, entity):
        """Display entity relationship hierarchy."""
        try:
            # Clear existing
            for item in self.relationship_tree.get_children():
                self.relationship_tree.delete(item)

            entity_id = entity.get('entity_id')

            if not self.storage_manager:
                return

            # Get hierarchy
            hierarchy = self.storage_manager.get_entity_hierarchy(entity_id)

            # Display as tree
            if hierarchy:
                self._add_relationship_node("", entity, hierarchy)
            else:
                self.relationship_tree.insert(
                    "",
                    "end",
                    text="当前实体",
                    values=("独立实体", "-")
                )

        except Exception as e:
            logger.error(f"显示实体关系失败: {e}", exc_info=True)

    def _add_relationship_node(self, parent, entity, hierarchy):
        """Recursively add relationship nodes."""
        entity_name = entity.get('entity_name', '未知')
        ownership = entity.get('ownership_percentage', 100.0)

        node = self.relationship_tree.insert(
            parent,
            "end",
            text=entity_name,
            values=("子公司" if parent else "母公司", f"{ownership}%")
        )

        # Add children
        for child in hierarchy:
            self._add_relationship_node(node, child, child.get('children', []))

    def _show_tree_context_menu(self, event):
        """Show context menu for tree items."""
        item = self.project_tree.identify_row(event.y)
        if not item:
            return

        self.project_tree.selection_set(item)
        tags = self.project_tree.item(item, 'tags')

        menu = tk.Menu(self.frame, tearoff=0)

        if 'project' in tags:
            menu.add_command(label="查看详情", command=lambda: self._display_project_details(item))
            menu.add_command(label="编辑项目", command=self._edit_project)
            menu.add_separator()
            menu.add_command(label="添加实体", command=self._add_entity)
            menu.add_separator()
            menu.add_command(label="删除项目", command=self._delete_project)
        elif 'entity' in tags:
            menu.add_command(label="查看详情", command=lambda: self._display_entity_details(item))
            menu.add_command(label="编辑实体", command=self._edit_entity)
            menu.add_command(label="设置关系", command=self._set_entity_relationship)
            menu.add_separator()
            menu.add_command(label="删除实体", command=self._delete_entity)

        menu.post(event.x_root, event.y_root)

    def _create_project(self):
        """Create new project."""
        dialog = ProjectDialog(self.frame, self.storage_manager)
        if dialog.result:
            self._refresh_project_tree()
            messagebox.showinfo("成功", "项目创建成功!")

    def _edit_project(self):
        """Edit selected project."""
        if not self.selected_project_id:
            messagebox.showwarning("提示", "请先选择一个项目")
            return

        messagebox.showinfo("提示", "项目编辑功能开发中...")

    def _delete_project(self):
        """Delete selected project."""
        if not self.selected_project_id:
            messagebox.showwarning("提示", "请先选择一个项目")
            return

        if not messagebox.askyesno("确认", "确定要删除此项目及其所有实体吗?"):
            return

        messagebox.showinfo("提示", "项目删除功能开发中...")

    def _add_entity(self):
        """Add entity to selected project."""
        if not self.selected_project_id:
            messagebox.showwarning("提示", "请先选择一个项目")
            return

        dialog = EntityDialog(self.frame, self.storage_manager, self.selected_project_id)
        if dialog.result:
            self._refresh_project_tree()
            messagebox.showinfo("成功", "实体添加成功!")

    def _edit_entity(self):
        """Edit selected entity."""
        if not self.selected_entity_id:
            messagebox.showwarning("提示", "请先选择一个实体")
            return

        messagebox.showinfo("提示", "实体编辑功能开发中...")

    def _set_entity_relationship(self):
        """Set entity relationship."""
        if not self.selected_entity_id:
            messagebox.showwarning("提示", "请先选择一个实体")
            return

        messagebox.showinfo("提示", "设置实体关系功能开发中...")

    def _delete_entity(self):
        """Delete selected entity."""
        if not self.selected_entity_id:
            messagebox.showwarning("提示", "请先选择一个实体")
            return

        if not messagebox.askyesno("确认", "确定要删除此实体吗?"):
            return

        try:
            if self.storage_manager:
                success = self.storage_manager.delete_entity(self.selected_entity_id)
                if success:
                    self._refresh_project_tree()
                    messagebox.showinfo("成功", "实体删除成功!")
                else:
                    messagebox.showerror("错误", "删除实体失败")
        except Exception as e:
            messagebox.showerror("错误", f"删除失败: {e}")

    def _generate_statistics_report(self):
        """Generate statistics report."""
        messagebox.showinfo("提示", "统计报告功能开发中...")

    def _export_structure(self):
        """Export project structure."""
        messagebox.showinfo("提示", "导出结构功能开发中...")


class ProjectDialog:
    """Project creation/edit dialog."""

    def __init__(self, parent, storage_manager, project=None):
        self.storage_manager = storage_manager
        self.result = None

        self.dialog = tk.Toplevel(parent)
        self.dialog.title("新建项目" if not project else "编辑项目")
        self.dialog.geometry("500x400")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self._build_form(project)

        # Center dialog
        self.dialog.update_idletasks()
        x = (self.dialog.winfo_screenwidth() // 2) - (self.dialog.winfo_width() // 2)
        y = (self.dialog.winfo_screenheight() // 2) - (self.dialog.winfo_height() // 2)
        self.dialog.geometry(f"+{x}+{y}")

        self.dialog.wait_window()

    def _build_form(self, project):
        """Build project form."""
        main_frame = ttk.Frame(self.dialog, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Form fields
        fields = [
            ("项目名称*:", "project_name"),
            ("项目代码:", "project_code"),
            ("客户名称:", "client_name"),
            ("会计年度:", "fiscal_year"),
            ("会计期间:", "fiscal_period"),
        ]

        self.entries = {}

        for idx, (label, key) in enumerate(fields):
            ttk.Label(main_frame, text=label).grid(row=idx, column=0, sticky=tk.W, pady=5)
            entry = ttk.Entry(main_frame, width=40)
            entry.grid(row=idx, column=1, sticky=(tk.W, tk.E), pady=5, padx=(10, 0))
            self.entries[key] = entry

            if project and key in project:
                entry.insert(0, project[key])

        main_frame.columnconfigure(1, weight=1)

        # Buttons
        btn_frame = ttk.Frame(main_frame)
        btn_frame.grid(row=len(fields), column=0, columnspan=2, pady=20)

        ttk.Button(btn_frame, text="保存", command=self._save).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="取消", command=self.dialog.destroy).pack(side=tk.LEFT, padx=5)

    def _save(self):
        """Save project."""
        try:
            project_name = self.entries["project_name"].get().strip()
            if not project_name:
                messagebox.showerror("错误", "请输入项目名称")
                return

            if self.storage_manager:
                project_id = self.storage_manager.create_project(
                    project_name=project_name,
                    project_code=self.entries["project_code"].get().strip() or None,
                    client_name=self.entries["client_name"].get().strip() or None,
                    fiscal_year=self.entries["fiscal_year"].get().strip() or None,
                    fiscal_period=self.entries["fiscal_period"].get().strip() or None,
                )
                self.result = project_id
                self.dialog.destroy()
            else:
                messagebox.showerror("错误", "存储管理器未初始化")
        except Exception as e:
            messagebox.showerror("错误", f"保存失败: {e}")


class EntityDialog:
    """Entity creation/edit dialog."""

    def __init__(self, parent, storage_manager, project_id, entity=None):
        self.storage_manager = storage_manager
        self.project_id = project_id
        self.result = None

        self.dialog = tk.Toplevel(parent)
        self.dialog.title("添加实体" if not entity else "编辑实体")
        self.dialog.geometry("500x450")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self._build_form(entity)

        # Center dialog
        self.dialog.update_idletasks()
        x = (self.dialog.winfo_screenwidth() // 2) - (self.dialog.winfo_width() // 2)
        y = (self.dialog.winfo_screenheight() // 2) - (self.dialog.winfo_height() // 2)
        self.dialog.geometry(f"+{x}+{y}")

        self.dialog.wait_window()

    def _build_form(self, entity):
        """Build entity form."""
        main_frame = ttk.Frame(self.dialog, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Form fields
        row = 0

        # Entity name
        ttk.Label(main_frame, text="实体名称*:").grid(row=row, column=0, sticky=tk.W, pady=5)
        self.name_entry = ttk.Entry(main_frame, width=40)
        self.name_entry.grid(row=row, column=1, sticky=(tk.W, tk.E), pady=5, padx=(10, 0))
        row += 1

        # Entity code
        ttk.Label(main_frame, text="实体代码*:").grid(row=row, column=0, sticky=tk.W, pady=5)
        self.code_entry = ttk.Entry(main_frame, width=40)
        self.code_entry.grid(row=row, column=1, sticky=(tk.W, tk.E), pady=5, padx=(10, 0))
        row += 1

        # Entity type
        ttk.Label(main_frame, text="实体类型:").grid(row=row, column=0, sticky=tk.W, pady=5)
        self.type_combo = ttk.Combobox(
            main_frame,
            values=["子公司", "母公司", "分公司", "合营企业", "联营企业"],
            state="readonly",
            width=37
        )
        self.type_combo.set("子公司")
        self.type_combo.grid(row=row, column=1, sticky=(tk.W, tk.E), pady=5, padx=(10, 0))
        row += 1

        # Ownership percentage
        ttk.Label(main_frame, text="持股比例(%):").grid(row=row, column=0, sticky=tk.W, pady=5)
        self.ownership_entry = ttk.Entry(main_frame, width=40)
        self.ownership_entry.insert(0, "100.0")
        self.ownership_entry.grid(row=row, column=1, sticky=(tk.W, tk.E), pady=5, padx=(10, 0))
        row += 1

        # Parent entity (optional)
        ttk.Label(main_frame, text="母公司:").grid(row=row, column=0, sticky=tk.W, pady=5)

        # Get existing entities
        parent_options = ["无"]
        if self.storage_manager:
            entities = self.storage_manager.list_entities(self.project_id)
            parent_options.extend([e.get('entity_name', '') for e in entities])

        self.parent_combo = ttk.Combobox(
            main_frame,
            values=parent_options,
            state="readonly",
            width=37
        )
        self.parent_combo.set("无")
        self.parent_combo.grid(row=row, column=1, sticky=(tk.W, tk.E), pady=5, padx=(10, 0))
        row += 1

        main_frame.columnconfigure(1, weight=1)

        # Buttons
        btn_frame = ttk.Frame(main_frame)
        btn_frame.grid(row=row, column=0, columnspan=2, pady=20)

        ttk.Button(btn_frame, text="保存", command=self._save).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="取消", command=self.dialog.destroy).pack(side=tk.LEFT, padx=5)

    def _save(self):
        """Save entity."""
        try:
            entity_name = self.name_entry.get().strip()
            entity_code = self.code_entry.get().strip()

            if not entity_name or not entity_code:
                messagebox.showerror("错误", "请输入实体名称和代码")
                return

            try:
                ownership = float(self.ownership_entry.get().strip())
                if ownership < 0 or ownership > 100:
                    raise ValueError()
            except ValueError:
                messagebox.showerror("错误", "持股比例必须是0-100之间的数字")
                return

            # Get parent entity ID if selected
            parent_entity_id = None
            parent_name = self.parent_combo.get()
            if parent_name != "无" and self.storage_manager:
                entities = self.storage_manager.list_entities(self.project_id)
                parent = next((e for e in entities if e.get('entity_name') == parent_name), None)
                if parent:
                    parent_entity_id = parent.get('entity_id')

            if self.storage_manager:
                entity_id = self.storage_manager.create_entity(
                    project_id=self.project_id,
                    entity_code=entity_code,
                    entity_name=entity_name,
                    entity_type=self.type_combo.get(),
                    parent_entity_id=parent_entity_id,
                    ownership_percentage=ownership
                )
                self.result = entity_id
                self.dialog.destroy()
            else:
                messagebox.showerror("错误", "存储管理器未初始化")
        except Exception as e:
            messagebox.showerror("错误", f"保存失败: {e}")


# Export for use in main launcher
__all__ = ['ProjectManagementTab']
