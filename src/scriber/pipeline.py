"""WhisperX pipeline: transcribe -> word alignment -> speaker diarization. Models load once per run."""

from __future__ import annotations

import gc
from typing import Any

import torch
import whisperx
from whisperx.diarize import DiarizationPipeline, assign_word_speakers

from scriber.config import Settings
from scriber.constants import AUTO, COMPUTE_TYPE_CPU, COMPUTE_TYPE_CUDA, DEVICE_CPU, DEVICE_CUDA

__all__ = ["Transcriber", "resolve_compute_type", "resolve_device"]


def resolve_device(requested: str) -> str:
    if requested != AUTO:
        return requested
    return DEVICE_CUDA if torch.cuda.is_available() else DEVICE_CPU


def resolve_compute_type(requested: str, device: str) -> str:
    if requested != AUTO:
        return requested
    return COMPUTE_TYPE_CUDA if device == DEVICE_CUDA else COMPUTE_TYPE_CPU


class Transcriber:
    def __init__(self, settings: Settings, glossary: list[str]) -> None:
        cfg = settings.model
        self._settings = settings
        self._device = resolve_device(cfg.device)
        self._language: str | None = None if cfg.language == AUTO else cfg.language
        asr_options: dict[str, Any] = settings.asr.model_dump()
        if glossary:
            asr_options["initial_prompt"] = settings.glossary.prompt_prefix + ", ".join(glossary) + "."
        self._asr = whisperx.load_model(
            cfg.name,
            self._device,
            compute_type=resolve_compute_type(cfg.compute_type, self._device),
            language=self._language,
            asr_options=asr_options,
        )
        self._aligners: dict[str, tuple[Any, Any]] = {}
        token = settings.hf_token
        diar = settings.diarization
        self._diarizer = (
            DiarizationPipeline(model_name=diar.model, token=token.get_secret_value(), device=self._device)
            if token
            else None
        )

    @property
    def diarizes(self) -> bool:
        return self._diarizer is not None

    @property
    def device(self) -> str:
        return self._device

    def _aligner(self, language: str) -> tuple[Any, Any]:
        if language not in self._aligners:
            self._aligners[language] = whisperx.load_align_model(language_code=language, device=self._device)
        return self._aligners[language]

    def run(self, media_path: str) -> dict[str, Any]:
        """Transcribe one audio or video file. Returns the WhisperX result dict (segments, language)."""
        diar = self._settings.diarization
        audio = whisperx.load_audio(media_path)
        result: dict[str, Any] = self._asr.transcribe(
            audio, batch_size=self._settings.model.batch_size, language=self._language
        )
        language = str(result.get("language") or self._language)
        if not result["segments"]:
            return {"segments": [], "language": language}
        model, meta = self._aligner(language)
        result = whisperx.align(result["segments"], model, meta, audio, self._device, return_char_alignments=False)
        if self._diarizer is not None:
            diarization = self._diarizer(
                audio,
                num_speakers=diar.num_speakers,
                min_speakers=diar.min_speakers,
                max_speakers=diar.max_speakers,
            )
            result = assign_word_speakers(diarization, result)
        result["language"] = language
        return result

    def close(self) -> None:
        del self._asr, self._aligners, self._diarizer
        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
