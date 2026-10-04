"""Versioned, secret-free persisted state for the Provider Registry (MAJOR-02).

This module owns the *shape* of the durable Provider Registry aggregate: one
immutable envelope carrying the canonical providers, their bound manifests, the
canonical model catalog entries, the accepted connections, the provider model
routes and a sanitized audit log, together with an explicit
:data:`SCHEMA_VERSION` and a monotonically meaningful revision.

Security boundary. Only opaque ``credential_ref`` values cross this boundary:
the serializer names every persisted field explicitly instead of delegating to
``dataclasses.asdict()``, so a future field cannot leak into persisted bytes by
existing. Deserialization additionally rejects secret-shaped values in
credential refs and audit detail, so a hand-edited or corrupted file cannot
smuggle plaintext material into the aggregate.

Determinism. ``to_dict()`` returns collections in canonical identity order
(providers by id, manifests by provider id, models by qualified id, connections
by connection id, routes by route id, audit records by
``(revision, occurred_at, event_type, entity_kind, entity_id)``), so two equal
states serialize to equal mappings and a repository can hash or diff them
reliably.

Fail-closed validation. An unsupported schema version raises
:class:`ProviderStateSchemaError`; a negative revision, a naive timestamp, a
missing field, an unknown field or a malformed payload raises
:class:`ProviderStateSerializationError`. Nothing partial is ever returned.

Manifest shape Ruling (MAJOR-V2-03): ``ProviderManifest`` gained the required
``requires_isolation`` policy field, so the persisted manifest shape changed and
:data:`SCHEMA_VERSION` was bumped with it. A document written before that change
is rejected by version rather than loaded with an assumed policy, and a manifest
entry that is missing the field — or carries an unknown one — is rejected by the
same fail-closed key checks every other persisted field uses. No migration path
and no legacy reader are introduced: an aggregate that this build cannot
reconstruct exactly is never partially accepted.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Final

from kernel.llm.capabilities import ModelCapabilities, ProviderCapabilities
from kernel.llm.model_catalog import ModelSpec
from kernel.llm.model_routes import (
    CapabilityConfidence,
    ModelRoute,
    RouteCapabilityState,
)
from kernel.llm.provider_connections import (
    BillingClass,
    ConnectionStatus,
    ProviderConnection,
)
from kernel.llm.provider_manifests import FIRST_WAVE_AUTH_SCHEME, ProviderManifest
from kernel.llm.provider_registry import ProviderSpec

SCHEMA_VERSION: Final[str] = "2"
"""The only persisted envelope version this build can read or write.

``"2"`` adds the required ``requires_isolation`` manifest policy field to the
``"1"`` shape; ``"1"`` documents are rejected by
:class:`ProviderStateSchemaError` instead of being read with an assumed policy
(module docstring, Manifest shape Ruling)."""

# Substrings marking a persisted value as carrying plaintext secret material.
# Checked case-insensitively against the whole value, mirroring the guard in
# ``provider_connections`` so a marker cannot slip past either boundary.
_SECRET_MARKERS: Final[tuple[str, ...]] = (
    "sk-",
    "api-key",
    "password=",
    "token=",
    "bearer",
)

_REQUIRED_KEYS: Final[tuple[str, ...]] = (
    "schema_version",
    "revision",
    "providers",
    "manifests",
    "models",
    "connections",
    "routes",
    "audit_log",
)


class ProviderStateError(ValueError):
    """Base error for invalid Provider Registry persisted state."""


class ProviderStateSchemaError(ProviderStateError):
    """The envelope's schema version is not supported by this build."""


class ProviderStateSerializationError(ProviderStateError):
    """A persisted payload is malformed, incomplete, or carries secrets."""


class ProviderStateCoherenceError(ProviderStateError):
    """Live components do not form one referentially coherent aggregate.

    Raised at capture time when a component carries an entry the canonical
    authority does not hold, so an unrestorable aggregate is never built.
    """


def _reject_secret_shaped(value: str, *, label: str) -> str:
    """Reject plaintext secret markers; return the value unchanged."""
    lowered = value.lower()
    for marker in _SECRET_MARKERS:
        if marker in lowered:
            raise ProviderStateSerializationError(
                f"{label} must not carry plaintext secrets"
            )
    return value


