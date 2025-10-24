"""
DAP - 启动界面
极简的图形用户界面，支持拖拽导入
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog
import tkinter.scrolledtext as scrolledtext
from tkinterdnd2 import DND_FILES, TkinterDnD
import threading
import os
import sys
import logging
import time
import platform
import subprocess
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Any, List, Callable, Set
import json
import pandas as pd

# 添加项目路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from main_engine import get_dap_engine
from gui_reconciliation_tabs import ReconciliationResultsTab, AdjustmentManagementTab

# 配置GUI日志处理器
class GUILogHandler(logging.Handler):
    """GUI日志处理器"""
    
    def __init__(self, text_widget):
        super().__init__()
        self.text_widget = text_widget
    
    def emit(self, record):
        """发送日志消息到GUI"""
        try:
            msg = self.format(record)
            # 在主线程中更新GUI
            self.text_widget.after(0, lambda: self._append_text(msg))
        except Exception:
            pass
    
    def _append_text(self, msg):
        """在文本框中添加消息"""
        try:
            self.text_widget.config(state='normal')
            self.text_widget.insert(tk.END, msg + '\n')
            self.text_widget.config(state='disabled')
            self.text_widget.see(tk.END)
        except Exception:
            pass

class DataExplorer(tk.Toplevel):
    PAGE_SIZE_OPTIONS = (25, 50, 100)

    def __init__(self, master, storage_manager):
        super().__init__(master)
        self.storage_manager = storage_manager
        self.master = master
        self.title("数据资产浏览器")
        self.geometry("1100x700")
        self.transient(master)
        self.grab_set()
        self.columnconfigure(0, weight=0)
        self.columnconfigure(1, weight=1)
        self.rowconfigure(0, weight=1)

        self.loaded_nodes: Set[str] = set()
        self.entity_cache: Dict[int, Dict[str, Any]] = {}
        self.year_cache: Dict[str, Dict[str, Any]] = {}
        self.account_cache: Dict[str, Dict[str, Any]] = {}
        self.current_view: str = "entity"
        self.context: Dict[str, Any] = {}
        self.current_fetcher: Optional[Callable[[int, int, Optional[str]], Dict[str, Any]]] = None
        self.current_page: int = 1
        self.total_pages: int = 1
        self.current_search: str = ""
        self.current_table_rows: List[Dict[str, Any]] = []
        self.current_columns: List[str] = []
        self.current_voucher_id: Optional[int] = None
        self.current_attachments: List[Dict[str, Any]] = []
        self._detail_row_map: Dict[str, Dict[str, Any]] = {}
        self.current_result_total: int = 0

        self.page_size_var = tk.IntVar(value=self.PAGE_SIZE_OPTIONS[1])
        self.filter_var = tk.StringVar()
        self.summary_var = tk.StringVar(value="请选择左侧节点以浏览数据。")
        self.pagination_info_var = tk.StringVar(value="")

        self._build_widgets()
        self.populate_entities()
        self.protocol("WM_DELETE_WINDOW", self.close)
        self.bind("<Escape>", lambda _event: self.close())
        self.filter_entry.focus_set()

    def _build_widgets(self) -> None:
        self.configure(padx=10, pady=10)

        tree_frame = ttk.Frame(self, padding=(0, 0, 10, 0))
        tree_frame.grid(row=0, column=0, sticky="ns")
        tree_frame.columnconfigure(0, weight=1)
        tree_frame.rowconfigure(1, weight=1)

        ttk.Label(tree_frame, text="数据结构").grid(row=0, column=0, sticky=tk.W, pady=(0, 5))

        self.tree = ttk.Treeview(tree_frame, show="tree", selectmode="browse", height=24)
        self.tree.grid(row=1, column=0, sticky="ns")
        tree_scroll = ttk.Scrollbar(tree_frame, orient="vertical", command=self.tree.yview)
        tree_scroll.grid(row=1, column=1, sticky="ns")
        self.tree.configure(yscrollcommand=tree_scroll.set)
        self.tree.bind("<<TreeviewOpen>>", self.on_tree_open)
        self.tree.bind("<<TreeviewSelect>>", self.on_tree_select)

        detail_frame = ttk.Frame(self)
        detail_frame.grid(row=0, column=1, sticky="nsew")
        detail_frame.columnconfigure(0, weight=1)
        detail_frame.rowconfigure(2, weight=1)
        detail_frame.rowconfigure(4, weight=1)

        summary_label = ttk.Label(detail_frame, textvariable=self.summary_var, font=("Arial", 11, "bold"))
        summary_label.grid(row=0, column=0, sticky=tk.W, pady=(0, 5))

        control_frame = ttk.Frame(detail_frame)
        control_frame.grid(row=1, column=0, sticky="ew", pady=(0, 5))
        control_frame.columnconfigure(1, weight=1)

        ttk.Label(control_frame, text="筛选:").grid(row=0, column=0, sticky=tk.W)
        self.filter_entry = ttk.Entry(control_frame, textvariable=self.filter_var)
        self.filter_entry.grid(row=0, column=1, sticky="ew", padx=(5, 5))
        self.apply_filter_button = ttk.Button(control_frame, text="应用", command=self.apply_filter)
        self.apply_filter_button.grid(row=0, column=2, padx=(5, 5))
        reset_button = ttk.Button(control_frame, text="清除", command=self.reset_filter)
        reset_button.grid(row=0, column=3)

        ttk.Label(control_frame, text="每页:").grid(row=0, column=4, padx=(15, 0))
        self.page_size_combo = ttk.Combobox(
            control_frame,
            width=5,
            state="readonly",
            values=self.PAGE_SIZE_OPTIONS,
            textvariable=self.page_size_var,
        )
        self.page_size_combo.grid(row=0, column=5)
        self.page_size_combo.bind("<<ComboboxSelected>>", self.on_page_size_change)
        self.page_size_combo.config(state="disabled")

        detail_table_frame = ttk.Frame(detail_frame)
        detail_table_frame.grid(row=2, column=0, sticky="nsew")
        detail_table_frame.columnconfigure(0, weight=1)
        detail_table_frame.rowconfigure(0, weight=1)

        self.detail_tree = ttk.Treeview(detail_table_frame, show="headings")
        self.detail_tree.grid(row=0, column=0, sticky="nsew")
        detail_scroll_y = ttk.Scrollbar(detail_table_frame, orient="vertical", command=self.detail_tree.yview)
        detail_scroll_y.grid(row=0, column=1, sticky="ns")
        detail_scroll_x = ttk.Scrollbar(detail_table_frame, orient="horizontal", command=self.detail_tree.xview)
        detail_scroll_x.grid(row=1, column=0, sticky="ew")
        self.detail_tree.configure(yscrollcommand=detail_scroll_y.set, xscrollcommand=detail_scroll_x.set)
        self.detail_tree.bind("<Double-1>", self.on_detail_double_click)

        pagination_frame = ttk.Frame(detail_frame)
        pagination_frame.grid(row=3, column=0, sticky="ew", pady=(5, 5))
        pagination_frame.columnconfigure(1, weight=1)

        self.prev_button = ttk.Button(pagination_frame, text="上一页", command=self.go_prev_page, state=tk.DISABLED)
        self.prev_button.grid(row=0, column=0)

        pagination_label = ttk.Label(pagination_frame, textvariable=self.pagination_info_var)
        pagination_label.grid(row=0, column=1, sticky=tk.EW)

        self.next_button = ttk.Button(pagination_frame, text="下一页", command=self.go_next_page, state=tk.DISABLED)
        self.next_button.grid(row=0, column=2)

        attachment_frame = ttk.LabelFrame(detail_frame, text="附件", padding=5)
        attachment_frame.grid(row=4, column=0, sticky="nsew")
        attachment_frame.columnconfigure(0, weight=1)
        attachment_frame.rowconfigure(0, weight=1)

        self.attachment_tree = ttk.Treeview(
            attachment_frame,
            columns=("path", "description", "uploaded"),
            show="headings",
            height=6,
        )
        self.attachment_tree.heading("path", text="路径")
        self.attachment_tree.heading("description", text="说明")
        self.attachment_tree.heading("uploaded", text="上传时间")
        self.attachment_tree.column("path", width=360)
        self.attachment_tree.column("description", width=240)
        self.attachment_tree.column("uploaded", width=140)
        self.attachment_tree.grid(row=0, column=0, sticky="nsew")

        attachment_scroll = ttk.Scrollbar(attachment_frame, orient="vertical", command=self.attachment_tree.yview)
        attachment_scroll.grid(row=0, column=1, sticky="ns")
        self.attachment_tree.configure(yscrollcommand=attachment_scroll.set)
        self.attachment_tree.bind("<Double-1>", lambda _event: self.open_selected_attachment())

        self.attachment_button = ttk.Button(
            attachment_frame,
            text="打开附件",
            command=self.open_selected_attachment,
            state=tk.DISABLED,
        )
        self.attachment_button.grid(row=1, column=0, sticky=tk.E, pady=(5, 0))

        self._clear_attachments()
        self._update_pagination_controls({"total": 0, "page": 1, "total_pages": 1})

    def _add_placeholder(self, node_id: str) -> None:
        placeholder_id = f"{node_id}::placeholder"
        if placeholder_id not in self.tree.get_children(node_id):
            self.tree.insert(node_id, "end", iid=placeholder_id, text="加载中…")

    def _remove_placeholder(self, node_id: str) -> None:
        for child in list(self.tree.get_children(node_id)):
            if child.endswith("::placeholder"):
                self.tree.delete(child)

    def _safe_key(self, value: Any) -> str:
        text = str(value) if value not in (None, "") else "UNSET"
        return text.replace(":", "_").replace("/", "_").replace("\\", "_").replace(" ", "_")

    def populate_entities(self) -> None:
        for child in self.tree.get_children():
            self.tree.delete(child)
        self.loaded_nodes.clear()
        self.entity_cache.clear()
        self.year_cache.clear()
        self.account_cache.clear()

        try:
            entities = self.storage_manager.list_entities_summary()
        except Exception as exc:
            logging.error("加载实体失败: %s", exc)
            messagebox.showerror("错误", f"无法加载实体: {exc}")
            self.summary_var.set("加载实体失败，请检查日志。")
            return

        if not entities:
            self.summary_var.set("暂无可浏览的数据，请先完成数据处理。")
            return

        for entity in entities:
            entity_id = entity.get("entity_id")
            if entity_id is None:
                continue
            name = entity.get("entity_name") or "未命名实体"
            code = entity.get("entity_code") or ""
            voucher_count = entity.get("voucher_count", 0)
            parts = [name]
            if code:
                parts.append(f"代码 {code}")
            parts.append(f"{voucher_count} 张凭证")
            node_id = f"entity:{entity_id}"
            self.entity_cache[entity_id] = entity
            self.tree.insert("", "end", iid=node_id, text=" · ".join(parts))
            self._add_placeholder(node_id)

    def on_tree_open(self, event) -> None:
        node_id = self.tree.focus()
        if not node_id or node_id.endswith("::placeholder"):
            return
        if node_id in self.loaded_nodes:
            return
        node_type, *parts = node_id.split(":")
        if node_type == "entity":
            entity_id = int(parts[0])
            self._load_year_nodes(node_id, entity_id)
        elif node_type == "year":
            self._load_account_nodes(node_id)
        self.loaded_nodes.add(node_id)

    def on_tree_select(self, event) -> None:
        node_id = self.tree.focus()
        if not node_id or node_id.endswith("::placeholder"):
            return
        node_type, *parts = node_id.split(":")
        self._clear_attachments()
        if node_type == "entity":
            entity_id = int(parts[0])
            self._show_entity(entity_id)
        elif node_type == "year":
            data = self.year_cache.get(node_id)
            if not data:
                return
            self._show_accounts(data["entity_id"], data["fiscal_year"], data["display"], search=None)
        elif node_type == "account":
            data = self.account_cache.get(node_id)
            if not data:
                return
            self._show_vouchers(
                data["entity_id"],
                data["fiscal_year"],
                data["display_year"],
                data["account_id"],
                account_label=data["account_label"],
                search=None,
            )

    def _load_year_nodes(self, node_id: str, entity_id: int) -> None:
        self._remove_placeholder(node_id)
        try:
            years = self.storage_manager.list_years_for_entity(entity_id)
        except Exception as exc:
            logging.error("加载年度失败: %s", exc)
            messagebox.showerror("错误", f"无法加载年度: {exc}")
            return
        for year in years:
            fiscal_year = year.get("fiscal_year") or "未设置"
            display = str(fiscal_year)
            cache = {
                "entity_id": entity_id,
                "fiscal_year": year.get("fiscal_year") or "",
                "display": display,
            }
            child_id = f"year:{entity_id}:{len(self.year_cache)}"
            self.year_cache[child_id] = cache
            text = f"{display} 年（{year.get('voucher_count', 0)} 张凭证）"
            self.tree.insert(node_id, "end", iid=child_id, text=text)
            self._add_placeholder(child_id)

    def _load_account_nodes(self, node_id: str) -> None:
        self._remove_placeholder(node_id)
        data = self.year_cache.get(node_id)
        if not data:
            return
        entity_id = data["entity_id"]
        fiscal_year = data["fiscal_year"]
        display_year = data["display"]
        try:
            accounts = self.storage_manager.list_accounts_for_entity_year(entity_id, fiscal_year)
        except Exception as exc:
            logging.error("加载科目失败: %s", exc)
            messagebox.showerror("错误", f"无法加载科目: {exc}")
            return
        for account in accounts:
            account_id = account.get("account_id")
            if account_id is None:
                continue
            code = account.get("account_code") or ""
            name = account.get("account_name") or ""
            label = f"{code} {name}".strip() or f"科目 {account_id}"
            text = f"{label}（{account.get('voucher_count', 0)} 张凭证）"
            child_id = f"account:{entity_id}:{len(self.account_cache)}:{account_id}"
            self.account_cache[child_id] = {
                "entity_id": entity_id,
                "fiscal_year": fiscal_year,
                "display_year": display_year,
                "account_id": account_id,
                "account_code": code,
                "account_name": name,
                "account_label": label,
            }
            self.tree.insert(node_id, "end", iid=child_id, text=text)

    def _show_entity(self, entity_id: int) -> None:
        entity = self.entity_cache.get(entity_id)
        if not entity:
            return
        try:
            years = self.storage_manager.list_years_for_entity(entity_id)
        except Exception as exc:
            logging.error("获取年度统计失败: %s", exc)
            messagebox.showerror("错误", f"无法获取年度统计: {exc}")
            return
        name = entity.get("entity_name") or "未命名实体"
        code = entity.get("entity_code") or ""
        voucher_count = entity.get("voucher_count", 0)
        parts = [name]
        if code:
            parts.append(f"代码 {code}")
        parts.append(f"共 {voucher_count} 张凭证")
        self._set_summary(" · ".join(parts))
        rows: List[Dict[str, Any]] = []
        for year in years:
            display = year.get("fiscal_year") or "未设置"
            rows.append(
                {
                    "年度": display,
                    "凭证数量": year.get("voucher_count", 0),
                    "借方金额": year.get("total_debit", 0),
                    "贷方金额": year.get("total_credit", 0),
                    "期间数": year.get("period_count", 0),
                }
            )
        columns = ["年度", "凭证数量", "借方金额", "贷方金额", "期间数"]
        self.filter_var.set("")
        self._set_static_table(columns, rows, view="entity_years", context={"entity_id": entity_id})

    def _show_accounts(
        self,
        entity_id: int,
        fiscal_year: str,
        display_year: str,
        search: Optional[str] = None,
    ) -> None:
        try:
            accounts = self.storage_manager.list_accounts_for_entity_year(entity_id, fiscal_year, search=search)
        except Exception as exc:
            logging.error("获取科目统计失败: %s", exc)
            messagebox.showerror("错误", f"无法获取科目统计: {exc}")
            return
        entity = self.entity_cache.get(entity_id, {})
        name = entity.get("entity_name") or "实体"
        summary = f"{name} · {display_year} 年度科目（{len(accounts)} 个）"
        if search:
            summary += f" · 筛选: {search}"
        self._set_summary(summary)
        if search is None:
            self.filter_var.set("")
        rows: List[Dict[str, Any]] = []
        for account in accounts:
            account_id = account.get("account_id")
            code = account.get("account_code") or ""
            name = account.get("account_name") or ""
            label = f"{code} {name}".strip() or f"科目 {account_id}"
            rows.append(
                {
                    "科目编码": code,
                    "科目名称": name,
                    "凭证数量": account.get("voucher_count", 0),
                    "借方金额": account.get("total_debit", 0),
                    "贷方金额": account.get("total_credit", 0),
                    "account_id": account_id,
                    "account_label": label,
                }
            )
        columns = ["科目编码", "科目名称", "凭证数量", "借方金额", "贷方金额"]
        self.context = {
            "entity_id": entity_id,
            "fiscal_year": fiscal_year,
            "display_year": display_year,
        }
        self._set_static_table(columns, rows, view="accounts", context=self.context.copy())

    def _show_vouchers(
        self,
        entity_id: int,
        fiscal_year: str,
        display_year: str,
        account_id: int,
        account_label: str,
        search: Optional[str] = None,
    ) -> None:
        entity = self.entity_cache.get(entity_id, {})
        entity_name = entity.get("entity_name") or "实体"
        try:
            result = self.storage_manager.list_vouchers_for_account(
                entity_id,
                fiscal_year,
                account_id,
                page=1,
                page_size=self.page_size_var.get(),
                search=search,
            )
        except Exception as exc:
            logging.error("获取凭证失败: %s", exc)
            messagebox.showerror("错误", f"无法获取凭证: {exc}")
            return
        total = result.get("total", 0)
        summary = f"{entity_name} · {display_year} 年 · {account_label}（{total} 张凭证）"
        if search:
            summary += f" · 筛选: {search}"
        self._set_summary(summary)
        if search is None:
            self.filter_var.set("")
        fetcher = lambda page, size, term=None: self.storage_manager.list_vouchers_for_account(
            entity_id,
            fiscal_year,
            account_id,
            page=page,
            page_size=size,
            search=term,
        )
        self.context = {
            "entity_id": entity_id,
            "fiscal_year": fiscal_year,
            "display_year": display_year,
            "account_id": account_id,
            "account_label": account_label,
        }
        self._set_paged_fetcher(
            fetcher,
            view="vouchers",
            context=self.context.copy(),
            initial_result=result,
            search_term=search,
        )

    def _open_voucher(self, voucher_row: Dict[str, Any]) -> None:
        voucher_id = voucher_row.get("voucher_id")
        if not voucher_id:
            return
        ctx = self.context.copy()
        entity_id = ctx.get("entity_id")
        entity = self.entity_cache.get(entity_id, {})
        entity_name = entity.get("entity_name") or "实体"
        display_year = ctx.get("display_year", "")
        account_label = ctx.get("account_label", "关联科目")
        number = voucher_row.get("voucher_number") or ""
        date_text = voucher_row.get("voucher_date") or "无日期"
        summary = voucher_row.get("summary") or ""
        header = f"凭证：{number}（{date_text}）"
        if summary:
            header += f" · {summary}"
        self._set_summary(f"{entity_name} · {display_year} · {account_label}\n{header}")
        self.filter_var.set("")
        fetcher = lambda page, size, term=None: self.storage_manager.get_voucher_entries_paginated(
            voucher_id,
            page=page,
            page_size=size,
            search=term,
        )
        try:
            result = fetcher(1, self.page_size_var.get(), None)
        except Exception as exc:
            logging.error("获取分录失败: %s", exc)
            messagebox.showerror("错误", f"无法获取分录: {exc}")
            return
        self.context = {
            "entity_id": entity_id,
            "fiscal_year": ctx.get("fiscal_year", ""),
            "display_year": display_year,
            "account_id": ctx.get("account_id"),
            "account_label": account_label,
            "voucher_id": voucher_id,
        }
        self.current_voucher_id = voucher_id
        self._set_paged_fetcher(
            fetcher,
            view="entries",
            context=self.context.copy(),
            initial_result=result,
            search_term=None,
        )
        try:
            attachments = self.storage_manager.get_voucher_attachments(voucher_id)
        except Exception as exc:
            logging.error("获取附件失败: %s", exc)
            attachments = []
        self._load_attachments(attachments)

    def _set_summary(self, text: str) -> None:
        self.summary_var.set(text)

    def _set_static_table(
        self,
        columns: List[str],
        rows: List[Dict[str, Any]],
        view: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> None:
        self.current_fetcher = None
        self.current_view = view
        self.context = context or {}
        self.current_search = ""
        self.current_page = 1
        self.total_pages = 1
        self.current_table_rows = rows
        self.current_columns = columns
        self._update_detail_table(columns, rows)
        self._update_pagination_controls({"total": len(rows), "page": 1, "total_pages": 1})
        self.page_size_combo.config(state="disabled")

    def _set_paged_fetcher(
        self,
        fetcher: Callable[[int, int, Optional[str]], Dict[str, Any]],
        view: str,
        context: Dict[str, Any],
        initial_result: Optional[Dict[str, Any]] = None,
        search_term: Optional[str] = None,
    ) -> None:
        self.current_fetcher = fetcher
        self.current_view = view
        self.context = context
        self.current_search = search_term or ""
        self.page_size_combo.config(state="readonly")
        if initial_result is not None:
            self.current_page = initial_result.get("page", 1)
            self.total_pages = initial_result.get("total_pages", 1)
            self.current_result_total = initial_result.get("total", 0)
            page_size = initial_result.get("page_size")
            if page_size:
                self.page_size_var.set(int(page_size))
            self._apply_result(initial_result)
        else:
            self.current_page = 1
            self._refresh_page()

    def _apply_result(self, result: Dict[str, Any]) -> None:
        columns = result.get("columns", [])
        rows = result.get("rows", [])
        self.current_columns = columns
        self.current_table_rows = rows
        self.current_page = result.get("page", self.current_page)
        self.total_pages = result.get("total_pages", self.total_pages)
        self.current_result_total = result.get("total", len(rows))
        self._update_detail_table(columns, rows)
        self._update_pagination_controls(result)

    def _update_detail_table(self, columns: List[str], rows: List[Dict[str, Any]]) -> None:
        self.detail_tree.delete(*self.detail_tree.get_children())
        self._detail_row_map = {}
        if not columns:
            self.detail_tree["columns"] = ()
            return
        self.detail_tree["columns"] = columns
        for col in columns:
            self.detail_tree.heading(col, text=col)
            self.detail_tree.column(col, width=160, anchor=tk.W)
        for row in rows:
            if isinstance(row, dict):
                values = [self._format_value(row.get(col)) for col in columns]
            else:
                values = [self._format_value(value) for value in row]
            item_id = self.detail_tree.insert("", "end", values=values)
            if isinstance(row, dict):
                self._detail_row_map[item_id] = row

    def _update_pagination_controls(self, result: Dict[str, Any]) -> None:
        total = result.get("total", len(self.current_table_rows))
        page = result.get("page", 1)
        total_pages = max(1, result.get("total_pages", 1))
        if self.current_fetcher:
            self.pagination_info_var.set(f"第 {page} / {total_pages} 页 · 共 {total} 条记录")
            self.prev_button.config(state=tk.NORMAL if page > 1 else tk.DISABLED)
            self.next_button.config(state=tk.NORMAL if page < total_pages else tk.DISABLED)
        else:
            self.pagination_info_var.set(f"共 {total} 条记录")
            self.prev_button.config(state=tk.DISABLED)
            self.next_button.config(state=tk.DISABLED)

    def _refresh_page(self) -> None:
        if not self.current_fetcher:
            return
        try:
            result = self.current_fetcher(self.current_page, self.page_size_var.get(), self.current_search or None)
        except Exception as exc:
            logging.error("分页查询失败: %s", exc)
            messagebox.showerror("错误", f"查询失败: {exc}")
            return
        self._apply_result(result)

    def go_prev_page(self) -> None:
        if self.current_fetcher and self.current_page > 1:
            self.current_page -= 1
            self._refresh_page()

    def go_next_page(self) -> None:
        if self.current_fetcher and self.current_page < self.total_pages:
            self.current_page += 1
            self._refresh_page()

    def apply_filter(self) -> None:
        term = (self.filter_var.get() or "").strip()
        if self.current_view == "accounts":
            ctx = self.context.copy()
            self._show_accounts(ctx.get("entity_id"), ctx.get("fiscal_year", ""), ctx.get("display_year", ""), search=term or None)
        elif self.current_view in {"vouchers", "entries"}:
            self.current_search = term
            self.current_page = 1
            self._refresh_page()
        elif term:
            messagebox.showinfo("筛选", "当前视图不支持筛选。")

    def reset_filter(self) -> None:
        if not self.filter_var.get():
            return
        self.filter_var.set("")
        if self.current_view == "accounts":
            ctx = self.context.copy()
            self._show_accounts(ctx.get("entity_id"), ctx.get("fiscal_year", ""), ctx.get("display_year", ""), search=None)
        elif self.current_view in {"vouchers", "entries"}:
            self.current_search = ""
            self.current_page = 1
            self._refresh_page()

    def on_page_size_change(self, _event=None) -> None:
        if not self.current_fetcher:
            return
        self.current_page = 1
        self._refresh_page()

    def on_detail_double_click(self, _event=None) -> None:
        item_id = self.detail_tree.focus()
        if not item_id:
            return
        row = self._detail_row_map.get(item_id)
        if not row:
            return
        if self.current_view == "accounts":
            account_id = row.get("account_id")
            if account_id is None:
                return
            ctx = self.context.copy()
            label = row.get("account_label") or ""
            if not label:
                code = row.get("科目编码") or ""
                name = row.get("科目名称") or ""
                label = f"{code} {name}".strip() or f"科目 {account_id}"
            self._show_vouchers(
                ctx.get("entity_id"),
                ctx.get("fiscal_year", ""),
                ctx.get("display_year", ""),
                account_id,
                account_label=label,
                search=None,
            )
        elif self.current_view == "vouchers":
            self._open_voucher(row)

    def _clear_attachments(self) -> None:
        self.attachment_tree.delete(*self.attachment_tree.get_children())
        self.current_attachments = []
        self.attachment_button.config(state=tk.DISABLED)

    def _load_attachments(self, attachments: List[Dict[str, Any]]) -> None:
        self.attachment_tree.delete(*self.attachment_tree.get_children())
        self.current_attachments = attachments
        for attachment in attachments:
            values = [
                attachment.get("file_path") or "",
                attachment.get("description") or "",
                attachment.get("uploaded_at") or "",
            ]
            self.attachment_tree.insert("", "end", values=values)
        self.attachment_button.config(state=tk.NORMAL if attachments else tk.DISABLED)

    def open_selected_attachment(self) -> None:
        if not self.current_attachments:
            return
        selection = self.attachment_tree.focus()
        if not selection:
            return
        index = self.attachment_tree.index(selection)
        if index >= len(self.current_attachments):
            return
        attachment = self.current_attachments[index]
        file_path = attachment.get("file_path")
        if not file_path:
            messagebox.showwarning("附件", "附件路径为空。")
            return
        full_path = Path(file_path)
        if not full_path.is_absolute():
            full_path = Path.cwd() / full_path
        if not full_path.exists():
            messagebox.showerror("附件", f"附件不存在：{full_path}")
            return
        try:
            if platform.system() == "Windows":
                os.startfile(str(full_path))  # type: ignore[attr-defined]
            elif platform.system() == "Darwin":
                subprocess.Popen(["open", str(full_path)])
            else:
                subprocess.Popen(["xdg-open", str(full_path)])
        except Exception as exc:
            messagebox.showerror("附件", f"无法打开附件：{exc}")

    def _format_value(self, value: Any) -> str:
        if value is None:
            return ""
        if isinstance(value, float):
            return f"{value:,.2f}"
        return str(value)

    def close(self) -> None:
        try:
            self.grab_release()
        except Exception:
            pass
        self.destroy()


class DAPLauncher:
    """DAP启动器主界面"""
    
    def __init__(self):
        # 创建主窗口
        self.root = TkinterDnD.Tk()
        self.root.title("DAP - 数据处理审计智能体")
        self.root.geometry("900x700")
        self.root.resizable(True, True)

        # 项目选择状态
        self.project_var = tk.StringVar()
        self.project_combobox: Optional[ttk.Combobox] = None
        self.project_choice_map: Dict[str, Dict[str, Any]] = {}
        self.active_project_id: Optional[str] = None

        # 设置窗口图标（如果有的话）
        try:
            # self.root.iconbitmap('icon.ico')  # 如果有图标文件
            pass
        except:
            pass
        
        # 初始化变量
        self.processing = False
        self.dap_engine = None
        self.current_file = None
        self.report_notes = []
        self.last_command_result = []
        
        # 创建界面
        self.create_widgets()
        
        # 配置拖拽
        self.setup_drag_drop()
        
        # 设置日志
        self.setup_logging()
        
        # 初始化引擎
        self.init_engine()
        
        print("DAP启动器界面初始化完成")
    
    def create_widgets(self):
        """创建界面组件"""
        # 主框架
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # 配置网格权重
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(0, weight=1)
        main_frame.rowconfigure(2, weight=1)
        
        # 标题
        title_label = ttk.Label(
            main_frame, 
            text="DAP - 数据处理审计智能体",
            font=('Arial', 16, 'bold')
        )
        title_label.grid(row=0, column=0, pady=(0, 10))
        
        # 副标题
        subtitle_label = ttk.Label(
            main_frame,
            text="一键启动数据处理 | 支持拖拽导入 | AI智能分析",
            font=('Arial', 10)
        )
        subtitle_label.grid(row=1, column=0, pady=(0, 20))
        
        # 主要操作区域
        self.create_main_area(main_frame)
        
        # 状态栏
        self.create_status_bar(main_frame)
    
    def create_main_area(self, parent):
        """创建主要操作区域"""
        # 创建笔记本组件（标签页）
        self.notebook = ttk.Notebook(parent)
        self.notebook.grid(row=2, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(0, 10))

        # 数据导入标签页
        self.create_import_tab(self.notebook)

        # 系统状态标签页
        self.create_status_tab(self.notebook)

        # 数据管理标签页
        self.create_data_tab(self.notebook)

        # AI分析标签页
        self.create_ai_tab(self.notebook)

        # 对账结果展示标签页
        self.create_reconciliation_tab(self.notebook)

        # 调整管理标签页
        self.create_adjustment_tab(self.notebook)
    
    def create_import_tab(self, parent):
        """创建数据导入标签页"""
        import_frame = ttk.Frame(parent, padding="10")
        parent.add(import_frame, text="数据导入")
        
        # 配置网格
        import_frame.columnconfigure(0, weight=1)
        import_frame.rowconfigure(1, weight=1)
        
        # 导入说明
        info_text = """
