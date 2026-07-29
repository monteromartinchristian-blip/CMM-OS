from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from cmm.cognitive.contracts import Confidence
from cmm.cognitive.enums import (
    ResourceIntegrityStatus,
    ResourceKind,
    ResourcePermissionOperation,
    ResourceSourceKind,
    SensitivityLevel,
)
from cmm.cognitive.errors import (
    InvalidResourceError,
    InvalidResourcePermissionError,
    InvalidResourceProvenanceError,
    InvalidResourceTemporalScopeError,
)
from cmm.cognitive.identifiers import generate_cognitive_id


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _require_aware_datetime(
    value: datetime | None,
    field_name: str,
    error_type: type[ValueError],
) -> None:
    if value is not None and value.tzinfo is None:
        raise error_type(f"{field_name} must be timezone-aware")


@dataclass(frozen=True, slots=True)
class ResourceTransformation:
    operation: str
    actor_id: str
    created_at: datetime = field(default_factory=_utc_now)
    input_checksum: str | None = None
    output_checksum: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.operation.strip():
            raise InvalidResourceProvenanceError(
                "resource transformation operation must not be empty"
            )
        if not self.actor_id.strip():
            raise InvalidResourceProvenanceError(
                "resource transformation actor_id must not be empty"
            )

        _require_aware_datetime(
            self.created_at,
            "resource transformation created_at",
            InvalidResourceProvenanceError,
        )
        object.__setattr__(self, "metadata", dict(self.metadata))

    def to_dict(self) -> dict[str, Any]:
        return {
            "operation": self.operation,
            "actor_id": self.actor_id,
            "created_at": self.created_at.isoformat(),
            "input_checksum": self.input_checksum,
            "output_checksum": self.output_checksum,
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True, slots=True)
class ResourceProvenance:
    source_type: ResourceSourceKind
    source_id: str
    author: str | None = None
    retrieved_at: datetime = field(default_factory=_utc_now)
    original_location: str | None = None
    checksum: str | None = None
    transformation_history: tuple[ResourceTransformation, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.source_id.strip():
            raise InvalidResourceProvenanceError(
                "resource provenance source_id must not be empty"
            )
        if self.author is not None and not self.author.strip():
            raise InvalidResourceProvenanceError(
                "resource provenance author must not be blank"
            )
        if self.original_location is not None and not self.original_location.strip():
            raise InvalidResourceProvenanceError(
                "resource provenance original_location must not be blank"
            )
        if self.checksum is not None and not self.checksum.strip():
            raise InvalidResourceProvenanceError(
                "resource provenance checksum must not be blank"
            )

        _require_aware_datetime(
            self.retrieved_at,
            "resource provenance retrieved_at",
            InvalidResourceProvenanceError,
        )
        object.__setattr__(
            self,
            "transformation_history",
            tuple(self.transformation_history),
        )
        object.__setattr__(self, "metadata", dict(self.metadata))

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_type": self.source_type.value,
            "source_id": self.source_id,
            "author": self.author,
            "retrieved_at": self.retrieved_at.isoformat(),
            "original_location": self.original_location,
            "checksum": self.checksum,
            "transformation_history": [
                transformation.to_dict()
                for transformation in self.transformation_history
            ],
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True, slots=True)
class ResourceTemporalScope:
    content_created_at: datetime | None = None
    observed_at: datetime | None = None
    ingested_at: datetime = field(default_factory=_utc_now)
    valid_from: datetime | None = None
    valid_until: datetime | None = None
    event_start: datetime | None = None
    event_end: datetime | None = None
    last_verified_at: datetime | None = None
    timezone_name: str = "UTC"
    recurrence: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for field_name in (
            "content_created_at",
            "observed_at",
            "ingested_at",
            "valid_from",
            "valid_until",
            "event_start",
            "event_end",
            "last_verified_at",
        ):
            _require_aware_datetime(
                getattr(self, field_name),
                f"resource temporal scope {field_name}",
                InvalidResourceTemporalScopeError,
            )

        if not self.timezone_name.strip():
            raise InvalidResourceTemporalScopeError(
                "resource temporal scope timezone_name must not be empty"
            )

        if self.recurrence is not None and not self.recurrence.strip():
            raise InvalidResourceTemporalScopeError(
                "resource temporal scope recurrence must not be blank"
            )

        if (
            self.valid_from is not None
            and self.valid_until is not None
            and self.valid_until < self.valid_from
        ):
            raise InvalidResourceTemporalScopeError(
                "resource valid_until must not precede valid_from"
            )

        if (
            self.event_start is not None
            and self.event_end is not None
            and self.event_end < self.event_start
        ):
            raise InvalidResourceTemporalScopeError(
                "resource event_end must not precede event_start"
            )

        object.__setattr__(self, "metadata", dict(self.metadata))

    def is_valid_at(self, moment: datetime) -> bool:
        _require_aware_datetime(
            moment,
            "resource validity reference",
            InvalidResourceTemporalScopeError,
        )

        if self.valid_from is not None and moment < self.valid_from:
            return False
        if self.valid_until is not None and moment > self.valid_until:
            return False
        return True

    @property
    def expired(self) -> bool:
        if self.valid_until is None:
            return False
        return _utc_now() > self.valid_until

    def to_dict(self) -> dict[str, Any]:
        return {
            "content_created_at": (
                self.content_created_at.isoformat()
                if self.content_created_at is not None
                else None
            ),
            "observed_at": (
                self.observed_at.isoformat() if self.observed_at is not None else None
            ),
            "ingested_at": self.ingested_at.isoformat(),
            "valid_from": (
                self.valid_from.isoformat() if self.valid_from is not None else None
            ),
            "valid_until": (
                self.valid_until.isoformat() if self.valid_until is not None else None
            ),
            "event_start": (
                self.event_start.isoformat() if self.event_start is not None else None
            ),
            "event_end": (
                self.event_end.isoformat() if self.event_end is not None else None
            ),
            "last_verified_at": (
                self.last_verified_at.isoformat()
                if self.last_verified_at is not None
                else None
            ),
            "timezone_name": self.timezone_name,
            "recurrence": self.recurrence,
            "expired": self.expired,
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True, slots=True)
class ResourcePermission:
    allowed_actor_ids: tuple[str, ...] = ()
    allowed_domains: tuple[str, ...] = ()
    allowed_operations: tuple[ResourcePermissionOperation, ...] = (
        ResourcePermissionOperation.READ,
    )
    expires_at: datetime | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _require_aware_datetime(
            self.expires_at,
            "resource permission expires_at",
            InvalidResourcePermissionError,
        )

        if any(not actor_id.strip() for actor_id in self.allowed_actor_ids):
            raise InvalidResourcePermissionError(
                "resource permission actor ids must not be empty"
            )

        if any(not domain.strip() for domain in self.allowed_domains):
            raise InvalidResourcePermissionError(
                "resource permission domains must not be empty"
            )

        if len(set(self.allowed_actor_ids)) != len(self.allowed_actor_ids):
            raise InvalidResourcePermissionError(
                "resource permission actor ids must be unique"
            )

        if len(set(self.allowed_domains)) != len(self.allowed_domains):
            raise InvalidResourcePermissionError(
                "resource permission domains must be unique"
            )

        if len(set(self.allowed_operations)) != len(self.allowed_operations):
            raise InvalidResourcePermissionError(
                "resource permission operations must be unique"
            )

        object.__setattr__(self, "allowed_actor_ids", tuple(self.allowed_actor_ids))
        object.__setattr__(self, "allowed_domains", tuple(self.allowed_domains))
        object.__setattr__(self, "allowed_operations", tuple(self.allowed_operations))
        object.__setattr__(self, "metadata", dict(self.metadata))

    @property
    def expired(self) -> bool:
        return self.expires_at is not None and _utc_now() > self.expires_at

    def allows(
        self,
        operation: ResourcePermissionOperation,
        *,
        actor_id: str | None = None,
        domain: str | None = None,
        at: datetime | None = None,
    ) -> bool:
        reference = at or _utc_now()
        _require_aware_datetime(
            reference,
            "resource permission reference",
            InvalidResourcePermissionError,
        )

        if self.expires_at is not None and reference > self.expires_at:
            return False

        if operation not in self.allowed_operations:
            return False

        if self.allowed_actor_ids and actor_id not in self.allowed_actor_ids:
            return False

        if self.allowed_domains and domain not in self.allowed_domains:
            return False

        return True

    def to_dict(self) -> dict[str, Any]:
        return {
            "allowed_actor_ids": list(self.allowed_actor_ids),
            "allowed_domains": list(self.allowed_domains),
            "allowed_operations": [
                operation.value for operation in self.allowed_operations
            ],
            "expires_at": (
                self.expires_at.isoformat() if self.expires_at is not None else None
            ),
            "expired": self.expired,
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True, slots=True)
class Resource:
    domain: str
    kind: ResourceKind
    source: ResourceSourceKind
    content: Any
    provenance: ResourceProvenance
    reliability: Confidence
    temporal_scope: ResourceTemporalScope
    id: str = field(
        default_factory=lambda: generate_cognitive_id("resource", "general")
    )
    version: str = "1"
    language: str | None = None
    entity_ids: tuple[str, ...] = ()
    relationship_ids: tuple[str, ...] = ()
    sensitivity: SensitivityLevel = SensitivityLevel.INTERNAL
    permissions: tuple[ResourcePermission, ...] = ()
    integrity: ResourceIntegrityStatus = ResourceIntegrityStatus.UNKNOWN
    created_at: datetime = field(default_factory=_utc_now)
    updated_at: datetime = field(default_factory=_utc_now)
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.id.strip():
            raise InvalidResourceError("resource id must not be empty")
        if not self.domain.strip():
            raise InvalidResourceError("resource domain must not be empty")
        if not self.version.strip():
            raise InvalidResourceError("resource version must not be empty")
        if self.language is not None and not self.language.strip():
            raise InvalidResourceError("resource language must not be blank")

        for field_name in ("created_at", "updated_at"):
            _require_aware_datetime(
                getattr(self, field_name),
                f"resource {field_name}",
                InvalidResourceError,
            )

        if self.updated_at < self.created_at:
            raise InvalidResourceError(
                "resource updated_at must not precede created_at"
            )

        if len(set(self.entity_ids)) != len(self.entity_ids):
            raise InvalidResourceError("resource entity ids must be unique")

        if len(set(self.relationship_ids)) != len(self.relationship_ids):
            raise InvalidResourceError("resource relationship ids must be unique")

        object.__setattr__(self, "entity_ids", tuple(self.entity_ids))
        object.__setattr__(
            self,
            "relationship_ids",
            tuple(self.relationship_ids),
        )
        object.__setattr__(self, "permissions", tuple(self.permissions))
        object.__setattr__(self, "metadata", dict(self.metadata))

    def permits(
        self,
        operation: ResourcePermissionOperation,
        *,
        actor_id: str | None = None,
        domain: str | None = None,
        at: datetime | None = None,
    ) -> bool:
        if not self.permissions:
            return operation is ResourcePermissionOperation.READ

        return any(
            permission.allows(
                operation,
                actor_id=actor_id,
                domain=domain,
                at=at,
            )
            for permission in self.permissions
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "domain": self.domain,
            "kind": self.kind.value,
            "source": self.source.value,
            "content": self.content,
            "provenance": self.provenance.to_dict(),
            "reliability": self.reliability.to_dict(),
            "temporal_scope": self.temporal_scope.to_dict(),
            "version": self.version,
            "language": self.language,
            "entity_ids": list(self.entity_ids),
            "relationship_ids": list(self.relationship_ids),
            "sensitivity": self.sensitivity.value,
            "permissions": [permission.to_dict() for permission in self.permissions],
            "integrity": self.integrity.value,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> Resource:
        def parse_datetime(
            value: Any, *, default: datetime | None = None
        ) -> datetime | None:
            if value is None:
                return default
            if isinstance(value, datetime):
                return value
            if isinstance(value, str):
                return datetime.fromisoformat(value)
            raise InvalidResourceError("resource datetime value is invalid")

        provenance_data = data["provenance"]
        reliability_data = data["reliability"]
        temporal_data = data["temporal_scope"]

        if not isinstance(provenance_data, Mapping):
            raise InvalidResourceError("resource provenance must be a mapping")
        if not isinstance(reliability_data, Mapping):
            raise InvalidResourceError("resource reliability must be a mapping")
        if not isinstance(temporal_data, Mapping):
            raise InvalidResourceError("resource temporal_scope must be a mapping")

        transformations = tuple(
            ResourceTransformation(
                operation=str(item["operation"]),
                actor_id=str(item["actor_id"]),
                created_at=parse_datetime(
                    item.get("created_at"),
                    default=_utc_now(),
                )
                or _utc_now(),
                input_checksum=item.get("input_checksum"),
                output_checksum=item.get("output_checksum"),
                metadata=dict(item.get("metadata", {})),
            )
            for item in provenance_data.get("transformation_history", ())
            if isinstance(item, Mapping)
        )

        provenance = ResourceProvenance(
            source_type=ResourceSourceKind(provenance_data["source_type"]),
            source_id=str(provenance_data["source_id"]),
            author=provenance_data.get("author"),
            retrieved_at=parse_datetime(
                provenance_data.get("retrieved_at"),
                default=_utc_now(),
            )
            or _utc_now(),
            original_location=provenance_data.get("original_location"),
            checksum=provenance_data.get("checksum"),
            transformation_history=transformations,
            metadata=dict(provenance_data.get("metadata", {})),
        )

        reliability = Confidence(
            value=float(reliability_data["value"]),
            source=reliability_data.get("source"),
            reasons=tuple(str(item) for item in reliability_data.get("reasons", ())),
            metadata=dict(reliability_data.get("metadata", {})),
        )

        temporal_scope = ResourceTemporalScope(
            content_created_at=parse_datetime(temporal_data.get("content_created_at")),
            observed_at=parse_datetime(temporal_data.get("observed_at")),
            ingested_at=parse_datetime(
                temporal_data.get("ingested_at"),
                default=_utc_now(),
            )
            or _utc_now(),
            valid_from=parse_datetime(temporal_data.get("valid_from")),
            valid_until=parse_datetime(temporal_data.get("valid_until")),
            event_start=parse_datetime(temporal_data.get("event_start")),
            event_end=parse_datetime(temporal_data.get("event_end")),
            last_verified_at=parse_datetime(temporal_data.get("last_verified_at")),
            timezone_name=str(temporal_data.get("timezone_name", "UTC")),
            recurrence=temporal_data.get("recurrence"),
            metadata=dict(temporal_data.get("metadata", {})),
        )

        permissions = tuple(
            ResourcePermission(
                allowed_actor_ids=tuple(
                    str(actor_id) for actor_id in item.get("allowed_actor_ids", ())
                ),
                allowed_domains=tuple(
                    str(domain) for domain in item.get("allowed_domains", ())
                ),
                allowed_operations=tuple(
                    ResourcePermissionOperation(operation)
                    for operation in item.get(
                        "allowed_operations",
                        (ResourcePermissionOperation.READ.value,),
                    )
                ),
                expires_at=parse_datetime(item.get("expires_at")),
                metadata=dict(item.get("metadata", {})),
            )
            for item in data.get("permissions", ())
            if isinstance(item, Mapping)
        )

        created_at = parse_datetime(data.get("created_at"), default=_utc_now())
        updated_at = parse_datetime(data.get("updated_at"), default=created_at)

        return cls(
            id=str(data["id"]),
            domain=str(data["domain"]),
            kind=ResourceKind(data["kind"]),
            source=ResourceSourceKind(data["source"]),
            content=data.get("content"),
            provenance=provenance,
            reliability=reliability,
            temporal_scope=temporal_scope,
            version=str(data.get("version", "1")),
            language=data.get("language"),
            entity_ids=tuple(str(item) for item in data.get("entity_ids", ())),
            relationship_ids=tuple(
                str(item) for item in data.get("relationship_ids", ())
            ),
            sensitivity=SensitivityLevel(
                data.get("sensitivity", SensitivityLevel.INTERNAL.value)
            ),
            permissions=permissions,
            integrity=ResourceIntegrityStatus(
                data.get("integrity", ResourceIntegrityStatus.UNKNOWN.value)
            ),
            created_at=created_at or _utc_now(),
            updated_at=updated_at or created_at or _utc_now(),
            metadata=dict(data.get("metadata", {})),
        )
