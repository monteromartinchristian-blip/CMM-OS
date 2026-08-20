"""Phase 10.24 — Reflection Domain Audit V2 remediation closure suite.

This file permanently encodes the six Important findings from
``docs/audits/phase-10.24-reflection-independent-audit-v2.md`` and proves each
is closed through its canonical surface.  Every assertion below is a real
executable proof; no gate string is hard-coded without a live assertion behind
it.

Closure matrix:

* VALIDATE_LITERAL_BOOL_GATE — shared workflow gate rejects ``1``/``"true"``
  for an expected ``True`` and requires literal boolean identity (V2-I1).
* VALIDATE_CONFLICT_GATE — shared workflow gate fails closed when the same
  condition field is observed across dependencies with disagreeing values
  (V2-I1).
* PERSISTENCE_SHARED_CONTRACT_GATE — only an authoritative shared approval
  snapshot authorizes persistence; arbitrary caller-shaped mappings are
  insufficient (V2-I2).
* INTEREST_SINGLE_SOURCE_UNCERTAINTY_GATE — repetition within one grounded
  source stays uncertain; uncertainty is driven by independent grounded source
  count, not mention count (V2-I3).
* DIAGNOSIS_SPANISH_GATE — Spanish direct classifications (e.g. "Eres
  narcisista") are marked diagnostic/restricted and not presented verbatim as
  safe hypotheses (V2-I4).
* NO_FORCED_CONCLUSION_SPANISH_GATE — unresolved Spanish forced-certainty
  wording is flagged as a forced conclusion and cannot complete as resolved
  (V2-I5).
"""

from __future__ import annotations

from cmm.domains.memory_contracts import DomainMemoryApprovalDecisionSnapshot
from cmm.domains.reflection.rules import (
    classify_persistence,
    evaluate_hypotheses,
    map_interests,
    no_forced_conclusion_policy,
)
from cmm.workflows.contracts import WorkflowDefinition, WorkflowNode
from cmm.workflows.engine import NodeExecution, WorkflowEngine
from cmm.workflows.enums import WorkflowRunStatus

# ─────────────────────────────────────────────────────────────────────────────
# V2-I1 — VALIDATE_LITERAL_BOOL_GATE + VALIDATE_CONFLICT_GATE
# ─────────────────────────────────────────────────────────────────────────────


def _make_two_producer_definition(*, validate_condition):
    return WorkflowDefinition(
        "validate.gate.v2.closure", "1.0.0", "ValidateGateV2Closure",
        nodes=(
            WorkflowNode("producer_a", "execute_operation", "ProducerA",
                         operation_id="op.a", operation_version="1.0.0"),
            WorkflowNode("producer_z", "execute_operation", "ProducerZ",
                         operation_id="op.z", operation_version="1.0.0"),
            WorkflowNode("validate", "validate", "Validate",
                         dependencies=("producer_a", "producer_z"),
                         wait_condition=validate_condition),
            WorkflowNode("finish", "complete", "Finish", dependencies=("validate",)),
        ),
        metadata={},
    )


def _run_two_producers(validate_condition, *, a_output, z_output):
    def adapter(node, run):
        if node.node_id == "producer_a":
            return NodeExecution.complete(a_output)
        if node.node_id == "producer_z":
            return NodeExecution.complete(z_output)
        return NodeExecution.complete({"ok": True})

    engine = WorkflowEngine(
        _make_two_producer_definition(validate_condition=validate_condition),
        id_factory=lambda: "run-v2-closure",
        clock=lambda: __import__("datetime").datetime.now(__import__("datetime").timezone.utc),
        node_adapter=adapter,
    )
    return engine.start({})


def test_validate_gate_rejects_numeric_one_for_expected_true():
    result = _run_two_producers(
        {"flag": True}, a_output={"flag": 1}, z_output={"flag": 1}
    )
    assert result.run.status is not WorkflowRunStatus.COMPLETED
    assert result.run.error_code == "validate.condition_false"


def test_validate_gate_rejects_string_true_for_expected_true():
    result = _run_two_producers(
        {"flag": True}, a_output={"flag": "true"}, z_output={"flag": "true"}
    )
    assert result.run.status is not WorkflowRunStatus.COMPLETED
    assert result.run.error_code == "validate.condition_false"


def test_validate_gate_rejects_numeric_zero_for_expected_false():
    result = _run_two_producers(
        {"flag": False}, a_output={"flag": 0}, z_output={"flag": 0}
    )
    assert result.run.status is not WorkflowRunStatus.COMPLETED
    assert result.run.error_code == "validate.condition_false"


def test_validate_gate_accepts_literal_true_for_expected_true():
    result = _run_two_producers(
        {"flag": True}, a_output={"flag": True}, z_output={"flag": True}
    )
    assert result.run.status is WorkflowRunStatus.COMPLETED


def test_validate_gate_fails_closed_on_conflicting_dependency_values():
    result = _run_two_producers(
        {"safe": True},
        a_output={"safe": False},
        z_output={"safe": True},
    )
    assert result.run.status is not WorkflowRunStatus.COMPLETED
    assert result.run.error_code == "validate.condition_conflict"


def test_validate_gate_passes_when_dependencies_agree():
    result = _run_two_producers(
        {"safe": True},
        a_output={"safe": True},
        z_output={"safe": True},
    )
    assert result.run.status is WorkflowRunStatus.COMPLETED


# ─────────────────────────────────────────────────────────────────────────────
# V2-I2 — PERSISTENCE_SHARED_CONTRACT_GATE
# ─────────────────────────────────────────────────────────────────────────────


