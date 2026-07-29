"""Phase 8.25 – Privacy and Sensitivity Metadata.

Adds structured, immutable, versioned processing-policy metadata that can be
propagated across cognitive artifacts. This module deliberately keeps three
concepts separate and never merges them:

* **Sensitivity** — the nature/criticality of content. Already represented
  by :class:`cmm.cognitive.enums.SensitivityLevel`. Not redefined here.
* **Permissions** — who may perform which operation on a resource. Already
  represented by :class:`cmm.cognitive.resources.ResourcePermission` and
  :class:`cmm.cognitive.enums.ResourcePermissionOperation`. Not redefined
  here.
* **Processing policy** — where content may be processed, whether it may
  leave the local runtime, be cached, be exported, or requires redaction or
  approval. This is what :class:`PrivacyMetadata` adds.

Out of scope for this phase (deferred to later phases, see
``docs/roadmap/phase-8-cognitive-layer.md``): model routing, provider
selection/registry, domain-specific policies (Phase 10), global auditing of
provider calls (Phase 11), automatic redaction/anonymization, secrets
management, encryption, data residency/regions, exporters, provider
adapters, fallback selection, full human-approval workflows, and Structural
Cognitive Validation (Phase 8.26). This module only decides and propagates
metadata; it never executes a redaction or approval.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from types import MappingProxyType
from typing import Any, cast

from cmm.cognitive.enums import ResourcePermissionOperation, SensitivityLevel
from cmm.cognitive.errors import (
    InvalidPrivacyMetadataError,
    PrivacyResolutionError,
)
from cmm.cognitive.knowledge import KnowledgeItem
from cmm.cognitive.knowledge_packages import KnowledgePackage
from cmm.cognitive.resources import Resource, ResourcePermission

PRIVACY_METADATA_SCHEMA_VERSION = 1


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _require_aware(value: datetime | None, name: str) -> None:
    if value is not None and value.tzinfo is None:
        raise InvalidPrivacyMetadataError(f"{name} must be timezone-aware")


def _jsonable(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, Enum):
        return value.value
    if hasattr(value, "to_dict") and callable(value.to_dict):
        return _jsonable(value.to_dict())
    if isinstance(value, Mapping):
        return {str(key): _jsonable(value[key]) for key in sorted(value, key=str)}
    if isinstance(value, (tuple, list)):
        return [_jsonable(item) for item in value]
    if isinstance(value, (set, frozenset)):
        return [_jsonable(item) for item in sorted(value, key=str)]
    return value


def _ensure_json_serializable(value: Any, name: str) -> None:
    try:
        json.dumps(_jsonable(value))
    except (TypeError, ValueError) as exc:
        raise InvalidPrivacyMetadataError(f"{name} must be JSON-serializable") from exc


def _coerce_enum(value: Any, enum_type: type[Enum], name: str) -> Enum:
    if isinstance(value, enum_type):
        return value
    if isinstance(value, str):
        try:
            return enum_type(value)
        except ValueError as exc:
            raise InvalidPrivacyMetadataError(f"Invalid {name}: {value}") from exc
    raise InvalidPrivacyMetadataError(f"Invalid {name}: {value!r}")


def _string_sequence(value: Any, name: str) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, (str, bytes, bytearray, Mapping)) or not isinstance(
        value, Sequence
    ):
        raise InvalidPrivacyMetadataError(f"{name} must be a sequence of strings")
    result: list[str] = []
    for item in value:
        text = str(item)
        if not text.strip():
            raise InvalidPrivacyMetadataError(f"{name} entries must not be blank")
        result.append(text)
    return tuple(result)


_INCOMPATIBLE = object()


def _strict_bool(payload: Mapping[str, Any], key: str, default: bool) -> bool:
    """Read a boolean field from a deserialized mapping without truthy coercion.

    ``bool("false")`` is ``True`` in Python, so a naive ``bool(payload.get(...))``
    would silently treat the string ``"false"`` (or any non-empty string/list/
    dict) as an authorization. Only an absent key falls back to ``default``;
    every present value must already be a real ``bool``.
    """
    if key not in payload:
        return default
    value = payload[key]
    if isinstance(value, bool):
        return value
    raise InvalidPrivacyMetadataError(f"{key} must be a boolean, got {value!r}")


def _coerce_permissions(
    value: Any, name: str = "permissions"
) -> tuple[ResourcePermission, ...]:
    if value is None:
        return ()
    if isinstance(value, (str, bytes, bytearray, Mapping)) or not isinstance(
        value, Sequence
    ):
        raise InvalidPrivacyMetadataError(f"{name} must be a sequence")
    result: list[ResourcePermission] = []
    for item in value:
        if isinstance(item, ResourcePermission):
            result.append(item)
        elif isinstance(item, Mapping):
            result.append(
                ResourcePermission(
                    allowed_actor_ids=tuple(
                        str(v) for v in item.get("allowed_actor_ids", ())
                    ),
                    allowed_domains=tuple(
                        str(v) for v in item.get("allowed_domains", ())
                    ),
                    allowed_operations=tuple(
                        ResourcePermissionOperation(v)
                        for v in item.get(
                            "allowed_operations",
                            (ResourcePermissionOperation.READ.value,),
                        )
                    ),
                    expires_at=(
                        datetime.fromisoformat(item["expires_at"])
                        if item.get("expires_at")
                        else None
                    ),
                    metadata=dict(item.get("metadata", {})),
                )
            )
        else:
            raise InvalidPrivacyMetadataError(
                f"{name} must contain ResourcePermission values"
            )
    return tuple(result)


def _conjoin_ids(
    a_ids: tuple[str, ...], b_ids: tuple[str, ...]
) -> tuple[str, ...] | object:
    """Combine two id restrictions so the result satisfies *both*.

    If both sides restrict, only ids common to both survive (``_INCOMPATIBLE``
    if that intersection is empty). If only one side restricts, its
    restriction is kept as-is. If neither restricts, the result is
    unrestricted (``()``).
    """
    if a_ids and b_ids:
        overlap = tuple(x for x in a_ids if x in b_ids)
        return overlap if overlap else _INCOMPATIBLE
    if a_ids:
        return a_ids
    if b_ids:
        return b_ids
    return ()


def _earliest_expiry(a: datetime | None, b: datetime | None) -> datetime | None:
    if a is None:
        return b
    if b is None:
        return a
    return min(a, b)


def _conjoin_permission(
    a: ResourcePermission, b: ResourcePermission
) -> ResourcePermission | None:
    """Combine two ResourcePermission grants into the single grant that
    satisfies both, or ``None`` if no actor/domain/operation combination can
    ever satisfy both simultaneously (an unsatisfiable pairwise conjunction).
    """
    actors = _conjoin_ids(a.allowed_actor_ids, b.allowed_actor_ids)
    if actors is _INCOMPATIBLE:
        return None
    domains = _conjoin_ids(a.allowed_domains, b.allowed_domains)
    if domains is _INCOMPATIBLE:
        return None
    operations = tuple(op for op in a.allowed_operations if op in b.allowed_operations)
    if not operations:
        return None
    return ResourcePermission(
        allowed_actor_ids=cast(tuple, actors),
        allowed_domains=cast(tuple, domains),
        allowed_operations=operations,
        expires_at=_earliest_expiry(a.expires_at, b.expires_at),
    )


def _intersect_permissions(
    policies: Sequence[PrivacyMetadata],
) -> tuple[tuple[ResourcePermission, ...], bool]:
    """Combine every policy's permission OR-list with AND-across-policies
    semantics: a request must be authorized under *every* policy that
    declares any permission restriction. A policy that declares none
    contributes no restriction and never widens or narrows this result.

    Returns ``(permissions, denied)``. ``denied=True`` means at least two
    policies declared permissions but no actor/domain/operation/expiry
    combination satisfies all of them simultaneously — this is never
    collapsed into a silent, unrestricted ``()``.
    """
    accumulated: tuple[ResourcePermission, ...] | None = None
    for policy in policies:
        current = tuple(policy.permissions)
        if not current:
            continue
        if accumulated is None:
            accumulated = current
            continue
        combined: list[ResourcePermission] = []
        for left in accumulated:
            for right in current:
                merged = _conjoin_permission(left, right)
                if merged is not None and merged not in combined:
                    combined.append(merged)
        accumulated = tuple(combined)
    if accumulated is None:
        return (), False
    return accumulated, len(accumulated) == 0


# ── Enums ───────────────────────────────────────────────────────────────────


class PrivacyPolicy(str, Enum):
    """Where cognitive content may be processed.

    Explicit hierarchy, from most to least restrictive:

    ``LOCAL_ONLY``
        Content must never leave the local runtime.
    ``LOCAL_PREFERRED``
        Content must be processed locally whenever possible; remote use
        requires an explicit exception (``allow_remote=True``).
    ``REMOTE_ALLOWED``
        Content may be processed remotely once every other restriction
        (allowed locations, providers, cache/export flags) permits it.
    ``PREMIUM_ALLOWED``
        In addition to remote processing, premium providers/modes may be
        used when explicitly authorized (``allow_premium=True``).
    """

    LOCAL_ONLY = "local_only"
    LOCAL_PREFERRED = "local_preferred"
    REMOTE_ALLOWED = "remote_allowed"
    PREMIUM_ALLOWED = "premium_allowed"


class ProcessingLocation(str, Enum):
    LOCAL = "local"
    REMOTE = "remote"


class PrivacyOperation(str, Enum):
    PROCESS_LOCAL = "process_local"
    PROCESS_REMOTE = "process_remote"
    CACHE = "cache"
    EXPORT = "export"
    USE_PREMIUM = "use_premium"
    TRANSMIT_TO_PROVIDER = "transmit_to_provider"


class PrivacyDecisionStatus(str, Enum):
    ALLOWED = "allowed"
    DENIED = "denied"
    REDACTION_REQUIRED = "redaction_required"
    APPROVAL_REQUIRED = "approval_required"


# Explicit hierarchy, declared here rather than derived from enum member
# order, so a future reordering of ``PrivacyPolicy``/``SensitivityLevel``
# cannot silently change resolution semantics (mirrors the pattern used for
# sensitivity ranking in Phase 8.24's cognitive_cache.py).
_POLICY_HIERARCHY: tuple[PrivacyPolicy, ...] = (
    PrivacyPolicy.LOCAL_ONLY,
    PrivacyPolicy.LOCAL_PREFERRED,
    PrivacyPolicy.REMOTE_ALLOWED,
    PrivacyPolicy.PREMIUM_ALLOWED,
)
_POLICY_RANK: Mapping[PrivacyPolicy, int] = {
    policy: index for index, policy in enumerate(_POLICY_HIERARCHY)
}
_SENSITIVITY_HIERARCHY: tuple[SensitivityLevel, ...] = (
    SensitivityLevel.PUBLIC,
    SensitivityLevel.INTERNAL,
    SensitivityLevel.PERSONAL,
    SensitivityLevel.SENSITIVE,
    SensitivityLevel.HIGHLY_SENSITIVE,
    SensitivityLevel.RESTRICTED,
)
_SENSITIVITY_RANK: Mapping[SensitivityLevel, int] = {
    level: index for index, level in enumerate(_SENSITIVITY_HIERARCHY)
}


# ── PrivacyMetadata ─────────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class PrivacyMetadata:
    """Immutable, versioned processing-policy metadata for a cognitive artifact.

    Distinct from — and composable with — sensitivity (``SensitivityLevel``)
    and permissions (``ResourcePermission``), both of which it reuses rather
    than reimplements. Defaults are deliberately conservative: an artifact
    with no explicit privacy metadata is treated as local-only, maximally
    sensitive, non-remote, non-premium, non-exportable.

    ``allowed_providers`` distinguishes "no allowlist configured" (``None``,
    the default — every provider is a candidate unless prohibited) from "an
    allowlist was configured with zero entries" (``()`` — no provider is
    ever allowed). Collapsing both to ``()`` would let two incompatible,
    non-overlapping allowlists resolve to "unrestricted" once intersected;
    keeping them distinct means an empty intersection stays ``()``, which
    still means "nothing is allowed."

    ``permissions_denied`` is the analogous safeguard for
    :attr:`permissions`: when :func:`resolve_effective_privacy_metadata`
    combines permission restrictions from multiple sources and no
    actor/domain/operation/expiry combination satisfies all of them, the
    result is *not* silently represented as ``permissions=()`` (which means
    "no restriction" when a policy never declared any permissions). Instead
    ``permissions_denied=True`` is set, and :func:`evaluate_privacy_operation`
    always denies when it is set, regardless of the operation.
    """

    policy: PrivacyPolicy = PrivacyPolicy.LOCAL_ONLY
    sensitivity: SensitivityLevel = SensitivityLevel.RESTRICTED
    allowed_processing_locations: tuple[ProcessingLocation, ...] = (
        ProcessingLocation.LOCAL,
    )
    allowed_providers: tuple[str, ...] | None = None
    prohibited_providers: tuple[str, ...] = ()
    allow_remote: bool = False
    allow_premium: bool = False
    allow_cache: bool = True
    allow_export: bool = False
    requires_redaction: bool = False
    requires_approval: bool = False
    inherited_from: tuple[str, ...] = ()
    permissions: tuple[ResourcePermission, ...] = ()
    permissions_denied: bool = False
    metadata: Mapping[str, Any] = field(default_factory=dict)
    schema_version: int = PRIVACY_METADATA_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if self.schema_version != PRIVACY_METADATA_SCHEMA_VERSION:
            raise InvalidPrivacyMetadataError(
                f"Unsupported PrivacyMetadata schema_version: {self.schema_version}"
            )

        policy = _coerce_enum(self.policy, PrivacyPolicy, "policy")
        object.__setattr__(self, "policy", policy)

        sensitivity = _coerce_enum(self.sensitivity, SensitivityLevel, "sensitivity")
        object.__setattr__(self, "sensitivity", sensitivity)

        locations = tuple(
            _coerce_enum(item, ProcessingLocation, "allowed_processing_locations")
            for item in (self.allowed_processing_locations or ())
        )
        if len(set(locations)) != len(locations):
            raise InvalidPrivacyMetadataError(
                "allowed_processing_locations must not contain duplicates"
            )
        object.__setattr__(self, "allowed_processing_locations", locations)

        allowed_providers: tuple[str, ...] | None
        if self.allowed_providers is None:
            allowed_providers = None
        else:
            allowed_providers = _string_sequence(
                self.allowed_providers, "allowed_providers"
            )
            if len(set(allowed_providers)) != len(allowed_providers):
                raise InvalidPrivacyMetadataError(
                    "allowed_providers must not contain duplicates"
                )
        prohibited_providers = _string_sequence(
            self.prohibited_providers, "prohibited_providers"
        )
        if len(set(prohibited_providers)) != len(prohibited_providers):
            raise InvalidPrivacyMetadataError(
                "prohibited_providers must not contain duplicates"
            )
        if allowed_providers is not None:
            overlap = set(allowed_providers) & set(prohibited_providers)
            if overlap:
                raise InvalidPrivacyMetadataError(
                    f"providers cannot be both allowed and prohibited: {sorted(overlap)}"
                )
        object.__setattr__(self, "allowed_providers", allowed_providers)
        object.__setattr__(self, "prohibited_providers", prohibited_providers)

        inherited_from = _string_sequence(self.inherited_from, "inherited_from")
        if len(set(inherited_from)) != len(inherited_from):
            raise InvalidPrivacyMetadataError(
                "inherited_from must not contain duplicates"
            )
        object.__setattr__(self, "inherited_from", inherited_from)

        object.__setattr__(self, "permissions", _coerce_permissions(self.permissions))

        for name in (
            "allow_remote",
            "allow_premium",
            "allow_cache",
            "allow_export",
            "requires_redaction",
            "requires_approval",
            "permissions_denied",
        ):
            if not isinstance(getattr(self, name), bool):
                raise InvalidPrivacyMetadataError(f"{name} must be a boolean")

        if not isinstance(self.metadata, Mapping):
            raise InvalidPrivacyMetadataError("metadata must be a mapping")
        _ensure_json_serializable(self.metadata, "metadata")
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))

        if policy is PrivacyPolicy.LOCAL_ONLY:
            if self.allow_remote:
                raise InvalidPrivacyMetadataError(
                    "allow_remote=True is incompatible with LOCAL_ONLY policy"
                )
            if ProcessingLocation.REMOTE in locations:
                raise InvalidPrivacyMetadataError(
                    "REMOTE in allowed_processing_locations is incompatible with "
                    "LOCAL_ONLY policy"
                )

        if self.allow_premium and policy is not PrivacyPolicy.PREMIUM_ALLOWED:
            raise InvalidPrivacyMetadataError(
                "allow_premium=True requires PREMIUM_ALLOWED policy"
            )

    def serialize(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "policy": self.policy.value,
            "sensitivity": self.sensitivity.value,
            "allowed_processing_locations": [
                loc.value for loc in self.allowed_processing_locations
            ],
            "allowed_providers": (
                list(self.allowed_providers)
                if self.allowed_providers is not None
                else None
            ),
            "prohibited_providers": list(self.prohibited_providers),
            "allow_remote": self.allow_remote,
            "allow_premium": self.allow_premium,
            "allow_cache": self.allow_cache,
            "allow_export": self.allow_export,
            "requires_redaction": self.requires_redaction,
            "requires_approval": self.requires_approval,
            "inherited_from": list(self.inherited_from),
            "permissions": [permission.to_dict() for permission in self.permissions],
            "permissions_denied": self.permissions_denied,
            "metadata": dict(self.metadata),
        }

    def to_dict(self) -> dict[str, Any]:
        return self.serialize()

    @classmethod
    def from_mapping(cls, payload: Mapping[str, Any]) -> PrivacyMetadata:
        if not isinstance(payload, Mapping):
            raise InvalidPrivacyMetadataError("payload must be a mapping")
        if "schema_version" not in payload:
            raise InvalidPrivacyMetadataError(
                "PrivacyMetadata.from_mapping requires an explicit schema_version"
            )
        schema_version = payload["schema_version"]
        if not isinstance(schema_version, int) or isinstance(schema_version, bool):
            raise InvalidPrivacyMetadataError(
                f"schema_version must be an integer, got {schema_version!r}"
            )

        raw_allowed_providers = payload.get("allowed_providers")
        allowed_providers = (
            tuple(raw_allowed_providers) if raw_allowed_providers is not None else None
        )

        return cls(
            policy=payload.get("policy", PrivacyPolicy.LOCAL_ONLY.value),
            sensitivity=payload.get("sensitivity", SensitivityLevel.RESTRICTED.value),
            allowed_processing_locations=tuple(
                payload.get(
                    "allowed_processing_locations", (ProcessingLocation.LOCAL.value,)
                )
            ),
            allowed_providers=allowed_providers,
            prohibited_providers=tuple(payload.get("prohibited_providers", ())),
            allow_remote=_strict_bool(payload, "allow_remote", False),
            allow_premium=_strict_bool(payload, "allow_premium", False),
            allow_cache=_strict_bool(payload, "allow_cache", True),
            allow_export=_strict_bool(payload, "allow_export", False),
            requires_redaction=_strict_bool(payload, "requires_redaction", False),
            requires_approval=_strict_bool(payload, "requires_approval", False),
            inherited_from=tuple(payload.get("inherited_from", ())),
            permissions=tuple(payload.get("permissions", ())),
            permissions_denied=_strict_bool(payload, "permissions_denied", False),
            metadata=dict(payload.get("metadata") or {}),
            schema_version=schema_version,
        )

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> PrivacyMetadata:
        return cls.from_mapping(data)


# ── Resolution of effective policy across multiple sources ─────────────────


@dataclass(frozen=True, slots=True)
class PrivacyResolution:
    """Auditable outcome of combining several :class:`PrivacyMetadata`."""

    effective: PrivacyMetadata
    source_count: int
    restrictions_applied: tuple[str, ...] = ()
    conflicts: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "effective": self.effective.to_dict(),
            "source_count": self.source_count,
            "restrictions_applied": list(self.restrictions_applied),
            "conflicts": list(self.conflicts),
        }


def resolve_effective_privacy_metadata(*policies: PrivacyMetadata) -> PrivacyResolution:
    """Combine several :class:`PrivacyMetadata`, always applying the strongest
    restriction. A descendant policy can never widen what an ancestor
    restricted."""
    if not policies:
        raise PrivacyResolutionError(
            "resolve_effective_privacy_metadata requires at least one PrivacyMetadata"
        )
    for candidate in policies:
        if not isinstance(candidate, PrivacyMetadata):
            raise PrivacyResolutionError(
                f"Expected PrivacyMetadata, got {type(candidate).__name__}"
            )

    restrictions: list[str] = []
    conflicts: list[str] = []

    policy_ranks = [_POLICY_RANK[p.policy] for p in policies]
    effective_policy = _POLICY_HIERARCHY[min(policy_ranks)]
    if len(set(policy_ranks)) > 1:
        restrictions.append(f"policy narrowed to {effective_policy.value}")

    sensitivity_ranks = [_SENSITIVITY_RANK[p.sensitivity] for p in policies]
    effective_sensitivity = _SENSITIVITY_HIERARCHY[max(sensitivity_ranks)]
    if len(set(sensitivity_ranks)) > 1:
        restrictions.append(f"sensitivity raised to {effective_sensitivity.value}")

    location_sets = [set(p.allowed_processing_locations) for p in policies]
    effective_locations = set.intersection(*location_sets) if location_sets else set()
    if any(candidate != effective_locations for candidate in location_sets):
        restrictions.append("allowed_processing_locations narrowed by intersection")
    if location_sets and not effective_locations:
        conflicts.append(
            "allowed_processing_locations intersection is empty: no location "
            "satisfies every source"
        )

    # `None` means "no allowlist configured" and must never participate in the
    # intersection, or a source with no allowlist would silently widen an
    # allowlist declared by another source. Only sources that actually
    # declared one (including an explicit, maximally restrictive `()`) are
    # intersected; if none declared one, the effective allowlist stays `None`
    # (unrestricted), not `()` (nothing allowed).
    declared_allowlists = [
        p.allowed_providers for p in policies if p.allowed_providers is not None
    ]
    if declared_allowlists:
        effective_allowed_providers_set = set.intersection(
            *(set(allowlist) for allowlist in declared_allowlists)
        )
        effective_allowed_providers: tuple[str, ...] | None = tuple(
            sorted(effective_allowed_providers_set)
        )
        if len(declared_allowlists) > 1 and any(
            set(allowlist) != effective_allowed_providers_set
            for allowlist in declared_allowlists
        ):
            restrictions.append("allowed_providers narrowed by intersection")
        if not effective_allowed_providers_set:
            conflicts.append(
                "allowed_providers intersection is empty: no provider satisfies "
                "every allowlist"
            )
    else:
        effective_allowed_providers = None

    effective_prohibited_providers: set[str] = set()
    for p in policies:
        effective_prohibited_providers |= set(p.prohibited_providers)
    if any(p.prohibited_providers for p in policies):
        restrictions.append("prohibited_providers widened by union")

    effective_allow_remote = all(p.allow_remote for p in policies)
    effective_allow_premium = all(p.allow_premium for p in policies)
    effective_allow_cache = all(p.allow_cache for p in policies)
    effective_allow_export = all(p.allow_export for p in policies)
    for flag_name, effective_flag in (
        ("allow_remote", effective_allow_remote),
        ("allow_premium", effective_allow_premium),
        ("allow_cache", effective_allow_cache),
        ("allow_export", effective_allow_export),
    ):
        if any(getattr(p, flag_name) != effective_flag for p in policies):
            restrictions.append(f"{flag_name} narrowed to {effective_flag}")

    effective_requires_redaction = any(p.requires_redaction for p in policies)
    effective_requires_approval = any(p.requires_approval for p in policies)

    effective_permissions, permissions_denied = _intersect_permissions(policies)
    if permissions_denied:
        conflicts.append(
            "permissions intersection is unsatisfiable: no actor/domain/"
            "operation/expiry combination is authorized by every source"
        )

    inherited_from: list[str] = []
    for p in policies:
        for ref in p.inherited_from:
            if ref not in inherited_from:
                inherited_from.append(ref)

    effective = PrivacyMetadata(
        policy=effective_policy,
        sensitivity=effective_sensitivity,
        allowed_processing_locations=tuple(
            sorted(effective_locations, key=lambda loc: loc.value)
        ),
        allowed_providers=effective_allowed_providers,
        prohibited_providers=tuple(sorted(effective_prohibited_providers)),
        allow_remote=effective_allow_remote,
        allow_premium=effective_allow_premium,
        allow_cache=effective_allow_cache,
        allow_export=effective_allow_export,
        requires_redaction=effective_requires_redaction,
        requires_approval=effective_requires_approval,
        inherited_from=tuple(inherited_from),
        permissions=effective_permissions,
        permissions_denied=permissions_denied,
    )

    return PrivacyResolution(
        effective=effective,
        source_count=len(policies),
        restrictions_applied=tuple(restrictions),
        conflicts=tuple(conflicts),
    )


# ── Operation evaluation ─────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class PrivacyOperationContext:
    """The caller's context, used to decide whether an operation is authorized."""

    actor_id: str | None = None
    domain: str | None = None
    processing_location: ProcessingLocation = ProcessingLocation.LOCAL
    provider_id: str | None = None
    is_premium: bool = False
    redaction_applied: bool = False
    approval_granted: bool = False
    at: datetime = field(default_factory=_utc_now)

    def __post_init__(self) -> None:
        location = _coerce_enum(
            self.processing_location, ProcessingLocation, "processing_location"
        )
        object.__setattr__(self, "processing_location", location)
        if self.provider_id is not None and not self.provider_id.strip():
            raise InvalidPrivacyMetadataError("provider_id must not be blank")
        _require_aware(self.at, "at")
        if not isinstance(self.at, datetime):
            raise InvalidPrivacyMetadataError("at must be a datetime")


