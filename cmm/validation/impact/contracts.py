from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Mapping

from cmm.validation.artifacts import ValidationArtifact
from cmm.validation.findings import ValidationFinding
from cmm.validation.errors import ValidationContractError


def _as_path(value: Path | str | None) -> Path | None:
    if value is None:
        return None
    return Path(str(value))


def _as_tuple(value: Any) -> tuple[Any, ...]:
    if value is None:
        return ()
    if isinstance(value, tuple):
        return value
    if isinstance(value, list):
        return tuple(value)
    return (value,)


class ChangeType(str, Enum):
    UNKNOWN = "unknown"
    NEW_FILE = "new_file"
    DELETED_FILE = "deleted_file"
    RENAMED_FILE = "renamed_file"
    IMPORT_CHANGE = "import_change"
    SYMBOL_CHANGE = "symbol_change"
    PUBLIC_API_CHANGE = "public_api_change"
    STRUCTURAL_CHANGE = "structural_change"


class FileChangeKind(str, Enum):
    ADDED = "added"
    MODIFIED = "modified"
    DELETED = "deleted"
    RENAMED = "renamed"
    UNKNOWN = "unknown"


class SymbolChangeKind(str, Enum):
    ADDED = "added"
    MODIFIED = "modified"
    DELETED = "deleted"


class ImportChangeKind(str, Enum):
    ADDED = "added"
    REMOVED = "removed"
    MODIFIED = "modified"


class PublicAPIChangeKind(str, Enum):
    ADDED = "added"
    REMOVED = "removed"
    CHANGED = "changed"


@dataclass(frozen=True, slots=True)
class FileVersion:
    path: Path
    exists: bool
    content_hash: str
    source: str
    content: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.source not in {"before", "after"}:
            raise ValidationContractError(
                "FileVersion.source must be 'before' or 'after'"
            )
        if not self.content_hash and self.exists:
            raise ValidationContractError(
                "FileVersion.content_hash must not be empty for existing files"
            )
        object.__setattr__(self, "path", Path(str(self.path)))
        object.__setattr__(self, "metadata", dict(self.metadata or {}))

    def serialize(self) -> dict[str, Any]:
        return {
            "path": str(self.path),
            "exists": self.exists,
            "content_hash": self.content_hash,
            "source": self.source,
            "content": self.content,
            "metadata": dict(self.metadata or {}),
        }

    @classmethod
    def from_mapping(cls, payload: Mapping[str, Any]) -> "FileVersion":
        return cls(
            path=Path(str(payload["path"])),
            exists=bool(payload["exists"]),
            content_hash=str(payload.get("content_hash", "")),
            source=str(payload.get("source", "after")),
            content=payload.get("content"),
            metadata=dict(payload.get("metadata", {}))
            if isinstance(payload.get("metadata"), Mapping)
            else {},
        )


@dataclass(frozen=True, slots=True)
class FileChange:
    before_path: Path | None
    after_path: Path | None
    kind: FileChangeKind
    before: FileVersion | None = None
    after: FileVersion | None = None
    confidence: float = 0.0
    reasons: tuple[str, ...] = ()
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not 0.0 <= self.confidence <= 1.0:
            raise ValidationContractError(
                "FileChange.confidence must be between 0 and 1"
            )
        object.__setattr__(self, "before_path", _as_path(self.before_path))
        object.__setattr__(self, "after_path", _as_path(self.after_path))
        object.__setattr__(
            self, "reasons", tuple(str(item) for item in self.reasons or ())
        )
        object.__setattr__(self, "metadata", dict(self.metadata or {}))

    def serialize(self) -> dict[str, Any]:
        return {
            "before_path": None if self.before_path is None else str(self.before_path),
            "after_path": None if self.after_path is None else str(self.after_path),
            "kind": self.kind.value,
            "before": None if self.before is None else self.before.serialize(),
            "after": None if self.after is None else self.after.serialize(),
            "confidence": self.confidence,
            "reasons": list(self.reasons),
            "metadata": dict(self.metadata or {}),
        }

    @classmethod
    def from_mapping(cls, payload: Mapping[str, Any]) -> "FileChange":
        before = payload.get("before")
        after = payload.get("after")
        return cls(
            before_path=payload.get("before_path"),
            after_path=payload.get("after_path"),
            kind=FileChangeKind(str(payload.get("kind", "unknown"))),
            before=None if before is None else FileVersion.from_mapping(before),
            after=None if after is None else FileVersion.from_mapping(after),
            confidence=float(payload.get("confidence", 0.0)),
            reasons=tuple(str(item) for item in payload.get("reasons", ())),
            metadata=dict(payload.get("metadata", {}))
            if isinstance(payload.get("metadata"), Mapping)
            else {},
        )


