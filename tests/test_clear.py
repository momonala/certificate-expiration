"""Tests for clearing Xcode provisioning profiles."""

import re
from pathlib import Path

from typer.testing import CliRunner

from src.main import app
from src.main import clear_provisioning_profiles

runner = CliRunner()
_ANSI_ESCAPE = re.compile(r"\x1b\[[0-9;]*m")


def _strip_ansi(text: str) -> str:
    return _ANSI_ESCAPE.sub("", text)


def test_clear_provisioning_profiles_removes_files_and_dirs(tmp_path: Path):
    file_path = tmp_path / "profile.mobileprovision"
    file_path.write_text("profile")
    nested = tmp_path / "nested"
    nested.mkdir()
    (nested / "inner.txt").write_text("inner")

    removed = clear_provisioning_profiles(tmp_path)

    assert removed == 2
    assert list(tmp_path.iterdir()) == []
    assert tmp_path.exists()


def test_clear_provisioning_profiles_missing_dir(tmp_path: Path):
    missing = tmp_path / "does-not-exist"

    removed = clear_provisioning_profiles(missing)

    assert removed == 0


def test_clear_command_invokes_clear(monkeypatch):
    calls: list[tuple] = []

    def fake_clear(*args, **kwargs) -> int:
        calls.append((args, kwargs))
        return 3

    monkeypatch.setattr("src.main.clear_provisioning_profiles", fake_clear)

    result = runner.invoke(app, ["clear"])

    assert result.exit_code == 0
    assert len(calls) == 1
    assert "Cleared 3 item(s)" in _strip_ansi(result.stdout)