@dataclass(frozen=True, slots=True)
class PrivacyDecision:
    """Unambiguous outcome of evaluating one privacy-governed operation."""

    allowed: bool
    status: PrivacyDecisionStatus
    reason_code: str
    reasons: tuple[str, ...] = ()
    requires_redaction: bool = False
    requires_approval: bool = False
    excluded: bool = False
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        status = _coerce_enum(self.status, PrivacyDecisionStatus, "status")
        object.__setattr__(self, "status", status)
        object.__setattr__(self, "reasons", tuple(str(item) for item in self.reasons))
        if not isinstance(self.metadata, Mapping):
            raise InvalidPrivacyMetadataError("metadata must be a mapping")
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))

    def to_dict(self) -> dict[str, Any]:
        return {
            "allowed": self.allowed,
            "status": self.status.value,
            "reason_code": self.reason_code,
            "reasons": list(self.reasons),
            "requires_redaction": self.requires_redaction,
            "requires_approval": self.requires_approval,
            "excluded": self.excluded,
            "metadata": dict(self.metadata),
        }


# Maps each PrivacyOperation to the ResourcePermission operation it must be
# authorized under. ResourcePermission is always consulted regardless of
# processing-policy outcome: privacy policy governs *where/whether*
# processing may happen, permissions govern *who* may trigger it.
_OPERATION_PERMISSION_MAP: Mapping[PrivacyOperation, ResourcePermissionOperation] = {
    PrivacyOperation.PROCESS_LOCAL: ResourcePermissionOperation.INFER,
    PrivacyOperation.PROCESS_REMOTE: ResourcePermissionOperation.INFER,
    PrivacyOperation.CACHE: ResourcePermissionOperation.PERSIST,
    PrivacyOperation.EXPORT: ResourcePermissionOperation.EXPORT,
    PrivacyOperation.USE_PREMIUM: ResourcePermissionOperation.INFER,
    PrivacyOperation.TRANSMIT_TO_PROVIDER: ResourcePermissionOperation.TRANSFORM,
}

