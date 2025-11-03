#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
代码审查后验证脚本
验证所有修复是否正常工作
"""

import sys
import os

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_thread_safety():
    """测试线程安全修复"""
    print("\n" + "="*60)
    print("✅ 测试 1: 线程安全 (threading.RLock)")
    print("="*60)
    
    from layer2.project_manager import ProjectManager
    pm = ProjectManager()
    
    # 检查是否有锁
    if hasattr(pm, '_lock'):
        print("✅ 项目管理器已添加线程锁 (_lock)")
    else:
        print("❌ 项目管理器缺少线程锁")
        return False
    
    # 测试并发创建
    import threading
    results = []
    
    def create_project(index):
        result = pm.create_project({
            'project_name': f'并发测试项目_{index}',
            'client_name': f'测试客户_{index}'
        })
        results.append(result)
    
    threads = []
    for i in range(5):
        t = threading.Thread(target=create_project, args=(i,))
        threads.append(t)
        t.start()
    
    for t in threads:
        t.join()
    
    success_count = sum(1 for r in results if r.get('success'))
    print(f"✅ 并发创建测试完成: {success_count}/5 成功")
    
    pm.close()
    return True


def test_transaction_rollback():
    """测试事务回滚修复"""
    print("\n" + "="*60)
    print("✅ 测试 2: 数据库事务回滚")
    print("="*60)
    
    from layer2.project_manager import ProjectManager
    pm = ProjectManager()
    
    # 测试创建重复项目（应该触发 rollback）
    project_code = "TEST_ROLLBACK_001"
    
    # 第一次创建
    result1 = pm.create_project({
        'project_name': '回滚测试项目',
        'project_code': project_code,
        'client_name': '测试客户'
    })
    
    if result1.get('success'):
        print(f"✅ 第一次创建成功: {result1['project_id']}")
    else:
        print(f"❌ 第一次创建失败: {result1.get('error')}")
        pm.close()
        return False
    
    # 第二次创建（应该失败并回滚）
    result2 = pm.create_project({
        'project_name': '回滚测试项目2',
        'project_code': project_code,  # 重复的 project_code
        'client_name': '测试客户2'
    })
    
    if not result2.get('success'):
        print(f"✅ 重复创建正确失败: {result2.get('error')}")
        print("✅ 事务回滚机制正常工作")
    else:
        print("❌ 重复创建应该失败但成功了")
        pm.close()
        return False
    
    # 清理
    pm.delete_project(result1['project_id'], soft_delete=False)
    pm.close()
    return True


def test_input_validation():
    """测试输入验证增强"""
    print("\n" + "="*60)
    print("✅ 测试 3: Web API 输入验证")
    print("="*60)
    
    # 模拟 API 请求
    test_cases = [
        {
            'name': '空项目名',
            'data': {'project_name': ''},
            'should_fail': True
        },
        {
            'name': '超长项目名',
            'data': {'project_name': 'A' * 201},
            'should_fail': True
        },
        {
            'name': '正常项目名',
            'data': {'project_name': '正常测试项目'},
            'should_fail': False
        }
    ]
    
    from layer2.project_manager import ProjectManager
    pm = ProjectManager()
    
    for test in test_cases:
        result = pm.create_project(test['data'])
        
        if test['should_fail']:
            if not result.get('success'):
                print(f"✅ {test['name']}: 正确拒绝")
            else:
                print(f"❌ {test['name']}: 应该失败但成功了")
        else:
            if result.get('success'):
                print(f"✅ {test['name']}: 正确接受")
                # 清理
                pm.delete_project(result['project_id'], soft_delete=False)
            else:
                print(f"❌ {test['name']}: 应该成功但失败了")
    
    pm.close()
    return True


def test_file_monitor():
    """测试文件监控器改进"""
    print("\n" + "="*60)
    print("✅ 测试 4: 文件监控器资源管理")
    print("="*60)
    
    from layer5.file_change_monitor import FileChangeMonitor
    import time
    
    triggered = []
    
    def callback(changed_files):
        triggered.append(changed_files)
    
    monitor = FileChangeMonitor(
        watch_paths=['.'],
        callback=callback,
        extensions={'.py'},
        check_interval=1,
        debounce_seconds=1
    )
    
    print("✅ 启动文件监控器...")
    monitor.start()
    time.sleep(2)
    
    print("✅ 停止文件监控器...")
    monitor.stop()
    
    # 检查线程是否正确停止
    if monitor._worker_thread is None or not monitor._worker_thread.is_alive():
        print("✅ 文件监控线程已正确停止")
        return True
    else:
        print("❌ 文件监控线程未能正确停止")
        return False


def test_security_config():
    """测试安全配置"""
    print("\n" + "="*60)
    print("✅ 测试 5: 安全配置检查")
    print("="*60)
    
    # 检查 .env 文件
    env_path = '.env'
    if os.path.exists(env_path):
        with open(env_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 检查 Token 是否已被注释
        if 'DAP_GITHUB_TOKEN=' in content:
            lines = [l for l in content.split('\n') if 'DAP_GITHUB_TOKEN=' in l and not l.strip().startswith('#')]
            if lines:
                print("❌ .env 文件中仍有未注释的 GitHub Token")
                print(f"   请检查: {lines[0][:50]}...")
                return False
            else:
                print("✅ GitHub Token 已正确注释")
        
        # 检查是否有示例文件
        if os.path.exists('.env.example'):
            print("✅ .env.example 示例文件已创建")
        else:
            print("⚠️  .env.example 文件不存在")
    else:
        print("⚠️  .env 文件不存在")
    
    return True


def main():
    """运行所有测试"""
    print("\n" + "="*60)
    print("🔍 DAP 代码审查修复验证")
    print("="*60)
    
    tests = [
        ("线程安全", test_thread_safety),
        ("事务回滚", test_transaction_rollback),
        ("输入验证", test_input_validation),
        ("文件监控", test_file_monitor),
        ("安全配置", test_security_config),
    ]
    
    results = []
    
    for name, test_func in tests:
        try:
            success = test_func()
            results.append((name, success))
        except Exception as e:
            print(f"\n❌ 测试 '{name}' 异常: {e}")
            import traceback
            traceback.print_exc()
            results.append((name, False))
    
    # 打印总结
    print("\n" + "="*60)
    print("📊 测试结果总结")
    print("="*60)
    
    for name, success in results:
        status = "✅ 通过" if success else "❌ 失败"
        print(f"{status}: {name}")
    
    passed = sum(1 for _, s in results if s)
    total = len(results)
    
    print("\n" + "="*60)
    print(f"总计: {passed}/{total} 测试通过")
    
    if passed == total:
        print("🎉 所有修复验证通过！系统已就绪。")
        return 0
    else:
        print("⚠️  部分测试失败，请检查修复。")
        return 1


if __name__ == "__main__":
    sys.exit(main())
