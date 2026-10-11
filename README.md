# scriber

Transcribe audio **and video** to text, subtitles and JSON, with speaker labels. Everything runs on your own machine:
your media never leaves it.

Under the hood: [WhisperX](https://github.com/m-bain/whisperX) (Whisper large-v3 via faster-whisper, word-level
alignment) plus pyannote speaker diarization. Works on an NVIDIA GPU (fast) or CPU (slower, including Apple Silicon Macs).

## Install

Requirements: Python 3.13, [uv](https://docs.astral.sh/uv/), [FFmpeg](https://ffmpeg.org/download.html) on `PATH`
(`winget install Gyan.FFmpeg`, `brew install ffmpeg`, `apt install ffmpeg`).
Platforms: Windows and Linux (NVIDIA GPU recommended, CPU works), macOS on Apple Silicon (CPU only, slower).

```bash
git clone <this repo> && cd scriber
uv sync                      # installs torch (CUDA 12.8 build) + whisperx into .venv
uv tool install .            # optional: puts `scriber` on your PATH
```

Speaker labels need a free Hugging Face token. Without one, you still get transcripts, just without labels.
Setup is in [docs/USAGE.md](docs/USAGE.md#speaker-labels-hugging-face-token).

## 60-second quickstart

```bash
scriber doctor                        # check ffmpeg, GPU, token
mkdir input && cp talk.mp4 input/     # any audio or video file
scriber run                           # transcribes everything in ./input into ./output
```

Results land in `output/talk/talk.txt` (readable, with speakers and timestamps), `talk.srt` and `talk.json`.

```text
[00:00:00] SPEAKER_00: Welcome to the weekly meeting.

[00:00:04] SPEAKER_01: Thanks, glad to be here.
```

Already-transcribed files are skipped on re-runs. Pass `--overwrite` to redo them.

## Common commands

```bash
scriber run talk.mp4                          # one file, any location
scriber run recordings/ -o transcripts/       # a folder (recursive), custom output folder
scriber run "videos/*.mkv" --speakers 2       # a glob, known speaker count
scriber run call.m4a --enhance -t Kubernetes  # noisy audio, steer spelling of jargon
scriber run talk.mp4 -f srt -f vtt --layout flat   # subtitles only, no per-file folders
scriber run --dry-run                         # show what would run, load nothing
scriber run --json                            # machine-readable result on stdout
```

## Documentation

| Doc | What is in it |
|---|---|
| [docs/USAGE.md](docs/USAGE.md) | Recipes, output formats and layouts, speaker labels, troubleshooting |
| [docs/CONFIGURATION.md](docs/CONFIGURATION.md) | Every setting, its env var and CLI flag, config file, precedence |
| [docs/AI.md](docs/AI.md) and [AGENTS.md](AGENTS.md) | Driving scriber from an AI agent (what to ask, what to run) |

## Configuration in one paragraph

Defaults ship in the package. Override them, lowest to highest priority, with a `scriber.toml` file, `SCRIBER_*`
environment variables (e.g. `SCRIBER_MODEL__DEVICE=cpu`), or CLI flags. Nothing is hard-coded.
Details in [docs/CONFIGURATION.md](docs/CONFIGURATION.md).

## Privacy

Models run locally; after the first model download no network access is needed except an optional token check.
`input/`, `output/`, `.env` and `scriber.toml` are gitignored so personal media and transcripts are not committed by
accident. Treat your Hugging Face token as a secret: keep it in `.env` or the environment, never in `scriber.toml`.

## Development

```bash
uv run pytest                                   # unit tests, no GPU needed
uv run ruff check . && uv run ruff format --check . && uv run mypy src
```

Tests generate their own tiny audio and video with ffmpeg, so the repo contains no recordings.

## License

MIT, see [LICENSE](LICENSE).