_REMOTE_LIKE_OPERATIONS = frozenset(
    {PrivacyOperation.PROCESS_REMOTE, PrivacyOperation.TRANSMIT_TO_PROVIDER}
)


def _denied(
    reason_code: str, reasons: Sequence[str], **overrides: Any
) -> PrivacyDecision:
    payload: dict[str, Any] = {
        "allowed": False,
        "status": PrivacyDecisionStatus.DENIED,
        "reason_code": reason_code,
        "reasons": tuple(reasons),
        "requires_redaction": False,
        "requires_approval": False,
        "excluded": False,
    }
    payload.update(overrides)
    return PrivacyDecision(**payload)


def evaluate_privacy_operation(
    privacy: PrivacyMetadata,
    operation: PrivacyOperation,
    context: PrivacyOperationContext,
) -> PrivacyDecision:
    """Evaluate whether a single operation is authorized under ``privacy``.

    Pure and deterministic: never selects a provider, never applies a
    fallback, never performs the redaction/approval it may require.
    """
    if not isinstance(privacy, PrivacyMetadata):
        raise InvalidPrivacyMetadataError(
            f"Expected PrivacyMetadata, got {type(privacy).__name__}"
        )
    operation = cast(
        PrivacyOperation, _coerce_enum(operation, PrivacyOperation, "operation")
    )
    if not isinstance(context, PrivacyOperationContext):
        raise InvalidPrivacyMetadataError(
            f"Expected PrivacyOperationContext, got {type(context).__name__}"
        )

    if privacy.permissions_denied:
        return _denied(
            "permissions_denied",
            (
                "combined permission restrictions are unsatisfiable: no actor/domain/operation/expiry combination is authorized by every source",
            ),
        )

    if privacy.permissions:
        required_operation = _OPERATION_PERMISSION_MAP[operation]
        permitted = any(
            permission.allows(
                required_operation,
                actor_id=context.actor_id,
                domain=context.domain,
                at=context.at,
            )
            for permission in privacy.permissions
        )
        if not permitted:
            all_expired = all(
                permission.expires_at is not None and context.at > permission.expires_at
                for permission in privacy.permissions
            )
            if all_expired:
                return _denied(
                    "permission_expired",
                    ("every applicable ResourcePermission has expired",),
                )
            return _denied(
                "permission_denied",
                ("no ResourcePermission authorizes this actor/domain/operation",),
            )

    if operation in _REMOTE_LIKE_OPERATIONS:
        if privacy.policy is PrivacyPolicy.LOCAL_ONLY:
            return _denied(
                "remote_blocked_local_only",
                ("LOCAL_ONLY policy never authorizes remote operations",),
            )
        if privacy.policy is PrivacyPolicy.LOCAL_PREFERRED and not privacy.allow_remote:
            return _denied(
                "remote_blocked_not_authorized",
                (
                    "LOCAL_PREFERRED policy requires an explicit allow_remote=True exception",
                ),
            )
        if not privacy.allow_remote:
            return _denied("remote_blocked_not_allowed", ("allow_remote is False",))
        if ProcessingLocation.REMOTE not in privacy.allowed_processing_locations:
            return _denied(
                "remote_blocked_location_not_allowed",
                ("REMOTE is not in allowed_processing_locations",),
            )

    if operation is PrivacyOperation.CACHE and not privacy.allow_cache:
        return _denied("cache_blocked", ("allow_cache is False",))

    if operation is PrivacyOperation.EXPORT and not privacy.allow_export:
        return _denied("export_blocked", ("allow_export is False",))

    if operation is PrivacyOperation.USE_PREMIUM and (
        not privacy.allow_premium or privacy.policy is not PrivacyPolicy.PREMIUM_ALLOWED
    ):
        return _denied(
            "premium_blocked",
            ("premium use requires allow_premium=True and PREMIUM_ALLOWED policy",),
        )

    if operation is PrivacyOperation.TRANSMIT_TO_PROVIDER:
        provider_id = context.provider_id
        # Prohibition always prevails, checked before the allowlist.
        if provider_id is not None and provider_id in privacy.prohibited_providers:
            return _denied(
                "provider_prohibited",
                (f"provider '{provider_id}' is explicitly prohibited",),
                excluded=True,
            )
        # `allowed_providers is None` means "no allowlist configured" (every
        # non-prohibited provider is a candidate). Any other value — including
        # an explicit `()` — means only providers in that set are allowed, and
        # a request without a provider_id can never satisfy it.
        if privacy.allowed_providers is not None and (
            provider_id is None or provider_id not in privacy.allowed_providers
        ):
            return _denied(
                "provider_not_allowlisted",
                (f"provider {provider_id!r} is not in the allowed_providers list",),
                excluded=True,
            )
        if context.is_premium and (
            not privacy.allow_premium
            or privacy.policy is not PrivacyPolicy.PREMIUM_ALLOWED
        ):
            return _denied(
                "premium_blocked",
                (
                    "premium transmission requires allow_premium=True and PREMIUM_ALLOWED policy",
                ),
            )

    if privacy.requires_redaction and not context.redaction_applied:
        return PrivacyDecision(
            allowed=False,
            status=PrivacyDecisionStatus.REDACTION_REQUIRED,
            reason_code="redaction_required",
            reasons=("privacy metadata requires redaction before this operation",),
            requires_redaction=True,
            requires_approval=privacy.requires_approval
            and not context.approval_granted,
        )

    if privacy.requires_approval and not context.approval_granted:
        return PrivacyDecision(
            allowed=False,
            status=PrivacyDecisionStatus.APPROVAL_REQUIRED,
            reason_code="approval_required",
            reasons=("privacy metadata requires approval before this operation",),
            requires_approval=True,
        )

    return PrivacyDecision(
        allowed=True,
        status=PrivacyDecisionStatus.ALLOWED,
        reason_code="allowed",
    )