@dataclass(frozen=True, slots=True)
class SymbolChange:
    module: str
    symbol: str
    kind: SymbolChangeKind
    confidence: float = 0.0
    before_signature: str | None = None
    after_signature: str | None = None
    before_decorators: tuple[str, ...] = ()
    after_decorators: tuple[str, ...] = ()
    before_bases: tuple[str, ...] = ()
    after_bases: tuple[str, ...] = ()
    public_before: bool = True
    public_after: bool = True
    reasons: tuple[str, ...] = ()
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not 0.0 <= self.confidence <= 1.0:
            raise ValidationContractError(
                "SymbolChange.confidence must be between 0 and 1"
            )
        object.__setattr__(
            self, "before_decorators", tuple(self.before_decorators or ())
        )
        object.__setattr__(self, "after_decorators", tuple(self.after_decorators or ()))
        object.__setattr__(self, "before_bases", tuple(self.before_bases or ()))
        object.__setattr__(self, "after_bases", tuple(self.after_bases or ()))
        object.__setattr__(
            self, "reasons", tuple(str(item) for item in self.reasons or ())
        )
        object.__setattr__(self, "metadata", dict(self.metadata or {}))

    def serialize(self) -> dict[str, Any]:
        return {
            "module": self.module,
            "symbol": self.symbol,
            "kind": self.kind.value,
            "confidence": self.confidence,
            "before_signature": self.before_signature,
            "after_signature": self.after_signature,
            "before_decorators": list(self.before_decorators),
            "after_decorators": list(self.after_decorators),
            "before_bases": list(self.before_bases),
            "after_bases": list(self.after_bases),
            "public_before": self.public_before,
            "public_after": self.public_after,
            "reasons": list(self.reasons),
            "metadata": dict(self.metadata or {}),
        }

    @classmethod
    def from_mapping(cls, payload: Mapping[str, Any]) -> "SymbolChange":
        return cls(
            module=str(payload["module"]),
            symbol=str(payload["symbol"]),
            kind=SymbolChangeKind(str(payload.get("kind", "modified"))),
            confidence=float(payload.get("confidence", 0.0)),
            before_signature=payload.get("before_signature"),
            after_signature=payload.get("after_signature"),
            before_decorators=tuple(
                str(item) for item in payload.get("before_decorators", ())
            ),
            after_decorators=tuple(
                str(item) for item in payload.get("after_decorators", ())
            ),
            before_bases=tuple(str(item) for item in payload.get("before_bases", ())),
            after_bases=tuple(str(item) for item in payload.get("after_bases", ())),
            public_before=bool(payload.get("public_before", True)),
            public_after=bool(payload.get("public_after", True)),
            reasons=tuple(str(item) for item in payload.get("reasons", ())),
            metadata=dict(payload.get("metadata", {}))
            if isinstance(payload.get("metadata"), Mapping)
            else {},
        )


@dataclass(frozen=True, slots=True)
class ImportChange:
    module: str
    imported_module: str
    kind: ImportChangeKind
    confidence: float = 0.0
    imported_symbol: str | None = None
    alias: str | None = None
    before: str | None = None
    after: str | None = None
    reasons: tuple[str, ...] = ()
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not 0.0 <= self.confidence <= 1.0:
            raise ValidationContractError(
                "ImportChange.confidence must be between 0 and 1"
            )
        object.__setattr__(
            self, "reasons", tuple(str(item) for item in self.reasons or ())
        )
        object.__setattr__(self, "metadata", dict(self.metadata or {}))

    def serialize(self) -> dict[str, Any]:
        return {
            "module": self.module,
            "imported_module": self.imported_module,
            "kind": self.kind.value,
            "confidence": self.confidence,
            "imported_symbol": self.imported_symbol,
            "alias": self.alias,
            "before": self.before,
            "after": self.after,
            "reasons": list(self.reasons),
            "metadata": dict(self.metadata or {}),
        }

    @classmethod
    def from_mapping(cls, payload: Mapping[str, Any]) -> "ImportChange":
        return cls(
            module=str(payload["module"]),
            imported_module=str(payload["imported_module"]),
            kind=ImportChangeKind(str(payload.get("kind", "modified"))),
            confidence=float(payload.get("confidence", 0.0)),
            imported_symbol=payload.get("imported_symbol"),
            alias=payload.get("alias"),
            before=payload.get("before"),
            after=payload.get("after"),
            reasons=tuple(str(item) for item in payload.get("reasons", ())),
            metadata=dict(payload.get("metadata", {}))
            if isinstance(payload.get("metadata"), Mapping)
            else {},
        )


