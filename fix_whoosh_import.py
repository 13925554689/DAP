#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
修复 Whoosh 导入问题的脚本
"""

import os
import sys
import fileinput

def fix_whoosh_import(file_path):
    """修复 Whoosh 导入问题"""
    if not os.path.exists(file_path):
        print(f"文件不存在: {file_path}")
        return False
    
    # 替换导入语句
    replacements = [
        ("from whoosh.index import create_index, open_index, exists_in", 
         "from whoosh.index import create_in, open_dir, exists_in"),
        ("create_index(", "create_in("),
        ("open_index(", "open_dir(")
    ]
    
    try:
        with fileinput.FileInput(file_path, inplace=True) as file:
            for line in file:
                for old, new in replacements:
                    line = line.replace(old, new)
                print(line, end='')
        
        print(f"✅ 已修复文件: {file_path}")
        return True
    except Exception as e:
        print(f"❌ 修复文件失败: {e}")
        return False

def main():
    """主函数"""
    # 需要修复的文件列表
    files_to_fix = [
        r"d:\REGKB\modules\database.py",
        r"d:\REGKB\modules\search_engine.py"
    ]
    
    fixed_count = 0
    for file_path in files_to_fix:
        if os.path.exists(file_path):
            if fix_whoosh_import(file_path):
                fixed_count += 1
        else:
            print(f"⚠️  文件不存在，跳过: {file_path}")
    
    print(f"\n📊 修复完成: {fixed_count}/{len(files_to_fix)} 个文件已修复")

if __name__ == "__main__":
    main()