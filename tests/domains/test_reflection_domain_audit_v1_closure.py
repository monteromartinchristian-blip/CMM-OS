"""Phase 10.24 — Reflection Domain Audit V1 remediation closure suite.

This file permanently encodes the adversarial reproductions from
``the historical Phase 10.24 independent Audit V1 findings`` and proves each
Important/Minor finding is closed through its canonical surface (helpers,
operations, presentation, and the shared workflow runtime).

Every assertion below is a real executable proof; no gate string is hard-coded
without a live assertion behind it.
"""

from __future__ import annotations

import inspect
import itertools
import json
from datetime import datetime, timezone

from cmm.domains.memory_contracts import DomainMemoryApprovalDecisionSnapshot
from cmm.domains.reflection.operations import (
    build_personal_timeline_result,
    extract_beliefs_result,
    generate_summary_result,
    prepare_notion_entry_result,
    review_decision_result,
    structure_reflection_result,
)
from cmm.domains.reflection.presentation import (
    present_reflection_result,
    present_state,
)
from cmm.domains.reflection.rules import (
    classify_belief_evidence,
    classify_persistence,
    compare_reflection_versions,
    evaluate_ambivalence,
    evaluate_hypotheses,
    evaluate_open_questions,
    evaluate_persistence_basis,
    map_interests,
    no_forced_conclusion_policy,
)
from cmm.workflows.contracts import WorkflowDefinition, WorkflowNode
from cmm.workflows.engine import NodeExecution, WorkflowEngine
from cmm.workflows.enums import WorkflowRunStatus

# ─────────────────────────────────────────────────────────────────────────────
# Shared workflow VALIDATE helper (V1-I8)
# ─────────────────────────────────────────────────────────────────────────────


def _run_validate_workflow(
    condition, *, producer_output=None, metadata=None, inputs=None
):
    def adapter(node, run):
        if node.node_id == "producer":
            return NodeExecution.complete(producer_output or {"ok": True})
        return NodeExecution.complete({"ok": True})

    definition = WorkflowDefinition(
        "validate.flow",
        "1.0.0",
        "ValidateFlow",
        nodes=(
            WorkflowNode(
                "producer",
                "execute_operation",
                "Producer",
                operation_id="op.x",
                operation_version="1.0.0",
            ),
            WorkflowNode(
                "validate",
                "validate",
                "Validate",
                dependencies=("producer",),
                wait_condition=condition,
            ),
            WorkflowNode("finish", "complete", "Finish", dependencies=("validate",)),
        ),
        metadata=metadata or {},
    )
    engine = WorkflowEngine(
        definition,
        id_factory=lambda: "run-1",
        clock=lambda: datetime.now(timezone.utc),
        node_adapter=adapter,
    )
    return engine.start(inputs or {})


# ─────────────────────────────────────────────────────────────────────────────
# V1-I1 — duplicate/conflict fail-closed
# ─────────────────────────────────────────────────────────────────────────────


def test_hypothesis_identity_collision_fails_closed():
    result = evaluate_hypotheses(
        hypotheses=(
            {"identity": "h1", "statement": "A", "supporting_ids": ["s1"]},
            {"identity": "h1", "statement": "NOT A", "supporting_ids": ["s2"]},
        )
    )
    assert "h1" in result["collision_ids"]
    assert result["unresolved"] is True
    assert result["evidence_state"] == "conflicting"
    # no clean stronger ranking for the collided identity
    assert all(h["relative_strength"] is None for h in result["hypotheses"])


def test_hypothesis_collision_order_invariant():
    def _canonical(order):
        result = evaluate_hypotheses(
            hypotheses=tuple(
                {"identity": i, "statement": s, "supporting_ids": ["s"]}
                for i, s in order
            )
        )
        return (
            result["unresolved"],
            result["evidence_state"],
            frozenset(result["collision_ids"]),
        )

    a = (("h1", "A"), ("h1", "NOT A"))
    b = (("h1", "NOT A"), ("h1", "A"))
    assert _canonical(a) == _canonical(b)


