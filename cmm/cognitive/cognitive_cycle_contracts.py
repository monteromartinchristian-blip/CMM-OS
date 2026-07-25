"""Phase 8.15 – Cognitive Cycle Contracts.

Defines immutable contracts, enums, dataclasses, and deterministic ID generators
for the end-to-end cognitive integration cycle.
"""

from __future__ import annotations

import hashlib
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from types import MappingProxyType
from typing import Any

from cmm.cognitive.errors import InvalidCognitiveCycleError


class CognitiveCycleStatus(str, Enum):
    """Execution status of an end-to-end cognitive cycle."""

    CREATED = "created"
    ANALYSING = "analysing"
    CONTRADICTIONS_FOUND = "contradictions_found"
    AWAITING_POLICY = "awaiting_policy"
    EXECUTING = "executing"
    COMPLETED = "completed"
    FAILED = "failed"


def generate_cognitive_cycle_id(
    input_item_ids: Sequence[str] | Iterable[str],
    created_at: datetime | str | None = None,
    contradiction_ids: Sequence[str] | Iterable[str] | None = None,
    resolution_proposal_ids: Sequence[str] | Iterable[str] | None = None,
    execution_ids: Sequence[str] | Iterable[str] | None = None,
    status: CognitiveCycleStatus | str | None = None,
) -> str:
    """Generate a deterministic cognitive identifier for an integrated cognitive cycle.

    Format:
        cognitive-cycle:<sha256_hash>
    """
    if input_item_ids is None:
        raise InvalidCognitiveCycleError("input_item_ids cannot be None")

    if isinstance(input_item_ids, (str, bytes)):
        raise InvalidCognitiveCycleError(
            "input_item_ids must be an iterable of strings"
        )

    sorted_inputs = sorted(str(x).strip() for x in input_item_ids if str(x).strip())
    if not sorted_inputs:
        raise InvalidCognitiveCycleError(
            "input_item_ids must contain at least one non-empty string"
        )

    ts_str = ""
    if created_at is not None:
        if isinstance(created_at, datetime):
            ts_str = created_at.isoformat()
        else:
            ts_str = str(created_at).strip()

    sorted_cntrs = sorted(
        str(x).strip() for x in (contradiction_ids or ()) if str(x).strip()
    )
    sorted_props = sorted(
        str(x).strip() for x in (resolution_proposal_ids or ()) if str(x).strip()
    )

    st_str = ""
    if status is not None:
        st_str = (
            status.value
            if isinstance(status, CognitiveCycleStatus)
            else str(status).strip()
        )

    seed_parts = [
        ",".join(sorted_inputs),
        ts_str,
        ",".join(sorted_cntrs),
        ",".join(sorted_props),
        st_str,
    ]
    seed = "|".join(seed_parts)
    digest = hashlib.sha256(seed.encode("utf-8")).hexdigest()[:16]
    return f"cognitive-cycle:{digest}"


