"""Top-level package for the E-Ink calendar display application."""
from .config import AppConfig, GoogleCalendarSettings, load_config
from .scheduler import Scheduler, next_half_minute_boundary
from __future__ import annotations


__version__ = "0.1.0"

__all__ = [
    "__version__",
    "Scheduler",
    "next_half_minute_boundary",
    "calendar",
    "AppConfig",
    "GoogleCalendarSettings",
    "load_config",
]