🚀 支持的数据源类型：
• ERP/SAP 导出文件 (.xlsx, .xls)
• 通用 CSV 文本 (.csv)
• SQL/数据库备份 (.bak, .sql)
• 数据库文件 (.db, .sqlite, .mdb, .accdb)
• AIS/行业专用格式 (.ais)
• 压缩文件 (.zip, .rar) —— 完整模式可自动解压
• 文件夹（批量处理多个数据文件）

📋 操作方式：
1. 点击下方按钮选择文件或文件夹
2. 也可以直接拖拽到中间区域
3. 轻量模式支持常见表格文件，完整模式可处理压缩包与数据库
        """
        
        info_label = ttk.Label(import_frame, text=info_text, justify=tk.LEFT)
        info_label.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=(0, 10))
        
        # 拖拽区域
        self.drag_frame = tk.Frame(
            import_frame,
            bg='#f0f0f0',
            relief=tk.RAISED,
            bd=2,
            height=200
        )
        self.drag_frame.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(0, 10))
        self.drag_frame.grid_propagate(False)
        
        # 拖拽区域内容
        drag_label = tk.Label(
            self.drag_frame,
            text="🗂️ 拖拽文件或文件夹到此处\n\n支持: Excel / CSV / 数据库文件 / 压缩包\n提示: 复杂数据库建议在完整模式下处理",
            bg="#f0f0f0",
            font=("Arial", 12),
            fg="#666",
        )
        drag_label.pack(expand=True)
        
        # 按钮框架
        button_frame = ttk.Frame(import_frame)
        button_frame.grid(row=2, column=0, pady=5)
        
        # 选择文件按钮
        select_file_button = ttk.Button(
            button_frame,
            text="📁 选择文件",
            command=self.select_file,
            style='Accent.TButton'
        )
        select_file_button.pack(side=tk.LEFT, padx=5)
        
        # 选择文件夹按钮
        select_folder_button = ttk.Button(
            button_frame,
            text="📂 选择文件夹",
            command=self.select_folder,
            style='Accent.TButton'
        )
        select_folder_button.pack(side=tk.LEFT, padx=5)
        
        # 项目设置
        project_frame = ttk.LabelFrame(import_frame, text="项目设置", padding="5")
        project_frame.grid(row=3, column=0, sticky=(tk.W, tk.E), pady=10)
        project_frame.columnconfigure(1, weight=1)

        ttk.Label(project_frame, text="选择项目").grid(row=0, column=0, sticky=tk.W)
        self.project_combobox = ttk.Combobox(
            project_frame,
            textvariable=self.project_var,
            state="readonly",
            height=6,
        )
        self.project_combobox.grid(row=0, column=1, sticky=(tk.W, tk.E), padx=(5, 5))
        self.project_combobox.bind("<<ComboboxSelected>>", self.on_project_selected)

        refresh_button = ttk.Button(
            project_frame,
            text="刷新",
            width=8,
            command=self.refresh_project_list,
        )
        refresh_button.grid(row=0, column=2, padx=(5, 5))

        create_button = ttk.Button(
            project_frame,
            text="新建项目",
            width=10,
            command=self.prompt_create_project,
        )
        create_button.grid(row=0, column=3)

        # 处理选项
        options_frame = ttk.LabelFrame(import_frame, text="处理选项", padding="5")
        options_frame.grid(row=4, column=0, sticky=(tk.W, tk.E), pady=10)
        
        self.auto_start_api = tk.BooleanVar(value=True)
        api_check = ttk.Checkbutton(
            options_frame,
            text="自动启动API服务",
            variable=self.auto_start_api
        )
        api_check.grid(row=0, column=0, sticky=tk.W)
        
        self.auto_ai_analysis = tk.BooleanVar(value=False)
        ai_check = ttk.Checkbutton(
            options_frame,
            text="自动进行AI分析",
            variable=self.auto_ai_analysis
        )
        ai_check.grid(row=0, column=1, sticky=tk.W, padx=(20, 0))
        
        # 开始处理按钮
        self.process_button = ttk.Button(
            import_frame,
            text="🚀 开始处理",
            command=self.start_processing,
            state='disabled'
        )
        self.process_button.grid(row=5, column=0, pady=10)

        self.refresh_project_list()
    
    def create_status_tab(self, parent):
        """创建系统状态标签页"""
        status_frame = ttk.Frame(parent, padding="10")
        parent.add(status_frame, text="系统状态")
        
        # 配置网格
        status_frame.columnconfigure(0, weight=1)
        status_frame.rowconfigure(1, weight=1)
        
        # 刷新按钮
        refresh_button = ttk.Button(
            status_frame,
            text="🔄 刷新状态",
            command=self.refresh_status
        )
        refresh_button.grid(row=0, column=0, sticky=tk.W, pady=(0, 10))
        
        # 状态显示区域
        self.status_text = scrolledtext.ScrolledText(
            status_frame,
            height=15,
            state='disabled',
            wrap=tk.WORD
        )
        self.status_text.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # 初始显示状态
        self.refresh_status()
    
    def create_data_tab(self, parent):
        """创建数据管理标签页"""
        data_frame = ttk.Frame(parent, padding="10")
        parent.add(data_frame, text="数据管理")
        
        # 配置网格
        data_frame.columnconfigure(0, weight=1)
        data_frame.rowconfigure(3, weight=1)
        
        # 操作按钮区域
        button_frame = ttk.Frame(data_frame)
        button_frame.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=(0, 10))
        
        # 查看表按钮
        view_tables_button = ttk.Button(
            button_frame,
            text="📊 查看数据表",
            command=self.view_tables
        )
        view_tables_button.grid(row=0, column=0, padx=(0, 5))
        
        # 查看视图按钮
        view_views_button = ttk.Button(
            button_frame,
            text="👁️ 查看数据视图",
            command=self.view_views
        )
        view_views_button.grid(row=0, column=1, padx=5)
        
        # 导入新输出格式按钮
        import_button = ttk.Button(
            button_frame,
            text="📥 导入新输出格式",
            command=self.import_data_dialog
        )
        import_button.grid(row=0, column=2, padx=5)
        
        # 财务报表导出按钮
        financial_export_button = ttk.Button(
            button_frame,
            text="💰 财务报表导出",
            command=self.financial_export_dialog
        )
        financial_export_button.grid(row=0, column=3, padx=5)

        # 财务报表查看器按钮 (新增)
        view_financial_button = ttk.Button(
            button_frame,
            text="📊 财务报表查看",
            command=self.open_financial_viewer,
            style='Accent.TButton'
        )
        view_financial_button.grid(row=0, column=4, padx=5)

        # 生成报告按钮
        report_button = ttk.Button(
            button_frame,
            text="📋 生成审计报告",
            command=self.generate_report_dialog
        )
        report_button.grid(row=0, column=5, padx=(5, 0))
        
        # 人机交互区域
        interaction_frame = ttk.LabelFrame(
            data_frame, text="人机交互 · 数据处理指令", padding="10"
        )
        interaction_frame.grid(row=1, column=0, sticky=(tk.W, tk.E), pady=(0, 10))
        interaction_frame.columnconfigure(1, weight=1)

        ttk.Label(interaction_frame, text="处理指令:").grid(
            row=0, column=0, sticky=tk.NW
        )
        self.command_input = tk.Text(interaction_frame, height=3, wrap=tk.WORD)
        self.command_input.grid(
            row=0, column=1, sticky=(tk.W, tk.E), padx=(5, 0), pady=(0, 5)
        )

        submit_button = ttk.Button(
            interaction_frame,
            text="✅ 提交指令",
            command=self.execute_data_command,
        )
        submit_button.grid(row=1, column=1, sticky=tk.E, pady=(0, 5))

        self.command_output = scrolledtext.ScrolledText(
            interaction_frame,
            height=6,
            state="disabled",
            wrap=tk.WORD,
        )
        self.command_output.grid(
            row=2, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 5)
        )

        # 审计成果输出区域
        output_frame = ttk.LabelFrame(data_frame, text="审计成果输出", padding="10")
        output_frame.grid(row=2, column=0, sticky=(tk.W, tk.E), pady=(0, 10))

        output_buttons = ttk.Frame(output_frame)
        output_buttons.grid(row=0, column=0, sticky=tk.W)

        workpaper_button = ttk.Button(
            output_buttons,
            text="📁 输出审计底稿",
            command=self.export_audit_workpapers,
        )
        workpaper_button.grid(row=0, column=0, padx=(0, 5), pady=2)

        report_button = ttk.Button(
            output_buttons,
            text="📄 输出审计报告",
            command=self.export_audit_report,
        )
        report_button.grid(row=0, column=1, padx=5, pady=2)

        note_button = ttk.Button(
            output_buttons,
            text="📝 添加审计报告附注",
            command=self.add_report_note,
        )
        note_button.grid(row=0, column=2, padx=5, pady=2)

        self.output_status_var = tk.StringVar(
            value="请选择操作生成底稿或报告。"
        )
        ttk.Label(output_frame, textvariable=self.output_status_var).grid(
            row=1, column=0, sticky=tk.W, pady=(5, 0)
        )

        # 数据显示区域
        self.data_text = scrolledtext.ScrolledText(
            data_frame,
            height=15,
            state='disabled',
            wrap=tk.NONE
        )
        self.data_text.grid(row=3, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
    
    def create_ai_tab(self, parent):
        """创建AI分析标签页"""
        ai_frame = ttk.Frame(parent, padding="10")
        parent.add(ai_frame, text="AI分析")
        
        # 配置网格
        ai_frame.columnconfigure(0, weight=1)
        ai_frame.rowconfigure(2, weight=1)
        
        # AI客户端状态
        status_frame = ttk.LabelFrame(ai_frame, text="AI客户端状态", padding="5")
        status_frame.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=(0, 10))
        
        self.ai_status_label = ttk.Label(status_frame, text="正在检查AI客户端...")
        self.ai_status_label.grid(row=0, column=0, sticky=tk.W)
        
        # 分析输入区域
        input_frame = ttk.LabelFrame(ai_frame, text="分析请求", padding="5")
        input_frame.grid(row=1, column=0, sticky=(tk.W, tk.E), pady=(0, 10))
        input_frame.columnconfigure(0, weight=1)
        
        # 数据源选择
        ttk.Label(input_frame, text="数据源:").grid(row=0, column=0, sticky=tk.W)
        self.data_source_var = tk.StringVar()
        self.data_source_combo = ttk.Combobox(
            input_frame,
            textvariable=self.data_source_var,
            state="readonly"
        )
        self.data_source_combo.grid(row=0, column=1, sticky=(tk.W, tk.E), padx=(5, 0))
        
        # 分析提示
        ttk.Label(input_frame, text="分析要求:").grid(row=1, column=0, sticky=(tk.W, tk.N), pady=(5, 0))
        self.prompt_text = tk.Text(input_frame, height=3, wrap=tk.WORD)
        self.prompt_text.grid(row=1, column=1, sticky=(tk.W, tk.E), padx=(5, 0), pady=(5, 0))
        
        # 预设分析按钮
        preset_frame = ttk.Frame(input_frame)
        preset_frame.grid(row=2, column=0, columnspan=2, pady=5)
        
        preset_buttons = [
            ("💰 财务分析", "请分析这些财务数据的总体状况、趋势和关键指标"),
            ("⚠️ 风险识别", "请识别数据中的潜在风险点和异常交易"),
            ("📊 数据质量", "请评估数据质量，识别缺失值、重复项和异常值"),
            ("🔍 异常检测", "请检测数据中的异常模式和可疑交易")
        ]
        
        for i, (text, prompt) in enumerate(preset_buttons):
            btn = ttk.Button(
                preset_frame,
                text=text,
                command=lambda p=prompt: self.set_prompt_text(p)
            )
            btn.grid(row=i//2, column=i%2, padx=5, pady=2, sticky=tk.W)
        
        # 分析按钮
        analyze_button = ttk.Button(
            input_frame,
            text="🤖 开始AI分析",
            command=self.start_ai_analysis
        )
        analyze_button.grid(row=3, column=0, columnspan=2, pady=10)
        
        # 分析结果显示
        self.ai_result_text = scrolledtext.ScrolledText(
            ai_frame,
            height=12,
            state='disabled',
            wrap=tk.WORD
        )
        self.ai_result_text.grid(row=2, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # 更新AI状态
        self.update_ai_status()
    
    def create_status_bar(self, parent):
        """创建状态栏"""
        status_frame = ttk.Frame(parent)
        status_frame.grid(row=3, column=0, sticky=(tk.W, tk.E))
        status_frame.columnconfigure(1, weight=1)
        
        # 进度条
        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(
            status_frame,
            variable=self.progress_var,
            maximum=100
        )
        self.progress_bar.grid(row=0, column=0, sticky=(tk.W, tk.E), padx=(0, 10))
        
        # 状态文本
        self.status_var = tk.StringVar(value="就绪")
        status_label = ttk.Label(status_frame, textvariable=self.status_var)
        status_label.grid(row=0, column=1, sticky=tk.W)
        
        # 时间标签
        self.time_var = tk.StringVar()
        time_label = ttk.Label(status_frame, textvariable=self.time_var)
        time_label.grid(row=0, column=2, sticky=tk.E)
        
        # 更新时间
        self.update_time()
    
    def setup_drag_drop(self):
        """设置拖拽功能"""
        self.drag_frame.drop_target_register(DND_FILES)
        self.drag_frame.dnd_bind('<<Drop>>', self.on_drop)
    
    def setup_logging(self):
        """设置日志处理"""
        # 创建GUI日志处理器
        gui_handler = GUILogHandler(self.status_text)
        gui_handler.setFormatter(
            logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        )
        
        # 添加到根日志记录器
        logging.getLogger().addHandler(gui_handler)
        logging.getLogger().setLevel(logging.INFO)
    
    def init_engine(self):
        """初始化DAP引擎"""
        try:
            self.dap_engine = get_dap_engine()
            self.status_var.set("DAP引擎已就绪")
            print("DAP引擎初始化成功")
            self.refresh_project_list()
        except Exception as e:
            self.status_var.set(f"引擎初始化失败: {str(e)}")
            print(f"DAP引擎初始化失败: {e}")
    
    def _get_storage_manager(self):
        if not self.dap_engine:
            return None
        return getattr(self.dap_engine, "storage_manager", None)
    
    def refresh_project_list(self, select_project_id: Optional[str] = None):
        if self.project_combobox is None:
            return

        storage_manager = self._get_storage_manager()
        projects: List[Dict[str, Any]] = []
        if storage_manager:
            try:
                projects = storage_manager.list_projects()
            except Exception as exc:
                logging.error("刷新项目列表失败: %s", exc)

        default_project_id = (
            getattr(storage_manager, "DEFAULT_PROJECT_ID", "default_project")
            if storage_manager
            else "default_project"
        )
        default_project_name = "默认项目"
        if not projects:
            projects = [
                {
                    "project_id": default_project_id,
                    "project_code": default_project_id,
                    "project_name": default_project_name,
                    "client_name": None,
                }
            ]

        self.project_choice_map = {}
        values: List[str] = []
        target_project = select_project_id
        if target_project is None and storage_manager:
            try:
                target_project = storage_manager.get_current_project_id()
            except Exception:
                target_project = default_project_id

        selected_display: Optional[str] = None
        for project in projects:
            name = project.get("project_name") or project.get("project_id")
            code = project.get("project_code")
            display = f"{name} ({code})" if code and code != name else name
            values.append(display)
            self.project_choice_map[display] = project
            if target_project and project.get("project_id") == target_project:
                selected_display = display

        if not values:
            display = f"{default_project_name} ({default_project_id})"
            values = [display]
            self.project_choice_map[display] = {
                "project_id": default_project_id,
                "project_code": default_project_id,
                "project_name": default_project_name,
                "client_name": None,
            }
            selected_display = display

        if not selected_display:
            selected_display = values[0]

        self.project_combobox["values"] = values
        self.project_combobox.set(selected_display)
        self.project_var.set(selected_display)

        info = self.get_selected_project_info()
        self.active_project_id = info.get("project_id") if info else None
        self.on_project_selected()

    def get_selected_project_info(self) -> Optional[Dict[str, Any]]:
        if not self.project_combobox:
            return None
        display = self.project_combobox.get()
        info = self.project_choice_map.get(display)
        if info:
            return info
        if self.project_choice_map:
            fallback_display = next(iter(self.project_choice_map))
            self.project_combobox.set(fallback_display)
            self.project_var.set(fallback_display)
            return self.project_choice_map[fallback_display]
        return None

    def on_project_selected(self, _event=None):
        info = self.get_selected_project_info()
        if info is None:
            return
        self.active_project_id = info.get("project_id")
        storage_manager = self._get_storage_manager()
        if storage_manager and self.active_project_id:
            try:
                storage_manager.set_current_project(self.active_project_id)
            except Exception as exc:
                logging.error("项目切换失败: %s", exc)

    def prompt_create_project(self):
        storage_manager = self._get_storage_manager()
        if not storage_manager:
            messagebox.showerror("错误", "请先初始化DAP引擎后再创建项目")
            return

        name = simpledialog.askstring("新建项目", "请输入项目名称：")
        if not name:
            return
        code = simpledialog.askstring("新建项目", "请输入项目编码（可选）：")
        client = simpledialog.askstring("新建项目", "请输入客户名称（可选）：")

        try:
            project_id = storage_manager.create_project(
                project_name=name.strip(),
                project_code=code.strip() if code else None,
                client_name=client.strip() if client else None,
                created_by="gui",
            )
            storage_manager.set_current_project(project_id)
            messagebox.showinfo("成功", f"项目已创建：{name.strip()}")
            self.refresh_project_list(select_project_id=project_id)
        except Exception as exc:
            logging.error("创建项目失败: %s", exc)
            messagebox.showerror("错误", f"创建项目失败: {exc}")

    def on_drop(self, event):
        """拖拽文件/文件夹处理"""
        try:
            files = self.root.tk.splitlist(event.data)
            if files:
                dropped_path = files[0]  # 取第一个路径
                
                # 验证路径存在
                if not os.path.exists(dropped_path):
                    messagebox.showerror("错误", "文件或文件夹不存在")
                    return
                
                if not os.access(dropped_path, os.R_OK):
                    messagebox.showerror("错误", "文件或文件夹无法读取")
                    return
                
                # 判断是文件还是文件夹
                if os.path.isdir(dropped_path):
                    # 文件夹处理
                    self._handle_dropped_folder(dropped_path)
                else:
                    # 文件处理
                    self._handle_dropped_file(dropped_path)
                
        except Exception as e:
            logging.error(f"拖拽处理错误: {e}")
            messagebox.showerror("错误", f"处理拖拽项目时出错: {str(e)}")
    
    def _handle_dropped_file(self, file_path):
        """处理拖拽的文件"""
        # 检查文件扩展名（包含AIS）
        valid_extensions = ['.xlsx', '.xls', '.csv', '.bak', '.sql', '.db', '.sqlite', '.mdb', '.accdb', '.ais', '.zip', '.rar']
        file_ext = os.path.splitext(file_path)[1].lower()
        
        if file_ext not in valid_extensions:
            if not messagebox.askyesno("警告", f"文件类型 {file_ext} 可能不支持，是否继续？"):
                return
        
        self.current_file = file_path
        self.process_button.config(state='normal')
        self.status_var.set(f"已选择文件: {os.path.basename(file_path)}")
    
    def _handle_dropped_folder(self, folder_path):
        """处理拖拽的文件夹"""
        # 检查文件夹是否包含支持的数据库文件
        supported_extensions = ['.db', '.sqlite', '.mdb', '.accdb', '.ais', '.bak', '.sql']
        db_files = []
        
        for root, dirs, files in os.walk(folder_path):
            for file in files:
                if any(file.lower().endswith(ext) for ext in supported_extensions):
                    db_files.append(os.path.join(root, file))
        
        if not db_files:
            messagebox.showwarning("警告", "拖拽的文件夹中没有找到支持的数据库文件")
            return
        
        # 显示找到的文件信息
        if len(db_files) > 10:
            file_info = f"找到 {len(db_files)} 个数据库文件（显示前10个）:\\n"
            for file_path in db_files[:10]:
                file_info += f"• {os.path.basename(file_path)}\\n"
            file_info += "..."
        else:
            file_info = f"找到 {len(db_files)} 个数据库文件:\\n"
            for file_path in db_files:
                file_info += f"• {os.path.basename(file_path)}\\n"
        
        if messagebox.askyesno("确认", f"{file_info}\\n是否开始批量处理？"):
            self.current_file = folder_path
            self.process_button.config(state='normal')
            self.status_var.set(f"已选择文件夹: {os.path.basename(folder_path)} ({len(db_files)} 个文件)")
    
    def select_file(self):
        """选择文件对话框"""
        try:
            file_types = [
                ("所有支持的格式", "*.xlsx;*.xls;*.csv;*.bak;*.sql;*.db;*.sqlite;*.mdb;*.accdb;*.ais;*.zip;*.rar"),
                ("Excel文件", "*.xlsx;*.xls"),
                ("CSV文件", "*.csv"),
                ("数据库文件", "*.db;*.sqlite;*.mdb;*.accdb;*.bak;*.sql"),
                ("AIS数据库", "*.ais"),
                ("压缩文件", "*.zip;*.rar"),
                ("所有文件", "*.*")
            ]
            
            file_path = filedialog.askopenfilename(
                title="选择数据文件",
                filetypes=file_types
            )
            
            if file_path:
                # 验证文件
                if not os.access(file_path, os.R_OK):
                    messagebox.showerror("错误", "文件无法读取，请检查文件权限")
                    return
                
                # 检查文件大小（限制在1GB以下）
                try:
                    file_size = os.path.getsize(file_path)
                    if file_size > 1024 * 1024 * 1024:  # 1GB
                        if not messagebox.askyesno("警告", f"文件较大（{file_size/(1024*1024*1024):.1f}GB），处理可能需要较长时间，是否继续？"):
                            return
                except Exception:
                    pass
                
                self.current_file = file_path
                self.process_button.config(state='normal')
                self.status_var.set(f"已选择文件: {os.path.basename(file_path)}")
                
        except Exception as e:
            logging.error(f"选择文件错误: {e}")
            messagebox.showerror("错误", f"选择文件时出错: {str(e)}")
    
    def select_folder(self):
        """选择文件夹对话框"""
        try:
            folder_path = filedialog.askdirectory(
                title="选择包含数据库文件的文件夹"
            )
            
            if folder_path:
                # 验证文件夹
                if not os.access(folder_path, os.R_OK):
                    messagebox.showerror("错误", "文件夹无法读取，请检查文件夹权限")
                    return
                
                # 检查文件夹是否包含支持的数据库文件
                supported_extensions = ['.db', '.sqlite', '.mdb', '.accdb', '.ais', '.bak', '.sql']
                db_files = []
                
                for root, dirs, files in os.walk(folder_path):
                    for file in files:
                        if any(file.lower().endswith(ext) for ext in supported_extensions):
                            db_files.append(os.path.join(root, file))
                
                if not db_files:
                    messagebox.showwarning("警告", "选择的文件夹中没有找到支持的数据库文件")
                    return
                
                # 显示找到的文件信息
                if len(db_files) > 10:
                    file_info = f"找到 {len(db_files)} 个数据库文件（显示前10个）:\\n"
                    for file_path in db_files[:10]:
                        file_info += f"• {os.path.basename(file_path)}\\n"
                    file_info += "..."
                else:
                    file_info = f"找到 {len(db_files)} 个数据库文件:\\n"
                    for file_path in db_files:
                        file_info += f"• {os.path.basename(file_path)}\\n"
                
                if messagebox.askyesno("确认", f"{file_info}\\n是否开始批量处理？"):
                    self.current_file = folder_path
                    self.process_button.config(state='normal')
                    self.status_var.set(f"已选择文件夹: {os.path.basename(folder_path)} ({len(db_files)} 个文件)")
                
        except Exception as e:
            logging.error(f"选择文件夹错误: {e}")
            messagebox.showerror("错误", f"选择文件夹时出错: {str(e)}")
    
    def start_processing(self):
        """开始数据处理"""
        if not self.current_file or self.processing:
            return
        
        if not self.dap_engine:
            messagebox.showerror("错误", "DAP引擎未初始化")
            return
        selected_project = self.get_selected_project_info()
        if selected_project is None:
            messagebox.showwarning("提示", "请先选择要处理的项目")
            return
        self.on_project_selected()

        # 确认开始处理
        if not messagebox.askyesno("确认", f"确定要处理文件 {os.path.basename(self.current_file)} 吗？"):
            return

        self.processing = True
        self.process_button.config(state='disabled', text="处理中...")
        self.progress_var.set(0)
        
        # 在后台线程中处理
        def process_thread():
            try:
                options = {
                    'start_api_server': self.auto_start_api.get(),
                    'auto_ai_analysis': self.auto_ai_analysis.get(),
                    'project_create_if_missing': False,
                }
                if selected_project:
                    options["project_id"] = selected_project.get("project_id")
                    if selected_project.get("project_code"):
                        options["project_code"] = selected_project.get("project_code")
                    if selected_project.get("project_name"):
                        options["project_name"] = selected_project.get("project_name")
                    if selected_project.get("client_name"):
                        options["project_client"] = selected_project.get("client_name")

                # 监控进度
                def monitor_progress():
                    while self.processing:
                        try:
                            status = self.dap_engine.get_status()
                            self.root.after(0, lambda s=status: self.update_progress(s))
                            time.sleep(1)
                        except Exception as e:
                            logging.warning(f"Progress monitoring error: {e}")
                            break
                
                # 启动进度监控
                monitor_thread = threading.Thread(target=monitor_progress, daemon=True)
                monitor_thread.start()
                
                # 执行处理
                result = self.dap_engine.process(self.current_file, options)
                
                # 更新界面
                self.root.after(0, lambda r=result: self.on_processing_complete(r))
                
            except Exception as e:
                error_result = {'success': False, 'error': str(e)}
                self.root.after(0, lambda r=error_result: self.on_processing_complete(r))
        
        # 启动处理线程
        threading.Thread(target=process_thread, daemon=True).start()
    
    def update_progress(self, status):
        """更新进度"""
        self.progress_var.set(status.get('progress', 0))
        self.status_var.set(status.get('current_step', '处理中'))
    
    def on_processing_complete(self, result):
        """处理完成回调"""
        self.processing = False
        self.process_button.config(state='normal', text="🚀 开始处理")
        
        if result['success']:
            self.progress_var.set(100)
            self.status_var.set("处理完成")

            # 显示成功消息
            success_msg = f"""