@dataclass(frozen=True, slots=True)
class CognitiveCycleRecord:
    """Immutable audit record of an end-to-end cognitive cycle execution."""

    cycle_id: str
    created_at: datetime
    input_item_ids: tuple[str, ...]
    contradiction_ids: tuple[str, ...]
    resolution_proposal_ids: tuple[str, ...]
    execution_ids: tuple[str, ...]
    memory_entry_ids: tuple[str, ...]
    reflection_report_id: str | None
    status: CognitiveCycleStatus
    warnings: tuple[str, ...] = ()
    metadata: Mapping[str, Any] = field(default_factory=lambda: MappingProxyType({}))

    def __post_init__(self) -> None:
        """Enforce strict validation and deep immutability."""
        if not isinstance(self.cycle_id, str) or not self.cycle_id.strip():
            raise InvalidCognitiveCycleError("cycle_id must be a non-empty string")
        if not self.cycle_id.startswith("cognitive-cycle:"):
            raise InvalidCognitiveCycleError(
                f"cycle_id must start with 'cognitive-cycle:', got '{self.cycle_id}'"
            )

        if not isinstance(self.created_at, datetime):
            raise InvalidCognitiveCycleError("created_at must be a datetime instance")
        if self.created_at.tzinfo is None:
            raise InvalidCognitiveCycleError("created_at must be timezone-aware")

        # Validate tuples
        for field_name, val in (
            ("input_item_ids", self.input_item_ids),
            ("contradiction_ids", self.contradiction_ids),
            ("resolution_proposal_ids", self.resolution_proposal_ids),
            ("execution_ids", self.execution_ids),
            ("memory_entry_ids", self.memory_entry_ids),
            ("warnings", self.warnings),
        ):
            if not isinstance(val, (tuple, list)):
                raise InvalidCognitiveCycleError(
                    f"{field_name} must be a tuple or list of strings"
                )
            converted = []
            for item in val:
                if not isinstance(item, str) or not item.strip():
                    raise InvalidCognitiveCycleError(
                        f"All elements in {field_name} must be non-empty strings"
                    )
                converted.append(item.strip())
            object.__setattr__(self, field_name, tuple(converted))

        if self.reflection_report_id is not None and (
            not isinstance(self.reflection_report_id, str)
            or not self.reflection_report_id.strip()
        ):
            raise InvalidCognitiveCycleError(
                "reflection_report_id must be a non-empty string if provided"
            )

        if isinstance(self.status, str):
            try:
                object.__setattr__(self, "status", CognitiveCycleStatus(self.status))
            except ValueError as exc:
                raise InvalidCognitiveCycleError(
                    f"Invalid CognitiveCycleStatus string: '{self.status}'"
                ) from exc
        elif not isinstance(self.status, CognitiveCycleStatus):
            raise InvalidCognitiveCycleError(
                f"status must be a CognitiveCycleStatus enum, got {type(self.status).__name__}"
            )

        # Metadata immutability
        if self.metadata is None:
            meta_proxy = MappingProxyType({})
        elif isinstance(self.metadata, Mapping):
            meta_dict = dict(self.metadata)
            for k in meta_dict:
                if not isinstance(k, str):
                    raise InvalidCognitiveCycleError("Metadata keys must be strings")
            meta_proxy = MappingProxyType(meta_dict)
        else:
            raise InvalidCognitiveCycleError("metadata must be a Mapping instance")

        object.__setattr__(self, "metadata", meta_proxy)

    def serialize(self) -> dict[str, Any]:
        """Serialize record to dictionary."""
        return {
            "cycle_id": self.cycle_id,
            "created_at": self.created_at.isoformat(),
            "input_item_ids": list(self.input_item_ids),
            "contradiction_ids": list(self.contradiction_ids),
            "resolution_proposal_ids": list(self.resolution_proposal_ids),
            "execution_ids": list(self.execution_ids),
            "memory_entry_ids": list(self.memory_entry_ids),
            "reflection_report_id": self.reflection_report_id,
            "status": self.status.value,
            "warnings": list(self.warnings),
            "metadata": dict(self.metadata),
        }

    def to_dict(self) -> dict[str, Any]:
        """Alias for serialize()."""
        return self.serialize()

    @classmethod
    def from_mapping(cls, mapping: Mapping[str, Any]) -> CognitiveCycleRecord:
        """Construct a CognitiveCycleRecord from a mapping."""
        if not isinstance(mapping, Mapping):
            raise InvalidCognitiveCycleError("mapping must be a Mapping instance")

        required_keys = {
            "cycle_id",
            "created_at",
            "input_item_ids",
            "contradiction_ids",
            "resolution_proposal_ids",
            "execution_ids",
            "memory_entry_ids",
            "reflection_report_id",
            "status",
        }
        missing = required_keys - set(mapping.keys())
        if missing:
            raise InvalidCognitiveCycleError(
                f"Missing required fields in mapping: {sorted(missing)}"
            )

        raw_created = mapping["created_at"]
        if isinstance(raw_created, datetime):
            created_at = raw_created
        elif isinstance(raw_created, str):
            try:
                created_at = datetime.fromisoformat(raw_created)
            except ValueError as exc:
                raise InvalidCognitiveCycleError(
                    f"Invalid isoformat datetime string: '{raw_created}'"
                ) from exc
        else:
            raise InvalidCognitiveCycleError(
                "created_at must be an ISO string or datetime"
            )

        raw_status = mapping["status"]
        if isinstance(raw_status, CognitiveCycleStatus):
            status = raw_status
        elif isinstance(raw_status, str):
            try:
                status = CognitiveCycleStatus(raw_status)
            except ValueError as exc:
                raise InvalidCognitiveCycleError(
                    f"Invalid status value: '{raw_status}'"
                ) from exc
        else:
            raise InvalidCognitiveCycleError(
                "status must be a CognitiveCycleStatus or string"
            )

        return cls(
            cycle_id=str(mapping["cycle_id"]),
            created_at=created_at,
            input_item_ids=tuple(mapping.get("input_item_ids", ())),
            contradiction_ids=tuple(mapping.get("contradiction_ids", ())),
            resolution_proposal_ids=tuple(mapping.get("resolution_proposal_ids", ())),
            execution_ids=tuple(mapping.get("execution_ids", ())),
            memory_entry_ids=tuple(mapping.get("memory_entry_ids", ())),
            reflection_report_id=mapping.get("reflection_report_id"),
            status=status,
            warnings=tuple(mapping.get("warnings", ())),
            metadata=mapping.get("metadata") or {},
        )

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CognitiveCycleRecord:
        """Alias for from_mapping()."""
        return cls.from_mapping(data)
