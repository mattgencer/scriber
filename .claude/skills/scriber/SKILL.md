---
name: scriber
description: Use when asked to transcribe, run, or process audio or video recordings (meetings, calls, lectures, podcasts, any media file) with this project, or to set up or troubleshoot transcription. Follows the run protocol in AGENTS.md.
---

# Transcribing audio and video with scriber

Follow the protocol in `AGENTS.md` (repo root). In short:

1. `scriber doctor --json` (or `uv run scriber doctor --json`). Report blocking failures; a missing token only means no speaker labels.
2. Ask what is not yet known: source path(s), speaker count, language, noisy audio, jargon terms, output formats and folder.
3. `scriber run <sources> <flags> --dry-run --json`, show the plan.
4. A single named file runs without confirmation. A folder, glob or several files: ask first.
5. `scriber run <sources> <flags> --json`. Run long jobs in the background and report when done.
6. Summarise from the manifest: outputs, skipped, failed, warnings.

Use `scriber describe` for the exact flags and settings. Never print or commit the Hugging Face token, and never
commit `input/`, `output/` or `.env`.