处理成功完成！

统计信息：
• 处理时间: {result['processing_time']:.2f}秒
• 处理表数: {result['statistics']['tables_processed']}
• 应用规则: {result['statistics']['rules_applied']}
• 创建视图: {result['statistics']['views_created']}
• 总记录数: {result['statistics']['total_records']}

API服务地址: {result['api_url']}
            """
            project_info = result.get("project")
            if project_info:
                line = f"\n当前项目: {project_info.get('project_name') or project_info.get('project_id')}"
                code = project_info.get("project_code")
                if code:
                    line += f" ({code})"
                client = project_info.get("client_name")
                if client:
                    line += f" · 客户: {client}"
                success_msg += line

            messagebox.showinfo("处理完成", success_msg)

            # 更新数据源下拉框
            self.update_data_sources()
            if project_info:
                self.refresh_project_list(select_project_id=project_info.get("project_id"))

        else:
            self.progress_var.set(0)
            self.status_var.set("处理失败")
            error_message = result.get('error', '处理失败')
            project_info = result.get("project")
            if project_info:
                detail = project_info.get("project_name") or project_info.get("project_id")
                if detail:
                    code = project_info.get("project_code")
                    if code:
                        detail = f"{detail} ({code})"
                    error_message = f"{error_message}\n\n项目: {detail}"
            messagebox.showerror("处理失败", error_message)
    
    def refresh_status(self):
        """刷新系统状态"""
        if not self.dap_engine:
            return
        
        try:
            system_info = self.dap_engine.get_system_info()
            status_info = self.dap_engine.get_status()
            
            status_text = f"""
