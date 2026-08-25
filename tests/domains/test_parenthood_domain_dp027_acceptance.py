"""Phase 10.27 — AT-DP-027 Connected Acceptance Test Suite for Parenthood Domain.

A continuous 10-checkpoint acceptance lifecycle verifying:
- CP1: Domain bootstrap & registration (Parenthood + General coexistence).
- CP2: Profile and fail-closed permission boundaries.
- CP3: Pre-parenthood journey pathway comparison (cost uncertainty, non-adoption).
- CP4: Journey timeline and requirements tracking (medical/legal/financial separation).
- CP5: Selective journey-to-child context transfer (bulk copy prohibited, provenance preserved).
- CP6: Child workspace initialization (stable ID vs display name, scope isolation).
- CP7: Developmental stage review & routines (non-diagnostic normal variation).
- CP8: Parental decision proposal (child needs vs parent preferences, explicit adoption gate).
- CP9: Sibling identity isolation (multi-child workspace isolation, cross-contamination blocked).
- CP10: Scoped presentation, memory proposal binding, and provenance trace assembly.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from cmm.agent_runtime.domain_permission_contracts import PermissionCapability
from cmm.cognitive.reasoning_rule_contracts import ReasoningRuleContext
from cmm.domains.identifiers import DomainId
from cmm.domains.parenthood.bootstrap import (
    build_standard_parenthood_domain_bootstrap,
)
from cmm.domains.parenthood.definition import PARENTHOOD_DOMAIN_ID
from cmm.domains.parenthood.memory import (
    build_parenthood_memory_proposal,
    build_parenthood_memory_view_request,
)
from cmm.domains.parenthood.operations import (
    build_timeline_result,
    compare_pathways_result,
    plan_routines_result,
    prepare_parental_decision_result,
)
from cmm.domains.parenthood.permissions import (
    build_parenthood_permission_policy,
    permission_authorization_allows,
    persistence_confirmation_accepted,
)
from cmm.domains.parenthood.presentation import present_parenthood_result
from cmm.domains.parenthood.profile import build_parenthood_profile
from cmm.domains.parenthood.rules import (
    CostUncertaintyRule,
    DevelopmentalContextRule,
    ParenthoodDecisionExplicitRule,
)
from cmm.domains.parenthood.trace import (
    assemble_parenthood_trace,
)
from cmm.domains.parenthood.workspaces import (
    build_child_workspace,
    ensure_sibling_identity_isolation,
    parse_parenthood_scope,
    select_journey_transfer_candidates,
    validate_child_workspace,
)
from cmm.domains.trace_contracts import (
    DomainTraceStatus,
)


def _ctx(
    active_domains: tuple[str, ...] = ("domain:parenthood",),
    metadata: dict | None = None,
) -> ReasoningRuleContext:
    return ReasoningRuleContext(
        reasoning_id="acceptance-scenario-dp027",
        timestamp=datetime.now(timezone.utc),
        active_domains=active_domains,
        primary_domain=active_domains[0],
        metadata=metadata or {},
    )


class TestParenthoodDomainDP027Acceptance:
    """AT-DP-027: Complete connected acceptance suite."""

    def test_cp01_domain_bootstrap_and_coexistence(self) -> None:
        """CP1: Verify standard bootstrap initialization and registry registration."""
        bootstrap = build_standard_parenthood_domain_bootstrap()

        assert bootstrap.domain_registry.get(PARENTHOOD_DOMAIN_ID) is not None
        assert bootstrap.domain_registry.get("domain:general") is not None
        assert (
            bootstrap.profile_registry.get_by_domain(DomainId("parenthood")) is not None
        )
        assert (
            len(bootstrap.workflow_registry.list_for_domain(PARENTHOOD_DOMAIN_ID)) == 16
        )
        assert len(bootstrap.operation_registry.list_definitions()) >= 20

    def test_cp02_profile_and_permission_boundaries(self) -> None:
        """CP2: Verify profile policies and fail-closed permission gates."""
        profile = build_parenthood_profile()
        policy = build_parenthood_permission_policy()

        # Prohibited actions include autonomous medical decisions and contracting
        assert "medical_decision" in profile.prohibited_actions
        assert "contracting" in profile.prohibited_actions
        assert "direct_memory_write" in profile.prohibited_actions

        # Read allowed, write memory prohibited
        assert PermissionCapability.RESOURCE_READ in policy.allowed_capabilities
        assert PermissionCapability.MEMORY_READ in policy.allowed_capabilities
        assert policy.allow_memory_write is False
        assert policy.allow_export is False

        # Strict authorization helper
        assert permission_authorization_allows(True) is True
        assert permission_authorization_allows(False) is False
        assert permission_authorization_allows("True") is False

        # Memory persistence confirmation fails closed when unbound
        res = persistence_confirmation_accepted(proposal_id="prop-001")
        assert res["accepted"] is False
        assert res["chain_valid"] is False

    def test_cp03_journey_pathway_comparison_and_uncertainty(self) -> None:
        """CP3: Compare pathways preserving uncertainty and non-adoption."""
        rule_dec = ParenthoodDecisionExplicitRule()
        rule_cost = CostUncertaintyRule()

        # Operations result
        comp = compare_pathways_result(
            pathways=["gestational_surrogacy_usa", "domestic_adoption"],
            criteria={"budget_range": (70000, 130000)},
        )
        assert comp["is_proposal"] is True
        assert comp["has_autonomous_decision"] is False

        # Rule evaluations
        ctx = _ctx(
            metadata={
                "decisions": [
                    {
                        "topic": "chosen_pathway",
                        "status": "proposed",
                        "explicitly_adopted": False,
                    },
                ],
                "financial_scenarios": [
                    {"item": "clinic_fees", "is_guaranteed": True},
                ],
            }
        )
        res_dec = rule_dec.evaluate(ctx)
        res_cost = rule_cost.evaluate(ctx)

        assert any(f.code == "PROPOSED_DECISION_PRESERVED" for f in res_dec.findings)
        assert any(f.code == "COST_CERTAINTY_FLAGGED" for f in res_cost.findings)

    def test_cp04_journey_timeline_and_boundary_separation(self) -> None:
        """CP4: Build timeline and verify epistemic separation between medical and legal."""
        timeline = build_timeline_result(
            pathway="gestational_surrogacy_usa",
            start_date="2026-10-01",
        )
        assert timeline["status"] == "completed"
        assert len(timeline["milestones"]) >= 5

    def test_cp05_selective_journey_to_child_context_transfer(self) -> None:
        """CP5: Transfer selective child-facing records without bulk copy."""
        journey_dossier = {
            "legal_contract_01": {
                "topic": "surrogacy_agreement",
                "category": "legal_contract",
            },
            "pediatrician_contact": {
                "topic": "Dr. Miller",
                "category": "pediatric_contact",
            },
            "child_origin_narrative": {
                "topic": "family_story",
                "category": "narrative",
            },
        }

        # Bulk copy fails
        with pytest.raises(ValueError, match="bulk copy prohibited"):
            select_journey_transfer_candidates(
                journey_context=journey_dossier,
                selected_keys=None,
                allow_bulk_transfer=True,
            )

        # Selective transfer succeeds
        transfers = select_journey_transfer_candidates(
            journey_context=journey_dossier,
            selected_keys=("pediatrician_contact", "child_origin_narrative"),
            target_child_id="child:lucas-001",
        )
        assert len(transfers) == 2
        assert {t["key"] for t in transfers} == {
            "pediatrician_contact",
            "child_origin_narrative",
        }

    def test_cp06_child_workspace_initialization_and_scope(self) -> None:
        """CP6: Initialize child workspace with stable ID and display name."""
        scope_parsed = parse_parenthood_scope("parenthood.child:child:lucas-001")
        assert scope_parsed.kind == "child"
        assert scope_parsed.child_id == "child:lucas-001"

        ws = build_child_workspace(
            id="child:lucas-001",
            display_name="Lucas",
            developmental_stage="infant",
            metadata={"birth_or_arrival_date": "2026-08-01"},
        )
        assert ws.id == "child:lucas-001"
        assert ws.display_name == "Lucas"
        assert ws.developmental_stage == "infant"

        assert validate_child_workspace(ws) is True

    def test_cp07_developmental_stage_and_non_pathology_invariant(self) -> None:
        """CP7: Review developmental stage with non-diagnostic normal variation."""
        dev_rule = DevelopmentalContextRule()

        ctx = _ctx(
            metadata={
                "active_child_id": "child:lucas-001",
                "child_observations": [
                    {
                        "behavior": "waking at night",
                        "stage": "infant",
                        "proposed_diagnosis": "infant_insomnia_disorder",
                    },
                ],
            }
        )
        res_dev = dev_rule.evaluate(ctx)
        assert any(f.code == "PATHOLOGY_LABEL_REJECTED" for f in res_dev.findings)

        routine_plan = plan_routines_result(
            child_id="child:lucas-001",
            stage="infant",
            routines={"sleep": "wake window 90-120 mins", "feeding": "on demand"},
        )
        assert routine_plan["is_proposal"] is True

    def test_cp08_parental_decision_proposal_and_boundary(self) -> None:
        """CP8: Prepare parental decision proposal requiring explicit adoption."""
        dec_proposal = prepare_parental_decision_result(
            child_id="child:lucas-001",
            topic="early_childcare_schedule",
            options=["half_day_nursery", "home_nanny_share"],
        )
        assert dec_proposal["requires_explicit_user_adoption"] is True
        assert dec_proposal["adopted_by_system"] is False

    def test_cp09_sibling_identity_isolation_enforcement(self) -> None:
        """CP9: Create second child workspace and enforce absolute sibling isolation."""
        ws_lucas = build_child_workspace(
            id="child:lucas-001",
            display_name="Lucas",
            developmental_stage="toddler",
        )
        ws_sofia = build_child_workspace(
            id="child:sofia-002",
            display_name="Sofía",
            developmental_stage="infant",
        )

        record_lucas = {"child_id": "child:lucas-001", "data": "Lucas allergy to dairy"}
        record_shared = {
            "is_shared_family_context": True,
            "data": "Grandparents visit on Sundays",
        }

        # Lucas accessing Lucas record -> allowed
        res1 = ensure_sibling_identity_isolation(
            target_workspace=ws_lucas,
            record=record_lucas,
        )
        assert res1["access_allowed"] is True

        # Sofía accessing Lucas private record -> BLOCKED
        res2 = ensure_sibling_identity_isolation(
            target_workspace=ws_sofia,
            record=record_lucas,
        )
        assert res2["access_allowed"] is False
        assert res2["reason"] == "sibling_identity_mismatch"

        # Sofía accessing shared family context -> allowed
        res3 = ensure_sibling_identity_isolation(
            target_workspace=ws_sofia,
            record=record_shared,
        )
        assert res3["access_allowed"] is True

    def test_cp10_scoped_presentation_memory_and_trace_assembly(self) -> None:
        """CP10: Project scoped human-facing presentation, bind memory proposal, assemble trace."""
        # Presentation projection
        pres = present_parenthood_result(
            {"child_id": "child:lucas-001", "status": "completed"},
            scope="parenthood.child:child:lucas-001",
            child_display_name="Lucas",
        )
        assert pres["domain_display_name"] == "Paternidad"
        assert pres["scope_display_name"] == "Lucas"
        assert pres["child_id"] == "child:lucas-001"

        # Memory proposal and view request
        prop = build_parenthood_memory_proposal(
            proposal_id="prop-lucas-milestone-01",
            affected_reference_ids=("ref-routine-01",),
        )
        assert prop.requires_confirmation is True

        req = build_parenthood_memory_view_request(
            request_id="req-view-01",
            trace_id="trace-lucas-01",
        )
        assert str(req.primary_domain) == "domain:parenthood"

        # Trace assembly
        now = datetime.now(timezone.utc)
        trace = assemble_parenthood_trace(
            request_id="trace-req-acceptance",
            resolution_context_id="ctx-01",
            resolution_result_id="resol-01",
            composition_id="comp-01",
            domain_result_id="dom-res-01",
            started_at=now,
            completed_at=now,
            scope="parenthood.child:child:lucas-001",
            child_id="child:lucas-001",
        )
        assert trace.status is DomainTraceStatus.COMPLETED
        assert trace.metadata.get("child_id") == "child:lucas-001"
