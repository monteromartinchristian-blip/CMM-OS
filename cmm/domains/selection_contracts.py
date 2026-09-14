"""Phase 10.31 — Domain Selection Policy contracts.

Immutable, deterministic and JSON-serializable policy contracts used by the
shared Domain Resolver.  This module contains configuration contracts only;
it performs no resolution, registry access, persistence, or operation
execution.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any

from cmm.domains.contracts import (
    _reject_unknown_fields,
    _validate_non_empty_str,
    _validate_strict_bool,
)
from cmm.domains.errors import DomainContractValidationError
from cmm.domains.identifiers import DomainId
from cmm.domains.resolver_contracts import (
    _coerce_domain_id,
    _deep_unfreeze_value,
    _reject_credential_keys_deep,
    _validate_confidence,
    _validate_json_safe_metadata,
)

_SELECTION_POLICY_KNOWN = frozenset(
    {
        "name",
        "explicit_domain_priority",
        "session_domain_priority",
        "goal_domain_priority",
        "allow_multi_domain",
        "maximum_supporting_domains",
        "minimum_primary_confidence",
        "minimum_supporting_confidence",
        "fallback_domain",
        "ambiguity_strategy",
        "metadata",
    }
)

_SUPPORTED_AMBIGUITY_STRATEGIES = frozenset(
    {
        "clarify_or_fallback",
    }
)


@dataclass(frozen=True, slots=True)
class DomainSelectionPolicy:
    """Immutable policy controlling domain selection semantics."""

    name: str = "default"
    explicit_domain_priority: bool = True
    session_domain_priority: bool = True
    goal_domain_priority: bool = True
    allow_multi_domain: bool = True
    maximum_supporting_domains: int = 3
    minimum_primary_confidence: float = 0.70
    minimum_supporting_confidence: float = 0.55
    fallback_domain: DomainId = field(
        default_factory=lambda: DomainId.from_str("domain:general")
    )
    ambiguity_strategy: str = "clarify_or_fallback"
    metadata: MappingProxyType[str, Any] = field(
        default_factory=lambda: MappingProxyType({})
    )

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "name",
            _validate_non_empty_str(self.name, "name"),
        )

        for field_name in (
            "explicit_domain_priority",
            "session_domain_priority",
            "goal_domain_priority",
            "allow_multi_domain",
        ):
            object.__setattr__(
                self,
                field_name,
                _validate_strict_bool(getattr(self, field_name), field_name),
            )

        if not isinstance(self.maximum_supporting_domains, int) or isinstance(
            self.maximum_supporting_domains, bool
        ):
            raise DomainContractValidationError(
                "maximum_supporting_domains must be an integer",
                field="maximum_supporting_domains",
            )

        if self.maximum_supporting_domains < 0:
            raise DomainContractValidationError(
                "maximum_supporting_domains must be non-negative",
                field="maximum_supporting_domains",
            )

        object.__setattr__(
            self,
            "minimum_primary_confidence",
            _validate_confidence(
                self.minimum_primary_confidence,
                "minimum_primary_confidence",
            ),
        )
        object.__setattr__(
            self,
            "minimum_supporting_confidence",
            _validate_confidence(
                self.minimum_supporting_confidence,
                "minimum_supporting_confidence",
            ),
        )

        object.__setattr__(
            self,
            "fallback_domain",
            _coerce_domain_id(self.fallback_domain, "fallback_domain"),
        )

        ambiguity_strategy = _validate_non_empty_str(
            self.ambiguity_strategy,
            "ambiguity_strategy",
        )
        if ambiguity_strategy not in _SUPPORTED_AMBIGUITY_STRATEGIES:
            raise DomainContractValidationError(
                "Unsupported ambiguity strategy",
                field="ambiguity_strategy",
                details={
                    "value": ambiguity_strategy,
                    "supported": sorted(_SUPPORTED_AMBIGUITY_STRATEGIES),
                },
            )
        object.__setattr__(
            self,
            "ambiguity_strategy",
            ambiguity_strategy,
        )

        frozen_metadata = _validate_json_safe_metadata(
            self.metadata,
            "metadata",
        )
        _reject_credential_keys_deep(frozen_metadata, "metadata")
        object.__setattr__(self, "metadata", frozen_metadata)

    def to_dict(self) -> dict[str, Any]:
        """Serialize the policy to a JSON-safe dictionary."""
        return {
            "name": self.name,
            "explicit_domain_priority": self.explicit_domain_priority,
            "session_domain_priority": self.session_domain_priority,
            "goal_domain_priority": self.goal_domain_priority,
            "allow_multi_domain": self.allow_multi_domain,
            "maximum_supporting_domains": self.maximum_supporting_domains,
            "minimum_primary_confidence": self.minimum_primary_confidence,
            "minimum_supporting_confidence": self.minimum_supporting_confidence,
            "fallback_domain": str(self.fallback_domain),
            "ambiguity_strategy": self.ambiguity_strategy,
            "metadata": _deep_unfreeze_value(self.metadata),
        }

    @classmethod
    def from_dict(
        cls,
        data: Mapping[str, Any],
    ) -> DomainSelectionPolicy:
        """Deserialize a policy from a strict mapping."""
        if not isinstance(data, Mapping):
            raise DomainContractValidationError(
                "DomainSelectionPolicy.from_dict requires a mapping",
                field="data",
            )

        _reject_unknown_fields(
            data,
            _SELECTION_POLICY_KNOWN,
            "DomainSelectionPolicy",
        )

        return cls(**{key: data[key] for key in _SELECTION_POLICY_KNOWN if key in data})


_SELECTION_TRANSITION_KNOWN = frozenset(
    {
        "previous_resolution_id",
        "new_resolution_id",
        "previous_primary_domain",
        "new_primary_domain",
        "previous_supporting_domains",
        "new_supporting_domains",
        "primary_changed",
        "supporting_changed",
        "reason_codes",
        "requires_recomposition",
        "requires_session_update",
        "metadata",
    }
)


def _coerce_optional_domain_id(
    value: DomainId | str | None,
    field_name: str,
) -> DomainId | None:
    if value is None:
        return None
    return _coerce_domain_id(value, field_name)


def _coerce_domain_id_tuple(
    value: tuple[DomainId | str, ...] | list[DomainId | str],
    field_name: str,
) -> tuple[DomainId, ...]:
    if not isinstance(value, (tuple, list)):
        raise DomainContractValidationError(
            f"{field_name} must be a tuple or list",
            field=field_name,
        )

    result = tuple(
        _coerce_domain_id(item, f"{field_name}[{index}]")
        for index, item in enumerate(value)
    )

    slugs = [str(item) for item in result]
    if len(slugs) != len(set(slugs)):
        raise DomainContractValidationError(
            f"{field_name} must not contain duplicate domains",
            field=field_name,
        )

    return result


def _coerce_reason_codes(
    value: tuple[str, ...] | list[str],
) -> tuple[str, ...]:
    if not isinstance(value, (tuple, list)):
        raise DomainContractValidationError(
            "reason_codes must be a tuple or list",
            field="reason_codes",
        )

    result = tuple(
        _validate_non_empty_str(item, f"reason_codes[{index}]")
        for index, item in enumerate(value)
    )

    if len(result) != len(set(result)):
        raise DomainContractValidationError(
            "reason_codes must not contain duplicates",
            field="reason_codes",
        )

    return result


@dataclass(frozen=True, slots=True)
class DomainSelectionTransition:
    """Pure, auditable comparison between two domain resolutions."""

    previous_resolution_id: str
    new_resolution_id: str
    previous_primary_domain: DomainId | None = None
    new_primary_domain: DomainId | None = None
    previous_supporting_domains: tuple[DomainId, ...] = ()
    new_supporting_domains: tuple[DomainId, ...] = ()
    primary_changed: bool = False
    supporting_changed: bool = False
    reason_codes: tuple[str, ...] = ()
    requires_recomposition: bool = False
    requires_session_update: bool = False
    metadata: MappingProxyType[str, Any] = field(
        default_factory=lambda: MappingProxyType({})
    )

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "previous_resolution_id",
            _validate_non_empty_str(
                self.previous_resolution_id,
                "previous_resolution_id",
            ),
        )
        object.__setattr__(
            self,
            "new_resolution_id",
            _validate_non_empty_str(
                self.new_resolution_id,
                "new_resolution_id",
            ),
        )
        object.__setattr__(
            self,
            "previous_primary_domain",
            _coerce_optional_domain_id(
                self.previous_primary_domain,
                "previous_primary_domain",
            ),
        )
        object.__setattr__(
            self,
            "new_primary_domain",
            _coerce_optional_domain_id(
                self.new_primary_domain,
                "new_primary_domain",
            ),
        )
        object.__setattr__(
            self,
            "previous_supporting_domains",
            _coerce_domain_id_tuple(
                self.previous_supporting_domains,
                "previous_supporting_domains",
            ),
        )
        object.__setattr__(
            self,
            "new_supporting_domains",
            _coerce_domain_id_tuple(
                self.new_supporting_domains,
                "new_supporting_domains",
            ),
        )

        for field_name in (
            "primary_changed",
            "supporting_changed",
            "requires_recomposition",
            "requires_session_update",
        ):
            object.__setattr__(
                self,
                field_name,
                _validate_strict_bool(getattr(self, field_name), field_name),
            )

        expected_primary_changed = (
            self.previous_primary_domain != self.new_primary_domain
        )
        if self.primary_changed != expected_primary_changed:
            raise DomainContractValidationError(
                "primary_changed must match the primary-domain identity change",
                field="primary_changed",
            )
        expected_supporting_changed = (
            self.previous_supporting_domains != self.new_supporting_domains
        )
        if self.supporting_changed != expected_supporting_changed:
            raise DomainContractValidationError(
                "supporting_changed must match the supporting-domain composition change",
                field="supporting_changed",
            )
        expected_selection_changed = (
            expected_primary_changed or expected_supporting_changed
        )
        if self.requires_recomposition != expected_selection_changed:
            raise DomainContractValidationError(
                "requires_recomposition must match the selection change state",
                field="requires_recomposition",
            )
        if self.requires_session_update != expected_selection_changed:
            raise DomainContractValidationError(
                "requires_session_update must match the selection change state",
                field="requires_session_update",
            )

        object.__setattr__(
            self,
            "reason_codes",
            _coerce_reason_codes(self.reason_codes),
        )

        frozen_metadata = _validate_json_safe_metadata(
            self.metadata,
            "metadata",
        )
        _reject_credential_keys_deep(frozen_metadata, "metadata")
        object.__setattr__(self, "metadata", frozen_metadata)

    def to_dict(self) -> dict[str, Any]:
        """Serialize the transition to a JSON-safe dictionary."""
        return {
            "previous_resolution_id": self.previous_resolution_id,
            "new_resolution_id": self.new_resolution_id,
            "previous_primary_domain": (
                str(self.previous_primary_domain)
                if self.previous_primary_domain is not None
                else None
            ),
            "new_primary_domain": (
                str(self.new_primary_domain)
                if self.new_primary_domain is not None
                else None
            ),
            "previous_supporting_domains": [
                str(domain_id) for domain_id in self.previous_supporting_domains
            ],
            "new_supporting_domains": [
                str(domain_id) for domain_id in self.new_supporting_domains
            ],
            "primary_changed": self.primary_changed,
            "supporting_changed": self.supporting_changed,
            "reason_codes": list(self.reason_codes),
            "requires_recomposition": self.requires_recomposition,
            "requires_session_update": self.requires_session_update,
            "metadata": _deep_unfreeze_value(self.metadata),
        }

    @classmethod
    def from_dict(
        cls,
        data: Mapping[str, Any],
    ) -> DomainSelectionTransition:
        """Deserialize a transition from a strict mapping."""
        if not isinstance(data, Mapping):
            raise DomainContractValidationError(
                "DomainSelectionTransition.from_dict requires a mapping",
                field="data",
            )

        _reject_unknown_fields(
            data,
            _SELECTION_TRANSITION_KNOWN,
            "DomainSelectionTransition",
        )

        required = {
            "previous_resolution_id",
            "new_resolution_id",
        }
        missing = required - set(data)
        if missing:
            raise DomainContractValidationError(
                "DomainSelectionTransition.from_dict missing required fields",
                field="data",
                details={"missing_fields": sorted(missing)},
            )

        return cls(
            **{key: data[key] for key in _SELECTION_TRANSITION_KNOWN if key in data}
        )


__all__ = [
    "DomainSelectionPolicy",
    "DomainSelectionTransition",
]
