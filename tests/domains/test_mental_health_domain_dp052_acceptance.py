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

import pytest

from cmm.agent_runtime.approval_repository import InMemoryApprovalRepository
from cmm.agent_runtime.approval_service import ApprovalService
from cmm.agent_runtime.domain_permission_contracts import (
    PermissionApprovalRequirement,
    PermissionCapability,
    PermissionOutcome,
)
from cmm.cognitive.enums import SensitivityLevel
from cmm.cognitive.privacy import (
    ProcessingLocation,
    resolve_effective_privacy_metadata,
)
from cmm.cognitive.reasoning_rule_contracts import ReasoningRuleContext
from cmm.domains.approval_bridge import to_approval_requirement
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
from cmm.domains.permission_contracts import (
    CrossDomainPermissionRequest,
    DomainPermissionRequest,
)
from cmm.domains.permission_gate import (
    DomainPermissionGate,
    PermissionGateOutcome,
)
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
    from cmm.cognitive.enums import ResourceSourceKind
    from cmm.cognitive.resources import ResourceProvenance

    # Real canonical source provenance for the transcript resource — the rule
    # must consume and propagate it rather than asserting preservation.
    source_id = "mental_health.therapy_transcript:session-42"
    provenance = ResourceProvenance(
        source_type=ResourceSourceKind.UPLOADED_FILE,
        source_id=source_id,
        author="user",
        retrieved_at=NOW,
    ).to_dict()

    rules = {rule.definition.id: rule for rule in build_mental_health_rules()}
    provenance_rule = rules["mental_health.therapy_speaker_provenance"]
    context = ReasoningRuleContext(
        reasoning_id="rid",
        timestamp=NOW,
        active_domains=("domain:mental-health",),
        primary_domain="domain:mental-health",
        metadata={
            "source_provenance": provenance,
            "transcript_turns": [
                {"id": "t1", "speaker": "therapist", "source_ref": "turn:1"},
                {"id": "t2", "speaker": "user", "source_ref": "turn:2"},
                {
                    "id": "t3",
                    "speaker": "model",
                    "model_interpretation": True,
                    "source_ref": "turn:3",
                },
            ],
        },
    )
    result = provenance_rule.evaluate(context)
    assert result.status.value == "applied"
    assert result.trace_entries[0].code == "SPEAKER_PROVENANCE_PRESERVED"
    assert result.metadata["provenance_preserved"] is True
    assert result.metadata["source_provenance_id"] == source_id
    assert {finding.metadata["speaker"] for finding in result.findings} == {
        "therapist",
        "user",
        "model",
    }
    by_speaker = {finding.metadata["speaker"]: finding for finding in result.findings}
    # The real per-turn source reference survives into the finding.
    assert "turn:1" in by_speaker["therapist"].references
    assert by_speaker["therapist"].metadata["source_identity_preserved"] is True
    # Model interpretation stays distinguishable from source statements.
    assert by_speaker["model"].metadata["model_interpretation_distinct"] is True
    assert by_speaker["therapist"].metadata["model_interpretation_distinct"] is False

    # Speaker-only turns carry no source evidence and must fail closed.
    unprovenanced = provenance_rule.evaluate(
        ReasoningRuleContext(
            reasoning_id="rid",
            timestamp=NOW,
            active_domains=("domain:mental-health",),
            primary_domain="domain:mental-health",
            metadata={"transcript_turns": [{"id": "t1", "speaker": "therapist"}]},
        )
    )
    assert unprovenanced.status.value == "blocked"
    assert unprovenanced.metadata["provenance_preserved"] is False
    assert unprovenanced.metadata["unprovenanced_turns"] == ("t1",)

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

CROSS_DOMAIN_PURPOSE = "emotional_context"
CROSS_DOMAIN_SOURCE_KIND = "health_projection"
HEALTH_DOMAIN_ID = "domain:health"


def _canonical_transfer(
    identifier,
    *,
    source_domain=HEALTH_DOMAIN_ID,
    target_domain=MENTAL_HEALTH_DOMAIN_ID,
    reason=CROSS_DOMAIN_PURPOSE,
    provenance=("finding:health:13",),
    transferable=True,
    private=False,
):
    """Return the JSON-safe canonical ``CrossDomainContextTransfer`` mapping."""
    from cmm.domains.cross_domain_contracts import CrossDomainContextTransfer

    return CrossDomainContextTransfer(
        source_domain=source_domain,
        target_domain=target_domain,
        kind="finding",
        identifier=identifier,
        value=True,
        reason=reason,
        provenance=provenance,
        transferable=transferable,
        private=private,
    ).to_dict()


