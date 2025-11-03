import sqlite3
import os

def check_database():
    db_path = 'data/dap_data.db'
    if not os.path.exists(db_path):
        print(f"数据库文件不存在: {db_path}")
        return
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = cursor.fetchall()
        print('数据库表结构:')
        for table in tables:
            print(f'  - {table[0]}')
        conn.close()
        print('\n✅ 数据库连接正常')
    except Exception as e:
        print(f'❌ 数据库连接失败: {e}')

if __name__ == "__main__":
    check_database()