def test_ambivalence_identity_collision_fails_closed():
    result = evaluate_ambivalence(
        records=(
            {
                "identity": "p1",
                "statement": "want closeness",
                "kind": "need",
                "context": "c",
                "temporal": "t",
                "polarity": 1,
            },
            {
                "identity": "p1",
                "statement": "want distance",
                "kind": "need",
                "context": "c",
                "temporal": "t",
                "polarity": -1,
            },
        )
    )
    assert "p1" in result["collision_ids"]
    assert result["conflict_state"] in ("conflicting", "unresolved", "ambivalent")
    assert result["evidence_state"] != "grounded"


def test_counterevidence_not_bypassed_by_evidence_count():
    result = classify_belief_evidence(
        records=(
            {
                "identity": "e1",
                "kind": "evidence",
                "statement": "supports",
                "source": "s1",
            },
            {
                "identity": "e2",
                "kind": "evidence",
                "statement": "supports",
                "source": "s2",
            },
            {
                "identity": "c1",
                "kind": "counterevidence",
                "statement": "against",
                "source": "s3",
            },
        )
    )
    assert result["conflict_state"] == "conflicting"
    assert result["unresolved"] is True
    assert result["evidence_state"] == "conflicting"


# ─────────────────────────────────────────────────────────────────────────────
# V1-I2 — temporal normalization
# ─────────────────────────────────────────────────────────────────────────────


def test_equal_time_subgroup_remains_ambiguous():
    result = compare_reflection_versions(
        versions=(
            {
                "version_id": "v1",
                "observed_at": "2029-01-15T00:00:00Z",
                "content": "alpha",
            },
            {
                "version_id": "v2",
                "observed_at": "2029-01-15T03:00:00+03:00",
                "content": "beta",
            },
            {
                "version_id": "v3",
                "observed_at": "2029-01-16T00:00:00Z",
                "content": "gamma",
            },
        )
    )
    # v1 and v2 are the same instant; no directional change inside that subgroup
    assert result["equal_timestamps_no_evolution"] is True
    states = {v["version_id"]: v["state"] for v in result["versions"]}
    assert states["v1"] == "simultaneous"
    assert states["v2"] == "simultaneous"
    changes = {(c["from_version_id"], c["to_version_id"]) for c in result["changes"]}
    assert ("v1", "v2") not in changes


def test_timeline_orders_by_normalized_instant_not_raw_text():
    result = build_personal_timeline_result(
        events=(
            {"event_id": "A", "observed_at": "2029-01-15T23:00:00+14:00"},  # 09:00Z
            {"event_id": "B", "observed_at": "2029-01-15T10:00:00Z"},  # 10:00Z
        )
    )
    assert [e["event_id"] for e in result["events"]] == ["A", "B"]


def test_temporal_permutation_identical():
    versions = (
        {"version_id": "v1", "observed_at": "2029-01-15T00:00:00Z", "content": "a"},
        {
            "version_id": "v2",
            "observed_at": "2029-01-15T00:00:00+00:00",
            "content": "b",
        },
        {"version_id": "v3", "observed_at": "2029-01-16T00:00:00Z", "content": "c"},
    )
    canonical = {
        (
            compare_reflection_versions(versions=tuple(order))["chronology_state"],
            compare_reflection_versions(versions=tuple(order))[
                "equal_timestamps_no_evolution"
            ],
        )
        for order in itertools.permutations(versions)
    }
    assert len(canonical) == 1


# ─────────────────────────────────────────────────────────────────────────────
# V1-I3 — source-grounded interest mapping
# ─────────────────────────────────────────────────────────────────────────────


def test_unsupported_source_kinds_not_grounded():
    for kind in (
        "synthetic_model_output",
        "MEMORY_SUMMARY",
        "memory_summary",
        "memory_entry",
        "unknown",
        "model_summary",
    ):
        result = map_interests(
            records=({"interest": "x", "source": "s1", "source_kind": kind},)
        )
        candidate = result["interest_candidates"][0]
        assert candidate["grounded_evidence_count"] == 0
        assert candidate["independent_grounded_count"] == 0
        assert result["evidence_state"] != "grounded"