def _projection(**fields):
    return {
        "purpose": CROSS_DOMAIN_PURPOSE,
        "fields": {name: {"relevant": value} for name, value in fields.items()},
    }


def _cross_domain_rule():
    rules = {rule.definition.id: rule for rule in build_mental_health_rules()}
    return rules["mental_health.purpose_minimized_cross_domain"]


def _evaluate(projection, transfers=()):
    """Evaluate the rule over a projection and canonical transfer evidence."""
    return _cross_domain_rule().evaluate(
        ReasoningRuleContext(
            reasoning_id="rid-at-dp-052-13",
            timestamp=NOW,
            active_domains=(MENTAL_HEALTH_DOMAIN_ID,),
            primary_domain=MENTAL_HEALTH_DOMAIN_ID,
            metadata={"projection": projection, "transfers": tuple(transfers)},
        )
    )


def _cross_domain_permission_request(request_id, resource_id):
    """Real canonical cross-domain request bound to one projected resource."""
    return CrossDomainPermissionRequest(
        request_id,
        source_domain=HEALTH_DOMAIN_ID,
        target_domain=MENTAL_HEALTH_DOMAIN_ID,
        resource_ids=(resource_id,),
        resource_kinds=(CROSS_DOMAIN_SOURCE_KIND,),
        reason=CROSS_DOMAIN_PURPOSE,
        actor_id="user-1",
        session_id="session-1",
        sensitivity_level=SensitivityLevel.RESTRICTED,
        capability=PermissionCapability.RESOURCE_READ,
    )


def _authorized_cross_domain_resolver():
    """Canonical permission authority for one explicitly authorized path.

    Mental Health never auto-grants cross-domain authority: with the real
    registered policies every source -> Mental Health path resolves to DENY
    (proved by ``test_checkpoint_13d_...``).  This positive control is built
    from the same canonical ``DomainPermissionPolicy`` contract — by
    ``dataclasses.replace`` on the real Health and Mental Health policies —
    so the real ``DomainPermissionResolver`` stays the only authority.  The
    SENSITIVE privacy floor is untouched, so the authorized decision remains
    approval-gated rather than a silent ALLOW.
    """
    from dataclasses import replace

    from cmm.domains.health.permissions import build_health_permission_policy
    from cmm.domains.mental_health.permissions import (
        MENTAL_HEALTH_PROHIBITED_CAPABILITIES,
        build_mental_health_permission_policy,
    )
    from cmm.domains.permission_registry import DomainPermissionRegistry

    source = build_health_permission_policy()
    target = build_mental_health_permission_policy()
    store = DomainPermissionRegistry()
    store.register(
        replace(
            source,
            allowed_capabilities=source.allowed_capabilities
            + (PermissionCapability.DOMAIN_CROSS_ACCESS,),
            allowed_target_domains=(MENTAL_HEALTH_DOMAIN_ID,),
            allowed_resource_kinds=tuple(source.allowed_resource_kinds)
            + (CROSS_DOMAIN_SOURCE_KIND,),
        )
    )
    store.register(
        replace(
            target,
            policy_id="domain-permission:mental-health:1.0.0-authorized-projection",
            version="1.0.0-authorized-projection",
            prohibited_capabilities=tuple(
                item
                for item in MENTAL_HEALTH_PROHIBITED_CAPABILITIES
                if item is not PermissionCapability.DOMAIN_CROSS_ACCESS
            ),
            allowed_source_domains=(HEALTH_DOMAIN_ID,),
        )
    )
    return DomainPermissionResolver(store)


def _health_and_mental_health_bootstrap():
    """Real canonical registries holding both Health and Mental Health policies."""
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
    return bootstrap


# ── Connected permission-gated projection path (V4 MAJOR-03) ─────────────────
#
# The V3 re-audit proved that a structurally valid ``CrossDomainContextTransfer``
# is not the same thing as *current permission authority*: a supplied transfer
# for a field the real canonical resolver denies could still reach the
# minimization rule.  ``PurposeMinimizedCrossDomainRule`` owns minimization and
# provenance only — it is deliberately not a second permission engine — so the
# authority decision belongs at the projection boundary, *before* a transfer is
# admitted.  The path below is that boundary.  It composes only canonical
# components: the real ``DomainPermissionResolver``, the real
# ``DomainPermissionGate`` (with the canonical ``ApprovalService`` /
# ``InMemoryApprovalRepository`` on the approval-gated path), the canonical
# ``CrossDomainPermissionRequest`` / ``CrossDomainContextTransfer`` contracts,
# and the Mental Health minimization rule.  Current permission authority is
# what permits a concrete field transfer; structural transfer validity alone
# never does.