# ── Minimal, explicit propagation helpers ────────────────────────────────────
#
# These intentionally do not walk the Knowledge Store, do not touch
# extraction pipelines, and do not introduce new persistence. Each takes
# already-available objects and returns a PrivacyMetadata; callers wire them
# in explicitly where needed.


def privacy_from_resource(
    resource: Resource, *, privacy: PrivacyMetadata | None = None
) -> PrivacyMetadata:
    """Resolve a Resource's effective privacy metadata.

    Reuses the Resource's existing ``sensitivity`` and ``permissions``
    rather than duplicating them; ``privacy`` (if given) contributes the
    processing-policy dimension Resource does not itself carry, and is
    combined via :func:`resolve_effective_privacy_metadata` so it can only
    narrow, never widen, what the Resource's own sensitivity/permissions
    already imply.
    """
    if not isinstance(resource, Resource):
        raise InvalidPrivacyMetadataError(
            f"Expected Resource, got {type(resource).__name__}"
        )
    derived = PrivacyMetadata(
        policy=PrivacyPolicy.LOCAL_ONLY,
        sensitivity=resource.sensitivity,
        permissions=resource.permissions,
        inherited_from=(resource.id,),
    )
    if privacy is None:
        return derived
    return resolve_effective_privacy_metadata(derived, privacy).effective


