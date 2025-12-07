"""Top-level package for the E-Ink calendar display application."""

from __future__ import annotations
from .config import AppConfig, GoogleCalendarSettings, load_config
from .scheduler import Scheduler, next_half_minute_boundary

__all__ = [
    "__version__",
    "Scheduler",
    "next_half_minute_boundary",
    "calendar",
    "AppConfig",
    "GoogleCalendarSettings",
    "load_config",
]

__version__ = "0.1.0"
