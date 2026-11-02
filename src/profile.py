"""Parsing of iOS provisioning profiles (.mobileprovision)."""

import plistlib
from datetime import UTC
from datetime import datetime
from pathlib import Path
from xml.parsers.expat import ExpatError

from pydantic import AwareDatetime
from pydantic import BaseModel
from pydantic import field_validator

_PLIST_START = b"<?xml"
_PLIST_END = b"</plist>"
_NON_APP_SUFFIXES = ("tests", "widget", "widgets")


class ProfileParseError(ValueError):
    """A provisioning profile could not be read."""


class ProvisioningProfile(BaseModel, frozen=True):
    path: Path
    bundle_id: str
    expires_at: AwareDatetime

    @field_validator("expires_at", mode="before")
    @classmethod
    def _assume_utc(cls, value: datetime) -> datetime:
        return value if value.tzinfo else value.replace(tzinfo=UTC)

    @property
    def app_name(self) -> str:
        return self.bundle_id.rsplit(".", 1)[-1]

    @property
    def is_app(self) -> bool:
        """False for test runners and widget extensions, which share the app's expiry."""
        return not self.app_name.lower().endswith(_NON_APP_SUFFIXES)


def parse_profile(path: Path) -> ProvisioningProfile:
    """Read the property list embedded in a signed .mobileprovision file.

    Raises:
        ProfileParseError: the file holds no property list or lacks a required key.
    """
    data = path.read_bytes()
    start = data.find(_PLIST_START)
    end = data.find(_PLIST_END)
    if start == -1 or end == -1:
        raise ProfileParseError(f"{path}: no property list found")

    try:
        info = plistlib.loads(data[start : end + len(_PLIST_END)])
        application_id = info["Entitlements"]["application-identifier"]
        expiration = info["ExpirationDate"]
        _team_id, bundle_id = application_id.split(".", 1)
    except (ExpatError, KeyError, ValueError) as exc:
        raise ProfileParseError(f"{path}: {exc!r}") from exc

    return ProvisioningProfile(path=path, bundle_id=bundle_id, expires_at=expiration)
