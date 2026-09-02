"""Tests for Phase 10.40 Domain/Cognitive integration contracts."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from cmm.cognitive import (
    Confidence,
    KnowledgeBundle,
    KnowledgePackage,
    Resource,
    ResourceInput,
    ResourceKind,
    ResourceProvenance,
    ResourceSourceKind,
    ResourceTemporalScope,
    SensitivityLevel,
)
from cmm.cognitive.reasoning_rule_contracts import ReasoningRuleContext
from cmm.cognitive.validation import (
    CognitiveValidationDecision,
    CognitiveValidationResult,
)
from cmm.domains.cognitive_integration_contracts import (
    DomainCognitiveIntegrationRequest,
    DomainCognitiveIntegrationResult,
    DomainCognitiveResourceInput,
)
from cmm.domains.composition_contracts import DomainComposition
from cmm.domains.enums import (
    DomainCompositionStatus,
    DomainReasoningDepth,
    DomainResourceResolutionStatus,
    DomainRuleExecutionStatus,
    DomainRuleSelectionStatus,
)
from cmm.domains.errors import DomainCognitiveIntegrationContractError
from cmm.domains.identifiers import DomainId
from cmm.domains.presentation_contracts import (
    DomainPresentationItemRef,
    DomainPresentationItemType,
)
from cmm.domains.profile_contracts import (
    DomainMemoryPolicy,
    DomainPresentationPolicy,
    DomainProductionPolicy,
    DomainQuestionPolicy,
    DomainTemporalPolicy,
    ResolvedDomainProfile,
)
from cmm.domains.resource_contracts import (
    DomainResourceBinding,
    DomainResourceResolution,
)
from cmm.domains.rule_contracts import (
    DomainRuleExecutionPlan,
    DomainRuleExecutionResult,
)
from cmm.domains.trace_contracts import DomainTraceReferences
from cmm.validation.enums import ValidationStatus

NOW = datetime(2026, 9, 2, tzinfo=timezone.utc)


def _binding(**overrides: object) -> DomainResourceBinding:
    values: dict[str, object] = {
        "id": "binding-1",
        "resource_id": "resource-1",
        "definition_id": "definition-1",
        "domain_id": DomainId("health"),
        "adapter": "health.note",
        "provenance": ("source-1",),
        "sensitivity": SensitivityLevel.INTERNAL,
    }
    values.update(overrides)
    return DomainResourceBinding(**values)  # type: ignore[arg-type]


def _resolution(
    binding: DomainResourceBinding, **overrides: object
) -> DomainResourceResolution:
    values: dict[str, object] = {
        "id": "resource-resolution-1",
        "resource_id": binding.resource_id,
        "status": DomainResourceResolutionStatus.RESOLVED,
        "trace_id": "resource-trace-1",
        "resolved_at": NOW,
        "bindings": (binding,),
    }
    values.update(overrides)
    return DomainResourceResolution(**values)  # type: ignore[arg-type]


def _source(**overrides: object) -> ResourceInput:
    values: dict[str, object] = {
        "id": "resource-1",
        "source_kind": ResourceSourceKind.USER_INPUT,
        "payload": "resource content",
        "sensitivity": SensitivityLevel.INTERNAL,
    }
    values.update(overrides)
    return ResourceInput(**values)  # type: ignore[arg-type]


def _composition(**overrides: object) -> DomainComposition:
    values: dict[str, object] = {
        "id": "composition-1",
        "resolution_id": "resolution-result-1",
        "status": DomainCompositionStatus.COMPOSED,
        "primary_domain": DomainId("health"),
        "supporting_domains": (DomainId("university"),),
        "composed_at": NOW,
    }
    values.update(overrides)
    return DomainComposition(**values)  # type: ignore[arg-type]


def _profile(**overrides: object) -> ResolvedDomainProfile:
    values: dict[str, object] = {
        "id": "profile-1",
        "primary_domain": DomainId("health"),
        "supporting_domains": (DomainId("university"),),
        "profile_names": ("HealthProfile",),
        "required_rules": (),
        "optional_rules": (),
        "prohibited_rules": (),
        "allowed_resource_kinds": None,
        "priority_resource_kinds": (),
        "prohibited_resource_kinds": (),
        "minimum_confidence": 0.5,
        "reasoning_depth": DomainReasoningDepth.STANDARD,
        "allowed_inferences": None,
        "prohibited_inferences": (),
        "maximum_questions": 5,
        "escalation_rules": (),
        "prohibited_actions": (),
        "question_policy": DomainQuestionPolicy(),
        "presentation_policy": DomainPresentationPolicy(),
        "memory_policy": DomainMemoryPolicy(),
        "temporal_policy": DomainTemporalPolicy(),
        "production_policy": DomainProductionPolicy(),
        "permissions": None,
        "modifications": (),
        "trace_id": "profile-trace-1",
        "resolved_at": NOW,
    }
    values.update(overrides)
    return ResolvedDomainProfile(**values)  # type: ignore[arg-type]


def _resource_input(**overrides: object) -> DomainCognitiveResourceInput:
    binding = _binding(**overrides.pop("binding_overrides", {}))
    resolution = _resolution(binding)
    return DomainCognitiveResourceInput(
        resolution=resolution, binding=binding, source=_source()
    )


def _request(**overrides: object) -> DomainCognitiveIntegrationRequest:
    values: dict[str, object] = {
        "request_id": "request-1",
        "resolution_context_id": "resolution-context-1",
        "resolution_result_id": "resolution-result-1",
        "objective": "Review health information",
        "composition": _composition(),
        "profile": _profile(),
    }
    values.update(overrides)
    return DomainCognitiveIntegrationRequest(**values)  # type: ignore[arg-type]


def _adapted_resource(resource_id: str = "adapted-resource-1") -> Resource:
    return Resource(
        id=resource_id,
        domain="health",
        kind=ResourceKind.NOTE,
        source=ResourceSourceKind.USER_INPUT,
        content="adapted resource content",
        provenance=ResourceProvenance(
            source_type=ResourceSourceKind.USER_INPUT,
            source_id="source-1",
            retrieved_at=NOW,
        ),
        reliability=Confidence(1.0),
        temporal_scope=ResourceTemporalScope(ingested_at=NOW),
        created_at=NOW,
        updated_at=NOW,
    )


def _result(**overrides: object) -> DomainCognitiveIntegrationResult:
    values: dict[str, object] = {
        "request_id": "request-1",
        "knowledge_package": KnowledgePackage(
            id="knowledge-package-1",
            objective="Review health information",
            created_at=NOW,
        ),
        "validation_results": (
            CognitiveValidationResult(
                id="validation-1",
                target_id="knowledge-package-1",
                target_kind="knowledge_package",
                status=ValidationStatus.PASSED,
                decision=CognitiveValidationDecision.ACCEPT,
                created_at=NOW,
            ),
        ),
        "reasoning_context": ReasoningRuleContext(
            reasoning_id="reasoning-1", timestamp=NOW
        ),
        "rule_plan": DomainRuleExecutionPlan(
            id="rule-plan-1", status=DomainRuleSelectionStatus.READY, created_at=NOW
        ),
        "rule_result": DomainRuleExecutionResult(
            id="rule-result-1",
            plan_id="rule-plan-1",
            status=DomainRuleExecutionStatus.COMPLETED,
            started_at=NOW,
            completed_at=NOW,
        ),
        "adapted_resources": (_adapted_resource(),),
        "extracted_bundles": (KnowledgeBundle(id="bundle-1", created_at=NOW),),
        "presentation_items": (
            DomainPresentationItemRef(
                ref_id="presentation-1",
                item_type=DomainPresentationItemType.FINDING,
                source_order=0,
            ),
        ),
        "trace_references": DomainTraceReferences(
            resolution_context_id="resolution-context-1",
            resolution_result_id="resolution-result-1",
            composition_id="composition-1",
        ),
    }
    values.update(overrides)
    return DomainCognitiveIntegrationResult(**values)  # type: ignore[arg-type]


def test_resource_input_accepts_resolved_binding_and_matching_source() -> None:
    """Would fail if the contract stopped enforcing the accepted resource lineage."""
    binding = _binding()

    resource_input = DomainCognitiveResourceInput(
        resolution=_resolution(binding), binding=binding, source=_source()
    )

    assert resource_input.binding is binding


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("resolution", object()),
        ("binding", object()),
        ("source", object()),
    ],
)
def test_resource_input_rejects_wrong_boundary_type(field: str, value: object) -> None:
    """Would fail if a non-canonical resource boundary object were accepted."""
    binding = _binding()
    values: dict[str, object] = {
        "resolution": _resolution(binding),
        "binding": binding,
        "source": _source(),
    }
    values[field] = value

    with pytest.raises(DomainCognitiveIntegrationContractError, match=field):
        DomainCognitiveResourceInput(**values)  # type: ignore[arg-type]


def test_resource_input_rejects_binding_absent_from_resolution() -> None:
    """Would fail if a resource could be linked to unaccepted domain binding."""
    accepted = _binding(id="binding-accepted")
    disconnected = _binding(id="binding-disconnected")

    with pytest.raises(DomainCognitiveIntegrationContractError, match="binding"):
        DomainCognitiveResourceInput(
            resolution=_resolution(accepted), binding=disconnected, source=_source()
        )


@pytest.mark.parametrize(
    "status",
    (DomainResourceResolutionStatus.BLOCKED, DomainResourceResolutionStatus.FAILED),
)
def test_resource_input_rejects_non_executable_resolution_status(
    status: DomainResourceResolutionStatus,
) -> None:
    """Would fail if blocked or failed resource evidence reached cognition."""
    binding = _binding()
    resolution = _resolution(binding)
    object.__setattr__(resolution, "status", status)

    with pytest.raises(DomainCognitiveIntegrationContractError, match="resolution"):
        DomainCognitiveResourceInput(
            resolution=resolution, binding=binding, source=_source()
        )


@pytest.mark.parametrize(
    ("source_overrides", "field"),
    [
        ({"id": "another-resource"}, "source.id"),
        ({"sensitivity": SensitivityLevel.PUBLIC}, "source.sensitivity"),
    ],
)
def test_resource_input_rejects_source_that_does_not_match_binding(
    source_overrides: dict[str, object], field: str
) -> None:
    """Would fail if source identity or sensitivity drifted from the binding."""
    binding = _binding()

    with pytest.raises(DomainCognitiveIntegrationContractError, match=field):
        DomainCognitiveResourceInput(
            resolution=_resolution(binding),
            binding=binding,
            source=_source(**source_overrides),
        )


@pytest.mark.parametrize("extractor_name", ("", "   ", 3))
def test_resource_input_rejects_blank_or_non_string_extractor_name(
    extractor_name: object,
) -> None:
    """Would fail if the optional extractor name ceased being a usable identifier."""
    binding = _binding()

    with pytest.raises(DomainCognitiveIntegrationContractError, match="extractor_name"):
        DomainCognitiveResourceInput(
            resolution=_resolution(binding),
            binding=binding,
            source=_source(),
            extractor_name=extractor_name,  # type: ignore[arg-type]
        )


@pytest.mark.parametrize(
    "field",
    ("request_id", "resolution_context_id", "resolution_result_id", "objective"),
)
def test_request_rejects_blank_required_identifiers(field: str) -> None:
    """Would fail if an integration request accepted an untraceable intent."""
    with pytest.raises(DomainCognitiveIntegrationContractError, match=field):
        _request(**{field: "   "})


@pytest.mark.parametrize(
    ("field", "value"),
    (("composition", object()), ("profile", object())),
)
def test_request_rejects_wrong_composition_or_profile_type(
    field: str, value: object
) -> None:
    """Would fail if the request stopped requiring canonical Domain evidence."""
    with pytest.raises(DomainCognitiveIntegrationContractError, match=field):
        _request(**{field: value})


@pytest.mark.parametrize(
    "status", (DomainCompositionStatus.BLOCKED, DomainCompositionStatus.FAILED)
)
def test_request_rejects_non_executable_composition(
    status: DomainCompositionStatus,
) -> None:
    """Would fail if a blocked or failed composition were sent to cognition."""
    composition = _composition()
    object.__setattr__(composition, "status", status)

    with pytest.raises(DomainCognitiveIntegrationContractError, match="composition"):
        _request(composition=composition)


@pytest.mark.parametrize(
    "profile_overrides",
    (
        {"primary_domain": DomainId("university")},
        {"supporting_domains": ()},
    ),
)
def test_request_rejects_profile_with_different_active_domains(
    profile_overrides: dict[str, object],
) -> None:
    """Would fail if composition and profile described different domain identity."""
    with pytest.raises(DomainCognitiveIntegrationContractError, match="profile"):
        _request(profile=_profile(**profile_overrides))


def test_request_rejects_resource_binding_outside_active_domains() -> None:
    """Would fail if an inactive Domain's resource reached the integration."""
    resource = _resource_input(binding_overrides={"domain_id": DomainId("sport")})

    with pytest.raises(DomainCognitiveIntegrationContractError) as error:
        _request(resources=(resource,))
    assert error.value.field == "resources"