def test_valid_grounded_user_source_counts():
    result = map_interests(
        records=({"interest": "x", "source": "msg:1", "source_kind": "user_statement"},)
    )
    candidate = result["interest_candidates"][0]
    assert candidate["grounded_evidence_count"] == 1
    assert result["evidence_state"] == "grounded"


def test_case_variant_user_source_grounds_via_allowlist():
    result = map_interests(
        records=({"interest": "x", "source": "msg:1", "source_kind": "User_Statement"},)
    )
    assert result["interest_candidates"][0]["grounded_evidence_count"] == 1


def test_duplicate_valid_source_no_corroboration():
    result = map_interests(
        records=(
            {"interest": "x", "source": "s1", "source_kind": "user_statement"},
            {"interest": "x", "source": "s1", "source_kind": "user_statement"},
        )
    )
    assert result["interest_candidates"][0]["grounded_evidence_count"] == 1


def test_model_only_interest_not_grounded_top_level():
    result = map_interests(
        records=(
            {
                "interest": "photography",
                "source": "model:1",
                "source_kind": "model_summary",
            },
        )
    )
    assert result["interest_candidates"][0]["grounded_evidence_count"] == 0
    assert result["evidence_state"] != "grounded"


# ─────────────────────────────────────────────────────────────────────────────
# V1-I4 — confirmed persistence bound to shared confirmation
# ─────────────────────────────────────────────────────────────────────────────


def test_raw_true_alone_is_not_complete_confirmation():
    record = classify_persistence(
        {"pattern": "fixed identity", "sources": ("msg:1", "msg:2")},
        confirmation=True,
    )
    assert record["confirmed"] is False
    assert record["authorization_accepted"] is False


from cmm.domains.memory_contracts import (
    DomainMemoryApprovalRequestSnapshot,
    DomainMemoryCapability,
    DomainMemoryPermissionDecisionSnapshot,
    DomainMemoryReference,
    DomainMemoryReferenceInventory,
    DomainMemoryReferenceKind,
    DomainMemorySensitivityLevel,
    DomainMemoryTraceSnapshot,
    DomainMemoryViewSnapshot,
)
from cmm.domains.reflection.memory import (
    build_reflection_memory_binding,
    build_reflection_memory_proposal,
    build_reflection_memory_view,
    build_reflection_memory_view_request,
)


def _valid_confirmation_chain(
    proposal_id: str = "prop-1",
    *,
    approved: bool = True,
):
    ref = DomainMemoryReference(
        reference_id=f"ref:{proposal_id}",
        kind=DomainMemoryReferenceKind.KNOWLEDGE_ITEM,
        canonical_id=f"item:{proposal_id}",
        domain_id="domain:reflection",
        applicable_domains=("domain:reflection",),
        evidence_ids=("ev:1",),
        resource_ids=("res:1",),
    )
    permission = DomainMemoryPermissionDecisionSnapshot(
        decision_id=f"perm:{proposal_id}",
        allowed=True,
        capabilities=(DomainMemoryCapability.PROPOSE,),
        source_domain_id="domain:reflection",
        target_domain_id="domain:reflection",
        sensitivity_levels=(DomainMemorySensitivityLevel.NORMAL,),
    )
    view_request = build_reflection_memory_view_request(
        request_id=f"req:{proposal_id}",
        trace_id=f"trace:{proposal_id}",
        requested_kinds=(DomainMemoryReferenceKind.KNOWLEDGE_ITEM,),
        candidates=(ref,),
        permission_decision_ids=(f"perm:{proposal_id}",),
    )
    proposal = build_reflection_memory_proposal(
        proposal_id=proposal_id,
        affected_reference_ids=(f"ref:{proposal_id}",),
    )
    temp_inventory = DomainMemoryReferenceInventory(
        references=(ref,),
        traces=(
            DomainMemoryTraceSnapshot(
                trace_id=f"trace:{proposal_id}", primary_domain="domain:reflection"
            ),
        ),
        permission_decisions=(permission,),
    )
    view = build_reflection_memory_view(request=view_request, inventory=temp_inventory)
    binding = build_reflection_memory_binding(
        proposal=proposal,
        view=view,
        trace_id=f"trace:{proposal_id}",
        permission_decision_ids=(f"perm:{proposal_id}",),
        approval_request_ids=(f"appr-req:{proposal_id}",),
        approval_decision_ids=(f"appr-dec:{proposal_id}",),
    )
    inventory = DomainMemoryReferenceInventory(
        references=(ref,),
        proposals=(proposal,),
        permission_decisions=(permission,),
        approval_requests=(
            DomainMemoryApprovalRequestSnapshot(
                request_id=f"appr-req:{proposal_id}", proposal_id=proposal_id
            ),
        ),
        approval_decisions=(
            DomainMemoryApprovalDecisionSnapshot(
                decision_id=f"appr-dec:{proposal_id}",
                request_id=f"appr-req:{proposal_id}",
                approved=approved,
            ),
        ),
        traces=(
            DomainMemoryTraceSnapshot(
                trace_id=f"trace:{proposal_id}", primary_domain="domain:reflection"
            ),
        ),
        views=(
            DomainMemoryViewSnapshot(
                view_id=view.view_id,
                request_id=view.request_id,
                primary_domain=view.primary_domain,
                trace_id=view.trace_id,
                view_digest=view.content_digest,
            ),
        ),
    )
    return binding, inventory


