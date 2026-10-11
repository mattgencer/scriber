# AGENTS.md

Instructions for AI coding and assistant agents using or working on this repository.

## What this is

`scriber` is a local CLI that transcribes audio and video files to text, subtitles and JSON, with speaker labels
(WhisperX: Whisper large-v3 + alignment + pyannote diarization). Media never leaves the machine.
Run it with `uv run scriber ...` from the repo, or `scriber ...` if installed with `uv tool install .`.

## Running a transcription (protocol)

1. **Check the environment**: `scriber doctor --json`. Blocking failure (exit 3) usually means ffmpeg is missing.
   A missing Hugging Face token is not blocking: it only disables speaker labels. Tell the user.
2. **Ask the user** whatever they have not already said:
   - Which file(s) or folder? (absolute or relative paths, globs allowed)
   - How many speakers? (exact number or a range; skip if one speaker or unknown)
   - Language? (default `en`; `auto` for mixed or unknown)
   - Is the audio noisy (hum, traffic, fan)? If yes add `--enhance`, otherwise never.
   - Any technical jargon Whisper might mangle? (`-t term`). Not people's names or rare words.
   - Output formats (`txt srt vtt tsv json`), output folder and layout (`per-file-folder`, `flat`, `mirror`)?
   - Redo files that already have outputs? (`--overwrite`)
3. **Preview**: `scriber run <sources> <flags> --dry-run --json`. Show the planned files and output paths.
4. **Confirm when heavy**: a single named file may run without asking. A folder, glob, or more than one file can mean
   many long GPU jobs, so get a yes first.
5. **Run**: `scriber run <sources> <flags> --json`. Long jobs: run in the background and report when done.
6. **Report** from the manifest: outputs written (`jobs[].outputs`), skipped, failed (`jobs[].error`), `warnings`.
   Exit code 4 means some files failed and the rest succeeded.

Rules:

- Never print, log or commit the Hugging Face token. It is read only from `HF_TOKEN` / `SCRIBER_HF_TOKEN` / `.env`.
- Never commit anything from `input/`, `output/` or `.env`. They are gitignored on purpose: they hold personal media.
- Do not invent flags. `scriber describe` lists every option, setting, env var and default as JSON.
- Prefer config over code changes: all tunables are in `src/scriber/config.default.toml` and overridable by
  `scriber.toml`, `SCRIBER_*` env vars and CLI flags (precedence in `docs/CONFIGURATION.md`).

## Working on the code

- Python 3.13, `uv`. Tests: `uv run pytest` (no GPU needed, tests synthesise their own media with ffmpeg).
- Quality gate: `uv run ruff check . && uv run ruff format --check . && uv run mypy src && uv run pytest`.
- No magic values: new tunables go into `config.default.toml` plus a `Field(description=...)` in `config.py`;
  `describe` and the docs table pick them up from there. Structural invariants only go in `constants.py`.
- Heavy imports (torch, whisperx) stay out of module top level in `cli.py` so `--help`, `--dry-run`, `describe`
  stay instant.
- Add a test with every behavior change. Keep real recordings and transcripts out of the repo and out of tests.
