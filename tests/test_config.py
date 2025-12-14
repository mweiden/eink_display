from __future__ import annotations

import os
from pathlib import Path

import pytest

from eink_display.config import ConfigError, load_env_file


def test_load_env_file_sets_missing_values(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text("FOO=bar\n# comment\nBAZ = 123\n", encoding="utf-8")

    monkeypatch.delenv("FOO", raising=False)
    monkeypatch.setenv("BAZ", "keep")

    load_env_file(env_file)

    assert os.environ["FOO"] == "bar"
    assert os.environ["BAZ"] == "keep"


def test_load_env_file_is_noop_when_missing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    missing = tmp_path / "missing.env"
    monkeypatch.delenv("FOO", raising=False)

    load_env_file(missing)

    assert "FOO" not in os.environ


def test_invalid_line_raises(tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text("INVALID", encoding="utf-8")

    with pytest.raises(ConfigError, match="Invalid line"):
        load_env_file(env_file)
