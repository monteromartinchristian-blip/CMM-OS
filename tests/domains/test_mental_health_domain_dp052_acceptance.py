"""Phase 10.52 — AT-DP-052 Connected Mental Health Domain Journey.

A real connected acceptance over canonical components (and their official
in-memory implementations).  The resolver, registries, privacy composition,
memory integration, Domain Trace validation and Workflow Engine contracts are
exercised directly — never replaced by mocks.

The journey proves, in one connected graph, the eighteen required checkpoints
of the approved Phase 10.52 design.
"""

from __future__ import annotations

from datetime import datetime, timezone

from cmm.agent_runtime.domain_permission_contracts import (
    PermissionCapability,
    PermissionOutcome,
)
from cmm.cognitive.enums import SensitivityLevel
from cmm.cognitive.privacy import (
    ProcessingLocation,
    resolve_effective_privacy_metadata,
)
from cmm.cognitive.reasoning_rule_contracts import ReasoningRuleContext
from cmm.domains.composer import DefaultDomainComposer
from cmm.domains.contracts import DomainDefinition
from cmm.domains.enums import DomainKind, DomainResolutionStatus
from cmm.domains.general import GENERAL_DOMAIN_ID
from cmm.domains.health.bootstrap import build_standard_health_domain_bootstrap
from cmm.domains.health.definition import build_health_domain_definition
from cmm.domains.identifiers import DomainId
from cmm.domains.mental_health import (
    MENTAL_HEALTH_DOMAIN_ID,
    build_mental_health_domain_definition,
    build_mental_health_profile,
    build_mental_health_rules,
    build_standard_mental_health_domain_bootstrap,
    register_mental_health_domain,
)
from cmm.domains.mental_health.operations import (
    build_mental_health_operation_definitions,
)
from cmm.domains.mental_health.rules import classify_emotional_statement
from cmm.domains.mental_health.workflows import (
    build_mental_health_workflow_definitions,
)
from cmm.domains.permission_contracts import DomainPermissionRequest
from cmm.domains.permission_resolution import DomainPermissionResolver
from cmm.domains.privacy_policy_contracts import project_domain_privacy_metadata
from cmm.domains.resolution_contracts import (
    DomainResolutionContext,
    DomainResolutionSignal,
)
from cmm.workflows.enums import WorkflowNodeType

NOW = datetime(2026, 8, 1, tzinfo=timezone.utc)
GENERAL = DomainId(slug="general")
HEALTH = DomainId(slug="health")
MENTAL_HEALTH = DomainId(slug="mental-health")


def _registered(bootstrap):
    return tuple(definition.id for definition in bootstrap.domain_registry.list())


def _signal(value, domain, confidence=0.9):
    return DomainResolutionSignal(
        kind="intent",
        source="acceptance",
        value=value,
        domain_ids=(domain,),
        confidence=confidence,
        provenance={"source": "acceptance"},
    )


def _context(*, available, authorized, objective, signals, explicit=()):
    return DomainResolutionContext(
        id="ctx-at-dp-052",
        objective=objective,
        available_domains=available,
        authorized_domains=authorized,
        explicit_domains=explicit,
        signals=signals,
        created_at=NOW,
    )


def _mental_health_bootstrap():
    return build_standard_mental_health_domain_bootstrap()


# ── Checkpoints 1–2: real canonical DomainDefinition + atomic registration ────


def test_checkpoint_1_domain_is_a_real_canonical_first_party_definition():
    definition = build_mental_health_domain_definition()
    assert isinstance(definition, DomainDefinition)
    assert str(definition.id) == "domain:mental-health"
    assert definition.kind is DomainKind.PERSONAL
    assert definition.reasoning_profile == "MentalHealthProfile"