def _require_mapping(value: object, *, label: str) -> Mapping[str, object]:
    """Require a mapping payload; reject scalars and sequences."""
    if not isinstance(value, Mapping):
        raise ProviderStateSerializationError(f"{label} must be a mapping")
    return value


def _require_text(value: object, *, label: str) -> str:
    """Require a non-blank string."""
    if not isinstance(value, str) or not value.strip():
        raise ProviderStateSerializationError(f"{label} must be a non-empty string")
    return value


def _optional_text(value: object, *, label: str) -> str | None:
    """Require ``None`` or a string; blank strings and markers are allowed here.

    Read-side only: the envelope-level secret scan (see
    :func:`_reject_secret_strings`) rejects marker-shaped strings before any
    field parser runs, and blank optional strings are legitimate domain values
    (e.g. ``ProviderSpec(region="")``), so this check stays structural — the
    value objects themselves validate what matters.
    """
    if value is None:
        return None
    if not isinstance(value, str):
        raise ProviderStateSerializationError(f"{label} must be a string")
    return value


def _reject_secret_strings(value: object, *, label: str = "persisted state") -> None:
    """Recursively reject secret-shaped strings anywhere in an envelope.

    Applied at the persistence boundary in both directions: ``to_dict()``
    refuses to emit (and therefore persist) any secret-shaped string in any
    field — not only credential refs — and ``from_dict()`` refuses to rebuild
    from one. The single documented exemption is the pinned bearer
    auth-scheme value, which is part of the domain, not a secret.
    """
    if isinstance(value, Mapping):
        for key, item in value.items():
            if key == "auth_scheme" and item == FIRST_WAVE_AUTH_SCHEME:
                continue
            _reject_secret_shaped(str(key), label=f"{label} key {key!r}")
            _reject_secret_strings(item, label=f"{label}.{key}")
        return
    if isinstance(value, (list, tuple)):
        for index, item in enumerate(value):
            _reject_secret_strings(item, label=f"{label}[{index}]")
        return
    if isinstance(value, str):
        _reject_secret_shaped(value, label=f"{label} value")


def _require_bool(value: object, *, label: str) -> bool:
    """Require a bool; reject truthy non-bools."""
    if not isinstance(value, bool):
        raise ProviderStateSerializationError(f"{label} must be a bool")
    return value


def _require_optional_bool(value: object, *, label: str) -> bool | None:
    """Require a bool or an explicit absence.

    Used only for the three-state capabilities, where ``None`` means the
    authority declared nothing. Round-tripping an absent declaration as
    ``False`` is what turned "unknown" into "known to have none" on every
    reload, so the persisted state keeps the distinction.
    """
    if value is None:
        return None
    return _require_bool(value, label=label)


def _require_int(value: object, *, label: str) -> int:
    """Require an integer; reject bools and floats."""
    if isinstance(value, bool) or not isinstance(value, int):
        raise ProviderStateSerializationError(f"{label} must be an integer")
    return value


def _require_sequence(value: object, *, label: str) -> Sequence[object]:
    """Require a list/tuple payload; reject strings and mappings."""
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        raise ProviderStateSerializationError(f"{label} must be a list")
    return value


def _require_aware(value: object, *, label: str) -> datetime:
    """Parse an ISO-8601 timestamp and require an explicit timezone."""
    text = _require_text(value, label=label)
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        raise ProviderStateSerializationError(
            f"{label} must be an ISO-8601 timestamp"
        ) from None
    if parsed.tzinfo is None:
        raise ProviderStateError(f"{label} must be timezone-aware")
    return parsed


def _optional_aware(value: object, *, label: str) -> datetime | None:
    """Parse ``None`` or a timezone-aware ISO-8601 timestamp."""
    if value is None:
        return None
    return _require_aware(value, label=label)


def _isoformat(value: datetime | None, *, label: str) -> str | None:
    """Render an aware timestamp as ISO-8601; reject naive values."""
    if value is None:
        return None
    if value.tzinfo is None:
        raise ProviderStateError(f"{label} must be timezone-aware")
    return value.isoformat()


