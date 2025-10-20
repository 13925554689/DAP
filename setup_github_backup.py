#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DAP GitHub 备份一键配置工具
交互式配置 GitHub 自动备份功能
"""

import os
import sys
from pathlib import Path


def main():
    """主配置流程"""
    print("="*60)
    print("DAP GitHub 自动备份配置向导")
    print("="*60)
    print()

    # 检查 .env 文件
    env_file = Path(".env")
    env_example = Path(".env.example")

    if not env_example.exists():
        print("[错误] 未找到 .env.example 文件")
        return 1

    # 读取现有配置
    existing_config = {}
    if env_file.exists():
        print("检测到现有 .env 文件，读取现有配置...")
        with open(env_file, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    existing_config[key.strip()] = value.strip()
        print()

    print("请按照提示输入配置信息 (按 Enter 使用默认值):")
    print()

    # GitHub Token
    print("-"*60)
    print("1. GitHub Personal Access Token")
    print("   获取方式：")
    print("   1) 访问 https://github.com/settings/tokens")
    print("   2) 点击 'Generate new token (classic)'")
    print("   3) 选择权限: repo (完整仓库访问)")
    print("   4) 生成并复制 token")
    print()
    token = input("请输入您的 GitHub Token: ").strip()
    if not token:
        print("[错误] Token 不能为空")
        return 1

    # GitHub 仓库
    print()
    print("-"*60)
    print("2. GitHub 仓库")
    print("   格式: username/repository")
    print("   例如: 13925554689/DAP")
    print()
    default_repo = existing_config.get('DAP_GITHUB_BACKUP_REPO', '13925554689/DAP')
    repo = input(f"请输入仓库名称 [{default_repo}]: ").strip() or default_repo

    # 分支
    print()
    print("-"*60)
    print("3. 目标分支")
    default_branch = existing_config.get('DAP_GITHUB_BACKUP_BRANCH', 'main')
    branch = input(f"请输入分支名称 [{default_branch}]: ").strip() or default_branch

    # 备份间隔
    print()
    print("-"*60)
    print("4. 备份间隔")
    default_interval = existing_config.get('DAP_GITHUB_BACKUP_INTERVAL_MINUTES', '120')
    interval = input(f"请输入备份间隔(分钟) [{default_interval}]: ").strip() or default_interval

    # 备份路径
    print()
    print("-"*60)
    print("5. 备份路径")
    print("   多个路径用逗号分隔")
    default_paths = existing_config.get('DAP_GITHUB_BACKUP_PATHS',
                                         'data,exports,config,layer1,layer2,layer3,layer4,layer5,main_engine.py,dap_launcher.py')
    paths = input(f"请输入备份路径 [{default_paths}]: ").strip() or default_paths

    # 生成 .env 文件
    print()
    print("-"*60)
    print("生成配置文件...")

    # 读取模板
    with open(env_example, 'r', encoding='utf-8') as f:
        template = f.read()

    # 替换配置
    config_dict = {
        'DAP_GITHUB_BACKUP_ENABLED': 'true',
        'DAP_GITHUB_BACKUP_REPO': repo,
        'DAP_GITHUB_BACKUP_BRANCH': branch,
        'DAP_GITHUB_TOKEN': token,
        'DAP_GITHUB_BACKUP_INTERVAL_MINUTES': interval,
        'DAP_GITHUB_BACKUP_PATHS': paths,
    }

    # 保留其他现有配置
    for key, value in existing_config.items():
        if key not in config_dict and not key.startswith('DAP_GITHUB'):
            config_dict[key] = value

    # 写入 .env
    lines = []
    for line in template.split('\n'):
        if line.strip() and not line.strip().startswith('#') and '=' in line:
            key = line.split('=')[0].strip()
            if key in config_dict:
                lines.append(f"{key}={config_dict[key]}")
            else:
                lines.append(line)
        else:
            lines.append(line)

    with open(env_file, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))

    print("✓ 配置文件已生成: .env")
    print()

    # 测试配置
    print("-"*60)
    print("测试配置...")
    print()

    try:
        # 设置环境变量
        os.environ.update(config_dict)

        # 测试导入
        from config.settings import get_config
        from layer5.github_backup_manager import GitHubBackupManager

        cfg = get_config()

        print(f"✓ 备份状态: {'启用' if cfg.github_backup.enabled else '禁用'}")
        print(f"✓ 目标仓库: {cfg.github_backup.repository}")
        print(f"✓ 分支: {cfg.github_backup.branch}")
        print(f"✓ 备份间隔: {cfg.github_backup.interval_minutes} 分钟")
        print(f"✓ 备份路径: {len(cfg.github_backup.backup_paths)} 个路径")
        print()

        # 询问是否立即测试备份
        print("-"*60)
        test = input("是否立即测试备份? (y/n) [y]: ").strip().lower()

        if test != 'n':
            print()
            print("正在执行测试备份...")
            manager = GitHubBackupManager(cfg.github_backup)
            success = manager.run_backup('test')

            if success:
                print()
                print("✓ 备份测试成功!")
                print(f"  请访问 https://github.com/{repo}/tree/{branch}/backups 查看备份文件")
            else:
                print()
                print("✗ 备份测试失败")
                status = manager.get_status()
                print(f"  失败原因: {status.get('message', '未知')}")
                print()
                print("  请检查:")
                print("  1. GitHub Token 是否正确")
                print("  2. Token 是否有 repo 权限")
                print("  3. 仓库名称是否正确")
                print("  4. 网络连接是否正常")

    except Exception as e:
        print(f"✗ 配置测试失败: {e}")
        return 1

    # 完成
    print()
    print("="*60)
    print("配置完成!")
    print("="*60)
    print()
    print("后续步骤:")
    print("1. 运行 start_github_backup.bat 启动自动备份服务")
    print("2. 或运行 deploy_github.bat 查看完整部署选项")
    print(f"3. 访问 https://github.com/{repo} 查看您的备份")
    print()

    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n\n操作已取消")
        sys.exit(1)
    except Exception as e:
        print(f"\n[错误] {e}")
        sys.exit(1)