def test_shared_confirmation_reference_plus_grounded_provenance_confirms():
    binding, inventory = _valid_confirmation_chain(
        proposal_id="prop-v1-1", approved=True
    )
    record = classify_persistence(
        {
            "proposal_id": "prop-v1-1",
            "pattern": "fixed identity",
            "sources": ("msg:1", "msg:2"),
        },
        confirmation_binding=binding,
        confirmation_inventory=inventory,
    )
    assert record["confirmed"] is True
    assert record["persistence_state"] == "confirmed"


def test_nonliteral_confirmation_denied():
    for raw in (False, "true", 1, None, {}, {"approved": "yes"}, []):
        record = classify_persistence(
            {"pattern": "fixed identity", "sources": ("msg:1",)},
            confirmation=raw,
        )
        assert record["confirmed"] is False
        assert record["persistence_state"] != "confirmed"


def test_model_or_memory_summary_provenance_not_independently_grounded():
    binding, inventory = _valid_confirmation_chain(
        proposal_id="prop-v1-2", approved=True
    )
    for sources in (("model:1",), ("memory:summary:1",), ("memory:1",), ("summary:1",)):
        record = classify_persistence(
            {"proposal_id": "prop-v1-2", "pattern": "x", "sources": sources},
            confirmation_binding=binding,
            confirmation_inventory=inventory,
        )
        assert record["confirmed"] is False
        assert record["basis_sufficient"] is False


# ─────────────────────────────────────────────────────────────────────────────
# V1-I5 — presentation fail-closed literal states
# ─────────────────────────────────────────────────────────────────────────────


def test_presentation_malformed_persistence_decision_fail_closed():
    presented = present_reflection_result(
        {
            "persistent_confirmed": "false",
            "decision_adopted": "false",
            "eligible_for_confirmation": "false",
        }
    )
    assert presented["persistent_confirmed"] is False
    assert presented["decision_adopted"] is False
    assert presented["persistence_state"] != "confirmed"
    assert presented["decision_state"] == "not-adopted"


def test_present_state_bare_boolean_is_not_confirmed():
    assert present_state(True) == "unknown"
    assert present_state(False) == "unknown"


def test_presentation_primitive_matrix_fail_closed():
    for raw in ("true", "false", 1, 0, -1, None, {}, [], ()):
        presented = present_reflection_result(
            {"persistent_confirmed": raw, "decision_adopted": raw}
        )
        assert presented["persistent_confirmed"] is False
        assert presented["decision_adopted"] is False
    # literal True still maps
    assert (
        present_reflection_result(
            {"persistent_confirmed": True, "decision_adopted": True}
        )["persistent_confirmed"]
        is True
    )


def test_interest_candidate_state_not_contradictory():
    presented = present_reflection_result(
        {
            "unresolved": False,
            "interest_candidates": [
                {
                    "interest": "photography",
                    "persistent_confirmed": "false",
                    "sources": ("m",),
                }
            ],
            "persistent_confirmed": False,
        }
    )
    candidate = presented["interest_candidates"][0]
    assert candidate["persistent_confirmed"] is False
    assert candidate["presentation_state"] == "pending-confirmation"