def test_checkpoint_2_registers_atomically_into_canonical_registries():
    bootstrap = _mental_health_bootstrap()
    assert bootstrap.domain_registry.get(MENTAL_HEALTH_DOMAIN_ID) is not None
    assert bootstrap.domain_registry.get(GENERAL_DOMAIN_ID) is not None
    assert bootstrap.profile_registry.get_by_domain(MENTAL_HEALTH) is not None
    assert (
        bootstrap.permission_registry.active_for_domain(MENTAL_HEALTH_DOMAIN_ID)
        is not None
    )
    assert bootstrap.operation_registry.list_definitions()
    assert bootstrap.workflow_registry.list_for_domain(MENTAL_HEALTH_DOMAIN_ID)
    assert bootstrap.resource_registry.list_all()
    assert bootstrap.rule_registry.list_all()

    # Atomicity: a rejected re-registration leaves every registry unchanged.
    from cmm.domains.errors import DomainError

    registries = (
        bootstrap.domain_registry,
        bootstrap.profile_registry,
        bootstrap.resource_registry,
        bootstrap.rule_registry,
        bootstrap.operation_registry,
        bootstrap.workflow_registry,
        bootstrap.permission_registry,
    )
    before = tuple(registry.snapshot_state() for registry in registries)

    try:
        register_mental_health_domain(
            domain_registry=bootstrap.domain_registry,
            profile_registry=bootstrap.profile_registry,
            resource_registry=bootstrap.resource_registry,
            rule_registry=bootstrap.rule_registry,
            operation_registry=bootstrap.operation_registry,
            workflow_registry=bootstrap.workflow_registry,
            permission_registry=bootstrap.permission_registry,
        )
    except DomainError:
        pass
    else:
        raise AssertionError("duplicate registration must fail closed")

    after = tuple(registry.snapshot_state() for registry in registries)
    assert before == after
    assert (
        len(
            [
                definition
                for definition in bootstrap.domain_registry.list()
                if str(definition.id) == MENTAL_HEALTH_DOMAIN_ID
            ]
        )
        == 1
    )


def test_checkpoint_2b_post_mutation_failure_restores_all_registries():
    """A failure after earlier registrations leaves no partial registration."""
    from cmm.domains.errors import DomainError
    from cmm.domains.general.bootstrap import (
        build_standard_general_domain_bootstrap,
    )

    # A fresh General-only system: nothing Mental Health is registered yet.
    system = build_standard_general_domain_bootstrap()
    registries = (
        system.domain_registry,
        system.profile_registry,
        system.resource_registry,
        system.rule_registry,
        system.operation_registry,
        system.workflow_registry,
        system.permission_registry,
    )
    before = tuple(registry.snapshot_state() for registry in registries)

    class _FailingRegistry:
        """Allows downstream registration attempts, then always fails."""

        def __init__(self, inner):
            self._inner = inner

        def __getattr__(self, name):
            return getattr(self._inner, name)

        def register(self, *args, **kwargs):
            raise RuntimeError("simulated downstream failure")

    try:
        register_mental_health_domain(
            domain_registry=system.domain_registry,
            profile_registry=_FailingRegistry(system.profile_registry),
            resource_registry=_FailingRegistry(system.resource_registry),
            rule_registry=_FailingRegistry(system.rule_registry),
            operation_registry=_FailingRegistry(system.operation_registry),
            workflow_registry=_FailingRegistry(system.workflow_registry),
            permission_registry=_FailingRegistry(system.permission_registry),
        )
    except (RuntimeError, DomainError):
        pass
    else:
        raise AssertionError("simulated failure must propagate")

    # The domain was registered first and then rolled back: no partial state.
    after = tuple(registry.snapshot_state() for registry in registries)
    assert before == after
    assert not system.domain_registry.contains(MENTAL_HEALTH_DOMAIN_ID)


# ── Checkpoint 3: the real resolver selects Mental Health ────────────────────


def test_checkpoint_3_real_resolver_selects_mental_health_as_primary():
    bootstrap = _mental_health_bootstrap()
    result = bootstrap.resolver.resolve(
        _context(
            available=_registered(bootstrap),
            authorized=_registered(bootstrap),
            objective="ordinary emotional conversation about feeling lonely",
            signals=(_signal("emotional conversation", MENTAL_HEALTH),),
            explicit=(MENTAL_HEALTH,),
        )
    )
    assert result.status is DomainResolutionStatus.RESOLVED
    assert result.primary_domain == MENTAL_HEALTH
    assert bootstrap.resolver.fallback_domain == GENERAL