def test_request_rejects_duplicate_resource_binding_ids() -> None:
    """Would fail if the same Domain binding could be integrated twice."""
    resource = _resource_input()

    with pytest.raises(DomainCognitiveIntegrationContractError, match="resources"):
        _request(resources=(resource, resource))


@pytest.mark.parametrize(
    "field",
    (
        "effective_permissions",
        "global_mandatory_rules",
        "security_rules",
        "requested_rule_ids",
    ),
)
def test_request_rejects_blank_or_duplicate_string_collections(field: str) -> None:
    """Would fail if policy IDs became ambiguous or unusable."""
    with pytest.raises(DomainCognitiveIntegrationContractError, match=field):
        _request(**{field: ("valid.id", "valid.id")})
    with pytest.raises(DomainCognitiveIntegrationContractError, match=field):
        _request(**{field: ("   ",)})


@pytest.mark.parametrize("field", ("actor_id", "session_id"))
def test_request_rejects_blank_optional_identity(field: str) -> None:
    """Would fail if an optional identity, once supplied, were blank."""
    with pytest.raises(DomainCognitiveIntegrationContractError, match=field):
        _request(**{field: "   "})


def test_request_deep_freezes_metadata() -> None:
    """Would fail if caller-owned nested metadata could mutate the request."""
    metadata = {"nested": {"items": ["stable"]}}

    request = _request(metadata=metadata)
    metadata["nested"]["items"].append("later")

    assert request.metadata["nested"]["items"] == ("stable",)
    with pytest.raises(TypeError):
        request.metadata["nested"]["items"] += ("forbidden",)  # type: ignore[index,operator]