@dataclass(frozen=True, slots=True)
class PublicAPIChange:
    module: str
    added: tuple[str, ...] = ()
    removed: tuple[str, ...] = ()
    changed: tuple[str, ...] = ()
    confidence: float = 0.0
    reasons: tuple[str, ...] = ()
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not 0.0 <= self.confidence <= 1.0:
            raise ValidationContractError(
                "PublicAPIChange.confidence must be between 0 and 1"
            )
        object.__setattr__(self, "added", tuple(str(item) for item in self.added or ()))
        object.__setattr__(
            self, "removed", tuple(str(item) for item in self.removed or ())
        )
        object.__setattr__(
            self, "changed", tuple(str(item) for item in self.changed or ())
        )
        object.__setattr__(
            self, "reasons", tuple(str(item) for item in self.reasons or ())
        )
        object.__setattr__(self, "metadata", dict(self.metadata or {}))

    def serialize(self) -> dict[str, Any]:
        return {
            "module": self.module,
            "added": list(self.added),
            "removed": list(self.removed),
            "changed": list(self.changed),
            "confidence": self.confidence,
            "reasons": list(self.reasons),
            "metadata": dict(self.metadata or {}),
        }

    @classmethod
    def from_mapping(cls, payload: Mapping[str, Any]) -> "PublicAPIChange":
        return cls(
            module=str(payload["module"]),
            added=tuple(str(item) for item in payload.get("added", ())),
            removed=tuple(str(item) for item in payload.get("removed", ())),
            changed=tuple(str(item) for item in payload.get("changed", ())),
            confidence=float(payload.get("confidence", 0.0)),
            reasons=tuple(str(item) for item in payload.get("reasons", ())),
            metadata=dict(payload.get("metadata", {}))
            if isinstance(payload.get("metadata"), Mapping)
            else {},
        )


@dataclass(frozen=True, slots=True)
class DependencyEdge:
    source: str
    target: str
    kind: str = "import"
    confidence: float = 1.0

    def serialize(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "target": self.target,
            "kind": self.kind,
            "confidence": self.confidence,
        }

    @classmethod
    def from_mapping(cls, payload: Mapping[str, Any]) -> "DependencyEdge":
        return cls(
            source=str(payload["source"]),
            target=str(payload["target"]),
            kind=str(payload.get("kind", "import")),
            confidence=float(payload.get("confidence", 1.0)),
        )


@dataclass(frozen=True, slots=True)
class DependencyGraph:
    modules: tuple[str, ...]
    edges: tuple[DependencyEdge, ...]
    confidence: float = 1.0
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not 0.0 <= self.confidence <= 1.0:
            raise ValidationContractError(
                "DependencyGraph.confidence must be between 0 and 1"
            )
        object.__setattr__(
            self, "modules", tuple(sorted(str(item) for item in self.modules))
        )
        object.__setattr__(self, "edges", tuple(self.edges or ()))
        object.__setattr__(self, "metadata", dict(self.metadata or {}))

    def dependencies_of(self, module: str) -> tuple[str, ...]:
        return tuple(
            sorted(edge.target for edge in self.edges if edge.source == module)
        )

    def dependents_of(self, module: str) -> tuple[str, ...]:
        return tuple(
            sorted(edge.source for edge in self.edges if edge.target == module)
        )

    def serialize(self) -> dict[str, Any]:
        return {
            "modules": list(self.modules),
            "edges": [edge.serialize() for edge in self.edges],
            "confidence": self.confidence,
            "metadata": dict(self.metadata or {}),
        }

    @classmethod
    def from_mapping(cls, payload: Mapping[str, Any]) -> "DependencyGraph":
        return cls(
            modules=tuple(str(item) for item in payload.get("modules", ())),
            edges=tuple(
                DependencyEdge.from_mapping(item) for item in payload.get("edges", ())
            ),
            confidence=float(payload.get("confidence", 1.0)),
            metadata=dict(payload.get("metadata", {}))
            if isinstance(payload.get("metadata"), Mapping)
            else {},
        )


