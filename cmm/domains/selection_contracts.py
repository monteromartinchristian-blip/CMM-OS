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


__all__ = [
    "DomainSelectionPolicy",
]