def test_request_rejects_non_string_metadata_key() -> None:
    """Would fail if metadata ceased to have a stable string-keyed shape."""
    with pytest.raises(DomainCognitiveIntegrationContractError) as error:
        _request(metadata={1: "not allowed"})
    assert error.value.field == "metadata"


def test_result_accepts_only_canonical_evidence_and_freezes_collections() -> None:
    """Would fail if result evidence were mutable or stopped using canonical types."""
    result = _result(
        validation_results=[
            CognitiveValidationResult(
                id="validation-1",
                target_id="knowledge-package-1",
                target_kind="knowledge_package",
                status=ValidationStatus.PASSED,
                decision=CognitiveValidationDecision.ACCEPT,
                created_at=NOW,
            )
        ],
        adapted_resources=[_adapted_resource()],
        extracted_bundles=[KnowledgeBundle(id="bundle-1", created_at=NOW)],
        presentation_items=[
            DomainPresentationItemRef(
                ref_id="presentation-1",
                item_type=DomainPresentationItemType.FINDING,
                source_order=0,
            )
        ],
        warnings=["review recommended"],
    )

    assert result.validation_results == (result.validation_results[0],)
    assert result.adapted_resources == (result.adapted_resources[0],)
    assert result.extracted_bundles == (result.extracted_bundles[0],)
    assert result.presentation_items == (result.presentation_items[0],)
    assert result.warnings == ("review recommended",)
    with pytest.raises(AttributeError):
        result.warnings = ()  # type: ignore[misc]


