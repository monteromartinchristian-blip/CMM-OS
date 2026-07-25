"""Phase 8.6 – Knowledge Query contracts.

Defines immutable, typed, and serializable contracts for expressing queries and
structured query results against the Knowledge Store.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from types import MappingProxyType
from typing import Any

from cmm.cognitive.enums import (
    KnowledgeKind,
    KnowledgeRelationKind,
    KnowledgeStatus,
    SensitivityLevel,
)
from cmm.cognitive.errors import InvalidKnowledgeQueryError
from cmm.cognitive.knowledge import KnowledgeItem


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _require_aware_query(value: datetime | None, field_name: str) -> None:
    if value is not None:
        if not isinstance(value, datetime):
            raise InvalidKnowledgeQueryError(
                f"{field_name} must be a datetime instance"
            )
        if value.tzinfo is None:
            raise InvalidKnowledgeQueryError(
                f"{field_name} must be timezone-aware when provided"
            )


class KnowledgeOrderField(str, Enum):
    CREATED_AT = "created_at"
    UPDATED_AT = "updated_at"
    CONFIDENCE = "confidence"
    KIND = "kind"
    STATUS = "status"
    ID = "id"


class SortDirection(str, Enum):
    ASC = "asc"
    DESC = "desc"


@dataclass(frozen=True, slots=True)
class KnowledgeQuery:
    """Immutable, typed query specification for retrieving KnowledgeItems."""

    kinds: tuple[KnowledgeKind, ...] = ()
    statuses: tuple[KnowledgeStatus, ...] = ()
    resource_ids: tuple[str, ...] = ()
    actor_ids: tuple[str, ...] = ()
    sensitivities: tuple[SensitivityLevel, ...] = ()
    created_from: datetime | None = None
    created_until: datetime | None = None
    updated_from: datetime | None = None
    updated_until: datetime | None = None
    valid_at: datetime | None = None
    include_expired: bool = True
    include_superseded: bool = True
    include_invalidated: bool = True
    has_evidence: bool | None = None
    has_relations: bool | None = None
    relation_kinds: tuple[KnowledgeRelationKind, ...] = ()
    text_contains: str | None = None
    limit: int | None = None
    offset: int = 0
    order_by: KnowledgeOrderField = KnowledgeOrderField.CREATED_AT
    order_direction: SortDirection = SortDirection.DESC
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.limit is not None and (
            not isinstance(self.limit, int)
            or isinstance(self.limit, bool)
            or self.limit < 0
        ):
            raise InvalidKnowledgeQueryError("limit must be a non-negative integer")

        if (
            not isinstance(self.offset, int)
            or isinstance(self.offset, bool)
            or self.offset < 0
        ):
            raise InvalidKnowledgeQueryError("offset must be a non-negative integer")

        _require_aware_query(self.created_from, "created_from")
        _require_aware_query(self.created_until, "created_until")
        _require_aware_query(self.updated_from, "updated_from")
        _require_aware_query(self.updated_until, "updated_until")
        _require_aware_query(self.valid_at, "valid_at")

        if (
            self.created_from is not None
            and self.created_until is not None
            and self.created_until < self.created_from
        ):
            raise InvalidKnowledgeQueryError(
                "created_until cannot be before created_from"
            )

        if (
            self.updated_from is not None
            and self.updated_until is not None
            and self.updated_until < self.updated_from
        ):
            raise InvalidKnowledgeQueryError(
                "updated_until cannot be before updated_from"
            )

        if self.text_contains is not None:
            if not isinstance(self.text_contains, str):
                raise InvalidKnowledgeQueryError("text_contains must be a string")
            if not self.text_contains.strip():
                raise InvalidKnowledgeQueryError(
                    "text_contains must not be empty or whitespace only"
                )

        # Normalize kinds
        kinds_norm: list[KnowledgeKind] = []
        for k in self.kinds or ():
            if isinstance(k, KnowledgeKind):
                kinds_norm.append(k)
            elif isinstance(k, str):
                try:
                    kinds_norm.append(KnowledgeKind(k))
                except ValueError as exc:
                    raise InvalidKnowledgeQueryError(
                        f"Invalid KnowledgeKind: {k}"
                    ) from exc
            else:
                raise InvalidKnowledgeQueryError(f"Invalid KnowledgeKind: {k}")
        object.__setattr__(self, "kinds", tuple(kinds_norm))

        # Normalize statuses
        statuses_norm: list[KnowledgeStatus] = []
        for s in self.statuses or ():
            if isinstance(s, KnowledgeStatus):
                statuses_norm.append(s)
            elif isinstance(s, str):
                try:
                    statuses_norm.append(KnowledgeStatus(s))
                except ValueError as exc:
                    raise InvalidKnowledgeQueryError(
                        f"Invalid KnowledgeStatus: {s}"
                    ) from exc
            else:
                raise InvalidKnowledgeQueryError(f"Invalid KnowledgeStatus: {s}")
        object.__setattr__(self, "statuses", tuple(statuses_norm))

        # Normalize resource_ids
        r_ids: list[str] = []
        for rid in self.resource_ids or ():
            if not isinstance(rid, str) or not rid.strip():
                raise InvalidKnowledgeQueryError(
                    "resource_ids elements must be non-empty strings"
                )
            r_ids.append(rid)
        object.__setattr__(self, "resource_ids", tuple(r_ids))

        # Normalize actor_ids
        a_ids: list[str] = []
        for aid in self.actor_ids or ():
            if not isinstance(aid, str) or not aid.strip():
                raise InvalidKnowledgeQueryError(
                    "actor_ids elements must be non-empty strings"
                )
            a_ids.append(aid)
        object.__setattr__(self, "actor_ids", tuple(a_ids))

        # Normalize sensitivities
        sens_norm: list[SensitivityLevel] = []
        for sens in self.sensitivities or ():
            if isinstance(sens, SensitivityLevel):
                sens_norm.append(sens)
            elif isinstance(sens, str):
                try:
                    sens_norm.append(SensitivityLevel(sens))
                except ValueError as exc:
                    raise InvalidKnowledgeQueryError(
                        f"Invalid SensitivityLevel: {sens}"
                    ) from exc
            else:
                raise InvalidKnowledgeQueryError(f"Invalid SensitivityLevel: {sens}")
        object.__setattr__(self, "sensitivities", tuple(sens_norm))

        # Normalize relation_kinds
        rel_kinds_norm: list[KnowledgeRelationKind] = []
        for rk in self.relation_kinds or ():
            if isinstance(rk, KnowledgeRelationKind):
                rel_kinds_norm.append(rk)
            elif isinstance(rk, str):
                try:
                    rel_kinds_norm.append(KnowledgeRelationKind(rk))
                except ValueError as exc:
                    raise InvalidKnowledgeQueryError(
                        f"Invalid KnowledgeRelationKind: {rk}"
                    ) from exc
            else:
                raise InvalidKnowledgeQueryError(f"Invalid KnowledgeRelationKind: {rk}")
        object.__setattr__(self, "relation_kinds", tuple(rel_kinds_norm))

        # Normalize order_by
        if isinstance(self.order_by, str):
            try:
                object.__setattr__(self, "order_by", KnowledgeOrderField(self.order_by))
            except ValueError as exc:
                raise InvalidKnowledgeQueryError(
                    f"Invalid KnowledgeOrderField: {self.order_by}"
                ) from exc
        elif not isinstance(self.order_by, KnowledgeOrderField):
            raise InvalidKnowledgeQueryError(
                f"Invalid KnowledgeOrderField: {self.order_by}"
            )

        # Normalize order_direction
        if isinstance(self.order_direction, str):
            try:
                object.__setattr__(
                    self, "order_direction", SortDirection(self.order_direction)
                )
            except ValueError as exc:
                raise InvalidKnowledgeQueryError(
                    f"Invalid SortDirection: {self.order_direction}"
                ) from exc
        elif not isinstance(self.order_direction, SortDirection):
            raise InvalidKnowledgeQueryError(
                f"Invalid SortDirection: {self.order_direction}"
            )

        # Normalize booleans / Optionals
        if self.has_evidence is not None and not isinstance(self.has_evidence, bool):
            raise InvalidKnowledgeQueryError("has_evidence must be a boolean or None")
        if self.has_relations is not None and not isinstance(self.has_relations, bool):
            raise InvalidKnowledgeQueryError("has_relations must be a boolean or None")
        if not isinstance(self.include_expired, bool):
            raise InvalidKnowledgeQueryError("include_expired must be a boolean")
        if not isinstance(self.include_superseded, bool):
            raise InvalidKnowledgeQueryError("include_superseded must be a boolean")
        if not isinstance(self.include_invalidated, bool):
            raise InvalidKnowledgeQueryError("include_invalidated must be a boolean")

        object.__setattr__(
            self, "metadata", MappingProxyType(dict(self.metadata or {}))
        )

    def serialize(self) -> dict[str, Any]:
        """Canonical JSON-safe dictionary serialization."""
        return {
            "kinds": [k.value for k in self.kinds],
            "statuses": [s.value for s in self.statuses],
            "resource_ids": list(self.resource_ids),
            "actor_ids": list(self.actor_ids),
            "sensitivities": [s.value for s in self.sensitivities],
            "created_from": (
                self.created_from.isoformat() if self.created_from else None
            ),
            "created_until": (
                self.created_until.isoformat() if self.created_until else None
            ),
            "updated_from": (
                self.updated_from.isoformat() if self.updated_from else None
            ),
            "updated_until": (
                self.updated_until.isoformat() if self.updated_until else None
            ),
            "valid_at": self.valid_at.isoformat() if self.valid_at else None,
            "include_expired": self.include_expired,
            "include_superseded": self.include_superseded,
            "include_invalidated": self.include_invalidated,
            "has_evidence": self.has_evidence,
            "has_relations": self.has_relations,
            "relation_kinds": [rk.value for rk in self.relation_kinds],
            "text_contains": self.text_contains,
            "limit": self.limit,
            "offset": self.offset,
            "order_by": self.order_by.value,
            "order_direction": self.order_direction.value,
            "metadata": dict(self.metadata),
        }

    def to_dict(self) -> dict[str, Any]:
        """Compatibility alias for :meth:`serialize`."""
        return self.serialize()

    @classmethod
    def from_mapping(cls, payload: Mapping[str, Any]) -> KnowledgeQuery:
        """Canonical deserialization from mapping."""

        def _parse_ts(key: str) -> datetime | None:
            raw = payload.get(key)
            if raw is None:
                return None
            if isinstance(raw, datetime):
                return raw
            if isinstance(raw, str):
                try:
                    return datetime.fromisoformat(raw)
                except ValueError as exc:
                    raise InvalidKnowledgeQueryError(
                        f"Invalid ISO timestamp for {key}: {raw}"
                    ) from exc
            raise InvalidKnowledgeQueryError(
                f"Expected timestamp string for {key}: {raw}"
            )

        return cls(
            kinds=tuple(payload.get("kinds") or ()),
            statuses=tuple(payload.get("statuses") or ()),
            resource_ids=tuple(payload.get("resource_ids") or ()),
            actor_ids=tuple(payload.get("actor_ids") or ()),
            sensitivities=tuple(payload.get("sensitivities") or ()),
            created_from=_parse_ts("created_from"),
            created_until=_parse_ts("created_until"),
            updated_from=_parse_ts("updated_from"),
            updated_until=_parse_ts("updated_until"),
            valid_at=_parse_ts("valid_at"),
            include_expired=payload.get("include_expired", True),
            include_superseded=payload.get("include_superseded", True),
            include_invalidated=payload.get("include_invalidated", True),
            has_evidence=payload.get("has_evidence"),
            has_relations=payload.get("has_relations"),
            relation_kinds=tuple(payload.get("relation_kinds") or ()),
            text_contains=payload.get("text_contains"),
            limit=payload.get("limit"),
            offset=payload.get("offset", 0),
            order_by=payload.get("order_by", KnowledgeOrderField.CREATED_AT),
            order_direction=payload.get("order_direction", SortDirection.DESC),
            metadata=dict(payload.get("metadata") or {}),
        )

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> KnowledgeQuery:
        """Compatibility alias for :meth:`from_mapping`."""
        return cls.from_mapping(data)


@dataclass(frozen=True, slots=True)
class KnowledgeQueryResult:
    """Immutable, structured result of executing a KnowledgeQuery."""

    query: KnowledgeQuery
    items: tuple[KnowledgeItem, ...]
    total_count: int
    returned_count: int
    offset: int
    limit: int | None
    has_more: bool
    applied_filters: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    created_at: datetime = field(default_factory=_utc_now)
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.query, KnowledgeQuery):
            raise InvalidKnowledgeQueryError("query must be a KnowledgeQuery instance")

        _require_aware_query(self.created_at, "created_at")

        if self.total_count < 0:
            raise InvalidKnowledgeQueryError("total_count must be non-negative")
        if self.returned_count < 0:
            raise InvalidKnowledgeQueryError("returned_count must be non-negative")
        if self.offset < 0:
            raise InvalidKnowledgeQueryError("offset must be non-negative")
        if self.limit is not None and self.limit < 0:
            raise InvalidKnowledgeQueryError("limit must be non-negative")

        items_tuple = tuple(self.items or ())
        object.__setattr__(self, "items", items_tuple)

        if self.returned_count != len(items_tuple):
            raise InvalidKnowledgeQueryError(
                f"returned_count ({self.returned_count}) must match len(items) ({len(items_tuple)})"
            )

        object.__setattr__(self, "applied_filters", tuple(self.applied_filters or ()))
        object.__setattr__(self, "warnings", tuple(self.warnings or ()))
        object.__setattr__(
            self, "metadata", MappingProxyType(dict(self.metadata or {}))
        )

    def serialize(self) -> dict[str, Any]:
        """Canonical JSON-safe dictionary serialization."""
        return {
            "query": self.query.serialize(),
            "items": [item.serialize() for item in self.items],
            "total_count": self.total_count,
            "returned_count": self.returned_count,
            "offset": self.offset,
            "limit": self.limit,
            "has_more": self.has_more,
            "applied_filters": list(self.applied_filters),
            "warnings": list(self.warnings),
            "created_at": self.created_at.isoformat(),
            "metadata": dict(self.metadata),
        }

    def to_dict(self) -> dict[str, Any]:
        """Compatibility alias for :meth:`serialize`."""
        return self.serialize()

    @classmethod
    def from_mapping(cls, payload: Mapping[str, Any]) -> KnowledgeQueryResult:
        """Canonical deserialization from mapping."""
        query_data = payload.get("query")
        if isinstance(query_data, KnowledgeQuery):
            query_val = query_data
        elif isinstance(query_data, Mapping):
            query_val = KnowledgeQuery.from_mapping(query_data)
        else:
            raise InvalidKnowledgeQueryError("Invalid query in KnowledgeQueryResult")

        items_raw = payload.get("items") or ()
        items_parsed: list[KnowledgeItem] = []
        for it in items_raw:
            if isinstance(it, KnowledgeItem):
                items_parsed.append(it)
            elif isinstance(it, Mapping):
                items_parsed.append(KnowledgeItem.from_mapping(it))
            else:
                raise InvalidKnowledgeQueryError("Invalid item in KnowledgeQueryResult")

        created_at_raw = payload.get("created_at")
        if isinstance(created_at_raw, datetime):
            created_at = created_at_raw
        elif isinstance(created_at_raw, str):
            try:
                created_at = datetime.fromisoformat(created_at_raw)
            except ValueError as exc:
                raise InvalidKnowledgeQueryError(
                    f"Invalid ISO timestamp for created_at: {created_at_raw}"
                ) from exc
        else:
            created_at = _utc_now()

        return cls(
            query=query_val,
            items=tuple(items_parsed),
            total_count=payload.get("total_count", len(items_parsed)),
            returned_count=payload.get("returned_count", len(items_parsed)),
            offset=payload.get("offset", 0),
            limit=payload.get("limit"),
            has_more=payload.get("has_more", False),
            applied_filters=tuple(payload.get("applied_filters") or ()),
            warnings=tuple(payload.get("warnings") or ()),
            created_at=created_at,
            metadata=dict(payload.get("metadata") or {}),
        )

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> KnowledgeQueryResult:
        """Compatibility alias for :meth:`from_mapping`."""
        return cls.from_mapping(data)
