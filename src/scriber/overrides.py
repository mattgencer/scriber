"""Which CLI flags override which setting. Shared by the CLI and `describe` so they cannot drift."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

__all__ = ["OVERRIDES", "Override", "nest"]


@dataclass(frozen=True)
class Override:
    option: str  # parameter name on the `run` command
    flag: str  # human-facing flag(s), for docs and `describe`
    key: str  # dotted settings path


OVERRIDES: tuple[Override, ...] = (
    Override("output", "--output / -o", "paths.output_dir"),
    Override("formats", "--format / -f (repeatable)", "output.formats"),
    Override("layout", "--layout", "output.layout"),
    Override("skip_existing", "--skip-existing / --overwrite", "output.skip_existing"),
    Override("recursive", "--recursive / --no-recursive", "media.recursive"),
    Override("enhance", "--enhance / --no-enhance", "enhance.enabled"),
    Override("model", "--model", "model.name"),
    Override("device", "--device", "model.device"),
    Override("language", "--language / -l", "model.language"),
    Override("batch_size", "--batch-size", "model.batch_size"),
    Override("speakers", "--speakers", "diarization.num_speakers"),
    Override("min_speakers", "--min-speakers", "diarization.min_speakers"),
    Override("max_speakers", "--max-speakers", "diarization.max_speakers"),
)


def nest(values: dict[str, Any]) -> dict[str, Any]:
    """{'a.b': 1, 'a.c': None} -> {'a': {'b': 1}}. None means 'flag not given' and is dropped."""
    tree: dict[str, Any] = {}
    for dotted, value in values.items():
        if value is None:
            continue
        *parents, leaf = dotted.split(".")
        node = tree
        for part in parents:
            node = node.setdefault(part, {})
        node[leaf] = value
    return tree
