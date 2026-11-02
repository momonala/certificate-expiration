"""Secrets loaded from .env (copy .env.example to .env for local development)."""

import os

from dotenv import load_dotenv

from src.config import PROJECT_ROOT

load_dotenv(PROJECT_ROOT / ".env")


def calendar_id() -> str:
    """The Google Calendar to write to. Raises KeyError when unset."""
    return os.environ["CALENDAR_ID"]
