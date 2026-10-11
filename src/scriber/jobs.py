"""Planning: map input media to output paths according to the configured layout. Pure, no models."""

from __future__ import annotations

import hashlib
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from scriber.config import Layout, OutputFormat, Settings
from scriber.constants import COLLISION_HASH_LENGTH
from scriber.media import MediaFile

__all__ = ["Job", "plan_jobs"]


@dataclass(frozen=True)
class Job:
    media: MediaFile
    out_dir: Path
    name: str
    formats: tuple[OutputFormat, ...]

    def output_path(self, fmt: OutputFormat) -> Path:
        return self.out_dir / f"{self.name}.{fmt.value}"

    @property
    def outputs(self) -> list[Path]:
        return [self.output_path(fmt) for fmt in self.formats]

    @property
    def complete(self) -> bool:
        return all(path.exists() for path in self.outputs)


def _destination(layout: Layout, output_root: Path, item: MediaFile, name: str) -> Path:
    if layout is Layout.FLAT:
        return output_root
    if layout is Layout.MIRROR:
        try:
            return output_root / item.path.parent.relative_to(item.root)
        except ValueError:
            return output_root
    return output_root / name


def _short_hash(path: Path) -> str:
    return hashlib.sha256(str(path.resolve()).encode("utf-8")).hexdigest()[:COLLISION_HASH_LENGTH]


def plan_jobs(files: list[MediaFile], settings: Settings) -> list[Job]:
    """One job per input. Inputs that would share an output path get a short hash suffix, so none is overwritten."""
    layout = settings.output.layout
    root = settings.paths.output_dir
    formats = tuple(dict.fromkeys(settings.output.formats))
    keys = [(_destination(layout, root, f, f.path.stem), f.path.stem) for f in files]
    clashes = Counter(keys)
    jobs = []
    for item, (out_dir, name) in zip(files, keys, strict=True):
        if clashes[(out_dir, name)] > 1:
            name = f"{name}-{_short_hash(item.path)}"
            out_dir = _destination(layout, root, item, name)
        jobs.append(Job(item, out_dir, name, formats))
    return jobs
