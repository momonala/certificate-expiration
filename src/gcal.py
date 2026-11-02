"""Google Calendar utilities for managing events."""

import json
from datetime import timedelta

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from rich.console import Console

from src.config import CALENDAR_PATH
from src.config import GOOGLE_CREDS_PATH
from src.config import TIMEZONE
from src.env import calendar_id
from src.profile import ProvisioningProfile

console = Console()

SCOPES = ["https://www.googleapis.com/auth/calendar"]
_EVENT_GONE_STATUSES = {404, 410}


def load_event_ids() -> dict[str, str]:
    """Load the mapping of app names to calendar event IDs."""
    if not CALENDAR_PATH.exists():
        return {}
    with CALENDAR_PATH.open() as f:
        return json.load(f)


def save_event_ids(event_mapping: dict[str, str]) -> None:
    """Save the mapping of app names to calendar event IDs."""
    with CALENDAR_PATH.open("w") as f:
        json.dump(event_mapping, f, indent=2)


def _build_event(profile: ProvisioningProfile) -> dict:
    expires_at = profile.expires_at.astimezone(TIMEZONE)
    event_date = expires_at.date() - timedelta(days=1)
    return {
        "summary": f"🔄 Rebuild {profile.app_name}",
        "description": (
            f"Certificate for {profile.app_name} expires tomorrow!\n\n"
            f"Bundle ID: {profile.bundle_id}\n"
            f"Certificate Path: {profile.path}\n"
            f"Expiration: {expires_at.strftime('%Y-%m-%d %H:%M:%S %Z')}"
        ),
        "start": {"date": event_date.isoformat(), "timeZone": str(TIMEZONE)},
        "end": {"date": (event_date + timedelta(days=1)).isoformat(), "timeZone": str(TIMEZONE)},
        "status": "confirmed",
        "colorId": "11",
        "reminders": {
            "useDefault": False,
            "overrides": [
                {"method": "popup", "minutes": 1440},
                {"method": "popup", "minutes": 60},
            ],
        },
    }


def create_or_update_calendar_event(profile: ProvisioningProfile, event_id: str | None = None) -> str:
    """Create or update the all-day rebuild reminder the day before the profile expires.

    An event that was deleted from the calendar is recreated. Any other API failure raises.

    Returns:
        The ID of the event now in the calendar.
    """
    credentials = service_account.Credentials.from_service_account_file(str(GOOGLE_CREDS_PATH), scopes=SCOPES)
    events = build("calendar", "v3", credentials=credentials, cache_discovery=False).events()
    event = _build_event(profile)
    target_calendar = calendar_id()

    if event_id:
        try:
            result = events.update(calendarId=target_calendar, eventId=event_id, body=event).execute()
            console.print("  [green]✓[/green] [dim]Updated calendar event[/dim]")
            return result["id"]
        except HttpError as exc:
            if exc.status_code not in _EVENT_GONE_STATUSES:
                raise
            console.print("  [yellow]![/yellow] [dim]Tracked event no longer exists, recreating[/dim]")

    result = events.insert(calendarId=target_calendar, body=event).execute()
    console.print("  [green]✓[/green] [dim]Created calendar event[/dim]")
    return result["id"]
