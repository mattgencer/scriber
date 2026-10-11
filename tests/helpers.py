"""Test helpers: synthetic media (no real recordings in this repo)."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

needs_ffmpeg = pytest.mark.skipif(
    shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None, reason="ffmpeg/ffprobe not installed"
)


def make_audio(path: Path, seconds: int = 1) -> Path:
    subprocess.run(
        ["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", f"sine=f=440:d={seconds}", str(path)], check=True
    )
    return path


def make_video(path: Path, *, with_audio: bool = True, seconds: int = 1) -> Path:
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", f"testsrc=d={seconds}:s=64x64:r=5"]
    if with_audio:
        cmd += ["-f", "lavfi", "-i", f"sine=f=440:d={seconds}", "-shortest"]
    subprocess.run([*cmd, str(path)], check=True)
    return path
