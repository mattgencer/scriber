"""Pure helpers: readable transcript rendering. No model dependencies."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Any

from scriber.constants import SECONDS_PER_HOUR, SECONDS_PER_MINUTE, UNKNOWN_SPEAKER

__all__ = ["Turn", "format_timestamp", "merge_turns", "render_transcript"]


@dataclass(frozen=True)
class Turn:
    speaker: str | None
    start: float
    text: str


def format_timestamp(seconds: float) -> str:
    total = max(0, int(seconds))
    hours, rest = divmod(total, SECONDS_PER_HOUR)
    minutes, secs = divmod(rest, SECONDS_PER_MINUTE)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"


def merge_turns(segments: Iterable[Mapping[str, Any]]) -> list[Turn]:
    """Collapse consecutive segments from the same speaker into one turn."""
    turns: list[Turn] = []
    for seg in segments:
        text = str(seg.get("text", "")).strip()
        if not text:
            continue
        speaker = seg.get("speaker")
        if turns and turns[-1].speaker == speaker:
            last = turns[-1]
            turns[-1] = Turn(last.speaker, last.start, f"{last.text} {text}")
        else:
            turns.append(Turn(speaker, float(seg.get("start", 0.0)), text))
    return turns


def render_transcript(segments: Iterable[Mapping[str, Any]], diarized: bool) -> str:
    """One paragraph per speaker turn: '[hh:mm:ss] SPEAKER_00: text'."""
    lines = []
    for turn in merge_turns(segments):
        stamp = format_timestamp(turn.start)
        if diarized:
            lines.append(f"[{stamp}] {turn.speaker or UNKNOWN_SPEAKER}: {turn.text}")
        else:
            lines.append(f"[{stamp}] {turn.text}")
    return "\n\n".join(lines) + ("\n" if lines else "")
