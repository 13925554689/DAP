"""
DAP - 增强版财务报表查看器 GUI模块
提供类似金蝶/用友的综合财务数据查看界面
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import pandas as pd
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional, List
import logging
import os
import sys

# 添加项目路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from layer2.financial_reports import FinancialReportsGenerator

logger = logging.getLogger(__name__)


class FinancialReportViewer(tk.Toplevel):
    """财务报表综合查看器 - 类似金蝶/用友界面"""

    def __init__(self, master, storage_manager, db_path='data/dap_data.db'):
        super().__init__(master)
        self.storage_manager = storage_manager
        self.db_path = db_path
        self.report_generator = FinancialReportsGenerator(db_path)

        self.title("财务报表查看器")
        self.geometry("1200x800")
        self.transient(master)

        # 数据缓存
        self.current_period = tk.StringVar(value="2024年度")
        self.current_report_type = tk.StringVar(value="科目余额表")
        self.current_data = None

        # 可用的报表类型
        self.report_types = {
            "科目余额表": self._load_account_balance,
            "科目明细账": self._load_account_detail,
            "资产负债表": self._load_balance_sheet,
            "利润表": self._load_income_statement,
            "现金流量表": self._load_cash_flow,
            "凭证查询": self._load_vouchers
        }

        self._build_ui()
        self._load_periods()

        # 自动加载默认报表
        self.after(100, lambda: self._load_report())

    def _build_ui(self):
        """构建用户界面"""
        # 主容器
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)

        # ===== 顶部控制面板 =====
        control_frame = ttk.Frame(self, padding=10)
        control_frame.grid(row=0, column=0, sticky="ew")
        control_frame.columnconfigure(3, weight=1)

        # 报表类型选择
        ttk.Label(control_frame, text="报表类型:", font=("微软雅黑", 10)).grid(row=0, column=0, padx=5)
        report_combo = ttk.Combobox(
            control_frame,
            textvariable=self.current_report_type,
            values=list(self.report_types.keys()),
            state="readonly",
            width=15,
            font=("微软雅黑", 10)
        )
        report_combo.grid(row=0, column=1, padx=5)
        report_combo.bind("<<ComboboxSelected>>", lambda e: self._load_report())

        # 会计期间选择
        ttk.Label(control_frame, text="会计期间:", font=("微软雅黑", 10)).grid(row=0, column=2, padx=5)
        self.period_combo = ttk.Combobox(
            control_frame,
            textvariable=self.current_period,
            state="readonly",
            width=15,
            font=("微软雅黑", 10)
        )
        self.period_combo.grid(row=0, column=3, padx=5, sticky="w")
        self.period_combo.bind("<<ComboboxSelected>>", lambda e: self._load_report())

        # 按钮组
        button_frame = ttk.Frame(control_frame)
        button_frame.grid(row=0, column=4, padx=10, sticky="e")

        ttk.Button(
            button_frame,
            text="📊 刷新",
            command=self._load_report,
            width=10
        ).pack(side=tk.LEFT, padx=2)

        ttk.Button(
            button_frame,
            text="📤 导出Excel",
            command=self._export_excel,
            width=12
        ).pack(side=tk.LEFT, padx=2)

        ttk.Button(
            button_frame,
            text="📄 导出PDF",
            command=self._export_pdf,
            width=12
        ).pack(side=tk.LEFT, padx=2)

        # ===== 主显示区域 =====
        display_frame = ttk.Frame(self, padding=10)
        display_frame.grid(row=1, column=0, sticky="nsew")
        display_frame.columnconfigure(0, weight=1)
        display_frame.rowconfigure(0, weight=1)

        # 创建Notebook用于多Sheet显示
        self.notebook = ttk.Notebook(display_frame)
        self.notebook.grid(row=0, column=0, sticky="nsew")

        # ===== 状态栏 =====
        status_frame = ttk.Frame(self)
        status_frame.grid(row=2, column=0, sticky="ew")

        self.status_var = tk.StringVar(value="就绪")
        status_label = ttk.Label(
            status_frame,
            textvariable=self.status_var,
            relief=tk.SUNKEN,
            anchor=tk.W,
            padding=5
        )
        status_label.pack(fill=tk.X)

    def _load_periods(self):
        """加载可用的会计期间"""
        try:
            # 从数据库中提取年度信息
            periods = self._get_available_periods()

            if periods:
                self.period_combo['values'] = periods
                if self.current_period.get() not in periods:
                    self.current_period.set(periods[0])
            else:
                self.period_combo['values'] = ["2024年度", "2023年度", "2022年度"]

        except Exception as e:
            logger.error(f"加载会计期间失败: {e}")
            self.period_combo['values'] = ["2024年度"]

    def _get_available_periods(self) -> List[str]:
        """从数据库获取可用的会计期间"""
        try:
            entities = self.storage_manager.list_entities_summary()
            years = set()

            for entity in entities:
                # 从实体数据中提取年份
                fiscal_year = entity.get('fiscal_year')
                if fiscal_year:
                    years.add(f"{fiscal_year}年度")

            # 如果没有找到,使用默认值
            if not years:
                import sqlite3
                conn = sqlite3.connect(self.db_path)
                cursor = conn.cursor()

                # 尝试从数据表中提取年份
                cursor.execute("""
                    SELECT name FROM sqlite_master
                    WHERE type='table' AND name LIKE 'raw_clean_%'
                    LIMIT 1
                """)

                table = cursor.fetchone()
                if table:
                    # 尝试查找日期字段
                    cursor.execute(f"PRAGMA table_info('{table[0]}')")
                    columns = cursor.fetchall()

                    date_col = None
                    for col in columns:
                        col_name = col[1].lower()
                        if any(kw in col_name for kw in ['date', '日期', 'time', '时间']):
                            date_col = col[1]
                            break

                    if date_col:
                        cursor.execute(f"""
                            SELECT DISTINCT strftime('%Y', "{date_col}") as year
                            FROM "{table[0]}"
                            WHERE "{date_col}" IS NOT NULL
                            ORDER BY year DESC
                        """)

                        for row in cursor.fetchall():
                            if row[0]:
                                years.add(f"{row[0]}年度")

                conn.close()

            result = sorted(list(years), reverse=True)
            return result if result else ["2024年度", "2023年度"]

        except Exception as e:
            logger.error(f"获取会计期间失败: {e}")
            return ["2024年度"]

    def _load_report(self):
        """加载选中的报表"""
        report_type = self.current_report_type.get()
        period = self.current_period.get()

        self.status_var.set(f"正在加载 {report_type} - {period}...")
        self.update()

        try:
            # 清空现有标签页
            for tab in self.notebook.tabs():
                self.notebook.forget(tab)

            # 调用对应的加载函数
            load_func = self.report_types.get(report_type)
            if load_func:
                load_func(period)
            else:
                messagebox.showerror("错误", f"不支持的报表类型: {report_type}")

            self.status_var.set(f"已加载 {report_type} - {period}")

        except Exception as e:
            logger.error(f"加载报表失败: {e}", exc_info=True)
            messagebox.showerror("加载失败", f"加载报表时发生错误:\n{str(e)}")
            self.status_var.set("加载失败")

    def _load_account_balance(self, period: str):
        """加载科目余额表"""
        data = self.report_generator._get_account_balance_data(period)

        if data.empty:
            messagebox.showwarning("无数据", "未找到科目余额数据")
            return

        self.current_data = {"科目余额表": data}
        self._display_dataframe("科目余额表", data)

    def _load_account_detail(self, period: str):
        """加载科目明细账"""
        data = self.report_generator._get_account_detail_data(period)

        if data.empty:
            messagebox.showwarning("无数据", "未找到科目明细数据")
            return

        self.current_data = {"科目明细账": data}
        self._display_dataframe("科目明细账", data)

    def _load_balance_sheet(self, period: str):
        """加载资产负债表"""
        data_dict = self.report_generator._get_balance_sheet_data(period)

        if not data_dict or all(df.empty for df in data_dict.values()):
            messagebox.showwarning("无数据", "未找到资产负债表数据")
            return

        self.current_data = data_dict

        # 显示综合报表
        combined = self.report_generator._create_combined_balance_sheet(data_dict)
        self._display_dataframe("资产负债表", combined)

        # 显示明细分类
        for sheet_name, df in data_dict.items():
            if not df.empty:
                self._display_dataframe(sheet_name, df)

    def _load_income_statement(self, period: str):
        """加载利润表"""
        data_dict = self.report_generator._get_income_statement_data(period)

        if not data_dict or all(df.empty for df in data_dict.values()):
            messagebox.showwarning("无数据", "未找到利润表数据")
            return

        self.current_data = data_dict

        # 显示综合报表
        combined = self.report_generator._create_combined_income_statement(data_dict)
        self._display_dataframe("利润表", combined)

        # 显示明细分类
        for sheet_name, df in data_dict.items():
            if not df.empty:
                self._display_dataframe(sheet_name, df)

    def _load_cash_flow(self, period: str):
        """加载现金流量表"""
        data_dict = self.report_generator._get_cash_flow_data(period)

        if not data_dict or all(df.empty for df in data_dict.values()):
            messagebox.showwarning("无数据", "未找到现金流量表数据")
            return

        self.current_data = data_dict

        # 显示综合报表
        combined = self.report_generator._create_combined_cash_flow(data_dict)
        self._display_dataframe("现金流量表", combined)

        # 显示明细分类
        for sheet_name, df in data_dict.items():
            if not df.empty:
                self._display_dataframe(sheet_name, df)

    def _load_vouchers(self, period: str):
        """加载凭证查询"""
        try:
            # 查询所有凭证
            vouchers = self._query_all_vouchers(period)

            if vouchers.empty:
                messagebox.showwarning("无数据", "未找到凭证数据")
                return

            self.current_data = {"凭证查询": vouchers}
            self._display_dataframe(f"凭证查询 - 共{len(vouchers)}条", vouchers)

        except Exception as e:
            logger.error(f"加载凭证失败: {e}")
            messagebox.showerror("错误", f"加载凭证失败:\n{str(e)}")

    def _query_all_vouchers(self, period: str) -> pd.DataFrame:
        """查询所有凭证数据"""
        import sqlite3

        conn = sqlite3.connect(self.db_path)

        try:
            # 查找fact_vouchers表
            cursor = conn.cursor()
            cursor.execute("""
                SELECT name FROM sqlite_master
                WHERE type='table' AND name='fact_vouchers'
            """)

            if cursor.fetchone():
                # 使用fact_vouchers表
                query = """
                    SELECT
                        v.voucher_date as 日期,
                        v.voucher_number as 凭证号,
                        v.abstract as 摘要,
                        e.debit_amount as 借方金额,
                        e.credit_amount as 贷方金额,
                        a.account_code as 科目编码,
                        a.account_name as 科目名称
                    FROM fact_vouchers v
                    LEFT JOIN fact_entries e ON v.voucher_id = e.voucher_id
                    LEFT JOIN dim_accounts a ON e.account_id = a.account_id
                    ORDER BY v.voucher_date DESC, v.voucher_number
                """

                vouchers = pd.read_sql_query(query, conn)
            else:
                # 回退到raw_clean表
                cursor.execute("""
                    SELECT name FROM sqlite_master
                    WHERE type='table' AND name LIKE 'raw_clean_%'
                    LIMIT 1
                """)

                table = cursor.fetchone()
                if not table:
                    return pd.DataFrame()

                table_name = table[0]

                # 分析表结构
                table_info = self.report_generator._analyze_table_structure(table_name, conn)

                # 构建查询
                select_parts = []
                if table_info.get('date_col'):
                    select_parts.append(f'"{table_info["date_col"]}" as 日期')
                else:
                    select_parts.append("'' as 日期")

                select_parts.extend([
                    "'' as 凭证号",
                    "'' as 摘要"
                ])

                if table_info.get('account_col'):
                    select_parts.append(f'"{table_info["account_col"]}" as 科目编码')
                if table_info.get('name_col'):
                    select_parts.append(f'"{table_info["name_col"]}" as 科目名称')
                if table_info.get('amount_col'):
                    select_parts.append(f'"{table_info["amount_col"]}" as 借方金额')
                    select_parts.append("0 as 贷方金额")

                query = f"""
                    SELECT {', '.join(select_parts)}
                    FROM "{table_name}"
                    LIMIT 10000
                """

                vouchers = pd.read_sql_query(query, conn)

            return vouchers

        finally:
            conn.close()

    def _display_dataframe(self, tab_name: str, data: pd.DataFrame):
        """在Treeview中显示DataFrame"""
        # 创建标签页
        tab_frame = ttk.Frame(self.notebook)
        self.notebook.add(tab_frame, text=tab_name)

        # 配置框架
        tab_frame.columnconfigure(0, weight=1)
        tab_frame.rowconfigure(0, weight=1)

        # 创建Treeview
        tree_frame = ttk.Frame(tab_frame)
        tree_frame.grid(row=0, column=0, sticky="nsew")
        tree_frame.columnconfigure(0, weight=1)
        tree_frame.rowconfigure(0, weight=1)

        # 创建Treeview控件
        columns = list(data.columns)
        tree = ttk.Treeview(tree_frame, columns=columns, show="headings", height=25)

        # 配置列标题
        for col in columns:
            tree.heading(col, text=col, anchor=tk.CENTER)

            # 自动调整列宽
            max_width = max(
                len(str(col)) * 10,
                data[col].astype(str).str.len().max() * 8 if not data.empty else 100
            )
            tree.column(col, width=min(max_width, 200), anchor=tk.E if pd.api.types.is_numeric_dtype(data[col]) else tk.W)

        # 添加数据
        for idx, row in data.iterrows():
            values = []
            for col in columns:
                val = row[col]
                # 格式化数值
                if pd.api.types.is_numeric_dtype(data[col]) and pd.notna(val):
                    if isinstance(val, (int, float)):
                        values.append(f"{val:,.2f}" if val != int(val) else f"{int(val):,}")
                    else:
                        values.append(str(val))
                else:
                    values.append(str(val) if pd.notna(val) else "")

            tree.insert("", tk.END, values=values)

        # 添加滚动条
        v_scroll = ttk.Scrollbar(tree_frame, orient="vertical", command=tree.yview)
        h_scroll = ttk.Scrollbar(tree_frame, orient="horizontal", command=tree.xview)
        tree.configure(yscrollcommand=v_scroll.set, xscrollcommand=h_scroll.set)

        tree.grid(row=0, column=0, sticky="nsew")
        v_scroll.grid(row=0, column=1, sticky="ns")
        h_scroll.grid(row=1, column=0, sticky="ew")

        # 添加统计信息
        stats_frame = ttk.Frame(tab_frame)
        stats_frame.grid(row=1, column=0, sticky="ew", pady=5)

        stats_text = f"记录数: {len(data):,} | "

        # 添加数值列汇总
        numeric_cols = data.select_dtypes(include=['number']).columns
        for col in numeric_cols[:3]:  # 只显示前3个数值列的汇总
            total = data[col].sum()
            stats_text += f"{col}合计: {total:,.2f} | "

        ttk.Label(stats_frame, text=stats_text.rstrip(" | "), foreground="blue").pack(side=tk.LEFT, padx=10)

    def _export_excel(self):
        """导出为Excel"""
        if not self.current_data:
            messagebox.showwarning("无数据", "没有可导出的数据")
            return

        try:
            report_type = self.current_report_type.get()
            period = self.current_period.get()
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

            filename = filedialog.asksaveasfilename(
                title="保存Excel文件",
                defaultextension=".xlsx",
                initialfile=f"{report_type}_{period}_{timestamp}.xlsx",
                filetypes=[("Excel文件", "*.xlsx"), ("所有文件", "*.*")]
            )

            if not filename:
                return

            # 导出到Excel
            with pd.ExcelWriter(filename, engine='openpyxl') as writer:
                for sheet_name, df in self.current_data.items():
                    df.to_excel(writer, sheet_name=sheet_name[:31], index=False)  # Excel sheet name限制31字符

            messagebox.showinfo("导出成功", f"报表已导出到:\n{filename}")
            self.status_var.set(f"已导出: {filename}")

        except Exception as e:
            logger.error(f"导出Excel失败: {e}")
            messagebox.showerror("导出失败", f"导出Excel时发生错误:\n{str(e)}")

    def _export_pdf(self):
        """导出为PDF"""
        messagebox.showinfo("功能开发中", "PDF导出功能正在开发中,请使用Excel导出")


def show_financial_viewer(parent, storage_manager, db_path='data/dap_data.db'):
    """显示财务报表查看器"""
    viewer = FinancialReportViewer(parent, storage_manager, db_path)
    viewer.grab_set()
    parent.wait_window(viewer)


if __name__ == "__main__":
    # 测试模块
    root = tk.Tk()
    root.withdraw()

    # 需要提供storage_manager实例
    from layer1.storage_manager import StorageManager
    storage_manager = StorageManager('data/dap_data.db')

    show_financial_viewer(root, storage_manager)
