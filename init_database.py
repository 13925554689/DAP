#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
初始化DAP数据库脚本
创建必要的表结构
"""

import sqlite3
import os
from pathlib import Path

def init_database(db_path="data/dap_data.db"):
    """初始化数据库表结构"""
    # 确保数据库目录存在
    db_dir = os.path.dirname(db_path)
    if db_dir:
        os.makedirs(db_dir, exist_ok=True)
    
    # 连接数据库
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # 创建凭证表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS vouchers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            voucher_date DATE NOT NULL,
            voucher_number TEXT NOT NULL,
            description TEXT,
            amount REAL NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # 创建凭证明细表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS voucher_details (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            voucher_id INTEGER NOT NULL,
            account_code TEXT NOT NULL,
            account_name TEXT NOT NULL,
            debit_amount REAL DEFAULT 0,
            credit_amount REAL DEFAULT 0,
            description TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (voucher_id) REFERENCES vouchers (id)
        )
    ''')
    
    # 创建项目表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS projects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_code TEXT UNIQUE NOT NULL,
            project_name TEXT NOT NULL,
            client_name TEXT,
            start_date DATE,
            end_date DATE,
            status TEXT DEFAULT 'active',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # 创建审计底稿表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS audit_papers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            paper_type TEXT NOT NULL,
            period TEXT NOT NULL,
            group_name TEXT,
            file_path TEXT NOT NULL,
            file_name TEXT NOT NULL,
            uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            status TEXT DEFAULT 'active'
        )
    ''')
    
    # 创建合并底稿表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS consolidation_papers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            paper_type TEXT NOT NULL,
            group_name TEXT NOT NULL,
            period TEXT NOT NULL,
            file_path TEXT NOT NULL,
            file_name TEXT NOT NULL,
            uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            status TEXT DEFAULT 'active'
        )
    ''')
    
    # 创建科目余额表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS account_balances (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            account_code TEXT NOT NULL,
            account_name TEXT NOT NULL,
            period TEXT NOT NULL,
            opening_balance REAL DEFAULT 0,
            debit_amount REAL DEFAULT 0,
            credit_amount REAL DEFAULT 0,
            closing_balance REAL DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # 创建索引
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_voucher_date ON vouchers (voucher_date)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_voucher_number ON vouchers (voucher_number)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_account_code ON voucher_details (account_code)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_project_code ON projects (project_code)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_audit_paper_period ON audit_papers (period)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_consolidation_paper_period ON consolidation_papers (period)')
    
    # 提交更改并关闭连接
    conn.commit()
    conn.close()
    
    print(f"✅ 数据库初始化完成: {db_path}")

def insert_sample_data(db_path="data/dap_data.db"):
    """插入示例数据"""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # 插入示例凭证
    cursor.execute('''
        INSERT OR IGNORE INTO vouchers (voucher_date, voucher_number, description, amount)
        VALUES (?, ?, ?, ?)
    ''', ('2024-01-01', 'V20240101001', '收到投资款', 1000000.0))
    
    voucher_id = cursor.lastrowid or 1
    
    # 插入示例凭证明细
    cursor.execute('''
        INSERT OR IGNORE INTO voucher_details (voucher_id, account_code, account_name, debit_amount, credit_amount)
        VALUES (?, ?, ?, ?, ?)
    ''', (voucher_id, '1002', '银行存款', 1000000.0, 0.0))
    
    cursor.execute('''
        INSERT OR IGNORE INTO voucher_details (voucher_id, account_code, account_name, debit_amount, credit_amount)
        VALUES (?, ?, ?, ?, ?)
    ''', (voucher_id, '4001', '实收资本', 0.0, 1000000.0))
    
    # 插入示例科目余额
    cursor.execute('''
        INSERT OR IGNORE INTO account_balances (account_code, account_name, period, opening_balance, debit_amount, credit_amount, closing_balance)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', ('1002', '银行存款', '2024-01', 0.0, 1000000.0, 0.0, 1000000.0))
    
    cursor.execute('''
        INSERT OR IGNORE INTO account_balances (account_code, account_name, period, opening_balance, debit_amount, credit_amount, closing_balance)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', ('4001', '实收资本', '2024-01', 0.0, 0.0, 1000000.0, 1000000.0))
    
    # 插入示例项目
    cursor.execute('''
        INSERT OR IGNORE INTO projects (project_code, project_name, client_name, start_date, end_date, status)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', ('P2024001', 'ABC公司年度审计', 'ABC有限公司', '2024-01-01', '2024-12-31', 'active'))
    
    # 提交更改并关闭连接
    conn.commit()
    conn.close()
    
    print("✅ 示例数据插入完成")

if __name__ == "__main__":
    print("初始化DAP数据库...")
    init_database()
    insert_sample_data()
    print("数据库初始化完成！")