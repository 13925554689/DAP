import base64
import io
import zipfile
from pathlib import Path

import pytest

from config.settings import GitHubBackupConfig
from layer5.github_backup_manager import GitHubBackupManager

pytestmark = pytest.mark.unit


class DummyResponse:
    def __init__(
        self, status_code=200, json_data=None, text: str = "", raise_for_status=False
    ):
        self.status_code = status_code
        self._json_data = json_data or {}
        self.text = text
        self._raise = raise_for_status

    def json(self):
        return self._json_data

    def raise_for_status(self):
        if self._raise or not (200 <= self.status_code < 300):
            from requests import HTTPError

            raise HTTPError(response=self)


class FakeSession:
    def __init__(self):
        self.last_get = None
        self.last_put = None
        self.closed = False

    def get(self, url, headers=None, verify=True):
        self.last_get = {"url": url, "headers": headers, "verify": verify}
        return DummyResponse(status_code=404, json_data={})

    def put(self, url, headers=None, json=None, verify=True):
        self.last_put = {
            "url": url,
            "headers": headers,
            "json": json,
            "verify": verify,
        }
        return DummyResponse(
            status_code=201, json_data={"commit": {"sha": "abc123"}}
        )

    def close(self):
        self.closed = True


def make_config(tmp_path: Path, backup_paths):
    return GitHubBackupConfig(
        enabled=True,
        repository="owner/repo",
        branch="main",
        token_env_var="TEST_GITHUB_TOKEN",
        backup_paths=backup_paths,
        backup_temp_dir=str(tmp_path / "temp"),
        remote_path="backups",
        interval_minutes=120,
        commit_message_template="Automated backup: {timestamp}",
        retention_count=5,
        author_name="Unit Tester",
        author_email="tester@example.com",
        verify_ssl=False,
    )


def test_run_backup_requires_token(monkeypatch, tmp_path):
    target_dir = tmp_path / "data"
    target_dir.mkdir()
    (target_dir / "file.txt").write_text("payload", encoding="utf-8")

    config = make_config(tmp_path, [str(target_dir)])
    session = FakeSession()
    manager = GitHubBackupManager(config, session=session)

    # Ensure token missing causes a skip
    monkeypatch.delenv("TEST_GITHUB_TOKEN", raising=False)
    assert manager.run_backup(triggered_by="unit-test") is False
    status = manager.get_status()
    assert status["success"] is False
    assert "token" in status["message"].lower()


def test_run_backup_uploads_archive(monkeypatch, tmp_path):
    target_dir = tmp_path / "exports"
    target_dir.mkdir()
    target_file = target_dir / "report.csv"
    target_file.write_text("id,value\n1,100", encoding="utf-8")

    config = make_config(tmp_path, [str(target_dir)])
    session = FakeSession()
    manager = GitHubBackupManager(config, session=session)

    monkeypatch.setenv("TEST_GITHUB_TOKEN", "ghp_dummy")

    assert manager.run_backup(triggered_by="unit-test") is True
    status = manager.get_status()
    assert status["success"] is True
    assert status["details"]["commit_sha"] == "abc123"
    assert status["details"]["remote_path"].startswith("backups/dap-backup-")
    assert session.last_put is not None
    assert session.last_put["url"].startswith(
        "https://api.github.com/repos/owner/repo/contents/backups/dap-backup-"
    )
    assert session.last_get is not None
    assert session.last_get["url"] == session.last_put["url"]

    payload = session.last_put["json"]
    assert payload["branch"] == "main"
    assert "Automated backup" in payload["message"]

    archive_bytes = base64.b64decode(payload["content"])
    with zipfile.ZipFile(io.BytesIO(archive_bytes), "r") as zf:
        assert "report.csv" in zf.namelist()

    manager.stop()
    assert session.closed is True