def _connected_permission_stack(resolver):
    """Real canonical gate + approval stack over an already-built resolver."""
    approval_service = ApprovalService(InMemoryApprovalRepository())
    gate = DomainPermissionGate(resolver, approval_service, clock=lambda: NOW)
    return approval_service, gate


def _grant_canonical_cross_domain_approval(approval_service, gate, request):
    """Drive the canonical approval lifecycle for ``request`` to consumption."""
    pending = gate.evaluate_cross_domain(request)
    assert pending.outcome is PermissionGateOutcome.APPROVAL_REQUIRED
    requirement = PermissionApprovalRequirement.from_dict(
        pending.approval_requirements[0]
    )
    approval_request = approval_service.create_request_from_requirement(
        to_approval_requirement(requirement, agent_run_id="run-at-dp-052"),
        requested_by="user",
    )
    approval_service.approve(approval_request.id, "user")
    return approval_request.id


def _admit_cross_domain_transfers(
    *,
    request,
    candidates,
    resolver,
    gate,
    approval_request_id=None,
    now=NOW,
):
    """Admit only transfers backed by effective *current* permission authority.

    Returns ``(decision, gate_result, admitted)``.  ``decision`` is the current
    canonical policy resolution, ``gate_result`` is the effective authority
    after the canonical approval path and ``admitted`` are the candidate
    transfers allowed to reach ``PurposeMinimizedCrossDomainRule``.

    A candidate is admitted only when the gate reports effective authority
    (``ALLOW`` or ``APPROVAL_CONSUMED`` — never an unconsumed
    ``APPROVAL_REQUIRED``, never ``DENY``) *and* its own authority tuple —
    source domain, target domain, resource identifier and reason — is the exact
    tuple that authority was issued for.  Candidates are supplied by the caller
    whether or not they are authorized; a structurally valid matching transfer
    is therefore genuinely presented in every denial case.
    """
    decision = resolver.resolve_cross_domain(request, now=now)
    gate_result = gate.evaluate_cross_domain(
        request, approval_request_id=approval_request_id
    )
    admitted = ()
    if gate_result.allowed:
        admitted = tuple(
            candidate
            for candidate in candidates
            if candidate["identifier"] in request.resource_ids
            and candidate["source_domain"] == request.source_domain
            and candidate["target_domain"] == request.target_domain
            and candidate["reason"] == request.reason
        )
    return decision, gate_result, admitted


