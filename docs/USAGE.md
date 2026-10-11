# Usage

## Inputs

`scriber run [SOURCE...]` accepts any mix of:

- a **file** (always accepted, whatever its extension),
- a **folder** (scanned recursively; only known audio and video extensions are picked up),
- a **glob** such as `"videos/*.mkv"` (quote it so your shell does not expand it, PowerShell never does).

With no source it scans the configured input folder (`./input` by default).

Supported by default: audio `m4a mp3 wav ogg opus aac flac wma amr 3gp`, video `mp4 mkv webm mov avi m4v flv wmv ts mpg mpeg`.
Video is handled by ffmpeg, which reads the first audio stream. A video without sound is reported as failed for that
file and the rest of the batch continues. Add extensions in `[media]` (see CONFIGURATION).

`--no-recursive` limits a folder scan to its top level.

## Outputs

Choose formats with `-f` (repeatable) or `output.formats`: `txt`, `srt`, `vtt`, `tsv`, `json`.

| Format | Contents |
|---|---|
| `txt` | One paragraph per speaker turn: `[hh:mm:ss] SPEAKER_00: text` |
| `srt`, `vtt` | Subtitles. Open next to the media in VLC to check a passage |
| `tsv` | Start, end, text columns |
| `json` | Full WhisperX result: segments, word timings, speaker per word |

Choose where they go with `-o <dir>` and `--layout`:

| Layout | Result for `in/team/talk.mp4` |
|---|---|
| `per-file-folder` (default) | `output/talk/talk.txt` |
| `flat` | `output/talk.txt` |
| `mirror` | `output/team/talk.txt` (keeps the input folder tree) |

If two inputs would write to the same place (same name in different folders), both get a short hash suffix
(`talk-3fa91c`) so nothing is overwritten. A file is skipped when **all** requested outputs already exist; use
`--overwrite` to redo it. A silent recording produces empty outputs and a warning.

## Recipes

```bash
scriber run talk.mp4                           # simplest case
scriber run meeting.mp4 --speakers 3           # known speaker count: noticeably better labels
scriber run panel.mp4 --min-speakers 2 --max-speakers 5
scriber run call.m4a --enhance                 # noisy audio (hum, traffic, fan)
scriber run talk.mp4 -t EKS -t SRE             # jargon spelling hints
scriber run lecture.mp4 -l auto                # detect the language per file
scriber run talk.mp4 -l de --model medium      # other language, smaller model
scriber run talk.mp4 --device cpu              # force CPU
scriber run talk.mp4 --batch-size 4            # GPU out of memory
scriber run folder/ --layout mirror -o out/    # keep folder structure
scriber run talk.mp4 -f srt --config my.toml   # use a specific config file
```

Tips:

- `--speakers N` when you know the count. It improves labels more than anything else.
- `--term` is for technical jargon Whisper mangles. Avoid people's names and rare words: terms are fed to Whisper as a
  prompt, and a rare name there gets hallucinated into unrelated sentences. Fix names afterwards with find and replace.
- `--enhance` only for genuinely noisy audio. On clean audio it can slightly reduce accuracy.
- Speaker labels are generic (`SPEAKER_00`). Find and replace them with names after skimming.

## Preview and automation

- `scriber run --dry-run` lists the files that would be processed and the exact output paths. No models load.
- `scriber run --json` prints one JSON document on stdout and sends logs to stderr:

```json
{
  "exit_code": 0, "dry_run": false, "diarization": true,
  "counts": {"planned": 0, "done": 1, "skipped": 0, "failed": 0},
  "jobs": [{"source": "talk.mp4", "outputs": ["output/talk/talk.txt"], "status": "done", "seconds": 29.8, "error": null}],
  "warnings": []
}
```

- Exit codes: `0` ok, `2` invalid usage or settings, `3` environment problem (ffmpeg missing, config not found,
  `doctor` check failed), `4` at least one file failed (the others were processed).
- `scriber doctor` checks ffmpeg, GPU, token and config. Add `--online` to confirm the token can read the diarization
  model. `scriber describe` prints every option as JSON.

## Speaker labels: Hugging Face token

The diarization models are free but gated.

1. Create an account at huggingface.co and a **read** token (Settings > Access Tokens).
2. Accept the terms at <https://huggingface.co/pyannote/speaker-diarization-community-1>.
3. Put the token in `.env` as `HF_TOKEN=...` (gitignored, see `.env.example`) or set the `HF_TOKEN` (or
   `SCRIBER_HF_TOKEN`) environment variable.
4. `scriber doctor --online` should now report the model as readable.

Revoke and rotate the token at huggingface.co if it ever leaks.

## First run and hardware

- Models download on first use to `~/.cache/huggingface` and `~/.cache/torch` (about 3.5 GB).
- `device = auto` picks CUDA when available, otherwise CPU with int8. CPU works but is many times slower.
- **Windows and Linux (NVIDIA):** `uv sync` installs CUDA 12.8 builds of torch, required for RTX 50-series
  (Blackwell) and fine for other NVIDIA cards. Without an NVIDIA GPU the same install runs on CPU.
- **macOS (Apple Silicon):** `uv sync` installs the regular PyPI torch. Transcription runs on the CPU (int8): the
  Whisper backend (CTranslate2) has no Apple GPU support, so expect it to be several times slower than real time for
  large-v3. Use `--model medium` or `small` for faster results. Intel Macs are not supported (torch 2.8 has no
  wheels for them). Install FFmpeg with `brew install ffmpeg`.

## Troubleshooting

| Symptom | Fix |
|---|---|
| `ffmpeg not found` (exit 3) | Install FFmpeg and reopen the terminal, then `scriber doctor`. |
| No speaker labels, warning about token | Set `HF_TOKEN`, accept the model terms, `scriber doctor --online`. |
| CUDA out of memory | `--batch-size 4`, or `--model medium`, or `--device cpu`. |
| `model.device is 'cuda' but no CUDA GPU` | Use `--device auto` or `cpu`; check drivers; reinstall with `uv sync`. |
| "could not load libtorchcodec" warning | Harmless. Audio is decoded by the ffmpeg CLI, not torchcodec. |
| Repeated or hallucinated sentences | Remove rare names from `--term`; keep `condition_on_previous_text = false`. |
| Wrong language output | Set `-l <code>`, or `-l auto` for mixed collections. |
| `MemoryError` / `mkl_malloc` during model load | The machine is out of free RAM. Close other programs and retry. |
