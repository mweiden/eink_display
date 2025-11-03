from __future__ import annotations

from pathlib import Path

import pytest

from eink_display.config import ConfigError, load_config


def test_load_config_from_env_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("GOOGLE_CREDENTIALS_PATH", raising=False)
    monkeypatch.delenv("CALENDAR_IDS", raising=False)

    credentials_file = tmp_path / "credentials.json"
    credentials_file.write_text("{}", encoding="utf-8")

    env_file = tmp_path / ".env"
    env_file.write_text(
        "\n".join(
            [
                f"GOOGLE_CREDENTIALS_PATH={credentials_file}",
                "CALENDAR_IDS=primary,team@example.com ",
            ]
        ),
        encoding="utf-8",
    )

    config = load_config(env_file=env_file)

    assert config.google.credentials_path == credentials_file.resolve()
    assert config.google.calendar_ids == ("primary", "team@example.com")


def test_load_config_requires_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("GOOGLE_CREDENTIALS_PATH", raising=False)
    monkeypatch.delenv("CALENDAR_IDS", raising=False)

    with pytest.raises(ConfigError, match="GOOGLE_CREDENTIALS_PATH"):
        load_config()


def test_load_config_requires_existing_credentials(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    missing_file = tmp_path / "missing.json"
    monkeypatch.setenv("GOOGLE_CREDENTIALS_PATH", str(missing_file))
    monkeypatch.setenv("CALENDAR_IDS", "primary")

    with pytest.raises(ConfigError, match="does not exist"):
        load_config()


def test_invalid_env_line_raises(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("GOOGLE_CREDENTIALS_PATH", raising=False)
    monkeypatch.delenv("CALENDAR_IDS", raising=False)

    env_file = tmp_path / ".env"
    env_file.write_text("INVALID_LINE", encoding="utf-8")

    with pytest.raises(ConfigError, match="Invalid line"):
        load_config(env_file=env_file)
