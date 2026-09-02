"""Strict contracts at the Domain Intelligence/Cognitive Layer boundary."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any

from cmm.cognitive.adapters import ResourceInput
from cmm.cognitive.knowledge import KnowledgeBundle
from cmm.cognitive.knowledge_packages import KnowledgePackage
from cmm.cognitive.reasoning_rule_contracts import ReasoningRuleContext
from cmm.cognitive.resources import Resource
from cmm.cognitive.validation import CognitiveValidationResult
from cmm.domains.composition_contracts import DomainComposition
from cmm.domains.contracts import _deep_freeze
from cmm.domains.enums import (
    DomainCompositionStatus,
    DomainResourceResolutionStatus,
)
from cmm.domains.errors import (
    DomainCognitiveIntegrationContractError,
    DomainContractValidationError,
)
from cmm.domains.presentation_contracts import DomainPresentationItemRef
from cmm.domains.profile_contracts import ResolvedDomainProfile
from cmm.domains.resource_contracts import (
    DomainResourceBinding,
    DomainResourceResolution,
)
from cmm.domains.rule_contracts import (
    DomainRuleExecutionPlan,
    DomainRuleExecutionResult,
)
from cmm.domains.trace_contracts import DomainTraceReferences


@dataclass(frozen=True, slots=True)
class DomainCognitiveResourceInput:
    """Accepted Domain resource lineage paired with its Cognitive source input."""

    resolution: DomainResourceResolution
    binding: DomainResourceBinding
    source: ResourceInput
    extractor_name: str | None = None

    def __post_init__(self) -> None:
        if type(self.resolution) is not DomainResourceResolution:
            raise DomainCognitiveIntegrationContractError(
                "resolution must be a DomainResourceResolution", field="resolution"
            )
        if type(self.binding) is not DomainResourceBinding:
            raise DomainCognitiveIntegrationContractError(
                "binding must be a DomainResourceBinding", field="binding"
            )
        if self.binding not in self.resolution.bindings:
            raise DomainCognitiveIntegrationContractError(
                "binding must occur in resolution.bindings", field="binding"
            )
        if self.resolution.status not in {
            DomainResourceResolutionStatus.RESOLVED,
            DomainResourceResolutionStatus.PARTIAL,
        }:
            raise DomainCognitiveIntegrationContractError(
                "resolution status must be RESOLVED or PARTIAL", field="resolution"
            )
        if type(self.source) is not ResourceInput:
            raise DomainCognitiveIntegrationContractError(
                "source must be a ResourceInput", field="source"
            )
        if self.source.id != self.binding.resource_id:
            raise DomainCognitiveIntegrationContractError(
                "source.id must match binding.resource_id", field="source.id"
            )
        if self.source.sensitivity != self.binding.sensitivity:
            raise DomainCognitiveIntegrationContractError(
                "source.sensitivity must match binding.sensitivity",
                field="source.sensitivity",
            )
        if self.extractor_name is not None:
            if (
                not isinstance(self.extractor_name, str)
                or not self.extractor_name.strip()
            ):
                raise DomainCognitiveIntegrationContractError(
                    "extractor_name must be None or a non-blank string",
                    field="extractor_name",
                )
            object.__setattr__(self, "extractor_name", self.extractor_name.strip())


def _non_blank(value: Any, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise DomainCognitiveIntegrationContractError(
            f"{field_name} must be a non-blank string", field=field_name
        )
    return value.strip()


def _optional_non_blank(value: Any, field_name: str) -> str | None:
    if value is None:
        return None
    return _non_blank(value, field_name)


def _tuple_of_instances(
    value: Any, expected_type: type, field_name: str
) -> tuple[Any, ...]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        raise DomainCognitiveIntegrationContractError(
            f"{field_name} must be a sequence", field=field_name
        )
    values = tuple(value)
    for index, item in enumerate(values):
        if type(item) is not expected_type:
            raise DomainCognitiveIntegrationContractError(
                f"{field_name}[{index}] must be a {expected_type.__name__}",
                field=field_name,
            )
    return values


def _unique_non_blank_strings(value: Any, field_name: str) -> tuple[str, ...]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        raise DomainCognitiveIntegrationContractError(
            f"{field_name} must be a sequence of strings", field=field_name
        )
    values = tuple(_non_blank(item, field_name) for item in value)
    if len(set(values)) != len(values):
        raise DomainCognitiveIntegrationContractError(
            f"{field_name} must not contain duplicates", field=field_name
        )
    return values


def _non_blank_strings(value: Any, field_name: str) -> tuple[str, ...]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        raise DomainCognitiveIntegrationContractError(
            f"{field_name} must be a sequence of strings", field=field_name
        )
    return tuple(_non_blank(item, field_name) for item in value)


def _freeze_metadata(value: Any) -> MappingProxyType[str, Any]:
    if not isinstance(value, Mapping):
        raise DomainCognitiveIntegrationContractError(
            "metadata must be a mapping", field="metadata"
        )
    try:
        return _deep_freeze(value)
    except DomainContractValidationError as exc:
        raise DomainCognitiveIntegrationContractError(
            exc.message, field="metadata", details=dict(exc.details)
        ) from exc


@dataclass(frozen=True, slots=True)
class DomainCognitiveIntegrationRequest:
    """Immutable request evidence that Domains may pass to Cognitive services."""

    request_id: str
    resolution_context_id: str
    resolution_result_id: str
    objective: str
    composition: DomainComposition
    profile: ResolvedDomainProfile
    resources: tuple[DomainCognitiveResourceInput, ...] = ()
    actor_id: str | None = None
    session_id: str | None = None
    effective_permissions: tuple[str, ...] = ()
    global_mandatory_rules: tuple[str, ...] = ()
    security_rules: tuple[str, ...] = ()
    requested_rule_ids: tuple[str, ...] = ()
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for field_name in (
            "request_id",
            "resolution_context_id",
            "resolution_result_id",
            "objective",
        ):
            object.__setattr__(
                self, field_name, _non_blank(getattr(self, field_name), field_name)
            )
        if type(self.composition) is not DomainComposition:
            raise DomainCognitiveIntegrationContractError(
                "composition must be a DomainComposition", field="composition"
            )
        if self.composition.status not in {
            DomainCompositionStatus.COMPOSED,
            DomainCompositionStatus.PARTIAL,
        }:
            raise DomainCognitiveIntegrationContractError(
                "composition status must be COMPOSED or PARTIAL", field="composition"
            )
        if type(self.profile) is not ResolvedDomainProfile:
            raise DomainCognitiveIntegrationContractError(
                "profile must be a ResolvedDomainProfile", field="profile"
            )
        if (
            self.profile.primary_domain != self.composition.primary_domain
            or self.profile.supporting_domains != self.composition.supporting_domains
        ):
            raise DomainCognitiveIntegrationContractError(
                "profile active domains must match composition", field="profile"
            )
        resources = _tuple_of_instances(
            self.resources, DomainCognitiveResourceInput, "resources"
        )
        active_domains = {
            self.composition.primary_domain,
            *self.composition.supporting_domains,
        }
        binding_ids = set()
        for resource in resources:
            if resource.binding.domain_id not in active_domains:
                raise DomainCognitiveIntegrationContractError(
                    "resource binding must belong to an active Domain",
                    field="resources",
                )
            if resource.binding.id in binding_ids:
                raise DomainCognitiveIntegrationContractError(
                    "resources must not duplicate binding IDs", field="resources"
                )
            binding_ids.add(resource.binding.id)
        object.__setattr__(self, "resources", resources)
        object.__setattr__(
            self, "actor_id", _optional_non_blank(self.actor_id, "actor_id")
        )
        object.__setattr__(
            self, "session_id", _optional_non_blank(self.session_id, "session_id")
        )
        for field_name in (
            "effective_permissions",
            "global_mandatory_rules",
            "security_rules",
            "requested_rule_ids",
        ):
            object.__setattr__(
                self,
                field_name,
                _unique_non_blank_strings(getattr(self, field_name), field_name),
            )
        object.__setattr__(self, "metadata", _freeze_metadata(self.metadata))


@dataclass(frozen=True, slots=True)
class DomainCognitiveIntegrationResult:
    """Immutable evidence returned from Cognitive services to Domain Intelligence."""

    request_id: str
    knowledge_package: KnowledgePackage
    validation_results: tuple[CognitiveValidationResult, ...]
    reasoning_context: ReasoningRuleContext
    rule_plan: DomainRuleExecutionPlan
    rule_result: DomainRuleExecutionResult
    adapted_resources: tuple[Resource, ...]
    extracted_bundles: tuple[KnowledgeBundle, ...]
    presentation_items: tuple[DomainPresentationItemRef, ...]
    trace_references: DomainTraceReferences
    warnings: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "request_id", _non_blank(self.request_id, "request_id")
        )
        for field_name, expected_type in (
            ("knowledge_package", KnowledgePackage),
            ("reasoning_context", ReasoningRuleContext),
            ("rule_plan", DomainRuleExecutionPlan),
            ("rule_result", DomainRuleExecutionResult),
            ("trace_references", DomainTraceReferences),
        ):
            if type(getattr(self, field_name)) is not expected_type:
                raise DomainCognitiveIntegrationContractError(
                    f"{field_name} must be a {expected_type.__name__}",
                    field=field_name,
                )
        object.__setattr__(
            self,
            "validation_results",
            _tuple_of_instances(
                self.validation_results,
                CognitiveValidationResult,
                "validation_results",
            ),
        )
        adapted_resources = _tuple_of_instances(
            self.adapted_resources, Resource, "adapted_resources"
        )
        resource_ids = [resource.id for resource in adapted_resources]
        if len(set(resource_ids)) != len(resource_ids):
            raise DomainCognitiveIntegrationContractError(
                "adapted_resources must not duplicate resource IDs",
                field="adapted_resources",
            )
        object.__setattr__(self, "adapted_resources", adapted_resources)
        object.__setattr__(
            self,
            "extracted_bundles",
            _tuple_of_instances(
                self.extracted_bundles, KnowledgeBundle, "extracted_bundles"
            ),
        )
        presentation_items = _tuple_of_instances(
            self.presentation_items, DomainPresentationItemRef, "presentation_items"
        )
        ref_ids = [item.ref_id for item in presentation_items]
        if len(set(ref_ids)) != len(ref_ids):
            raise DomainCognitiveIntegrationContractError(
                "presentation_items must not duplicate reference IDs",
                field="presentation_items",
            )
        object.__setattr__(self, "presentation_items", presentation_items)
        object.__setattr__(
            self, "warnings", _non_blank_strings(self.warnings, "warnings")
        )
