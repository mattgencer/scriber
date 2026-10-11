"""Layered settings: packaged TOML < user TOML < environment (SCRIBER_*) < CLI overrides.

Every default lives in config.default.toml. The models below only declare structure, so a value
can never be defined (and drift) in two places.
"""

from __future__ import annotations

import os
import tomllib
from enum import StrEnum
from pathlib import Path
from typing import Any

from platformdirs import user_config_dir
from pydantic import AliasChoices, BaseModel, ConfigDict, Field, SecretStr, field_validator
from pydantic_settings import (
    BaseSettings,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
    TomlConfigSettingsSource,
)

from scriber.constants import (
    APP_NAME,
    CONFIG_ENV_VAR,
    DEFAULT_CONFIG_NAME,
    DOTENV_FILE,
    ENV_NESTED_DELIMITER,
    ENV_PREFIX,
    HF_TOKEN_ENV_VARS,
    LOCAL_CONFIG_NAME,
    USER_CONFIG_FILE_NAME,
)

__all__ = [
    "ConfigError",
    "Layout",
    "OutputFormat",
    "Settings",
    "default_config_path",
    "load_defaults_dict",
    "load_settings",
    "user_config_files",
    "user_config_path",
]


class ConfigError(Exception):
    """A config file the user asked for is missing or unreadable."""


class OutputFormat(StrEnum):
    TXT = "txt"
    SRT = "srt"
    VTT = "vtt"
    TSV = "tsv"
    JSON = "json"


class Layout(StrEnum):
    PER_FILE_FOLDER = "per-file-folder"
    FLAT = "flat"
    MIRROR = "mirror"


class _Section(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Paths(_Section):
    input_dir: Path = Field(description="Folder scanned when `run` is given no source.")
    output_dir: Path = Field(description="Root folder for all outputs.")

    @field_validator("input_dir", "output_dir")
    @classmethod
    def _expand_home(cls, value: Path) -> Path:
        """`~` works on every OS, including Windows shells that do not expand it."""
        return value.expanduser()


class Output(_Section):
    formats: list[OutputFormat] = Field(description="Output files to write per input: txt, srt, vtt, tsv, json.")
    layout: Layout = Field(description="Where outputs go: per-file-folder, flat, or mirror (keeps input tree).")
    skip_existing: bool = Field(description="Skip an input when all requested outputs already exist.")


class Model(_Section):
    name: str = Field(description="Whisper model name (faster-whisper / CTranslate2).")
    device: str = Field(description="auto, cuda or cpu.")
    compute_type: str = Field(description="auto (float16 on cuda, int8 on cpu) or a CTranslate2 compute type.")
    batch_size: int = Field(description="Inference batch size. Lower it on out-of-memory errors.", gt=0)
    language: str = Field(description="ISO language code, or auto to detect per file.")


class Asr(_Section):
    beam_size: int = Field(description="Whisper beam search width.", gt=0)
    condition_on_previous_text: bool = Field(description="Feed earlier text into later windows (can cascade errors).")
    no_speech_threshold: float = Field(description="Segments above this no-speech probability are dropped.")
    compression_ratio_threshold: float = Field(description="Segments above this gzip ratio are treated as repetition.")


class Diarization(_Section):
    model: str = Field(description="pyannote diarization model (gated on Hugging Face).")
    num_speakers: int | None = Field(default=None, description="Exact speaker count, if known.", gt=0)
    min_speakers: int | None = Field(default=None, description="Minimum speaker count.", gt=0)
    max_speakers: int | None = Field(default=None, description="Maximum speaker count.", gt=0)


class Enhance(_Section):
    enabled: bool = Field(description="Clean up audio with ffmpeg before transcribing (noisy recordings only).")
    ffmpeg_filter: str = Field(description="ffmpeg -af filter chain used for cleanup.")
    sample_rate: int = Field(description="Sample rate in Hz of the cleaned audio.", gt=0)


class Glossary(_Section):
    terms: list[str] = Field(description="Jargon to steer spelling. Avoid rare personal names.")
    prompt_prefix: str = Field(description="Text placed before the terms in the Whisper prompt.")


class Subtitles(_Section):
    highlight_words: bool = Field(description="Underline each word as it is spoken in srt/vtt.")
    max_line_width: int | None = Field(default=None, description="Wrap subtitle lines at this width.", gt=0)
    max_line_count: int | None = Field(default=None, description="Maximum lines per subtitle cue.", gt=0)


class Media(_Section):
    recursive: bool = Field(description="Search folders recursively.")
    audio_extensions: list[str] = Field(description="Audio file extensions picked up when scanning a folder.")
    video_extensions: list[str] = Field(description="Video file extensions picked up when scanning a folder.")

    @property
    def extensions(self) -> frozenset[str]:
        return frozenset(ext.lower() for ext in (*self.audio_extensions, *self.video_extensions))


def default_config_path() -> Path:
    return Path(__file__).with_name(DEFAULT_CONFIG_NAME)


def load_defaults_dict() -> dict[str, Any]:
    """The packaged defaults as plain data (used by `describe`)."""
    with default_config_path().open("rb") as handle:
        return tomllib.load(handle)


def user_config_path() -> Path:
    """Per-user config file in the OS convention (XDG on Linux, Application Support on macOS, AppData on Windows)."""
    return Path(user_config_dir(APP_NAME, appauthor=False)) / USER_CONFIG_FILE_NAME


def user_config_files(explicit: Path | None) -> list[Path]:
    """Config files layered above the packaged defaults, lowest priority first."""
    chosen = explicit or (Path(os.environ[CONFIG_ENV_VAR]) if os.environ.get(CONFIG_ENV_VAR) else None)
    if chosen is not None:
        chosen = chosen.expanduser()
        if not chosen.is_file():
            raise ConfigError(f"Config file not found: {chosen}")
        return [chosen]
    candidates = [user_config_path(), Path(LOCAL_CONFIG_NAME)]
    return [path for path in candidates if path.is_file()]


class Settings(BaseSettings):
    """All settings. Build with `load_settings`, not directly."""

    model_config = SettingsConfigDict(
        env_prefix=ENV_PREFIX,
        env_nested_delimiter=ENV_NESTED_DELIMITER,
        env_file=DOTENV_FILE,
        extra="ignore",
    )

    paths: Paths
    output: Output
    model: Model
    asr: Asr
    diarization: Diarization
    enhance: Enhance
    glossary: Glossary
    subtitles: Subtitles
    media: Media
    hf_token: SecretStr | None = Field(
        default=None,
        validation_alias=AliasChoices(*HF_TOKEN_ENV_VARS),
        description="Hugging Face read token, enables speaker labels. Secret: env or .env only.",
    )


def load_settings(config_file: Path | None = None, overrides: dict[str, Any] | None = None) -> Settings:
    """Resolve settings. `overrides` is a nested dict of CLI values and wins over everything."""
    files = [default_config_path(), *user_config_files(config_file)]

    class _Loaded(Settings):
        @classmethod
        def settings_customise_sources(
            cls,
            settings_cls: type[BaseSettings],
            init_settings: PydanticBaseSettingsSource,
            env_settings: PydanticBaseSettingsSource,
            dotenv_settings: PydanticBaseSettingsSource,
            file_secret_settings: PydanticBaseSettingsSource,
        ) -> tuple[PydanticBaseSettingsSource, ...]:
            toml = TomlConfigSettingsSource(settings_cls, toml_file=files, deep_merge=True)
            return (init_settings, env_settings, dotenv_settings, toml)

    return _Loaded(**(overrides or {}))
