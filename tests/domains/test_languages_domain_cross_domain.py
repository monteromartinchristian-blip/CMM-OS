"""Phase 10.26 — Languages Cross-Domain Boundary Tests."""

from __future__ import annotations

import inspect
import json
from datetime import datetime, timezone

from cmm.agent_runtime.domain_permission_contracts import PermissionCapability
from cmm.domains.composer import DefaultDomainComposer
from cmm.domains.concerns.definition import build_concerns_domain_definition
from cmm.domains.contracts import DomainResult
from cmm.domains.general.definition import build_general_domain_definition
from cmm.domains.identifiers import DomainId
from cmm.domains.languages import (
    build_standard_languages_domain_bootstrap,
    register_languages_domain,
)
from cmm.domains.languages.definition import build_languages_domain_definition
from cmm.domains.languages.permissions import build_languages_permission_policy
from cmm.domains.languages.resources import build_languages_resource_definitions
from cmm.domains.oppositions.definition import build_oppositions_domain_definition
from cmm.domains.reflection.definition import build_reflection_domain_definition
from cmm.domains.registry import DomainRegistry
from cmm.domains.resolution_builder import DomainResolutionContextBuilder
from cmm.domains.resolution_contracts import DomainResolutionSignal
from cmm.domains.resolver import DefaultDomainResolver
from cmm.domains.university.definition import build_university_domain_definition
from cmm.domains.university.permissions import build_university_permission_policy

NOW = datetime(2026, 8, 23, 12, 0, tzinfo=timezone.utc)

_BUILDERS = {
    "general": build_general_domain_definition,
    "languages": build_languages_domain_definition,
    "oppositions": build_oppositions_domain_definition,
    "university": build_university_domain_definition,
    "concerns": build_concerns_domain_definition,
    "reflection": build_reflection_domain_definition,
}


def _resolve(primary: str, supporting: str | None = None):
    registry = DomainRegistry()
    for builder in _BUILDERS.values():
        definition = builder()
        registry.register(definition)
        registry.enable(str(definition.id))
    signals = [
        DomainResolutionSignal(
            kind="intent",
            source="user",
            value=f"{primary}-intent",
            domain_ids=(f"domain:{primary}",),
        ),
        DomainResolutionSignal(
            kind="objective",
            source="user",
            value=f"{primary}-objective",
            domain_ids=(f"domain:{primary}",),
        ),
        DomainResolutionSignal(
            kind="entity",
            source="user",
            value=f"{primary}-entity",
            domain_ids=(f"domain:{primary}",),
        ),
    ]
    if supporting is not None:
        signals.extend(
            (
                DomainResolutionSignal(
                    kind="operation",
                    source="system",
                    value=f"{supporting}-operation",
                    domain_ids=(f"domain:{supporting}",),
                ),
                DomainResolutionSignal(
                    kind="entity",
                    source="system",
                    value=f"{supporting}-entity",
                    domain_ids=(f"domain:{supporting}",),
                ),
            )
        )
    context = DomainResolutionContextBuilder(
        id_factory=lambda: f"context-{primary}-{supporting or 'none'}",
        clock=lambda: NOW,
    ).build(
        registry_snapshot=registry.snapshot(),
        user_input=f"Connected {primary} request",
        authorized_domains=tuple(f"domain:{slug}" for slug in _BUILDERS),
        signals=tuple(signals),
    )
    result = DefaultDomainResolver(
        fallback_domain=DomainId("general"),
        id_factory=lambda: f"resolution-{primary}-{supporting or 'none'}",
        clock=lambda: NOW,
    ).resolve(context)
    return result


def test_general_fallback_reused() -> None:
    """Standard Languages bootstrap keeps General domain as fallback."""
    bootstrap = build_standard_languages_domain_bootstrap()
    assert bootstrap.domain_registry.get("domain:general") is not None
    assert bootstrap.domain_registry.get("domain:languages") is not None
    assert bootstrap.resolver.fallback_domain == DomainId(slug="general")


def test_cross_domain_resource_projection_boundary() -> None:
    """Verify languages.domain_result carries clean cross-domain metadata."""
    resources = {r.id: r for r in build_languages_resource_definitions()}
    boundary = resources["languages.domain_result"]
    assert boundary.metadata.get("cross_domain_projection") is True
    assert boundary.metadata.get("no_private_store_merge") is True
    assert boundary.metadata.get("specialized_ownership_preserved") is True


def test_no_direct_sibling_store_import() -> None:
    """Verify Languages package does not import private stores from sibling domains."""
    source = inspect.getsource(__import__("cmm.domains.languages", fromlist=["*"]))
    assert "university_store" not in source
    assert "oppositions_store" not in source
    assert "health_store" not in source
    assert "concerns_store" not in source