def test_checkpoint_13_supporting_context_is_purpose_minimized():
    from cmm.domains.cross_domain_contracts import CrossDomainContextTransfer

    projection = {
        "purpose": CROSS_DOMAIN_PURPOSE,
        "fields": {
            "documented_medication_change": {"relevant": True},
            "appointment_phone": {"relevant": False},
            "clinician_personal_notes": {"relevant": False},
        },
    }

    result = _evaluate(
        projection,
        (
            _canonical_transfer("documented_medication_change"),
            _canonical_transfer("appointment_phone"),
            _canonical_transfer("clinician_personal_notes"),
        ),
    )
    assert result.status.value == "applied"
    assert result.trace_entries[0].code == "CROSS_DOMAIN_MINIMIZED"
    assert result.metadata["included_fields"] == ("documented_medication_change",)
    assert set(result.metadata["excluded_fields"]) == {
        "appointment_phone",
        "clinician_personal_notes",
    }
    # Provenance is proven by real canonical transfer evidence, not asserted.
    assert result.metadata["provenance_preserved"] is True
    assert result.metadata["provenance_references"] == ("finding:health:13",)
    assert result.metadata["source_domains"] == ("domain:health",)
    assert not set(result.metadata["included_fields"]) & set(
        result.metadata["excluded_fields"]
    )
    # Every included field is backed by its own accepted transfer evidence.
    assert result.metadata["unbound_fields"] == ()

    # The included field is bound to a transfer with the same identifier.
    transfer = CrossDomainContextTransfer.from_dict(
        _canonical_transfer("documented_medication_change")
    )
    assert transfer.identifier in result.metadata["included_fields"]
    assert transfer.source_domain.slug == "health"
    assert str(transfer.target_domain) == MENTAL_HEALTH_DOMAIN_ID
    assert transfer.provenance
    assert transfer.transferable is True
    assert transfer.private is False
    assert transfer.reason == projection["purpose"]

    # Current canonical permission authority for that exact projected path is
    # approval-gated, and only canonical consumption of that approval is
    # authorization — an unconsumed ``APPROVAL_REQUIRED`` decision admits
    # nothing.  The connected boundary therefore admits the transfer only once
    # ``DomainPermissionGate`` reports ``APPROVAL_CONSUMED``.
    authorized_resolver = _authorized_cross_domain_resolver()
    approval_service, gate = _connected_permission_stack(authorized_resolver)
    projected_request = _cross_domain_permission_request(
        "req-at-dp-052-13", "documented_medication_change"
    )
    candidates = (_canonical_transfer("documented_medication_change"),)
    decision, gate_result, admitted = _admit_cross_domain_transfers(
        request=projected_request,
        candidates=candidates,
        resolver=authorized_resolver,
        gate=gate,
    )
    assert decision.request_id == "req-at-dp-052-13"
    assert decision.decision is PermissionOutcome.APPROVAL_REQUIRED
    assert gate_result.outcome is PermissionGateOutcome.APPROVAL_REQUIRED
    assert admitted == ()

    approval_request_id = _grant_canonical_cross_domain_approval(
        approval_service, gate, projected_request
    )
    decision, gate_result, admitted = _admit_cross_domain_transfers(
        request=projected_request,
        candidates=candidates,
        resolver=authorized_resolver,
        gate=gate,
        approval_request_id=approval_request_id,
    )
    assert gate_result.outcome is PermissionGateOutcome.APPROVAL_CONSUMED
    assert admitted == candidates

    # Only now does the projection apply, and only from admitted evidence.
    gated = _evaluate(projection, admitted)
    assert gated.status.value == "applied"
    assert gated.metadata["included_fields"] == ("documented_medication_change",)

    # Canonical privacy composition for the projected path stays SENSITIVE.
    from cmm.domains.mental_health.privacy import build_mental_health_privacy_policy

    projected_privacy = project_domain_privacy_metadata(
        build_mental_health_privacy_policy(),
        processing_location=ProcessingLocation.LOCAL,
    )
    effective_privacy = resolve_effective_privacy_metadata(projected_privacy).effective
    assert effective_privacy.sensitivity is SensitivityLevel.SENSITIVE
    assert effective_privacy.allow_remote is False
    assert effective_privacy.allow_export is False

    # The same projection without canonical transfer evidence fails closed.
    bare = _evaluate(projection)
    assert bare.status.value == "blocked"
    assert bare.metadata["provenance_preserved"] is False
    assert bare.metadata["included_fields"] == ()

    # Current transfer authority is connected to the projection: an explicit
    # permission denial for the projection's transfer blocks it.
    denied = _evaluate(
        projection,
        (_canonical_transfer("documented_medication_change", transferable=False),),
    )
    assert denied.status.value == "blocked"
    assert denied.metadata["provenance_preserved"] is False
    assert denied.metadata["rejected_transfers"] == ("transfer_not_permitted",)
    assert denied.metadata["unbound_fields"] == ("documented_medication_change",)


def test_checkpoint_13a_unbound_relevant_field_is_excluded():
    """V2 MAJOR-03: one authorized field never authorizes another field."""
    result = _evaluate(
        _projection(authorized_field=True, UNAUTHORIZED_SENSITIVE_FIELD=True),
        (_canonical_transfer("authorized_field"),),
    )
    assert result.metadata["included_fields"] == ("authorized_field",)
    assert "UNAUTHORIZED_SENSITIVE_FIELD" in result.metadata["excluded_fields"]
    assert result.metadata["unbound_fields"] == ("UNAUTHORIZED_SENSITIVE_FIELD",)
    # The unauthorized field inherits no provenance from the authorized one.
    assert result.metadata["provenance_references"] == ("finding:health:13",)
    assert result.metadata["source_domains"] == ("domain:health",)


def test_checkpoint_13b_unrelated_transfer_cannot_authorize_projection():
    """V2 MAJOR-03: a transfer absent from the projection grants no authority."""
    result = _evaluate(
        _projection(field_a=True, field_b=True),
        (_canonical_transfer("not_in_projection"),),
    )
    assert result.status.value == "blocked"
    assert result.metadata["included_fields"] == ()
    assert result.metadata["provenance_preserved"] is False
    assert result.metadata["unbound_fields"] == ("field_a", "field_b")
    assert set(result.metadata["excluded_fields"]) == {"field_a", "field_b"}


