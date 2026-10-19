"""Secrets loaded from .env (copy .env.example to .env for local development)."""

import os
from pathlib import Path

from dotenv import load_dotenv

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(_PROJECT_ROOT / ".env")

TELEGRAM_API_TOKEN = os.environ.get("TELEGRAM_API_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")
CALENDAR_ID = os.environ.get("CALENDAR_ID", "")
