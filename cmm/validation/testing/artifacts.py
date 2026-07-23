from __future__ import annotations

import tempfile
from pathlib import Path
from typing import TYPE_CHECKING, Any, Mapping, Sequence

from cmm.validation.artifacts import ValidationArtifact
from .selection import TestSelection

if TYPE_CHECKING:
    from .pytest_parser import PytestRunSummary, PytestTestCaseResult


def create_pytest_report_paths(scope: str) -> tuple[Path, Path]:
    temp_dir = Path(tempfile.mkdtemp(prefix=f"cmm-pytest-{scope}-"))
    report_path = temp_dir / "pytest-junit.xml"
    return temp_dir, report_path


def build_pytest_artifact(
    *,
    scope: str,
    full_suite: bool,
    confidence: float,
    selection: TestSelection,
    command: Sequence[str],
    summary: PytestRunSummary | None,
    test_cases: Sequence[PytestTestCaseResult],
    related_changes: Mapping[str, tuple[str, ...]],
    metadata: Mapping[str, Any] | None = None,
) -> ValidationArtifact:
    summary_payload = summary.serialize() if summary is not None else {}
    content = {
        "selection": selection.serialize(),
        "command": list(command),
        "tests": [case.serialize() for case in test_cases],
        "summary": summary_payload,
        "related_changes": {key: list(value) for key, value in related_changes.items()},
    }
    metrics = {
        "collected": summary.collected if summary is not None else 0,
        "passed": summary.passed if summary is not None else 0,
        "failed": summary.failed if summary is not None else 0,
        "errors": summary.errors if summary is not None else 0,
        "skipped": summary.skipped if summary is not None else 0,
        "xfailed": summary.xfailed if summary is not None else 0,
        "xpassed": summary.xpassed if summary is not None else 0,
        "duration_ms": summary.duration_ms if summary is not None else 0,
    }
    return ValidationArtifact(
        id=f"pytest-{scope}-report",
        kind="pytest_report",
        source="pytest",
        content=content,
        metrics=metrics,
        metadata={
            "scope": scope,
            "full_suite": full_suite,
            "confidence": confidence,
            **dict(metadata or {}),
        },
    )