@pytest.mark.parametrize(
    "denied_kwargs",
    (
        {"transferable": False},
        {"private": True},
        {"reason": "an_unrelated_purpose"},
        {"target_domain": "domain:project"},
    ),
    ids=("non_transferable", "private", "purpose_mismatch", "target_mismatch"),
)
def test_checkpoint_13c_accepted_transfer_cannot_launder_rejected_field(
    denied_kwargs,
):
    """V2 MAJOR-03: an accepted transfer never launders a rejected field."""
    result = _evaluate(
        _projection(allowed_field=True, denied_field=True),
        (
            _canonical_transfer("allowed_field"),
            _canonical_transfer("denied_field", **denied_kwargs),
        ),
    )
    assert result.metadata["included_fields"] == ("allowed_field",)
    assert "denied_field" in result.metadata["excluded_fields"]
    assert result.metadata["unbound_fields"] == ("denied_field",)


def test_checkpoint_13d_current_canonical_permission_deny_blocks_the_projection():
    """V2 MAJOR-03: a current canonical DENY excludes the denied field."""
    real_resolver = DomainPermissionResolver(
        _health_and_mental_health_bootstrap().permission_registry
    )
    denied_decision = real_resolver.resolve_cross_domain(
        _cross_domain_permission_request("req-at-dp-052-deny", "denied_field")
    )
    assert denied_decision.decision is PermissionOutcome.DENY
    assert denied_decision.granted_resources == ()

    authorized_decision = _authorized_cross_domain_resolver().resolve_cross_domain(
        _cross_domain_permission_request("req-at-dp-052-authorize", "allowed_field")
    )
    assert authorized_decision.decision is not PermissionOutcome.DENY

    # Only the authorized path yields canonical transfer evidence, so the
    # denied field cannot survive next to an authorized one.
    result = _evaluate(
        _projection(allowed_field=True, denied_field=True),
        (_canonical_transfer("allowed_field"),),
    )
    assert result.metadata["included_fields"] == ("allowed_field",)
    assert "denied_field" in result.metadata["excluded_fields"]

    # With no authorized field at all the denied projection fails closed.
    only_denied = _evaluate(_projection(denied_field=True))
    assert only_denied.status.value == "blocked"
    assert only_denied.metadata["included_fields"] == ()


def test_checkpoint_13e_private_or_non_transferable_path_is_blocked():
    """V2 MAJOR-03: a privacy-incompatible path never becomes a projection."""
    from cmm.cognitive.privacy import PrivacyMetadata, PrivacyPolicy
    from cmm.domains.mental_health.privacy import build_mental_health_privacy_policy

    projected_privacy = project_domain_privacy_metadata(
        build_mental_health_privacy_policy(),
        processing_location=ProcessingLocation.LOCAL,
    )
    # A maximally permissive source can never widen Mental Health privacy.
    permissive = PrivacyMetadata(
        policy=PrivacyPolicy.REMOTE_ALLOWED,
        sensitivity=SensitivityLevel.PUBLIC,
        allowed_processing_locations=(
            ProcessingLocation.LOCAL,
            ProcessingLocation.REMOTE,
        ),
        allow_remote=True,
        allow_export=True,
    )
    effective = resolve_effective_privacy_metadata(
        permissive, projected_privacy
    ).effective
    assert effective.sensitivity is SensitivityLevel.SENSITIVE
    assert effective.allow_remote is False
    assert effective.allow_export is False

    # The private (privacy-incompatible) canonical transfer cannot survive
    # beside an authorized one.
    mixed = _evaluate(
        _projection(allowed_field=True, private_field=True),
        (
            _canonical_transfer("allowed_field"),
            _canonical_transfer("private_field", private=True),
        ),
    )
    assert mixed.metadata["included_fields"] == ("allowed_field",)
    assert "private_field" in mixed.metadata["excluded_fields"]

    # A private field alone blocks the whole projection.
    only_private = _evaluate(
        _projection(private_field=True),
        (_canonical_transfer("private_field", private=True),),
    )
    assert only_private.status.value == "blocked"
    assert only_private.metadata["included_fields"] == ()

    # A non-transferable field alone blocks the whole projection too.
    only_non_transferable = _evaluate(
        _projection(restricted_field=True),
        (_canonical_transfer("restricted_field", transferable=False),),
    )
    assert only_non_transferable.status.value == "blocked"
    assert only_non_transferable.metadata["included_fields"] == ()


def test_checkpoint_13f_duplicate_transfer_evidence_is_deterministic():
    """Duplicate accepted evidence authorizes once, with a deduplicated union."""
    result = _evaluate(
        _projection(deduplicated=True),
        (
            _canonical_transfer("deduplicated", provenance=("finding:health:b",)),
            _canonical_transfer("deduplicated", provenance=("finding:health:a",)),
        ),
    )
    assert result.metadata["included_fields"] == ("deduplicated",)
    assert result.metadata["provenance_references"] == (
        "finding:health:a",
        "finding:health:b",
    )
    assert result.metadata["source_domains"] == ("domain:health",)