def _decimal_text(value: Decimal | None, *, label: str) -> str | None:
    """Render an optional cost as exact decimal text (never a float)."""
    if value is None:
        return None
    return format(value, "f")


def _decimal_value(value: object, *, label: str) -> Decimal | None:
    """Parse an optional exact decimal cost from its string form."""
    if value is None:
        return None
    text = _require_text(value, label=label)
    try:
        parsed = Decimal(text)
    except InvalidOperation:
        raise ProviderStateSerializationError(
            f"{label} must be a decimal number"
        ) from None
    if not parsed.is_finite():
        raise ProviderStateSerializationError(
            f"{label} must be a finite decimal number"
        )
    return parsed


def _map_to_dict(
    pairs: tuple[tuple[str, str], ...],
) -> list[list[str]]:
    """Render ordered key/value pairs as JSON-friendly nested lists."""
    return [[key, value] for key, value in pairs]


def _pairs_from(value: object, *, label: str) -> tuple[tuple[str, str], ...]:
    """Parse ordered key/value pairs, rejecting secret-shaped entries."""
    items = _require_sequence(value, label=label)
    pairs: list[tuple[str, str]] = []
    for item in items:
        entry = _require_sequence(item, label=f"{label} entry")
        if len(entry) != 2:
            raise ProviderStateSerializationError(
                f"{label} entries must be (key, value) pairs"
            )
        key = _require_text(entry[0], label=f"{label} key")
        raw = _require_text(entry[1], label=f"{label} value")
        _reject_secret_shaped(key, label=f"{label} key")
        _reject_secret_shaped(raw, label=f"{label} value")
        pairs.append((key, raw))
    return tuple(pairs)


@dataclass(frozen=True, slots=True)
class ProviderRegistryAuditRecord:
    """One sanitized state transition; never carries secret material."""

    revision: int
    event_type: str
    entity_kind: str
    entity_id: str
    occurred_at: datetime
    detail: tuple[tuple[str, str], ...] = ()

    def __post_init__(self) -> None:
        """Validate the audit record and normalize its detail pairs."""
        if isinstance(self.revision, bool) or not isinstance(self.revision, int):
            raise ProviderStateError("audit revision must be an integer")
        if self.revision < 0:
            raise ProviderStateError("audit revision cannot be negative")
        for name in ("event_type", "entity_kind", "entity_id"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise ProviderStateError(f"{name} cannot be empty")
        if self.occurred_at.tzinfo is None:
            raise ProviderStateError("occurred_at must be timezone-aware")
        pairs = tuple(tuple(pair) for pair in self.detail)
        for key, value in pairs:
            if not key.strip() or not value.strip():
                raise ProviderStateError("detail cannot contain empty keys or values")
        object.__setattr__(self, "detail", pairs)

    def to_dict(self) -> dict[str, object]:
        """Return a primitive-serializable mapping of this record."""
        return {
            "revision": self.revision,
            "event_type": self.event_type,
            "entity_kind": self.entity_kind,
            "entity_id": self.entity_id,
            "occurred_at": self.occurred_at.isoformat(),
            "detail": _map_to_dict(self.detail),
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, object]) -> ProviderRegistryAuditRecord:
        """Rebuild an audit record, rejecting secret-shaped detail."""
        mapping = _require_mapping(payload, label="audit record")
        expected = {
            "revision",
            "event_type",
            "entity_kind",
            "entity_id",
            "occurred_at",
            "detail",
        }
        _reject_unknown_keys(mapping, expected, label="audit record")
        _require_keys(mapping, expected, label="audit record")
        detail = _pairs_from(mapping["detail"], label="audit detail")
        for key, value in detail:
            _reject_secret_shaped(key, label="audit detail key")
            _reject_secret_shaped(value, label="audit detail value")
        return cls(
            revision=_require_int(mapping["revision"], label="revision"),
            event_type=_require_text(mapping["event_type"], label="event_type"),
            entity_kind=_require_text(mapping["entity_kind"], label="entity_kind"),
            entity_id=_require_text(mapping["entity_id"], label="entity_id"),
            occurred_at=_require_aware(mapping["occurred_at"], label="occurred_at"),
            detail=detail,
        )


