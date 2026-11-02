import logging
import shutil
from datetime import datetime
from pathlib import Path

import typer
from rich import box
from rich.console import Console
from rich.logging import RichHandler
from rich.panel import Panel
from rich.text import Text

from src.config import TIMEZONE
from src.gcal import create_or_update_calendar_event
from src.gcal import load_event_ids
from src.gcal import save_event_ids
from src.profile import ProfileParseError
from src.profile import ProvisioningProfile
from src.profile import parse_profile

# Setup rich console and logging
console = Console()
logging.basicConfig(
    level=logging.INFO,
    format="%(message)s",
    datefmt="[%X]",
    handlers=[RichHandler(console=console, rich_tracebacks=True, show_path=False)],
)

PROVISIONING_PROFILES_DIR = Path.home() / "Library/Developer/Xcode/UserData/Provisioning Profiles"

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


def latest_app_profiles(profiles: list[ProvisioningProfile]) -> list[ProvisioningProfile]:
    """Drop non-app profiles and keep the latest-expiring profile per app name."""
    latest: dict[str, ProvisioningProfile] = {}
    for profile in profiles:
        if not profile.is_app:
            continue
        current = latest.get(profile.app_name)
        if current is None or profile.expires_at > current.expires_at:
            latest[profile.app_name] = profile
    return sorted(latest.values(), key=lambda p: p.app_name)


def print_expiry(app_name: str, expiration_date: datetime):
    formatted_expiriation = expiration_date.strftime("%a %d %b at %H:%M %Z")

    current_datetime = datetime.now(TIMEZONE)
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


def check_certificates(profiles: list[ProvisioningProfile]) -> None:
    console.print()
    console.rule("[bold cyan]🔐 Certificate Expiration Checker[/bold cyan]", style="cyan")
    console.print()

    if not profiles:
        console.print("[yellow]⚠️  No certificates found![/yellow]")
        return

    console.print(f"[dim]Processing {len(profiles)} certificate(s)...[/dim]\n")

    event_mapping = load_event_ids()
    for profile in profiles:
        event_mapping[profile.app_name] = create_or_update_calendar_event(
            profile, event_mapping.get(profile.app_name)
        )
        save_event_ids(event_mapping)
        print_expiry(profile.app_name, profile.expires_at.astimezone(TIMEZONE))

    console.print()
    console.rule(f"[bold green]✨ Processed {len(profiles)} certificate(s)[/bold green]", style="green")
    console.print()


@app.callback(invoke_without_command=True)
def default(
    ctx: typer.Context,
    profile: Path | None = typer.Option(
        None,
        "--profile",
        exists=True,
        dir_okay=False,
        help="Check only this .mobileprovision instead of scanning Xcode's profiles directory.",
    ),
) -> None:
    """Run the certificate expiration check."""
    if ctx.invoked_subcommand is not None:
        return
    try:
        if profile:
            profiles = [parse_profile(profile)]
        else:
            scanned = [parse_profile(path) for path in PROVISIONING_PROFILES_DIR.glob("*.mobileprovision")]
            profiles = latest_app_profiles(scanned)
    except ProfileParseError as exc:
        console.print(f"[bold red]✗ ERROR:[/bold red] {exc}")
        raise typer.Exit(1) from exc
    check_certificates(profiles)


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
