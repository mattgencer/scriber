# Configuration

Every tunable value is a setting with a packaged default. Nothing is hard-coded in the source.

## Precedence

Highest wins:

1. **CLI flag** (`scriber run --device cpu`)
2. **Environment variable** (`SCRIBER_MODEL__DEVICE=cpu`, also read from a `.env` file in the working directory)
3. **User config file** (`scriber.toml`, see below)
4. **Packaged defaults** ([`src/scriber/config.default.toml`](../src/scriber/config.default.toml))

Files are merged key by key, so a user file only needs the keys it changes.

## Config file

Searched in this order; the later file overrides the earlier one:

1. Per-user file in your OS's standard config folder (per user):
   - Linux: `~/.config/scriber/config.toml` (honours `XDG_CONFIG_HOME`)
   - macOS: `~/Library/Application Support/scriber/config.toml`
   - Windows: `%LOCALAPPDATA%\scriber\config.toml`
2. `./scriber.toml` (per project, gitignored)

`scriber doctor` prints which config files were loaded. Paths in config files and arguments may start with `~`
(expanded on every OS) and are otherwise relative to the folder you run `scriber` from. Both `/` and `\` separators
work on Windows. Text outputs are always UTF-8 with LF line endings, whatever the OS.

Or choose one explicitly with `--config path.toml` or `SCRIBER_CONFIG=path.toml`. An explicit file replaces the
search and must exist (otherwise exit code 3).

```toml
# scriber.toml
[paths]
input_dir = "media"
output_dir = "transcripts"

[output]
formats = ["txt", "srt"]
layout = "mirror"

[model]
language = "auto"
batch_size = 8

[glossary]
terms = ["Kubernetes", "OAuth"]
```

## Environment variables

`SCRIBER_<SECTION>__<KEY>` (double underscore between section and key), case-insensitive. Lists use JSON:

```bash
SCRIBER_MODEL__DEVICE=cpu
SCRIBER_OUTPUT__FORMATS='["txt","json"]'
SCRIBER_PATHS__OUTPUT_DIR=/data/transcripts
```

The Hugging Face token is a secret and is **only** read from the environment or `.env`: `SCRIBER_HF_TOKEN` or the
standard `HF_TOKEN`. Do not put it in a TOML file.

## Settings reference

| Key | Default | CLI flag | Meaning |
|---|---|---|---|
| `paths.input_dir` | `input` | (positional SOURCE) | Folder scanned when `run` gets no source |
| `paths.output_dir` | `output` | `-o`, `--output` | Root folder for all outputs |
| `output.formats` | `["txt","srt","json"]` | `-f`, `--format` (repeat) | `txt`, `srt`, `vtt`, `tsv`, `json` |
| `output.layout` | `per-file-folder` | `--layout` | `per-file-folder`, `flat`, `mirror` |
| `output.skip_existing` | `true` | `--skip-existing / --overwrite` | Skip inputs whose outputs all exist |
| `media.recursive` | `true` | `--recursive / --no-recursive` | Recurse into folders |
| `media.audio_extensions` | see file | | Audio extensions picked up in folder scans |
| `media.video_extensions` | see file | | Video extensions picked up in folder scans |
| `model.name` | `large-v3` | `--model` | Whisper model (faster-whisper name) |
| `model.device` | `auto` | `--device` | `auto`, `cuda`, `cpu` |
| `model.compute_type` | `auto` | | `auto` = float16 on CUDA, int8 on CPU; or a CTranslate2 type |
| `model.batch_size` | `16` | `--batch-size` | Lower on out-of-memory |
| `model.language` | `en` | `-l`, `--language` | ISO code or `auto` |
| `asr.beam_size` | `5` | | Beam search width |
| `asr.condition_on_previous_text` | `false` | | Feed earlier text to later windows |
| `asr.no_speech_threshold` | `0.6` | | Drop segments above this no-speech probability |
| `asr.compression_ratio_threshold` | `2.4` | | Treat higher gzip ratios as repetition |
| `diarization.model` | `pyannote/speaker-diarization-community-1` | | Gated model, needs the token |
| `diarization.num_speakers` | unset | `--speakers` | Exact speaker count |
| `diarization.min_speakers` | unset | `--min-speakers` | Lower bound |
| `diarization.max_speakers` | unset | `--max-speakers` | Upper bound |
| `enhance.enabled` | `false` | `--enhance / --no-enhance` | ffmpeg cleanup before transcribing |
| `enhance.ffmpeg_filter` | highpass, denoise, loudness | | ffmpeg `-af` chain |
| `enhance.sample_rate` | `16000` | | Hz of the cleaned audio |
| `glossary.terms` | `[]` | `-t`, `--term` (repeat, appended) | Jargon hints for Whisper |
| `glossary.prompt_prefix` | `Terms and names: ` | | Text before the terms in the prompt |
| `subtitles.highlight_words` | `false` | | Per-word highlighting in srt/vtt |
| `subtitles.max_line_width` | unset | | Wrap subtitle lines |
| `subtitles.max_line_count` | unset | | Max lines per cue |
| `hf_token` | unset | | Secret. `HF_TOKEN` or `SCRIBER_HF_TOKEN` only |

`scriber describe` prints this table as JSON, generated from the code, so it is always accurate. If this table and
`describe` ever disagree, `describe` is right.

Invalid values (for example `batch_size = 0`) are rejected with a clear message and exit code 2.
