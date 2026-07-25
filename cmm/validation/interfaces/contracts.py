"""Application API data contracts for CMM OS Validation (Phase 7.12)."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .errors import ValidationInvalidRequestError


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _assert_path_within_root(path: Path, root: Path) -> Path:
    """Ensure *path* is within *root* and return its normalized path relative to root if possible."""
    resolved_root = root.resolve()
    resolved_path = (
        (root / path).resolve() if not path.is_absolute() else path.resolve()
    )
    try:
        resolved_path.relative_to(resolved_root)
    except ValueError as exc:
        raise ValidationInvalidRequestError(
            f"Path '{path}' escapes project root '{root}'. Path traversal is prohibited.",
            details={"path": str(path), "project_root": str(root)},
        ) from exc
    return resolved_path


@dataclass(slots=True)
class StartValidationRequest:
    """Contract for starting a validation run."""

    project_root: Path = field(default_factory=Path.cwd)
    policy_name: str | None = None
    steps: tuple[str, ...] | None = None
    files: tuple[Path, ...] | None = None
    use_git_changes: bool = False
    actor: str | None = None
    metadata: dict[str, Any] | None = None
    persist: bool = True
    execution_mode: str = "local"
    request_id: str | None = None

    def __post_init__(self) -> None:
        root = Path(self.project_root).resolve()
        if not root.exists() or not root.is_dir():
            raise ValidationInvalidRequestError(
                f"Project root '{self.project_root}' does not exist or is not a directory.",
                details={"project_root": str(self.project_root)},
            )
        object.__setattr__(self, "project_root", root)

        if self.files is not None:
            validated_files: list[Path] = []
            for f in self.files:
                p = Path(f)
                _assert_path_within_root(p, root)
                validated_files.append(p)
            object.__setattr__(self, "files", tuple(validated_files))

        if self.steps is not None:
            object.__setattr__(self, "steps", tuple(str(s) for s in self.steps))

        if self.metadata is not None:
            if not isinstance(self.metadata, dict):
                raise ValidationInvalidRequestError(
                    "Metadata must be a dictionary.",
                    details={"metadata": type(self.metadata).__name__},
                )
            object.__setattr__(self, "metadata", dict(self.metadata))

    def serialize(self) -> dict[str, Any]:
        return {
            "project_root": str(self.project_root),
            "policy_name": self.policy_name,
            "steps": list(self.steps) if self.steps is not None else None,
            "files": [str(f) for f in self.files] if self.files is not None else None,
            "use_git_changes": self.use_git_changes,
            "actor": self.actor,
            "metadata": dict(self.metadata or {}),
            "persist": self.persist,
            "execution_mode": self.execution_mode,
            "request_id": self.request_id,
        }

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any]) -> StartValidationRequest:
        files_raw = data.get("files")
        files = tuple(Path(f) for f in files_raw) if files_raw is not None else None
        steps_raw = data.get("steps")
        steps = tuple(str(s) for s in steps_raw) if steps_raw is not None else None
        return cls(
            project_root=Path(data.get("project_root", Path.cwd())),
            policy_name=data.get("policy_name"),
            steps=steps,
            files=files,
            use_git_changes=bool(data.get("use_git_changes", False)),
            actor=data.get("actor"),
            metadata=dict(data.get("metadata") or {}) if data.get("metadata") else None,
            persist=bool(data.get("persist", True)),
            execution_mode=str(data.get("execution_mode", "local")),
            request_id=data.get("request_id"),
        )


@dataclass(slots=True)
class CancelValidationRequest:
    """Contract for requesting cancellation of an active validation run."""

    validation_id: str

    def serialize(self) -> dict[str, Any]:
        return {"validation_id": self.validation_id}

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any]) -> CancelValidationRequest:
        return cls(validation_id=str(data["validation_id"]))


@dataclass(slots=True)
class ValidationStatusResponse:
    """Contract representing current status of a validation execution."""

    validation_id: str
    status: str
    policy: str | None = None
    actor: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    duration_ms: int | None = None
    gate_allowed: bool | None = None
    commit_hash: str | None = None

    def serialize(self) -> dict[str, Any]:
        return {
            "validation_id": self.validation_id,
            "status": self.status,
            "policy": self.policy,
            "actor": self.actor,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat()
            if self.completed_at
            else None,
            "duration_ms": self.duration_ms,
            "gate_allowed": self.gate_allowed,
            "commit_hash": self.commit_hash,
        }

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any]) -> ValidationStatusResponse:
        def _parse_dt(raw: Any) -> datetime | None:
            if isinstance(raw, str):
                return datetime.fromisoformat(raw)
            if isinstance(raw, datetime):
                return raw
            return None

        return cls(
            validation_id=str(data["validation_id"]),
            status=str(data["status"]),
            policy=data.get("policy"),
            actor=data.get("actor"),
            started_at=_parse_dt(data.get("started_at")),
            completed_at=_parse_dt(data.get("completed_at")),
            duration_ms=data.get("duration_ms"),
            gate_allowed=data.get("gate_allowed"),
            commit_hash=data.get("commit_hash"),
        )


@dataclass(slots=True)
class ValidationResultResponse:
    """Contract representing complete validation run execution results."""

    validation_id: str
    status: str
    policy: str
    steps: tuple[dict[str, Any], ...] = ()
    artifacts: tuple[dict[str, Any], ...] = ()
    blocking_findings: tuple[dict[str, Any], ...] = ()
    warnings: tuple[dict[str, Any], ...] = ()
    duration_ms: int = 0
    started_at: datetime | None = None
    completed_at: datetime | None = None
    can_commit: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)

    def serialize(self) -> dict[str, Any]:
        return {
            "validation_id": self.validation_id,
            "status": self.status,
            "policy": self.policy,
            "steps": list(self.steps),
            "artifacts": list(self.artifacts),
            "blocking_findings": list(self.blocking_findings),
            "warnings": list(self.warnings),
            "duration_ms": self.duration_ms,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat()
            if self.completed_at
            else None,
            "can_commit": self.can_commit,
            "metadata": dict(self.metadata or {}),
        }

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any]) -> ValidationResultResponse:
        def _parse_dt(raw: Any) -> datetime | None:
            if isinstance(raw, str):
                return datetime.fromisoformat(raw)
            if isinstance(raw, datetime):
                return raw
            return None

        return cls(
            validation_id=str(data.get("validation_id") or data.get("id")),
            status=str(data.get("status")),
            policy=str(data.get("policy")),
            steps=tuple(dict(s) for s in data.get("steps", ())),
            artifacts=tuple(dict(a) for a in data.get("artifacts", ())),
            blocking_findings=tuple(dict(f) for f in data.get("blocking_findings", ())),
            warnings=tuple(dict(f) for f in data.get("warnings", ())),
            duration_ms=int(data.get("duration_ms", 0)),
            started_at=_parse_dt(data.get("started_at")),
            completed_at=_parse_dt(data.get("completed_at")),
            can_commit=bool(data.get("can_commit", False)),
            metadata=dict(data.get("metadata") or {}),
        )


@dataclass(slots=True)
class ValidationArtifactResponse:
    """Contract representing a stored validation artifact."""

    id: str
    kind: str
    source: str
    path: str | None = None
    size_bytes: int = 0
    content: dict[str, Any] = field(default_factory=dict)
    findings: tuple[dict[str, Any], ...] = ()
    metrics: dict[str, Any] = field(default_factory=dict)
    created_at: datetime | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def serialize(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "kind": self.kind,
            "source": self.source,
            "path": self.path,
            "size_bytes": self.size_bytes,
            "content": dict(self.content or {}),
            "findings": list(self.findings),
            "metrics": dict(self.metrics or {}),
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "metadata": dict(self.metadata or {}),
        }

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any]) -> ValidationArtifactResponse:
        created_at_raw = data.get("created_at")
        created_at = (
            datetime.fromisoformat(created_at_raw)
            if isinstance(created_at_raw, str)
            else (created_at_raw if isinstance(created_at_raw, datetime) else None)
        )
        content_dict = dict(data.get("content") or {})
        size = len(str(content_dict).encode("utf-8"))
        return cls(
            id=str(data["id"]),
            kind=str(data["kind"]),
            source=str(data["source"]),
            path=str(data["path"]) if data.get("path") else None,
            size_bytes=int(data.get("size_bytes", size)),
            content=content_dict,
            findings=tuple(dict(f) for f in data.get("findings", ())),
            metrics=dict(data.get("metrics") or {}),
            created_at=created_at,
            metadata=dict(data.get("metadata") or {}),
        )


@dataclass(slots=True)
class ValidationGateResponse:
    """Contract representing Commit Gate evaluation for a validation run."""

    allowed: bool
    reasons: tuple[dict[str, Any], ...]
    blocking_findings: tuple[dict[str, Any], ...]
    validation_result_id: str
    commit_created: bool = False
    commit_hash: str | None = None

    def serialize(self) -> dict[str, Any]:
        return {
            "allowed": self.allowed,
            "reasons": list(self.reasons),
            "blocking_findings": list(self.blocking_findings),
            "validation_result_id": self.validation_result_id,
            "commit_created": self.commit_created,
            "commit_hash": self.commit_hash,
        }

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any]) -> ValidationGateResponse:
        return cls(
            allowed=bool(data["allowed"]),
            reasons=tuple(dict(r) for r in data.get("reasons", ())),
            blocking_findings=tuple(dict(f) for f in data.get("blocking_findings", ())),
            validation_result_id=str(data["validation_result_id"]),
            commit_created=bool(data.get("commit_created", False)),
            commit_hash=data.get("commit_hash"),
        )


__all__ = [
    "CancelValidationRequest",
    "StartValidationRequest",
    "ValidationArtifactResponse",
    "ValidationGateResponse",
    "ValidationResultResponse",
    "ValidationStatusResponse",
]