def _reject_unknown_keys(
    payload: Mapping[str, object],
    expected: set[str] | frozenset[str],
    *,
    label: str,
) -> None:
    """Fail closed on a field this build does not understand."""
    unknown = sorted(set(payload) - set(expected))
    if unknown:
        raise ProviderStateSerializationError(f"unknown field in {label}: {unknown[0]}")


def _require_keys(
    payload: Mapping[str, object],
    required: set[str] | frozenset[str],
    *,
    label: str,
) -> None:
    """Fail closed on a missing required field."""
    missing = sorted(set(required) - set(payload))
    if missing:
        raise ProviderStateSerializationError(f"missing required field: {missing[0]}")


def _provider_to_dict(spec: ProviderSpec) -> dict[str, object]:
    """Serialize one canonical provider definition field by field."""
    return {
        "id": spec.id,
        "provider_type": spec.provider_type,
        "api_style": spec.api_style,
        "api_key_env": spec.api_key_env,
        "base_url": spec.base_url,
        "base_url_env": spec.base_url_env,
        "enabled": spec.enabled,
        "region": spec.region,
        "data_policy": spec.data_policy,
        "availability": spec.availability,
        "capabilities": {
            "chat_completions": spec.capabilities.chat_completions,
            "responses_api": spec.capabilities.responses_api,
            "streaming": spec.capabilities.streaming,
            "embeddings": spec.capabilities.embeddings,
        },
    }


def _provider_from_dict(payload: Mapping[str, object]) -> ProviderSpec:
    """Rebuild one canonical provider definition from persisted fields."""
    mapping = _require_mapping(payload, label="provider")
    expected = {
        "id",
        "provider_type",
        "api_style",
        "api_key_env",
        "base_url",
        "base_url_env",
        "enabled",
        "region",
        "data_policy",
        "availability",
        "capabilities",
    }
    _reject_unknown_keys(mapping, expected, label="provider")
    _require_keys(mapping, expected, label="provider")
    capabilities = _require_mapping(mapping["capabilities"], label="capabilities")
    cap_keys = {
        "chat_completions",
        "responses_api",
        "streaming",
        "embeddings",
    }
    _reject_unknown_keys(capabilities, cap_keys, label="capabilities")
    _require_keys(capabilities, cap_keys, label="capabilities")
    try:
        return ProviderSpec(
            id=_require_text(mapping["id"], label="provider id"),
            provider_type=_require_text(  # type: ignore[arg-type]
                mapping["provider_type"], label="provider_type"
            ),
            api_style=_require_text(  # type: ignore[arg-type]
                mapping["api_style"], label="api_style"
            ),
            api_key_env=_optional_text(mapping["api_key_env"], label="api_key_env"),
            base_url=_optional_text(mapping["base_url"], label="base_url"),
            base_url_env=_optional_text(mapping["base_url_env"], label="base_url_env"),
            enabled=_require_bool(mapping["enabled"], label="enabled"),
            region=_optional_text(mapping["region"], label="region"),
            data_policy=_optional_text(mapping["data_policy"], label="data_policy"),
            availability=_require_text(  # type: ignore[arg-type]
                mapping["availability"], label="availability"
            ),
            capabilities=ProviderCapabilities(
                chat_completions=_require_bool(
                    capabilities["chat_completions"], label="chat_completions"
                ),
                responses_api=_require_bool(
                    capabilities["responses_api"], label="responses_api"
                ),
                streaming=_require_bool(capabilities["streaming"], label="streaming"),
                embeddings=_require_bool(
                    capabilities["embeddings"], label="embeddings"
                ),
            ),
        )
    except ValueError as error:
        raise ProviderStateSerializationError(f"invalid provider: {error}") from error


def _manifest_to_dict(manifest: ProviderManifest) -> dict[str, object]:
    """Serialize one declarative manifest field by field."""
    return {
        "provider_id": manifest.provider_id,
        "display_name": manifest.display_name,
        "billing_class": manifest.billing_class.value,
        "default_base_url": manifest.default_base_url,
        "auth_scheme": manifest.auth_scheme,
        "models_path": manifest.models_path,
        "api_styles": list(manifest.api_styles),
        "activation_allowlist": list(manifest.activation_allowlist),
        "requires_isolation": manifest.requires_isolation,
    }


