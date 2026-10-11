"""Environment checks, so a human or an agent can find out what is missing before a long run."""

from __future__ import annotations

import shutil
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from scriber.config import Settings
from scriber.constants import DEVICE_CUDA, FFMPEG, FFPROBE

__all__ = ["Check", "run_checks"]


@dataclass(frozen=True)
class Check:
    name: str
    ok: bool
    detail: str
    blocking: bool = True

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _tool_check(name: str) -> Check:
    found = shutil.which(name)
    return Check(name, found is not None, found or "not on PATH. Install FFmpeg: https://ffmpeg.org/download.html")


def _torch_check(settings: Settings) -> Check:
    try:
        import torch
        import whisperx  # noqa: F401
    except ImportError as exc:
        return Check("python-deps", False, f"cannot import: {exc}. Run `uv sync`.")
    cuda = torch.cuda.is_available()
    device = settings.model.device
    if cuda:
        return Check("compute", True, f"CUDA available: {torch.cuda.get_device_name(0)} (torch {torch.__version__})")
    if device == DEVICE_CUDA:
        return Check("compute", False, "model.device is 'cuda' but no CUDA GPU is available to torch.")
    return Check(
        "compute",
        True,
        "no CUDA GPU: will run on CPU (works, slower; Apple GPUs are not used by the Whisper backend)",
        blocking=False,
    )


def _token_check(settings: Settings) -> Check:
    if settings.hf_token is None:
        return Check("hf-token", False, "HF_TOKEN not set: transcripts will have no speaker labels.", blocking=False)
    return Check("hf-token", True, "set")


def _access_check(settings: Settings) -> Check:
    """Network call: confirms the token can read the gated diarization model."""
    token = settings.hf_token
    model = settings.diarization.model
    if token is None:
        return Check("diarization-access", False, "skipped: no token", blocking=False)
    try:
        from huggingface_hub import HfApi

        HfApi().model_info(model, token=token.get_secret_value())
    except Exception as exc:  # network and auth failures come in many types; report them all the same way
        return Check(
            "diarization-access",
            False,
            f"cannot read {model}: {type(exc).__name__}. Accept its terms on huggingface.co.",
            blocking=False,
        )
    return Check("diarization-access", True, f"can read {model}")


def run_checks(settings: Settings, config_files: list[Path], online: bool) -> list[Check]:
    input_dir = settings.paths.input_dir
    checks = [
        _tool_check(FFMPEG),
        _tool_check(FFPROBE),
        _torch_check(settings),
        _token_check(settings),
        Check("config", True, ", ".join(map(str, config_files)) or "packaged defaults only", blocking=False),
        Check("input-dir", input_dir.is_dir(), f"{input_dir.resolve()}", blocking=False),
    ]
    if online:
        checks.append(_access_check(settings))
    return checks
