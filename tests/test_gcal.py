"""Tests for syncing the rebuild reminder to Google Calendar."""

from datetime import UTC
from datetime import datetime
from pathlib import Path

import pytest
from googleapiclient.errors import HttpError
from httplib2 import Response

from src import gcal
from src.profile import ProvisioningProfile

PROFILE = ProvisioningProfile(
    path=Path("p.mobileprovision"),
    bundle_id="org.mnalavadi.Trace",
    expires_at=datetime(2026, 11, 9, 8, 40, tzinfo=UTC),
)


class _Request:
    def __init__(self, result: dict | None = None, error: HttpError | None = None):
        self._result, self._error = result, error

    def execute(self) -> dict:
        if self._error:
            raise self._error
        return self._result


class _FakeEvents:
    def __init__(self, update_status: int | None):
        self.update_status = update_status
        self.inserted: list[dict] = []

    def update(self, calendarId: str, eventId: str, body: dict) -> _Request:
        if self.update_status:
            return _Request(error=HttpError(Response({"status": self.update_status}), b""))
        return _Request({"id": eventId})

    def insert(self, calendarId: str, body: dict) -> _Request:
        self.inserted.append(body)
        return _Request({"id": "new-event"})


@pytest.fixture
def fake_events(monkeypatch, request) -> _FakeEvents:
    events = _FakeEvents(request.param)
    monkeypatch.setenv("CALENDAR_ID", "calendar")
    monkeypatch.setattr(gcal.service_account.Credentials, "from_service_account_file", lambda *a, **k: None)
    monkeypatch.setattr(gcal, "build", lambda *a, **k: type("Service", (), {"events": lambda self: events})())
    return events


@pytest.mark.parametrize("fake_events", [None], indirect=True)
def test_existing_event_is_updated(fake_events: _FakeEvents):
    assert gcal.create_or_update_calendar_event(PROFILE, "existing") == "existing"
    assert fake_events.inserted == []


@pytest.mark.parametrize("fake_events", [404, 410], indirect=True)
def test_deleted_event_is_recreated(fake_events: _FakeEvents):
    assert gcal.create_or_update_calendar_event(PROFILE, "gone") == "new-event"
    assert fake_events.inserted[0]["start"]["date"] == "2026-11-08"


@pytest.mark.parametrize("fake_events", [403], indirect=True)
def test_other_api_errors_propagate(fake_events: _FakeEvents):
    with pytest.raises(HttpError):
        gcal.create_or_update_calendar_event(PROFILE, "existing")