def _manifest_from_dict(payload: Mapping[str, object]) -> ProviderManifest:
    """Rebuild one declarative manifest from persisted fields."""
    mapping = _require_mapping(payload, label="manifest")
    expected = {
        "provider_id",
        "display_name",
        "billing_class",
        "default_base_url",
        "auth_scheme",
        "models_path",
        "api_styles",
        "activation_allowlist",
        "requires_isolation",
    }
    _reject_unknown_keys(mapping, expected, label="manifest")
    _require_keys(mapping, expected, label="manifest")
    # Fail closed on a missing or non-bool policy: an isolation-required bridge
    # must never be reconstructed from an assumed default. Checked before the
    # constructor try-block so the structural error is not re-wrapped.
    requires_isolation = _require_bool(
        mapping["requires_isolation"], label="requires_isolation"
    )
    try:
        return ProviderManifest(
            provider_id=_require_text(mapping["provider_id"], label="provider_id"),
            display_name=_require_text(mapping["display_name"], label="display_name"),
            billing_class=BillingClass(
                _require_text(mapping["billing_class"], label="billing_class")
            ),
            default_base_url=_require_text(
                mapping["default_base_url"], label="default_base_url"
            ),
            auth_scheme=_require_text(mapping["auth_scheme"], label="auth_scheme"),
            models_path=_require_text(mapping["models_path"], label="models_path"),
            api_styles=tuple(
                _require_text(item, label="api_styles entry")
                for item in _require_sequence(mapping["api_styles"], label="api_styles")
            ),
            activation_allowlist=tuple(
                _require_text(item, label="activation_allowlist entry")
                for item in _require_sequence(
                    mapping["activation_allowlist"], label="activation_allowlist"
                )
            ),
            requires_isolation=requires_isolation,
        )
    except ValueError as error:
        raise ProviderStateSerializationError(f"invalid manifest: {error}") from error


def _model_to_dict(spec: ModelSpec) -> dict[str, object]:
    """Serialize one canonical model definition field by field."""
    return {
        "id": spec.id,
        "provider_id": spec.provider_id,
        "qualified_id": spec.qualified_id,
        "context_window": spec.context_window,
        "aliases": list(spec.aliases),
        "input_cost_per_million": _decimal_text(
            spec.input_cost_per_million, label="input_cost_per_million"
        ),
        "output_cost_per_million": _decimal_text(
            spec.output_cost_per_million, label="output_cost_per_million"
        ),
        "cached_input_cost_per_million": _decimal_text(
            spec.cached_input_cost_per_million, label="cached_input_cost_per_million"
        ),
        "availability": spec.availability,
        "version": spec.version,
        "capabilities": {
            "reasoning": spec.capabilities.reasoning,
            "tool_calling": spec.capabilities.tool_calling,
            "structured_output": spec.capabilities.structured_output,
            "json_mode": spec.capabilities.json_mode,
            "json_schema": spec.capabilities.json_schema,
            "vision": spec.capabilities.vision,
            "audio_input": spec.capabilities.audio_input,
            "audio_output": spec.capabilities.audio_output,
            "embeddings": spec.capabilities.embeddings,
        },
    }


_MODEL_CAPABILITY_NAMES: Final[tuple[str, ...]] = (
    "reasoning",
    "tool_calling",
    "structured_output",
    "json_mode",
    "json_schema",
    "vision",
    "audio_input",
    "audio_output",
    "embeddings",
)


