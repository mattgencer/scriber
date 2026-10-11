"""`scriber` command: run, doctor, describe."""

from __future__ import annotations

import contextlib
import json
import logging
import sys
from pathlib import Path
from typing import Annotated, Any

import typer

from scriber.config import ConfigError, Layout, OutputFormat, Settings, load_settings, user_config_files
from scriber.constants import APP_NAME, FFMPEG, FFPROBE, ExitCode
from scriber.describe import build_description
from scriber.doctor import run_checks
from scriber.jobs import plan_jobs
from scriber.manifest import JobResult, JobStatus, Manifest
from scriber.media import find_media, require_tool
from scriber.overrides import nest

log = logging.getLogger(APP_NAME)
app = typer.Typer(
    help="Transcribe audio and video to text, subtitles and JSON, with speaker labels. Runs entirely on your machine.",
    no_args_is_help=True,
)


def _configure_logging(verbose: bool) -> None:
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO, format="%(levelname)s %(message)s", stream=sys.stderr
    )


def _load(config: Path | None, overrides: dict[str, Any] | None = None) -> Settings:
    try:
        return load_settings(config, overrides)
    except ConfigError as exc:
        typer.echo(f"error: {exc}", err=True)
        raise typer.Exit(ExitCode.ENVIRONMENT) from exc
    except ValueError as exc:  # invalid values in config, env or flags
        typer.echo(f"error: invalid configuration:\n{exc}", err=True)
        raise typer.Exit(ExitCode.USAGE) from exc


def _emit(manifest: Manifest, as_json: bool) -> None:
    if as_json:
        typer.echo(json.dumps(manifest.to_dict(), indent=2))
        return
    for job in manifest.jobs:
        typer.echo(f"{job.status.value:8} {job.source}")
        for output in job.outputs if job.status in (JobStatus.PLANNED, JobStatus.DONE) else []:
            typer.echo(f"         -> {output}")
        if job.error:
            typer.echo(f"         error: {job.error}")
    counts = ", ".join(f"{manifest.count(status)} {status.value}" for status in JobStatus if manifest.count(status))
    typer.echo(counts or "nothing to do")


