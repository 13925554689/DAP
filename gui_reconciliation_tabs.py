"""GUI Reconciliation and Adjustment Tabs - 对账与调整管理界面

This module provides GUI components for:
1. Reconciliation results display and management
2. Adjustment management with audit trail
3. Elimination template library configuration
4. Manual difference handling interface
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog, simpledialog
from typing import Any, Dict, List, Optional
import logging
import pandas as pd
from datetime import datetime
import threading

from layer2.reconciliation_engine import ReconciliationEngine
from layer2.adjustment_manager import AdjustmentManager
from layer2.elimination_template_library import EliminationTemplateLibrary
from layer2.consolidation_engine import ConsolidationEngine

logger = logging.getLogger(__name__)


class ReconciliationResultsTab:
    """对账结果展示与管理Tab"""

    def __init__(self, parent, dap_engine):
        """Initialize reconciliation results tab.

        Args:
            parent: Parent notebook widget
            dap_engine: DAP engine instance
        """
        self.dap_engine = dap_engine
        self.recon_engine: Optional[ReconciliationEngine] = None
        self.consolidation_engine: Optional[ConsolidationEngine] = None

        # Create main frame
        self.frame = ttk.Frame(parent, padding="10")
        parent.add(self.frame, text="🔄 智能对账")

        # Initialize engines
        self._init_engines()

        # Build widgets
        self._build_widgets()

    def _init_engines(self):
        """Initialize reconciliation engines."""
        try:
            db_path = self.dap_engine.storage_manager.db_path
            self.recon_engine = ReconciliationEngine(db_path)
            self.consolidation_engine = ConsolidationEngine(db_path)
            logger.info("Reconciliation engines initialized")
        except Exception as e:
            logger.error(f"Failed to initialize engines: {e}")

    def _build_widgets(self):
        """Build tab widgets."""
        # Configure grid
        self.frame.columnconfigure(0, weight=1)
        self.frame.rowconfigure(2, weight=1)
        self.frame.rowconfigure(4, weight=1)

        # Title
        title_label = ttk.Label(
            self.frame,
            text="智能对账 - 内部交易自动匹配与差异处理",
            font=("Arial", 14, "bold")
        )
        title_label.grid(row=0, column=0, pady=(0, 10), sticky=tk.W)

        # Parameters panel
        self._create_parameters_panel()

        # Statistics panel
        self._create_statistics_panel()

        # Matched transactions panel
        self._create_matched_panel()

        # Unmatched transactions panel
        self._create_unmatched_panel()

        # Actions panel
        self._create_actions_panel()

    def _create_parameters_panel(self):
        """Create reconciliation parameters panel."""
        param_frame = ttk.LabelFrame(self.frame, text="对账参数设置", padding="10")
        param_frame.grid(row=1, column=0, sticky=(tk.W, tk.E), pady=(0, 10))

        # Entity selection
        ttk.Label(param_frame, text="对账实体:").grid(row=0, column=0, padx=5, pady=5, sticky=tk.W)
        self.entity_text = ttk.Entry(param_frame, width=50)
        self.entity_text.insert(0, "选择实体ID (逗号分隔): 1,2,3,4")
        self.entity_text.grid(row=0, column=1, padx=5, pady=5, sticky=tk.W)

        # Period
        ttk.Label(param_frame, text="对账期间:").grid(row=1, column=0, padx=5, pady=5, sticky=tk.W)
        self.period_entry = ttk.Entry(param_frame, width=20)
        self.period_entry.insert(0, datetime.now().strftime("%Y-%m"))
        self.period_entry.grid(row=1, column=1, padx=5, pady=5, sticky=tk.W)

        # Scenario
        ttk.Label(param_frame, text="业务场景:").grid(row=2, column=0, padx=5, pady=5, sticky=tk.W)
        self.scenario_combo = ttk.Combobox(
            param_frame,
            values=["全部", "销售商品", "提供服务", "借款", "资产转让"],
            width=18,
            state="readonly"
        )
        self.scenario_combo.set("全部")
        self.scenario_combo.grid(row=2, column=1, padx=5, pady=5, sticky=tk.W)

        # Execute button
        ttk.Button(
            param_frame,
            text="🚀 执行对账",
            command=self._execute_reconciliation,
            style="Accent.TButton"
        ).grid(row=0, column=2, rowspan=3, padx=20, pady=5)

    def _create_statistics_panel(self):
        """Create statistics display panel."""
        stats_frame = ttk.LabelFrame(self.frame, text="对账统计", padding="10")
        stats_frame.grid(row=2, column=0, sticky=(tk.W, tk.E), pady=(0, 10))

        # Statistics labels
        self.stats_labels = {}
        stats_items = [
            ("total", "总交易笔数:", "0"),
            ("matched", "✅ 已匹配:", "0"),
            ("auto_adjusted", "🔧 自动调整:", "0"),
            ("manual_review", "⚠️  需人工审核:", "0"),
            ("unmatched_seller", "❌ 卖方未匹配:", "0"),
            ("unmatched_buyer", "❌ 买方未匹配:", "0"),
            ("total_diff", "💰 总差异金额:", "0.00")
        ]

        for idx, (key, label, default) in enumerate(stats_items):
            ttk.Label(stats_frame, text=label, font=("Arial", 10, "bold")).grid(
                row=idx // 4, column=(idx % 4) * 2, padx=10, pady=5, sticky=tk.W
            )
            value_label = ttk.Label(stats_frame, text=default, font=("Arial", 10))
            value_label.grid(row=idx // 4, column=(idx % 4) * 2 + 1, padx=10, pady=5, sticky=tk.W)
            self.stats_labels[key] = value_label

    def _create_matched_panel(self):
        """Create matched transactions display panel."""
        matched_frame = ttk.LabelFrame(self.frame, text="已匹配交易 (含自动调整)", padding="10")
        matched_frame.grid(row=3, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(0, 10))

        # Tree with scrollbar
        tree_frame = ttk.Frame(matched_frame)
        tree_frame.pack(fill=tk.BOTH, expand=True)

        y_scrollbar = ttk.Scrollbar(tree_frame)
        y_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        x_scrollbar = ttk.Scrollbar(tree_frame, orient=tk.HORIZONTAL)
        x_scrollbar.pack(side=tk.BOTTOM, fill=tk.X)

        self.matched_tree = ttk.Treeview(
            tree_frame,
            columns=("卖方ID", "买方ID", "交易类型", "卖方金额", "买方金额", "金额差异", "时间差(天)", "匹配评分", "状态"),
            show="headings",
            yscrollcommand=y_scrollbar.set,
            xscrollcommand=x_scrollbar.set
        )

        # Configure columns
        columns_config = [
            ("卖方ID", 80),
            ("买方ID", 80),
            ("交易类型", 100),
            ("卖方金额", 120),
            ("买方金额", 120),
            ("金额差异", 100),
            ("时间差(天)", 80),
            ("匹配评分", 80),
            ("状态", 100)
        ]

        for col, width in columns_config:
            self.matched_tree.heading(col, text=col)
            self.matched_tree.column(col, width=width)

        self.matched_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        y_scrollbar.config(command=self.matched_tree.yview)
        x_scrollbar.config(command=self.matched_tree.xview)

        # Context menu
        self.matched_tree.bind("<Button-3>", self._show_matched_context_menu)

    def _create_unmatched_panel(self):
        """Create unmatched transactions display panel."""
        unmatched_frame = ttk.LabelFrame(self.frame, text="未匹配交易 (需人工处理)", padding="10")
        unmatched_frame.grid(row=4, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(0, 10))

        # Tree with scrollbar
        tree_frame = ttk.Frame(unmatched_frame)
        tree_frame.pack(fill=tk.BOTH, expand=True)

        y_scrollbar = ttk.Scrollbar(tree_frame)
        y_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        x_scrollbar = ttk.Scrollbar(tree_frame, orient=tk.HORIZONTAL)
        x_scrollbar.pack(side=tk.BOTTOM, fill=tk.X)

        self.unmatched_tree = ttk.Treeview(
            tree_frame,
            columns=("交易ID", "方向", "实体ID", "对手方ID", "交易日期", "交易类型", "金额", "描述"),
            show="headings",
            yscrollcommand=y_scrollbar.set,
            xscrollcommand=x_scrollbar.set
        )

        # Configure columns
        columns_config = [
            ("交易ID", 80),
            ("方向", 60),
            ("实体ID", 80),
            ("对手方ID", 80),
            ("交易日期", 100),
            ("交易类型", 100),
            ("金额", 120),
            ("描述", 200)
        ]

        for col, width in columns_config:
            self.unmatched_tree.heading(col, text=col)
            self.unmatched_tree.column(col, width=width)

        self.unmatched_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        y_scrollbar.config(command=self.unmatched_tree.yview)
        x_scrollbar.config(command=self.unmatched_tree.xview)

        # Context menu
        self.unmatched_tree.bind("<Button-3>", self._show_unmatched_context_menu)

    def _create_actions_panel(self):
        """Create action buttons panel."""
        action_frame = ttk.Frame(self.frame)
        action_frame.grid(row=5, column=0, pady=(10, 0), sticky=tk.W)

        ttk.Button(
            action_frame,
            text="📋 生成对账报告",
            command=self._generate_report
        ).pack(side=tk.LEFT, padx=5)

        ttk.Button(
            action_frame,
            text="💾 导出已匹配交易",
            command=self._export_matched
        ).pack(side=tk.LEFT, padx=5)

        ttk.Button(
            action_frame,
            text="💾 导出未匹配交易",
            command=self._export_unmatched
        ).pack(side=tk.LEFT, padx=5)

        ttk.Button(
            action_frame,
            text="🔧 批量手动匹配",
            command=self._batch_manual_match
        ).pack(side=tk.LEFT, padx=5)

        ttk.Button(
            action_frame,
            text="⚙️ 对账规则设置",
            command=self._configure_rules
        ).pack(side=tk.LEFT, padx=5)

    def _execute_reconciliation(self):
        """Execute reconciliation."""
        if not self.recon_engine:
            messagebox.showerror("错误", "对账引擎未初始化")
            return

        # Parse entity IDs
        entity_text = self.entity_text.get().strip()
        try:
            # Extract numbers from text
            entity_ids = [int(x.strip()) for x in entity_text.split(',') if x.strip().isdigit()]
            if not entity_ids:
                messagebox.showwarning("提示", "请输入有效的实体ID")
                return
        except ValueError:
            messagebox.showerror("错误", "实体ID格式不正确")
            return

        period = self.period_entry.get().strip()
        scenario = self.scenario_combo.get()
        scenario = None if scenario == "全部" else scenario

        # Execute in thread
        def execute():
            try:
                self.recon_engine.connect()
                result = self.recon_engine.auto_reconcile_transactions(
                    entity_ids=entity_ids,
                    period=period,
                    scenario=scenario
                )
                self.recon_engine.disconnect()

                # Update UI in main thread
                self.frame.after(0, lambda: self._display_results(result))

            except Exception as e:
                logger.error(f"Reconciliation failed: {e}", exc_info=True)
                self.frame.after(0, lambda: messagebox.showerror("错误", f"对账执行失败: {e}"))

        threading.Thread(target=execute, daemon=True).start()
        messagebox.showinfo("提示", "对账任务已启动,请稍候...")

    def _display_results(self, result: Dict[str, Any]):
        """Display reconciliation results."""
        # Update statistics
        self.stats_labels["total"].config(text=str(result.get("total_transactions", 0)))
        self.stats_labels["matched"].config(text=str(result.get("matched_count", 0)))
        self.stats_labels["auto_adjusted"].config(text=str(result.get("auto_adjusted_count", 0)))
        self.stats_labels["manual_review"].config(text=str(result.get("manual_review_count", 0)))
        self.stats_labels["unmatched_seller"].config(text=str(len(result.get("unmatched_seller", []))))
        self.stats_labels["unmatched_buyer"].config(text=str(len(result.get("unmatched_buyer", []))))
        self.stats_labels["total_diff"].config(text=f"{result.get('total_difference', 0.0):,.2f}")

        # Display matched transactions
        self._display_matched_transactions(result.get("matched_pairs", []))

        # Display unmatched transactions
        unmatched = result.get("unmatched_seller", []) + result.get("unmatched_buyer", [])
        self._display_unmatched_transactions(unmatched)

        messagebox.showinfo("完成", f"对账完成!\n已匹配: {result.get('matched_count', 0)} 笔\n"
                                    f"自动调整: {result.get('auto_adjusted_count', 0)} 笔\n"
                                    f"需人工处理: {len(unmatched)} 笔")

    def _display_matched_transactions(self, matched_pairs: List[Dict[str, Any]]):
        """Display matched transaction pairs."""
        # Clear existing
        for item in self.matched_tree.get_children():
            self.matched_tree.delete(item)

        for pair in matched_pairs:
            status = "✅ 自动调整" if pair.get("auto_adjusted") else "✅ 完全匹配"
            self.matched_tree.insert(
                "",
                "end",
                values=(
                    pair.get("seller_txn_id", ""),
                    pair.get("buyer_txn_id", ""),
                    pair.get("transaction_type", ""),
                    f"{pair.get('seller_amount', 0):,.2f}",
                    f"{pair.get('buyer_amount', 0):,.2f}",
                    f"{pair.get('amount_difference', 0):,.2f}",
                    pair.get("time_difference_days", 0),
                    f"{pair.get('match_score', 0):.2f}",
                    status
                )
            )

    def _display_unmatched_transactions(self, unmatched: List[Dict[str, Any]]):
        """Display unmatched transactions."""
        # Clear existing
        for item in self.unmatched_tree.get_children():
            self.unmatched_tree.delete(item)

        for txn in unmatched:
            direction = "卖方" if txn.get("is_seller") else "买方"
            self.unmatched_tree.insert(
                "",
                "end",
                values=(
                    txn.get("transaction_id", ""),
                    direction,
                    txn.get("entity_id", ""),
                    txn.get("counterparty_id", ""),
                    txn.get("transaction_date", ""),
                    txn.get("transaction_type", ""),
                    f"{txn.get('transaction_amount', 0):,.2f}",
                    txn.get("description", "")[:50]
                )
            )

    def _show_matched_context_menu(self, event):
        """Show context menu for matched transactions."""
        menu = tk.Menu(self.frame, tearoff=0)
        menu.add_command(label="查看详情", command=self._view_matched_details)
        menu.add_command(label="取消匹配", command=self._unmatch_pair)
        menu.post(event.x_root, event.y_root)

    def _show_unmatched_context_menu(self, event):
        """Show context menu for unmatched transactions."""
        menu = tk.Menu(self.frame, tearoff=0)
        menu.add_command(label="查看详情", command=self._view_unmatched_details)
        menu.add_command(label="手动匹配...", command=self._manual_match)
        menu.add_command(label="标记为无需对账", command=self._mark_no_recon_needed)
        menu.post(event.x_root, event.y_root)

    def _view_matched_details(self):
        """View matched transaction details."""
        selection = self.matched_tree.selection()
        if not selection:
            return
        messagebox.showinfo("提示", "查看匹配详情功能开发中...")

    def _unmatch_pair(self):
        """Unmatch a transaction pair."""
        messagebox.showinfo("提示", "取消匹配功能开发中...")

    def _view_unmatched_details(self):
        """View unmatched transaction details."""
        selection = self.unmatched_tree.selection()
        if not selection:
            return
        messagebox.showinfo("提示", "查看交易详情功能开发中...")

    def _manual_match(self):
        """Manually match selected transaction."""
        selection = self.unmatched_tree.selection()
        if not selection:
            messagebox.showwarning("提示", "请先选择一笔交易")
            return
        messagebox.showinfo("提示", "手动匹配功能请使用 '批量手动匹配' 按钮")

    def _mark_no_recon_needed(self):
        """Mark transaction as no reconciliation needed."""
        messagebox.showinfo("提示", "标记功能开发中...")

    def _generate_report(self):
        """Generate reconciliation report."""
        messagebox.showinfo("提示", "生成对账报告功能开发中...")

    def _export_matched(self):
        """Export matched transactions to Excel."""
        data = []
        for item in self.matched_tree.get_children():
            values = self.matched_tree.item(item)['values']
            data.append(values)

        if not data:
            messagebox.showwarning("提示", "没有数据可导出")
            return

        filename = filedialog.asksaveasfilename(
            defaultextension=".xlsx",
            filetypes=[("Excel files", "*.xlsx")],
            initialfile=f"已匹配交易_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        )

        if filename:
            try:
                df = pd.DataFrame(data, columns=[col for col in self.matched_tree["columns"]])
                df.to_excel(filename, index=False)
                messagebox.showinfo("成功", f"已导出到: {filename}")
            except Exception as e:
                messagebox.showerror("错误", f"导出失败: {e}")

    def _export_unmatched(self):
        """Export unmatched transactions to Excel."""
        data = []
        for item in self.unmatched_tree.get_children():
            values = self.unmatched_tree.item(item)['values']
            data.append(values)

        if not data:
            messagebox.showwarning("提示", "没有数据可导出")
            return

        filename = filedialog.asksaveasfilename(
            defaultextension=".xlsx",
            filetypes=[("Excel files", "*.xlsx")],
            initialfile=f"未匹配交易_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        )

        if filename:
            try:
                df = pd.DataFrame(data, columns=[col for col in self.unmatched_tree["columns"]])
                df.to_excel(filename, index=False)
                messagebox.showinfo("成功", f"已导出到: {filename}")
            except Exception as e:
                messagebox.showerror("错误", f"导出失败: {e}")

    def _batch_manual_match(self):
        """Batch manual matching interface."""
        # Create dialog
        dialog = tk.Toplevel(self.frame)
        dialog.title("批量手动匹配")
        dialog.geometry("900x600")
        dialog.transient(self.frame)
        dialog.grab_set()

        ttk.Label(
            dialog,
            text="批量手动匹配 - 将卖方和买方交易手动配对",
            font=("Arial", 12, "bold")
        ).pack(pady=10)

        # Create two-panel layout
        paned = ttk.PanedWindow(dialog, orient=tk.HORIZONTAL)
        paned.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Left panel - Seller transactions
        left_frame = ttk.LabelFrame(paned, text="卖方交易", padding="10")
        paned.add(left_frame, weight=1)

        seller_tree = ttk.Treeview(
            left_frame,
            columns=("ID", "日期", "金额", "描述"),
            show="headings",
            height=20
        )
        for col in ["ID", "日期", "金额", "描述"]:
            seller_tree.heading(col, text=col)
        seller_tree.pack(fill=tk.BOTH, expand=True)

        # Right panel - Buyer transactions
        right_frame = ttk.LabelFrame(paned, text="买方交易", padding="10")
        paned.add(right_frame, weight=1)

        buyer_tree = ttk.Treeview(
            right_frame,
            columns=("ID", "日期", "金额", "描述"),
            show="headings",
            height=20
        )
        for col in ["ID", "日期", "金额", "描述"]:
            buyer_tree.heading(col, text=col)
        buyer_tree.pack(fill=tk.BOTH, expand=True)

        # Bottom panel - Actions
        btn_frame = ttk.Frame(dialog)
        btn_frame.pack(fill=tk.X, padx=10, pady=10)

        ttk.Button(
            btn_frame,
            text="➡️ 配对选中交易",
            command=lambda: messagebox.showinfo("提示", "手动配对功能开发中...")
        ).pack(side=tk.LEFT, padx=5)

        ttk.Button(
            btn_frame,
            text="❌ 关闭",
            command=dialog.destroy
        ).pack(side=tk.RIGHT, padx=5)

    def _configure_rules(self):
        """Configure reconciliation rules."""
        messagebox.showinfo("提示", "对账规则配置功能开发中...")


# Continue in next message due to length...