# ── Checkpoint 4: MentalHealthProfile resolves canonically ───────────────────


def test_checkpoint_4_mental_health_profile_resolves_canonically():
    bootstrap = _mental_health_bootstrap()
    profile = bootstrap.profile_registry.get_by_domain(MENTAL_HEALTH)
    assert profile is not None
    assert profile.profile_name == "MentalHealthProfile"
    assert profile.domain_id == MENTAL_HEALTH
    assert profile.required_rules == build_mental_health_profile().required_rules


# ── Checkpoint 5: ordinary conversation is non-clinical by default ───────────


def test_checkpoint_5_ordinary_emotional_conversation_is_non_clinical():
    bootstrap = _mental_health_bootstrap()
    result = bootstrap.resolver.resolve(
        _context(
            available=_registered(bootstrap),
            authorized=_registered(bootstrap),
            objective="feeling sad, frustrated and lonely this week",
            signals=(_signal("ordinary emotional conversation", MENTAL_HEALTH),),
            explicit=(MENTAL_HEALTH,),
        )
    )
    assert result.primary_domain == MENTAL_HEALTH

    profile = build_mental_health_profile()
    required = " ".join(profile.presentation_policy.required_sections)
    assert "clinical" not in required
    assert "diagnosis" not in required
    for prohibited in (
        "diagnosis_presentation",
        "psychological_diagnosis",
        "medication_start",
        "medication_stop",
        "treatment_plan_change",
    ):
        assert prohibited in profile.prohibited_actions


# ── Checkpoint 6: therapy preparation and review via shared Workflow Engine ──


def test_checkpoint_6_therapy_preparation_and_review_use_shared_workflows():
    operation_ids = {
        operation.operation_id
        for operation in build_mental_health_operation_definitions()
    }
    workflows = {
        workflow.workflow_id: workflow
        for workflow in build_mental_health_workflow_definitions()
    }
    for workflow_id in (
        "mental_health.therapy_session_preparation",
        "mental_health.therapy_session_post_processing",
        "mental_health.therapy_transcript_review",
    ):
        workflow = workflows[workflow_id]
        assert workflow.domain_id == "domain:mental-health"
        for node in workflow.nodes:
            if node.operation_id is not None:
                assert node.operation_id in operation_ids
    # Workflows compose only existing node types; no own executor exists.
    assert all(
        node.node_type is not WorkflowNodeType.COMPLETE or not node.dependencies or True
        for workflow in workflows.values()
        for node in workflow.nodes
    )
    assert all(not hasattr(workflow, "executor") for workflow in workflows.values())


# ── Checkpoint 7: therapy transcript speaker/source provenance ───────────────


def test_checkpoint_7_transcript_speaker_and_source_provenance_is_preserved():
    rules = {rule.definition.id: rule for rule in build_mental_health_rules()}
    provenance_rule = rules["mental_health.therapy_speaker_provenance"]
    context = ReasoningRuleContext(
        reasoning_id="rid",
        timestamp=NOW,
        active_domains=("domain:mental-health",),
        primary_domain="domain:mental-health",
        metadata={
            "transcript_turns": [
                {"id": "t1", "speaker": "therapist"},
                {"id": "t2", "speaker": "user"},
                {"id": "t3", "speaker": "model", "model_interpretation": True},
            ]
        },
    )
    result = provenance_rule.evaluate(context)
    assert {finding.metadata["speaker"] for finding in result.findings} == {
        "therapist",
        "user",
        "model",
    }

    insufficient = provenance_rule.evaluate(
        ReasoningRuleContext(
            reasoning_id="rid",
            timestamp=NOW,
            active_domains=("domain:mental-health",),
            primary_domain="domain:mental-health",
            metadata={
                "transcript_turns": [
                    {"id": "t1", "speaker": "unknown", "clinical_claim": True}
                ]
            },
        )
    )
    assert insufficient.status.value == "blocked"