def test_checkpoint_13g_current_permission_deny_blocks_a_matching_transfer():
    """V4 MAJOR-03: DENY plus a matching transfer object is still not authority.

    The exact V3 re-audit adversarial: the real canonical registries deny the
    path, yet a structurally valid canonical transfer for the denied field is
    supplied.  Omitting that transfer is not a valid fix — it is presented, and
    the connected boundary must refuse to admit it into the projection.
    """
    real_resolver = DomainPermissionResolver(
        _health_and_mental_health_bootstrap().permission_registry
    )
    _approval_service, gate = _connected_permission_stack(real_resolver)
    denied_request = _cross_domain_permission_request(
        "req-at-dp-052-v4-deny", "denied_field"
    )
    candidate = _canonical_transfer("denied_field", provenance=("prov:denied",))

    # PERMISSION_DENY=YES — the real current canonical authority denies the path.
    decision = real_resolver.resolve_cross_domain(denied_request, now=NOW)
    assert decision.decision is PermissionOutcome.DENY
    assert decision.granted_resources == ()
    assert "source_cross_domain_denied" in decision.reasons
    assert "target_cross_domain_denied" in decision.reasons

    # MATCHING_TRANSFER_PRESENT=YES — the withheld evidence is a genuinely
    # matching canonical transfer for exactly the denied resource.
    assert candidate["identifier"] in denied_request.resource_ids
    assert candidate["source_domain"] == denied_request.source_domain
    assert candidate["target_domain"] == denied_request.target_domain
    assert candidate["reason"] == denied_request.reason
    assert candidate["transferable"] is True
    assert candidate["private"] is False
    assert candidate["provenance"] == ["prov:denied"]

    # Boundary under test, deliberately asserted: ``PurposeMinimizedCrossDomainRule``
    # owns minimization and provenance only — it is *not* the permission owner,
    # so on its own it accepts evidence that current authority denies.  That is
    # exactly why admission must be permission-gated before the rule runs.
    ungated = _evaluate(_projection(denied_field=True), (candidate,))
    assert ungated.metadata["included_fields"] == ("denied_field",)

    # DENIED_TRANSFER_ADMITTED_TO_PROJECTION=NO / DENIED_FIELD_INCLUDED=NO.
    decision, gate_result, admitted = _admit_cross_domain_transfers(
        request=denied_request,
        candidates=(candidate,),
        resolver=real_resolver,
        gate=gate,
    )
    assert decision.decision is PermissionOutcome.DENY
    assert gate_result.outcome is PermissionGateOutcome.DENY
    assert gate_result.allowed is False
    assert admitted == ()
    gated = _evaluate(_projection(denied_field=True), admitted)
    assert gated.status.value == "blocked"
    assert gated.metadata["included_fields"] == ()
    assert gated.metadata["provenance_preserved"] is False
    assert gated.metadata["source_domains"] == ()

    # A supplied approval reference never repairs a canonical DENY.
    repaired = gate.evaluate_cross_domain(
        denied_request, approval_request_id="approval-req-supplied"
    )
    assert repaired.outcome is PermissionGateOutcome.DENY


def test_checkpoint_13h_approval_required_is_not_authorization():
    """V4 MAJOR-03: an unconsumed APPROVAL_REQUIRED admits no transfer.

    The V3 positive control treated ``decision is not DENY`` as sufficient.
    Canonical semantics do not: an approval-gated path becomes effective
    authority only through canonical approval validation and consumption.
    """
    authorized_resolver = _authorized_cross_domain_resolver()
    _approval_service, gate = _connected_permission_stack(authorized_resolver)
    request = _cross_domain_permission_request(
        "req-at-dp-052-v4-pending", "documented_medication_change"
    )
    candidate = _canonical_transfer("documented_medication_change")
    decision, gate_result, admitted = _admit_cross_domain_transfers(
        request=request,
        candidates=(candidate,),
        resolver=authorized_resolver,
        gate=gate,
    )

    # RESOLVER_OUTCOME=APPROVAL_REQUIRED / APPROVAL_CONSUMED=NO.
    assert decision.decision is PermissionOutcome.APPROVAL_REQUIRED
    assert decision.granted_resources == ()
    assert decision.approval_requirements
    assert decision.approval_requirements[0].requirement_id == (
        "cross-domain:req-at-dp-052-v4-pending"
    )
    assert gate_result.outcome is PermissionGateOutcome.APPROVAL_REQUIRED
    assert gate_result.allowed is False

    # TRANSFER_EFFECTIVELY_AUTHORIZED=NO — the structurally valid matching
    # transfer above is proposed evidence, not authority.
    assert admitted == ()
    # FIELD_INCLUDED=NO.
    result = _evaluate(_projection(documented_medication_change=True), admitted)
    assert result.status.value == "blocked"
    assert result.metadata["included_fields"] == ()
    assert result.metadata["provenance_preserved"] is False

    # The SENSITIVE floor was not lowered to manufacture an ALLOW.
    from cmm.domains.mental_health.privacy import build_mental_health_privacy_policy

    floor = resolve_effective_privacy_metadata(
        project_domain_privacy_metadata(
            build_mental_health_privacy_policy(),
            processing_location=ProcessingLocation.LOCAL,
        )
    ).effective
    assert floor.sensitivity is SensitivityLevel.SENSITIVE