def _authoritative_approval(approved: bool = True) -> DomainMemoryApprovalDecisionSnapshot:
    return DomainMemoryApprovalDecisionSnapshot(
        decision_id="d-v2-closure", request_id="r-v2-closure", approved=approved
    )


def test_arbitrary_mapping_is_not_a_shared_confirmation():
    confirmation = {
        "decision_id": "fake-decision",
        "request_id": "fake-request",
        "approved": True,
    }
    record = classify_persistence(
        {"pattern": "x", "sources": ("msg:1",)},
        confirmation=confirmation,
    )
    assert record["confirmed"] is False
    assert record["authorization_accepted"] is False
    assert record["authorization_malformed"] is True


def test_raw_true_is_not_a_shared_confirmation():
    record = classify_persistence(
        {"pattern": "x", "sources": ("msg:1",)},
        confirmation=True,
    )
    assert record["confirmed"] is False
    assert record["authorization_accepted"] is False


def test_authoritative_shared_confirmation_authorizes_when_grounded():
    record = classify_persistence(
        {"pattern": "x", "sources": ("msg:1", "msg:2")},
        confirmation=_authoritative_approval(approved=True),
    )
    assert record["confirmed"] is True
    assert record["authorization_accepted"] is True
    assert record["persistence_state"] == "confirmed"


def test_authoritative_rejection_does_not_confirm():
    record = classify_persistence(
        {"pattern": "x", "sources": ("msg:1", "msg:2")},
        confirmation=_authoritative_approval(approved=False),
    )
    assert record["confirmed"] is False
    assert record["authorization_accepted"] is False


# ─────────────────────────────────────────────────────────────────────────────
# V2-I3 — INTEREST_SINGLE_SOURCE_UNCERTAINTY_GATE
# ─────────────────────────────────────────────────────────────────────────────


def test_one_source_many_mentions_stays_uncertain():
    result = map_interests(
        records=(
            {
                "interest": "photography",
                "source": "msg:one",
                "source_kind": "user_statement",
                "recording": "I like photography",
            },
            {
                "interest": "photography",
                "source": "msg:one",
                "source_kind": "user_statement",
                "recording": "Photography interests me",
            },
        )
    )
    candidate = result["interest_candidates"][0]
    assert candidate["mention_count"] == 2
    assert candidate["grounded_evidence_count"] == 1
    assert candidate["independent_grounded_count"] == 1
    assert candidate["uncertainty"] is True


def test_two_independent_sources_distinguished_from_repetition():
    result = map_interests(
        records=(
            {
                "interest": "photography",
                "source": "msg:one",
                "source_kind": "user_statement",
                "recording": "I like photography",
            },
            {
                "interest": "photography",
                "source": "msg:two",
                "source_kind": "user_statement",
                "recording": "Photography interests me",
            },
        )
    )
    candidate = result["interest_candidates"][0]
    assert candidate["mention_count"] == 2
    assert candidate["grounded_evidence_count"] == 2
    assert candidate["independent_grounded_count"] == 2
    assert candidate["uncertainty"] is False


# ─────────────────────────────────────────────────────────────────────────────
# V2-I4 — DIAGNOSIS_SPANISH_GATE
# ─────────────────────────────────────────────────────────────────────────────


def test_spanish_direct_classifications_are_diagnostic():
    for statement in (
        "Eres narcisista",
        "Tienes trastorno bipolar",
        "Tienes un trastorno de apego",
        "Eres una persona manipuladora",
    ):
        result = evaluate_hypotheses(
            hypotheses=(
                {"identity": "hp", "statement": statement, "supporting_ids": ("s1",)},
            )
        )
        hypo = result["hypotheses"][0]
        assert hypo["diagnostic"] is True
        assert hypo["restricted_inference"] is True
        # The whole result must not present a non-diagnostic hypothesis surface
        # when a direct classification is present.
        assert result["no_diagnosis"] is False


def test_spanish_prudent_hypotheses_remain_usable():
    for statement in (
        "Una posibilidad es que esta situación te genere ambivalencia",
        "Podría haber varias explicaciones y no hay base para concluir una",
    ):
        result = evaluate_hypotheses(
            hypotheses=(
                {"identity": "hp", "statement": statement, "supporting_ids": ("s1",)},
            )
        )
        hypo = result["hypotheses"][0]
        assert hypo["diagnostic"] is False
        assert hypo["restricted_inference"] is False


# ─────────────────────────────────────────────────────────────────────────────
# V2-I5 — NO_FORCED_CONCLUSION_SPANISH_GATE
# ─────────────────────────────────────────────────────────────────────────────


def test_spanish_forced_certainty_flagged_unresolved():
    for statement in (
        "Es evidente que soy narcisista",
        "Está claro que todo se debe a un trauma",
        "Esto demuestra que él nunca me quiso",
    ):
        policy = no_forced_conclusion_policy(
            {"unresolved": True, "conclusion": statement}
        )
        assert policy["forced_conclusion"] is True
        assert policy["valid_unresolved_completion"] is False


def test_spanish_tentative_wording_not_forced():
    for statement in (
        "Una posibilidad es que haya influido el contexto",
        "No puedo concluirlo, pero esta hipótesis merece consideración",
    ):
        policy = no_forced_conclusion_policy(
            {"unresolved": True, "conclusion": statement}
        )
        assert policy["forced_conclusion"] is False
        assert policy["valid_unresolved_completion"] is True