# ─────────────────────────────────────────────────────────────────────────────
# V1-I6 — diagnosis / restricted-inference enforcement
# ─────────────────────────────────────────────────────────────────────────────


def test_diagnostic_hypothesis_is_not_safe_non_diagnostic():
    result = evaluate_hypotheses(
        hypotheses=(
            {
                "identity": "dx1",
                "statement": "You have bipolar disorder",
                "supporting_ids": ("msg:1",),
            },
        )
    )
    hypothesis = result["hypotheses"][0]
    assert hypothesis["diagnostic"] is True
    assert hypothesis["restricted_inference"] is True
    assert hypothesis["relative_strength"] is None
    assert result["no_diagnosis"] is False


def test_identity_classification_forms_detected():
    for statement in (
        "You are narcissistic",
        "You definitely have an attachment disorder",
        "You are a psychopath",
    ):
        result = evaluate_hypotheses(
            hypotheses=(
                {
                    "identity": "dx",
                    "statement": statement,
                    "supporting_ids": ("s",),
                },
            )
        )
        assert result["hypotheses"][0]["diagnostic"] is True


def test_diagnostic_statement_not_presented_verbatim():
    presented = present_reflection_result(
        {
            "unresolved": False,
            "hypotheses": [
                {"identity": "dx1", "statement": "You have bipolar disorder"}
            ],
        }
    )
    hypothesis = presented["hypotheses"][0]
    assert hypothesis["diagnosis"] is True
    assert "bipolar" not in hypothesis["statement"].lower()
    assert "restricted" in hypothesis["statement"].lower()


def test_prudent_hypothesis_still_possible():
    result = evaluate_hypotheses(
        hypotheses=(
            {
                "identity": "h1",
                "statement": "maybe I am avoiding conflict",
                "supporting_ids": ("s1",),
            },
        )
    )
    assert result["hypotheses"][0]["diagnostic"] is False
    assert result["no_diagnosis"] is True


# ─────────────────────────────────────────────────────────────────────────────
# V1-I7 — no-forced-conclusion / certainty
# ─────────────────────────────────────────────────────────────────────────────


def test_unsupported_certainty_variants_cannot_close_unresolved():
    for text in (
        "This definitely proves I am broken",
        "The real cause is obviously trauma",
        "Esto demuestra que soy una persona narcisista",
    ):
        result = no_forced_conclusion_policy({"unresolved": True, "conclusion": text})
        assert result["forced_conclusion"] is True
        assert result["valid_unresolved_completion"] is False
        assert result["unsupported_certainty"]


def test_unresolved_without_certainty_is_valid_completion():
    result = no_forced_conclusion_policy(
        {"unresolved": True, "open_questions": ("why?",)}
    )
    assert result["forced_conclusion"] is False
    assert result["valid_unresolved_completion"] is True


def test_summary_certainty_override_cannot_increase_certainty():
    result = generate_summary_result(
        source={"unresolved": True}, certainty_override="raise wording"
    )
    assert result["certainty_increased"] is False
    assert result["certainty_override_rejected"] is True


# ─────────────────────────────────────────────────────────────────────────────
# V1-I8 — shared executable VALIDATE gates
# ─────────────────────────────────────────────────────────────────────────────


def test_workflow_validate_gate_true_completes():
    result = _run_validate_workflow({"flag": True}, producer_output={"flag": True})
    assert result.run.status is WorkflowRunStatus.COMPLETED


def test_workflow_validate_gate_false_blocks():
    result = _run_validate_workflow({"flag": False}, producer_output={"flag": True})
    assert result.run.status is WorkflowRunStatus.FAILED
    assert result.run.error_code == "validate.condition_false"


def test_workflow_validate_gate_missing_condition_fails_closed():
    result = _run_validate_workflow({}, producer_output={"flag": True})
    assert result.run.status is WorkflowRunStatus.FAILED
    assert result.run.error_code == "validate.condition_missing"


def test_workflow_validate_gate_unknown_condition_fails_closed():
    result = _run_validate_workflow({"missing": True}, producer_output={"other": 1})
    assert result.run.status is WorkflowRunStatus.FAILED
    assert result.run.error_code == "validate.condition_unknown"


