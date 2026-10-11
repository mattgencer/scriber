from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from helpers import make_audio, make_video, needs_ffmpeg

from scriber.config import Settings, load_settings
from scriber.jobs import Job, plan_jobs
from scriber.manifest import JobStatus
from scriber.media import MediaFile
from scriber.runner import execute

SEGMENTS = [
    {
        "start": 0.0,
        "end": 1.0,
        "text": "Hello there.",
        "speaker": "SPEAKER_00",
        "words": [
            {"word": "Hello", "start": 0.0, "end": 0.5, "speaker": "SPEAKER_00"},
            {"word": "there.", "start": 0.5, "end": 1.0, "speaker": "SPEAKER_00"},
        ],
    },
    {
        "start": 1.0,
        "end": 2.0,
        "text": "Hi.",
        "speaker": "SPEAKER_01",
        "words": [{"word": "Hi.", "start": 1.0, "end": 2.0, "speaker": "SPEAKER_01"}],
    },
]


class FakeTranscriber:
    def __init__(self, segments: list[dict[str, Any]], diarizes: bool = True) -> None:
        self.segments = segments
        self.diarizes = diarizes
        self.calls: list[str] = []
        self.closed = False

    def run(self, media_path: str) -> dict[str, Any]:
        self.calls.append(media_path)
        return {"segments": self.segments, "language": "en"}

    def close(self) -> None:
        self.closed = True


def _plan(settings: Settings, *paths: Path) -> list[Job]:
    return plan_jobs([MediaFile(p, p.parent) for p in paths], settings)


@pytest.fixture
def out_settings(tmp_path: Path) -> Settings:
    return load_settings(overrides={"paths": {"output_dir": str(tmp_path / "out")}})


@needs_ffmpeg
def test_video_is_transcribed_and_all_default_formats_are_written(tmp_path: Path, out_settings: Settings) -> None:
    video = make_video(tmp_path / "meeting.mp4")
    fake = FakeTranscriber(SEGMENTS)
    manifest = execute(_plan(out_settings, video), out_settings, lambda: fake)
    assert [j.status for j in manifest.jobs] == [JobStatus.DONE]
    folder = tmp_path / "out" / "meeting"
    assert (folder / "meeting.txt").read_text(encoding="utf-8").startswith("[00:00:00] SPEAKER_00: Hello there.")
    assert "Hello there." in (folder / "meeting.srt").read_text(encoding="utf-8")
    assert json.loads((folder / "meeting.json").read_text(encoding="utf-8"))["segments"]
    assert fake.calls == [str(video)]
    assert fake.closed


@needs_ffmpeg
def test_existing_outputs_are_skipped_and_no_model_is_loaded(tmp_path: Path, out_settings: Settings) -> None:
    audio = make_audio(tmp_path / "a.mp3")
    jobs = _plan(out_settings, audio)
    execute(jobs, out_settings, lambda: FakeTranscriber(SEGMENTS))

    def must_not_load() -> FakeTranscriber:
        raise AssertionError("models loaded although nothing was pending")

    manifest = execute(jobs, out_settings, must_not_load)
    assert [j.status for j in manifest.jobs] == [JobStatus.SKIPPED]


@needs_ffmpeg
def test_overwrite_reprocesses(tmp_path: Path) -> None:
    settings = load_settings(
        overrides={"paths": {"output_dir": str(tmp_path / "out")}, "output": {"skip_existing": False}}
    )
    audio = make_audio(tmp_path / "a.mp3")
    jobs = _plan(settings, audio)
    execute(jobs, settings, lambda: FakeTranscriber(SEGMENTS))
    manifest = execute(jobs, settings, lambda: FakeTranscriber(SEGMENTS))
    assert [j.status for j in manifest.jobs] == [JobStatus.DONE]


@needs_ffmpeg
def test_silent_video_fails_that_file_but_not_the_batch(tmp_path: Path, out_settings: Settings) -> None:
    silent = make_video(tmp_path / "silent.mp4", with_audio=False)
    good = make_audio(tmp_path / "good.mp3")
    manifest = execute(_plan(out_settings, silent, good), out_settings, lambda: FakeTranscriber(SEGMENTS))
    by_name = {Path(j.source).name: j for j in manifest.jobs}
    assert by_name["silent.mp4"].status is JobStatus.FAILED
    assert "no audio stream" in (by_name["silent.mp4"].error or "")
    assert by_name["good.mp3"].status is JobStatus.DONE
    assert manifest.exit_code == 4


@needs_ffmpeg
def test_empty_transcript_writes_empty_outputs_and_warns(tmp_path: Path, out_settings: Settings) -> None:
    audio = make_audio(tmp_path / "quiet.mp3")
    manifest = execute(_plan(out_settings, audio), out_settings, lambda: FakeTranscriber([]))
    assert manifest.jobs[0].status is JobStatus.DONE
    assert (tmp_path / "out" / "quiet" / "quiet.txt").read_text(encoding="utf-8") == ""
    assert any("no speech" in w for w in manifest.warnings)


@needs_ffmpeg
def test_missing_diarization_is_reported_and_labels_omitted(tmp_path: Path, out_settings: Settings) -> None:
    audio = make_audio(tmp_path / "a.mp3")
    manifest = execute(_plan(out_settings, audio), out_settings, lambda: FakeTranscriber(SEGMENTS, diarizes=False))
    assert manifest.diarization is False
    assert any("speaker labels" in w for w in manifest.warnings)
    assert "SPEAKER" not in (tmp_path / "out" / "a" / "a.txt").read_text(encoding="utf-8")


@needs_ffmpeg
def test_enhance_runs_on_video_and_transcriber_receives_the_wav(tmp_path: Path) -> None:
    settings = load_settings(overrides={"paths": {"output_dir": str(tmp_path / "out")}, "enhance": {"enabled": True}})
    video = make_video(tmp_path / "clip.mp4")
    fake = FakeTranscriber(SEGMENTS)
    manifest = execute(_plan(settings, video), settings, lambda: fake)
    assert manifest.jobs[0].status is JobStatus.DONE
    assert fake.calls[0].endswith(".enhanced.wav")


@needs_ffmpeg
def test_text_output_is_utf8_with_lf_endings_on_every_os(tmp_path: Path, out_settings: Settings) -> None:
    audio = make_audio(tmp_path / "café talk.mp3")
    execute(_plan(out_settings, audio), out_settings, lambda: FakeTranscriber(SEGMENTS))
    raw = (tmp_path / "out" / "café talk" / "café talk.txt").read_bytes()
    assert b"\r\n" not in raw
    assert raw.endswith(b"\n")
