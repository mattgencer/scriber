"""Finding input media (audio and video) and optional ffmpeg pre-processing."""

from __future__ import annotations

import glob
import shutil
import subprocess
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

from scriber.config import Media, Settings
from scriber.constants import ENHANCE_CHANNELS, ENHANCED_SUFFIX, FFMPEG, FFMPEG_PROTOCOL_WHITELIST, FFPROBE

__all__ = ["MediaFile", "build_enhance_command", "enhance_audio", "find_media", "has_audio_stream", "require_tool"]


@dataclass(frozen=True)
class MediaFile:
    """An input file plus the root it was found under (used by the `mirror` output layout)."""

    path: Path
    root: Path


def require_tool(name: str) -> str:
    found = shutil.which(name)
    if found is None:
        raise RuntimeError(f"{name} not found on PATH. Install FFmpeg (https://ffmpeg.org/download.html).")
    return found


def _scan(root: Path, media: Media) -> list[Path]:
    walker = root.rglob("*") if media.recursive else root.glob("*")
    extensions = media.extensions
    return sorted(
        p for p in walker if p.is_file() and p.suffix.lower() in extensions and not p.name.endswith(ENHANCED_SUFFIX)
    )


def _expand(source: Path) -> list[Path]:
    """A source that does not exist but contains glob characters is expanded (shells like PowerShell do not)."""
    source = source.expanduser()
    if source.exists():
        return [source]
    return [Path(match) for match in sorted(glob.glob(str(source), recursive=True))]


def find_media(sources: Iterable[Path], settings: Settings) -> list[MediaFile]:
    """Resolve sources (files, folders, globs) to media files, deduplicated, in a stable order.

    An explicitly named file is always accepted, whatever its extension. The extension filter
    only applies when scanning a folder.
    """
    found: dict[Path, MediaFile] = {}
    for source in sources:
        for entry in _expand(source):
            if entry.is_file():
                candidates = [MediaFile(entry, entry.parent)]
            elif entry.is_dir():
                candidates = [MediaFile(p, entry) for p in _scan(entry, settings.media)]
            else:
                continue
            for item in candidates:
                found.setdefault(item.path.resolve(), item)
    return sorted(found.values(), key=lambda item: str(item.path))


def build_enhance_command(source: Path, target: Path, ffmpeg_filter: str, sample_rate: int) -> list[str]:
    return [
        FFMPEG, "-y", "-hide_banner", "-loglevel", "error",
        *FFMPEG_PROTOCOL_WHITELIST,
        "-i", str(source.absolute()),
        "-vn",
        "-af", ffmpeg_filter,
        "-ac", str(ENHANCE_CHANNELS), "-ar", str(sample_rate),
        str(target),
    ]  # fmt: skip


def enhance_audio(source: Path, work_dir: Path, ffmpeg_filter: str, sample_rate: int) -> Path:
    """Write a cleaned mono WAV (video stream dropped) into work_dir and return its path."""
    require_tool(FFMPEG)
    work_dir.mkdir(parents=True, exist_ok=True)
    target = work_dir / f"{source.stem}{ENHANCED_SUFFIX}"
    # Argument list, no shell: file names are passed verbatim.
    subprocess.run(build_enhance_command(source, target, ffmpeg_filter, sample_rate), check=True)
    return target


def has_audio_stream(path: Path) -> bool:
    """True when ffprobe finds at least one audio stream (False for silent video)."""
    require_tool(FFPROBE)
    probe = subprocess.run(
        [
            FFPROBE,
            "-v",
            "error",
            "-select_streams",
            "a",
            "-show_entries",
            "stream=index",
            "-of",
            "csv=p=0",
            *FFMPEG_PROTOCOL_WHITELIST,
            "-i",
            str(path.absolute()),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    return probe.returncode == 0 and bool(probe.stdout.strip())
