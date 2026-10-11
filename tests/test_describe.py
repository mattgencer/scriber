from __future__ import annotations

import json

import pytest

from scriber.describe import build_description, iter_settings
from scriber.overrides import OVERRIDES, nest


def test_description_covers_every_setting_with_env_name_and_default() -> None:
    described = {item["key"]: item for item in build_description()["settings"]}
    assert set(described) == {".".join(path) for path, _ in iter_settings()}
    assert described["model.device"]["env"] == ["SCRIBER_MODEL__DEVICE"]
    assert described["model.device"]["default"] == "auto"
    assert described["output.formats"]["default"] == ["txt", "srt", "json"]
    assert all(item["description"] for item in described.values())


def test_every_cli_override_targets_a_real_setting() -> None:
    keys = {".".join(path) for path, _ in iter_settings()}
    assert {override.key for override in OVERRIDES} <= keys


def test_secret_has_no_default_and_is_flagged(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HF_TOKEN", "hf_should_never_appear")
    text = json.dumps(build_description())
    assert "hf_should_never_appear" not in text
    token = next(item for item in build_description()["settings"] if item["key"] == "hf_token")
    assert token["secret"] is True
    assert token["default"] is None


def test_nest_drops_unset_values() -> None:
    assert nest({"a.b": 1, "a.c": None, "d": False}) == {"a": {"b": 1}, "d": False}