=== DAP系统状态 ===
系统: {system_info.get('system', 'N/A')}
版本: {system_info.get('version', 'N/A')}
状态: {system_info.get('status', 'N/A')}

数据库路径: {system_info.get('database_path', 'N/A')}
导出目录: {system_info.get('export_directory', 'N/A')}

=== 统计信息 ===
数据表数量: {system_info.get('statistics', {}).get('total_tables', 0)}
视图数量: {system_info.get('statistics', {}).get('total_views', 0)}
可用AI客户端: {', '.join(system_info.get('statistics', {}).get('available_ai_clients', []))}

=== 当前状态 ===
正在处理: {'是' if status_info.get('processing') else '否'}
当前步骤: {status_info.get('current_step', 'N/A')}
进度: {status_info.get('progress', 0)}%
API服务: {'运行中' if status_info.get('api_server_running') else '未启动'}

最后更新: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
            """
            
            self.status_text.config(state='normal')
            self.status_text.delete('1.0', tk.END)
            self.status_text.insert('1.0', status_text)
            self.status_text.config(state='disabled')
            
        except Exception as e:
            error_text = f"获取状态失败: {str(e)}"
            self.status_text.config(state='normal')
            self.status_text.delete('1.0', tk.END)
            self.status_text.insert('1.0', error_text)
            self.status_text.config(state='disabled')
    
    def view_tables(self):
        """查看数据表"""
        self.open_data_explorer()


    def view_views(self):
        """查看数据视图"""
        self.open_data_explorer()

    def open_data_explorer(self):
        """打开统一数据浏览器。"""
        if not self.dap_engine:
            messagebox.showerror("错误", "DAP引擎尚未初始化。")
            return
        storage_manager = getattr(self.dap_engine, "storage_manager", None)
        if storage_manager is None:
            messagebox.showerror("错误", "未找到存储管理器实例。")
            return
        if not hasattr(storage_manager, "list_entities_summary"):
            messagebox.showwarning("提示", "当前存储实现不支持数据资产浏览，请切换完整模式或完成数据处理。")
            return
        selected_project = self.get_selected_project_info()
        if selected_project and hasattr(storage_manager, "set_current_project"):
            try:
                storage_manager.set_current_project(selected_project["project_id"])
            except Exception as exc:
                logging.warning("同步项目上下文失败: %s", exc)
        try:
            DataExplorer(self.root, storage_manager)
        except Exception as exc:
            logging.error("打开数据浏览器失败: %s", exc)
            messagebox.showerror("错误", f"无法打开数据浏览器: {exc}")


    def _append_command_output(self, message: str) -> None:
        """在交互输出框追加信息"""
        try:
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            self.command_output.config(state='normal')
            self.command_output.insert(tk.END, f"[{timestamp}] {message}\n")
            self.command_output.config(state='disabled')
            self.command_output.see(tk.END)
        except Exception as exc:
            print(f"追加命令输出失败: {exc}")

    def execute_data_command(self):
        """执行人工输入的处理指令"""
        command = self.command_input.get('1.0', tk.END).strip()
        if not command:
            messagebox.showerror('错误', '请输入数据处理指令')
            return

        self.command_input.delete('1.0', tk.END)

        if not self.dap_engine:
            self._append_command_output('DAP 引擎尚未初始化，无法处理指令。')
            return

        data_source = self.data_source_var.get() or None

        try:
            result = self.dap_engine.analyze_with_ai(command, data_source)
            self.last_command_result = result
            if result.get('success'):
                payload = result.get('result') or result.get('analysis') or '指令执行成功，但没有详细输出。'
                self._append_command_output(f"指令: {command}\n结果: {payload}")
            else:
                error_msg = result.get('error', '指令执行失败')
                warnings = result.get('warnings') or []
                if warnings:
                    warning_text = '; '.join(warnings)
                    error_msg += f"\n提示: {warning_text}"
                self._append_command_output(f"指令: {command}\n失败: {error_msg}")
        except Exception as exc:
            self._append_command_output(f"指令执行异常: {exc}")

    def export_audit_workpapers(self):
        """输出审计底稿"""
        if not self.dap_engine:
            messagebox.showerror('错误', 'DAP引擎未初始化')
            return

        source = self.data_source_var.get()
        if not source:
            values = self.data_source_combo['values']
            if values:
                source = values[0]
            else:
                messagebox.showerror('提示', '暂无可用数据源，请先执行数据处理。')
                return

        file_path = filedialog.asksaveasfilename(
            title='保存审计底稿',
            defaultextension='.xlsx',
            filetypes=[('Excel 工作簿', '*.xlsx'), ('CSV 文件', '*.csv'), ('所有文件', '*.*')]
        )
        if not file_path:
            return

        format_type = 'excel' if file_path.lower().endswith('.xlsx') else 'csv'

        try:
            result = self.dap_engine.export_data(source, format_type, file_path)
            if result.get('success'):
                path_hint = result.get('output_path', file_path)
                self.output_status_var.set(f'审计底稿已保存至: {path_hint}')
                self._append_command_output(f'审计底稿导出完成 → {path_hint}')
            else:
                message = result.get('error', '导出失败')
                self.output_status_var.set(f'审计底稿导出失败: {message}')
                self._append_command_output(f'审计底稿导出失败: {message}')
        except Exception as exc:
            self.output_status_var.set(f'审计底稿导出异常: {exc}')
            self._append_command_output(f'审计底稿导出异常: {exc}')

    def export_audit_report(self):
        """输出审计报告"""
        if not self.dap_engine:
            messagebox.showerror('错误', 'DAP引擎未初始化')
            return

        company = simpledialog.askstring('审计报告', '请输入被审计单位名称：', parent=self.root)
        if not company:
            return
        period = simpledialog.askstring('审计报告', '请输入审计期间（例：2024年度）：', parent=self.root)
        if not period:
            return

        file_path = filedialog.asksaveasfilename(
            title='保存审计报告',
            defaultextension='.html',
            filetypes=[('HTML 报告', '*.html'), ('PDF 报告', '*.pdf'), ('Excel 报告', '*.xlsx'), ('所有文件', '*.*')]
        )
        if not file_path:
            return

        ext = os.path.splitext(file_path)[1].lower()
        if ext == '.pdf':
            format_type = 'pdf'
        elif ext == '.xlsx':
            format_type = 'excel'
        else:
            format_type = 'html'

        try:
            result = self.dap_engine.generate_audit_report(company, period, format_type)
            if result.get('success'):
                self.output_status_var.set(f'审计报告已生成。可在 {file_path} 查看（需要完整模式导出文件）。')
                self._append_command_output(f'审计报告生成完成：单位 {company}，期间 {period}')
            else:
                message = result.get('error', '报告生成失败')
                self.output_status_var.set(f'审计报告生成失败: {message}')
                self._append_command_output(f'审计报告生成失败: {message}')
        except Exception as exc:
            self.output_status_var.set(f'审计报告生成异常: {exc}')
            self._append_command_output(f'审计报告生成异常: {exc}')

    def add_report_note(self):
        """添加审计报告附注"""
        note = simpledialog.askstring('审计报告附注', '请输入附注内容：', parent=self.root)
        if note:
            entry = {
                'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'content': note,
            }
            self.report_notes.append(entry)
            self._append_command_output(f'已记录报告附注：{note}')
            self.output_status_var.set('附注内容已添加，可在报告撰写时引用。')

    def export_data_dialog(self):
        """导出数据对话框"""
        if not self.dap_engine:
            messagebox.showerror("错误", "DAP引擎未初始化")
            return
        
        # 创建导出对话框
        dialog = tk.Toplevel(self.root)
        dialog.title("导出数据")
        dialog.geometry("400x300")
        dialog.transient(self.root)
        dialog.grab_set()
        
        # 数据源选择
        ttk.Label(dialog, text="数据源:").pack(pady=5)
        source_var = tk.StringVar()
        source_combo = ttk.Combobox(dialog, textvariable=source_var, width=50)
        
        # 获取可用的表和视图
        try:
            tables = self.dap_engine.storage_manager.get_table_list()
            views = self.dap_engine.storage_manager.get_view_list()
            
            sources = [f"raw_clean_{table['table_name']}" for table in tables]
            sources.extend([view['view_name'] for view in views])
            
            source_combo['values'] = sources
            if sources:
                source_combo.set(sources[0])
                
        except Exception as e:
            messagebox.showerror("错误", f"获取数据源失败: {str(e)}")
            dialog.destroy()
            return
        
        source_combo.pack(pady=5)
        
        # 格式选择
        ttk.Label(dialog, text="导出格式:").pack(pady=5)
        format_var = tk.StringVar(value="excel")
        formats = [("Excel", "excel"), ("CSV", "csv"), ("JSON", "json"), ("HTML", "html")]
        
        for text, value in formats:
            ttk.Radiobutton(dialog, text=text, variable=format_var, value=value).pack()
        
        # 按钮
        button_frame = ttk.Frame(dialog)
        button_frame.pack(pady=10)
        
        def do_export():
            source = source_var.get()
            format_type = format_var.get()
            
            if not source:
                messagebox.showerror("错误", "请选择数据源")
                return
            
            try:
                result = self.dap_engine.export_data(source, format_type)
                if result['success']:
                    messagebox.showinfo("成功", f"数据导出成功:\n{result['output_path']}")
                    dialog.destroy()
                else:
                    messagebox.showerror("失败", f"导出失败: {result['error']}")
            except Exception as e:
                messagebox.showerror("错误", f"导出异常: {str(e)}")
        
        ttk.Button(button_frame, text="导出", command=do_export).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="取消", command=dialog.destroy).pack(side=tk.LEFT, padx=5)
    
    def import_data_dialog(self):
        """导入数据对话框"""
        if not self.dap_engine:
            messagebox.showerror("错误", "DAP引擎未初始化")
            return
        
        # 创建导入对话框
        dialog = tk.Toplevel(self.root)
        dialog.title("导入数据文件")
        dialog.geometry("600x500")
        dialog.transient(self.root)
        dialog.grab_set()
        
        # 主框架
        main_frame = ttk.Frame(dialog, padding="10")
        main_frame.pack(fill="both", expand=True)
        
        # 文件选择部分
        file_frame = ttk.LabelFrame(main_frame, text="选择数据文件", padding="10")
        file_frame.pack(fill="x", pady=(0, 10))
        
        # 文件路径
        self.import_file_var = tk.StringVar()
        file_entry = ttk.Entry(file_frame, textvariable=self.import_file_var, width=60)
        file_entry.grid(row=0, column=0, sticky="ew", padx=(0, 5))
        
        # 浏览按钮
        browse_button = ttk.Button(
            file_frame,
            text="浏览...",
            command=self.browse_import_file
        )
        browse_button.grid(row=0, column=1)
        
        file_frame.columnconfigure(0, weight=1)
        
        # 支持格式说明
        format_info = ttk.Label(
            file_frame, 
            text="支持格式: Excel (.xlsx, .xls), CSV (.csv), JSON (.json)",
            font=('Arial', 8)
        )
        format_info.grid(row=1, column=0, columnspan=2, sticky="w", pady=(5, 0))
        
        # 导入选项
        options_frame = ttk.LabelFrame(main_frame, text="导入选项", padding="10")
        options_frame.pack(fill="x", pady=(0, 10))
        options_frame.columnconfigure(1, weight=1)
        
        # 表名
        ttk.Label(options_frame, text="表名:").grid(row=0, column=0, sticky="w", pady=2)
        self.import_table_var = tk.StringVar()
        table_entry = ttk.Entry(options_frame, textvariable=self.import_table_var)
        table_entry.grid(row=0, column=1, sticky="ew", padx=(5, 0), pady=2)
        
        # 编码选择（CSV用）
        ttk.Label(options_frame, text="编码 (CSV):").grid(row=1, column=0, sticky="w", pady=2)
        self.import_encoding_var = tk.StringVar(value="utf-8")
        encoding_combo = ttk.Combobox(
            options_frame, 
            textvariable=self.import_encoding_var,
            values=["utf-8", "gbk", "gb2312", "utf-16", "auto"],
            state="readonly"
        )
        encoding_combo.grid(row=1, column=1, sticky="ew", padx=(5, 0), pady=2)
        
        # 分隔符选择（CSV用）
        ttk.Label(options_frame, text="分隔符 (CSV):").grid(row=2, column=0, sticky="w", pady=2)
        self.import_separator_var = tk.StringVar(value=",")
        separator_combo = ttk.Combobox(
            options_frame,
            textvariable=self.import_separator_var,
            values=[",", ";", "\t", "|"],
            state="readonly"
        )
        separator_combo.grid(row=2, column=1, sticky="ew", padx=(5, 0), pady=2)
        
        # 标题行
        ttk.Label(options_frame, text="标题行:").grid(row=3, column=0, sticky="w", pady=2)
        self.import_header_var = tk.IntVar(value=0)
        header_spin = ttk.Spinbox(
            options_frame,
            from_=0,
            to=10,
            textvariable=self.import_header_var,
            width=10
        )
        header_spin.grid(row=3, column=1, sticky="w", padx=(5, 0), pady=2)
        
        # 预览区域
        preview_frame = ttk.LabelFrame(main_frame, text="数据预览", padding="10")
        preview_frame.pack(fill="both", expand=True, pady=(0, 10))
        
        # 预览按钮
        preview_button = ttk.Button(
            preview_frame,
            text="🔍 预览数据",
            command=self.preview_import_data
        )
        preview_button.pack(pady=(0, 10))
        
        # 预览文本框
        self.import_preview_text = scrolledtext.ScrolledText(
            preview_frame,
            height=8,
            state='disabled',
            wrap=tk.NONE
        )
        self.import_preview_text.pack(fill="both", expand=True)
        
        # 按钮区域
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(pady=10)
        
        # 导入按钮
        import_btn = ttk.Button(
            button_frame,
            text="📥 开始导入",
            command=lambda: self.do_import_data(dialog),
            style='Accent.TButton'
        )
        import_btn.pack(side=tk.LEFT, padx=5)
        
        # 取消按钮
        cancel_btn = ttk.Button(
            button_frame,
            text="取消",
            command=dialog.destroy
        )
        cancel_btn.pack(side=tk.LEFT, padx=5)
        
        # 查看导入历史按钮
        history_btn = ttk.Button(
            button_frame,
            text="📊 导入历史",
            command=self.show_import_history
        )
        history_btn.pack(side=tk.LEFT, padx=5)
    
    def browse_import_file(self):
        """浏览导入文件"""
        file_types = [
            ("支持的格式", "*.xlsx;*.xls;*.csv;*.json"),
            ("Excel文件", "*.xlsx;*.xls"),
            ("CSV文件", "*.csv"),
            ("JSON文件", "*.json"),
            ("所有文件", "*.*")
        ]
        
        file_path = filedialog.askopenfilename(
            title="选择要导入的数据文件",
            filetypes=file_types
        )
        
        if file_path:
            self.import_file_var.set(file_path)
            # 自动生成表名
            base_name = os.path.splitext(os.path.basename(file_path))[0]
            safe_name = "".join(c if c.isalnum() or c in '_' else '_' for c in base_name)
            self.import_table_var.set(f"imported_{safe_name}")
    
    def preview_import_data(self):
        """预览导入数据"""
        file_path = self.import_file_var.get().strip()
        if not file_path:
            messagebox.showerror("错误", "请先选择文件")
            return
        
        if not os.path.exists(file_path):
            messagebox.showerror("错误", "文件不存在")
            return
        
        try:
            # 根据文件类型预览数据
            file_ext = os.path.splitext(file_path)[1].lower()
            
            if file_ext in ['.xlsx', '.xls']:
                # Excel文件预览
                df = pd.read_excel(file_path, nrows=10)
            elif file_ext == '.csv':
                # CSV文件预览
                encoding = self.import_encoding_var.get()
                separator = self.import_separator_var.get()
                header_row = self.import_header_var.get()
                
                if encoding == 'auto':
                    import chardet
                    with open(file_path, 'rb') as f:
                        raw_data = f.read(1024)
                        encoding = chardet.detect(raw_data)['encoding']
                
                df = pd.read_csv(
                    file_path,
                    encoding=encoding,
                    sep=separator,
                    header=header_row,
                    nrows=10
                )
            elif file_ext == '.json':
                # JSON文件预览
                with open(file_path, 'r', encoding='utf-8') as f:
                    json_data = json.load(f)
                
                if isinstance(json_data, list):
                    df = pd.DataFrame(json_data[:10])
                else:
                    df = pd.DataFrame([json_data])
            else:
                messagebox.showerror("错误", f"不支持的文件格式: {file_ext}")
                return
            
            # 显示预览
            preview_text = f"文件: {os.path.basename(file_path)}\\n"
            preview_text += f"预览前10行数据:\\n\\n"
            preview_text += f"形状: {df.shape[0]} 行 x {df.shape[1]} 列\\n"
            preview_text += f"列名: {list(df.columns)}\\n\\n"
            preview_text += df.to_string(max_rows=10, max_cols=10, width=80)
            
            self.import_preview_text.config(state='normal')
            self.import_preview_text.delete('1.0', tk.END)
            self.import_preview_text.insert('1.0', preview_text)
            self.import_preview_text.config(state='disabled')
            
        except Exception as e:
            messagebox.showerror("预览失败", f"无法预览文件: {str(e)}")
    
    def do_import_data(self, dialog):
        """执行数据导入"""
        file_path = self.import_file_var.get().strip()
        table_name = self.import_table_var.get().strip()
        
        if not file_path:
            messagebox.showerror("错误", "请选择文件")
            return
        
        if not table_name:
            messagebox.showerror("错误", "请输入表名")
            return
        
        if not os.path.exists(file_path):
            messagebox.showerror("错误", "文件不存在")
            return
        
        try:
            # 构建导入选项
            options = {
                'encoding': self.import_encoding_var.get(),
                'separator': self.import_separator_var.get(),
                'header_row': self.import_header_var.get()
            }
            
            # 执行导入
            result = self.dap_engine.output_formatter.import_data_from_file(
                file_path, table_name, options
            )
            
            if result['success']:
                success_msg = f"""