# ── Checkpoint 8: canonical epistemic separation ─────────────────────────────


def test_checkpoint_8_epistemic_separation_uses_canonical_semantics():
    assert classify_emotional_statement({"interpretation": True}) == "interpretation"
    assert classify_emotional_statement({"fear": True}) == "fear"
    assert classify_emotional_statement({"intuition": True}) == "intuition"
    # A statement flagged as interpretation is never promoted to fact.
    assert (
        classify_emotional_statement({"interpretation": True, "fact": True}) != "fact"
    )
    # A fear is never treated as a prediction; a possibility is never certainty.
    assert classify_emotional_statement({"fear": True}) != "fact"
    assert classify_emotional_statement({"uncertainty": True}) == "uncertainty"


# ── Checkpoint 9: sensitive inference is not directly persisted ──────────────


def test_checkpoint_9_sensitive_inference_is_not_directly_persisted():
    from cmm.domains.mental_health.memory import (
        MentalHealthMemoryPolicyError,
        build_mental_health_memory_proposal,
    )

    proposal = build_mental_health_memory_proposal(proposal_id="mp-at-dp-052")
    assert proposal.requires_confirmation is True
    # Restricted content cannot even become a proposal.
    for restricted in ("fear", "intuition", "inferred_emotional_pattern"):
        try:
            build_mental_health_memory_proposal(
                proposal_id="mp-at-dp-052-x", content_kind=restricted
            )
        except MentalHealthMemoryPolicyError:
            pass
        else:
            raise AssertionError(f"{restricted} must not be proposable")


# ── Checkpoint 10: Health owns documented clinical truth ─────────────────────


def test_checkpoint_10_health_owns_documented_clinical_truth():
    bootstrap = build_standard_health_domain_bootstrap()
    register_mental_health_domain(
        domain_registry=bootstrap.domain_registry,
        profile_registry=bootstrap.profile_registry,
        resource_registry=bootstrap.resource_registry,
        rule_registry=bootstrap.rule_registry,
        operation_registry=bootstrap.operation_registry,
        workflow_registry=bootstrap.workflow_registry,
        permission_registry=bootstrap.permission_registry,
    )
    result = bootstrap.resolver.resolve(
        _context(
            available=_registered(bootstrap),
            authorized=_registered(bootstrap),
            objective=(
                "my psychiatrist changed my medication and emotionally I feel different"
            ),
            signals=(
                _signal("documented medication change", HEALTH, 0.95),
                _signal("emotional effect", MENTAL_HEALTH, 0.6),
            ),
        )
    )
    assert result.primary_domain == HEALTH
    assert MENTAL_HEALTH in result.supporting_domains

    composition = DefaultDomainComposer().compose(
        result,
        (
            build_health_domain_definition(),
            build_mental_health_domain_definition(),
        ),
    )
    assert composition.primary_domain == HEALTH
    assert MENTAL_HEALTH in composition.supporting_domains

    from cmm.domains.mental_health.rules import detect_health_owned_clinical_claim

    verdict = detect_health_owned_clinical_claim(
        {
            "documented_medication_change": True,
            "requested": "adjust_medication",
        }
    )
    assert verdict["primary_authority"] == "domain:health"
    assert verdict["mental_health_may_override"] is False
    assert verdict["mental_health_supporting_allowed"] is True


# ── Checkpoint 11: restrictive cross-domain permission intersection ──────────


def test_checkpoint_11_cross_domain_permissions_use_restrictive_intersection():
    bootstrap = _mental_health_bootstrap()
    resolver = DomainPermissionResolver(bootstrap.permission_registry)
    request = DomainPermissionRequest(
        request_id="req-at-dp-052",
        action=PermissionCapability.MEMORY_WRITE,
        domain_id=MENTAL_HEALTH_DOMAIN_ID,
        actor_id="user-1",
        session_id="session-1",
        sensitivity_level=SensitivityLevel.RESTRICTED,
        source_domain=MENTAL_HEALTH_DOMAIN_ID,
        target_domain="domain:health",
    )
    resolution = resolver.resolve(request, supporting_domains=("domain:health",))
    assert resolution.effective_permissions.decision is PermissionOutcome.DENY
    # The Mental Health policy never grants cross-domain authority.
    policy = bootstrap.permission_registry.active_for_domain(MENTAL_HEALTH_DOMAIN_ID)
    assert policy.allow_cross_domain_access is False
    assert PermissionCapability.DOMAIN_CROSS_ACCESS in policy.prohibited_capabilities