def test_workflow_validate_gate_metadata_condition():
    result = _run_validate_workflow({"meta_true": True}, metadata={"meta_true": True})
    assert result.run.status is WorkflowRunStatus.COMPLETED


def test_workflow_validate_gate_executable():
    positive = _run_validate_workflow({"flag": True}, producer_output={"flag": True})
    negative = _run_validate_workflow({"flag": False}, producer_output={"flag": True})
    assert positive.run.status is WorkflowRunStatus.COMPLETED
    assert negative.run.status is WorkflowRunStatus.FAILED


# ─────────────────────────────────────────────────────────────────────────────
# V1-I8 — Reflection workflow VALIDATE nodes actually block invalid states
# ─────────────────────────────────────────────────────────────────────────────


def _run_reflection_workflow_blocking(workflow_id, producer_node_id, producer_output):
    from cmm.domains.reflection import build_reflection_workflow_definitions
    from cmm.domains.workflow_contracts import DomainWorkflowContext
    from cmm.domains.workflow_execution import DomainWorkflowExecutor

    wf = next(
        w
        for w in build_reflection_workflow_definitions()
        if w.workflow_id == workflow_id
    )

    class _Ids:
        def __init__(self):
            self.value = 0

        def __call__(self):
            self.value += 1
            return f"id-{self.value}"

    def adapter(node, run):
        if node.node_id == producer_node_id:
            return NodeExecution.complete(producer_output)
        return NodeExecution.complete({"ok": True})

    executor = DomainWorkflowExecutor(id_factory=_Ids(), operation_adapter=adapter)
    context = DomainWorkflowContext(
        primary_domain_id="domain:reflection",
        known_domain_ids=frozenset({"domain:reflection", "domain:general"}),
        available_resources=frozenset(wf.required_resources),
        available_operations=frozenset(
            n.operation_id for n in wf.nodes if n.operation_id
        ),
    )
    return executor.execute(wf, context, {})


def test_reflection_no_decision_adoption_blocks():
    run = _run_reflection_workflow_blocking(
        "reflection.decision_reflection",
        "decision",
        {"decision_adopted": True},
    )
    assert run.status is not WorkflowRunStatus.COMPLETED
    assert run.execution_result.node_results["no_adoption"].status.value == "failed"


def test_reflection_no_identity_classification_blocks():
    run = _run_reflection_workflow_blocking(
        "reflection.identity_narrative_review",
        "compare",
        {"identity_not_classified": False},
    )
    assert run.status is not WorkflowRunStatus.COMPLETED
    assert (
        run.execution_result.node_results["no_classification"].status.value == "failed"
    )


def test_reflection_grounded_chronology_only_blocks():
    run = _run_reflection_workflow_blocking(
        "reflection.longitudinal_review",
        "compare",
        {"grounded_chronology_required": False},
    )
    assert run.status is not WorkflowRunStatus.COMPLETED
    assert (
        run.execution_result.node_results["grounded_chronology"].status.value
        == "failed"
    )


def test_reflection_validate_unresolved_completion_blocks():
    run = _run_reflection_workflow_blocking(
        "reflection.personal_question_exploration",
        "questions",
        {"unresolved_completion_allowed": False},
    )
    assert run.status is not WorkflowRunStatus.COMPLETED
    assert run.execution_result.node_results["validate"].status.value == "failed"


# ─────────────────────────────────────────────────────────────────────────────
# V1-I9 — strict JSON / no-exception public helpers
# ─────────────────────────────────────────────────────────────────────────────


def test_nan_inf_never_escape_public_output():
    result = classify_belief_evidence(
        records=(
            {
                "identity": "e",
                "kind": "evidence",
                "statement": "x",
                "source": "s",
                "value": float("nan"),
            },
        )
    )
    assert result["evidence"][0]["value"] is None
    json.dumps(result, allow_nan=False)

    structure = structure_reflection_result(
        material=({"level": "belief", "content": float("inf")},)
    )
    json.dumps(structure, allow_nan=False)

    review = review_decision_result(decision_candidate=float("nan"))
    json.dumps(review, allow_nan=False)


