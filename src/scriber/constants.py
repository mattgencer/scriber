"""Structural invariants. Every tunable value lives in config.default.toml and is overridable."""

from __future__ import annotations

from enum import IntEnum
from typing import Final

APP_NAME: Final = "scriber"

# Configuration discovery. Precedence, high to low: CLI flag > environment > user TOML > packaged defaults.
ENV_PREFIX: Final = "SCRIBER_"
ENV_NESTED_DELIMITER: Final = "__"
CONFIG_ENV_VAR: Final = "SCRIBER_CONFIG"
HF_TOKEN_ENV_VARS: Final = ("SCRIBER_HF_TOKEN", "HF_TOKEN")
DOTENV_FILE: Final = ".env"
DEFAULT_CONFIG_NAME: Final = "config.default.toml"
LOCAL_CONFIG_NAME: Final = "scriber.toml"
USER_CONFIG_FILE_NAME: Final = "config.toml"  # inside the OS-specific per-user config dir (platformdirs)

# Names of computed values the config layer resolves at run time.
AUTO: Final = "auto"
DEVICE_CUDA: Final = "cuda"
DEVICE_CPU: Final = "cpu"
COMPUTE_TYPE_CUDA: Final = "float16"
COMPUTE_TYPE_CPU: Final = "int8"

# Files we create next to the media (never picked up as input).
ENHANCED_SUFFIX: Final = ".enhanced.wav"
COLLISION_HASH_LENGTH: Final = 6
# whisperx names every output after the "audio path" it is given; this keeps dots in a stem intact.
WRITER_NAME_SUFFIX: Final = ".src"

# Output text format.
UNKNOWN_SPEAKER: Final = "UNKNOWN"
SECONDS_PER_HOUR: Final = 3600
SECONDS_PER_MINUTE: Final = 60

# Text files are always written with LF and UTF-8, whatever the OS default is.
TEXT_ENCODING: Final = "utf-8"
TEXT_NEWLINE: Final = "\n"

# Tools we shell out to.
FFMPEG: Final = "ffmpeg"
FFPROBE: Final = "ffprobe"
ENHANCE_CHANNELS: Final = 1


class ExitCode(IntEnum):
    OK = 0
    USAGE = 2  # also what Typer returns for bad arguments
    ENVIRONMENT = 3  # missing ffmpeg, unreadable config, failed doctor check
    PARTIAL_FAILURE = 4  # at least one file failed; the rest were processed