数据导入成功！

表名: {result['table_name']}
记录数: {result['record_count']}
字段数: {len(result['columns'])}
文件格式: {result['format']}

字段名称: {', '.join(result['columns'][:10])}{'...' if len(result['columns']) > 10 else ''}
                """
                
                messagebox.showinfo("导入成功", success_msg)
                
                # 更新数据源下拉框
                self.update_data_sources()
                
                dialog.destroy()
            else:
                messagebox.showerror("导入失败", result['error'])
                
        except Exception as e:
            messagebox.showerror("导入异常", f"导入过程中发生错误: {str(e)}")
    
    def show_import_history(self):
        """显示导入历史"""
        if not self.dap_engine:
            messagebox.showerror("错误", "DAP引擎未初始化")
            return
        
        # 创建历史对话框
        history_dialog = tk.Toplevel(self.root)
        history_dialog.title("导入历史")
        history_dialog.geometry("800x400")
        history_dialog.transient(self.root)
        history_dialog.grab_set()
        
        # 创建表格
        columns = ('时间', '表名', '源文件', '格式', '记录数', '文件大小')
        tree = ttk.Treeview(history_dialog, columns=columns, show='headings', height=15)
        
        # 定义表头
        for col in columns:
            tree.heading(col, text=col)
            tree.column(col, width=120)
        
        # 添加滚动条
        scrollbar = ttk.Scrollbar(history_dialog, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=scrollbar.set)
        
        # 获取导入历史
        history = self.dap_engine.output_formatter.get_import_history()
        
        # 填充数据
        for item in history:
            file_size_mb = item['file_size'] / (1024*1024) if item['file_size'] else 0
            tree.insert('', tk.END, values=(
                item['import_time'][:19] if item['import_time'] else '',
                item['table_name'],
                os.path.basename(item['source_file']) if item['source_file'] else '',
                item['format_type'],
                item['record_count'],
                f"{file_size_mb:.1f}MB"
            ))
        
        # 布局
        tree.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        # 关闭按钮
        close_btn = ttk.Button(
            history_dialog,
            text="关闭",
            command=history_dialog.destroy
        )
        close_btn.pack(pady=5)

    def financial_export_dialog(self):
        """财务报表导出对话框"""
        if not self.dap_engine:
            messagebox.showerror("错误", "DAP引擎未初始化")
            return
        
        # 创建财务报表导出对话框
        dialog = tk.Toplevel(self.root)
        dialog.title("财务报表导出")
        dialog.geometry("700x600")
        dialog.resizable(True, True)
        dialog.transient(self.root)
        dialog.grab_set()
        
        # 居中显示
        dialog.update_idletasks()
        x = (dialog.winfo_screenwidth() - dialog.winfo_width()) // 2
        y = (dialog.winfo_screenheight() - dialog.winfo_height()) // 2
        dialog.geometry(f"+{x}+{y}")
        
        # 报表类型选择
        ttk.Label(dialog, text="财务报表类型:", font=('Arial', 12, 'bold')).pack(pady=10)
        
        # 报表类型变量
        report_type_var = tk.StringVar(value="balance_sheet")
        
        # 报表类型选项框
        report_frame = ttk.LabelFrame(dialog, text="选择报表类型", padding="10")
        report_frame.pack(fill="x", padx=20, pady=5)
        
        report_types = [
            ("科目余额表", "account_balance", "按科目汇总的期初余额、发生额和期末余额"),
            ("科目明细账", "account_detail", "科目的详细交易记录和明细分录"),
            ("资产负债表", "balance_sheet", "企业财务状况表：资产、负债和权益"),
            ("利润表", "income_statement", "企业经营成果：收入、费用和利润"),
            ("现金流量表", "cash_flow", "企业现金流入流出情况分析")
        ]
        
        for i, (text, value, desc) in enumerate(report_types):
            frame = ttk.Frame(report_frame)
            frame.pack(fill="x", pady=3)
            
            ttk.Radiobutton(frame, text=text, variable=report_type_var, value=value).pack(side=tk.LEFT)
            # 使用Text widget显示长描述，避免截断
            desc_text = tk.Text(frame, height=1, wrap=tk.WORD, font=('Arial', 8), 
                              foreground='gray', relief=tk.FLAT, state=tk.DISABLED,
                              bg=frame.cget('bg'))
            desc_text.pack(side=tk.LEFT, padx=(10, 0), fill="x", expand=True)
            desc_text.config(state=tk.NORMAL)
            desc_text.insert(tk.END, f"({desc})")
            desc_text.config(state=tk.DISABLED)
        
        # 期间选择
        period_frame = ttk.LabelFrame(dialog, text="报表期间", padding="10")
        period_frame.pack(fill="x", padx=20, pady=5)
        
        # 期间类型选择
        ttk.Label(period_frame, text="期间类型:").grid(row=0, column=0, sticky="w", pady=2)
        period_type_var = tk.StringVar(value="年度")
        period_type_combo = ttk.Combobox(
            period_frame, 
            textvariable=period_type_var,
            values=["年度", "期间范围"],
            state="readonly",
            width=15
        )
        period_type_combo.grid(row=0, column=1, padx=5, pady=2)
        
        # 具体期间输入
        ttk.Label(period_frame, text="具体期间:").grid(row=1, column=0, sticky="w", pady=2)
        period_var = tk.StringVar(value="2024")
        period_entry = ttk.Entry(period_frame, textvariable=period_var, width=20)
        period_entry.grid(row=1, column=1, padx=5, pady=2)
        
        # 期间示例说明
        period_example = ttk.Label(
            period_frame, 
            text="示例: 年度填写\"2024\", 期间范围填写\"2017-2025\"",
            font=('Arial', 8),
            foreground='gray'
        )
        period_example.grid(row=2, column=0, columnspan=2, sticky="w", pady=(5, 0))
        
        # 导出选项
        options_frame = ttk.LabelFrame(dialog, text="导出选项", padding="10")
        options_frame.pack(fill="x", padx=20, pady=5)
        
        # 格式选择
        ttk.Label(options_frame, text="导出格式:").grid(row=0, column=0, sticky="w")
        format_var = tk.StringVar(value="excel")
        format_combo = ttk.Combobox(options_frame, textvariable=format_var, values=["excel", "csv", "html", "pdf_report"], state="readonly")
        format_combo.grid(row=0, column=1, padx=5, sticky="w")
        
        # 包含汇总选项
        include_summary_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(options_frame, text="包含数据汇总", variable=include_summary_var).grid(row=1, column=0, columnspan=2, sticky="w", pady=5)
        
        # 包含图表选项
        include_charts_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(options_frame, text="包含分析图表", variable=include_charts_var).grid(row=2, column=0, columnspan=2, sticky="w")
        
        # 按钮区域 - 确保在底部可见
        button_frame = ttk.Frame(dialog)
        button_frame.pack(side="bottom", pady=20, padx=20, fill="x")
        
        def do_financial_export():
            report_type = report_type_var.get()
            period_type = period_type_var.get()
            period = period_var.get().strip()
            format_type = format_var.get()
            
            if not period:
                messagebox.showerror("错误", "请填写报表期间")
                return
            
            # 验证期间格式
            if period_type == "年度":
                try:
                    year = int(period)
                    if year < 1900 or year > 2100:
                        messagebox.showerror("错误", "请输入有效的年份 (1900-2100)")
                        return
                    period = f"{year}年度"
                except ValueError:
                    messagebox.showerror("错误", "年度格式错误，请输入数字年份，如：2024")
                    return
            elif period_type == "期间范围":
                if "-" not in period:
                    messagebox.showerror("错误", "期间范围格式错误，请使用格式：开始年-结束年，如：2017-2025")
                    return
                try:
                    start_year, end_year = period.split("-", 1)
                    start_year = int(start_year.strip())
                    end_year = int(end_year.strip())
                    if start_year >= end_year or start_year < 1900 or end_year > 2100:
                        messagebox.showerror("错误", "期间范围无效，请确保开始年份小于结束年份，且在1900-2100范围内")
                        return
                    period = f"{start_year}-{end_year}年期间"
                except ValueError:
                    messagebox.showerror("错误", "期间范围格式错误，请使用格式：开始年-结束年，如：2017-2025")
                    return
            
            # 预检查数据可用性
            if not self._check_financial_data_availability():
                if not messagebox.askyesno(
                    "数据检查", 
                    "系统未检测到财务数据，可能导致报表为空。\n\n是否继续生成报表？"
                ):
                    return
            
            # 在后台线程中生成报表
            def generate_report_thread():
                try:
                    # 更新UI状态
                    self.root.after(0, lambda: self._update_export_progress("正在分析数据源...", 10))
                    
                    # 验证数据源
                    data_validation = self._validate_financial_data_sources(period)
                    
                    if not data_validation['valid']:
                        result = {
                            'success': False, 
                            'error': f"数据验证失败: {data_validation['message']}"
                        }
                        self.root.after(0, lambda r=result: self._handle_export_result(r, dialog))
                        return
                    
                    self.root.after(0, lambda: self._update_export_progress("正在生成报表数据...", 30))
                    
                    # 生成报表
                    result = self._generate_financial_report(
                        report_type, 
                        period, 
                        format_type,
                        {
                            'include_summary': include_summary_var.get(),
                            'include_charts': include_charts_var.get(),
                            'data_sources': data_validation['sources']
                        }
                    )
                    
                    self.root.after(0, lambda: self._update_export_progress("正在格式化输出...", 80))
                    
                    # 处理结果
                    self.root.after(0, lambda r=result: self._handle_export_result(r, dialog))
                    
                except Exception as e:
                    error_result = {
                        'success': False, 
                        'error': f"报表生成异常: {str(e)}"
                    }
                    self.root.after(0, lambda r=error_result: self._handle_export_result(r, dialog))
            
            # 创建进度指示器
            self._create_export_progress_indicator(button_frame)
            
            # 启动后台线程
            import threading
            threading.Thread(target=generate_report_thread, daemon=True).start()

    def open_financial_viewer(self):
        """打开财务报表综合查看器"""
        if not self.dap_engine:
            messagebox.showerror("错误", "DAP引擎未初始化")
            return

        try:
            # 导入财务报表查看器模块
            from gui_financial_viewer import FinancialReportViewer

            # 检查是否有数据
            if not self._check_financial_data_availability():
                result = messagebox.askyesno(
                    "数据提示",
                    "系统中暂无数据。\n\n是否仍要打开报表查看器?\n(可以查看示例数据或等待数据导入后使用)"
                )
                if not result:
                    return

            # 创建并显示报表查看器
            viewer = FinancialReportViewer(
                master=self.root,
                storage_manager=self.dap_engine.storage_manager,
                db_path=self.dap_engine.db_path
            )

            logging.info("财务报表查看器已打开")

        except ImportError as e:
            logging.error(f"导入财务报表查看器失败: {e}")
            messagebox.showerror(
                "模块错误",
                f"无法导入财务报表查看器模块:\n{str(e)}\n\n请确保 gui_financial_viewer.py 文件存在"
            )
        except Exception as e:
            logging.error(f"打开财务报表查看器失败: {e}", exc_info=True)
            messagebox.showerror(
                "错误",
                f"打开财务报表查看器时发生错误:\n{str(e)}"
            )

    def _check_financial_data_availability(self) -> bool:
            """检查财务数据可用性"""
            try:
                if not self.dap_engine or not self.dap_engine.storage_manager:
                    return False
                
                tables = self.dap_engine.storage_manager.get_table_list()
                return len(tables) > 0
            except:
                return False
        
    def _validate_financial_data_sources(self, period: str) -> Dict[str, Any]:
            """验证财务数据源"""
            try:
                if not self.dap_engine:
                    return {'valid': False, 'message': 'DAP引擎未初始化'}
                
                tables = self.dap_engine.storage_manager.get_table_list()
                
                if not tables:
                    return {'valid': False, 'message': '未找到任何数据表'}
                
                # 检查财务相关表
                financial_tables = [
                    table for table in tables 
                    if any(keyword in table.get('table_name', '').lower() 
                          for keyword in ['ledger', 'account', 'financial', '科目', '账目'])
                ]
                
                if not financial_tables:
                    return {
                        'valid': True,  # 允许继续，但给出警告
                        'message': '未检测到明确的财务表，将尝试从所有表中提取财务数据',
                        'sources': [table['table_name'] for table in tables]
                    }
                
                return {
                    'valid': True,
                    'message': f'检测到 {len(financial_tables)} 个财务相关表',
                    'sources': [table['table_name'] for table in financial_tables]
                }
                
            except Exception as e:
                return {'valid': False, 'message': f'数据验证异常: {str(e)}'}
        
    def _create_export_progress_indicator(self, parent):
        """创建导出进度指示器"""
        if hasattr(self, 'progress_frame'):
            self.progress_frame.destroy()
        
        self.progress_frame = ttk.Frame(parent)
        self.progress_frame.pack(fill='x', pady=5)
        
        # 进度条
        self.export_progress = ttk.Progressbar(
            self.progress_frame, 
            mode='determinate', 
            maximum=100
        )
        self.export_progress.pack(fill='x', pady=2)
        
        # 状态标签
        self.export_status_label = ttk.Label(
            self.progress_frame, 
            text="准备开始...",
            font=('Arial', 8)
        )
        self.export_status_label.pack(pady=2)
        
    def _update_export_progress(self, status: str, progress: int):
        """更新导出进度"""
        if hasattr(self, 'export_progress'):
            self.export_progress['value'] = progress
        if hasattr(self, 'export_status_label'):
            self.export_status_label.config(text=status)
        
    def _handle_export_result(self, result: Dict[str, Any], dialog):
        """处理导出结果"""
        # 清理进度指示器
        if hasattr(self, 'progress_frame'):
            self.progress_frame.destroy()
        
        if result['success']:
            self._update_export_progress("导出完成！", 100)
            
            # 显示详细成功信息
            success_msg = f"""财务报表导出成功！
            