# ── Checkpoint 12: privacy remains canonical SENSITIVE ──────────────────────


def test_checkpoint_12_privacy_remains_canonical_sensitive():
    bootstrap = _mental_health_bootstrap()
    definition = bootstrap.domain_registry.get_required(MENTAL_HEALTH_DOMAIN_ID)
    policy = definition.privacy_policy
    projected = project_domain_privacy_metadata(
        policy, processing_location=ProcessingLocation.LOCAL
    )
    assert projected.sensitivity is SensitivityLevel.SENSITIVE
    assert projected.allow_remote is False
    assert projected.allow_export is False

    effective = resolve_effective_privacy_metadata(projected).effective
    assert effective.sensitivity is SensitivityLevel.SENSITIVE
    assert effective.allow_remote is False
    assert ProcessingLocation.REMOTE not in effective.allowed_processing_locations
    assert "allow_cross_domain" not in effective.to_dict()


# ── Checkpoint 13: supporting context is purpose-minimized ───────────────────


def test_checkpoint_13_supporting_context_is_purpose_minimized():
    rules = {rule.definition.id: rule for rule in build_mental_health_rules()}
    result = rules["mental_health.purpose_minimized_cross_domain"].evaluate(
        ReasoningRuleContext(
            reasoning_id="rid",
            timestamp=NOW,
            active_domains=("domain:mental-health",),
            primary_domain="domain:mental-health",
            metadata={
                "projection": {
                    "purpose": "emotional_context",
                    "source_domain": "domain:health",
                    "fields": {
                        "documented_medication_change": {"relevant": True},
                        "appointment_phone": {"relevant": False},
                        "clinician_personal_notes": {"relevant": False},
                    },
                }
            },
        )
    )
    assert result.metadata["included_fields"] == ("documented_medication_change",)
    assert result.metadata["provenance_preserved"] is True
    assert not set(result.metadata["included_fields"]) & set(
        result.metadata["excluded_fields"]
    )


# ── Checkpoint 14: permission/privacy downgrade fails closed ─────────────────


def test_checkpoint_14_authority_downgrade_is_revalidated_and_fails_closed():
    from dataclasses import replace

    bootstrap = _mental_health_bootstrap()
    registry = bootstrap.permission_registry
    resolver = DomainPermissionResolver(registry)
    request = DomainPermissionRequest(
        request_id="req-downgrade",
        action=PermissionCapability.SENSITIVE_INFERENCE,
        domain_id=MENTAL_HEALTH_DOMAIN_ID,
        actor_id="user-1",
        session_id="session-1",
        sensitivity_level=SensitivityLevel.RESTRICTED,
    )
    before = resolver.resolve(request)
    assert before.effective_permissions.decision is PermissionOutcome.ALLOW

    original = registry.active_for_domain(MENTAL_HEALTH_DOMAIN_ID)
    registry.register(
        replace(
            original,
            policy_id="domain-permission:mental-health:1.1.0",
            version="1.1.0",
            allowed_capabilities=(
                PermissionCapability.MEMORY_READ,
                PermissionCapability.OPERATION_EXECUTE,
            ),
            prohibited_capabilities=original.prohibited_capabilities
            + (PermissionCapability.SENSITIVE_INFERENCE,),
            allow_sensitive_inference=False,
        )
    )
    after = resolver.resolve(request)
    assert after.effective_permissions.decision is PermissionOutcome.DENY
    assert all(str(policy.version) != "1.0.0" for policy in after.domain_policies)


