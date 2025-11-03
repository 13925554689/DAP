"""
GitHub Backup Manager
Layer 5 component responsible for automated repository backups.

This module packages configured project artifacts, uploads them to a GitHub
repository via the REST API, and optionally schedules recurring uploads.
"""

from __future__ import annotations

import base64
import logging
import os
import threading
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import requests

from config.settings import GitHubBackupConfig

LOGGER = logging.getLogger(__name__)


@dataclass
class BackupStatus:
    """Lightweight state container describing the most recent backup run."""

    success: Optional[bool] = None
    message: str = ""
    last_run: Optional[str] = None
    details: Dict[str, Any] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "message": self.message,
            "last_run": self.last_run,
            "details": self.details or {},
        }


class GitHubBackupManager:
    """Coordinates GitHub backup uploads and optional scheduling."""

    API_URL_TEMPLATE = "https://api.github.com/repos/{repository}/contents/{path}"

    def __init__(
        self,
        config: GitHubBackupConfig,
        session: Optional[requests.Session] = None,
        logger: Optional[logging.Logger] = None,
    ) -> None:
        self.config = config
        self.logger = logger or LOGGER.getChild("GitHubBackupManager")
        self.session = session or requests.Session()

        self._stop_event = threading.Event()
        self._worker_thread: Optional[threading.Thread] = None
        self._status = BackupStatus(details={})

        if not self.config.enabled:
            self.logger.info("GitHub backup manager initialised in disabled state.")

    # --------------------------------------------------------------------- API
    def start(self, enable_scheduler: bool = False) -> None:
        """Start the background scheduler if enabled.
        
        Args:
            enable_scheduler: 是否启动定时备份调度器，False表示只使用文件变更触发
        """
        if not self.config.enabled:
            return
        
        # 默认不启动定时备份，只使用文件变更触发
        if not enable_scheduler:
            self.logger.info(
                "GitHub backup manager started (file-change triggered mode only, no scheduled backups)."
            )
            return
            
        if self._worker_thread and self._worker_thread.is_alive():
            return

        self._stop_event.clear()
        interval_minutes = max(1, int(self.config.interval_minutes))

        self._worker_thread = threading.Thread(
            target=self._run_loop,
            name="GitHubBackupWorker",
            args=(interval_minutes,),
            daemon=True,
        )
        self._worker_thread.start()
        self.logger.info(
            "GitHub backup scheduler started (every %s minutes).", interval_minutes
        )

    def stop(self) -> None:
        """Stop the background scheduler and release resources."""
        self._stop_event.set()
        if self._worker_thread and self._worker_thread.is_alive():
            self._worker_thread.join(timeout=10)
        self._worker_thread = None
        self.session.close()
        self.logger.info("GitHub backup scheduler stopped.")

    def run_backup(self, triggered_by: str = "manual") -> bool:
        """Execute a backup immediately."""
        if not self.config.enabled:
            self._set_status(False, "GitHub backup disabled via configuration.")
            return False

        token = os.getenv(self.config.token_env_var)
        if not token:
            message = (
                f"No GitHub token found in environment variable "
                f"{self.config.token_env_var}; skipping backup."
            )
            self._set_status(False, message)
            self.logger.warning(message)
            return False

        archive_path: Optional[Path] = None
        timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")

        try:
            archive_path, file_count = self._create_backup_archive()
            if archive_path is None or file_count == 0:
                message = "No files matched configured backup paths; nothing to upload."
                self._set_status(True, message, details={"trigger": triggered_by})
                self.logger.info(message)
                return True

            remote_path = self._build_remote_path(archive_path.name)
            response = self._upload_to_github(
                archive_path=archive_path,
                token=token,
                remote_path=remote_path,
                triggered_by=triggered_by,
                file_count=file_count,
                timestamp=timestamp,
            )
            response.raise_for_status()
            commit_sha = response.json().get("commit", {}).get("sha")

            message = (
                f"Backup uploaded successfully to {remote_path} "
                f"({file_count} files, commit {commit_sha})."
            )
            self._set_status(
                True,
                message,
                details={
                    "trigger": triggered_by,
                    "commit_sha": commit_sha,
                    "remote_path": remote_path,
                    "files": file_count,
                },
            )
            self.logger.info(message)
            return True
        except requests.HTTPError as exc:
            status_code = getattr(exc.response, "status_code", None)
            message = f"GitHub API error during backup (status={status_code}): {exc}"
            self._set_status(
                False,
                message,
                details={
                    "trigger": triggered_by,
                    "status_code": status_code,
                    "response": getattr(exc.response, "text", ""),
                },
            )
            self.logger.error(message)
            return False
        except Exception as exc:  # pragma: no cover - defensive
            message = f"Unexpected error during GitHub backup: {exc}"
            self._set_status(False, message, details={"trigger": triggered_by})
            self.logger.exception(message)
            return False
        finally:
            if archive_path and archive_path.exists():
                try:
                    archive_path.unlink()
                except OSError:
                    self.logger.debug("Failed to remove temporary archive %s", archive_path)

            self._status.last_run = timestamp

    def get_status(self) -> Dict[str, Any]:
        """Return a snapshot of the latest backup state."""
        return self._status.to_dict()

    # ----------------------------------------------------------------- helpers
    def _run_loop(self, interval_minutes: int) -> None:
        """Worker loop that triggers scheduled backups."""
        # Run once immediately, then wait for interval.
        self.run_backup(triggered_by="scheduled")

        interval_seconds = max(60, interval_minutes * 60)
        while not self._stop_event.wait(interval_seconds):
            self.run_backup(triggered_by="scheduled")

    def _create_backup_archive(self) -> Tuple[Optional[Path], int]:
        """Create a ZIP archive containing all configured backup paths."""
        timestamp = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
        archive_name = f"dap-backup-{timestamp}.zip"
        archive_dir = Path(self.config.backup_temp_dir).resolve()
        archive_dir.mkdir(parents=True, exist_ok=True)
        archive_path = archive_dir / archive_name

        root_path = Path.cwd()
        included_files = 0
        temp_dir = archive_dir

        import zipfile

        with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            for raw_path in self.config.backup_paths:
                target_path = Path(raw_path)
                if not target_path.is_absolute():
                    target_path = root_path / target_path
                if not target_path.exists():
                    self.logger.debug("Skip missing backup path: %s", target_path)
                    continue
                if temp_dir in target_path.resolve().parents:
                    self.logger.debug(
                        "Skip backup temp directory to avoid recursion: %s", target_path
                    )
                    continue

                if target_path.is_file():
                    if self._insert_file(zf, target_path, root_path):
                        included_files += 1
                    continue

                for file_path in target_path.rglob("*"):
                    if not file_path.is_file():
                        continue
                    if temp_dir in file_path.resolve().parents:
                        # Avoid including generated archives.
                        continue
                    if self._insert_file(zf, file_path, root_path):
                        included_files += 1

        if included_files == 0:
            try:
                archive_path.unlink()
            except OSError:
                self.logger.debug("Failed to remove empty archive %s", archive_path)
            return None, 0

        return archive_path, included_files

    def _insert_file(self, zip_file, file_path: Path, root_path: Path) -> bool:
        """Add a file to the archive using a repository-relative path."""
        try:
            arcname = file_path.relative_to(root_path).as_posix()
        except ValueError:
            # File outside project root; include name-only to avoid disclosure.
            arcname = file_path.name
        try:
            zip_file.write(file_path, arcname=arcname)
            return True
        except OSError as exc:  # pragma: no cover - defensive
            self.logger.warning("Failed to add %s to backup archive: %s", file_path, exc)
            return False

    def _upload_to_github(
        self,
        archive_path: Path,
        token: str,
        remote_path: str,
        triggered_by: str,
        file_count: int,
        timestamp: str,
    ) -> requests.Response:
        """Upload the archive to GitHub via the contents API."""
        url = self.API_URL_TEMPLATE.format(
            repository=self.config.repository, path=remote_path
        )
        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
        }
        content = base64.b64encode(archive_path.read_bytes()).decode("utf-8")

        commit_message = self._format_commit_message(
            timestamp=timestamp, files=file_count, triggered_by=triggered_by
        )

        payload: Dict[str, Any] = {
            "message": commit_message,
            "content": content,
            "branch": self.config.branch,
            "committer": {
                "name": self.config.author_name,
                "email": self.config.author_email,
            },
        }

        existing_sha = self._fetch_existing_sha(url, headers)
        if existing_sha:
            payload["sha"] = existing_sha

        response = self.session.put(
            url, headers=headers, json=payload, verify=self.config.verify_ssl
        )
        return response

    def _fetch_existing_sha(
        self, url: str, headers: Dict[str, str]
    ) -> Optional[str]:
        """Return current file SHA if the remote object already exists."""
        try:
            response = self.session.get(url, headers=headers, verify=self.config.verify_ssl)
        except requests.RequestException:  # pragma: no cover - defensive
            return None

        if response.status_code == 200:
            try:
                return response.json().get("sha")
            except ValueError:
                return None
        return None

    def _set_status(
        self, success: bool, message: str, details: Optional[Dict[str, Any]] = None
    ) -> None:
        self._status.success = success
        self._status.message = message
        if details is not None:
            self._status.details = details

    def _build_remote_path(self, filename: str) -> str:
        """Construct remote path inside the repository."""
        if self.config.remote_path:
            return f"{self.config.remote_path.rstrip('/')}/{filename}"
        return filename

    def _format_commit_message(
        self, timestamp: str, files: int, triggered_by: str
    ) -> str:
        """Render commit message template with fallback."""
        template = self.config.commit_message_template or "Automated backup: {timestamp}"
        try:
            return template.format(
                timestamp=timestamp,
                files=files,
                trigger=triggered_by,
                triggered_by=triggered_by,
            )
        except Exception:
            self.logger.debug(
                "Failed to format commit message with template %s; using fallback.",
                template,
            )
            return (
                f"Automated backup at {timestamp} "
                f"(files={files}, trigger={triggered_by})"
            )
