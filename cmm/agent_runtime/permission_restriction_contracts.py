"""Neutral declarative restrictions for external effects and verification."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Self

from .agent_security_enums import SensitivityLevel
from .errors import InvalidPermissionRestrictionError


class ExternalSourceClass(str, Enum):
    GENERAL_WEB = "general_web"
    TRUSTED_SECONDARY = "trusted_secondary"
    PRIMARY_SOURCES = "primary_sources"
    OFFICIAL_ONLY = "official_only"


class ProviderLocation(str, Enum):
    LOCAL = "local"
    REMOTE = "remote"


class ExportContentKind(str, Enum):
    SUMMARY = "summary"
    ORIGINAL_EVIDENCE = "original_evidence"


class PostVerificationKind(str, Enum):
    DISPATCH_CONFIRMATION = "dispatch_confirmation"
    REFETCH = "refetch"
    COMPARISON = "comparison"
    MANUAL_VERIFICATION = "manual_verification"
    RESULT_EVIDENCE = "result_evidence"


def _enum(value: Any, kind: type[Enum], field: str) -> Any:
    try:
        return value if isinstance(value, kind) else kind(value)
    except (TypeError, ValueError) as exc:
        raise InvalidPermissionRestrictionError(f"invalid {field}") from exc


def _text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise InvalidPermissionRestrictionError(f"{field} must be a non-empty string")
    return value.strip()


def _optional_text(value: Any, field: str) -> str | None:
    return None if value is None else _text(value, field)


def _strings(value: Any, field: str) -> tuple[str, ...]:
    if value is None or isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        raise InvalidPermissionRestrictionError(f"{field} must be a sequence")
    result = tuple(_text(item, field) for item in value)
    if len(result) != len(set(result)):
        raise InvalidPermissionRestrictionError(f"{field} must not contain duplicates")
    return result


def _boolean(value: Any, field: str) -> bool:
    if not isinstance(value, bool):
        raise InvalidPermissionRestrictionError(f"{field} must be a boolean")
    return value


def _sensitivity(value: Any, field: str) -> SensitivityLevel:
    return _enum(value, SensitivityLevel, field)


def _optional_datetime(value: Any, field: str) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, str):
        try:
            value = datetime.fromisoformat(value)
        except ValueError as exc:
            raise InvalidPermissionRestrictionError(f"invalid {field}") from exc
    if not isinstance(value, datetime) or value.tzinfo is None:
        raise InvalidPermissionRestrictionError(f"{field} must be timezone-aware")
    return value


class _SerializableRestriction:
    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for name in self.__dataclass_fields__:  # type: ignore[attr-defined]
            value = getattr(self, name)
            if isinstance(value, Enum):
                result[name] = value.value
            elif isinstance(value, datetime):
                result[name] = value.isoformat()
            elif isinstance(value, tuple):
                result[name] = [item.value if isinstance(item, Enum) else item for item in value]
            else:
                result[name] = value
        return result

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> Self:
        if not isinstance(data, Mapping):
            raise InvalidPermissionRestrictionError("serialized restriction must be a mapping")
        unknown = set(data) - set(cls.__dataclass_fields__)  # type: ignore[attr-defined]
        if unknown:
            raise InvalidPermissionRestrictionError(f"unknown fields: {sorted(unknown)}")
        try:
            return cls(**dict(data))
        except InvalidPermissionRestrictionError:
            raise
        except TypeError as exc:
            raise InvalidPermissionRestrictionError(
                f"invalid {cls.__name__} payload"
            ) from exc


@dataclass(frozen=True, slots=True)
class ExternalSourceRequirement(_SerializableRestriction):
    minimum_source_class: ExternalSourceClass
    allowed_domains: tuple[str, ...] = ()
    prohibited_domains: tuple[str, ...] = ()
    require_additional_verification: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "minimum_source_class", _enum(self.minimum_source_class, ExternalSourceClass, "minimum_source_class"))
        object.__setattr__(self, "allowed_domains", _strings(self.allowed_domains, "allowed_domains"))
        object.__setattr__(self, "prohibited_domains", _strings(self.prohibited_domains, "prohibited_domains"))
        if set(self.allowed_domains) & set(self.prohibited_domains):
            raise InvalidPermissionRestrictionError(
                "allowed_domains and prohibited_domains must not overlap"
            )
        object.__setattr__(self, "require_additional_verification", _boolean(self.require_additional_verification, "require_additional_verification"))


@dataclass(frozen=True, slots=True)
class ExternalSourceUse(_SerializableRestriction):
    source_class: ExternalSourceClass
    domain: str
    additional_verification: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "source_class", _enum(self.source_class, ExternalSourceClass, "source_class"))
        object.__setattr__(self, "domain", _text(self.domain, "domain").lower())
        object.__setattr__(self, "additional_verification", _boolean(self.additional_verification, "additional_verification"))


@dataclass(frozen=True, slots=True)
class ExternalProviderEgressPolicy(_SerializableRestriction):
    provider_id: str
    provider_location: ProviderLocation
    allowed_source_domains: tuple[str, ...]
    maximum_sensitivity: SensitivityLevel
    allowed_data_categories: tuple[str, ...]
    allowed_purposes: tuple[str, ...]
    allowed_resource_ids: tuple[str, ...] = ()
    allowed_claims: tuple[str, ...] = ()
    require_redaction: bool = False
    require_consent: bool = False
    require_approval: bool = False
    allow_retention: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "provider_id", _text(self.provider_id, "provider_id"))
        object.__setattr__(self, "provider_location", _enum(self.provider_location, ProviderLocation, "provider_location"))
        for name in ("allowed_source_domains", "allowed_data_categories", "allowed_purposes", "allowed_resource_ids", "allowed_claims"):
            object.__setattr__(self, name, _strings(getattr(self, name), name))
        object.__setattr__(self, "maximum_sensitivity", _sensitivity(self.maximum_sensitivity, "maximum_sensitivity"))
        for name in ("require_redaction", "require_consent", "require_approval", "allow_retention"):
            object.__setattr__(self, name, _boolean(getattr(self, name), name))


@dataclass(frozen=True, slots=True)
class ExternalProviderEgressRequest(_SerializableRestriction):
    provider_id: str
    provider_location: ProviderLocation
    source_domains: tuple[str, ...]
    sensitivity: SensitivityLevel
    data_categories: tuple[str, ...]
    purpose: str
    resource_ids: tuple[str, ...] = ()
    claims: tuple[str, ...] = ()
    redaction_applied: bool = False
    consent_reference: str | None = None
    retention_requested: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "provider_id", _text(self.provider_id, "provider_id"))
        object.__setattr__(self, "provider_location", _enum(self.provider_location, ProviderLocation, "provider_location"))
        for name in ("source_domains", "data_categories", "resource_ids", "claims"):
            object.__setattr__(self, name, _strings(getattr(self, name), name))
        object.__setattr__(self, "sensitivity", _sensitivity(self.sensitivity, "sensitivity"))
        object.__setattr__(self, "purpose", _text(self.purpose, "purpose"))
        object.__setattr__(self, "redaction_applied", _boolean(self.redaction_applied, "redaction_applied"))
        object.__setattr__(self, "consent_reference", _optional_text(self.consent_reference, "consent_reference"))
        object.__setattr__(self, "retention_requested", _boolean(self.retention_requested, "retention_requested"))


@dataclass(frozen=True, slots=True)
class ExportPolicy(_SerializableRestriction):
    allowed_recipients: tuple[str, ...]
    allowed_recipient_classes: tuple[str, ...]
    allowed_purposes: tuple[str, ...]
    allowed_formats: tuple[str, ...]
    allowed_data_categories: tuple[str, ...]
    allowed_identifiers: tuple[str, ...]
    prohibited_identifiers: tuple[str, ...]
    maximum_sensitivity: SensitivityLevel
    allow_original_evidence: bool = False
    require_redaction: bool = False
    require_tokenization: bool = False
    expires_at: datetime | None = None
    one_time: bool = True
    require_approval: bool = False

    def __post_init__(self) -> None:
        for name in ("allowed_recipients", "allowed_recipient_classes", "allowed_purposes", "allowed_formats", "allowed_data_categories", "allowed_identifiers", "prohibited_identifiers"):
            object.__setattr__(self, name, _strings(getattr(self, name), name))
        if set(self.allowed_identifiers) & set(self.prohibited_identifiers):
            raise InvalidPermissionRestrictionError(
                "allowed_identifiers and prohibited_identifiers must not overlap"
            )
        object.__setattr__(self, "maximum_sensitivity", _sensitivity(self.maximum_sensitivity, "maximum_sensitivity"))
        for name in ("allow_original_evidence", "require_redaction", "require_tokenization", "one_time", "require_approval"):
            object.__setattr__(self, name, _boolean(getattr(self, name), name))
        object.__setattr__(self, "expires_at", _optional_datetime(self.expires_at, "expires_at"))


@dataclass(frozen=True, slots=True)
class ExportRequest(_SerializableRestriction):
    recipient_id: str
    recipient_class: str
    purpose: str
    format: str
    data_categories: tuple[str, ...]
    identifiers: tuple[str, ...]
    content_kind: ExportContentKind
    sensitivity: SensitivityLevel
    redaction_applied: bool = False
    tokenization_applied: bool = False

    def __post_init__(self) -> None:
        for name in ("recipient_id", "recipient_class", "purpose", "format"):
            object.__setattr__(self, name, _text(getattr(self, name), name))
        for name in ("data_categories", "identifiers"):
            object.__setattr__(self, name, _strings(getattr(self, name), name))
        object.__setattr__(self, "content_kind", _enum(self.content_kind, ExportContentKind, "content_kind"))
        object.__setattr__(self, "sensitivity", _sensitivity(self.sensitivity, "sensitivity"))
        object.__setattr__(self, "redaction_applied", _boolean(self.redaction_applied, "redaction_applied"))
        object.__setattr__(self, "tokenization_applied", _boolean(self.tokenization_applied, "tokenization_applied"))


@dataclass(frozen=True, slots=True)
class PostVerificationRequirement(_SerializableRestriction):
    kinds: tuple[PostVerificationKind, ...]
    resource_ids: tuple[str, ...] = ()
    comparison_fields: tuple[str, ...] = ()
    evidence_kinds: tuple[str, ...] = ()
    manual_verifier: str | None = None

    def __post_init__(self) -> None:
        kinds = tuple(_enum(item, PostVerificationKind, "kinds") for item in self.kinds)
        if not kinds or len(kinds) != len(set(kinds)):
            raise InvalidPermissionRestrictionError("kinds must be non-empty and unique")
        object.__setattr__(self, "kinds", kinds)
        for name in ("resource_ids", "comparison_fields", "evidence_kinds"):
            object.__setattr__(self, name, _strings(getattr(self, name), name))
        object.__setattr__(self, "manual_verifier", _optional_text(self.manual_verifier, "manual_verifier"))
        has_manual_kind = PostVerificationKind.MANUAL_VERIFICATION in self.kinds
        if self.manual_verifier is not None and not has_manual_kind:
            raise InvalidPermissionRestrictionError(
                "manual_verifier requires manual verification"
            )


__all__ = [
    "ExportContentKind", "ExportPolicy", "ExportRequest",
    "ExternalProviderEgressPolicy", "ExternalProviderEgressRequest",
    "ExternalSourceClass", "ExternalSourceRequirement", "ExternalSourceUse",
    "PostVerificationKind", "PostVerificationRequirement", "ProviderLocation",
]