@dataclass(frozen=True, slots=True)
class ProjectSnapshot:
    root: Path
    source: str
    files: tuple[FileVersion, ...]
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "root", Path(str(self.root)))
        object.__setattr__(self, "files", tuple(self.files or ()))
        object.__setattr__(self, "metadata", dict(self.metadata or {}))

    def serialize(self) -> dict[str, Any]:
        return {
            "root": str(self.root),
            "source": self.source,
            "files": [item.serialize() for item in self.files],
            "metadata": dict(self.metadata or {}),
        }

    @classmethod
    def from_mapping(cls, payload: Mapping[str, Any]) -> "ProjectSnapshot":
        return cls(
            root=Path(str(payload["root"])),
            source=str(payload.get("source", "snapshot")),
            files=tuple(
                FileVersion.from_mapping(item) for item in payload.get("files", ())
            ),
            metadata=dict(payload.get("metadata", {}))
            if isinstance(payload.get("metadata"), Mapping)
            else {},
        )


@dataclass(frozen=True, slots=True)
class ChangeSet:
    project_root: Path
    before_root: Path | None
    after_root: Path | None
    file_changes: tuple[FileChange, ...]
    change_type: ChangeType
    confidence: float
    requires_full_suite: bool
    source: str = "snapshots"
    symbol_changes: tuple[SymbolChange, ...] = ()
    import_changes: tuple[ImportChange, ...] = ()
    public_api_changes: tuple[PublicAPIChange, ...] = ()
    dependency_graph: DependencyGraph | None = None
    uncertainty: tuple[str, ...] = ()
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not 0.0 <= self.confidence <= 1.0:
            raise ValidationContractError(
                "ChangeSet.confidence must be between 0 and 1"
            )
        object.__setattr__(self, "project_root", Path(str(self.project_root)))
        object.__setattr__(self, "before_root", _as_path(self.before_root))
        object.__setattr__(self, "after_root", _as_path(self.after_root))
        object.__setattr__(self, "file_changes", tuple(self.file_changes or ()))
        object.__setattr__(self, "symbol_changes", tuple(self.symbol_changes or ()))
        object.__setattr__(self, "import_changes", tuple(self.import_changes or ()))
        object.__setattr__(
            self, "public_api_changes", tuple(self.public_api_changes or ())
        )
        object.__setattr__(
            self, "uncertainty", tuple(str(item) for item in self.uncertainty or ())
        )
        object.__setattr__(self, "metadata", dict(self.metadata or {}))

    @property
    def changed_files(self) -> tuple[Path, ...]:
        paths = [item.after_path or item.before_path for item in self.file_changes]
        return tuple(sorted({path for path in paths if path is not None}, key=str))

    @property
    def has_python_changes(self) -> bool:
        return any(str(path).endswith(".py") for path in self.changed_files)

    def serialize(self) -> dict[str, Any]:
        return {
            "project_root": str(self.project_root),
            "before_root": None if self.before_root is None else str(self.before_root),
            "after_root": None if self.after_root is None else str(self.after_root),
            "file_changes": [item.serialize() for item in self.file_changes],
            "change_type": self.change_type.value,
            "confidence": self.confidence,
            "requires_full_suite": self.requires_full_suite,
            "source": self.source,
            "symbol_changes": [item.serialize() for item in self.symbol_changes],
            "import_changes": [item.serialize() for item in self.import_changes],
            "public_api_changes": [
                item.serialize() for item in self.public_api_changes
            ],
            "dependency_graph": None
            if self.dependency_graph is None
            else self.dependency_graph.serialize(),
            "uncertainty": list(self.uncertainty),
            "metadata": dict(self.metadata or {}),
            "changed_files": [str(path) for path in self.changed_files],
        }

    @classmethod
    def from_mapping(cls, payload: Mapping[str, Any]) -> "ChangeSet":
        dependency_graph = payload.get("dependency_graph")
        return cls(
            project_root=Path(str(payload["project_root"])),
            before_root=payload.get("before_root"),
            after_root=payload.get("after_root"),
            file_changes=tuple(
                FileChange.from_mapping(item)
                for item in payload.get("file_changes", ())
            ),
            change_type=ChangeType(str(payload.get("change_type", "unknown"))),
            confidence=float(payload.get("confidence", 0.0)),
            requires_full_suite=bool(payload.get("requires_full_suite", False)),
            source=str(payload.get("source", "snapshots")),
            symbol_changes=tuple(
                SymbolChange.from_mapping(item)
                for item in payload.get("symbol_changes", ())
            ),
            import_changes=tuple(
                ImportChange.from_mapping(item)
                for item in payload.get("import_changes", ())
            ),
            public_api_changes=tuple(
                PublicAPIChange.from_mapping(item)
                for item in payload.get("public_api_changes", ())
            ),
            dependency_graph=None
            if dependency_graph is None
            else DependencyGraph.from_mapping(dependency_graph),
            uncertainty=tuple(str(item) for item in payload.get("uncertainty", ())),
            metadata=dict(payload.get("metadata", {}))
            if isinstance(payload.get("metadata"), Mapping)
            else {},
        )