def _model_from_dict(payload: Mapping[str, object]) -> ModelSpec:
    """Rebuild one canonical model definition from persisted fields."""
    mapping = _require_mapping(payload, label="model")
    expected = {
        "id",
        "provider_id",
        "qualified_id",
        "context_window",
        "aliases",
        "input_cost_per_million",
        "output_cost_per_million",
        "cached_input_cost_per_million",
        "availability",
        "version",
        "capabilities",
    }
    _reject_unknown_keys(mapping, expected, label="model")
    _require_keys(mapping, expected, label="model")
    capabilities = _require_mapping(mapping["capabilities"], label="model capabilities")
    cap_keys = frozenset(_MODEL_CAPABILITY_NAMES)
    _reject_unknown_keys(capabilities, cap_keys, label="model capabilities")
    _require_keys(capabilities, cap_keys, label="model capabilities")
    context_window = mapping["context_window"]
    try:
        return ModelSpec(
            id=_require_text(mapping["id"], label="model id"),
            provider_id=_require_text(mapping["provider_id"], label="provider_id"),
            context_window=(
                None
                if context_window is None
                else _require_int(context_window, label="context_window")
            ),
            capabilities=ModelCapabilities(
                **{
                    name: (
                        _require_optional_bool(capabilities[name], label=name)
                        if name == "reasoning"
                        else _require_bool(capabilities[name], label=name)
                    )
                    for name in _MODEL_CAPABILITY_NAMES
                }
            ),
            aliases=tuple(
                _require_text(item, label="alias")
                for item in _require_sequence(mapping["aliases"], label="aliases")
            ),
            input_cost_per_million=_decimal_value(
                mapping["input_cost_per_million"], label="input_cost_per_million"
            ),
            output_cost_per_million=_decimal_value(
                mapping["output_cost_per_million"], label="output_cost_per_million"
            ),
            cached_input_cost_per_million=_decimal_value(
                mapping["cached_input_cost_per_million"],
                label="cached_input_cost_per_million",
            ),
            availability=_require_text(  # type: ignore[arg-type]
                mapping["availability"], label="availability"
            ),
            version=_optional_text(mapping["version"], label="version"),
        )
    except ValueError as error:
        raise ProviderStateSerializationError(f"invalid model: {error}") from error


def _connection_to_dict(connection: ProviderConnection) -> dict[str, object]:
    """Serialize one accepted connection field by field (refs, never secrets)."""
    return {
        "connection_id": connection.connection_id,
        "provider_id": connection.provider_id,
        "display_name": connection.display_name,
        "billing_class": connection.billing_class.value,
        "credential_ref": connection.credential_ref,
        "endpoint": connection.endpoint,
        "isolation_profile_ref": connection.isolation_profile_ref,
        "status": connection.status.value,
        "created_at": _isoformat(connection.created_at, label="created_at"),
        "last_validated_at": _isoformat(
            connection.last_validated_at, label="last_validated_at"
        ),
    }


def _connection_from_dict(payload: Mapping[str, object]) -> ProviderConnection:
    """Rebuild one accepted connection, rejecting secret-shaped refs."""
    mapping = _require_mapping(payload, label="connection")
    expected = {
        "connection_id",
        "provider_id",
        "display_name",
        "billing_class",
        "credential_ref",
        "endpoint",
        "isolation_profile_ref",
        "status",
        "created_at",
        "last_validated_at",
    }
    _reject_unknown_keys(mapping, expected, label="connection")
    _require_keys(mapping, expected, label="connection")
    credential_ref = _optional_text(mapping["credential_ref"], label="credential_ref")
    if credential_ref is not None:
        _reject_secret_shaped(credential_ref, label="credential_ref")
    try:
        return ProviderConnection(
            connection_id=_require_text(
                mapping["connection_id"], label="connection_id"
            ),
            provider_id=_require_text(mapping["provider_id"], label="provider_id"),
            display_name=_require_text(mapping["display_name"], label="display_name"),
            billing_class=BillingClass(
                _require_text(mapping["billing_class"], label="billing_class")
            ),
            credential_ref=credential_ref,
            endpoint=_require_text(mapping["endpoint"], label="endpoint"),
            isolation_profile_ref=_optional_text(
                mapping["isolation_profile_ref"], label="isolation_profile_ref"
            ),
            status=ConnectionStatus(_require_text(mapping["status"], label="status")),
            created_at=_optional_aware(mapping["created_at"], label="created_at"),
            last_validated_at=_optional_aware(
                mapping["last_validated_at"], label="last_validated_at"
            ),
        )
    except ValueError as error:
        raise ProviderStateSerializationError(f"invalid connection: {error}") from error


