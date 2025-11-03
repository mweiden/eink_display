"""Top-level package for the e-ink calendar display application."""

from .config import AppConfig, GoogleCalendarSettings, load_config

__all__ = [
    "AppConfig",
    "GoogleCalendarSettings",
    "load_config",
]
