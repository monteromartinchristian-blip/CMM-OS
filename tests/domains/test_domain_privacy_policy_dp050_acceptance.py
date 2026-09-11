"""Phase 10.50 – connected acceptance ``AT-DP-050``.

Exercises the real canonical components end to end: real first-party
``DomainDefinition`` objects, the real ``DomainRegistry``, the canonical
``ParsedDomainPack`` declarative path, the real ``KnowledgePackageBuilder``,
``privacy_from_knowledge_package``, ``resolve_effective_privacy_metadata``,
``evaluate_privacy_operation``, the real Phase 10.15 permission stack and the
real Domain Trace reference contracts. No authority component is mocked.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from cmm.agent_runtime.agent_security_enums import (
    SensitivityLevel as PermissionSensitivity,
)
from cmm.agent_runtime.domain_permission_contracts import PermissionCapability
from cmm.cognitive.contracts import Confidence
from cmm.cognitive.enums import KnowledgeKind, SensitivityLevel
from cmm.cognitive.knowledge import KnowledgeItem
from cmm.cognitive.knowledge_packages import (
    KnowledgePackageBuilder,
    KnowledgePackageRequest,
)
from cmm.cognitive.privacy import (
    PrivacyDecisionStatus,
    PrivacyMetadata,
    PrivacyOperation,
    PrivacyOperationContext,
    PrivacyPolicy,
    ProcessingLocation,
    evaluate_privacy_operation,
    privacy_from_knowledge_package,
    resolve_effective_privacy_metadata,
)
from cmm.cognitive.resources import (
    Resource,
    ResourceKind,
    ResourceProvenance,
    ResourceSourceKind,
    ResourceTemporalScope,
)
from cmm.cognitive.store_memory import InMemoryKnowledgeStore
from cmm.domains.concerns.definition import build_concerns_domain_definition
from cmm.domains.contracts import DomainDefinition
from cmm.domains.enums import DomainKind, DomainPackKind
from cmm.domains.errors import DomainError
from cmm.domains.general.definition import build_general_domain_definition
from cmm.domains.health.definition import build_health_domain_definition
from cmm.domains.languages.definition import build_languages_domain_definition
from cmm.domains.life_plan.definition import build_life_plan_domain_definition
from cmm.domains.manifest import DomainComponentReference, DomainManifest
from cmm.domains.oppositions.definition import build_oppositions_domain_definition
from cmm.domains.pack import ParsedDomainPack
from cmm.domains.parenthood.definition import build_parenthood_domain_definition
from cmm.domains.permission_contracts import (
    CrossDomainPermissionRequest,
    DomainPermissionPolicy,
)
from cmm.domains.permission_gate import DomainPermissionGate
from cmm.domains.permission_registry import DomainPermissionRegistry
from cmm.domains.permission_resolution import DomainPermissionResolver
from cmm.domains.privacy_policy_contracts import (
    DomainPrivacyPolicy,
    project_domain_privacy_metadata,
)
from cmm.domains.project.definition import build_project_domain_definition
from cmm.domains.reflection.definition import build_reflection_domain_definition
from cmm.domains.registry import DomainRegistry
from cmm.domains.relationships.definition import (
    build_relationships_domain_definition,
)
from cmm.domains.sport.definition import build_sport_domain_definition
from cmm.domains.trace_contracts import (
    DomainTraceDomainSelection,
    DomainTraceReference,
    DomainTraceReferenceInventory,
    DomainTraceReferenceKind,
)
from cmm.domains.university.definition import build_university_domain_definition

NOW = datetime(2026, 9, 11, 12, 0, tzinfo=timezone.utc)

FIRST_PARTY_BUILDERS = {
    "general": build_general_domain_definition,
    "health": build_health_domain_definition,
    "relationships": build_relationships_domain_definition,
    "university": build_university_domain_definition,
    "oppositions": build_oppositions_domain_definition,
    "reflection": build_reflection_domain_definition,
    "concerns": build_concerns_domain_definition,
    "languages": build_languages_domain_definition,
    "parenthood": build_parenthood_domain_definition,
    "sport": build_sport_domain_definition,
    "life_plan": build_life_plan_domain_definition,
    "project": build_project_domain_definition,
}


class _Checkpointer:
    def __init__(self) -> None:
        self.points: list[str] = []

    def checkpoint(self, name: str) -> None:
        self.points.append(name)


def _manifest_for(definition: DomainDefinition) -> DomainManifest:
    """Build a coherent manifest for a real first-party definition."""

    def _components(ids: tuple[str, ...]) -> tuple[DomainComponentReference, ...]:
        return tuple(
            DomainComponentReference(id=item, path=f"{item.replace('.', '/')}.json")
            for item in ids
        )

    return DomainManifest(
        id=definition.manifest_id,
        domain_id=definition.id,
        schema_version="1",
        package_version=definition.version,
        pack_kind=DomainPackKind.INTERNAL,
        resources=_components(definition.resources),
        rules=_components(definition.rules),
        operations=_components(definition.operations),
        workflows=_components(definition.workflows),
        validators=_components(definition.validators),
    )


def _resource(
    resource_id: str,
    *,
    sensitivity: SensitivityLevel = SensitivityLevel.SENSITIVE,
    domain: str = "domain:health",
) -> Resource:
    return Resource(
        id=resource_id,
        domain=domain,
        kind=ResourceKind.DOCUMENT,
        source=ResourceSourceKind.USER_INPUT,
        content="canonical record content",
        provenance=ResourceProvenance(
            source_type=ResourceSourceKind.USER_INPUT,
            source_id="source-1",
            retrieved_at=NOW,
        ),
        reliability=Confidence(value=0.9),
        temporal_scope=ResourceTemporalScope(ingested_at=NOW),
        sensitivity=sensitivity,
        created_at=NOW,
        updated_at=NOW,
    )


def _package(resource: Resource):
    store = InMemoryKnowledgeStore()
    store.save_item(
        KnowledgeItem(
            id=f"item:{resource.id}",
            statement="Canonical recorded observation.",
            kind=KnowledgeKind.OBSERVATION,
            confidence=Confidence(value=0.9),
            resource_id=resource.id,
            sensitivity=resource.sensitivity,
            created_at=NOW,
            updated_at=NOW,
        )
    )
    return KnowledgePackageBuilder(store=store, resources=(resource,)).build(
        KnowledgePackageRequest(objective="canonical review", domain=resource.domain)
    )


def _permission_gate(
    source_policy: DomainPermissionPolicy, target_policy: DomainPermissionPolicy
) -> DomainPermissionGate:
    registry = DomainPermissionRegistry()
    registry.register(source_policy)
    registry.register(target_policy)
    return DomainPermissionGate(DomainPermissionResolver(registry), clock=lambda: NOW)


def _policy(
    policy_id: str, domain_id: str, **overrides: object
) -> DomainPermissionPolicy:
    values: dict[str, object] = {
        "policy_id": policy_id,
        "domain_id": domain_id,
        "version": "1.0.0",
        "allowed_sensitivity_levels": (
            PermissionSensitivity.PUBLIC,
            PermissionSensitivity.INTERNAL,
        ),
    }
    values.update(overrides)
    return DomainPermissionPolicy(**values)  # type: ignore[arg-type]


def test_at_dp050_connected_acceptance() -> None:
    """Connected AT-DP-050 acceptance covering scenarios A–K."""
    cp = _Checkpointer()

    # ── Scenario I: exact 12-domain first-party inventory ─────────────────
    definitions = {slug: builder() for slug, builder in FIRST_PARTY_BUILDERS.items()}
    assert len(definitions) == 12
    declared = {
        slug: definition.privacy_policy
        for slug, definition in definitions.items()
        if definition.privacy_policy is not None
    }
    assert len(declared) == 11
    for slug, definition in definitions.items():
        if definition.privacy_policy is None:
            assert slug == "general"
            continue
        assert definition.privacy_policy.domain_id == definition.id
        assert isinstance(definition.privacy_policy, DomainPrivacyPolicy)
    cp.checkpoint("01-first-party-inventory")

    # ── Scenario J: canonical declarative round trip ──────────────────────
    health = definitions["health"]
    manifest = _manifest_for(health)
    parsed = ParsedDomainPack(definition=health, manifest=manifest)
    restored = ParsedDomainPack.from_dict(parsed.to_dict())
    assert restored.definition.privacy_policy == health.privacy_policy
    assert restored.to_dict() == parsed.to_dict()

    declarative = ParsedDomainPack.from_declarative_dict(
        {
            "id": "health",
            "version": health.version,
            "name": health.name,
            "display_name": health.display_name,
            "description": health.description,
            "author": "CMM OS",
            "license": "internal",
            "privacy_policy": health.privacy_policy.to_dict(),
        }
    )
    assert declarative.definition.privacy_policy == health.privacy_policy
    assert (
        declarative.definition.privacy_policy.to_dict()
        == health.privacy_policy.to_dict()
    )

    with pytest.raises(DomainError):
        malformed = health.privacy_policy.to_dict()
        malformed["schema_version"] = "2"
        ParsedDomainPack.from_declarative_dict(
            {
                "id": "health",
                "version": health.version,
                "name": health.name,
                "display_name": health.display_name,
                "description": health.description,
                "author": "CMM OS",
                "license": "internal",
                "privacy_policy": malformed,
            }
        )
    cp.checkpoint("02-declarative-round-trip")

    # ── Real DomainRegistry path ──────────────────────────────────────────
    registry = DomainRegistry()
    registered_health = registry.register(health)
    registered_university = registry.register(definitions["university"])
    assert registered_health.privacy_policy == health.privacy_policy
    assert registry.get("domain:health").privacy_policy == health.privacy_policy
    assert registered_university.privacy_policy is not None
    cp.checkpoint("03-real-registry")

    # ── Scenario G: General synthesizes no grant ──────────────────────────
    general = definitions["general"]
    assert general.privacy_policy is None

    general_resource = _resource(
        "resource:general",
        sensitivity=SensitivityLevel.INTERNAL,
        domain="domain:general",
    )
    general_package = _package(general_resource)
    general_effective = resolve_effective_privacy_metadata(
        privacy_from_knowledge_package(general_package)
    ).effective
    assert general_effective.policy is PrivacyPolicy.LOCAL_ONLY
    assert general_effective.allow_remote is False

    general_remote = evaluate_privacy_operation(
        general_effective,
        PrivacyOperation.PROCESS_REMOTE,
        PrivacyOperationContext(processing_location=ProcessingLocation.REMOTE, at=NOW),
    )
    assert general_remote.allowed is False
    assert general_remote.reason_code == "remote_blocked_local_only"
    cp.checkpoint("04-general-no-default")

    # ── Scenario B: sensitive Domain is local by default ──────────────────
    health_resource = _resource("resource:health-record")
    health_package = _package(health_resource)
    health_domain_privacy = project_domain_privacy_metadata(
        health.privacy_policy, processing_location=ProcessingLocation.REMOTE
    )
    health_effective = resolve_effective_privacy_metadata(
        privacy_from_knowledge_package(health_package), health_domain_privacy
    ).effective

    assert health_effective.policy is PrivacyPolicy.LOCAL_ONLY
    assert health_effective.allow_remote is False
    assert health_effective.allow_export is False

    health_remote = evaluate_privacy_operation(
        health_effective,
        PrivacyOperation.PROCESS_REMOTE,
        PrivacyOperationContext(
            processing_location=ProcessingLocation.REMOTE,
            approval_granted=True,
            at=NOW,
        ),
    )
    assert health_remote.allowed is False
    assert health_remote.reason_code == "remote_blocked_local_only"

    health_export = evaluate_privacy_operation(
        health_effective,
        PrivacyOperation.EXPORT,
        PrivacyOperationContext(at=NOW),
    )
    assert health_export.allowed is False
    assert health_export.reason_code == "export_blocked"

    prohibited_input = PrivacyMetadata(
        policy=PrivacyPolicy.REMOTE_ALLOWED,
        allowed_processing_locations=(
            ProcessingLocation.LOCAL,
            ProcessingLocation.REMOTE,
        ),
        prohibited_providers=("provider:gamma",),
        allow_remote=True,
    )
    provider_effective = resolve_effective_privacy_metadata(
        prohibited_input, health_effective
    ).effective
    assert provider_effective.prohibited_providers == ("provider:gamma",)
    assert provider_effective.policy is PrivacyPolicy.LOCAL_ONLY

    provider_decision = evaluate_privacy_operation(
        provider_effective,
        PrivacyOperation.TRANSMIT_TO_PROVIDER,
        PrivacyOperationContext(
            processing_location=ProcessingLocation.REMOTE,
            provider_id="provider:gamma",
            at=NOW,
        ),
    )
    assert provider_decision.allowed is False
    assert provider_decision.reason_code == "remote_blocked_local_only"
    cp.checkpoint("05-sensitive-domain-local")

    # ── Scenario A: LOCAL_ONLY cannot be widened ──────────────────────────
    # Less restrictive real Domain policy (University: REMOTE_ALLOWED) plus a
    # stricter resource/package LOCAL_ONLY policy.
    permissive_domain = project_domain_privacy_metadata(
        definitions["university"].privacy_policy,
        processing_location=ProcessingLocation.REMOTE,
    )
    assert permissive_domain.policy is PrivacyPolicy.REMOTE_ALLOWED
    strict_package = PrivacyMetadata(
        policy=PrivacyPolicy.LOCAL_ONLY,
        sensitivity=SensitivityLevel.RESTRICTED,
        allowed_processing_locations=(ProcessingLocation.LOCAL,),
        allow_remote=False,
    )
    widened = resolve_effective_privacy_metadata(
        strict_package, permissive_domain
    ).effective
    assert widened.policy is PrivacyPolicy.LOCAL_ONLY
    assert widened.allow_remote is False

    widened_decision = evaluate_privacy_operation(
        widened,
        PrivacyOperation.PROCESS_REMOTE,
        PrivacyOperationContext(
            processing_location=ProcessingLocation.REMOTE,
            approval_granted=True,
            at=NOW,
        ),
    )
    assert widened_decision.allowed is False
    assert widened_decision.status is PrivacyDecisionStatus.DENIED
    cp.checkpoint("06-local-only-cannot-widen")

    # ── Scenario C: remote-allowed Domain is conditional ──────────────────
    university = definitions["university"]
    university_remote = project_domain_privacy_metadata(
        university.privacy_policy, processing_location=ProcessingLocation.REMOTE
    )
    domain_only = resolve_effective_privacy_metadata(university_remote).effective
    assert domain_only.policy is PrivacyPolicy.REMOTE_ALLOWED

    domain_only_decision = evaluate_privacy_operation(
        domain_only,
        PrivacyOperation.PROCESS_REMOTE,
        PrivacyOperationContext(processing_location=ProcessingLocation.REMOTE, at=NOW),
    )
    assert domain_only_decision.allowed is True

    university_resource = _resource(
        "resource:university-notes",
        sensitivity=SensitivityLevel.SENSITIVE,
        domain="domain:university",
    )
    university_package = _package(university_resource)
    conditional = resolve_effective_privacy_metadata(
        privacy_from_knowledge_package(university_package), university_remote
    ).effective
    assert conditional.policy is PrivacyPolicy.LOCAL_ONLY

    conditional_decision = evaluate_privacy_operation(
        conditional,
        PrivacyOperation.PROCESS_REMOTE,
        PrivacyOperationContext(processing_location=ProcessingLocation.REMOTE, at=NOW),
    )
    assert conditional_decision.allowed is False
    assert conditional_decision.reason_code == "remote_blocked_local_only"

    # Domain default grants no provider authorization.
    assert domain_only.allowed_providers is None
    provider_not_allowlisted = resolve_effective_privacy_metadata(
        domain_only,
        PrivacyMetadata(
            policy=PrivacyPolicy.REMOTE_ALLOWED,
            allowed_processing_locations=(
                ProcessingLocation.LOCAL,
                ProcessingLocation.REMOTE,
            ),
            allowed_providers=("provider:alpha",),
            allow_remote=True,
        ),
    ).effective
    blocked_provider = evaluate_privacy_operation(
        provider_not_allowlisted,
        PrivacyOperation.TRANSMIT_TO_PROVIDER,
        PrivacyOperationContext(
            processing_location=ProcessingLocation.REMOTE,
            provider_id="provider:beta",
            at=NOW,
        ),
    )
    assert blocked_provider.allowed is False
    assert blocked_provider.reason_code == "provider_not_allowlisted"
    cp.checkpoint("07-remote-allowed-conditional")

    # ── Scenario D: remote approval is additive ───────────────────────────
    project = definitions["project"]
    project_remote = project_domain_privacy_metadata(
        project.privacy_policy, processing_location=ProcessingLocation.REMOTE
    )
    assert project_remote.requires_approval is True

    without_approval = evaluate_privacy_operation(
        project_remote,
        PrivacyOperation.PROCESS_REMOTE,
        PrivacyOperationContext(processing_location=ProcessingLocation.REMOTE, at=NOW),
    )
    assert without_approval.allowed is False
    assert without_approval.status is PrivacyDecisionStatus.APPROVAL_REQUIRED

    with_approval = evaluate_privacy_operation(
        project_remote,
        PrivacyOperation.PROCESS_REMOTE,
        PrivacyOperationContext(
            processing_location=ProcessingLocation.REMOTE,
            approval_granted=True,
            at=NOW,
        ),
    )
    assert with_approval.allowed is True

    # Approval never widens an independent privacy denial.
    local_only_with_approval = project_domain_privacy_metadata(
        definitions["health"].privacy_policy,
        processing_location=ProcessingLocation.REMOTE,
    )
    still_denied = evaluate_privacy_operation(
        local_only_with_approval,
        PrivacyOperation.PROCESS_REMOTE,
        PrivacyOperationContext(
            processing_location=ProcessingLocation.REMOTE,
            approval_granted=True,
            at=NOW,
        ),
    )
    assert still_denied.allowed is False
    assert still_denied.reason_code == "remote_blocked_local_only"
    cp.checkpoint("08-remote-approval-additive")

    # ── Scenario E: restrictive booleans and obligations survive ──────────
    permissive = PrivacyMetadata(
        policy=PrivacyPolicy.PREMIUM_ALLOWED,
        sensitivity=SensitivityLevel.PUBLIC,
        allowed_processing_locations=(
            ProcessingLocation.LOCAL,
            ProcessingLocation.REMOTE,
        ),
        allow_remote=True,
        allow_premium=True,
        allow_cache=True,
        allow_export=True,
    )
    restrictive = PrivacyMetadata(
        policy=PrivacyPolicy.REMOTE_ALLOWED,
        sensitivity=SensitivityLevel.INTERNAL,
        allowed_processing_locations=(
            ProcessingLocation.LOCAL,
            ProcessingLocation.REMOTE,
        ),
        allow_remote=True,
        allow_cache=False,
        allow_export=False,
        requires_redaction=True,
        requires_approval=True,
    )
    composed = resolve_effective_privacy_metadata(permissive, restrictive).effective

    assert composed.allow_cache is False
    assert composed.allow_export is False
    assert composed.requires_redaction is True
    assert composed.requires_approval is True

    cache_decision = evaluate_privacy_operation(
        composed, PrivacyOperation.CACHE, PrivacyOperationContext(at=NOW)
    )
    assert cache_decision.allowed is False
    assert cache_decision.reason_code == "cache_blocked"

    export_decision = evaluate_privacy_operation(
        composed, PrivacyOperation.EXPORT, PrivacyOperationContext(at=NOW)
    )
    assert export_decision.allowed is False
    assert export_decision.reason_code == "export_blocked"

    redaction_decision = evaluate_privacy_operation(
        composed,
        PrivacyOperation.PROCESS_LOCAL,
        PrivacyOperationContext(at=NOW),
    )
    assert redaction_decision.status is PrivacyDecisionStatus.REDACTION_REQUIRED
    cp.checkpoint("09-restrictions-survive")

    # ── Scenario F: provider restrictions survive composition ─────────────
    allowlist_a = PrivacyMetadata(
        policy=PrivacyPolicy.REMOTE_ALLOWED,
        allowed_processing_locations=(
            ProcessingLocation.LOCAL,
            ProcessingLocation.REMOTE,
        ),
        allowed_providers=("provider:alpha", "provider:beta"),
        allow_remote=True,
    )
    allowlist_b = PrivacyMetadata(
        policy=PrivacyPolicy.REMOTE_ALLOWED,
        allowed_processing_locations=(
            ProcessingLocation.LOCAL,
            ProcessingLocation.REMOTE,
        ),
        allowed_providers=("provider:beta", "provider:gamma"),
        prohibited_providers=("provider:delta",),
        allow_remote=True,
    )
    provider_effective = resolve_effective_privacy_metadata(
        allowlist_a, allowlist_b
    ).effective

    assert provider_effective.allowed_providers == ("provider:beta",)
    assert provider_effective.prohibited_providers == ("provider:delta",)

    delta_decision = evaluate_privacy_operation(
        provider_effective,
        PrivacyOperation.TRANSMIT_TO_PROVIDER,
        PrivacyOperationContext(
            processing_location=ProcessingLocation.REMOTE,
            provider_id="provider:delta",
            at=NOW,
        ),
    )
    assert delta_decision.allowed is False
    assert delta_decision.reason_code == "provider_prohibited"
    cp.checkpoint("10-provider-restrictions")

    # ── Scenario H: Phase 10.15 permission remains authoritative ──────────
    gate_denied = _permission_gate(
        _policy(
            "perm-policy-university-1",
            "domain:university",
            allow_cross_domain_access=False,
        ),
        _policy(
            "perm-policy-health-1",
            "domain:health",
            allow_inbound_cross_domain_access=True,
            allowed_source_domains=("domain:university",),
        ),
    )
    cross_request = CrossDomainPermissionRequest(
        request_id="cross-domain-request-050",
        source_domain="domain:university",
        target_domain="domain:health",
        reason="transfer canonical summary",
        actor_id="actor-050",
        session_id="session-050",
        sensitivity_level=SensitivityLevel.INTERNAL,
        requires_approval=False,
    )

    assert gate_denied.evaluate_cross_domain(cross_request).denied
    assert domain_only_decision.allowed is True

    gate_allowed = _permission_gate(
        _policy(
            "perm-policy-university-1",
            "domain:university",
            allow_cross_domain_access=True,
            allowed_target_domains=("domain:health",),
        ),
        _policy(
            "perm-policy-health-1",
            "domain:health",
            allow_inbound_cross_domain_access=True,
            allowed_source_domains=("domain:university",),
        ),
    )
    assert gate_allowed.evaluate_cross_domain(cross_request).allowed

    privacy_denied = evaluate_privacy_operation(
        health_effective,
        PrivacyOperation.PROCESS_REMOTE,
        PrivacyOperationContext(processing_location=ProcessingLocation.REMOTE, at=NOW),
    )
    assert privacy_denied.allowed is False
    cp.checkpoint("11-permission-authority")

    # ── Scenario K: trace evidence is reference-only ──────────────────────
    decision = privacy_denied
    reference = DomainTraceReference(
        ref_id=f"privacy-decision:{health_resource.id}",
        kind=DomainTraceReferenceKind.PRIVACY_DECISION,
        domain_id="domain:health",
    )
    inventory = DomainTraceReferenceInventory(
        references=(reference,),
        expected_primary_domain="domain:health",
        resolution_result_domains=DomainTraceDomainSelection(
            source_id="resolution-result:050", primary_domain="domain:health"
        ),
        composition_domains=DomainTraceDomainSelection(
            source_id="composition:050", primary_domain="domain:health"
        ),
    )

    assert inventory.references == (reference,)
    assert inventory.references[0].kind is DomainTraceReferenceKind.PRIVACY_DECISION

    serialized = repr(inventory.to_dict())
    assert decision.reason_code not in serialized
    for forbidden in ("allowed_providers", "prohibited_providers", "sensitivity"):
        assert forbidden not in serialized
    cp.checkpoint("12-trace-reference-only")

    assert cp.points == [
        "01-first-party-inventory",
        "02-declarative-round-trip",
        "03-real-registry",
        "04-general-no-default",
        "05-sensitive-domain-local",
        "06-local-only-cannot-widen",
        "07-remote-allowed-conditional",
        "08-remote-approval-additive",
        "09-restrictions-survive",
        "10-provider-restrictions",
        "11-permission-authority",
        "12-trace-reference-only",
    ]


def test_at_dp050_remote_allowed_group_is_remote_capable_by_default() -> None:
    """Oppositions and Languages share the conditional remote-allowed posture."""
    for builder in (
        build_oppositions_domain_definition,
        build_languages_domain_definition,
    ):
        definition = builder()
        policy = definition.privacy_policy
        assert policy is not None
        projected = project_domain_privacy_metadata(
            policy, processing_location=ProcessingLocation.REMOTE
        )
        assert projected.policy is PrivacyPolicy.REMOTE_ALLOWED
        assert projected.allow_remote is True
        assert projected.requires_approval is False
        assert projected.allowed_providers is None

        decision = evaluate_privacy_operation(
            projected,
            PrivacyOperation.PROCESS_REMOTE,
            PrivacyOperationContext(
                processing_location=ProcessingLocation.REMOTE, at=NOW
            ),
        )
        assert decision.allowed is True


def test_at_dp050_university_never_synthesizes_provider_authorization() -> None:
    """A remote-allowed Domain default is not a provider authorization."""
    definition = build_university_domain_definition()
    projected = project_domain_privacy_metadata(
        definition.privacy_policy, processing_location=ProcessingLocation.REMOTE
    )
    assert projected.allowed_providers is None

    explicit_allowlist = PrivacyMetadata(
        policy=PrivacyPolicy.REMOTE_ALLOWED,
        allowed_processing_locations=(
            ProcessingLocation.LOCAL,
            ProcessingLocation.REMOTE,
        ),
        allowed_providers=("provider:alpha",),
        allow_remote=True,
    )
    effective = resolve_effective_privacy_metadata(
        projected, explicit_allowlist
    ).effective

    decision = evaluate_privacy_operation(
        effective,
        PrivacyOperation.TRANSMIT_TO_PROVIDER,
        PrivacyOperationContext(
            processing_location=ProcessingLocation.REMOTE,
            provider_id="provider:beta",
            at=NOW,
        ),
    )
    assert decision.allowed is False
    assert decision.reason_code == "provider_not_allowlisted"


def test_at_dp050_every_declared_policy_projects_without_widening() -> None:
    """Projection is a pure adapter: it never widens the declared default."""
    for slug, builder in FIRST_PARTY_BUILDERS.items():
        definition = builder()
        policy = definition.privacy_policy
        if policy is None:
            assert slug == "general"
            continue

        local = project_domain_privacy_metadata(
            policy, processing_location=ProcessingLocation.LOCAL
        )
        remote = project_domain_privacy_metadata(
            policy, processing_location=ProcessingLocation.REMOTE
        )
        default = policy.default_privacy

        assert local == default, slug
        assert remote.policy is default.policy, slug
        assert remote.allow_remote is default.allow_remote, slug
        assert remote.allow_export is default.allow_export, slug
        assert remote.allow_cache is default.allow_cache, slug
        assert remote.allow_premium is default.allow_premium, slug
        assert remote.prohibited_providers == default.prohibited_providers, slug
        assert remote.sensitivity is default.sensitivity, slug


def test_at_dp050_capability_permission_is_not_granted_by_privacy() -> None:
    """An external-model capability denial blocks even when privacy allows."""
    from cmm.domains.permission_contracts import DomainPermissionRequest
    from cmm.domains.permission_evaluator import evaluate_domain_policy

    policy = _policy(
        "perm-policy-university-1", "domain:university", allow_external_models=False
    )
    request = DomainPermissionRequest(
        request_id="external-model-request-050",
        action=PermissionCapability.MODEL_EXTERNAL,
        domain_id="domain:university",
        actor_id="actor-050",
        session_id="session-050",
    )
    evaluation = evaluate_domain_policy(policy, request, now=NOW)
    assert evaluation.effect.value == "deny"

    definition = build_university_domain_definition()
    projected = project_domain_privacy_metadata(
        definition.privacy_policy, processing_location=ProcessingLocation.REMOTE
    )
    privacy_decision = evaluate_privacy_operation(
        projected,
        PrivacyOperation.TRANSMIT_TO_PROVIDER,
        PrivacyOperationContext(
            processing_location=ProcessingLocation.REMOTE,
            provider_id="provider:alpha",
            at=NOW,
        ),
    )
    assert privacy_decision.allowed is True


def test_at_dp050_general_definition_is_a_real_registry_member() -> None:
    registry = DomainRegistry()
    registered = registry.register(build_general_domain_definition())

    assert registered.privacy_policy is None
    assert registry.get("domain:general").privacy_policy is None
    assert registered.kind is DomainKind.CORE or registered.kind is DomainKind.PERSONAL