def test_public_helper_no_accidental_exception():
    for value in (None, True, 1, "", {}, [], ()):
        extract_beliefs_result(statements=value)


def test_prepare_notion_entry_non_string_no_exception():
    # Non-string/non-iterable inputs must never raise and must stay JSON-safe.
    output = prepare_notion_entry_result(
        title=float("nan"), sections=5, raw_notes=float("inf")
    )
    json.dumps(output, allow_nan=False)
    assert isinstance(output["prepared_content"], str)


def test_all_public_helpers_strict_json_everywhere():
    """Every public operation/rule helper must emit strict JSON without exception
    under an adversarial NaN/inf/malformed matrix (V1-I9, not just a sample)."""
    nan = float("nan")
    inf = float("inf")
    checks = []
    # rules.py public helpers
    checks.append(
        (
            "evaluate_hypotheses",
            lambda: evaluate_hypotheses(
                hypotheses=({"identity": "h", "statement": "x", "value": nan},)
            ),
        )
    )
    checks.append(
        (
            "evaluate_ambivalence",
            lambda: evaluate_ambivalence(
                records=(
                    {
                        "identity": "p",
                        "statement": "x",
                        "kind": "need",
                        "context": "c",
                        "temporal": "t",
                        "polarity": 1,
                        "value": inf,
                    },
                )
            ),
        )
    )
    checks.append(
        (
            "no_forced_conclusion_policy",
            lambda: no_forced_conclusion_policy({"unresolved": True, "x": inf}),
        )
    )
    checks.append(
        (
            "classify_belief_evidence",
            lambda: classify_belief_evidence(
                records=(
                    {
                        "identity": "e",
                        "kind": "evidence",
                        "statement": "x",
                        "source": "s",
                        "value": nan,
                    },
                )
            ),
        )
    )
    checks.append(
        (
            "compare_reflection_versions",
            lambda: compare_reflection_versions(
                versions=(
                    {
                        "version_id": "v",
                        "observed_at": "2029-01-01T00:00:00Z",
                        "content": inf,
                        "value": nan,
                    },
                )
            ),
        )
    )
    checks.append(
        (
            "map_interests",
            lambda: map_interests(
                records=(
                    {
                        "interest": "x",
                        "source": "s",
                        "source_kind": "user_statement",
                        "observed_at": inf,
                    },
                )
            ),
        )
    )
    checks.append(
        (
            "classify_persistence",
            lambda: classify_persistence(
                {"pattern": "x", "sources": ("msg:1",), "value": nan},
                confirmation={"decision_id": "d", "approved": True},
            ),
        )
    )
    checks.append(
        (
            "evaluate_open_questions",
            lambda: evaluate_open_questions(questions=({"question": nan},)),
        )
    )
    checks.append(
        (
            "evaluate_persistence_basis",
            lambda: evaluate_persistence_basis(
                {"pattern": "x", "sources": ("msg:1",), "value": nan}
            ),
        )
    )
    checks.append(
        (
            "present_reflection_result",
            lambda: present_reflection_result(
                {
                    "unresolved": True,
                    "value": nan,
                    "hypotheses": ({"statement": 1},),
                    "interest_candidates": ({"x": inf},),
                }
            ),
        )
    )
    # operations.py public helpers
    checks.append(
        (
            "structure_reflection_result",
            lambda: structure_reflection_result(
                material=({"level": "belief", "content": inf},)
            ),
        )
    )
    checks.append(
        (
            "extract_beliefs_result",
            lambda: extract_beliefs_result(
                statements=({"statement": "x", "kind": "belief", "value": nan},)
            ),
        )
    )
    checks.append(
        (
            "build_personal_timeline_result",
            lambda: build_personal_timeline_result(
                events=(
                    {
                        "event_id": "e",
                        "observed_at": "2029-01-01T00:00:00Z",
                        "content": nan,
                    },
                )
            ),
        )
    )
    checks.append(
        (
            "prepare_notion_entry_result",
            lambda: prepare_notion_entry_result(
                title=nan, sections=(nan, nan), raw_notes=inf
            ),
        )
    )
    checks.append(
        (
            "generate_summary_result",
            lambda: generate_summary_result(source={"unresolved": True, "value": nan}),
        )
    )
    checks.append(
        (
            "review_decision_result",
            lambda: review_decision_result(
                decision_candidate={"idea": "x", "value": inf}
            ),
        )
    )

    results = {}
    for name, call in checks:
        output = call()  # must NOT raise (no accidental exception)
        json.dumps(output, allow_nan=False)  # must be strict-JSON safe
        results[name] = True
    assert all(results.values())
    assert set(results) == {name for name, _ in checks}


