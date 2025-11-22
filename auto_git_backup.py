"""
DAP v2.0 - 自动Git备份与GitHub上传守护进程
监控代码变更,自动提交并推送到GitHub

功能:
1. 监控dap_v2/目录的所有代码变更
2. 检测到变更后自动git add + commit
3. 自动推送到GitHub远程仓库
4. 失败重试机制
"""

import os
import time
import subprocess
from datetime import datetime
from pathlib import Path
import hashlib
import json

class GitAutoBackup:
    def __init__(self, watch_dir="dap_v2", check_interval=30):
        self.watch_dir = Path(watch_dir)
        self.check_interval = check_interval
        self.last_hash = None
        self.state_file = Path(".git_backup_state.json")
        self.load_state()

    def load_state(self):
        """加载上次备份状态"""
        if self.state_file.exists():
            with open(self.state_file, 'r') as f:
                state = json.load(f)
                self.last_hash = state.get('last_hash')

    def save_state(self, hash_value):
        """保存备份状态"""
        with open(self.state_file, 'w') as f:
            json.dump({
                'last_hash': hash_value,
                'last_backup': datetime.now().isoformat()
            }, f)

    def get_directory_hash(self):
        """计算目录内容hash值"""
        hash_md5 = hashlib.md5()

        for file_path in sorted(self.watch_dir.rglob('*')):
            if file_path.is_file():
                # 忽略.pyc, __pycache__, venv等
                if any(x in str(file_path) for x in ['__pycache__', '.pyc', 'venv', '.git']):
                    continue

                try:
                    with open(file_path, 'rb') as f:
                        hash_md5.update(f.read())
                except:
                    pass

        return hash_md5.hexdigest()

    def run_command(self, cmd, max_retries=3):
        """执行命令并返回结果"""
        for attempt in range(max_retries):
            try:
                result = subprocess.run(
                    cmd,
                    shell=True,
                    capture_output=True,
                    text=True,
                    timeout=120
                )
                return result.returncode == 0, result.stdout, result.stderr
            except Exception as e:
                print(f"[ERROR] Command failed (attempt {attempt + 1}/{max_retries}): {e}")
                time.sleep(5)
        return False, "", str(e)

    def commit_and_push(self):
        """提交并推送变更"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # 1. Git add
        print(f"[{timestamp}] Adding changes...")
        success, _, _ = self.run_command(f"git add {self.watch_dir}")
        if not success:
            print("[ERROR] Git add failed")
            return False

        # 2. Git commit
        commit_msg = f"""chore: Auto backup DAP v2.0 development progress

Timestamp: {timestamp}
Auto-committed by Git Auto Backup Daemon

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude <noreply@anthropic.com>"""

        print(f"[{timestamp}] Committing changes...")
        success, stdout, stderr = self.run_command(f'git commit -m "{commit_msg}"')

        if not success:
            if "nothing to commit" in stderr or "nothing to commit" in stdout:
                print("[INFO] No changes to commit")
                return True
            else:
                print(f"[ERROR] Git commit failed: {stderr}")
                return False

        # 3. Git push
        print(f"[{timestamp}] Pushing to GitHub...")
        success, stdout, stderr = self.run_command("git push origin clean-master")

        if not success:
            if "GH013" in stderr or "secret" in stderr.lower():
                print("[WARNING] GitHub push protection detected!")
                print("[ACTION REQUIRED] Please allow the secret at:")
                print("https://github.com/13925554689/DAP/security/secret-scanning/unblock-secret/35omQgQoNi6O2YdR25W6jsMaE42")
                return False
            else:
                print(f"[ERROR] Git push failed: {stderr}")
                return False

        print(f"[SUCCESS] Backup completed at {timestamp}")
        return True

    def check_git_status(self):
        """检查git状态"""
        success, stdout, _ = self.run_command("git status --porcelain")
        if success and stdout.strip():
            return True  # 有变更
        return False

    def run(self):
        """启动守护进程"""
        print("=" * 60)
        print("DAP v2.0 Git Auto Backup Daemon Started")
        print(f"Watching directory: {self.watch_dir.absolute()}")
        print(f"Check interval: {self.check_interval} seconds")
        print("=" * 60)

        while True:
            try:
                # 计算当前目录hash
                current_hash = self.get_directory_hash()

                # 检测到变更
                if current_hash != self.last_hash:
                    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    print(f"\n[{timestamp}] Change detected!")

                    # 等待5秒确保文件写入完成
                    time.sleep(5)

                    # 再次检查git状态
                    if self.check_git_status():
                        if self.commit_and_push():
                            self.last_hash = current_hash
                            self.save_state(current_hash)
                        else:
                            print("[WARNING] Backup failed, will retry next cycle")
                    else:
                        print("[INFO] No git changes detected")
                        self.last_hash = current_hash
                        self.save_state(current_hash)

                # 等待下一次检查
                time.sleep(self.check_interval)

            except KeyboardInterrupt:
                print("\n[INFO] Backup daemon stopped by user")
                break
            except Exception as e:
                print(f"[ERROR] Unexpected error: {e}")
                time.sleep(self.check_interval)

if __name__ == "__main__":
    daemon = GitAutoBackup(
        watch_dir="dap_v2",
        check_interval=30  # 每30秒检查一次
    )
    daemon.run()
