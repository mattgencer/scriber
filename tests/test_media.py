from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from helpers import make_audio, make_video, needs_ffmpeg

from scriber.config import Settings, load_settings
from scriber.media import build_enhance_command, enhance_audio, find_media, has_audio_stream


def _touch(*paths: Path) -> None:
    for path in paths:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"")


def test_find_media_picks_audio_and_video_recursively_and_skips_the_rest(tmp_path: Path, settings: Settings) -> None:
    wanted = [tmp_path / "a.M4A", tmp_path / "sub" / "b.mp3", tmp_path / "sub" / "clip.MKV", tmp_path / "c.mov"]
    _touch(*wanted, tmp_path / "notes.txt", tmp_path / "a.enhanced.wav", tmp_path / "pic.png")
    found = find_media([tmp_path], settings)
    assert [m.path for m in found] == sorted(wanted, key=str)
    assert all(m.root == tmp_path for m in found)


def test_find_media_non_recursive(tmp_path: Path) -> None:
    _touch(tmp_path / "a.mp3", tmp_path / "sub" / "b.mp3")
    flat = load_settings(overrides={"media": {"recursive": False}})
    assert [m.path for m in find_media([tmp_path], flat)] == [tmp_path / "a.mp3"]


def test_explicit_file_is_accepted_without_extension_but_folder_scan_ignores_it(
    tmp_path: Path, settings: Settings
) -> None:
    bare = tmp_path / "recording"
    _touch(bare)
    assert [m.path for m in find_media([bare], settings)] == [bare]
    assert find_media([tmp_path], settings) == []


def test_glob_sources_are_expanded_and_deduplicated(tmp_path: Path, settings: Settings) -> None:
    _touch(tmp_path / "a.mp3", tmp_path / "b.mp3")
    found = find_media([tmp_path / "*.mp3", tmp_path / "a.mp3", tmp_path], settings)
    assert [m.path.name for m in found] == ["a.mp3", "b.mp3"]


def test_missing_source_yields_nothing(tmp_path: Path, settings: Settings) -> None:
    assert find_media([tmp_path / "nope"], settings) == []


def test_enhance_command_passes_paths_verbatim_and_drops_video() -> None:
    tricky = Path("my clip; rm -rf x.mp4")
    cmd = build_enhance_command(tricky, Path("out.wav"), "highpass=f=80", 16_000)
    assert cmd[cmd.index("-i") + 1] == str(tricky.absolute())  # absolute: can never parse as a protocol
    assert cmd[cmd.index("-protocol_whitelist") + 1] == "file"
    assert cmd[cmd.index("-af") + 1] == "highpass=f=80"
    assert cmd[cmd.index("-ar") + 1] == "16000"
    assert "-vn" in cmd
    assert cmd[-1] == "out.wav"


@needs_ffmpeg
def test_enhance_audio_turns_a_video_into_16k_mono_wav(tmp_path: Path, settings: Settings) -> None:
    video = make_video(tmp_path / "clip.mp4")
    out = enhance_audio(video, tmp_path / "work", settings.enhance.ffmpeg_filter, settings.enhance.sample_rate)
    probe = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "stream=sample_rate,channels", "-of", "csv=p=0", str(out)],
        check=True, capture_output=True, text=True,
    )  # fmt: skip
    assert probe.stdout.strip() == "16000,1"


@needs_ffmpeg
def test_has_audio_stream_distinguishes_silent_video(tmp_path: Path) -> None:
    assert has_audio_stream(make_audio(tmp_path / "tone.mp3"))
    assert has_audio_stream(make_video(tmp_path / "with.mp4"))
    assert not has_audio_stream(make_video(tmp_path / "silent.mp4", with_audio=False))


def test_tilde_source_is_expanded(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, settings: Settings) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    _touch(tmp_path / "clips" / "a.mp3")
    assert [m.path for m in find_media([Path("~/clips")], settings)] == [tmp_path / "clips" / "a.mp3"]


@needs_ffmpeg
def test_spaces_unicode_and_leading_dash_in_names_survive_ffmpeg_and_ffprobe(
    tmp_path: Path, settings: Settings
) -> None:
    names = ["my meeting (final).mp4", "réunion équipe 会议.mp4", "-dash first.mp4"]
    for name in names:
        video = make_video(tmp_path / name)
        assert has_audio_stream(video), name
        out = enhance_audio(video, tmp_path / "work", settings.enhance.ffmpeg_filter, settings.enhance.sample_rate)
        assert out.is_file(), name
