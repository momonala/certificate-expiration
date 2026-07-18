"""Google Calendar utilities for managing events."""

import json
import logging
from dataclasses import dataclass
from datetime import datetime
from datetime import timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from google.oauth2 import service_account
from googleapiclient.discovery import build
from rich.console import Console

console = Console()
logger = logging.getLogger(__name__)

# Get the directory where this script is located
SCRIPT_DIR = Path(__file__).parent.parent.resolve()
EVENT_TRACKING_FILE = SCRIPT_DIR / "app_calendar_events.json"
SERVICE_ACCOUNT_FILE = SCRIPT_DIR / "google_application_credentials.json"
CALENDAR_ID = "mnalavadi@gmail.com"
SCOPES = ["https://www.googleapis.com/auth/calendar"]
BERLIN_TZ = ZoneInfo("Europe/Berlin")
credentials = service_account.Credentials.from_service_account_file(str(SERVICE_ACCOUNT_FILE), scopes=SCOPES)


@dataclass
class AppCertInfo:
    """Information about an app's certificate."""

    app_name: str
    expiration_date: datetime
    cert_path: str


def load_event_ids() -> dict[str, str]:
    """Load the mapping of app names to calendar event IDs."""
    if not EVENT_TRACKING_FILE.exists():
        return {}
    with open(EVENT_TRACKING_FILE) as f:
        return json.load(f)


def save_event_ids(event_mapping: dict[str, str]) -> None:
    """Save the mapping of app names to calendar event IDs."""
    with open(EVENT_TRACKING_FILE, "w") as f:
        json.dump(event_mapping, f, indent=2)


def create_or_update_calendar_event(app_info: AppCertInfo, event_id: str | None = None) -> str | None:
    """Create or update a calendar event for app certificate expiration."""
    calendar_service = build("calendar", "v3", credentials=credentials, cache_discovery=False)
    gcal_client = calendar_service.events()

    # Create event for the day before expiration
    event_date = app_info.expiration_date.date() - timedelta(days=1)
    event = {
        "summary": f"🔄 Rebuild {app_info.app_name}",
        "description": (
            f"Certificate for {app_info.app_name} expires tomorrow!\n\n"
            f"Certificate Path: {app_info.cert_path}\n"
            f"Expiration: {app_info.expiration_date.strftime('%Y-%m-%d %H:%M:%S %Z')}"
        ),
        "start": {
            "date": event_date.isoformat(),  # All-day event uses date instead of dateTime
            "timeZone": str(BERLIN_TZ),
        },
        "end": {
            "date": (
                event_date + timedelta(days=1)
            ).isoformat(),  # All-day event needs end date to be next day
            "timeZone": str(BERLIN_TZ),
        },
        "colorId": "11",  # Red color in Google Calendar
        "reminders": {
            "useDefault": False,
            "overrides": [
                {"method": "popup", "minutes": 1440},  # 1 day before
                {"method": "popup", "minutes": 60},  # 1 hour before
            ],
        },
    }

    try:
        if event_id:
            result = gcal_client.update(calendarId=CALENDAR_ID, eventId=event_id, body=event).execute()
            console.print("  [green]✓[/green] [dim]Updated calendar event[/dim]")
        else:
            result = gcal_client.insert(calendarId=CALENDAR_ID, body=event).execute()
            console.print("  [green]✓[/green] [dim]Created calendar event[/dim]")

        return result["id"]
    except Exception as e:
        console.print(f"  [red]✗[/red] [dim]Failed to sync calendar event: {e}[/dim]")
        return None