文件路径: {result['output_path']}
文件大小: {result.get('file_size', 0)} 字节
记录数量: {result.get('record_count', 0)}
生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
            
是否打开输出目录？"""
            
            if messagebox.askyesno("导出成功", success_msg):
                # 打开文件所在目录
                import subprocess
                import os
                try:
                    output_dir = os.path.dirname(result['output_path'])
                    subprocess.Popen(['explorer', output_dir])
                except Exception as e:
                    logger.warning(f"打开目录失败: {e}")
            
            dialog.destroy()
        else:
            self._update_export_progress("导出失败", 0)
            
            error_msg = f"""财务报表生成失败
            
错误信息: {result['error']}
            
可能的解决方案:
1. 检查数据是否已正确导入
2. 确认选择的期间内有数据
3. 验证数据格式是否正确
4. 查看系统日志获取详细信息"""
            
            messagebox.showerror("导出失败", error_msg)
        
        # 增强按钮显示
        ttk.Button(button_frame, text="📊 生成报表", command=do_financial_export, 
                  style='Accent.TButton', width=15).pack(side=tk.LEFT, padx=10)
        ttk.Button(button_frame, text="❌ 取消", command=dialog.destroy, 
                  width=15).pack(side=tk.LEFT, padx=10)
    
    def _generate_financial_report(self, report_type: str, period: str, format_type: str, options: dict) -> dict:
        """生成财务报表 - 增强版本"""
        try:
            logger.info(f"开始生成财务报表: {report_type}, 期间: {period}, 格式: {format_type}")
            
            # 验证参数
            if not report_type or not period or not format_type:
                return {
                    'success': False, 
                    'error': '参数不完整：报表类型、期间和格式都不能为空'
                }
            
            # 检查DAP引擎状态
            if not self.dap_engine:
                return {
                    'success': False, 
                    'error': 'DAP引擎未初始化，请重启应用程序'
                }
            
            # 根据报表类型选择生成方法
            report_methods = {
                "account_balance": self._generate_account_balance_report,
                "account_detail": self._generate_account_detail_report,
                "balance_sheet": self._generate_balance_sheet_report,
                "income_statement": self._generate_income_statement_report,
                "cash_flow": self._generate_cash_flow_report
            }
            
            if report_type not in report_methods:
                return {
                    'success': False, 
                    'error': f'不支持的报表类型: {report_type}\n支持的类型: {", ".join(report_methods.keys())}'
                }
            
            # 调用对应的生成方法
            method = report_methods[report_type]
            result = method(period, format_type, options)
            
            if result.get('success'):
                logger.info(f"财务报表生成成功: {result.get('output_path')}")
            else:
                logger.error(f"财务报表生成失败: {result.get('error')}")
            
            return result
                
        except Exception as e:
            error_msg = f"财务报表生成异常: {str(e)}"
            logger.error(error_msg)
            return {'success': False, 'error': error_msg}
    
    def _generate_account_balance_report(self, period: str, format_type: str, options: dict) -> dict:
        """生成科目余额表 - 增强版本"""
        generator = None
        try:
            from layer2.financial_reports import FinancialReportsGenerator
            
            # 检查数据库路径
            if not os.path.exists(self.dap_engine.db_path):
                return {
                    'success': False, 
                    'error': f'数据库文件不存在: {self.dap_engine.db_path}'
                }
            
            generator = FinancialReportsGenerator(self.dap_engine.db_path, self.dap_engine.export_dir)
            
            # 检查数据可用性
            data_check = generator._get_account_balance_data(period)
            if data_check.empty:
                return {
                    'success': False, 
                    'error': f'指定期间 "{period}" 内未找到科目余额数据\n\n请检查:\n1. 数据是否已正确导入\n2. 期间范围是否正确\n3. 数据表中是否包含科目信息'
                }
            
            result = generator.generate_account_balance_report(period, format_type, options)
            
            # 添加附加信息
            if result.get('success'):
                result['report_type'] = '科目余额表'
                result['period'] = period
                result['generated_at'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
            return result
            
        except ImportError:
            return {
                'success': False, 
                'error': '财务报表模块导入失败，请检查系统安装'
            }
        except Exception as e:
            return {
                'success': False, 
                'error': f'科目余额表生成失败: {str(e)}\n\n可能原因:\n1. 数据库连接失败\n2. SQL查询错误\n3. 数据格式问题\n\n请查看系统日志获取详细信息'
            }
        finally:
            if generator:
                try:
                    generator.close()
                except Exception as e:
                    logger.warning(f"关闭报表生成器失败: {e}")
    
    def _generate_account_detail_report(self, period: str, format_type: str, options: dict) -> dict:
        """生成科目明细账 - 增强版本"""
        generator = None
        try:
            from layer2.financial_reports import FinancialReportsGenerator
            generator = FinancialReportsGenerator(self.dap_engine.db_path, self.dap_engine.export_dir)
            
            # 检查数据可用性
            account_code = options.get('account_code')
            data_check = generator._get_account_detail_data(period, account_code)
            
            if data_check.empty:
                account_msg = f"科目 {account_code}" if account_code else "所有科目"
                return {
                    'success': False, 
                    'error': f'指定期间 "{period}" 内未找到 {account_msg} 的明细数据'
                }
            
            result = generator.generate_account_detail_report(period, account_code, format_type, options)
            
            if result.get('success'):
                result['report_type'] = '科目明细账'
                result['period'] = period
                result['account_code'] = account_code or '全部科目'
                result['generated_at'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
            return result
            
        except Exception as e:
            return {
                'success': False, 
                'error': f'科目明细账生成失败: {str(e)}'
            }
        finally:
            if generator:
                try:
                    generator.close()
                except Exception as e:
                    logger.warning(f"关闭报表生成器失败: {e}")
    
    def _generate_balance_sheet_report(self, period: str, format_type: str, options: dict) -> dict:
        """生成资产负债表 - 增强版本"""
        generator = None
        try:
            from layer2.financial_reports import FinancialReportsGenerator
            generator = FinancialReportsGenerator(self.dap_engine.db_path, self.dap_engine.export_dir)
            
            result = generator.generate_balance_sheet_report(period, format_type, options)
            
            if result.get('success'):
                result['report_type'] = '资产负债表'
                result['period'] = period
                result['generated_at'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
            return result
            
        except Exception as e:
            return {
                'success': False, 
                'error': f'资产负债表生成失败: {str(e)}'
            }
        finally:
            if generator:
                try:
                    generator.close()
                except Exception as e:
                    logger.warning(f"关闭报表生成器失败: {e}")
    
    def _generate_income_statement_report(self, period: str, format_type: str, options: dict) -> dict:
        """生成利润表 - 增强版本"""
        generator = None
        try:
            from layer2.financial_reports import FinancialReportsGenerator
            generator = FinancialReportsGenerator(self.dap_engine.db_path, self.dap_engine.export_dir)
            
            result = generator.generate_income_statement_report(period, format_type, options)
            
            if result.get('success'):
                result['report_type'] = '利润表'
                result['period'] = period
                result['generated_at'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
            return result
            
        except Exception as e:
            return {
                'success': False, 
                'error': f'利润表生成失败: {str(e)}'
            }
        finally:
            if generator:
                try:
                    generator.close()
                except Exception as e:
                    logger.warning(f"关闭报表生成器失败: {e}")
    
    def _generate_cash_flow_report(self, period: str, format_type: str, options: dict) -> dict:
        """生成现金流量表 - 增强版本"""
        generator = None
        try:
            from layer2.financial_reports import FinancialReportsGenerator
            generator = FinancialReportsGenerator(self.dap_engine.db_path, self.dap_engine.export_dir)
            
            result = generator.generate_cash_flow_report(period, format_type, options)
            
            if result.get('success'):
                result['report_type'] = '现金流量表'
                result['period'] = period
                result['generated_at'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
            return result
            
        except Exception as e:
            return {
                'success': False, 
                'error': f'现金流量表生成失败: {str(e)}'
            }
        finally:
            if generator:
                try:
                    generator.close()
                except Exception as e:
                    logger.warning(f"关闭报表生成器失败: {e}")
    
    
    def generate_report_dialog(self):
        """生成报告对话框"""
        if not self.dap_engine:
            messagebox.showerror("错误", "DAP引擎未初始化")
            return
        
        # 创建报告对话框
        dialog = tk.Toplevel(self.root)
        dialog.title("生成审计报告")
        dialog.geometry("350x250")
        dialog.transient(self.root)
        dialog.grab_set()
        
        # 公司名称
        ttk.Label(dialog, text="公司名称:").pack(pady=5)
        company_var = tk.StringVar(value="示例公司")
        ttk.Entry(dialog, textvariable=company_var, width=40).pack(pady=5)
        
        # 报告期间
        ttk.Label(dialog, text="报告期间:").pack(pady=5)
        period_var = tk.StringVar(value="2024年度")
        ttk.Entry(dialog, textvariable=period_var, width=40).pack(pady=5)
        
        # 报告格式
        ttk.Label(dialog, text="报告格式:").pack(pady=5)
        format_var = tk.StringVar(value="html")
        formats = [("HTML", "html"), ("Excel", "excel")]
        
        for text, value in formats:
            ttk.Radiobutton(dialog, text=text, variable=format_var, value=value).pack()
        
        # 按钮
        button_frame = ttk.Frame(dialog)
        button_frame.pack(pady=10)
        
        def do_generate():
            company = company_var.get().strip()
            period = period_var.get().strip()
            format_type = format_var.get()
            
            if not company or not period:
                messagebox.showerror("错误", "请填写公司名称和报告期间")
                return
            
            try:
                result = self.dap_engine.generate_audit_report(company, period, format_type)
                if result['success']:
                    messagebox.showinfo("成功", f"审计报告生成成功:\n{result['output_path']}")
                    dialog.destroy()
                else:
                    messagebox.showerror("失败", f"报告生成失败: {result['error']}")
            except Exception as e:
                messagebox.showerror("错误", f"报告生成异常: {str(e)}")
        
        ttk.Button(button_frame, text="生成", command=do_generate).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="取消", command=dialog.destroy).pack(side=tk.LEFT, padx=5)
    
    def update_ai_status(self):
        """更新AI客户端状态"""
        if not self.dap_engine:
            return
        
        try:
            available_clients = self.dap_engine.agent_bridge.get_available_clients()
            if available_clients:
                status_text = f"✅ 可用AI客户端: {', '.join(available_clients)}"
            else:
                status_text = "❌ 没有可用的AI客户端"
            
            self.ai_status_label.config(text=status_text)
            
        except Exception as e:
            self.ai_status_label.config(text=f"AI状态检查失败: {str(e)}")
    
    def update_data_sources(self):
        """更新数据源下拉框"""
        storage_manager = self._get_storage_manager()
        if not storage_manager:
            return

        selected_project = self.get_selected_project_info()
        if selected_project:
            try:
                storage_manager.set_current_project(selected_project["project_id"])
            except Exception as exc:
                logging.warning("同步项目上下文失败: %s", exc)

        try:
            tables = storage_manager.get_table_list()
            views = storage_manager.get_view_list()

            sources = [f"raw_clean_{table['table_name']}" for table in tables]
            sources.extend([view['view_name'] for view in views])

            self.data_source_combo['values'] = sources
            if sources and not self.data_source_var.get():
                self.data_source_combo.set(sources[0])
                
        except Exception as e:
            print(f"更新数据源失败: {e}")
    
    def start_ai_analysis(self):
        """开始AI分析"""
        data_source = self.data_source_var.get()
        prompt = self.prompt_text.get('1.0', tk.END).strip()
        
        if not prompt:
            messagebox.showerror("错误", "请输入分析要求")
            return
        
        if not self.dap_engine:
            messagebox.showerror("错误", "DAP引擎未初始化")
            return
        
        # 在后台线程中进行AI分析
        def ai_analysis_thread():
            try:
                # 更新界面状态
                self.root.after(0, lambda: self.ai_result_text.config(state='normal'))
                self.root.after(0, lambda: self.ai_result_text.delete('1.0', tk.END))
                self.root.after(0, lambda: self.ai_result_text.insert('1.0', "🤖 AI分析中，请稍候...\n"))
                self.root.after(0, lambda: self.ai_result_text.config(state='disabled'))
                
                # 执行AI分析
                result = self.dap_engine.analyze_with_ai(prompt, data_source)
                
                # 更新结果
                self.root.after(0, lambda r=result: self.update_ai_result(r))
                
            except Exception as e:
                error_result = {'success': False, 'error': str(e)}
                self.root.after(0, lambda r=error_result: self.update_ai_result(r))
        
        threading.Thread(target=ai_analysis_thread, daemon=True).start()
    
    def set_prompt_text(self, prompt):
        """设置分析提示文本"""
        try:
            self.prompt_text.delete('1.0', tk.END)
            self.prompt_text.insert('1.0', prompt)
        except Exception as e:
            logging.warning(f"设置提示文本失败: {e}")
    
    def update_ai_result(self, result):
        """更新AI分析结果"""
        self.ai_result_text.config(state='normal')
        self.ai_result_text.delete('1.0', tk.END)
        
        if result['success']:
            result_text = f"""