def test_absent_valid_empty_malformed_grounded_distinct():
    assert extract_beliefs_result(statements=None)["evidence_state"] == "absent"
    assert extract_beliefs_result(statements=[])["evidence_state"] == "valid_empty"
    assert extract_beliefs_result(statements=True)["evidence_state"] == "malformed"
    assert extract_beliefs_result(statements="")["evidence_state"] == "malformed"
    grounded = extract_beliefs_result(
        statements=({"statement": "x", "kind": "belief"},)
    )
    assert grounded["evidence_state"] == "grounded"


# ─────────────────────────────────────────────────────────────────────────────
# V1-M1 — dead code removed
# ─────────────────────────────────────────────────────────────────────────────


def test_extract_beliefs_result_has_no_unreachable_duplicate():
    source = inspect.getsource(extract_beliefs_result)
    # The duplicate docstring/implementation block after the first return is gone:
    # exactly one ``return`` statement remains in the function body.
    assert source.count("return ") == 1


# ─────────────────────────────────────────────────────────────────────────────
# Gate summary (every gate backed by a real assertion above)
# ─────────────────────────────────────────────────────────────────────────────


def test_all_v1_closure_gates_pass():
    gates = {
        "DUPLICATE_CONFLICT_GATE": _gate(
            _try(test_hypothesis_identity_collision_fails_closed)
            and _try(test_ambivalence_identity_collision_fails_closed)
        ),
        "COUNTEREVIDENCE_GATE": _gate(
            _try(test_counterevidence_not_bypassed_by_evidence_count)
        ),
        "TEMPORAL_EQUAL_GROUP_GATE": _gate(
            _try(test_equal_time_subgroup_remains_ambiguous)
        ),
        "TIMELINE_ORDER_GATE": _gate(
            _try(test_timeline_orders_by_normalized_instant_not_raw_text)
        ),
        "INTEREST_SOURCE_GROUNDING_GATE": _gate(
            _try(test_unsupported_source_kinds_not_grounded)
        ),
        "PERSISTENCE_CONFIRMATION_GATE": _gate(
            _try(test_raw_true_alone_is_not_complete_confirmation)
        ),
        "PRESENTATION_LITERAL_STATE_GATE": _gate(
            _try(test_presentation_malformed_persistence_decision_fail_closed)
        ),
        "DIAGNOSIS_BOUNDARY_GATE": _gate(
            _try(test_diagnostic_hypothesis_is_not_safe_non_diagnostic)
        ),
        "NO_FORCED_CONCLUSION_GATE": _gate(
            _try(test_unsupported_certainty_variants_cannot_close_unresolved)
        ),
        "STRICT_JSON_GATE": _gate(_try(test_nan_inf_never_escape_public_output)),
        "PUBLIC_HELPER_NO_EXCEPTION_GATE": _gate(
            _try(test_public_helper_no_accidental_exception)
        ),
        "WORKFLOW_VALIDATE_GATE": _gate(_try(test_workflow_validate_gate_executable)),
    }
    assert all(value == "PASS" for value in gates.values()), gates
    # The aggregate marker string is emitted only when every gate passed.
    assert "ALL_V1_CLOSURE_GATES_PASS=true" == _all_gate_str(gates)


def _try(func):
    try:
        func()
        return True
    except AssertionError:
        return False


def _gate(condition: bool) -> str:
    return "PASS" if condition else "FAIL"


def _all_gate_str(gates) -> str:
    return (
        "ALL_V1_CLOSURE_GATES_PASS=true"
        if all(g == "PASS" for g in gates.values())
        else "FAIL"
    )
