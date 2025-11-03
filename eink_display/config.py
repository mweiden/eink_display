"""Configuration loading utilities for the e-ink calendar display."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

__all__ = [
    "ConfigError",
    "GoogleCalendarSettings",
    "AppConfig",
    "load_config",
]


class ConfigError(RuntimeError):
    """Raised when configuration values are missing or invalid."""


@dataclass(frozen=True)
class GoogleCalendarSettings:
    """Configuration required to talk to the Google Calendar API."""

    credentials_path: Path
    calendar_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.credentials_path.exists():
            raise ConfigError(
                "Google credentials file does not exist: " f"{self.credentials_path}"
            )
        if not self.calendar_ids:
            raise ConfigError("At least one calendar ID must be configured.")


@dataclass(frozen=True)
class AppConfig:
    """Top level application configuration."""

    google: GoogleCalendarSettings


def load_config(env_file: str | Path | None = None) -> AppConfig:
    """Load configuration from the environment or an optional ``.env`` file."""

    load_env_file(env_file)

    google = GoogleCalendarSettings(
        credentials_path=_require_path("GOOGLE_CREDENTIALS_PATH"),
        calendar_ids=_parse_calendar_ids(_require_env("CALENDAR_IDS")),
    )

    return AppConfig(google=google)


def load_env_file(env_file: str | Path | None = None) -> None:
    """Load environment variables from ``env_file`` if provided.

    When ``env_file`` is :data:`None`, the loader looks for a ``.env`` file in the
    current working directory. Existing environment variables are never overwritten.
    """

    path = Path(env_file) if env_file is not None else Path.cwd() / ".env"
    if not path.exists() or not path.is_file():
        return

    for key, value in _iter_env_entries(path):
        os.environ.setdefault(key, value)


def _iter_env_entries(path: Path) -> Iterable[tuple[str, str]]:
    for raw_line in path.read_text().splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            raise ConfigError(
                f"Invalid line in {path.name!r}: {raw_line!r}. Expected KEY=VALUE format."
            )
        key, raw_value = line.split("=", 1)
        key = key.strip()
        value = raw_value.strip().strip('"').strip("'")
        if not key:
            raise ConfigError(f"Environment variable key is missing in line: {raw_line!r}")
        yield key, value


def _require_env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise ConfigError(
            f"Required environment variable {name!r} is not set. "
            "Set it in the environment or .env file."
        )
    return value


def _require_path(name: str) -> Path:
    raw = _require_env(name)
    return Path(raw).expanduser().resolve()


def _parse_calendar_ids(value: str) -> tuple[str, ...]:
    ids = tuple(part.strip() for part in value.split(",") if part.strip())
    if not ids:
        raise ConfigError("No valid calendar IDs provided in CALENDAR_IDS")
    return ids