@dataclass(frozen=True, slots=True)
class ChangeImpactResult:
    change_type: ChangeType
    affected_modules: tuple[str, ...]
    affected_symbols: tuple[str, ...]
    affected_tests: tuple[str, ...]
    public_api_changed: bool
    confidence: float
    requires_full_suite: bool
    findings: tuple[ValidationFinding, ...] = ()
    artifacts: tuple[ValidationArtifact, ...] = ()
    uncertainty: tuple[str, ...] = ()
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not 0.0 <= self.confidence <= 1.0:
            raise ValidationContractError(
                "ChangeImpactResult.confidence must be between 0 and 1"
            )
        object.__setattr__(
            self,
            "affected_modules",
            tuple(sorted(str(item) for item in self.affected_modules or ())),
        )
        object.__setattr__(
            self,
            "affected_symbols",
            tuple(sorted(str(item) for item in self.affected_symbols or ())),
        )
        object.__setattr__(
            self,
            "affected_tests",
            tuple(sorted(str(item) for item in self.affected_tests or ())),
        )
        object.__setattr__(self, "findings", tuple(self.findings or ()))
        object.__setattr__(self, "artifacts", tuple(self.artifacts or ()))
        object.__setattr__(
            self, "uncertainty", tuple(str(item) for item in self.uncertainty or ())
        )
        object.__setattr__(self, "metadata", dict(self.metadata or {}))

    def serialize(self) -> dict[str, Any]:
        return {
            "change_type": self.change_type.value,
            "affected_modules": list(self.affected_modules),
            "affected_symbols": list(self.affected_symbols),
            "affected_tests": list(self.affected_tests),
            "public_api_changed": self.public_api_changed,
            "confidence": self.confidence,
            "requires_full_suite": self.requires_full_suite,
            "findings": [item.serialize() for item in self.findings],
            "artifacts": [item.serialize() for item in self.artifacts],
            "uncertainty": list(self.uncertainty),
            "metadata": dict(self.metadata or {}),
        }

    @classmethod
    def from_mapping(cls, payload: Mapping[str, Any]) -> "ChangeImpactResult":
        return cls(
            change_type=ChangeType(str(payload.get("change_type", "unknown"))),
            affected_modules=tuple(
                str(item) for item in payload.get("affected_modules", ())
            ),
            affected_symbols=tuple(
                str(item) for item in payload.get("affected_symbols", ())
            ),
            affected_tests=tuple(
                str(item) for item in payload.get("affected_tests", ())
            ),
            public_api_changed=bool(payload.get("public_api_changed", False)),
            confidence=float(payload.get("confidence", 0.0)),
            requires_full_suite=bool(payload.get("requires_full_suite", False)),
            findings=tuple(
                item
                for item in payload.get("findings", ())
                if isinstance(item, ValidationFinding)
            ),
            artifacts=tuple(
                item
                for item in payload.get("artifacts", ())
                if isinstance(item, ValidationArtifact)
            ),
            uncertainty=tuple(str(item) for item in payload.get("uncertainty", ())),
            metadata=dict(payload.get("metadata", {}))
            if isinstance(payload.get("metadata"), Mapping)
            else {},
        )