def _route_to_dict(route: ModelRoute) -> dict[str, object]:
    """Serialize one provider model route field by field."""
    return {
        "route_id": route.route_id,
        "connection_id": route.connection_id,
        "provider_model_id": route.provider_model_id,
        "canonical_model_id": route.canonical_model_id,
        "available": route.available,
        "first_seen_at": _isoformat(route.first_seen_at, label="first_seen_at"),
        "last_seen_at": _isoformat(route.last_seen_at, label="last_seen_at"),
        "capabilities": [
            {
                "name": capability.name,
                "supported": capability.supported,
                "confidence": capability.confidence.value,
            }
            for capability in route.capabilities
        ],
    }


def _route_from_dict(payload: Mapping[str, object]) -> ModelRoute:
    """Rebuild one provider model route from persisted fields."""
    mapping = _require_mapping(payload, label="route")
    expected = {
        "route_id",
        "connection_id",
        "provider_model_id",
        "canonical_model_id",
        "available",
        "first_seen_at",
        "last_seen_at",
        "capabilities",
    }
    _reject_unknown_keys(mapping, expected, label="route")
    _require_keys(mapping, expected, label="route")
    capabilities: list[RouteCapabilityState] = []
    for item in _require_sequence(mapping["capabilities"], label="route capabilities"):
        claim = _require_mapping(item, label="route capability")
        claim_keys = {"name", "supported", "confidence"}
        _reject_unknown_keys(claim, claim_keys, label="route capability")
        _require_keys(claim, claim_keys, label="route capability")
        try:
            capabilities.append(
                RouteCapabilityState(
                    name=_require_text(claim["name"], label="capability name"),
                    supported=_require_bool(
                        claim["supported"], label="capability supported"
                    ),
                    confidence=CapabilityConfidence(
                        _require_text(
                            claim["confidence"], label="capability confidence"
                        )
                    ),
                )
            )
        except ValueError as error:
            raise ProviderStateSerializationError(
                f"invalid route capability: {error}"
            ) from error
    try:
        return ModelRoute(
            route_id=_require_text(mapping["route_id"], label="route_id"),
            connection_id=_require_text(
                mapping["connection_id"], label="connection_id"
            ),
            provider_model_id=_require_text(
                mapping["provider_model_id"], label="provider_model_id"
            ),
            canonical_model_id=_require_text(
                mapping["canonical_model_id"], label="canonical_model_id"
            ),
            available=_require_bool(mapping["available"], label="available"),
            first_seen_at=_optional_aware(
                mapping["first_seen_at"], label="first_seen_at"
            ),
            last_seen_at=_optional_aware(mapping["last_seen_at"], label="last_seen_at"),
            capabilities=tuple(capabilities),
        )
    except ValueError as error:
        raise ProviderStateSerializationError(f"invalid route: {error}") from error


def _provider_sort_key(spec: ProviderSpec) -> str:
    """Canonical identity order for providers."""
    return spec.id


def _manifest_sort_key(manifest: ProviderManifest) -> str:
    """Canonical identity order for manifests."""
    return manifest.provider_id


def _model_sort_key(spec: ModelSpec) -> str:
    """Canonical identity order for models."""
    return spec.qualified_id


def _connection_sort_key(connection: ProviderConnection) -> str:
    """Canonical identity order for connections."""
    return connection.connection_id


def _route_sort_key(route: ModelRoute) -> str:
    """Canonical identity order for routes."""
    return route.route_id


def _audit_sort_key(
    record: ProviderRegistryAuditRecord,
) -> tuple[int, datetime, str, str, str]:
    """Canonical order for audit records: revision, then full identity."""
    return (
        record.revision,
        record.occurred_at,
        record.event_type,
        record.entity_kind,
        record.entity_id,
    )