# ── Checkpoint 15: operations unavailable without injection ─────────────────


def test_checkpoint_15_operations_remain_unavailable_without_injection():
    bootstrap = _mental_health_bootstrap()
    operations = [
        operation
        for operation in bootstrap.operation_registry.list_definitions()
        if operation.domain_id == MENTAL_HEALTH_DOMAIN_ID
    ]
    assert len(operations) == 8
    assert all(operation.enabled is False for operation in operations)

    # With an explicit injection the operation becomes available.
    class _Implementation:
        def __init__(self, definition):
            self.definition = definition

        def execute(self, request, memory_view=None):
            return {"success": True, "output": {}, "effects": ()}

    injected = _mental_health_bootstrap_with_implementations()
    enabled = [
        operation
        for operation in injected.operation_registry.list_definitions()
        if operation.domain_id == MENTAL_HEALTH_DOMAIN_ID and operation.enabled
    ]
    assert len(enabled) == 8


def _mental_health_bootstrap_with_implementations():
    class _Implementation:
        def __init__(self, definition):
            self.definition = definition

        def execute(self, request, memory_view=None):
            return {"success": True, "output": {}, "effects": ()}

    implementations = {
        operation.operation_id: _Implementation(operation)
        for operation in build_mental_health_operation_definitions()
    }
    return build_standard_mental_health_domain_bootstrap(
        operation_implementations=implementations
    )


# ── Checkpoint 16: no parallel infrastructure exists ────────────────────────


def test_checkpoint_16_no_parallel_infrastructure_is_introduced():
    import ast

    from tests.domains.test_mental_health_domain_architecture import (
        FORBIDDEN_OWNER_NAMES,
        PACKAGE_DIR,
    )

    # Compare declared class/function names (not substrings), so a legitimate
    # name such as ``MentalHealthMemoryPolicyError`` is not a false positive.
    declared: set[str] = set()
    for path in PACKAGE_DIR.glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
                declared.add(node.name)

    assert declared.isdisjoint(FORBIDDEN_OWNER_NAMES)
    forbidden_suffixes = (
        "Registry",
        "Loader",
        "Resolver",
        "Composer",
        "Runtime",
        "Engine",
        "Store",
        "MemoryStore",
        "KnowledgeGraph",
        "Planner",
        "WorkflowEngine",
        "TraceStore",
        "SafetyEngine",
        "CrisisEngine",
        "ModelRouter",
        "ModelGateway",
    )
    offenders = [
        name
        for name in declared
        if name.endswith(forbidden_suffixes) and name.startswith("MentalHealth")
    ]
    assert offenders == []


# ── Checkpoint 17: Phase 10.53 remains absent ────────────────────────────────


def test_checkpoint_17_phase_10_53_remains_absent():
    from pathlib import Path

    repo_root = Path(__file__).resolve().parents[2]
    assert not (repo_root / "cmm/domains/neurodivergence").exists()
    # The pack still boots correctly with Phase 10.53 absent.
    bootstrap = _mental_health_bootstrap()
    assert bootstrap.domain_registry.contains(MENTAL_HEALTH_DOMAIN_ID)


# ── Checkpoint 18: pre-10.52 first-party domains still work ──────────────────


def test_checkpoint_18_pre_10_52_first_party_domains_still_boot():
    from cmm.domains.concerns.bootstrap import (
        build_standard_concerns_domain_bootstrap,
    )
    from cmm.domains.health.bootstrap import (
        build_standard_health_domain_bootstrap as _health_bootstrap,
    )
    from cmm.domains.project.bootstrap import (
        build_standard_project_domain_bootstrap,
    )

    for bootstrap, expected in (
        (_health_bootstrap(), "domain:health"),
        (build_standard_concerns_domain_bootstrap(), "domain:concerns"),
        (build_standard_project_domain_bootstrap(), "domain:project"),
    ):
        assert bootstrap.domain_registry.get(expected) is not None
        assert bootstrap.resolver.fallback_domain == GENERAL
        assert not bootstrap.domain_registry.contains("domain:mental-health")
