"""Shared fixtures. Every test runs in an empty cwd with no SCRIBER_*/HF_TOKEN env and no user config."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from scriber.config import Settings, load_settings


@pytest.fixture(autouse=True)
def isolated_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    for name in list(os.environ):
        if name.startswith("SCRIBER_") or name == "HF_TOKEN":
            monkeypatch.delenv(name)
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("USERPROFILE", str(home))
    monkeypatch.setattr("scriber.config.user_config_path", lambda: home / "scriber-user-config.toml")
    workdir = tmp_path / "work"
    workdir.mkdir()
    monkeypatch.chdir(workdir)
    return workdir


@pytest.fixture
def settings() -> Settings:
    return load_settings()
