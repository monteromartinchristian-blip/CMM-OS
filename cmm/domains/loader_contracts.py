"""Phase 10.4 – Domain Loader Contracts.

Immutable, JSON-serializable, type-safe contracts describing the result
of a single loader operation (load/unload/reload) and a structural
snapshot of loader state.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from functools import cmp_to_key
from types import MappingProxyType
from typing import Any

from cmm.domains.contracts import _ensure_tz_aware, _reject_unknown_fields
from cmm.domains.discovery_contracts import DomainCandidate
from cmm.domains.enums import DomainLoadStatus
from cmm.domains.errors import (
    DomainContractValidationError,
    DomainSerializationError,
)
from cmm.domains.pack import DomainPack
from cmm.domains.registry_contracts import (
    DomainRegistryRecord,
    _reject_sensitive_keys,
    _validate_json_safe_metadata,
)


def _coerce_load_status(value: Any, field_name: str) -> DomainLoadStatus:
    if isinstance(value, DomainLoadStatus):
        return value
    if isinstance(value, str):
        try:
            return DomainLoadStatus(value)
        except ValueError as exc:
            raise DomainContractValidationError(
                f"Invalid DomainLoadStatus for {field_name}: {value!r}",
                field=field_name,
            ) from exc
    raise DomainContractValidationError(
        f"{field_name} must be a DomainLoadStatus or string, got {type(value).__name__}",
        field=field_name,
    )


def _require_str_tuple_strict(raw: Any, field_name: str) -> tuple[str, ...]:
    if raw is None:
        return ()
    if isinstance(raw, str):
        raise DomainContractValidationError(
            f"{field_name} must be a sequence of strings, not a string",
            field=field_name,
        )
    if not isinstance(raw, (list, tuple)):
        raise DomainContractValidationError(
            f"{field_name} must be a list or tuple", field=field_name
        )
    result: list[str] = []
    for i, item in enumerate(raw):
        if not isinstance(item, str) or not item.strip():
            raise DomainContractValidationError(
                f"{field_name}[{i}] must be a non-empty string",
                field=field_name,
                details={"index": i},
            )
        result.append(item)
    return tuple(result)


# ── DomainLoadResult ─────────────────────────────────────────────────────────

_LOAD_RESULT_KNOWN = frozenset(
    {
        "candidate",
        "status",
        "pack",
        "registry_record",
        "errors",
        "warnings",
        "loaded_at",
        "metadata",
    }
)


@dataclass(frozen=True, slots=True)
class DomainLoadResult:
    """Immutable outcome of a single loader operation."""

    candidate: DomainCandidate
    status: DomainLoadStatus
    pack: DomainPack | None
    registry_record: DomainRegistryRecord | None
    errors: tuple[str, ...]
    warnings: tuple[str, ...]
    loaded_at: datetime
    metadata: Mapping[str, Any] = field(default_factory=lambda: MappingProxyType({}))

    def __post_init__(self) -> None:
        if isinstance(self.candidate, Mapping):
            object.__setattr__(
                self, "candidate", DomainCandidate.from_dict(dict(self.candidate))
            )
        elif not isinstance(self.candidate, DomainCandidate):
            raise DomainContractValidationError(
                "candidate must be a DomainCandidate or mapping", field="candidate"
            )

        object.__setattr__(self, "status", _coerce_load_status(self.status, "status"))

        if self.pack is not None and isinstance(self.pack, Mapping):
            object.__setattr__(self, "pack", DomainPack.from_dict(dict(self.pack)))
        elif self.pack is not None and not isinstance(self.pack, DomainPack):
            raise DomainContractValidationError(
                "pack must be a DomainPack, mapping, or None", field="pack"
            )

        if self.registry_record is not None and isinstance(
            self.registry_record, Mapping
        ):
            object.__setattr__(
                self,
                "registry_record",
                DomainRegistryRecord.from_dict(dict(self.registry_record)),
            )
        elif self.registry_record is not None and not isinstance(
            self.registry_record, DomainRegistryRecord
        ):
            raise DomainContractValidationError(
                "registry_record must be a DomainRegistryRecord, mapping, or None",
                field="registry_record",
            )

        object.__setattr__(
            self, "errors", _require_str_tuple_strict(self.errors, "errors")
        )
        object.__setattr__(
            self, "warnings", _require_str_tuple_strict(self.warnings, "warnings")
        )

        object.__setattr__(
            self, "loaded_at", _ensure_tz_aware(self.loaded_at, "loaded_at")
        )

        meta = _validate_json_safe_metadata(self.metadata, "metadata")
        _reject_sensitive_keys(meta, "metadata")
        object.__setattr__(self, "metadata", meta)

        # ── Invariants ───────────────────────────────────────────────────
        if self.status == DomainLoadStatus.LOADED and (
            self.pack is None or self.registry_record is None
        ):
            raise DomainContractValidationError(
                "status=LOADED requires both pack and registry_record",
                field="status",
            )
        if (
            self.status in (DomainLoadStatus.FAILED, DomainLoadStatus.REJECTED)
            and not self.errors
        ):
            raise DomainContractValidationError(
                f"status={self.status.value} requires at least one error",
                field="errors",
            )
        if self.status == DomainLoadStatus.UNLOADED and (
            self.pack is not None or self.registry_record is not None
        ):
            raise DomainContractValidationError(
                "status=UNLOADED must not carry an active pack or registry_record",
                field="status",
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "candidate": self.candidate.to_dict(),
            "status": self.status.value,
            "pack": self.pack.to_dict() if self.pack is not None else None,
            "registry_record": self.registry_record.to_dict()
            if self.registry_record is not None
            else None,
            "errors": list(self.errors),
            "warnings": list(self.warnings),
            "loaded_at": self.loaded_at.isoformat(),
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DomainLoadResult:
        if not isinstance(data, Mapping):
            raise DomainSerializationError(
                "DomainLoadResult.from_dict requires a mapping", field="data"
            )
        _reject_unknown_fields(data, _LOAD_RESULT_KNOWN, "DomainLoadResult")
        required = {"candidate", "status", "errors", "warnings", "loaded_at"}
        missing = required - set(data.keys())
        if missing:
            raise DomainSerializationError(
                f"DomainLoadResult.from_dict missing required fields: {sorted(missing)}",
                field="data",
            )
        loaded_raw = data["loaded_at"]
        if isinstance(loaded_raw, datetime):
            loaded_at = loaded_raw
        elif isinstance(loaded_raw, str):
            try:
                loaded_at = datetime.fromisoformat(loaded_raw)
            except ValueError as exc:
                raise DomainSerializationError(
                    f"Invalid isoformat datetime for loaded_at: {loaded_raw!r}",
                    field="loaded_at",
                ) from exc
        else:
            raise DomainSerializationError(
                "loaded_at must be a datetime or ISO string", field="loaded_at"
            )
        try:
            return cls(
                candidate=data["candidate"],
                status=data["status"],
                pack=data.get("pack"),
                registry_record=data.get("registry_record"),
                errors=tuple(data.get("errors", ())),
                warnings=tuple(data.get("warnings", ())),
                loaded_at=loaded_at,
                metadata=data.get("metadata", {}),
            )
        except DomainContractValidationError as exc:
            raise DomainSerializationError(
                exc.message, field=exc.field, details=dict(exc.details)
            ) from exc


def _compare_load_results(left: DomainLoadResult, right: DomainLoadResult) -> int:
    left_key = (left.candidate.candidate_id, left.loaded_at)
    right_key = (right.candidate.candidate_id, right.loaded_at)
    if left_key != right_key:
        return -1 if left_key < right_key else 1
    return 0


def _compare_candidates_for_snapshot(
    left: DomainCandidate, right: DomainCandidate
) -> int:
    if left.candidate_id != right.candidate_id:
        return -1 if left.candidate_id < right.candidate_id else 1
    return 0


# ── DomainLoaderSnapshot ─────────────────────────────────────────────────────

_SNAPSHOT_KNOWN = frozenset(
    {"known_candidates", "load_results", "captured_at", "snapshot_version"}
)


@dataclass(frozen=True, slots=True)
class DomainLoaderSnapshot:
    """Immutable, structural snapshot of loader state.

    Never includes handles, imported modules, or mutable objects.
    """

    known_candidates: tuple[DomainCandidate, ...]
    load_results: tuple[DomainLoadResult, ...]
    captured_at: datetime
    snapshot_version: str = "10.4.0"

    def __post_init__(self) -> None:
        if not isinstance(self.known_candidates, (list, tuple)):
            raise DomainContractValidationError(
                "known_candidates must be a list or tuple", field="known_candidates"
            )
        for c in self.known_candidates:
            if not isinstance(c, DomainCandidate):
                raise DomainContractValidationError(
                    "known_candidates items must be DomainCandidate",
                    field="known_candidates",
                )
        object.__setattr__(
            self,
            "known_candidates",
            tuple(
                sorted(
                    self.known_candidates,
                    key=cmp_to_key(_compare_candidates_for_snapshot),
                )
            ),
        )

        if not isinstance(self.load_results, (list, tuple)):
            raise DomainContractValidationError(
                "load_results must be a list or tuple", field="load_results"
            )
        for r in self.load_results:
            if not isinstance(r, DomainLoadResult):
                raise DomainContractValidationError(
                    "load_results items must be DomainLoadResult", field="load_results"
                )
        object.__setattr__(
            self,
            "load_results",
            tuple(sorted(self.load_results, key=cmp_to_key(_compare_load_results))),
        )

        object.__setattr__(
            self, "captured_at", _ensure_tz_aware(self.captured_at, "captured_at")
        )
        if not isinstance(self.snapshot_version, str) or not self.snapshot_version:
            raise DomainContractValidationError(
                "snapshot_version must be a non-empty string",
                field="snapshot_version",
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "known_candidates": [c.to_dict() for c in self.known_candidates],
            "load_results": [r.to_dict() for r in self.load_results],
            "captured_at": self.captured_at.isoformat(),
            "snapshot_version": self.snapshot_version,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DomainLoaderSnapshot:
        if not isinstance(data, Mapping):
            raise DomainSerializationError(
                "DomainLoaderSnapshot.from_dict requires a mapping", field="data"
            )
        _reject_unknown_fields(data, _SNAPSHOT_KNOWN, "DomainLoaderSnapshot")
        required = {"known_candidates", "load_results", "captured_at"}
        missing = required - set(data.keys())
        if missing:
            raise DomainSerializationError(
                f"DomainLoaderSnapshot.from_dict missing required fields: {sorted(missing)}",
                field="data",
            )
        captured_raw = data["captured_at"]
        if isinstance(captured_raw, datetime):
            captured_at = captured_raw
        elif isinstance(captured_raw, str):
            try:
                captured_at = datetime.fromisoformat(captured_raw)
            except ValueError as exc:
                raise DomainSerializationError(
                    f"Invalid isoformat datetime for captured_at: {captured_raw!r}",
                    field="captured_at",
                ) from exc
        else:
            raise DomainSerializationError(
                "captured_at must be a datetime or ISO string", field="captured_at"
            )
        known_candidates = tuple(
            DomainCandidate.from_dict(dict(c)) for c in data["known_candidates"]
        )
        load_results = tuple(
            DomainLoadResult.from_dict(dict(r)) for r in data["load_results"]
        )
        return cls(
            known_candidates=known_candidates,
            load_results=load_results,
            captured_at=captured_at,
            snapshot_version=data.get("snapshot_version", "10.4.0"),
        )


__all__ = [
    "DomainLoadResult",
    "DomainLoaderSnapshot",
]