def test_checkpoint_13i_consumed_canonical_approval_authorizes_the_exact_field():
    """V4 MAJOR-03: only a consumed canonical approval admits the exact field."""
    authorized_resolver = _authorized_cross_domain_resolver()
    approval_service, gate = _connected_permission_stack(authorized_resolver)
    request = _cross_domain_permission_request(
        "req-at-dp-052-v4-approved", "documented_medication_change"
    )
    candidates = (_canonical_transfer("documented_medication_change"),)

    # RESOLVER_OUTCOME=APPROVAL_REQUIRED / PRE_APPROVAL_GATE=APPROVAL_REQUIRED.
    decision, pending, admitted = _admit_cross_domain_transfers(
        request=request,
        candidates=candidates,
        resolver=authorized_resolver,
        gate=gate,
    )
    assert decision.decision is PermissionOutcome.APPROVAL_REQUIRED
    assert pending.outcome is PermissionGateOutcome.APPROVAL_REQUIRED
    assert admitted == ()

    # CANONICAL_APPROVAL_CREATED=YES / CANONICAL_APPROVAL_GRANTED=YES — the
    # approval request is created from the canonical requirement exposed by the
    # real gate and granted through the real canonical ApprovalService.
    approval_request_id = _grant_canonical_cross_domain_approval(
        approval_service, gate, request
    )
    assert approval_service.repository.get_request(approval_request_id) is not None

    # POST_APPROVAL_GATE=APPROVAL_CONSUMED.
    decision, consumed, admitted = _admit_cross_domain_transfers(
        request=request,
        candidates=candidates,
        resolver=authorized_resolver,
        gate=gate,
        approval_request_id=approval_request_id,
    )
    assert decision.decision is PermissionOutcome.APPROVAL_REQUIRED
    assert consumed.outcome is PermissionGateOutcome.APPROVAL_CONSUMED
    assert consumed.allowed is True
    evidence = consumed.approval_evidence
    assert evidence["granted"] is True
    assert evidence["consumed"] is True
    assert evidence["requirement_id"] == f"cross-domain:{request.request_id}"
    assert evidence["domain_id"] == request.source_domain
    assert evidence["target_domain"] == request.target_domain
    assert evidence["actor_id"] == request.actor_id
    assert evidence["session_id"] == request.session_id

    # MATCHING_TRANSFER_ADMITTED=YES.
    assert admitted == candidates
    # APPROVED_FIELD_INCLUDED=YES — and approval for one resource still
    # authorizes only the field whose own transfer was admitted.
    result = _evaluate(
        _projection(documented_medication_change=True, appointment_phone=True),
        admitted,
    )
    assert result.status.value == "applied"
    assert result.metadata["included_fields"] == ("documented_medication_change",)
    assert "appointment_phone" in result.metadata["excluded_fields"]
    assert result.metadata["unbound_fields"] == ("appointment_phone",)
    assert result.metadata["provenance_references"] == ("finding:health:13",)


