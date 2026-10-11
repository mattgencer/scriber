from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from helpers import make_audio, needs_ffmpeg
from typer.testing import CliRunner

import scriber.pipeline
from scriber.cli import app

runner = CliRunner()


def _invoke(*args: str) -> Any:
    return runner.invoke(app, list(args))


def test_describe_prints_valid_json_with_settings() -> None:
    result = _invoke("describe")
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert {"commands", "settings", "exit_codes", "precedence"} <= data.keys()


def test_dry_run_json_lists_planned_outputs_without_loading_models(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def explode(*_: Any, **__: Any) -> None:
        raise AssertionError("Transcriber constructed during dry run")

    monkeypatch.setattr(scriber.pipeline, "Transcriber", explode)
    (tmp_path / "talk.mp4").write_bytes(b"")
    out = tmp_path / "out"
    result = _invoke("run", str(tmp_path), "--dry-run", "--json", "-o", str(out), "-f", "txt", "--layout", "flat")
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert data["dry_run"] is True
    assert data["counts"]["planned"] == 1
    assert data["jobs"][0]["outputs"] == [str(out / "talk.txt")]


def test_no_media_found_is_a_clean_empty_result() -> None:
    result = _invoke("run", "--json")
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert data["jobs"] == []
    assert data["warnings"]


def test_missing_config_file_exits_3() -> None:
    result = _invoke("run", "--config", "does-not-exist.toml", "--dry-run")
    assert result.exit_code == 3


def test_invalid_flag_value_exits_2() -> None:
    result = _invoke("run", "--batch-size", "0", "--dry-run")
    assert result.exit_code == 2


def test_env_override_is_visible_in_dry_run_output_paths(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    (tmp_path / "a.mp3").write_bytes(b"")
    monkeypatch.setenv("SCRIBER_PATHS__OUTPUT_DIR", str(tmp_path / "from-env"))
    result = _invoke("run", str(tmp_path / "a.mp3"), "--dry-run", "--json")
    assert str(tmp_path / "from-env") in json.loads(result.stdout)["jobs"][0]["outputs"][0]


@needs_ffmpeg
def test_run_json_end_to_end_with_fake_transcriber(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    class Fake:
        diarizes = False

        def __init__(self, *_: Any) -> None: ...

        def run(self, media_path: str) -> dict[str, Any]:
            return {"segments": [{"start": 0.0, "end": 1.0, "text": "Hello.", "words": []}], "language": "en"}

        def close(self) -> None: ...

    monkeypatch.setattr(scriber.pipeline, "Transcriber", Fake)
    audio = make_audio(tmp_path / "a.mp3")
    out = tmp_path / "out"
    result = _invoke("run", str(audio), "--json", "-o", str(out), "-f", "txt", "--layout", "flat")
    assert result.exit_code == 0, result.output
    data = json.loads(result.stdout)
    assert data["counts"]["done"] == 1
    assert (out / "a.txt").read_text(encoding="utf-8") == "[00:00:00] Hello.\n"


def test_doctor_json_reports_checks_and_never_prints_the_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HF_TOKEN", "hf_should_never_appear")
    result = _invoke("doctor", "--json")
    assert "hf_should_never_appear" not in result.output
    data = json.loads(result.stdout)
    assert {c["name"] for c in data["checks"]} >= {"ffmpeg", "ffprobe", "compute", "hf-token"}