🤖 AI分析完成

客户端: {result.get('client', 'N/A')}
模型: {result.get('model', 'N/A')}
分析时间: {result.get('timestamp', 'N/A')}

=== 分析结果 ===
{result.get('analysis', '无分析结果')}
            """
        else:
            result_text = f"""
❌ AI分析失败

错误信息: {result.get('error', '未知错误')}

请检查：
1. AI客户端是否可用
2. 数据源是否正确
3. 网络连接是否正常
            """
        
        self.ai_result_text.insert('1.0', result_text)
        self.ai_result_text.config(state='disabled')
    
    def update_time(self):
        """更新时间显示"""
        current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        self.time_var.set(current_time)
        self.root.after(1000, self.update_time)  # 每秒更新
    
    def run(self):
        """运行界面"""
        try:
            self.root.mainloop()
        except KeyboardInterrupt:
            self.on_close()
        except Exception as e:
            print(f"界面运行错误: {e}")
        finally:
            self.on_close()
    
    def on_close(self):
        """关闭处理"""
        try:
            if self.dap_engine:
                self.dap_engine.close()
            print("DAP启动器已关闭")
        except Exception as e:
            print(f"关闭时出错: {e}")

def main():
    """主函数"""
    try:
        # 检查依赖
        import tkinterdnd2
        
        # 创建并运行界面
        launcher = DAPLauncher()
        launcher.run()
        
    except ImportError as e:
        print(f"缺少依赖库: {e}")
        print("请安装: pip install tkinterdnd2")
    except Exception as e:
        print(f"启动失败: {e}")

if __name__ == "__main__":
    main()