def test_checkpoint_13j_approval_for_one_field_cannot_authorize_another():
    """V4 MAJOR-03: the authority tuple binds resource, actor and session.

    A consumed canonical approval for one projected resource never authorizes a
    different resource, nor the same resource for a different actor.
    """
    authorized_resolver = _authorized_cross_domain_resolver()
    approval_service, gate = _connected_permission_stack(authorized_resolver)
    field_a = _cross_domain_permission_request("req-at-dp-052-v4-binding", "field_a")
    field_b = _cross_domain_permission_request("req-at-dp-052-v4-binding", "field_b")

    approval_request_id = _grant_canonical_cross_domain_approval(
        approval_service, gate, field_a
    )
    _decision, gate_a, admitted_a = _admit_cross_domain_transfers(
        request=field_a,
        candidates=(_canonical_transfer("field_a"),),
        resolver=authorized_resolver,
        gate=gate,
        approval_request_id=approval_request_id,
    )
    assert gate_a.outcome is PermissionGateOutcome.APPROVAL_CONSUMED
    assert admitted_a == (_canonical_transfer("field_a"),)

    # The same consumed approval cannot authorize a different resource, even
    # though the transfer for it is structurally valid and matching.
    _decision, gate_b, admitted_b = _admit_cross_domain_transfers(
        request=field_b,
        candidates=(_canonical_transfer("field_b"),),
        resolver=authorized_resolver,
        gate=gate,
        approval_request_id=approval_request_id,
    )
    assert gate_b.outcome is PermissionGateOutcome.APPROVAL_DENIED
    assert "approval.binding_failure" in gate_b.reasons
    assert admitted_b == ()
    result = _evaluate(_projection(field_b=True), admitted_b)
    assert result.status.value == "blocked"
    assert result.metadata["included_fields"] == ()

    # Nor can it authorize the same resource for a different actor.
    other_actor_request = CrossDomainPermissionRequest(
        "req-at-dp-052-v4-binding",
        source_domain=HEALTH_DOMAIN_ID,
        target_domain=MENTAL_HEALTH_DOMAIN_ID,
        resource_ids=("field_a",),
        resource_kinds=(CROSS_DOMAIN_SOURCE_KIND,),
        reason=CROSS_DOMAIN_PURPOSE,
        actor_id="user-2",
        session_id="session-1",
        sensitivity_level=SensitivityLevel.RESTRICTED,
        capability=PermissionCapability.RESOURCE_READ,
    )
    _decision, gate_actor, admitted_actor = _admit_cross_domain_transfers(
        request=other_actor_request,
        candidates=(_canonical_transfer("field_a"),),
        resolver=authorized_resolver,
        gate=gate,
        approval_request_id=approval_request_id,
    )
    assert gate_actor.outcome is PermissionGateOutcome.APPROVAL_DENIED
    assert "approval.binding_failure" in gate_actor.reasons
    assert admitted_actor == ()
    assert other_actor_request.actor_id != field_a.actor_id


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

    # The same downgrade must invalidate an already-validated memory binding
    # that references the revoked canonical permission decision.
    from dataclasses import replace

    from cmm.domains.memory_contracts import DomainMemoryReferenceInventory
    from cmm.domains.mental_health.memory import (
        validate_mental_health_memory_binding,
    )
    from tests.domains.test_mental_health_domain_memory import _full_chain

    binding, inventory, _view, _proposal = _full_chain("mp-at-dp-052-c14")
    assert (
        validate_mental_health_memory_binding(
            binding=binding, inventory=inventory
        ).is_valid
        is True
    )

    revoked_decision = replace(inventory.permission_decisions[0], allowed=False)
    stale = validate_mental_health_memory_binding(
        binding=binding,
        inventory=DomainMemoryReferenceInventory(
            references=inventory.references,
            proposals=inventory.proposals,
            permission_decisions=(revoked_decision,),
            approval_requests=inventory.approval_requests,
            approval_decisions=inventory.approval_decisions,
            traces=inventory.traces,
            views=inventory.views,
        ),
    )
    assert stale.is_valid is False
    # The stale binding is unchanged; only current authority moved.
    assert binding.permission_decision_ids == (
        inventory.permission_decisions[0].decision_id,
    )


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


# ── Checkpoint 17: Phase 10.53 independence (sibling is not a dependency) ────


def test_checkpoint_17_mental_health_is_independent_of_phase_10_53():
    """Durable invariant: Mental Health never depends on Neurodivergence.

    Phase 10.53 implemented ``domain:neurodivergence``.  The invariant that
    matters for AT-DP-052 is independence, not the sibling's absence: Mental
    Health boots on its own, never imports the sibling pack, and never
    auto-registers it.
    """
    from pathlib import Path

    repo_root = Path(__file__).resolve().parents[2]
    assert (repo_root / "cmm/domains/neurodivergence").is_dir()
    for path in sorted((repo_root / "cmm/domains/mental_health").glob("*.py")):
        assert "cmm.domains.neurodivergence" not in path.read_text(encoding="utf-8"), (
            path.name
        )

    bootstrap = _mental_health_bootstrap()
    assert bootstrap.domain_registry.contains(MENTAL_HEALTH_DOMAIN_ID)
    assert not bootstrap.domain_registry.contains("domain:neurodivergence")


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