def privacy_from_knowledge_item(
    item: KnowledgeItem,
    *,
    resource: Resource | None = None,
    privacy: PrivacyMetadata | None = None,
) -> PrivacyMetadata:
    """Resolve a KnowledgeItem's effective privacy metadata.

    Combines (when present): the item's own ``sensitivity``, its source
    Resource's privacy (if supplied by the caller), and an explicit
    ``privacy`` override. Does not look up the Resource automatically —
    callers pass it explicitly, keeping this a pure helper rather than a
    pipeline integration.
    """
    if not isinstance(item, KnowledgeItem):
        raise InvalidPrivacyMetadataError(
            f"Expected KnowledgeItem, got {type(item).__name__}"
        )
    sources: list[PrivacyMetadata] = [
        PrivacyMetadata(
            policy=PrivacyPolicy.LOCAL_ONLY,
            sensitivity=item.sensitivity or SensitivityLevel.RESTRICTED,
            inherited_from=(item.id,),
        )
    ]
    if resource is not None:
        sources.append(privacy_from_resource(resource))
    if privacy is not None:
        sources.append(privacy)
    return resolve_effective_privacy_metadata(*sources).effective


def _package_explicit_privacy(package: KnowledgePackage) -> PrivacyMetadata | None:
    payload = package.privacy
    if not isinstance(payload, Mapping) or "policy" not in payload:
        return None
    try:
        return PrivacyMetadata.from_mapping(payload)
    except InvalidPrivacyMetadataError:
        return None


