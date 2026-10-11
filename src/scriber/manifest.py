"""Run result: what was processed, skipped or failed. Serialises to the `--json` contract."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from scriber.constants import ExitCode

__all__ = ["JobResult", "JobStatus", "Manifest"]


class JobStatus(StrEnum):
    PLANNED = "planned"
    DONE = "done"
    SKIPPED = "skipped"
    FAILED = "failed"


@dataclass
class JobResult:
    source: str
    outputs: list[str]
    status: JobStatus
    seconds: float | None = None
    error: str | None = None


@dataclass
class Manifest:
    dry_run: bool
    diarization: bool | None = None
    jobs: list[JobResult] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def count(self, status: JobStatus) -> int:
        return sum(1 for job in self.jobs if job.status is status)

    @property
    def exit_code(self) -> ExitCode:
        return ExitCode.PARTIAL_FAILURE if self.count(JobStatus.FAILED) else ExitCode.OK

    def to_dict(self) -> dict[str, Any]:
        return {
            "exit_code": int(self.exit_code),
            "dry_run": self.dry_run,
            "diarization": self.diarization,
            "counts": {status.value: self.count(status) for status in JobStatus},
            "jobs": [
                {
                    "source": job.source,
                    "outputs": job.outputs,
                    "status": job.status.value,
                    "seconds": job.seconds,
                    "error": job.error,
                }
                for job in self.jobs
            ],
            "warnings": self.warnings,
        }
