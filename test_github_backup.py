#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试 GitHub 备份功能
验证所有组件是否正确配置和工作
"""

import os
import sys
from pathlib import Path

# 设置标准输出编码为UTF-8 (解决Windows GBK编码问题)
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

# 确保可以导入项目模块
sys.path.insert(0, str(Path(__file__).parent))


def test_imports():
    """测试模块导入"""
    print("测试 1/6: 模块导入...")
    try:
        from config.settings import get_config
        from layer5.github_backup_manager import GitHubBackupManager
        print("  ✓ 所有模块导入成功")
        return True
    except ImportError as e:
        print(f"  ✗ 模块导入失败: {e}")
        return False


def test_config_load():
    """测试配置加载"""
    print("\n测试 2/6: 配置加载...")
    try:
        from config.settings import get_config

        config = get_config()
        github_config = config.github_backup

        print(f"  - 备份启用: {github_config.enabled}")
        print(f"  - 目标仓库: {github_config.repository}")
        print(f"  - 分支: {github_config.branch}")
        print(f"  - 备份间隔: {github_config.interval_minutes} 分钟")
        print(f"  - 备份路径数: {len(github_config.backup_paths)}")
        print(f"  - Token 环境变量: {github_config.token_env_var}")
        print("  ✓ 配置加载成功")
        return True
    except Exception as e:
        print(f"  ✗ 配置加载失败: {e}")
        return False


def test_env_file():
    """测试 .env 文件"""
    print("\n测试 3/6: 环境文件...")

    env_file = Path(".env")
    env_example = Path(".env.example")

    if not env_example.exists():
        print("  ✗ .env.example 文件不存在")
        return False

    print("  ✓ .env.example 文件存在")

    if not env_file.exists():
        print("  ⚠ .env 文件不存在 (运行 setup_github_backup.bat 创建)")
        return False

    print("  ✓ .env 文件存在")

    # 检查关键配置
    with open(env_file, 'r', encoding='utf-8') as f:
        content = f.read()

    required_keys = [
        'DAP_GITHUB_BACKUP_ENABLED',
        'DAP_GITHUB_BACKUP_REPO',
        'DAP_GITHUB_TOKEN'
    ]

    missing_keys = []
    for key in required_keys:
        if key not in content or f"{key}=" not in content:
            missing_keys.append(key)

    if missing_keys:
        print(f"  ⚠ 缺少配置项: {', '.join(missing_keys)}")
        return False

    print("  ✓ 所有必需配置项存在")
    return True


def test_token():
    """测试 GitHub Token"""
    print("\n测试 4/6: GitHub Token...")
    try:
        from config.settings import get_config

        config = get_config()
        token_var = config.github_backup.token_env_var
        token = os.getenv(token_var)

        if not token:
            print(f"  ✗ 未找到 Token (环境变量: {token_var})")
            print("    请在 .env 文件中设置 DAP_GITHUB_TOKEN")
            return False

        if token == "your_github_token_here":
            print("  ✗ Token 未配置 (仍是占位符)")
            print("    请在 .env 文件中填入真实的 GitHub Token")
            return False

        # 简单验证 token 格式
        if not token.startswith(('ghp_', 'github_pat_')):
            print("  ⚠ Token 格式可能不正确")
            print(f"    当前: {token[:10]}...")
            print("    GitHub Token 通常以 'ghp_' 或 'github_pat_' 开头")

        print(f"  ✓ Token 已配置 ({token[:10]}...)")
        return True
    except Exception as e:
        print(f"  ✗ Token 检查失败: {e}")
        return False


def test_manager_creation():
    """测试管理器创建"""
    print("\n测试 5/6: 备份管理器创建...")
    try:
        from config.settings import get_config
        from layer5.github_backup_manager import GitHubBackupManager

        config = get_config()
        manager = GitHubBackupManager(config.github_backup)

        print("  ✓ 备份管理器创建成功")
        print(f"  - API URL 模板: {manager.API_URL_TEMPLATE}")
        print(f"  - 配置已加载: repository={config.github_backup.repository}")
        return True
    except Exception as e:
        print(f"  ✗ 管理器创建失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_dry_run():
    """测试模拟运行 (不实际上传)"""
    print("\n测试 6/6: 模拟备份流程...")
    try:
        from config.settings import get_config
        from layer5.github_backup_manager import GitHubBackupManager

        config = get_config()

        if not config.github_backup.enabled:
            print("  ⚠ GitHub 备份未启用")
            print("    在 .env 中设置 DAP_GITHUB_BACKUP_ENABLED=true")
            return False

        manager = GitHubBackupManager(config.github_backup)

        # 测试打包功能
        print("  - 测试文件打包...")
        archive_path, file_count = manager._create_backup_archive()

        if archive_path is None:
            print("  ⚠ 没有文件需要备份 (可能配置的路径不存在)")
            return False

        print(f"  ✓ 成功打包 {file_count} 个文件")
        print(f"  - 打包文件: {archive_path}")
        print(f"  - 文件大小: {archive_path.stat().st_size / 1024:.2f} KB")

        # 清理测试文件
        if archive_path.exists():
            archive_path.unlink()
            print("  ✓ 测试文件已清理")

        print("  ✓ 模拟备份流程成功")
        return True

    except Exception as e:
        print(f"  ✗ 模拟运行失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """主测试流程"""
    print("="*60)
    print("DAP GitHub 备份功能测试")
    print("="*60)
    print()

    tests = [
        ("模块导入", test_imports),
        ("配置加载", test_config_load),
        ("环境文件", test_env_file),
        ("GitHub Token", test_token),
        ("管理器创建", test_manager_creation),
        ("模拟备份", test_dry_run),
    ]

    results = []
    for name, test_func in tests:
        try:
            result = test_func()
            results.append((name, result))
        except Exception as e:
            print(f"\n[错误] {name} 测试异常: {e}")
            results.append((name, False))

    # 显示结果
    print("\n" + "="*60)
    print("测试结果汇总")
    print("="*60)

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for name, result in results:
        status = "✓ 通过" if result else "✗ 失败"
        print(f"  {status}  {name}")

    print("-"*60)
    print(f"总计: {passed}/{total} 测试通过")

    if passed == total:
        print("\n✓ 所有测试通过！")
        print("\n后续步骤:")
        print("1. 运行 setup_github_backup.bat 配置 Token (如未配置)")
        print("2. 运行 deploy_github.bat 执行完整部署")
        print("3. 运行 start_github_backup.bat 启动自动备份服务")
        return 0
    else:
        print("\n⚠ 部分测试失败，请检查上述错误信息")
        print("\n建议:")
        print("1. 确保已运行 install.bat 安装依赖")
        print("2. 运行 setup_github_backup.bat 配置环境")
        print("3. 检查 .env 文件中的配置")
        return 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n\n测试中断")
        sys.exit(1)
    except Exception as e:
        print(f"\n[严重错误] {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
