"""Executes planned jobs: transcribe, then write the requested outputs."""

from __future__ import annotations

import logging
import tempfile
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any, Protocol

from scriber.config import OutputFormat, Settings
from scriber.constants import TEXT_ENCODING, TEXT_NEWLINE, WRITER_NAME_SUFFIX
from scriber.jobs import Job
from scriber.manifest import JobResult, JobStatus, Manifest
from scriber.media import enhance_audio, has_audio_stream
from scriber.render import render_transcript

__all__ = ["TranscriberLike", "execute", "write_outputs"]

log = logging.getLogger("scriber")


class TranscriberLike(Protocol):
    @property
    def diarizes(self) -> bool: ...
    def run(self, media_path: str) -> dict[str, Any]: ...
    def close(self) -> None: ...


def _result_for(job: Job, status: JobStatus, **extra: Any) -> JobResult:
    return JobResult(str(job.media.path), [str(p) for p in job.outputs], status, **extra)


def write_outputs(job: Job, result: dict[str, Any], diarized: bool, settings: Settings) -> None:
    """Write every requested format for one job."""
    from whisperx.utils import get_writer  # heavy import, deferred

    job.out_dir.mkdir(parents=True, exist_ok=True)
    subs = settings.subtitles
    writer_options = {
        "highlight_words": subs.highlight_words,
        "max_line_width": subs.max_line_width,
        "max_line_count": subs.max_line_count,
    }
    for fmt in job.formats:
        if fmt is OutputFormat.TXT:
            job.output_path(fmt).write_text(
                render_transcript(result["segments"], diarized), encoding=TEXT_ENCODING, newline=TEXT_NEWLINE
            )
        else:
            get_writer(fmt.value, str(job.out_dir))(result, job.name + WRITER_NAME_SUFFIX, writer_options)


def execute(
    jobs: list[Job],
    settings: Settings,
    transcriber_factory: Callable[[], TranscriberLike],
) -> Manifest:
    """Process jobs one by one. A failing file is recorded and does not stop the rest."""
    manifest = Manifest(dry_run=False)
    pending: list[Job] = []
    for job in jobs:
        if settings.output.skip_existing and job.complete:
            manifest.jobs.append(_result_for(job, JobStatus.SKIPPED))
        else:
            pending.append(job)
    if not pending:
        return manifest

    transcriber = transcriber_factory()
    manifest.diarization = transcriber.diarizes
    if not transcriber.diarizes:
        manifest.warnings.append("No Hugging Face token set: transcripts have no speaker labels.")
        log.warning(manifest.warnings[-1])
    try:
        with tempfile.TemporaryDirectory() as tmp:
            for index, job in enumerate(pending, start=1):
                log.info("[%d/%d] %s", index, len(pending), job.media.path.name)
                manifest.jobs.append(_process(job, settings, transcriber, Path(tmp), manifest))
    finally:
        transcriber.close()
    return manifest


def _process(
    job: Job, settings: Settings, transcriber: TranscriberLike, work_dir: Path, manifest: Manifest
) -> JobResult:
    started = time.perf_counter()
    try:
        if not has_audio_stream(job.media.path):
            raise ValueError("no audio stream found")
        enh = settings.enhance
        source = (
            enhance_audio(job.media.path, work_dir, enh.ffmpeg_filter, enh.sample_rate)
            if enh.enabled
            else job.media.path
        )
        result = transcriber.run(str(source.absolute()))
        if not result["segments"]:
            manifest.warnings.append(f"{job.media.path.name}: no speech detected, wrote empty outputs.")
            log.warning(manifest.warnings[-1])
        write_outputs(job, result, transcriber.diarizes, settings)
    except Exception as exc:  # per-file boundary: record the failure and continue with the next file
        log.error("    failed: %s", exc)
        return _result_for(job, JobStatus.FAILED, seconds=time.perf_counter() - started, error=str(exc))
    elapsed = time.perf_counter() - started
    log.info("    done in %.0fs", elapsed)
    return _result_for(job, JobStatus.DONE, seconds=round(elapsed, 1))