def privacy_from_knowledge_package(
    package: KnowledgePackage, *, privacy: PrivacyMetadata | None = None
) -> PrivacyMetadata:
    """Resolve a KnowledgePackage's effective privacy metadata.

    Normalizes the generic ``privacy`` mapping introduced in Phase 8.23
    without changing its stored type: a well-formed serialized
    ``PrivacyMetadata`` mapping is recognized and honored; any other mapping
    (including historical, unstructured payloads such as
    ``{"classification": "internal"}``) is safely ignored rather than
    raising. The result is the most restrictive combination of the
    package's resources, its items' own sensitivity, any recognized
    explicit package-level privacy, and an optional caller-supplied
    ``privacy`` override.
    """
    if not isinstance(package, KnowledgePackage):
        raise InvalidPrivacyMetadataError(
            f"Expected KnowledgePackage, got {type(package).__name__}"
        )
    sources: list[PrivacyMetadata] = [
        privacy_from_resource(resource) for resource in package.resources
    ]
    for category in (
        package.facts,
        package.observations,
        package.inferences,
        package.hypotheses,
        package.other_knowledge,
    ):
        for item in category:
            sources.append(privacy_from_knowledge_item(item))
    explicit = _package_explicit_privacy(package)
    if explicit is not None:
        sources.append(explicit)
    if privacy is not None:
        sources.append(privacy)
    if not sources:
        return PrivacyMetadata()
    return resolve_effective_privacy_metadata(*sources).effective


__all__ = [
    "PRIVACY_METADATA_SCHEMA_VERSION",
    "PrivacyDecision",
    "PrivacyDecisionStatus",
    "PrivacyMetadata",
    "PrivacyOperation",
    "PrivacyOperationContext",
    "PrivacyPolicy",
    "PrivacyResolution",
    "ProcessingLocation",
    "evaluate_privacy_operation",
    "privacy_from_knowledge_item",
    "privacy_from_knowledge_package",
    "privacy_from_resource",
    "resolve_effective_privacy_metadata",
]
