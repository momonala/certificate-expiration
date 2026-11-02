"""Tests for reading provisioning profiles and picking which ones to track."""

import plistlib
from datetime import UTC
from datetime import datetime
from pathlib import Path

import pytest

from src.main import latest_app_profiles
from src.profile import ProfileParseError
from src.profile import parse_profile


def _write_profile(path: Path, bundle_id: str, expires: datetime) -> Path:
    info = {
        "Entitlements": {"application-identifier": f"52K2BR328Z.{bundle_id}"},
        "CreationDate": datetime(2026, 11, 2, 8, 40),
        "ExpirationDate": expires,
    }
    path.write_bytes(b"\x30\x80signature" + plistlib.dumps(info) + b"\x00trailer")
    return path


@pytest.mark.parametrize(
    "bundle_id,app_name,is_app",
    [
        ("mnalavadi.Urban-Sports-Club", "Urban-Sports-Club", True),
        ("org.mnalavadi.Trace", "Trace", True),
        ("org.mnalavadi.Trace.TraceWidgets", "TraceWidgets", False),
        ("mnalavadi.Urban-Sports-ClubUITests", "Urban-Sports-ClubUITests", False),
    ],
)
def test_parse_profile(tmp_path: Path, bundle_id: str, app_name: str, is_app: bool):
    path = _write_profile(tmp_path / "p.mobileprovision", bundle_id, datetime(2026, 11, 9, 8, 40))

    profile = parse_profile(path)

    assert profile.bundle_id == bundle_id
    assert profile.app_name == app_name
    assert profile.is_app is is_app
    assert profile.expires_at == datetime(2026, 11, 9, 8, 40, tzinfo=UTC)


@pytest.mark.parametrize(
    "content",
    [
        b"not a profile",
        b"<?xml version='1.0'?><plist><dict><key>broken</plist>",
        plistlib.dumps({"ExpirationDate": datetime(2026, 11, 9)}),
    ],
)
def test_parse_profile_errors_name_the_file(tmp_path: Path, content: bytes):
    path = tmp_path / "broken.mobileprovision"
    path.write_bytes(content)

    with pytest.raises(ProfileParseError, match="broken.mobileprovision"):
        parse_profile(path)


def test_latest_app_profiles_keeps_newest_per_app_after_bundle_id_rename(tmp_path: Path):
    old = _write_profile(tmp_path / "old", "mnalavadi.Trace", datetime(2026, 11, 6))
    new = _write_profile(tmp_path / "new", "org.mnalavadi.Trace", datetime(2026, 11, 9))
    widget = _write_profile(tmp_path / "widget", "org.mnalavadi.Trace.TraceWidgets", datetime(2026, 11, 9))

    profiles = latest_app_profiles([parse_profile(p) for p in (new, old, widget)])

    assert [p.bundle_id for p in profiles] == ["org.mnalavadi.Trace"]
