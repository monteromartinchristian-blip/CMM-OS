"""Phase 10.22 — B6: Academic Workload (constraint pipeline).

The audit found the previous implementation only compared a raw total against a
full-time reference.  Workload planning must follow a staged pipeline: HARD
CONSTRAINTS -> FEASIBILITY -> PREFERENCES -> TRADE-OFFS -> SCENARIOS ->
PROPOSAL.  An authorized Health functional constraint (e.g. a reduced-load
cap) affects feasibility; clinical details are never consumed by the domain.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from cmm.cognitive.enums import ReasoningRuleResultStatus
from cmm.cognitive.reasoning_rule_contracts import ReasoningRuleContext
from cmm.domains.university import build_university_rules
from cmm.domains.university.rules import evaluate_academic_workload

T = datetime(2026, 8, 1, tzinfo=timezone.utc)


def _scenario(scenario_id, **values):
    return {"id": scenario_id, **values}


def _canonical_result(workload):
    rule = {
        r.definition.id: r
        for r in build_university_rules()
    }["university.academic_workload"]
    context = ReasoningRuleContext(
        reasoning_id="workload-production",
        timestamp=T,
        active_domains=("domain:university",),
        primary_domain="domain:university",
        metadata={"workload": workload},
    )
    return rule.evaluate(context)


def test_hard_constraint_unsatisfied_blocks_feasibility():
    """An unsatisfied hard constraint stops the pipeline before preferences."""
    result = evaluate_academic_workload(
        hard_constraints=({"id": "hc-1", "satisfied": False},)
    )
    assert result["feasible"] is False
    assert result["stage"] == "feasibility"
    assert result["proposal"] is None


def test_all_hard_constraints_satisfied_is_feasible():
    result = evaluate_academic_workload(
        hard_constraints=({"id": "hc-1", "satisfied": True},)
    )
    assert result["feasible"] is True
    assert result["stage"] == "preferences"


def test_preferences_applied_after_feasibility():
    result = evaluate_academic_workload(
        hard_constraints=({"id": "hc-1", "satisfied": True},),
        preferences=({"id": "pref-1", "rank": 1},),
    )
    assert result["stage"] == "preferences"
    assert result["preferences_applied"] is True


def test_tradeoffs_emitted_when_preferences_conflict():
    """When preferences conflict, trade-offs are surfaced before scenarios."""
    result = evaluate_academic_workload(
        hard_constraints=({"id": "hc-1", "satisfied": True},),
        preferences=(
            {"id": "pref-1", "rank": 1},
            {"id": "pref-2", "rank": 1},
        ),
    )
    assert result["stage"] == "tradeoffs"
    assert result["tradeoffs"]  # non-empty


def test_scenarios_produced_when_preferences_are_compatible():
    result = evaluate_academic_workload(
        hard_constraints=({"id": "hc-1", "satisfied": True},),
        preferences=(
            {"id": "pref-1", "rank": 1},
            {"id": "pref-2", "rank": 2},
        ),
    )
    assert result["stage"] == "scenarios"
    assert result["scenarios"]


def test_proposal_emitted_when_scenario_selected():
    """A proposal is only emitted at the final stage, never adopted."""
    result = evaluate_academic_workload(
        hard_constraints=({"id": "hc-1", "satisfied": True},),
        preferences=({"id": "pref-1", "rank": 1},),
        selected_scenario="sc-1",
    )
    assert result["stage"] == "proposal"
    assert result["proposal"] == "sc-1"
    assert result["adopted_decision"] is False


def test_health_constraint_affects_feasibility():
    """An authorized Health functional constraint (reduced-load cap) is a hard
    constraint that affects feasibility."""
    result = evaluate_academic_workload(
        total_ect=40,
        full_time_ect=30,
        health_constraint={"functional_cap_ect": 20, "authorized": True},
    )
    assert result["feasible"] is False
    assert result["stage"] == "feasibility"


def test_health_constraint_satisfied_is_feasible():
    result = evaluate_academic_workload(
        total_ect=15,
        full_time_ect=30,
        health_constraint={"functional_cap_ect": 20, "authorized": True},
    )
    assert result["feasible"] is True


def test_clinical_details_never_consumed():
    """Clinical details supplied by Health are never consumed by the domain."""
    result = evaluate_academic_workload(
        total_ect=15,
        full_time_ect=30,
        health_constraint={
            "functional_cap_ect": 20,
            "authorized": True,
            "clinical_details": "sensitive-diagnosis",
        },
    )
    assert result["clinical_details_consumed"] is False
    assert "clinical_details" not in result["consumed_factors"]


def test_unauthorized_health_constraint_ignored():
    result = evaluate_academic_workload(
        total_ect=40,
        full_time_ect=30,
        health_constraint={"functional_cap_ect": 20, "authorized": False},
    )
    assert result["feasible"] is True


def test_canonical_rule_preferred_scenario_that_violates_prerequisite_cannot_win():
    result = _canonical_result(
        {
            "scenarios": (
                _scenario(
                    "preferred",
                    speed=1,
                    prerequisites_met=False,
                    hard_constraints=(
                        {
                            "id": "prereq-preferred",
                            "kind": "prerequisite",
                            "field": "prerequisites_met",
                            "requirement": True,
                            "grounded": True,
                        },
                    ),
                ),
                _scenario(
                    "feasible",
                    speed=2,
                    prerequisites_met=True,
                ),
            ),
            "preferences": ({"dimension": "speed", "direction": "minimize"},),
        }
    )
    finding = result.findings[0]
    assert result.status is ReasoningRuleResultStatus.APPLIED
    assert finding.metadata["feasible_scenarios"] == ("feasible",)
    assert "preferred" in finding.metadata["infeasible_scenarios"]
    assert finding.metadata["ranking"] == ("feasible",)


def test_canonical_rule_ranks_feasible_scenarios_by_explicit_lower_workload_preference():
    result = _canonical_result(
        {
            "scenarios": (
                _scenario("a", workload=12),
                _scenario("b", workload=6),
            ),
            "preferences": ({"dimension": "workload", "direction": "minimize"},),
        }
    )
    finding = result.findings[0]
    assert finding.metadata["ranking"] == ("b", "a")


def test_canonical_rule_does_not_invent_order_without_preference():
    result = _canonical_result(
        {
            "scenarios": (
                _scenario("a", workload=12),
                _scenario("b", workload=6),
            )
        }
    )
    finding = result.findings[0]
    assert finding.metadata["feasible_scenarios"] == ("a", "b")
    assert finding.metadata["ranking"] == ()


def test_canonical_rule_missing_decision_critical_availability_is_unresolved():
    result = _canonical_result(
        {
            "scenarios": (
                _scenario(
                    "unknown",
                    hard_constraints=(
                        {
                            "id": "availability",
                            "kind": "availability",
                            "field": "available_hours",
                            "requirement": 10,
                            "grounded": True,
                            "critical": True,
                        },
                    ),
                ),
            )
        }
    )
    finding = result.findings[0]
    assert finding.code == "WORKLOAD_FEASIBILITY_UNCERTAIN"
    assert finding.metadata["feasibility_uncertain"] is True
    assert finding.metadata["unresolved_scenarios"] == ("unknown",)


def test_canonical_rule_health_functional_cap_changes_scenario_feasibility():
    result = _canonical_result(
        {
            "scenarios": (_scenario("full", credit_load=30),),
            "health_constraint": {"functional_cap_ect": 6, "authorized": True},
        }
    )
    finding = result.findings[0]
    assert finding.metadata["feasible_scenarios"] == ()
    assert finding.metadata["infeasible_scenarios"] == ("full",)


def test_canonical_rule_missing_preference_value_keeps_ranking_incomplete():
    result = _canonical_result(
        {
            "scenarios": (
                _scenario("known-hours", hours=5),
                _scenario("missing-hours"),
            ),
            "preferences": ({"dimension": "hours", "direction": "minimize"},),
        }
    )
    finding = result.findings[0]
    assert finding.metadata["feasible_scenarios"] == (
        "known-hours",
        "missing-hours",
    )
    assert finding.metadata["ranking"] == ()
    assert finding.metadata["ranking_incomplete"] is True


@pytest.mark.parametrize(
    "workload",
    (
        {"total_ect": "abc", "scenarios": (_scenario("a", hours=5),)},
        {"full_time_ect": "invalid", "scenarios": (_scenario("a", hours=5),)},
    ),
)
def test_canonical_rule_malformed_numeric_metadata_is_feasibility_unknown(workload):
    result = _canonical_result(workload)
    finding = result.findings[0]
    assert finding.code == "WORKLOAD_FEASIBILITY_UNCERTAIN"
    assert finding.metadata["numeric_metadata_unknown"] is True
    assert finding.metadata["feasibility_uncertain"] is True


def test_canonical_rule_incomplete_preference_ranking_is_order_invariant():
    result = _canonical_result(
        {
            "scenarios": (
                _scenario("missing-hours"),
                _scenario("known-hours", hours=5),
            ),
            "preferences": ({"dimension": "hours", "direction": "minimize"},),
        }
    )
    finding = result.findings[0]
    assert finding.metadata["ranking"] == ()
    assert finding.metadata["ranking_incomplete"] is True


# ── V7-B4: malformed collection-shaped metadata must not leak TypeError; ─────
# ── the rule must degrade to a conservative result. ───────────────────────────


def test_canonical_rule_scalar_hard_constraints_collection_does_not_crash():
    """A scalar ``hard_constraints`` value must not raise TypeError."""
    result = _canonical_result({"hard_constraints": 7, "total_ect": 30})
    assert result.status is not None
    assert result.findings


def test_canonical_rule_scalar_preferences_collection_does_not_crash():
    """A scalar ``preferences`` value must not raise TypeError."""
    result = _canonical_result({"preferences": 7, "total_ect": 30})
    assert result.status is not None
    assert result.findings


def test_canonical_rule_scalar_scenarios_collection_does_not_crash():
    """A scalar ``scenarios`` value must not raise TypeError."""
    result = _canonical_result({"scenarios": 7, "total_ect": 30})
    assert result.status is not None
    assert result.findings


# ── V8-B1/V8-B2: malformed collection evidence must not be silently treated ──
# ── as an empty collection, because malformed constraints are not equivalent ──
# ── to no constraints. ───────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "workload",
    (
        {
            "scenarios": (_scenario("s1", credit_load=30),),
            "hard_constraints": 7,
        },
        {
            "scenarios": (_scenario("s1", credit_load=30),),
            "preferences": 7,
        },
        {"scenarios": 7, "total_ect": 30},
    ),
)
def test_canonical_rule_malformed_top_level_collections_preserve_uncertainty(
    workload,
):
    """Malformed top-level collection-shaped metadata must not be treated as
    an empty collection: the result is uncertain and no definite proposal is
    emitted."""
    result = _canonical_result(workload)
    finding = result.findings[0]
    assert finding.code == "WORKLOAD_FEASIBILITY_UNCERTAIN"
    assert finding.metadata["feasibility_uncertain"] is True
    assert finding.metadata["proposal"] is None
    assert finding.metadata["feasible"] is False


def test_canonical_rule_nested_scenario_malformed_hard_constraints_uncertain():
    """A malformed nested ``scenario.hard_constraints`` value must not raise
    TypeError and must not certify the scenario as definitely feasible."""
    result = _canonical_result(
        {
            "scenarios": (
                {
                    "id": "s1",
                    "credit_load": 30,
                    "hard_constraints": 7,
                },
            ),
            "selected_scenario": "s1",
        }
    )
    finding = result.findings[0]
    assert result.status is ReasoningRuleResultStatus.APPLIED
    assert finding.code == "WORKLOAD_FEASIBILITY_UNCERTAIN"
    assert finding.metadata["feasibility_uncertain"] is True
    assert finding.metadata["proposal"] is None
    assert "s1" in finding.metadata["unresolved_scenarios"]


@pytest.mark.parametrize(
    "nested_value",
    ("bad", {"unexpected": "mapping"}, None),
)
def test_canonical_rule_nested_scenario_malformed_variants_do_not_crash(
    nested_value,
):
    """None and other malformed nested values must remain safe and uncertain."""
    result = _canonical_result(
        {
            "scenarios": (
                {
                    "id": "s1",
                    "credit_load": 30,
                    "hard_constraints": nested_value,
                },
            ),
            "selected_scenario": "s1",
        }
    )
    finding = result.findings[0]
    assert finding.code == "WORKLOAD_FEASIBILITY_UNCERTAIN"
    assert finding.metadata["feasibility_uncertain"] is True
    assert finding.metadata["proposal"] is None


def test_canonical_rule_empty_hard_constraints_remain_feasible():
    """A valid empty hard_constraints collection keeps legitimate empty
    semantics instead of being treated as malformed."""
    result = _canonical_result(
        {
            "scenarios": (_scenario("s1", credit_load=30),),
            "hard_constraints": [],
        }
    )
    finding = result.findings[0]
    assert finding.code == "WORKLOAD_ASSESSED"
    assert finding.metadata["feasibility_uncertain"] is False
    assert finding.metadata["feasible"] is True
# ── V9-B1: element-aware collection validation.  A valid list/tuple container ──
# ── with a malformed member is NOT fully valid evidence. ─────────────────────


def test_canonical_rule_hard_constraint_scalar_element_uncertain():
    """``hard_constraints=[7]`` is malformed evidence inside a valid container:
    it must evaluate as uncertain, not as if the constraint did not exist."""
    result = _canonical_result(
        {
            "hard_constraints": [7],
            "scenarios": (_scenario("s1", credit_load=30),),
            "selected_scenario": "s1",
        }
    )
    finding = result.findings[0]
    assert result.status is ReasoningRuleResultStatus.APPLIED
    assert finding.code == "WORKLOAD_FEASIBILITY_UNCERTAIN"
    assert finding.metadata["feasibility_uncertain"] is True
    assert finding.metadata["feasible"] is False
    assert finding.metadata["proposal"] is None


def test_canonical_rule_hard_constraint_blank_string_element_uncertain():
    """An opaque (non-Mapping) member is malformed evidence, not absence."""
    result = _canonical_result(
        {
            "hard_constraints": ["bad"],
            "scenarios": (_scenario("s1", credit_load=30),),
            "selected_scenario": "s1",
        }
    )
    finding = result.findings[0]
    assert finding.code == "WORKLOAD_FEASIBILITY_UNCERTAIN"
    assert finding.metadata["feasibility_uncertain"] is True
    assert finding.metadata["feasible"] is False
    assert finding.metadata["proposal"] is None


def test_canonical_rule_preference_scalar_element_uncertain():
    """``preferences=[7]`` must not become "no preferences"."""
    result = _canonical_result(
        {
            "preferences": [7],
            "scenarios": (_scenario("s1", credit_load=30),),
            "selected_scenario": "s1",
        }
    )
    finding = result.findings[0]
    assert finding.code == "WORKLOAD_FEASIBILITY_UNCERTAIN"
    assert finding.metadata["feasibility_uncertain"] is True
    assert finding.metadata["feasible"] is False
    assert finding.metadata["proposal"] is None


def test_canonical_rule_scenario_malformed_member_uncertain():
    """A malformed scenario member inside a valid scenarios container must be
    preserved as malformed evidence; the scenario set cannot be fully
    characterized and no strong conclusion is drawn."""
    result = _canonical_result(
        {
            "scenarios": [7, _scenario("s1", credit_load=30)],
            "selected_scenario": "s1",
        }
    )
    finding = result.findings[0]
    assert finding.code == "WORKLOAD_FEASIBILITY_UNCERTAIN"
    assert finding.metadata["feasibility_uncertain"] is True
    assert finding.metadata["feasible"] is False
    assert finding.metadata["proposal"] is None


def test_canonical_rule_nested_scenario_hard_constraint_scalar_element_uncertain():
    """``scenario.hard_constraints=[7]`` leaves the scenario unresolved and
    yields no proposal; it must not become definitely feasible."""
    result = _canonical_result(
        {
            "scenarios": (
                {
                    "id": "s1",
                    "credit_load": 30,
                    "hard_constraints": [7],
                },
            ),
            "selected_scenario": "s1",
        }
    )
    finding = result.findings[0]
    assert finding.code == "WORKLOAD_FEASIBILITY_UNCERTAIN"
    assert finding.metadata["feasibility_uncertain"] is True
    assert finding.metadata["proposal"] is None
    assert "s1" in finding.metadata["unresolved_scenarios"]


def test_canonical_rule_valid_mapping_constraints_remain_feasible():
    """Valid Mapping-only constraints retain normal feasibility semantics."""
    result = _canonical_result(
        {
            "hard_constraints": (
                {
                    "id": "hc-1",
                    "kind": "workload_cap",
                    "field": "credit_load",
                    "limit": 30,
                    "grounded": True,
                },
            ),
            "scenarios": (_scenario("s1", credit_load=30),),
            "selected_scenario": "s1",
        }
    )
    finding = result.findings[0]
    assert finding.code == "WORKLOAD_ASSESSED"
    assert finding.metadata["feasibility_uncertain"] is False
    assert finding.metadata["feasible"] is True


# ── V10-B1/B3/B4: direct helper malformed containers, numeric/bool strict ────


def test_direct_helper_malformed_hard_constraints_container_no_exception():
    """hard_constraints=7 must not raise and must leave feasibility unknown."""
    result = evaluate_academic_workload(total_ect=30, hard_constraints=7)
    assert result["feasibility_uncertain"] is True
    assert result["feasible"] is False
    assert result["proposal"] is None


def test_direct_helper_malformed_preferences_container_no_exception():
    """preferences=7 must not raise and must produce no proposal."""
    result = evaluate_academic_workload(
        total_ect=30,
        preferences=7,
        selected_scenario="s1",
    )
    assert result["feasible"] is False
    assert result["proposal"] is None


def test_direct_helper_malformed_scenarios_container_no_exception():
    """scenarios=7 must not raise and must produce no proposal."""
    result = evaluate_academic_workload(total_ect=30, scenarios=7)
    assert result["feasibility_uncertain"] is True
    assert result["proposal"] is None


def test_direct_helper_malformed_hard_constraint_member_uncertain():
    """hard_constraints=(7,) must not become feasible as if no constraint."""
    result = evaluate_academic_workload(total_ect=30, hard_constraints=(7,))
    assert result["feasible"] is False
    assert result["feasibility_uncertain"] is True


def test_direct_helper_malformed_preference_member_no_proposal():
    """preferences=(7,) must not become no preferences / a clean proposal."""
    result = evaluate_academic_workload(
        total_ect=30,
        preferences=(7,),
        selected_scenario="s1",
    )
    assert result["feasible"] is False
    assert result["proposal"] is None
    assert result.get("preferences_malformed") is True


def test_direct_helper_malformed_scenario_member_no_proposal():
    """scenarios=(7, valid) must not characterize a clean scenario set."""
    result = evaluate_academic_workload(
        total_ect=30,
        scenarios=(7, _scenario("s1", credit_load=30)),
        selected_scenario="s1",
    )
    assert result["feasibility_uncertain"] is True
    assert result["proposal"] is None
    assert result.get("scenarios_malformed") is True


def test_direct_helper_empty_preference_mapping_is_malformed_evidence():
    """A Mapping preference without a usable dimension is malformed evidence,
    not an absence of preferences."""
    result = evaluate_academic_workload(
        scenarios=(_scenario("s1", credit_load=30),),
        preferences=({},),
        selected_scenario="s1",
    )
    assert result["feasibility_uncertain"] is True
    assert result["proposal"] is None
    assert result.get("preferences_malformed") is True


def test_direct_helper_anonymous_scenario_is_malformed_evidence():
    """A Mapping scenario without a usable id makes the scenario set
    incomplete; it must not disappear."""
    result = evaluate_academic_workload(
        scenarios=({}, _scenario("s1", credit_load=30)),
        selected_scenario="s1",
    )
    assert result["feasibility_uncertain"] is True
    assert result["proposal"] is None
    assert result.get("scenarios_malformed") is True


def test_direct_helper_unknown_preference_direction_is_unresolved():
    """direction='sideways' must not silently become minimize/ascending."""
    result = evaluate_academic_workload(
        scenarios=(
            _scenario("a", hours=10),
            _scenario("b", hours=5),
        ),
        preferences=({"dimension": "hours", "direction": "sideways"},),
    )
    assert result["ranking"] == ()
    assert result["ranking_incomplete"] is True
    assert result["proposal"] is None


def test_direct_helper_numeric_string_total_ect_no_type_error():
    """total_ect='abc' with an authorized health cap must not raise TypeError."""
    result = evaluate_academic_workload(
        total_ect="abc",
        health_constraint={"authorized": True, "functional_cap_ect": 20},
    )
    assert result["feasibility_uncertain"] is True
    assert result["proposal"] is None


def test_canonical_rule_workload_boolean_actual_string_false_does_not_satisfy():
    """scenario.prereq_met='false' against expected=True must NOT satisfy the
    hard constraint or produce a proposal."""
    result = _canonical_result(
        {
            "scenarios": (
                {
                    "id": "s1",
                    "prereq_met": "false",
                },
            ),
            "hard_constraints": (
                {
                    "id": "prereq",
                    "kind": "prerequisite",
                    "field": "prereq_met",
                    "requirement": True,
                    "grounded": True,
                },
            ),
            "selected_scenario": "s1",
        }
    )
    finding = result.findings[0]
    assert finding.code == "WORKLOAD_FEASIBILITY_UNCERTAIN"
    assert finding.metadata["feasible"] is False
    assert finding.metadata["proposal"] is None


# ── V10-B4 positive regressions: omitted direction / closed directions ───────


def test_direct_helper_omitted_direction_uses_documented_maximize_default():
    """A valid preference may omit direction; the documented default remains
    maximize instead of being treated as malformed."""
    result = evaluate_academic_workload(
        scenarios=(
            _scenario("low", hours=5),
            _scenario("high", hours=10),
        ),
        preferences=({"dimension": "hours"},),
    )
    assert result["ranking_incomplete"] is False
    assert result["ranking"] == ("high", "low")


def test_direct_helper_closed_direction_maximize_is_deterministic():
    result = evaluate_academic_workload(
        scenarios=(
            _scenario("low", hours=5),
            _scenario("high", hours=10),
        ),
        preferences=({"dimension": "hours", "direction": "maximize"},),
    )
    assert result["ranking"] == ("high", "low")
    assert result["ranking_incomplete"] is False


def test_direct_helper_closed_direction_minimize_is_deterministic():
    result = evaluate_academic_workload(
        scenarios=(
            _scenario("low", hours=5),
            _scenario("high", hours=10),
        ),
        preferences=({"dimension": "hours", "direction": "minimize"},),
    )
    assert result["ranking"] == ("low", "high")
    assert result["ranking_incomplete"] is False
