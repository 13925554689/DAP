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


class AdjustmentManagementTab:
    """调整管理Tab - 完整审计追踪"""

    def __init__(self, parent, dap_engine):
        """Initialize adjustment management tab.

        Args:
            parent: Parent notebook widget
            dap_engine: DAP engine instance
        """
        self.dap_engine = dap_engine
        self.adjustment_manager: Optional[AdjustmentManager] = None

        # Create main frame
        self.frame = ttk.Frame(parent, padding="10")
        parent.add(self.frame, text="📝 调整管理")

        # Initialize manager
        self._init_manager()

        # Build widgets
        self._build_widgets()

    def _init_manager(self):
        """Initialize adjustment manager."""
        try:
            db_path = self.dap_engine.storage_manager.db_path
            self.adjustment_manager = AdjustmentManager(db_path)
            logger.info("Adjustment manager initialized")
        except Exception as e:
            logger.error(f"Failed to initialize adjustment manager: {e}")

    def _build_widgets(self):
        """Build tab widgets."""
        # Configure grid
        self.frame.columnconfigure(0, weight=1)
        self.frame.rowconfigure(2, weight=1)

        # Title
        title_label = ttk.Label(
            self.frame,
            text="调整管理 - 完整审计追踪 & 调表不调账",
            font=("Arial", 14, "bold")
        )
        title_label.grid(row=0, column=0, pady=(0, 10), sticky=tk.W)

        # Create adjustment panel
        self._create_new_adjustment_panel()

        # Adjustment list panel
        self._create_adjustment_list_panel()

        # Detail panel
        self._create_detail_panel()

    def _create_new_adjustment_panel(self):
        """Create new adjustment creation panel."""
        new_frame = ttk.LabelFrame(self.frame, text="创建新调整", padding="10")
        new_frame.grid(row=1, column=0, sticky=(tk.W, tk.E), pady=(0, 10))

        # Adjustment type
        ttk.Label(new_frame, text="调整类型:").grid(row=0, column=0, padx=5, pady=5, sticky=tk.W)
        self.adj_type_combo = ttk.Combobox(
            new_frame,
            values=["单体调整", "公允价值调整", "合并调整", "初始化调整"],
            width=18,
            state="readonly"
        )
        self.adj_type_combo.set("单体调整")
        self.adj_type_combo.grid(row=0, column=1, padx=5, pady=5, sticky=tk.W)

        # Entity ID
        ttk.Label(new_frame, text="实体ID:").grid(row=0, column=2, padx=5, pady=5, sticky=tk.W)
        self.entity_id_entry = ttk.Entry(new_frame, width=15)
        self.entity_id_entry.grid(row=0, column=3, padx=5, pady=5, sticky=tk.W)

        # Period
        ttk.Label(new_frame, text="期间:").grid(row=0, column=4, padx=5, pady=5, sticky=tk.W)
        self.adj_period_entry = ttk.Entry(new_frame, width=15)
        self.adj_period_entry.insert(0, datetime.now().strftime("%Y-%m"))
        self.adj_period_entry.grid(row=0, column=5, padx=5, pady=5, sticky=tk.W)

        # Buttons
        ttk.Button(
            new_frame,
            text="➕ 新建调整分录",
            command=self._create_adjustment
        ).grid(row=0, column=6, padx=10, pady=5)

        ttk.Button(
            new_frame,
            text="📋 从模板创建",
            command=self._create_from_template
        ).grid(row=0, column=7, padx=5, pady=5)

    def _create_adjustment_list_panel(self):
        """Create adjustment list display panel."""
        list_frame = ttk.LabelFrame(self.frame, text="调整列表", padding="10")
        list_frame.grid(row=2, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(0, 10))

        # Tree with scrollbar
        tree_frame = ttk.Frame(list_frame)
        tree_frame.pack(fill=tk.BOTH, expand=True)

        y_scrollbar = ttk.Scrollbar(tree_frame)
        y_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        x_scrollbar = ttk.Scrollbar(tree_frame, orient=tk.HORIZONTAL)
        x_scrollbar.pack(side=tk.BOTTOM, fill=tk.X)

        self.adjustment_tree = ttk.Treeview(
            tree_frame,
            columns=("调整ID", "类型", "实体ID", "期间", "金额", "描述", "创建人", "创建时间", "状态"),
            show="headings",
            yscrollcommand=y_scrollbar.set,
            xscrollcommand=x_scrollbar.set
        )

        # Configure columns
        columns_config = [
            ("调整ID", 80),
            ("类型", 120),
            ("实体ID", 80),
            ("期间", 80),
            ("金额", 120),
            ("描述", 200),
            ("创建人", 100),
            ("创建时间", 150),
            ("状态", 80)
        ]

        for col, width in columns_config:
            self.adjustment_tree.heading(col, text=col)
            self.adjustment_tree.column(col, width=width)

        self.adjustment_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        y_scrollbar.config(command=self.adjustment_tree.yview)
        x_scrollbar.config(command=self.adjustment_tree.xview)

        # Bind selection event
        self.adjustment_tree.bind("<<TreeviewSelect>>", self._on_adjustment_selected)

        # Context menu
        self.adjustment_tree.bind("<Button-3>", self._show_adjustment_context_menu)

        # Action buttons
        btn_frame = ttk.Frame(list_frame)
        btn_frame.pack(fill=tk.X, pady=(10, 0))

        ttk.Button(btn_frame, text="🔄 刷新", command=self._refresh_adjustments).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="🔍 查看审计追踪", command=self._view_audit_trail).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="📊 调整前后对比", command=self._compare_before_after).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="↩️ 冲销调整", command=self._reverse_adjustment).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="💾 导出", command=self._export_adjustments).pack(side=tk.LEFT, padx=5)

        # Load adjustments
        self._refresh_adjustments()

    def _create_detail_panel(self):
        """Create adjustment detail display panel."""
        detail_frame = ttk.LabelFrame(self.frame, text="调整详情", padding="10")
        detail_frame.grid(row=3, column=0, sticky=(tk.W, tk.E), pady=(0, 10))

        self.detail_text = tk.Text(detail_frame, height=8, width=120, state='disabled', wrap=tk.WORD)
        self.detail_text.pack(fill=tk.BOTH, expand=True)

    def _create_adjustment(self):
        """Create new adjustment entry."""
        # Create dialog
        dialog = tk.Toplevel(self.frame)
        dialog.title("创建调整分录")
        dialog.geometry("600x500")
        dialog.transient(self.frame)
        dialog.grab_set()

        ttk.Label(
            dialog,
            text="新建调整分录",
            font=("Arial", 12, "bold")
        ).pack(pady=10)

        # Form frame
        form_frame = ttk.Frame(dialog, padding="20")
        form_frame.pack(fill=tk.BOTH, expand=True)

        fields = {}

        # Debit account
        ttk.Label(form_frame, text="借方科目代码:").grid(row=0, column=0, padx=5, pady=5, sticky=tk.W)
        fields["debit_code"] = ttk.Entry(form_frame, width=20)
        fields["debit_code"].grid(row=0, column=1, padx=5, pady=5, sticky=tk.W)

        ttk.Label(form_frame, text="借方科目名称:").grid(row=1, column=0, padx=5, pady=5, sticky=tk.W)
        fields["debit_name"] = ttk.Entry(form_frame, width=30)
        fields["debit_name"].grid(row=1, column=1, padx=5, pady=5, sticky=(tk.W, tk.E))

        # Credit account
        ttk.Label(form_frame, text="贷方科目代码:").grid(row=2, column=0, padx=5, pady=5, sticky=tk.W)
        fields["credit_code"] = ttk.Entry(form_frame, width=20)
        fields["credit_code"].grid(row=2, column=1, padx=5, pady=5, sticky=tk.W)

        ttk.Label(form_frame, text="贷方科目名称:").grid(row=3, column=0, padx=5, pady=5, sticky=tk.W)
        fields["credit_name"] = ttk.Entry(form_frame, width=30)
        fields["credit_name"].grid(row=3, column=1, padx=5, pady=5, sticky=(tk.W, tk.E))

        # Amount
        ttk.Label(form_frame, text="调整金额:").grid(row=4, column=0, padx=5, pady=5, sticky=tk.W)
        fields["amount"] = ttk.Entry(form_frame, width=20)
        fields["amount"].grid(row=4, column=1, padx=5, pady=5, sticky=tk.W)

        # Description
        ttk.Label(form_frame, text="调整说明:").grid(row=5, column=0, padx=5, pady=5, sticky=tk.NW)
        fields["description"] = tk.Text(form_frame, width=40, height=4)
        fields["description"].grid(row=5, column=1, padx=5, pady=5, sticky=(tk.W, tk.E))

        # Created by
        ttk.Label(form_frame, text="创建人:").grid(row=6, column=0, padx=5, pady=5, sticky=tk.W)
        fields["created_by"] = ttk.Entry(form_frame, width=20)
        fields["created_by"].insert(0, "系统用户")
        fields["created_by"].grid(row=6, column=1, padx=5, pady=5, sticky=tk.W)

        def save_adjustment():
            try:
                # Validate inputs
                debit_code = fields["debit_code"].get().strip()
                credit_code = fields["credit_code"].get().strip()
                amount = fields["amount"].get().strip()

                if not all([debit_code, credit_code, amount]):
                    messagebox.showerror("错误", "请填写必填字段")
                    return

                amount = float(amount)
                if amount <= 0:
                    messagebox.showerror("错误", "金额必须大于0")
                    return

                # Create adjustment
                self.adjustment_manager.connect()
                adjustment_id = self.adjustment_manager.create_adjustment(
                    adjustment_type=self.adj_type_combo.get(),
                    entity_id=int(self.entity_id_entry.get()),
                    period=self.adj_period_entry.get(),
                    entries=[{
                        "debit_account": debit_code,
                        "debit_account_name": fields["debit_name"].get().strip(),
                        "credit_account": credit_code,
                        "credit_account_name": fields["credit_name"].get().strip(),
                        "amount": amount,
                        "description": fields["description"].get("1.0", tk.END).strip()
                    }],
                    value_dimension="adjusted",
                    created_by=fields["created_by"].get().strip()
                )
                self.adjustment_manager.disconnect()

                messagebox.showinfo("成功", f"调整创建成功! ID: {adjustment_id}")
                self._refresh_adjustments()
                dialog.destroy()

            except Exception as e:
                messagebox.showerror("错误", f"创建调整失败: {e}")

        # Buttons
        btn_frame = ttk.Frame(dialog)
        btn_frame.pack(pady=20)

        ttk.Button(btn_frame, text="💾 保存", command=save_adjustment).pack(side=tk.LEFT, padx=10)
        ttk.Button(btn_frame, text="❌ 取消", command=dialog.destroy).pack(side=tk.LEFT, padx=10)

    def _create_from_template(self):
        """Create adjustment from template."""
        messagebox.showinfo("提示", "从模板创建功能开发中...")

    def _refresh_adjustments(self):
        """Refresh adjustment list."""
        # Clear existing
        for item in self.adjustment_tree.get_children():
            self.adjustment_tree.delete(item)

        if not self.adjustment_manager:
            return

        try:
            self.adjustment_manager.connect()
            cursor = self.adjustment_manager.conn.execute("""
                SELECT DISTINCT adjustment_id, adjustment_type, entity_id, period,
                       created_by, created_at, is_reversed
                FROM adjustment_history
                ORDER BY adjustment_id DESC
                LIMIT 100
            """)

            for row in cursor.fetchall():
                status = "❌ 已冲销" if row[6] else "✅ 正常"
                self.adjustment_tree.insert(
                    "",
                    "end",
                    values=(
                        row[0],  # adjustment_id
                        row[1],  # type
                        row[2],  # entity_id
                        row[3],  # period
                        "-",     # amount (would need to sum)
                        "-",     # description
                        row[4] or "未知",  # created_by
                        row[5],  # created_at
                        status
                    )
                )

            self.adjustment_manager.disconnect()

        except Exception as e:
            logger.error(f"Failed to refresh adjustments: {e}")

    def _on_adjustment_selected(self, event):
        """Handle adjustment selection."""
        selection = self.adjustment_tree.selection()
        if not selection:
            return

        values = self.adjustment_tree.item(selection[0])['values']
        adjustment_id = values[0]

        # Load and display details
        self._display_adjustment_details(adjustment_id)

    def _display_adjustment_details(self, adjustment_id: int):
        """Display adjustment details."""
        if not self.adjustment_manager:
            return

        try:
            self.adjustment_manager.connect()
            trail = self.adjustment_manager.get_adjustment_trail(adjustment_id)
            self.adjustment_manager.disconnect()

            # Format details
            self.detail_text.config(state='normal')
            self.detail_text.delete("1.0", tk.END)

            self.detail_text.insert(tk.END, f"调整ID: {adjustment_id}\n")
            self.detail_text.insert(tk.END, f"分录数量: {len(trail)}\n\n")

            for idx, entry in enumerate(trail, 1):
                self.detail_text.insert(tk.END, f"[分录 {idx}]\n")
                self.detail_text.insert(tk.END, f"  借: {entry['debit_account_name']} ({entry['debit_account']}) "
                                                f"{entry['amount']:,.2f}\n")
                self.detail_text.insert(tk.END, f"  贷: {entry['credit_account_name']} ({entry['credit_account']}) "
                                                f"{entry['amount']:,.2f}\n")
                self.detail_text.insert(tk.END, f"  说明: {entry.get('description', '-')}\n")
                self.detail_text.insert(tk.END, f"  时间: {entry['adjustment_date']}\n\n")

            self.detail_text.config(state='disabled')

        except Exception as e:
            logger.error(f"Failed to display adjustment details: {e}")

    def _show_adjustment_context_menu(self, event):
        """Show context menu for adjustments."""
        menu = tk.Menu(self.frame, tearoff=0)
        menu.add_command(label="查看审计追踪", command=self._view_audit_trail)
        menu.add_command(label="调整前后对比", command=self._compare_before_after)
        menu.add_separator()
        menu.add_command(label="冲销调整", command=self._reverse_adjustment)
        menu.add_command(label="导出PDF", command=lambda: messagebox.showinfo("提示", "导出PDF功能开发中..."))
        menu.post(event.x_root, event.y_root)

    def _view_audit_trail(self):
        """View complete audit trail for selected adjustment."""
        selection = self.adjustment_tree.selection()
        if not selection:
            messagebox.showwarning("提示", "请先选择一个调整")
            return

        values = self.adjustment_tree.item(selection[0])['values']
        adjustment_id = values[0]

        # Create dialog
        dialog = tk.Toplevel(self.frame)
        dialog.title(f"审计追踪 - 调整ID: {adjustment_id}")
        dialog.geometry("800x500")

        # Get trail
        try:
            self.adjustment_manager.connect()
            trail = self.adjustment_manager.get_adjustment_trail(adjustment_id)
            self.adjustment_manager.disconnect()

            # Display in tree
            tree = ttk.Treeview(
                dialog,
                columns=("历史ID", "调整日期", "借方", "贷方", "金额", "说明"),
                show="headings"
            )

            for col in ["历史ID", "调整日期", "借方", "贷方", "金额", "说明"]:
                tree.heading(col, text=col)

            for entry in trail:
                tree.insert(
                    "",
                    "end",
                    values=(
                        entry['history_id'],
                        entry['adjustment_date'],
                        f"{entry['debit_account_name']} ({entry['debit_account']})",
                        f"{entry['credit_account_name']} ({entry['credit_account']})",
                        f"{entry['amount']:,.2f}",
                        entry.get('description', '')[:50]
                    )
                )

            tree.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

            ttk.Button(dialog, text="关闭", command=dialog.destroy).pack(pady=10)

        except Exception as e:
            messagebox.showerror("错误", f"获取审计追踪失败: {e}")

    def _compare_before_after(self):
        """Compare data before and after adjustment."""
        selection = self.adjustment_tree.selection()
        if not selection:
            messagebox.showwarning("提示", "请先选择一个调整")
            return

        values = self.adjustment_tree.item(selection[0])['values']
        adjustment_id = values[0]
        entity_id = values[2]
        period = values[3]

        try:
            self.adjustment_manager.connect()
            comparison = self.adjustment_manager.compare_before_after(
                entity_id=entity_id,
                period=period,
                adjustment_id=adjustment_id
            )
            self.adjustment_manager.disconnect()

            # Display comparison
            message = f"调整前后对比 (调整ID: {adjustment_id})\n\n"
            message += f"调整前数据:\n{comparison.get('before', 'N/A')}\n\n"
            message += f"调整后数据:\n{comparison.get('after', 'N/A')}\n\n"
            message += f"影响金额:\n{comparison.get('impact', 'N/A')}"

            messagebox.showinfo("调整前后对比", message)

        except Exception as e:
            messagebox.showerror("错误", f"对比失败: {e}")

    def _reverse_adjustment(self):
        """Reverse selected adjustment."""
        selection = self.adjustment_tree.selection()
        if not selection:
            messagebox.showwarning("提示", "请先选择一个调整")
            return

        values = self.adjustment_tree.item(selection[0])['values']
        adjustment_id = values[0]

        if not messagebox.askyesno("确认", f"确认要冲销调整 {adjustment_id} 吗?\n将创建相反的分录。"):
            return

        reason = simpledialog.askstring("冲销原因", "请输入冲销原因:")
        if not reason:
            return

        try:
            self.adjustment_manager.connect()
            reversed_id = self.adjustment_manager.reverse_adjustment(
                adjustment_id=adjustment_id,
                reversed_by="系统用户",
                reason=reason
            )
            self.adjustment_manager.disconnect()

            messagebox.showinfo("成功", f"冲销成功!\n冲销调整ID: {reversed_id}")
            self._refresh_adjustments()

        except Exception as e:
            messagebox.showerror("错误", f"冲销失败: {e}")

    def _export_adjustments(self):
        """Export adjustments to Excel."""
        data = []
        for item in self.adjustment_tree.get_children():
            values = self.adjustment_tree.item(item)['values']
            data.append(values)

        if not data:
            messagebox.showwarning("提示", "没有数据可导出")
            return

        filename = filedialog.asksaveasfilename(
            defaultextension=".xlsx",
            filetypes=[("Excel files", "*.xlsx")],
            initialfile=f"调整列表_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        )

        if filename:
            try:
                df = pd.DataFrame(data, columns=[col for col in self.adjustment_tree["columns"]])
                df.to_excel(filename, index=False)
                messagebox.showinfo("成功", f"已导出到: {filename}")
            except Exception as e:
                messagebox.showerror("错误", f"导出失败: {e}")