@app.command()
def run(
    sources: Annotated[
        list[Path] | None,
        typer.Argument(help="Files, folders or globs of audio/video. Default: the configured input folder."),
    ] = None,
    config: Annotated[Path | None, typer.Option("--config", help="Config TOML file (or set SCRIBER_CONFIG).")] = None,
    output: Annotated[Path | None, typer.Option("--output", "-o", help="Output root folder.")] = None,
    formats: Annotated[
        list[OutputFormat] | None, typer.Option("--format", "-f", help="Output format. Repeatable.")
    ] = None,
    layout: Annotated[Layout | None, typer.Option("--layout", help="How outputs are organised.")] = None,
    skip_existing: Annotated[
        bool | None, typer.Option("--skip-existing/--overwrite", help="Skip inputs that already have all outputs.")
    ] = None,
    recursive: Annotated[
        bool | None, typer.Option("--recursive/--no-recursive", help="Search folders recursively.")
    ] = None,
    enhance: Annotated[
        bool | None, typer.Option("--enhance/--no-enhance", help="Clean noisy audio with ffmpeg first.")
    ] = None,
    model: Annotated[str | None, typer.Option("--model", help="Whisper model name.")] = None,
    device: Annotated[str | None, typer.Option("--device", help="auto, cuda or cpu.")] = None,
    language: Annotated[str | None, typer.Option("--language", "-l", help="ISO code, or auto to detect.")] = None,
    batch_size: Annotated[int | None, typer.Option("--batch-size", help="Inference batch size.")] = None,
    speakers: Annotated[int | None, typer.Option("--speakers", help="Exact speaker count, if known.")] = None,
    min_speakers: Annotated[int | None, typer.Option("--min-speakers", help="Minimum speaker count.")] = None,
    max_speakers: Annotated[int | None, typer.Option("--max-speakers", help="Maximum speaker count.")] = None,
    term: Annotated[
        list[str] | None, typer.Option("--term", "-t", help="Jargon to steer spelling. Repeatable.")
    ] = None,
    dry_run: Annotated[bool, typer.Option("--dry-run", help="Show what would run; load no models.")] = False,
    as_json: Annotated[bool, typer.Option("--json", help="Print a JSON manifest on stdout.")] = False,
    verbose: Annotated[bool, typer.Option("--verbose", "-v", help="Debug logging.")] = False,
) -> None:
    """Transcribe SOURCES into the output folder."""
    _configure_logging(verbose)
    values = {
        "paths.output_dir": output,
        "output.formats": formats,
        "output.layout": layout,
        "output.skip_existing": skip_existing,
        "media.recursive": recursive,
        "enhance.enabled": enhance,
        "model.name": model,
        "model.device": device,
        "model.language": language,
        "model.batch_size": batch_size,
        "diarization.num_speakers": speakers,
        "diarization.min_speakers": min_speakers,
        "diarization.max_speakers": max_speakers,
    }
    settings = _load(config, nest(values))
    for config_file in user_config_files(config):
        log.info("Using config file %s", config_file.absolute())
    glossary = [*settings.glossary.terms, *(term or [])]

    media = find_media(sources or [settings.paths.input_dir], settings)
    jobs = plan_jobs(media, settings)

    if dry_run:
        manifest = Manifest(dry_run=True)
        for job in jobs:
            skipped = settings.output.skip_existing and job.complete
            status = JobStatus.SKIPPED if skipped else JobStatus.PLANNED
            manifest.jobs.append(JobResult(str(job.media.path), [str(p) for p in job.outputs], status))
        _emit(manifest, as_json)
        raise typer.Exit(ExitCode.OK)

    if not any(not (settings.output.skip_existing and job.complete) for job in jobs):
        _emit(_skipped_only(jobs, settings), as_json)
        raise typer.Exit(ExitCode.OK)

    try:
        require_tool(FFMPEG)
        require_tool(FFPROBE)
    except RuntimeError as exc:
        typer.echo(f"error: {exc}", err=True)
        raise typer.Exit(ExitCode.ENVIRONMENT) from exc

    # Heavy imports deferred so --help, --dry-run, describe and doctor stay fast.
    from scriber.pipeline import Transcriber
    from scriber.runner import execute

    # Keep stdout clean for the JSON manifest: third-party libraries sometimes print to it.
    quiet = contextlib.redirect_stdout(sys.stderr) if as_json else contextlib.nullcontext()
    with quiet:
        manifest = execute(jobs, settings, lambda: Transcriber(settings, glossary))
    _emit(manifest, as_json)
    raise typer.Exit(manifest.exit_code)


def _skipped_only(jobs: list[Any], settings: Settings) -> Manifest:
    manifest = Manifest(dry_run=False)
    for job in jobs:
        manifest.jobs.append(JobResult(str(job.media.path), [str(p) for p in job.outputs], JobStatus.SKIPPED))
    if not jobs:
        manifest.warnings.append(f"No media files found (looked in {settings.paths.input_dir}).")
    return manifest


@app.command()
def doctor(
    config: Annotated[Path | None, typer.Option("--config", help="Config TOML file.")] = None,
    online: Annotated[bool, typer.Option("--online", help="Also check Hugging Face access (network).")] = False,
    as_json: Annotated[bool, typer.Option("--json", help="Print results as JSON.")] = False,
) -> None:
    """Check ffmpeg, GPU, Hugging Face token and config before a run."""
    settings = _load(config)
    files = user_config_files(config)
    checks = run_checks(settings, files, online)
    failed = [c for c in checks if not c.ok and c.blocking]
    if as_json:
        typer.echo(json.dumps({"ok": not failed, "checks": [c.to_dict() for c in checks]}, indent=2))
    else:
        for check in checks:
            mark = "ok  " if check.ok else ("FAIL" if check.blocking else "warn")
            typer.echo(f"[{mark}] {check.name}: {check.detail}")
    raise typer.Exit(ExitCode.ENVIRONMENT if failed else ExitCode.OK)


@app.command()
def describe() -> None:
    """Print every command, option, setting, env var and exit code as JSON (for scripts and AI agents)."""
    typer.echo(json.dumps(build_description(), indent=2))
