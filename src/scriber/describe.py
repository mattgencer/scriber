"""Machine-readable description of the tool, generated from the Settings model so it cannot drift."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel
from pydantic.fields import FieldInfo

from scriber.config import Layout, OutputFormat, Settings, load_defaults_dict
from scriber.constants import (
    CONFIG_ENV_VAR,
    ENV_NESTED_DELIMITER,
    ENV_PREFIX,
    HF_TOKEN_ENV_VARS,
    LOCAL_CONFIG_NAME,
    ExitCode,
)
from scriber.overrides import OVERRIDES

__all__ = ["build_description", "iter_settings"]

SECRET_FIELDS = frozenset({"hf_token"})


def _model_type(annotation: Any) -> type[BaseModel] | None:
    return annotation if isinstance(annotation, type) and issubclass(annotation, BaseModel) else None


def iter_settings(
    model: type[BaseModel] = Settings, prefix: tuple[str, ...] = ()
) -> list[tuple[tuple[str, ...], FieldInfo]]:
    """Every leaf setting as (path, field)."""
    leaves: list[tuple[tuple[str, ...], FieldInfo]] = []
    for name, info in model.model_fields.items():
        section = _model_type(info.annotation)
        if section is not None:
            leaves.extend(iter_settings(section, (*prefix, name)))
        else:
            leaves.append(((*prefix, name), info))
    return leaves


def _default_for(path: tuple[str, ...], defaults: dict[str, Any]) -> Any:
    node: Any = defaults
    for part in path:
        if not isinstance(node, dict) or part not in node:
            return None
        node = node[part]
    return node


def _jsonable(value: Any) -> Any:
    if isinstance(value, list):
        return [_jsonable(item) for item in value]
    return str(value) if not isinstance(value, str | int | float | bool | type(None)) else value


def build_description() -> dict[str, Any]:
    defaults = load_defaults_dict()
    flags = {override.key: override.flag for override in OVERRIDES}
    settings = []
    for path, info in iter_settings():
        dotted = ".".join(path)
        secret = path[-1] in SECRET_FIELDS
        env = list(HF_TOKEN_ENV_VARS) if secret else [ENV_PREFIX + ENV_NESTED_DELIMITER.join(path).upper()]
        settings.append(
            {
                "key": dotted,
                "type": str(info.annotation).replace("typing.", ""),
                "default": None if secret else _jsonable(_default_for(path, defaults)),
                "env": env,
                "cli_flag": flags.get(dotted),
                "description": info.description,
                "secret": secret,
            }
        )
    return {
        "tool": "scriber",
        "purpose": "Transcribe audio and video files to text, subtitles and JSON, with speaker labels. Runs locally.",
        "commands": {
            "run": "scriber run [SOURCE...] [options]. SOURCE is a file, folder or glob; default is paths.input_dir.",
            "doctor": "scriber doctor [--json] [--online]. Verifies ffmpeg, GPU, token, config. Exit 3 if blocking.",
            "describe": "scriber describe. Prints this document.",
        },
        "extra_run_flags": {
            "--term / -t": "Add a glossary term (repeatable). Appended to glossary.terms.",
            "--config": f"Config file. Also {CONFIG_ENV_VAR}. Else ./{LOCAL_CONFIG_NAME}.",
            "--dry-run": "Plan only: list inputs and output paths, load no models.",
            "--json": "Print one JSON manifest on stdout. Logs go to stderr.",
            "--verbose / -v": "Debug logging.",
        },
        "precedence": ["cli flag", "environment (SCRIBER_*)", "user toml", "packaged defaults"],
        "output_formats": [fmt.value for fmt in OutputFormat],
        "layouts": [layout.value for layout in Layout],
        "exit_codes": {code.name.lower(): int(code) for code in ExitCode},
        "settings": settings,
    }
