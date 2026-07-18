import logging
import re
import shutil
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import requests
import typer
from rich import box
from rich.console import Console
from rich.logging import RichHandler
from rich.panel import Panel
from rich.text import Text

from src.gcal import AppCertInfo
from src.gcal import create_or_update_calendar_event
from src.gcal import load_event_ids
from src.gcal import save_event_ids
from src.values import telegram_api_token
from src.values import telegram_chat_id

# Setup rich console and logging
console = Console()
logging.basicConfig(
    level=logging.INFO,
    format="%(message)s",
    datefmt="[%X]",
    handlers=[RichHandler(console=console, rich_tracebacks=True, show_path=False)],
)
logger = logging.getLogger(__name__)
telegrap_api_uri = f"https://api.telegram.org/bot{telegram_api_token}/sendMessage"

PROVISIONING_PROFILES_DIR = Path.home() / "Library/Developer/Xcode/UserData/Provisioning Profiles"
BERLIN_TZ = ZoneInfo("Europe/Berlin")

app = typer.Typer(help="Track iOS certificate expiration dates.")


def clear_provisioning_profiles(directory: Path = PROVISIONING_PROFILES_DIR) -> int:
    """Remove all files and directories under the provisioning profiles directory."""
    if not directory.exists():
        return 0

    removed = 0
    for path in directory.iterdir():
        if path.is_dir():
            shutil.rmtree(path)
        else:
            path.unlink()
        removed += 1
    return removed


def extract_app_name(_certificate: str) -> tuple[str, datetime]:
    # Define the regular expression pattern
    # line_with_app_name = d[5].decode("utf-8")
    identifier = "XC mnalavadi "
    lines = [x.decode("utf-8") for x in _certificate[4:7]]
    line_with_app_name = [x for x in lines if identifier in x][0]
    pattern = rf"<string>{identifier}(.*?)</string>"
    match = re.search(pattern, line_with_app_name)
    if not match:
        console.print(f"[bold red]✗ ERROR:[/bold red] Could not find app name in: {line_with_app_name}")
        return None, None
    app_name = match.group(1)
    if "test" in app_name.lower() or "widget" in app_name.lower():
        return None, None

    date_string = [x for x in _certificate if b"date" in x][1].decode("utf-8")
    date_time_str = date_string.split("<date>")[1].split("</date>")[0]
    # Convert UTC to Berlin time
    expiration_date = (
        datetime.strptime(date_time_str, "%Y-%m-%dT%H:%M:%SZ")
        .replace(tzinfo=ZoneInfo("UTC"))
        .astimezone(BERLIN_TZ)
    )

    return app_name, expiration_date


def send_telegram_message(app_name: str, expiration_date: datetime):
    formatted_expiriation = expiration_date.strftime("%a %d %b at %H:%M %Z")

    current_datetime = datetime.now(BERLIN_TZ)
    time_difference = expiration_date - current_datetime
    days = time_difference.days
    hours, remainder = divmod(time_difference.seconds, 3600)
    minutes, _ = divmod(remainder, 60)

    # Determine urgency color based on days remaining
    if days < 1:
        urgency_color = "red"
        urgency_icon = "🚨"
    elif days < 2:
        urgency_color = "yellow"
        urgency_icon = "⚠️"
    else:
        urgency_color = "green"
        urgency_icon = "✅"

    l1 = f"Expiration Date: {formatted_expiriation}"
    l2 = f"Expires in: {days}d {hours}h {minutes}m"
    telegram_msg = f"{app_name}\n{l1}\n{l2}"

    # Create a rich panel for display
    content = Text()
    content.append("📅 Expiration: ", style="bold")
    content.append(f"{formatted_expiriation}\n", style="cyan")
    content.append(f"{urgency_icon} Expires in: ", style="bold")
    content.append(f"{days}d {hours}h {minutes}m", style=f"bold {urgency_color}")

    panel = Panel(
        content,
        title=f"[bold magenta]📱 {app_name}[/bold magenta]",
        border_style=urgency_color,
        box=box.ROUNDED,
    )
    console.print(panel)

    json = {
        "chat_id": telegram_chat_id,
        "text": f"```---{telegram_msg}```",
        "parse_mode": "Markdown",
    }
    resp = requests.post(telegrap_api_uri, json=json)
    if resp.status_code != 200:
        logger.error(resp.text)


def check_certificates() -> None:
    console.print()
    console.rule("[bold cyan]🔐 Certificate Expiration Checker[/bold cyan]", style="cyan")
    console.print()

    certs = list(PROVISIONING_PROFILES_DIR.glob("*mobileprovision"))
    if not certs:
        console.print("[yellow]⚠️  No certificates found![/yellow]")
        return

    console.print(f"[dim]Found {len(certs)} certificate(s) to process...[/dim]\n")

    processed = 0
    for cert in certs:
        with open(cert, "rb") as f:
            _certificate = f.readlines()

        app_name, expiration_date = extract_app_name(_certificate)
        if not app_name:
            continue

        processed += 1

        # Create or update calendar event
        app_info = AppCertInfo(app_name=app_name, expiration_date=expiration_date, cert_path=str(cert))
        event_mapping = load_event_ids()
        event_id = event_mapping.get(app_name)
        new_event_id = create_or_update_calendar_event(app_info, event_id)
        if new_event_id:
            event_mapping[app_name] = new_event_id
        save_event_ids(event_mapping)

        # Send Telegram notification
        send_telegram_message(app_name, expiration_date)

    console.print()
    console.rule(f"[bold green]✨ Processed {processed} certificate(s)[/bold green]", style="green")
    console.print()


@app.callback(invoke_without_command=True)
def default(ctx: typer.Context) -> None:
    """Run the certificate expiration check."""
    if ctx.invoked_subcommand is not None:
        return
    check_certificates()


@app.command("clear")
def clear_cmd() -> None:
    """Remove all Xcode provisioning profiles."""
    removed = clear_provisioning_profiles()
    if removed == 0:
        console.print("[yellow]No provisioning profiles to clear.[/yellow]")
    else:
        console.print(f"[green]Cleared {removed} item(s) from provisioning profiles.[/green]")


def main() -> None:
    app()


if __name__ == "__main__":
    main()
