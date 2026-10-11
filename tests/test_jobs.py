from __future__ import annotations

from pathlib import Path

from scriber.config import Layout, OutputFormat, load_settings
from scriber.jobs import plan_jobs
from scriber.media import MediaFile


def _settings(layout: str, **output: object):  # type: ignore[no-untyped-def]
    return load_settings(overrides={"output": {"layout": layout, **output}, "paths": {"output_dir": "out"}})


def test_per_file_folder_layout() -> None:
    job = plan_jobs([MediaFile(Path("in/talk.mp4"), Path("in"))], _settings("per-file-folder"))[0]
    assert job.output_path(OutputFormat.TXT) == Path("out/talk/talk.txt")
    assert [p.name for p in job.outputs] == ["talk.txt", "talk.srt", "talk.json"]


def test_flat_layout() -> None:
    job = plan_jobs([MediaFile(Path("in/talk.mp4"), Path("in"))], _settings("flat"))[0]
    assert job.output_path(OutputFormat.SRT) == Path("out/talk.srt")


def test_mirror_layout_keeps_input_tree() -> None:
    job = plan_jobs([MediaFile(Path("in/team/week1/talk.mp4"), Path("in"))], _settings("mirror"))[0]
    assert job.output_path(OutputFormat.TXT) == Path("out/team/week1/talk.txt")


def test_same_stem_in_two_places_gets_hash_suffix_instead_of_overwriting() -> None:
    files = [MediaFile(Path("in/a/talk.mp4"), Path("in")), MediaFile(Path("in/b/talk.mp4"), Path("in"))]
    for layout in ("per-file-folder", "flat"):
        paths = [p for job in plan_jobs(files, _settings(layout)) for p in job.outputs]
        assert len(paths) == len(set(paths)), layout
        assert all("talk-" in p.name for p in paths), layout


def test_same_stem_different_extension_does_not_collide_across_layouts() -> None:
    files = [MediaFile(Path("in/talk.mp4"), Path("in")), MediaFile(Path("in/talk.m4a"), Path("in"))]
    jobs = plan_jobs(files, _settings("mirror"))
    assert len({job.output_path(OutputFormat.TXT) for job in jobs}) == 2


def test_distinct_stems_keep_clean_names_and_formats_are_deduplicated() -> None:
    files = [MediaFile(Path("in/a.mp3"), Path("in")), MediaFile(Path("in/b.mp3"), Path("in"))]
    jobs = plan_jobs(files, _settings("flat", formats=["txt", "txt", "vtt"]))
    assert [j.name for j in jobs] == ["a", "b"]
    assert jobs[0].formats == (OutputFormat.TXT, OutputFormat.VTT)


def test_complete_requires_every_requested_output(tmp_path: Path) -> None:
    settings = load_settings(
        overrides={"output": {"layout": Layout.FLAT, "formats": ["txt", "srt"]}, "paths": {"output_dir": str(tmp_path)}}
    )
    job = plan_jobs([MediaFile(Path("in/a.mp3"), Path("in"))], settings)[0]
    assert not job.complete
    (tmp_path / "a.txt").write_text("x", encoding="utf-8")
    assert not job.complete
    (tmp_path / "a.srt").write_text("x", encoding="utf-8")
    assert job.complete
