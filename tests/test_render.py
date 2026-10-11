from __future__ import annotations

import pytest
from hypothesis import given
from hypothesis import strategies as st

from scriber.render import Turn, format_timestamp, merge_turns, render_transcript


@pytest.mark.parametrize(
    ("seconds", "expected"),
    [(0, "00:00:00"), (59.9, "00:00:59"), (61, "00:01:01"), (3600, "01:00:00"), (-5, "00:00:00")],
)
def test_format_timestamp(seconds: float, expected: str) -> None:
    assert format_timestamp(seconds) == expected


@given(st.floats(min_value=0, max_value=10 * 3600, allow_nan=False))
def test_format_timestamp_round_trips_to_whole_seconds(seconds: float) -> None:
    h, m, s = (int(part) for part in format_timestamp(seconds).split(":"))
    assert h * 3600 + m * 60 + s == int(seconds)


def test_merge_turns_collapses_same_speaker_and_skips_blank() -> None:
    segments = [
        {"start": 0.0, "text": " Hello.", "speaker": "SPEAKER_00"},
        {"start": 2.0, "text": "How are you?", "speaker": "SPEAKER_00"},
        {"start": 4.0, "text": "   ", "speaker": "SPEAKER_01"},
        {"start": 5.0, "text": "Fine.", "speaker": "SPEAKER_01"},
        {"start": 7.0, "text": "Good.", "speaker": "SPEAKER_00"},
    ]
    assert merge_turns(segments) == [
        Turn("SPEAKER_00", 0.0, "Hello. How are you?"),
        Turn("SPEAKER_01", 5.0, "Fine."),
        Turn("SPEAKER_00", 7.0, "Good."),
    ]


def test_render_transcript_diarized_labels_missing_speaker() -> None:
    segments = [{"start": 0, "text": "Hi", "speaker": "SPEAKER_00"}, {"start": 65, "text": "Yo"}]
    assert render_transcript(segments, diarized=True) == "[00:00:00] SPEAKER_00: Hi\n\n[00:01:05] UNKNOWN: Yo\n"


def test_render_transcript_plain_and_empty() -> None:
    assert render_transcript([{"start": 1, "text": "Hi"}], diarized=False) == "[00:00:01] Hi\n"
    assert render_transcript([], diarized=True) == ""
