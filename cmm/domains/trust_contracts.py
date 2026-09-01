"""Phase 10.38 — Domain Trust contracts.

Immutable, JSON-safe, strict contracts describing the explicit Domain Pack
trust/authority boundary:

- ``DomainTrustLevel`` lives in :mod:`cmm.domains.enums`.
- ``DomainTrustPolicy`` is the caller/configuration-supplied explicit trust
  declaration.
- ``DomainTrustDecision`` is a pure, immutable *evidence* result from trust
  evaluation. It is **not** an authorization token: ``activation_allowed``
  never grants runtime permissions, and ``denied_capabilities`` contains
  canonical ``PermissionCapability.value`` strings only.

Trust may only restrict or require explicit review. It never grants.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from cmm.agent_runtime.domain_permission_contracts import PermissionCapability
from cmm.domains.contracts import _reject_unknown_fields
from cmm.domains.enums import DomainTrustLevel
from cmm.domains.errors import (
    DomainContractValidationError,
    DomainSerializationError,
)
from cmm.domains.registry_contracts import (
    _reject_sensitive_keys,
    _validate_json_safe_metadata,
)

# Stable closed set of trust reason codes. No raw prompt content, manifest
# content, secret material, signature material, or arbitrary text may ever
# appear in a reason code.
_TRUST_REASON_CODES: frozenset[str] = frozenset(
    {
        "trust.blocked",
        "trust.source_not_authorized",
        "trust.validation_failed",
        "trust.signature_required",
        "trust.manual_enable_required",
        "trust.code_execution_denied",
        "trust.external_access_denied",
        "trust.memory_write_denied",
        "trust.sensitive_resource_denied",
        "trust.destructive_operation_denied",
    }
)

_ALLOW_BOOL_FIELDS = (
    "allow_code_execution",
    "allow_external_access",
    "allow_memory_write",
    "allow_sensitive_resources",
    "allow_destructive_operations",
    "require_manual_enable",
    "require_signature",
)

_POLICY_KNOWN = frozenset(
    {
        "domain_id",
        "trust_level",
        "authorized_source_ids",
        "allow_code_execution",
        "allow_external_access",
        "allow_memory_write",
        "allow_sensitive_resources",
        "allow_destructive_operations",
        "require_manual_enable",
        "require_signature",
        "metadata",
    }
)

_DECISION_KNOWN = frozenset(
    {
        "domain_id",
        "candidate_id",
        "source_id",
        "trust_level",
        "activation_allowed",
        "manual_enable_required",
        "denied_capabilities",
        "reason_codes",
        "metadata",
    }
)


def _coerce_trust_level(value: Any, field_name: str) -> DomainTrustLevel:
    if isinstance(value, DomainTrustLevel):
        return value
    if isinstance(value, str):
        try:
            return DomainTrustLevel(value)
        except ValueError as exc:
            raise DomainContractValidationError(
                f"Invalid DomainTrustLevel for {field_name}: {value!r}",
                field=field_name,
            ) from exc
    raise DomainContractValidationError(
        f"{field_name} must be a DomainTrustLevel or string, "
        f"got {type(value).__name__}",
        field=field_name,
    )


def _validate_non_empty_str(value: Any, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise DomainContractValidationError(
            f"{field_name} must be a non-empty string", field=field_name
        )
    return value.strip()


def _validate_source_ids(value: Any, field_name: str) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        raise DomainContractValidationError(
            f"{field_name} must be a sequence of strings, not a string",
            field=field_name,
        )
    if not isinstance(value, (list, tuple)):
        raise DomainContractValidationError(
            f"{field_name} must be a list or tuple of strings", field=field_name
        )
    result: list[str] = []
    for i, item in enumerate(value):
        if not isinstance(item, str) or not item.strip():
            raise DomainContractValidationError(
                f"{field_name}[{i}] must be a non-empty string",
                field=field_name,
                details={"index": i},
            )
        result.append(item.strip())
    if len(result) != len(set(result)):
        raise DomainContractValidationError(
            f"{field_name} must not contain duplicates", field=field_name
        )
    # Deterministic ordering regardless of caller-supplied order.
    return tuple(sorted(result))


def _validate_strict_bool(value: Any, field_name: str) -> bool:
    if not isinstance(value, bool):
        raise DomainContractValidationError(
            f"{field_name} must be a boolean (True or False), "
            f"got {type(value).__name__}: {value!r}",
            field=field_name,
        )
    return value


def _coerce_capability_values(value: Any, field_name: str) -> tuple[str, ...]:
    """Validate a sequence of canonical ``PermissionCapability`` values."""
    if value is None:
        return ()
    if isinstance(value, (str, bytes)):
        raise DomainContractValidationError(
            f"{field_name} must be a sequence of capability strings, not a string",
            field=field_name,
        )
    if not isinstance(value, (list, tuple)):
        raise DomainContractValidationError(
            f"{field_name} must be a list or tuple of capability strings",
            field=field_name,
        )
    result: list[str] = []
    for i, item in enumerate(value):
        if isinstance(item, PermissionCapability):
            result.append(item.value)
            continue
        if not isinstance(item, str) or not item.strip():
            raise DomainContractValidationError(
                f"{field_name}[{i}] must be a non-empty capability string",
                field=field_name,
                details={"index": i},
            )
        try:
            result.append(PermissionCapability(item.strip()).value)
        except ValueError as exc:
            raise DomainContractValidationError(
                f"{field_name}[{i}] is not a canonical PermissionCapability value: "
                f"{item!r}",
                field=field_name,
                details={"index": i, "value": item.strip()},
            ) from exc
    if len(result) != len(set(result)):
        raise DomainContractValidationError(
            f"{field_name} must not contain duplicates", field=field_name
        )
    return tuple(sorted(result))


def _validate_reason_codes(value: Any, field_name: str) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, (str, bytes)):
        raise DomainContractValidationError(
            f"{field_name} must be a sequence of reason codes, not a string",
            field=field_name,
        )
    if not isinstance(value, (list, tuple)):
        raise DomainContractValidationError(
            f"{field_name} must be a list or tuple of reason codes",
            field=field_name,
        )
    result: list[str] = []
    for i, item in enumerate(value):
        if not isinstance(item, str) or not item.strip():
            raise DomainContractValidationError(
                f"{field_name}[{i}] must be a non-empty string",
                field=field_name,
                details={"index": i},
            )
        code = item.strip()
        if code not in _TRUST_REASON_CODES:
            raise DomainContractValidationError(
                f"{field_name}[{i}] is not a stable trust reason code: {code!r}",
                field=field_name,
                details={"index": i, "value": code},
            )
        result.append(code)
    if len(result) != len(set(result)):
        raise DomainContractValidationError(
            f"{field_name} must not contain duplicates", field=field_name
        )
    # Deterministic reason order for stable evidence.
    return tuple(sorted(result))


@dataclass(frozen=True, slots=True)
class DomainTrustPolicy:
    """Immutable explicit trust declaration for one Domain.

    Supplied by the caller/configuration boundary that owns runtime wiring.
    Safe defaults are restrictive: no capability is allowed, manual
    enablement is required, and signatures are not required by default.
    """

    domain_id: str
    trust_level: DomainTrustLevel
    authorized_source_ids: tuple[str, ...] = ()
    allow_code_execution: bool = False
    allow_external_access: bool = False
    allow_memory_write: bool = False
    allow_sensitive_resources: bool = False
    allow_destructive_operations: bool = False
    require_manual_enable: bool = True
    require_signature: bool = False
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "domain_id", _validate_non_empty_str(self.domain_id, "domain_id")
        )
        object.__setattr__(
            self, "trust_level", _coerce_trust_level(self.trust_level, "trust_level")
        )
        object.__setattr__(
            self,
            "authorized_source_ids",
            _validate_source_ids(self.authorized_source_ids, "authorized_source_ids"),
        )
        for name in _ALLOW_BOOL_FIELDS:
            object.__setattr__(
                self, name, _validate_strict_bool(getattr(self, name), name)
            )
        meta = _validate_json_safe_metadata(self.metadata, "metadata")
        _reject_sensitive_keys(meta, "metadata")
        object.__setattr__(self, "metadata", meta)

    def to_dict(self) -> dict[str, Any]:
        return {
            "domain_id": self.domain_id,
            "trust_level": self.trust_level.value,
            "authorized_source_ids": list(self.authorized_source_ids),
            "allow_code_execution": self.allow_code_execution,
            "allow_external_access": self.allow_external_access,
            "allow_memory_write": self.allow_memory_write,
            "allow_sensitive_resources": self.allow_sensitive_resources,
            "allow_destructive_operations": self.allow_destructive_operations,
            "require_manual_enable": self.require_manual_enable,
            "require_signature": self.require_signature,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> DomainTrustPolicy:
        if not isinstance(data, Mapping):
            raise DomainSerializationError(
                "DomainTrustPolicy.from_dict requires a mapping", field="data"
            )
        _reject_unknown_fields(data, _POLICY_KNOWN, "DomainTrustPolicy")
        required = {"domain_id", "trust_level"}
        missing = required - set(data.keys())
        if missing:
            raise DomainSerializationError(
                f"DomainTrustPolicy.from_dict missing required fields: "
                f"{sorted(missing)}",
                field="data",
            )
        try:
            return cls(
                domain_id=data["domain_id"],
                trust_level=data["trust_level"],
                authorized_source_ids=data.get("authorized_source_ids"),
                allow_code_execution=data.get("allow_code_execution", False),
                allow_external_access=data.get("allow_external_access", False),
                allow_memory_write=data.get("allow_memory_write", False),
                allow_sensitive_resources=data.get("allow_sensitive_resources", False),
                allow_destructive_operations=data.get(
                    "allow_destructive_operations", False
                ),
                require_manual_enable=data.get("require_manual_enable", True),
                require_signature=data.get("require_signature", False),
                metadata=data.get("metadata", {}),
            )
        except DomainContractValidationError as exc:
            raise DomainSerializationError(
                exc.message, field=exc.field, details=dict(exc.details)
            ) from exc


@dataclass(frozen=True, slots=True)
class DomainTrustDecision:
    """Immutable evidence result from the Domain trust boundary.

    ``activation_allowed`` is evidence that the explicit trust boundary
    permits activation; it never authorizes runtime operations. Denied
    capabilities are canonical ``PermissionCapability`` values only.

    The decision carries no raw prompt content, manifest content, secret
    material, signature material, or arbitrary exception text.
    """

    domain_id: str
    candidate_id: str
    source_id: str
    trust_level: DomainTrustLevel
    activation_allowed: bool
    manual_enable_required: bool
    denied_capabilities: tuple[str, ...] = ()
    reason_codes: tuple[str, ...] = ()
    metadata: Mapping[str, Any] = field(default_factory=dict)

    _BLOCKING_REASON_CODES: frozenset[str] = frozenset(
        {
            "trust.blocked",
            "trust.source_not_authorized",
            "trust.validation_failed",
            "trust.signature_required",
            "trust.manual_enable_required",
        }
    )

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "domain_id", _validate_non_empty_str(self.domain_id, "domain_id")
        )
        object.__setattr__(
            self,
            "candidate_id",
            _validate_non_empty_str(self.candidate_id, "candidate_id"),
        )
        object.__setattr__(
            self, "source_id", _validate_non_empty_str(self.source_id, "source_id")
        )
        object.__setattr__(
            self, "trust_level", _coerce_trust_level(self.trust_level, "trust_level")
        )
        object.__setattr__(
            self,
            "activation_allowed",
            _validate_strict_bool(self.activation_allowed, "activation_allowed"),
        )
        object.__setattr__(
            self,
            "manual_enable_required",
            _validate_strict_bool(
                self.manual_enable_required, "manual_enable_required"
            ),
        )
        object.__setattr__(
            self,
            "denied_capabilities",
            _coerce_capability_values(self.denied_capabilities, "denied_capabilities"),
        )
        object.__setattr__(
            self,
            "reason_codes",
            _validate_reason_codes(self.reason_codes, "reason_codes"),
        )
        meta = _validate_json_safe_metadata(self.metadata, "metadata")
        _reject_sensitive_keys(meta, "metadata")
        object.__setattr__(self, "metadata", meta)

        if self.activation_allowed and (
            set(self.reason_codes) & self._BLOCKING_REASON_CODES
        ):
            raise DomainContractValidationError(
                "DomainTrustDecision cannot claim activation_allowed=True while "
                "carrying an activation-blocking reason code",
                field="activation_allowed",
                details={"reason_codes": list(self.reason_codes)},
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "domain_id": self.domain_id,
            "candidate_id": self.candidate_id,
            "source_id": self.source_id,
            "trust_level": self.trust_level.value,
            "activation_allowed": self.activation_allowed,
            "manual_enable_required": self.manual_enable_required,
            "denied_capabilities": list(self.denied_capabilities),
            "reason_codes": list(self.reason_codes),
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> DomainTrustDecision:
        if not isinstance(data, Mapping):
            raise DomainSerializationError(
                "DomainTrustDecision.from_dict requires a mapping", field="data"
            )
        _reject_unknown_fields(data, _DECISION_KNOWN, "DomainTrustDecision")
        required = {
            "domain_id",
            "candidate_id",
            "source_id",
            "trust_level",
            "activation_allowed",
            "manual_enable_required",
        }
        missing = required - set(data.keys())
        if missing:
            raise DomainSerializationError(
                f"DomainTrustDecision.from_dict missing required fields: "
                f"{sorted(missing)}",
                field="data",
            )
        try:
            return cls(
                domain_id=data["domain_id"],
                candidate_id=data["candidate_id"],
                source_id=data["source_id"],
                trust_level=data["trust_level"],
                activation_allowed=data["activation_allowed"],
                manual_enable_required=data["manual_enable_required"],
                denied_capabilities=data.get("denied_capabilities"),
                reason_codes=data.get("reason_codes"),
                metadata=data.get("metadata", {}),
            )
        except DomainContractValidationError as exc:
            raise DomainSerializationError(
                exc.message, field=exc.field, details=dict(exc.details)
            ) from exc


__all__ = ["DomainTrustDecision", "DomainTrustPolicy"]