@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("knowledge_package", object()),
        ("reasoning_context", object()),
        ("rule_plan", object()),
        ("rule_result", object()),
        ("trace_references", object()),
        ("validation_results", (object(),)),
        ("adapted_resources", (object(),)),
        ("extracted_bundles", (object(),)),
        ("presentation_items", (object(),)),
    ),
)
def test_result_rejects_non_canonical_evidence(field: str, value: object) -> None:
    """Would fail if evidence from a non-owning subsystem crossed this boundary."""
    with pytest.raises(DomainCognitiveIntegrationContractError) as error:
        _result(**{field: value})
    assert error.value.field == field


def test_result_rejects_blank_request_id() -> None:
    """Would fail if result evidence could not be joined to its request."""
    with pytest.raises(DomainCognitiveIntegrationContractError, match="request_id"):
        _result(request_id="   ")


def test_result_rejects_duplicate_adapted_resource_ids() -> None:
    """Would fail if the same adapted resource could appear twice as evidence."""
    resource = _adapted_resource()

    with pytest.raises(DomainCognitiveIntegrationContractError) as error:
        _result(adapted_resources=(resource, resource))
    assert error.value.field == "adapted_resources"


def test_result_rejects_duplicate_presentation_reference_ids() -> None:
    """Would fail if evidence could point twice at one presentation reference."""
    item = DomainPresentationItemRef(
        ref_id="presentation-1",
        item_type=DomainPresentationItemType.FINDING,
        source_order=0,
    )

    with pytest.raises(DomainCognitiveIntegrationContractError) as error:
        _result(presentation_items=(item, item))
    assert error.value.field == "presentation_items"


@pytest.mark.parametrize("warnings", (("",), ("   ",), (3,)))
def test_result_rejects_blank_or_non_string_warnings(
    warnings: tuple[object, ...],
) -> None:
    """Would fail if a result warning were not a displayable diagnostic."""
    with pytest.raises(DomainCognitiveIntegrationContractError) as error:
        _result(warnings=warnings)
    assert error.value.field == "warnings"
