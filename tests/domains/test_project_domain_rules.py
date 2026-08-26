"""Phase 10.30 — Project Domain Reasoning Rules Tests."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from cmm.cognitive.reasoning_rule_contracts import (
    ReasoningRuleContext,
    ReasoningRuleResultStatus,
)
from cmm.development.analyzer import ProjectAnalyzer
from cmm.domains.project.catalog import (
    CANONICAL_PROJECT_RULE_IDS,
)
from cmm.domains.project.profile import (
    SOFTWARE_PROJECT_RULE_IDS,
)
from cmm.domains.project.rules import (
    build_project_rules,
    evaluate_dependency_consistency,
    evaluate_milestone_consistency,
    evaluate_project_decision_state,
    evaluate_project_progress_evidence,
    evaluate_project_resource_constraints,
    evaluate_project_scope_consistency,
    evaluate_project_status_transition,
    evaluate_project_temporal_validity,
)

# ── Generic Evaluators (Task 4) ───────────────────────────────────────────────


def test_evaluate_project_scope_consistency() -> None:
    declared = {
        "objective": "Build Core Subsystem",
        "deliverables": ["core_module", "tests"],
        "exclusions": ["ui_frontend", "external_api"],
    }

    # In scope
    res = evaluate_project_scope_consistency(
        declared,
        [
            {
                "id": "task_1",
                "deliverable": "core_module",
                "description": "core implementation",
            }
        ],
    )
    assert res["valid"] is True
    assert len(res["in_scope_items"]) == 1
    assert len(res["out_of_scope_items"]) == 0

    # Scope creep / excluded
    res_creep = evaluate_project_scope_consistency(
        declared,
        [{"id": "task_2", "deliverable": "ui_frontend", "description": "build UI"}],
    )
    assert res_creep["valid"] is False
    assert len(res_creep["out_of_scope_items"]) == 1


def test_evaluate_milestone_consistency() -> None:
    # Valid completed milestone with evidence
    valid_ms = [
        {
            "id": "m1",
            "title": "Milestone 1",
            "status": "completed",
            "evidence": ["commit:123", "test_report:pass"],
        },
        {"id": "m2", "title": "Milestone 2", "status": "active", "evidence": []},
    ]
    res_valid = evaluate_milestone_consistency(valid_ms)
    assert res_valid["valid"] is True
    assert len(res_valid["unsupported_completed_milestones"]) == 0

    # Completed milestone with no evidence
    invalid_ms = [
        {"id": "m1", "title": "Milestone 1", "status": "completed", "evidence": []},
    ]
    res_invalid = evaluate_milestone_consistency(invalid_ms)
    assert res_invalid["valid"] is False
    assert "m1" in res_invalid["unsupported_completed_milestones"]

    # Duplicate milestone IDs
    dup_ms = [
        {"id": "m1", "title": "Milestone 1", "status": "active"},
        {"id": "m1", "title": "Milestone 1 duplicate", "status": "active"},
    ]
    res_dup = evaluate_milestone_consistency(dup_ms)
    assert res_dup["valid"] is False
    assert "m1" in res_dup["duplicate_ids"]


def test_evaluate_dependency_consistency() -> None:
    # Acyclic graph
    deps = [
        {"source": "m1", "target": "m2"},
        {"source": "m2", "target": "m3"},
    ]
    res = evaluate_dependency_consistency(deps)
    assert res["valid"] is True
    assert len(res["cycles"]) == 0

    # Cycle preserved as blocker
    cycle_deps = [
        {"source": "m1", "target": "m2"},
        {"source": "m2", "target": "m1"},
    ]
    res_cycle = evaluate_dependency_consistency(cycle_deps)
    assert res_cycle["valid"] is False
    assert len(res_cycle["cycles"]) > 0
    assert len(res_cycle["blockers"]) > 0


def test_evaluate_project_status_transition() -> None:
    # Valid transition
    res = evaluate_project_status_transition("planned", "active")
    assert res["allowed"] is True

    # Completed without evidence
    res_comp_no_ev = evaluate_project_status_transition(
        "active", "completed", evidence=None
    )
    assert res_comp_no_ev["allowed"] is False
    assert res_comp_no_ev["reason"] == "missing_required_evidence"

    # Completed with evidence
    res_comp_ev = evaluate_project_status_transition(
        "active", "completed", evidence={"verified": True}
    )
    assert res_comp_ev["allowed"] is True

    # Unknown status fails closed
    res_unknown = evaluate_project_status_transition("active", "nearly_done")
    assert res_unknown["allowed"] is False
    assert "unknown_status" in res_unknown["reason"]


def test_evaluate_project_resource_constraints() -> None:
    resources = [
        {"kind": "developer_hours", "available": 40, "unit": "hours"},
    ]
    reqs = [
        {"resource": "developer_hours", "required": 30},
    ]
    res = evaluate_project_resource_constraints(resources, reqs)
    assert res["feasible"] is True

    reqs_exceeded = [
        {"resource": "developer_hours", "required": 60},
    ]
    res_exceeded = evaluate_project_resource_constraints(resources, reqs_exceeded)
    assert res_exceeded["feasible"] is False
    assert "developer_hours" in res_exceeded["bottlenecks"]

    # Unknown capacity preserved, not invented
    res_unknown = evaluate_project_resource_constraints(
        resources, [{"resource": "server_budget", "required": 500}]
    )
    assert res_unknown["feasible"] is None
    assert "server_budget" in res_unknown["unknown_capacity"]


def test_evaluate_project_decision_state() -> None:
    # proposal != decision
    res = evaluate_project_decision_state(
        "proposal", "decided", confirmation_evidence=None
    )
    assert res["allowed"] is False
    assert res["reason"] == "missing_required_evidence"

    res_dec = evaluate_project_decision_state(
        "proposal", "decided", confirmation_evidence={"confirmed": True}
    )
    assert res_dec["allowed"] is True

    # approved != applied
    res_app = evaluate_project_decision_state(
        "proposal", "applied", approval_evidence=None, execution_evidence=None
    )
    assert res_app["allowed"] is False

    res_applied = evaluate_project_decision_state(
        "approved",
        "applied",
        approval_evidence={"approval_id": "app:1"},
        execution_evidence={"execution_id": "exec:1"},
    )
    assert res_applied["allowed"] is True


def test_evaluate_project_temporal_validity() -> None:
    # Valid chronology
    milestones = [
        {"id": "m1", "target_date": "2026-09-01T00:00:00Z"},
        {"id": "m2", "target_date": "2026-10-01T00:00:00Z", "depends_on": "m1"},
    ]
    res = evaluate_project_temporal_validity(milestones)
    assert res["valid"] is True

    # Temporal conflict
    conflict_ms = [
        {"id": "m1", "target_date": "2026-10-01T00:00:00Z"},
        {"id": "m2", "target_date": "2026-09-01T00:00:00Z", "depends_on": "m1"},
    ]
    res_conf = evaluate_project_temporal_validity(conflict_ms)
    assert res_conf["valid"] is False
    assert len(res_conf["temporal_conflicts"]) > 0

    # Malformed date
    malformed_ms = [
        {"id": "m1", "target_date": "not-a-date"},
    ]
    res_malformed = evaluate_project_temporal_validity(malformed_ms)
    assert res_malformed["valid"] is False
    assert "m1" in res_malformed["malformed_dates"]


def test_evaluate_project_progress_evidence() -> None:
    claims = [{"id": "c1", "claim": "Feature X complete", "deliverable": "feat_x"}]
    authoritative = [
        {"deliverable": "feat_x", "status": "verified", "evidence": "test_pass"}
    ]

    res_pass = evaluate_project_progress_evidence(claims, authoritative)
    assert res_pass["supported"] is True
    assert "c1" in res_pass["verified_claims"]

    res_fail = evaluate_project_progress_evidence(claims, [])
    assert res_fail["supported"] is False
    assert "c1" in res_fail["unsupported_claims"]


# ── Software Rules (Task 5) ──────────────────────────────────────────────────


def test_software_rules_inactive_in_generic_context() -> None:
    rules = build_project_rules()
    assert len(rules) == 18
    assert tuple(r.definition.id for r in rules) == CANONICAL_PROJECT_RULE_IDS

    generic_context = ReasoningRuleContext(
        reasoning_id="reasoning:generic:1",
        timestamp=datetime.now(timezone.utc),
        metadata={"workflow_id": "project.project_setup"},
    )

    # Software rules (last 10 rules) must be no-op/not applicable in generic context
    software_rules = [r for r in rules if r.definition.id in SOFTWARE_PROJECT_RULE_IDS]
    assert len(software_rules) == 10

    for rule in software_rules:
        result = rule.evaluate(generic_context)
        assert result.status == ReasoningRuleResultStatus.APPLIED
        # Should not produce blocking findings or errors
        assert all(f.severity.value != "blocking" for f in result.findings)
        assert any(
            t.code == "SOFTWARE_CAPABILITY_INACTIVE" for t in result.trace_entries
        )


def test_software_rules_active_in_software_context() -> None:
    rules = build_project_rules()
    software_rules = {
        r.definition.id: r
        for r in rules
        if r.definition.id in SOFTWARE_PROJECT_RULE_IDS
    }

    software_context = ReasoningRuleContext(
        reasoning_id="reasoning:software:1",
        timestamp=datetime.now(timezone.utc),
        metadata={
            "workflow_id": "project.self_development",
            "architecture_findings": [
                {"contract": "api_contract", "status": "violated"}
            ],
            "validation_result": {"passed": False, "errors": ["test_failure"]},
            "technical_debt": [{"issue": "circular_import", "severity": "medium"}],
        },
    )
    project_context = ProjectAnalyzer().analyze(
        Path(__file__).resolve().parents[2],
        "project software rules",
        max_files=1,
    )

    arch_rule = software_rules["project.architecture_contract"]
    arch_res = arch_rule.evaluate(software_context, project_context=project_context)
    assert arch_res.status == ReasoningRuleResultStatus.APPLIED
    assert any(
        t.code == "ARCHITECTURE_CONTRACT_EVALUATED" for t in arch_res.trace_entries
    )

    val_rule = software_rules["project.validation_required"]
    val_res = val_rule.evaluate(software_context, project_context=project_context)
    assert val_res.status == ReasoningRuleResultStatus.APPLIED
    assert any(t.code == "VALIDATION_REQUIRED_EVALUATED" for t in val_res.trace_entries)


def test_no_forbidden_engines_in_rules_source() -> None:
    source = Path("cmm/domains/project/rules.py").read_text()
    forbidden_tokens = (
        "subprocess.run",
        "os.system",
        "shell=True",
        "PythonIndex(",
        "TechnicalMemory.for_project(",
        "ExecutionPipeline(",
    )
    for forbidden in forbidden_tokens:
        assert forbidden not in source, (
            f"Found forbidden token {forbidden!r} in rules.py"
        )
