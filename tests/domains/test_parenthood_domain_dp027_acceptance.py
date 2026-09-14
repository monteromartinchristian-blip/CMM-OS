"""Phase 10.27 — AT-DP-027 Connected Acceptance Test Suite for Parenthood Domain.

Definitive Remediation: Frozen 35-checkpoint connected lifecycle.

Proves:
- Single domain pack and shared profile (`domain:parenthood`, `ParenthoodProfile`) covering
  both journey (`parenthood.journey` / Camino a la Paternidad) and child workspaces
  (`parenthood.child:<child_id>`).
- Sibling identity isolation between multiple child workspaces (`child:001`, `child:002`).
- Child personal names ("Lucas", "Sofía") remain presentation data only and are never
  used as stable architectural identifiers.
- Epistemic separation between proposed pathways, hypotheses, and adopted parental decisions.
- Non-diagnostic preservation of normal developmental variations.
- Selective, provenance-preserving journey-to-child context transfer (bulk copy prohibited).
- Fail-closed permission policy blocking autonomous contracting, payment, legal/medical decisions,
  external communication, and direct memory writes.
- Real connected runtime ownership across resolution, composition, reasoning rules, operations,
  workflows, memory proposals/bindings, presentation, and traces.
- Zero parallel infrastructure; General domain remains fallback-compatible.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from cmm.agent_runtime.domain_permission_contracts import PermissionCapability
from cmm.cognitive.reasoning_rule_contracts import ReasoningRuleContext
from cmm.cognitive.reasoning_rule_registry import InMemoryReasoningRuleRegistry
from cmm.domains.composer import DefaultDomainComposer
from cmm.domains.identifiers import DomainId
from cmm.domains.memory_contracts import (
    DomainMemoryApprovalDecisionSnapshot,
    DomainMemoryApprovalRequestSnapshot,
    DomainMemoryCapability,
    DomainMemoryPermissionDecisionSnapshot,
    DomainMemoryReferenceInventory,
    DomainMemorySensitivityLevel,
    DomainMemoryTraceSnapshot,
    DomainMemoryViewSnapshot,
)
from cmm.domains.operation_registry import InMemoryDomainOperationRegistry
from cmm.domains.parenthood.bootstrap import (
    ParenthoodDomainBootstrap,
    build_standard_parenthood_domain_bootstrap,
)
from cmm.domains.parenthood.definition import (
    PARENTHOOD_DOMAIN_ID,
    build_parenthood_domain_definition,
)
from cmm.domains.parenthood.memory import (
    build_parenthood_memory_binding,
    build_parenthood_memory_proposal,
    build_parenthood_memory_view,
    build_parenthood_memory_view_request,
    validate_parenthood_memory_binding,
)
from cmm.domains.parenthood.operations import (
    build_timeline_result,
    compare_pathways_result,
    prepare_parental_decision_result,
    review_developmental_stage_result,
)
from cmm.domains.parenthood.permissions import (
    PARENTHOOD_PROHIBITED_CAPABILITIES,
    build_parenthood_permission_policy,
    persistence_confirmation_accepted,
)
from cmm.domains.parenthood.presentation import present_parenthood_result
from cmm.domains.parenthood.profile import (
    PARENTHOOD_PROFILE_NAME,
)
from cmm.domains.parenthood.rules import (
    CostUncertaintyRule,
    DevelopmentalContextRule,
    HealthBoundaryRule,
    JourneyDependencyRule,
    JourneyToChildBoundaryRule,
    LegalTemporalValidityRule,
    MedicalLegalSeparationRule,
    MinorPrivacyRule,
    ParentChildBoundaryRule,
    ParenthoodDecisionExplicitRule,
    SiblingIdentityIsolationRule,
)
from cmm.domains.parenthood.trace import (
    assemble_parenthood_trace,
    build_parenthood_trace_reference,
)
from cmm.domains.parenthood.workspaces import (
    build_child_workspace,
    ensure_sibling_identity_isolation,
    parse_parenthood_scope,
    select_journey_transfer_candidates,
    validate_child_workspace,
)
from cmm.domains.permission_registry import DomainPermissionRegistry
from cmm.domains.profile_contracts import DomainProfileDefinition
from cmm.domains.profile_registry import InMemoryDomainProfileRegistry
from cmm.domains.registry import DomainRegistry
from cmm.domains.resolution_builder import DomainResolutionContextBuilder
from cmm.domains.resolution_contracts import DomainResolutionSignal
from cmm.domains.resolver import DefaultDomainResolver
from cmm.domains.resource_registry import InMemoryDomainResourceRegistry
from cmm.domains.trace_contracts import (
    DomainTraceReferenceKind,
    DomainTraceStatus,
)
from cmm.domains.workflow_registry import InMemoryDomainWorkflowRegistry

NOW = datetime(2026, 8, 25, 14, 0, tzinfo=timezone.utc)

FROZEN_SEMANTIC_CHECKPOINTS = (
    "01-resolve-parenthood-journey",
    "02-load-parenthood-profile",
    "03-preserve-parenthood-goal-without-inventing-adoption",
    "04-compare-pathways",
    "05-preserve-legal-temporal-uncertainty",
    "06-keep-medical-legal-financial-evidence-separate",
    "07-preserve-cost-uncertainty",
    "08-prepare-questions-without-external-transmission",
    "09-track-explicit-journey-decision",
    "10-reject-inferred-decision-adoption",
    "11-build-journey-timeline",
    "12-review-documentation-requirements",
    "13-create-first-child-workspace",
    "14-separate-display-name-from-stable-id",
    "15-resolve-child-scope",
    "16-represent-developmental-stage",
    "17-separate-child-need-from-parent-preference",
    "18-keep-normal-variation-non-diagnostic",
    "19-project-only-relevant-authorized-health-context",
    "20-prepare-parental-decision-as-proposal",
    "21-deny-autonomous-enrollment-payment-consent-contact",
    "22-create-second-child-workspace",
    "23-prove-sibling-identity-isolation",
    "24-prove-sibling-health-context-isolation",
    "25-permit-explicitly-shared-family-context",
    "26-select-journey-child-transfer-candidates",
    "27-reject-bulk-journey-dossier-transfer",
    "28-preserve-transfer-provenance",
    "29-apply-privacy-permission-review",
    "30-require-valid-persistence-approval-binding",
    "31-preserve-proposed-vs-adopted-decisions",
    "32-present-uncertainty-and-alternatives",
    "33-trace-real-connected-runtime-identifiers",
    "34-prove-no-parallel-infrastructure",
    "35-prove-general-remains-fallback-compatible",
)


class DeterministicIds:
    """Generates deterministic monotonic identifiers for scenario run."""

    def __init__(self, prefix: str = "at-dp027") -> None:
        self.index = 0
        self.prefix = prefix

    def __call__(self) -> str:
        self.index += 1
        return f"{self.prefix}-{self.index:03d}"


def _make_rule_ctx(
    state: dict[str, Any],
    metadata: dict[str, Any] | None = None,
    active_domains: tuple[str, ...] = ("domain:parenthood",),
) -> ReasoningRuleContext:
    merged_metadata = dict(state.get("shared_metadata", {}))
    if metadata:
        merged_metadata.update(metadata)
    return ReasoningRuleContext(
        reasoning_id="reasoning-dp027",
        timestamp=NOW,
        active_domains=active_domains,
        primary_domain=active_domains[0],
        metadata=merged_metadata,
    )


@dataclass
class ConnectedParenthoodScenario:
    """Stateful, connected lifecycle driver executing all 35 semantic checkpoints in sequence."""

    ids: DeterministicIds = field(default_factory=DeterministicIds)
    state: dict[str, Any] = field(default_factory=dict)
    checkpoints: list[str] = field(default_factory=list)

    def checkpoint(self, name: str, condition: bool) -> None:
        assert condition, f"Checkpoint assertion failed: {name}"
        self.checkpoints.append(name)

    @staticmethod
    def signals(
        primary: str, supporting: str | None = None
    ) -> tuple[DomainResolutionSignal, ...]:
        sigs = [
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
        if supporting:
            sigs.extend(
                [
                    DomainResolutionSignal(
                        kind="intent",
                        source="user",
                        value=f"{supporting}-intent",
                        domain_ids=(f"domain:{supporting}",),
                    ),
                    DomainResolutionSignal(
                        kind="entity",
                        source="system",
                        value=f"{supporting}-entity",
                        domain_ids=(f"domain:{supporting}",),
                    ),
                ]
            )
        return tuple(sigs)

    def run(self) -> None:
        """Run all 35 checkpoints in continuous connected order."""
        # ── 01. Resolve parenthood journey ────────────────────────────────────
        bootstrap = build_standard_parenthood_domain_bootstrap()
        self.state["bootstrap"] = bootstrap
        assert bootstrap.resolver.fallback_domain == DomainId("general")

        context = DomainResolutionContextBuilder(
            id_factory=self.ids, clock=lambda: NOW
        ).build(
            registry_snapshot=bootstrap.domain_registry.snapshot(),
            user_input="Exploring family-building paths, surrogacy and adoption options.",
            authorized_domains=("domain:general", PARENTHOOD_DOMAIN_ID),
            signals=self.signals("parenthood"),
        )
        self.state["resolution_context"] = context

        resolver = DefaultDomainResolver(
            scoring_policy=bootstrap.resolver.scoring_policy,
            fallback_domain=bootstrap.resolver.fallback_domain,
            id_factory=self.ids,
            clock=lambda: NOW,
        )
        self.state["resolver"] = resolver
        resolution = resolver.resolve(context)
        self.state["resolution"] = resolution

        self.checkpoint(
            "01-resolve-parenthood-journey",
            str(resolution.primary_domain) == PARENTHOOD_DOMAIN_ID,
        )

        # ── 02. Load ParenthoodProfile ────────────────────────────────────────
        profile = bootstrap.profile_registry.get_by_domain(DomainId("parenthood"))
        self.state["profile"] = profile
        assert profile is not None
        assert profile.profile_name == PARENTHOOD_PROFILE_NAME

        composition = DefaultDomainComposer(
            id_factory=self.ids, clock=lambda: NOW
        ).compose(resolution, (build_parenthood_domain_definition(),))
        self.state["composition"] = composition

        self.checkpoint(
            "02-load-parenthood-profile",
            isinstance(profile, DomainProfileDefinition)
            and profile.profile_name == "ParenthoodProfile"
            and composition is not None,
        )

        # ── 03. Preserve parenthood goal without inventing adoption ──────────
        parenthood_goal = {
            "id": "goal-family-001",
            "kind": "family_building",
            "status": "exploring",
            "topic": "explore_pathways",
            "explicitly_adopted": False,
        }
        self.state["parenthood_goal"] = parenthood_goal

        rule_explicit = ParenthoodDecisionExplicitRule()
        res_goal = rule_explicit.evaluate(
            _make_rule_ctx(self.state, metadata={"decisions": [parenthood_goal]})
        )
        self.state["rule_res_03"] = res_goal
        self.checkpoint(
            "03-preserve-parenthood-goal-without-inventing-adoption",
            any(f.code == "PROPOSED_DECISION_PRESERVED" for f in res_goal.findings),
        )

        # ── 04. Compare pathways ──────────────────────────────────────────────
        pathways = ["gestational_surrogacy_usa", "domestic_adoption"]
        comp = compare_pathways_result(
            pathways=pathways,
            criteria={
                "budget_range": (70000, 130000),
                "jurisdiction_preference": "USA",
            },
        )
        self.state["pathway_comparison"] = comp
        self.checkpoint(
            "04-compare-pathways",
            comp["is_proposal"] is True
            and comp["has_autonomous_decision"] is False
            and len(comp["pathways"]) == 2,
        )

        # ── 05. Preserve legal temporal uncertainty ───────────────────────────
        legal_req = {
            "id": "req-legal-california-01",
            "jurisdiction": "California",
            "statute": "Family Code 7962",
            "verified_current": False,
        }
        self.state["legal_requirement"] = legal_req

        rule_legal = LegalTemporalValidityRule()
        res_legal = rule_legal.evaluate(
            _make_rule_ctx(self.state, metadata={"legal_requirements": [legal_req]})
        )
        self.state["rule_res_05"] = res_legal
        self.checkpoint(
            "05-preserve-legal-temporal-uncertainty",
            any(
                f.code == "LEGAL_TEMPORAL_VERIFICATION_REQUIRED"
                for f in res_legal.findings
            ),
        )

        # ── 06. Keep medical/legal/financial evidence separate ────────────────
        journey_dossier = {
            "medical": {"clinic_records": "IVF lab protocol and egg donor screening"},
            "legal": {"contract": "surrogacy_gestational_agreement_draft"},
            "financial": {"escrow": "agency_fee_schedule_contingencies"},
        }
        self.state["journey_dossier"] = journey_dossier

        rule_sep = MedicalLegalSeparationRule()
        res_sep = rule_sep.evaluate(_make_rule_ctx(self.state))
        self.state["rule_res_06"] = res_sep
        self.checkpoint(
            "06-keep-medical-legal-financial-evidence-separate",
            any(f.code == "MEDICAL_LEGAL_SEPARATED" for f in res_sep.findings)
            and set(journey_dossier.keys()) == {"medical", "legal", "financial"},
        )

        # ── 07. Preserve cost uncertainty ─────────────────────────────────────
        scenario = {
            "item": "clinical_and_agency_fees",
            "is_guaranteed": True,
            "estimated_range": (85000, 145000),
        }
        self.state["financial_scenario"] = scenario

        rule_cost = CostUncertaintyRule()
        res_cost = rule_cost.evaluate(
            _make_rule_ctx(self.state, metadata={"financial_scenarios": [scenario]})
        )
        self.state["rule_res_07"] = res_cost
        self.checkpoint(
            "07-preserve-cost-uncertainty",
            any(f.code == "COST_CERTAINTY_FLAGGED" for f in res_cost.findings),
        )

        # ── 08. Prepare questions without external transmission ───────────────
        questions = {
            "topic": "agency_consultation",
            "questions": [
                "What are the surrogate screening standards?",
                "How are contingency legal fees structured in California?",
            ],
            "external_transmitted": False,
        }
        self.state["consultation_questions"] = questions

        policy = build_parenthood_permission_policy()
        self.state["permission_policy"] = policy
        self.checkpoint(
            "08-prepare-questions-without-external-transmission",
            policy.allow_external_communication is False
            and not questions["external_transmitted"],
        )

        # ── 09. Track explicit journey decision ───────────────────────────────
        explicit_journey_decision = {
            "topic": "chosen_pathway",
            "status": "adopted",
            "explicitly_adopted": True,
            "selected_pathway": "gestational_surrogacy_usa",
        }
        self.state["explicit_journey_decision"] = explicit_journey_decision

        res_explicit = rule_explicit.evaluate(
            _make_rule_ctx(
                self.state, metadata={"decisions": [explicit_journey_decision]}
            )
        )
        self.state["rule_res_09"] = res_explicit
        self.checkpoint(
            "09-track-explicit-journey-decision",
            any(f.code == "ADOPTED_DECISION_VERIFIED" for f in res_explicit.findings),
        )

        # ── 10. Reject inferred decision adoption ─────────────────────────────
        inferred_agency_decision = {
            "topic": "surrogacy_agency_selection",
            "status": "proposed",
            "explicitly_adopted": False,
            "candidate_agency": "Agency Pacific",
        }
        self.state["inferred_agency_decision"] = inferred_agency_decision

        res_inferred = rule_explicit.evaluate(
            _make_rule_ctx(
                self.state, metadata={"decisions": [inferred_agency_decision]}
            )
        )
        self.state["rule_res_10"] = res_inferred
        self.checkpoint(
            "10-reject-inferred-decision-adoption",
            any(f.code == "PROPOSED_DECISION_PRESERVED" for f in res_inferred.findings)
            and not any(
                f.code == "ADOPTED_DECISION_VERIFIED" for f in res_inferred.findings
            ),
        )

        # ── 11. Build journey timeline ────────────────────────────────────────
        timeline = build_timeline_result(
            pathway=explicit_journey_decision["selected_pathway"],
            start_date="2026-10-01",
        )
        self.state["journey_timeline"] = timeline
        self.checkpoint(
            "11-build-journey-timeline",
            timeline["status"] == "completed" and len(timeline["milestones"]) >= 5,
        )

        # ── 12. Review documentation requirements ─────────────────────────────
        docs_deps = {
            "legal_parentage_order": {"prerequisite": "surrogacy_contract"},
            "birth_certificate": {"prerequisite": "legal_parentage_order"},
            "passport_and_consular_report": {"prerequisite": "birth_certificate"},
        }
        self.state["docs_deps"] = docs_deps

        rule_dep = JourneyDependencyRule()
        res_dep = rule_dep.evaluate(
            _make_rule_ctx(self.state, metadata={"dependencies": docs_deps})
        )
        self.state["rule_res_12"] = res_dep
        self.checkpoint(
            "12-review-documentation-requirements",
            any(f.code == "JOURNEY_DEPENDENCIES_TRACKED" for f in res_dep.findings),
        )

        # ── 13. Create first child workspace ──────────────────────────────────
        child_1 = build_child_workspace(
            id="child:001",
            display_name="Lucas",
            developmental_stage="infant",
            created_at=NOW,
            metadata={"notes": "healthy infant"},
        )
        self.state["child_1"] = child_1
        self.checkpoint(
            "13-create-first-child-workspace",
            validate_child_workspace(child_1) is True,
        )

        # ── 14. Separate display name from stable ID ──────────────────────────
        assert child_1.id == "child:001"
        assert child_1.display_name == "Lucas"
        assert "lucas" not in child_1.id.lower()

        # Display name mutation preserves stable internal identity
        child_1_renamed = build_child_workspace(
            id=child_1.id,
            display_name="Lucas Martin",
            developmental_stage=child_1.developmental_stage,
            created_at=child_1.created_at,
        )
        assert child_1_renamed.id == child_1.id == "child:001"
        assert child_1_renamed.display_name != child_1.display_name

        self.checkpoint(
            "14-separate-display-name-from-stable-id",
            child_1.id == "child:001"
            and child_1.display_name == "Lucas"
            and "lucas" not in child_1.id.lower(),
        )

        # ── 15. Resolve child scope ───────────────────────────────────────────
        scope_1 = parse_parenthood_scope(f"parenthood.child:{child_1.id}")
        self.state["scope_1"] = scope_1
        self.checkpoint(
            "15-resolve-child-scope",
            scope_1.is_child is True
            and scope_1.child_id == "child:001"
            and scope_1.scope_id == "parenthood.child:child:001",
        )

        # ── 16. Represent developmental stage ─────────────────────────────────
        stage_review = review_developmental_stage_result(
            child_id=child_1.id,
            stage="infant",
            observations={
                "sleep_pattern": "wake window 90-120 minutes",
                "motor_milestone": "rolling over and grasping objects",
            },
        )
        self.state["stage_review"] = stage_review
        self.checkpoint(
            "16-represent-developmental-stage",
            stage_review["stage"] == "infant" and stage_review["is_proposal"] is True,
        )

        # ── 17. Separate child need from parent preference ────────────────────
        rule_boundary = ParentChildBoundaryRule()
        res_boundary = rule_boundary.evaluate(
            _make_rule_ctx(
                self.state,
                metadata={
                    "child_needs": ["infant nap routine 90-120 min intervals"],
                    "parent_preferences": ["evening work/gym session"],
                },
            )
        )
        self.state["rule_res_17"] = res_boundary
        self.checkpoint(
            "17-separate-child-need-from-parent-preference",
            any(
                f.code == "PARENT_CHILD_BOUNDARY_PRESERVED"
                for f in res_boundary.findings
            ),
        )

        # ── 18. Keep normal variation non-diagnostic ──────────────────────────
        child_observation = {
            "behavior": "frequent night wakings during milestone leap",
            "stage": "infant",
            "proposed_diagnosis": "infant_sleep_wake_disorder",
        }
        self.state["child_observation"] = child_observation

        rule_dev = DevelopmentalContextRule()
        res_dev = rule_dev.evaluate(
            _make_rule_ctx(
                self.state, metadata={"child_observations": [child_observation]}
            )
        )
        self.state["rule_res_18"] = res_dev
        self.checkpoint(
            "18-keep-normal-variation-non-diagnostic",
            any(f.code == "PATHOLOGY_LABEL_REJECTED" for f in res_dev.findings),
        )

        # ── 19. Project only relevant authorized health context ───────────────
        health_summary = {
            "child_id": "child:001",
            "allergies": ["cow milk protein sensitivity"],
            "vaccination_status": "current_for_age",
            "unrelated_diagnostic_hypotheses": None,
        }
        self.state["health_summary"] = health_summary

        rule_health = HealthBoundaryRule()
        res_health = rule_health.evaluate(
            _make_rule_ctx(self.state, metadata={"health_summary": health_summary})
        )
        self.state["rule_res_19"] = res_health
        self.checkpoint(
            "19-project-only-relevant-authorized-health-context",
            any(f.code == "HEALTH_BOUNDARY_ENFORCED" for f in res_health.findings)
            and PermissionCapability.MEDICAL_DECISION
            in PARENTHOOD_PROHIBITED_CAPABILITIES,
        )

        # ── 20. Prepare parental decision as proposal ─────────────────────────
        dec_proposal = prepare_parental_decision_result(
            child_id=child_1.id,
            topic="early_childcare_schedule",
            options=["half_day_nursery", "home_nanny_share"],
        )
        self.state["parental_decision_proposal"] = dec_proposal
        self.checkpoint(
            "20-prepare-parental-decision-as-proposal",
            dec_proposal["is_proposal"] is True
            and dec_proposal["requires_explicit_user_adoption"] is True
            and dec_proposal["adopted_by_system"] is False,
        )

        # ── 21. Deny autonomous enrollment/payment/consent/contact ────────────
        prohibited = profile.prohibited_actions
        self.checkpoint(
            "21-deny-autonomous-enrollment-payment-consent-contact",
            "child_enrollment" in prohibited
            and "contracting" in prohibited
            and "payment" in prohibited
            and "consent" in prohibited
            and "external_communication" in prohibited
            and "medical_decision" in prohibited
            and policy.allow_memory_write is False
            and policy.allow_external_communication is False,
        )

        # ── 22. Create second child workspace ─────────────────────────────────
        child_2 = build_child_workspace(
            id="child:002",
            display_name="Sofía",
            developmental_stage="newborn",
            created_at=NOW,
            metadata={"notes": "newborn sibling"},
        )
        self.state["child_2"] = child_2
        assert child_2.id == "child:002"
        assert child_2.display_name == "Sofía"
        assert "sofia" not in child_2.id.lower()

        self.checkpoint(
            "22-create-second-child-workspace",
            validate_child_workspace(child_2) is True
            and child_2.id == "child:002"
            and "sofia" not in child_2.id.lower(),
        )

        # ── 23. Prove sibling identity isolation ──────────────────────────────
        record_lucas = {
            "child_id": child_1.id,
            "data": "Lucas routine and developmental notes",
            "is_shared_family_context": False,
        }
        iso_check = ensure_sibling_identity_isolation(
            target_workspace=child_2,
            record=record_lucas,
        )
        self.state["iso_check_23"] = iso_check
        self.checkpoint(
            "23-prove-sibling-identity-isolation",
            iso_check["isolated"] is True
            and iso_check["access_allowed"] is False
            and iso_check["reason"] == "sibling_identity_mismatch",
        )

        # ── 24. Prove sibling health/context isolation ────────────────────────
        rule_iso = SiblingIdentityIsolationRule()
        res_iso_rule = rule_iso.evaluate(
            _make_rule_ctx(
                self.state,
                metadata={
                    "active_child_id": child_2.id,
                    "context_records": [
                        {
                            "child_id": child_1.id,
                            "data": "Lucas allergy to dairy",
                            "is_shared": False,
                        }
                    ],
                },
            )
        )
        self.state["rule_res_24"] = res_iso_rule
        self.checkpoint(
            "24-prove-sibling-health-context-isolation",
            any(
                f.code == "SIBLING_CONTAMINATION_BLOCKED" for f in res_iso_rule.findings
            ),
        )

        # ── 25. Permit explicitly shared family context ───────────────────────
        shared_record = {
            "child_id": None,
            "data": "Family emergency contacts and holiday schedule",
            "is_shared_family_context": True,
        }
        iso_shared = ensure_sibling_identity_isolation(
            target_workspace=child_2,
            record=shared_record,
        )
        self.state["iso_shared_25"] = iso_shared
        self.checkpoint(
            "25-permit-explicitly-shared-family-context",
            iso_shared["access_allowed"] is True
            and iso_shared["reason"] == "explicit_shared_family_context",
        )

        # ── 26. Select journey→child transfer candidates ──────────────────────
        journey_pool = {
            "pediatrician_contact": {
                "category": "contact",
                "name": "Dr. Miller",
                "clinic": "Valencia Pediatrics",
            },
            "family_origin_narrative": {
                "category": "narrative",
                "story": "Family building journey notes",
            },
            "agency_surrogacy_contract": {
                "category": "legal_contract",
                "contract_draft": "Sensitive operational dossier",
            },
        }
        self.state["journey_pool"] = journey_pool

        transfers = select_journey_transfer_candidates(
            journey_context=journey_pool,
            selected_keys=("pediatrician_contact", "family_origin_narrative"),
            target_child_id=child_1.id,
        )
        self.state["transfers"] = transfers
        self.checkpoint(
            "26-select-journey-child-transfer-candidates",
            len(transfers) == 2
            and {t["key"] for t in transfers}
            == {"pediatrician_contact", "family_origin_narrative"},
        )

        # ── 27. Reject bulk journey dossier transfer ──────────────────────────
        bulk_rejected = False
        try:
            select_journey_transfer_candidates(
                journey_context=journey_pool,
                selected_keys=None,
                target_child_id=child_1.id,
                allow_bulk_transfer=True,
            )
        except ValueError as err:
            if "bulk copy prohibited" in str(err):
                bulk_rejected = True

        rule_j2c = JourneyToChildBoundaryRule()
        res_j2c = rule_j2c.evaluate(_make_rule_ctx(self.state))
        self.state["rule_res_27"] = res_j2c

        self.checkpoint(
            "27-reject-bulk-journey-dossier-transfer",
            bulk_rejected is True
            and any(
                f.code == "JOURNEY_TO_CHILD_BOUNDARY_ENFORCED" for f in res_j2c.findings
            ),
        )

        # ── 28. Preserve transfer provenance ──────────────────────────────────
        provenance_ok = len(transfers) == 2 and all(
            t["provenance"]["origin_domain"] == PARENTHOOD_DOMAIN_ID
            and t["provenance"]["origin_scope"] == "parenthood.journey"
            and t["provenance"]["target_child_id"] == child_1.id
            and t["provenance"]["transfer_authorized"] is True
            for t in transfers
        )
        self.checkpoint("28-preserve-transfer-provenance", provenance_ok)

        # ── 29. Apply privacy/permission review ───────────────────────────────
        rule_privacy = MinorPrivacyRule()
        res_priv_clean = rule_privacy.evaluate(
            _make_rule_ctx(
                self.state, metadata={"action_proposed": "internal_routine_plan"}
            )
        )
        res_priv_leak = rule_privacy.evaluate(
            _make_rule_ctx(
                self.state,
                metadata={"action_proposed": "external_export_minor_dossier"},
            )
        )
        self.state["rule_res_29"] = res_priv_clean
        self.checkpoint(
            "29-apply-privacy-permission-review",
            not any(
                f.code == "MINOR_PRIVACY_RESTRICTION" for f in res_priv_clean.findings
            )
            and any(
                f.code == "MINOR_PRIVACY_RESTRICTION" for f in res_priv_leak.findings
            ),
        )

        # ── 30. Require valid persistence approval/binding ────────────────────
        proposal = build_parenthood_memory_proposal(
            proposal_id=self.ids(),
            affected_reference_ids=("ref-routine-01",),
        )
        self.state["memory_proposal"] = proposal

        # 1. Unbound or missing authorization -> rejected
        unbound_res = persistence_confirmation_accepted(
            proposal_id=proposal.proposal_id
        )
        assert unbound_res["accepted"] is False

        # 2. Valid proposal + approval/binding chain -> accepted
        trace_id = self.ids()
        perm_dec_id = self.ids()
        memory_perm = DomainMemoryPermissionDecisionSnapshot(
            decision_id=perm_dec_id,
            allowed=True,
            capabilities=(DomainMemoryCapability.PROPOSE,),
            source_domain_id=DomainId("parenthood"),
            target_domain_id=DomainId("parenthood"),
            sensitivity_levels=(DomainMemorySensitivityLevel.NORMAL,),
        )

        mem_request = build_parenthood_memory_view_request(
            request_id=self.ids(),
            trace_id=trace_id,
            permission_decision_ids=(perm_dec_id,),
        )
        base_inventory = DomainMemoryReferenceInventory(
            traces=(
                DomainMemoryTraceSnapshot(
                    trace_id=trace_id, primary_domain=PARENTHOOD_DOMAIN_ID
                ),
            ),
            permission_decisions=(memory_perm,),
        )
        view = build_parenthood_memory_view(
            request=mem_request,
            inventory=base_inventory,
        )

        req_id = self.ids()
        dec_id = self.ids()
        binding = build_parenthood_memory_binding(
            proposal=proposal,
            view=view,
            trace_id=trace_id,
            permission_decision_ids=(perm_dec_id,),
            approval_request_ids=(req_id,),
            approval_decision_ids=(dec_id,),
        )
        self.state["memory_binding"] = binding

        full_inventory = DomainMemoryReferenceInventory(
            proposals=(proposal,),
            permission_decisions=(memory_perm,),
            approval_requests=(
                DomainMemoryApprovalRequestSnapshot(
                    request_id=req_id, proposal_id=proposal.proposal_id
                ),
            ),
            approval_decisions=(
                DomainMemoryApprovalDecisionSnapshot(
                    decision_id=dec_id, request_id=req_id, approved=True
                ),
            ),
            traces=(
                DomainMemoryTraceSnapshot(
                    trace_id=trace_id, primary_domain=PARENTHOOD_DOMAIN_ID
                ),
            ),
            views=(
                DomainMemoryViewSnapshot(
                    view_id=view.view_id,
                    request_id=mem_request.request_id,
                    primary_domain=DomainId("parenthood"),
                    trace_id=trace_id,
                    view_digest=view.content_digest,
                ),
            ),
        )
        self.state["memory_inventory"] = full_inventory

        validation = validate_parenthood_memory_binding(
            binding=binding,
            inventory=full_inventory,
            child_id=child_1.id,
        )
        assert validation.is_valid is True

        accepted_res = persistence_confirmation_accepted(
            confirmation_binding=binding,
            confirmation_inventory=full_inventory,
            proposal_id=proposal.proposal_id,
            child_id=child_1.id,
        )
        self.checkpoint(
            "30-require-valid-persistence-approval-binding",
            unbound_res["accepted"] is False
            and accepted_res["authorization_accepted"] is True,
        )

        # ── 31. Preserve proposed vs adopted decisions ────────────────────────
        # Journey pathway decision is adopted (CP09); childcare schedule is proposed (CP20).
        journey_dec = self.state["explicit_journey_decision"]
        child_dec = self.state["parental_decision_proposal"]

        self.checkpoint(
            "31-preserve-proposed-vs-adopted-decisions",
            journey_dec["status"] == "adopted"
            and journey_dec["explicitly_adopted"] is True
            and child_dec["is_proposal"] is True
            and child_dec["adopted_by_system"] is False,
        )

        # ── 32. Present uncertainty and alternatives ──────────────────────────
        pres_journey = present_parenthood_result(
            self.state["pathway_comparison"],
            scope="parenthood.journey",
        )
        pres_child = present_parenthood_result(
            self.state["parental_decision_proposal"],
            scope=scope_1.scope_id,
            child_display_name=child_1.display_name,
        )
        self.state["pres_journey"] = pres_journey
        self.state["pres_child"] = pres_child

        self.checkpoint(
            "32-present-uncertainty-and-alternatives",
            pres_journey["domain_display_name"] == "Paternidad"
            and pres_journey["scope_display_name"] == "Camino a la Paternidad"
            and pres_journey["uncertainty_preserved"] is True
            and pres_child["domain_display_name"] == "Paternidad"
            and pres_child["scope_display_name"] == "Lucas"
            and pres_child["non_diagnostic_badge"] is not None,
        )

        # ── 33. Trace real connected runtime identifiers ──────────────────────
        trace_refs = (
            build_parenthood_trace_reference(
                ref_id=str(profile.id),
                kind=DomainTraceReferenceKind.PROFILE,
            ),
            build_parenthood_trace_reference(
                ref_id=proposal.proposal_id,
                kind=DomainTraceReferenceKind.MEMORY_PROPOSAL,
            ),
            build_parenthood_trace_reference(
                ref_id=binding.binding_id,
                kind=DomainTraceReferenceKind.MEMORY_BINDING,
            ),
        )

        trace = assemble_parenthood_trace(
            request_id=self.ids(),
            resolution_context_id=context.id,
            resolution_result_id=resolution.id,
            composition_id=composition.id,
            domain_result_id=self.ids(),
            started_at=NOW,
            completed_at=NOW,
            references=trace_refs,
            scope=scope_1.scope_id,
            child_id=child_1.id,
        )
        self.state["trace"] = trace

        self.checkpoint(
            "33-trace-real-connected-runtime-identifiers",
            trace.status is DomainTraceStatus.COMPLETED
            and trace.references.resolution_context_id == context.id
            and trace.references.resolution_result_id == resolution.id
            and trace.references.composition_id == composition.id
            and trace.metadata.get("child_id") == "child:001",
        )

        # ── 34. Prove no parallel infrastructure ──────────────────────────────
        no_parallel = (
            isinstance(bootstrap, ParenthoodDomainBootstrap)
            and isinstance(bootstrap.domain_registry, DomainRegistry)
            and isinstance(bootstrap.profile_registry, InMemoryDomainProfileRegistry)
            and isinstance(bootstrap.rule_registry, InMemoryReasoningRuleRegistry)
            and isinstance(
                bootstrap.operation_registry, InMemoryDomainOperationRegistry
            )
            and isinstance(bootstrap.workflow_registry, InMemoryDomainWorkflowRegistry)
            and isinstance(bootstrap.permission_registry, DomainPermissionRegistry)
            and isinstance(bootstrap.resource_registry, InMemoryDomainResourceRegistry)
            and isinstance(bootstrap.resolver, DefaultDomainResolver)
        )
        self.checkpoint("34-prove-no-parallel-infrastructure", no_parallel)

        # ── 35. Prove General remains fallback-compatible ─────────────────────
        gen_context = DomainResolutionContextBuilder(
            id_factory=self.ids, clock=lambda: NOW
        ).build(
            registry_snapshot=bootstrap.domain_registry.snapshot(),
            user_input="General life planning question without parenthood context.",
            authorized_domains=("domain:general", PARENTHOOD_DOMAIN_ID),
            signals=self.signals("general"),
        )
        gen_resolution = resolver.resolve(gen_context)

        self.checkpoint(
            "35-prove-general-remains-fallback-compatible",
            str(gen_resolution.primary_domain) == "domain:general"
            and bootstrap.domain_registry.get("domain:general") is not None,
        )


def test_at_dp_027_connected_parenthood_lifecycle() -> None:
    """Canonical AT-DP-027 Acceptance Scenario: 35 connected checkpoints."""
    scenario = ConnectedParenthoodScenario()
    scenario.run()
    assert tuple(scenario.checkpoints) == FROZEN_SEMANTIC_CHECKPOINTS
    assert len(scenario.checkpoints) == 35


def test_at_dp_027_stable_child_id_isolation_adversarial() -> None:
    """Adversarial check: ensure child display name variations never alter stable ID."""
    child = build_child_workspace(
        id="child:001",
        display_name="Lucas",
    )
    assert child.id == "child:001"
    assert "lucas" not in child.id.lower()

    # Tampered display name with symbols and numbers
    tampered = build_child_workspace(
        id=child.id,
        display_name="Lucas-001 <Tampered>",
    )
    assert tampered.id == "child:001"
    assert tampered.display_name == "Lucas-001 <Tampered>"


def test_at_dp_027_bulk_transfer_adversarial() -> None:
    """Adversarial check: ensure all variants of bulk transfer are rejected."""
    dossier = {"item_1": {"data": "a"}, "item_2": {"data": "b"}}

    # Selected keys None
    try:
        select_journey_transfer_candidates(
            journey_context=dossier,
            selected_keys=None,
            target_child_id="child:001",
        )
        assert False, "Should have raised ValueError"
    except ValueError as e:
        assert "bulk copy prohibited" in str(e)

    # Allow bulk transfer True
    try:
        select_journey_transfer_candidates(
            journey_context=dossier,
            selected_keys=("item_1",),
            target_child_id="child:001",
            allow_bulk_transfer=True,
        )
        assert False, "Should have raised ValueError"
    except ValueError as e:
        assert "bulk copy prohibited" in str(e)
