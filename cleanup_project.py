#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DAP 项目清理脚本
自动清理临时文件、缓存文件和日志文件
"""

import os
import shutil
import glob
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def setup_logging():
    """设置日志"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )


def clean_pycache():
    """清理Python缓存文件"""
    logger.info("清理Python缓存文件...")
    
    # 查找所有 __pycache__ 目录
    for root, dirs, files in os.walk('.'):
        # 跳过虚拟环境目录
        if 'dap_env' in root:
            continue
            
        if '__pycache__' in dirs:
            pycache_path = os.path.join(root, '__pycache__')
            try:
                shutil.rmtree(pycache_path)
                logger.info(f"删除: {pycache_path}")
            except Exception as e:
                logger.error(f"删除失败: {pycache_path} - {e}")
    
    # 清理 .pyc 文件
    pyc_files = glob.glob('**/*.pyc', recursive=True)
    for pyc_file in pyc_files:
        if 'dap_env' not in pyc_file:
            try:
                os.remove(pyc_file)
                logger.info(f"删除: {pyc_file}")
            except Exception as e:
                logger.error(f"删除失败: {pyc_file} - {e}")


def clean_temp_files():
    """清理临时文件"""
    logger.info("清理临时文件...")
    
    temp_patterns = [
        '**/*.tmp',
        '**/*.temp',
        '**/*.bak',
        '**/*.swp',
        '**/*~',
        '**/.*~'
    ]
    
    for pattern in temp_patterns:
        files = glob.glob(pattern, recursive=True)
        for file_path in files:
            # 跳过虚拟环境和重要目录
            if any(skip in file_path for skip in ['dap_env', 'logs', 'data', 'exports']):
                continue
                
            try:
                os.remove(file_path)
                logger.info(f"删除临时文件: {file_path}")
            except Exception as e:
                logger.error(f"删除失败: {file_path} - {e}")


def clean_system_files():
    """清理系统生成的文件"""
    logger.info("清理系统文件...")
    
    system_patterns = [
        '**/.DS_Store',      # macOS
        '**/Thumbs.db',      # Windows
        '**/desktop.ini',    # Windows
        '**/._.DS_Store',    # macOS
    ]
    
    for pattern in system_patterns:
        files = glob.glob(pattern, recursive=True)
        for file_path in files:
            if 'dap_env' not in file_path:
                try:
                    os.remove(file_path)
                    logger.info(f"删除系统文件: {file_path}")
                except Exception as e:
                    logger.error(f"删除失败: {file_path} - {e}")


def clean_empty_directories():
    """清理空目录"""
    logger.info("清理空目录...")
    
    for root, dirs, files in os.walk('.', topdown=False):
        # 跳过重要目录
        if any(skip in root for skip in ['dap_env', '.git', '.claude']):
            continue
            
        for directory in dirs:
            dir_path = os.path.join(root, directory)
            try:
                if not os.listdir(dir_path):  # 目录为空
                    os.rmdir(dir_path)
                    logger.info(f"删除空目录: {dir_path}")
            except Exception as e:
                logger.debug(f"无法删除目录: {dir_path} - {e}")


def clean_cache_directories():
    """清理缓存目录"""
    logger.info("清理缓存目录...")
    
    cache_dirs = [
        'cache',
        'temp',
        '.cache',
        '__pycache__'
    ]
    
    for cache_dir in cache_dirs:
        if os.path.exists(cache_dir) and cache_dir != 'temp':  # 保留temp目录结构
            try:
                # 只清空内容，不删除目录
                for root, dirs, files in os.walk(cache_dir):
                    for file in files:
                        os.remove(os.path.join(root, file))
                    for dir in dirs:
                        shutil.rmtree(os.path.join(root, dir))
                logger.info(f"清空缓存目录: {cache_dir}")
            except Exception as e:
                logger.error(f"清理缓存目录失败: {cache_dir} - {e}")


def optimize_log_files():
    """优化日志文件"""
    logger.info("优化日志文件...")
    
    logs_dir = Path('logs')
    if logs_dir.exists():
        for log_file in logs_dir.glob('*.log'):
            try:
                # 如果日志文件为空或很小，删除它
                if log_file.stat().st_size < 100:  # 小于100字节
                    log_file.unlink()
                    logger.info(f"删除空日志文件: {log_file}")
                # 如果日志文件很大，截断它
                elif log_file.stat().st_size > 10 * 1024 * 1024:  # 大于10MB
                    with open(log_file, 'w') as f:
                        f.write("# 日志文件已被清理\n")
                    logger.info(f"截断大日志文件: {log_file}")
            except Exception as e:
                logger.error(f"处理日志文件失败: {log_file} - {e}")


def get_directory_size(path):
    """计算目录大小"""
    total_size = 0
    for dirpath, dirnames, filenames in os.walk(path):
        for filename in filenames:
            filepath = os.path.join(dirpath, filename)
            try:
                total_size += os.path.getsize(filepath)
            except (OSError, FileNotFoundError):
                pass
    return total_size


def generate_cleanup_report():
    """生成清理报告"""
    logger.info("生成清理报告...")
    
    report = {
        'project_size': get_directory_size('.'),
        'directories': {},
        'file_counts': {}
    }
    
    # 统计各目录大小
    for item in os.listdir('.'):
        if os.path.isdir(item):
            size = get_directory_size(item)
            report['directories'][item] = size
    
    # 统计文件类型
    file_extensions = {}
    for root, dirs, files in os.walk('.'):
        if 'dap_env' in root:
            continue
        for file in files:
            ext = Path(file).suffix.lower()
            file_extensions[ext] = file_extensions.get(ext, 0) + 1
    
    report['file_counts'] = file_extensions
    
    # 输出报告
    print("\n" + "="*50)
    print("DAP 项目清理报告")
    print("="*50)
    print(f"项目总大小: {report['project_size'] / 1024 / 1024:.1f} MB")
    
    print(f"\n目录大小:")
    for dir_name, size in sorted(report['directories'].items(), 
                                key=lambda x: x[1], reverse=True):
        size_mb = size / 1024 / 1024
        print(f"  {dir_name}: {size_mb:.1f} MB")
    
    print(f"\n文件类型统计:")
    for ext, count in sorted(report['file_counts'].items(), 
                           key=lambda x: x[1], reverse=True)[:10]:
        print(f"  {ext or '无扩展名'}: {count} 个文件")


def main():
    """主清理函数"""
    setup_logging()
    
    logger.info("开始DAP项目清理...")
    
    try:
        # 执行各种清理操作
        clean_pycache()
        clean_temp_files()
        clean_system_files()
        clean_cache_directories()
        optimize_log_files()
        clean_empty_directories()
        
        # 生成报告
        generate_cleanup_report()
        
        logger.info("项目清理完成!")
        
    except Exception as e:
        logger.error(f"清理过程中出错: {e}")
        raise


if __name__ == "__main__":
    main()