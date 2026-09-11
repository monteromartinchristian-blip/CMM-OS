"""Phase 10.50 – Domain-owned privacy policy declarations.

Declarative, immutable, versioned Domain specialization of the canonical Phase 8
:class:`cmm.cognitive.privacy.PrivacyMetadata` processing policy.

A ``DomainPrivacyPolicy`` is a *restrictive input only*. It declares the starting
privacy posture for one Domain Pack and projects into canonical
``PrivacyMetadata``; it never resolves effective privacy, never evaluates an
operation, never grants remote/provider/export/cache/approval authority and never
replaces the canonical Phase 8 resolver/evaluator or the Phase 10.15 permission
chain.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass, field, replace
from types import MappingProxyType
from typing import Any

from cmm.cognitive.privacy import PrivacyMetadata, ProcessingLocation
from cmm.domains.errors import (
    DomainPrivacyPolicyContractError,
    DomainPrivacyPolicySerializationError,
)
from cmm.domains.identifiers import DomainId

__all__ = [
    "DOMAIN_PRIVACY_POLICY_SCHEMA_VERSION",
    "DomainPrivacyPolicy",
    "project_domain_privacy_metadata",
]

DOMAIN_PRIVACY_POLICY_SCHEMA_VERSION = "1"

# Mirrors ``cmm.domains.registry_contracts`` sensitive-key vocabulary so the
# Domain privacy contract fails closed on credential-like declarative metadata
# without importing the ``contracts`` module that owns ``DomainDefinition``.
_SENSITIVE_EXACT_WORDS = frozenset(
    {
        "secret",
        "secrets",
        "password",
        "passwords",
        "token",
        "tokens",
        "credential",
        "credentials",
        "apikey",
        "api_key",
        "privatekey",
        "private_key",
        "auth_token",
        "authtoken",
        "access_key",
        "accesskey",
        "secret_key",
        "secretkey",
    }
)
_SENSITIVE_KEY_PARTS = frozenset({"secret", "password", "token", "credential"})

_KNOWN = frozenset(
    {
        "schema_version",
        "domain_id",
        "default_privacy",
        "require_approval_for_remote",
        "metadata",
    }
)

# Exact canonical serialized ``PrivacyMetadata`` field set, derived from
# ``PrivacyMetadata.serialize()`` in ``cmm/cognitive/privacy.py``. The Domain
# declarative adapter is deliberately stricter than the tolerant canonical
# ``from_mapping`` parser: it fails closed on unknown nested authority-like
# fields (for example ``allow_cross_domain``) instead of silently ignoring them.
_PRIVACY_METADATA_FIELDS = frozenset(
    {
        "schema_version",
        "policy",
        "sensitivity",
        "allowed_processing_locations",
        "allowed_providers",
        "prohibited_providers",
        "allow_remote",
        "allow_premium",
        "allow_cache",
        "allow_export",
        "requires_redaction",
        "requires_approval",
        "inherited_from",
        "permissions",
        "permissions_denied",
        "metadata",
    }
)


# ── JSON-safety, freezing and validation helpers ──────────────────────────────


def _require_non_empty_str(value: Any, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise DomainPrivacyPolicyContractError(
            f"{field_name} must be a non-empty string", field=field_name
        )
    return value.strip()


def _require_domain_id(value: Any, field_name: str) -> DomainId:
    if not isinstance(value, DomainId):
        raise DomainPrivacyPolicyContractError(
            f"{field_name} must be a DomainId, got {type(value).__name__}",
            field=field_name,
        )
    return value


def _require_privacy_metadata(value: Any, field_name: str) -> PrivacyMetadata:
    if not isinstance(value, PrivacyMetadata):
        raise DomainPrivacyPolicyContractError(
            f"{field_name} must be a canonical PrivacyMetadata, "
            f"got {type(value).__name__}",
            field=field_name,
        )
    return value


def _require_strict_bool(value: Any, field_name: str) -> bool:
    if not isinstance(value, bool):
        raise DomainPrivacyPolicyContractError(
            f"{field_name} must be a boolean (True or False), "
            f"got {type(value).__name__}: {value!r}",
            field=field_name,
        )
    return value


def _require_json_value(value: Any, field_name: str) -> None:
    if value is None or isinstance(value, (bool, str, int)):
        return
    if isinstance(value, float):
        if not math.isfinite(value):
            raise DomainPrivacyPolicyContractError(
                f"{field_name} must not contain non-finite floats",
                field=field_name,
            )
        return
    if isinstance(value, Mapping):
        for key, nested in value.items():
            if not isinstance(key, str) or isinstance(key, bool):
                raise DomainPrivacyPolicyContractError(
                    f"{field_name} keys must be strings", field=field_name
                )
            _require_json_value(nested, field_name)
        return
    if isinstance(value, (list, tuple)):
        for nested in value:
            _require_json_value(nested, field_name)
        return
    raise DomainPrivacyPolicyContractError(
        f"{field_name} must be JSON-safe, got {type(value).__name__}",
        field=field_name,
    )


def _freeze_json(value: Any) -> Any:
    if isinstance(value, Mapping):
        return MappingProxyType({key: _freeze_json(val) for key, val in value.items()})
    if isinstance(value, (list, tuple)):
        return tuple(_freeze_json(val) for val in value)
    return value


def _thaw_json(value: Any) -> Any:
    if isinstance(value, (MappingProxyType, Mapping)):
        return {key: _thaw_json(val) for key, val in value.items()}
    if isinstance(value, tuple):
        return [_thaw_json(val) for val in value]
    return value


def _reject_sensitive_metadata(value: Any, field_name: str) -> None:
    """Reject credential/secret-like metadata keys at every depth.

    Mirrors the canonical Domain sensitive-key predicate owned by
    ``cmm.domains.registry_contracts`` locally (as ``knowledge_package_contracts``
    does for the reserved authority-key boundary) so this contract module stays
    free of the ``contracts`` import cycle.
    """
    if isinstance(value, Mapping):
        for key in value:
            lower = key.lower().replace("-", "_").replace(" ", "_")
            if lower in _SENSITIVE_EXACT_WORDS or any(
                part in _SENSITIVE_KEY_PARTS for part in lower.split("_")
            ):
                raise DomainPrivacyPolicyContractError(
                    f"{field_name} contains sensitive key: {key!r}",
                    field=field_name,
                    details={"key": key},
                )
        for nested in value.values():
            _reject_sensitive_metadata(nested, field_name)
    elif isinstance(value, (list, tuple)):
        for nested in value:
            _reject_sensitive_metadata(nested, field_name)


def _require_metadata(value: Any, field_name: str) -> MappingProxyType[str, Any]:
    if not isinstance(value, Mapping):
        raise DomainPrivacyPolicyContractError(
            f"{field_name} must be a mapping", field=field_name
        )
    _require_json_value(value, field_name)
    _reject_sensitive_metadata(value, field_name)
    return _freeze_json(value)


def _validate_declarative_privacy_mapping(value: Any) -> None:
    """Fail closed on a nested Domain-declarative ``default_privacy`` payload.

    Rejects unknown serialized keys and credential/secret-like nested
    ``metadata`` before the tolerant canonical ``PrivacyMetadata.from_mapping``
    parser sees them. Secret values are never included in the raised error.
    """
    if not isinstance(value, Mapping):
        raise DomainPrivacyPolicySerializationError(
            "default_privacy must be a mapping", field="default_privacy"
        )
    unknown = set(value) - _PRIVACY_METADATA_FIELDS
    if unknown:
        raise DomainPrivacyPolicySerializationError(
            "default_privacy got unknown fields",
            field="default_privacy",
            details={"unknown_fields": sorted(str(item) for item in unknown)},
        )
    try:
        _reject_sensitive_metadata(value.get("metadata"), "default_privacy.metadata")
    except DomainPrivacyPolicyContractError as exc:
        raise DomainPrivacyPolicySerializationError(
            exc.message, field=exc.field, details=dict(exc.details)
        ) from exc


# ── Serialization helpers ─────────────────────────────────────────────────────


def _reject_unknown_fields(data: Mapping[str, Any]) -> None:
    unknown = set(data.keys()) - _KNOWN
    if unknown:
        raise DomainPrivacyPolicySerializationError(
            f"DomainPrivacyPolicy.from_dict got unknown fields: {sorted(unknown)}",
            field="data",
            details={"unknown_fields": sorted(unknown)},
        )


def _require_payload_mapping(value: Any) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise DomainPrivacyPolicySerializationError(
            "DomainPrivacyPolicy.from_dict requires a mapping", field="data"
        )
    return value


def _coerce_domain_id(value: Any) -> DomainId:
    if isinstance(value, DomainId):
        return value
    if isinstance(value, Mapping):
        return DomainId.from_dict(dict(value))
    if isinstance(value, str):
        return DomainId.from_str(value)
    raise DomainPrivacyPolicySerializationError(
        "domain_id must be a DomainId or canonical 'domain:<slug>' value",
        field="domain_id",
    )


def _wrap_contract_error(exc: DomainPrivacyPolicyContractError) -> Any:
    if isinstance(exc, DomainPrivacyPolicySerializationError):
        return exc
    return DomainPrivacyPolicySerializationError(
        exc.message, field=exc.field, details=dict(exc.details)
    )


# ── DomainPrivacyPolicy ───────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class DomainPrivacyPolicy:
    """Immutable, versioned Domain privacy default declaration.

    ``default_privacy`` is the canonical Phase 8 payload; the policy adds only
    Domain identity, the additional remote-approval obligation, and descriptive
    audit metadata. It carries no cross-domain authority and no provider/model
    routing choice.
    """

    schema_version: str
    domain_id: DomainId
    default_privacy: PrivacyMetadata
    require_approval_for_remote: bool = False
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        schema_version = _require_non_empty_str(self.schema_version, "schema_version")
        if schema_version != DOMAIN_PRIVACY_POLICY_SCHEMA_VERSION:
            raise DomainPrivacyPolicyContractError(
                f"Unsupported DomainPrivacyPolicy schema_version: {schema_version!r}",
                field="schema_version",
                details={"schema_version": schema_version},
            )
        object.__setattr__(self, "schema_version", schema_version)
        object.__setattr__(
            self, "domain_id", _require_domain_id(self.domain_id, "domain_id")
        )
        object.__setattr__(
            self,
            "default_privacy",
            _require_privacy_metadata(self.default_privacy, "default_privacy"),
        )
        _reject_sensitive_metadata(
            self.default_privacy.metadata, "default_privacy.metadata"
        )
        object.__setattr__(
            self,
            "require_approval_for_remote",
            _require_strict_bool(
                self.require_approval_for_remote, "require_approval_for_remote"
            ),
        )
        object.__setattr__(
            self, "metadata", _require_metadata(self.metadata, "metadata")
        )

    def to_dict(self) -> dict[str, Any]:
        """Serialize deterministically."""
        return {
            "schema_version": self.schema_version,
            "domain_id": str(self.domain_id),
            "default_privacy": self.default_privacy.to_dict(),
            "require_approval_for_remote": self.require_approval_for_remote,
            "metadata": _thaw_json(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: Any) -> DomainPrivacyPolicy:
        """Deserialize strictly, failing closed on malformed payloads."""
        mapping = _require_payload_mapping(data)
        _reject_unknown_fields(mapping)
        for name in ("schema_version", "domain_id", "default_privacy"):
            if name not in mapping:
                raise DomainPrivacyPolicySerializationError(
                    f"DomainPrivacyPolicy.from_dict missing required field {name!r}",
                    field=name,
                )
        try:
            default_privacy_payload = mapping["default_privacy"]
            _validate_declarative_privacy_mapping(default_privacy_payload)
            return cls(
                schema_version=mapping["schema_version"],
                domain_id=_coerce_domain_id(mapping["domain_id"]),
                default_privacy=PrivacyMetadata.from_mapping(default_privacy_payload),
                require_approval_for_remote=mapping.get(
                    "require_approval_for_remote", False
                ),
                metadata=mapping.get("metadata", {}),
            )
        except DomainPrivacyPolicyContractError as exc:
            raise _wrap_contract_error(exc) from exc
        except (TypeError, ValueError) as exc:
            raise DomainPrivacyPolicySerializationError(
                f"invalid DomainPrivacyPolicy payload: {exc}", field="data"
            ) from exc


# ── Pure projection into canonical PrivacyMetadata ────────────────────────────


def project_domain_privacy_metadata(
    policy: DomainPrivacyPolicy,
    *,
    processing_location: ProcessingLocation,
) -> PrivacyMetadata:
    """Project a Domain declaration into canonical ``PrivacyMetadata``.

    Pure and deterministic: returns ``policy.default_privacy`` unchanged for
    local processing, and adds only the canonical ``requires_approval=True``
    obligation when the Domain requires approval for a remote attempt. It never
    resolves effective privacy, never evaluates an operation and never widens a
    restriction.
    """
    if not isinstance(policy, DomainPrivacyPolicy):
        raise DomainPrivacyPolicyContractError(
            f"policy must be a DomainPrivacyPolicy, got {type(policy).__name__}",
            field="policy",
        )
    if not isinstance(processing_location, ProcessingLocation):
        try:
            processing_location = ProcessingLocation(processing_location)
        except (TypeError, ValueError) as exc:
            raise DomainPrivacyPolicyContractError(
                "processing_location must be a canonical ProcessingLocation",
                field="processing_location",
            ) from exc

    default = policy.default_privacy
    if (
        processing_location is ProcessingLocation.REMOTE
        and policy.require_approval_for_remote
        and not default.requires_approval
    ):
        return replace(default, requires_approval=True)
    return default
