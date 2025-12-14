"""Minimal helpers for loading environment variables."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Iterable

__all__ = ["ConfigError", "load_env_file"]


class ConfigError(RuntimeError):
    """Raised when configuration values are malformed."""


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