def test_most_restrictive_permissions_survive_composition() -> None:
    """Composed policy with university retains strict prohibited capabilities."""
    lang_policy = build_languages_permission_policy()
    univ_policy = build_university_permission_policy()
    composed_denied = set(lang_policy.prohibited_capabilities) | set(
        univ_policy.prohibited_capabilities
    )
    for cap in (
        PermissionCapability.COMMUNICATION_EXTERNAL,
        PermissionCapability.FILE_MODIFY,
        PermissionCapability.SCHEDULE_MODIFY,
        PermissionCapability.FINANCIAL_ACTION,
    ):
        assert cap in composed_denied


def test_registration_does_not_mutate_unregistered_domains() -> None:
    """Registering Languages touches only Languages definitions."""
    from cmm.agent_runtime.operation_registry import InMemoryAgentOperationRegistry
    from cmm.cognitive.reasoning_rule_registry import InMemoryReasoningRuleRegistry
    from cmm.domains.operation_registry import InMemoryDomainOperationRegistry
    from cmm.domains.permission_registry import DomainPermissionRegistry
    from cmm.domains.profile_registry import InMemoryDomainProfileRegistry
    from cmm.domains.registry import DomainRegistry
    from cmm.domains.resource_registry import InMemoryDomainResourceRegistry
    from cmm.domains.workflow_registry import InMemoryDomainWorkflowRegistry
    from cmm.workflows.registry import InMemoryWorkflowRegistry

    registries = {
        "domain_registry": DomainRegistry(),
        "profile_registry": InMemoryDomainProfileRegistry(),
        "resource_registry": InMemoryDomainResourceRegistry(),
        "rule_registry": InMemoryReasoningRuleRegistry(),
        "operation_registry": InMemoryDomainOperationRegistry(
            InMemoryAgentOperationRegistry()
        ),
        "workflow_registry": InMemoryDomainWorkflowRegistry(InMemoryWorkflowRegistry()),
        "permission_registry": DomainPermissionRegistry(),
    }
    register_languages_domain(**registries)
    for other in (
        "domain:relationships",
        "domain:health",
        "domain:reflection",
        "domain:university",
        "domain:oppositions",
        "domain:concerns",
    ):
        assert registries["domain_registry"].get(other) is None
    assert all(
        res.id.startswith("languages.")
        for res in registries["resource_registry"].list_all()
    )


def test_cross_domain_projection_json_safe() -> None:
    """Verify JSON safety of cross-domain payload."""
    payload = {
        "source_domain": "domain:university",
        "requirement": "B2 English required for Erasmus exchange",
        "factual_ownership_retained": True,
    }
    json_str = json.dumps(payload, allow_nan=False)
    assert json_str is not None


def test_real_default_resolver_preserves_languages_cross_domain_ownership() -> None:
    cases = (
        ("languages", None),  # direct practice
        ("languages", None),  # direct C1 oral practice
        ("oppositions", "languages"),
        ("university", "languages"),
        ("languages", "general"),
        ("concerns", "languages"),
        ("reflection", "languages"),
    )
    for primary, supporting in cases:
        resolution = _resolve(primary, supporting)
        assert resolution.status.value == "resolved"
        assert str(resolution.primary_domain) == f"domain:{primary}"
        actual_supporting = {str(item) for item in resolution.supporting_domains}
        if supporting is None:
            assert not actual_supporting
        else:
            assert f"domain:{supporting}" in actual_supporting


def test_real_oppositions_languages_resolution_composes() -> None:
    resolution = _resolve("oppositions", "languages")
    composition = DefaultDomainComposer(
        id_factory=lambda: "composition-oppositions-languages", clock=lambda: NOW
    ).compose(
        resolution,
        (
            build_oppositions_domain_definition(),
            build_languages_domain_definition(),
        ),
    )
    assert str(composition.primary_domain) == "domain:oppositions"
    assert tuple(str(item) for item in composition.supporting_domains) == (
        "domain:languages",
    )


def test_typed_oppositions_projection_is_purpose_minimized() -> None:
    allowed = {
        "certification_status": "not_certified",
        "estimated_readiness": "developing",
        "relevant_proficiency": {"reading": "B2"},
        "progress_toward_shared_goal": "on_track",
        "recommended_workload": "moderate",
        "blocking_language_gap": None,
    }
    projection = DomainResult(
        id="languages-oppositions-projection-1",
        status="completed",
        objective="Share only language readiness needed for opposition planning",
        primary_domain="domain:languages",
        supporting_domains=("domain:oppositions",),
        findings=(allowed,),
        confidence=0.8,
    )
    payload = projection.to_dict()
    assert set(payload["findings"][0]) == set(allowed)
    for forbidden in (
        "complete_vocabulary_history",
        "all_observed_errors",
        "all_transcripts",
        "all_writing_corrections",
        "full_languages_memory",
    ):
        assert forbidden not in payload["findings"][0]
    json.dumps(payload, allow_nan=False)