@dataclass(frozen=True, slots=True)
class ProviderRegistryState:
    """Immutable, versioned snapshot of the whole Provider Registry aggregate.

    Collections are stored in canonical identity order (see the module
    docstring), so equal aggregates are equal objects and serialization is
    stable without depending on caller insertion order.
    """

    schema_version: str
    revision: int
    providers: tuple[ProviderSpec, ...]
    manifests: tuple[ProviderManifest, ...]
    models: tuple[ModelSpec, ...]
    connections: tuple[ProviderConnection, ...]
    routes: tuple[ModelRoute, ...]
    audit_log: tuple[ProviderRegistryAuditRecord, ...] = ()

    def __post_init__(self) -> None:
        """Validate the envelope and store collections in canonical order.

        Ordering is normalized here rather than at serialization time so two
        equal aggregates built from differently ordered inputs are equal
        *objects*, and ``from_dict(to_dict())`` reproduces the original exactly.
        """
        if self.schema_version != SCHEMA_VERSION:
            raise ProviderStateSchemaError(
                f"unsupported schema_version: {self.schema_version!r}"
            )
        if isinstance(self.revision, bool) or not isinstance(self.revision, int):
            raise ProviderStateError("revision must be an integer")
        if self.revision < 0:
            raise ProviderStateError("revision cannot be negative")
        for name, expected, key in (
            ("providers", ProviderSpec, _provider_sort_key),
            ("manifests", ProviderManifest, _manifest_sort_key),
            ("models", ModelSpec, _model_sort_key),
            ("connections", ProviderConnection, _connection_sort_key),
            ("routes", ModelRoute, _route_sort_key),
            ("audit_log", ProviderRegistryAuditRecord, _audit_sort_key),
        ):
            values = tuple(getattr(self, name))
            for value in values:
                if not isinstance(value, expected):
                    raise ProviderStateError(
                        f"{name} must hold {expected.__name__} entries"
                    )
            object.__setattr__(self, name, tuple(sorted(values, key=key)))

    def to_dict(self) -> dict[str, object]:
        """Return the deterministic, primitive-serializable envelope.

        Every collection is already in canonical identity order (normalized at
        construction), so this mapping is byte-stable for equal aggregates.
        The finished mapping passes the envelope secret scan, so no
        secret-shaped string can cross the persistence boundary.
        """
        payload: dict[str, object] = {
            "schema_version": self.schema_version,
            "revision": self.revision,
            "providers": [_provider_to_dict(item) for item in self.providers],
            "manifests": [_manifest_to_dict(item) for item in self.manifests],
            "models": [_model_to_dict(item) for item in self.models],
            "connections": [_connection_to_dict(item) for item in self.connections],
            "routes": [_route_to_dict(item) for item in self.routes],
            "audit_log": [item.to_dict() for item in self.audit_log],
        }
        _reject_secret_strings(payload)
        return payload

    @classmethod
    def from_dict(cls, payload: Mapping[str, object]) -> ProviderRegistryState:
        """Rebuild the envelope, failing closed on any invalid field."""
        mapping = _require_mapping(payload, label="provider registry state")
        _reject_secret_strings(mapping)
        expected = frozenset(_REQUIRED_KEYS)
        _reject_unknown_keys(mapping, expected, label="provider registry state")
        _require_keys(mapping, expected, label="provider registry state")
        schema_version = _require_text(
            mapping["schema_version"], label="schema_version"
        )
        if schema_version != SCHEMA_VERSION:
            raise ProviderStateSchemaError(
                f"unsupported schema_version: {schema_version!r}"
            )
        revision = _require_int(mapping["revision"], label="revision")
        if revision < 0:
            raise ProviderStateError("revision cannot be negative")
        return cls(
            schema_version=schema_version,
            revision=revision,
            providers=tuple(
                _provider_from_dict(item)
                for item in _require_sequence(mapping["providers"], label="providers")
            ),
            manifests=tuple(
                _manifest_from_dict(item)
                for item in _require_sequence(mapping["manifests"], label="manifests")
            ),
            models=tuple(
                _model_from_dict(item)
                for item in _require_sequence(mapping["models"], label="models")
            ),
            connections=tuple(
                _connection_from_dict(item)
                for item in _require_sequence(
                    mapping["connections"], label="connections"
                )
            ),
            routes=tuple(
                _route_from_dict(item)
                for item in _require_sequence(mapping["routes"], label="routes")
            ),
            audit_log=tuple(
                ProviderRegistryAuditRecord.from_dict(item)
                for item in _require_sequence(mapping["audit_log"], label="audit_log")
            ),
        )
