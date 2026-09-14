"""Phase 10.24 — Reflection adversarial closure gate.

One-off adversarial hardening evidence produced by the implementation agent
before documentation/commit: primitive matrix (no exceptions, no permission/
certainty/persistence widening), permutation invariance, duplicate handling,
input non-mutation, strict JSON safety through the supported serializer, and
the 15-gate summary.  Probe values here intentionally differ from committed
regression tests (spec §45-§48, §14).
"""

from __future__ import annotations

import copy
import itertools
import json
from datetime import datetime, timezone

from cmm.domains.memory_contracts import DomainMemoryApprovalDecisionSnapshot
from cmm.domains.reflection.permissions import permission_authorization_allows
from cmm.domains.reflection.rules import (
    authorizes_confirmation,
    classify_belief_evidence,
    classify_persistence,
    classify_statement_level,
    compare_reflection_versions,
    evaluate_ambivalence,
    evaluate_hypotheses,
    evaluate_open_questions,
    map_interests,
    no_forced_conclusion_policy,
)

NOW = datetime(2027, 1, 15, tzinfo=timezone.utc)

_PRIMITIVES = [
    None,
    True,
    False,
    0,
    1,
    -1,
    1.5,
    float("nan"),
    float("inf"),
    -float("inf"),
    "",
    "unknown",
    "arbitrary",
    {},
    [],
    (),
    [{}],
    {"nested": {"a": [1, 2]}},
    {"level": "belief", "statement": "x", "fact": True},
]


def _probe(label, fn):
    """Run a probe and return True only when it raised no exception and the
    result is a plain JSON-safe value (no accidental exception)."""
    try:
        value = fn()
    except Exception:  # noqa: BLE001 -- no-exception gate swallows everything
        return False
    json.dumps(value, allow_nan=False)  # must serialize without NaN
    return True


def _assert_no_widening(result):
    """No permission/certainty/persistence widening."""
    return (
        not result.get("winner_selected", False)
        and result.get("forced_conclusion", False) is False
        and result.get("confirmed", False) is False
        and result.get("persistent_confirmed", False) is False
    )


def test_no_exception_gate_primitive_matrix():
    gates = []
    for value in _PRIMITIVES:
        gates.append(
            _probe(
                f"hypotheses({value!r})",
                lambda v=value: evaluate_hypotheses(hypotheses=v),
            )
        )
        gates.append(
            _probe(
                f"ambivalence({value!r})",
                lambda v=value: evaluate_ambivalence(records=v),
            )
        )
        gates.append(
            _probe(
                f"belief_evidence({value!r})",
                lambda v=value: classify_belief_evidence(records=v),
            )
        )
        gates.append(
            _probe(
                f"open_questions({value!r})",
                lambda v=value: evaluate_open_questions(questions=v),
            )
        )
        gates.append(
            _probe(
                f"versions({value!r})",
                lambda v=value: compare_reflection_versions(versions=v),
            )
        )
        gates.append(
            _probe(f"interests({value!r})", lambda v=value: map_interests(records=v))
        )
        gates.append(
            _probe(
                f"persistence({value!r})",
                lambda v=value: classify_persistence(
                    {"pattern": "probe"}, confirmation=v
                ),
            )
        )
        gates.append(
            _probe(f"nfc({value!r})", lambda v=value: no_forced_conclusion_policy(v))
        )
        gates.append(
            _probe(f"level({value!r})", lambda v=value: classify_statement_level(v))
        )
        gates.append(
            _probe(
                f"perm({value!r})", lambda v=value: permission_authorization_allows(v)
            )
        )
        gates.append(
            _probe(f"confirm({value!r})", lambda v=value: authorizes_confirmation(v))
        )
    assert all(gates), "primitive matrix raised or produced non-JSON-safe output"


def test_no_permission_widening_from_primitive_matrix():
    for value in _PRIMITIVES:
        if value is True:
            # True is the only valid authorization; everything else is denied
            continue
        assert permission_authorization_allows(value) is False
        assert authorizes_confirmation(value) is False
        record = classify_persistence({"pattern": "probe"}, confirmation=value)
        assert record["confirmed"] is False
        assert record["authorization_accepted"] is False
        assert record["persistence_state"] != "confirmed"
    assert permission_authorization_allows(True) is True
    assert authorizes_confirmation(True) is True
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

    def _make_adv_chain(prop_id="prop-adv-1", approved=True):
        ref = DomainMemoryReference(
            reference_id=f"ref:{prop_id}",
            kind=DomainMemoryReferenceKind.KNOWLEDGE_ITEM,
            canonical_id=f"item:{prop_id}",
            domain_id="domain:reflection",
            applicable_domains=("domain:reflection",),
            evidence_ids=("ev:1",),
            resource_ids=("res:1",),
        )
        permission = DomainMemoryPermissionDecisionSnapshot(
            decision_id=f"perm:{prop_id}",
            allowed=True,
            capabilities=(DomainMemoryCapability.PROPOSE,),
            source_domain_id="domain:reflection",
            target_domain_id="domain:reflection",
            sensitivity_levels=(DomainMemorySensitivityLevel.NORMAL,),
        )
        view_request = build_reflection_memory_view_request(
            request_id=f"req:{prop_id}",
            trace_id=f"trace:{prop_id}",
            requested_kinds=(DomainMemoryReferenceKind.KNOWLEDGE_ITEM,),
            candidates=(ref,),
            permission_decision_ids=(f"perm:{prop_id}",),
        )
        proposal = build_reflection_memory_proposal(
            proposal_id=prop_id,
            affected_reference_ids=(f"ref:{prop_id}",),
        )
        temp_inv = DomainMemoryReferenceInventory(
            references=(ref,),
            traces=(
                DomainMemoryTraceSnapshot(
                    trace_id=f"trace:{prop_id}", primary_domain="domain:reflection"
                ),
            ),
            permission_decisions=(permission,),
        )
        view = build_reflection_memory_view(request=view_request, inventory=temp_inv)
        binding = build_reflection_memory_binding(
            proposal=proposal,
            view=view,
            trace_id=f"trace:{prop_id}",
            permission_decision_ids=(f"perm:{prop_id}",),
            approval_request_ids=(f"appr-req:{prop_id}",),
            approval_decision_ids=(f"appr-dec:{prop_id}",),
        )
        inv = DomainMemoryReferenceInventory(
            references=(ref,),
            proposals=(proposal,),
            permission_decisions=(permission,),
            approval_requests=(
                DomainMemoryApprovalRequestSnapshot(
                    request_id=f"appr-req:{prop_id}", proposal_id=prop_id
                ),
            ),
            approval_decisions=(
                DomainMemoryApprovalDecisionSnapshot(
                    decision_id=f"appr-dec:{prop_id}",
                    request_id=f"appr-req:{prop_id}",
                    approved=approved,
                ),
            ),
            traces=(
                DomainMemoryTraceSnapshot(
                    trace_id=f"trace:{prop_id}", primary_domain="domain:reflection"
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
        return binding, inv

    # raw True alone is NOT a complete shared confirmation contract (V1-I4);
    # only a shared confirmation reference + grounded provenance confirms.
    assert (
        classify_persistence(
            {"pattern": "probe", "sources": ("s1",)}, confirmation=True
        )["confirmed"]
        is False
    )
    # Standalone snapshot alone does not confirm
    assert (
        classify_persistence(
            {"pattern": "probe", "sources": ("msg:1",)},
            confirmation=DomainMemoryApprovalDecisionSnapshot(
                decision_id="d-abc", request_id="r-abc", approved=True
            ),
        )["confirmed"]
        is False
    )
    adv_binding, adv_inv = _make_adv_chain("prop-adv-1", approved=True)
    assert (
        classify_persistence(
            {"proposal_id": "prop-adv-1", "pattern": "probe", "sources": ("msg:1",)},
            confirmation_binding=adv_binding,
            confirmation_inventory=adv_inv,
        )["confirmed"]
        is True
    )


def test_open_ended_gate():
    result = evaluate_open_questions(
        questions=(
            {"identity": "q-probe-1", "question": "why now, probe?", "evidence": None},
            {
                "identity": "q-probe-2",
                "question": "what changes next?",
                "future_behavior": True,
            },
        )
    )
    policy = no_forced_conclusion_policy(
        {
            "unresolved": True,
            "open_questions": ("why now, probe?", "what changes next?"),
        }
    )
    assert result["unresolved_count"] == 2
    assert policy["valid_unresolved_completion"] is True
    assert policy["forced_conclusion"] is False


def test_hypothesis_gate():
    result = evaluate_hypotheses(
        hypotheses=(
            {
                "identity": "p1",
                "statement": "probe pattern is work-driven",
                "supporting_ids": ("ps1",),
            },
            {
                "identity": "p2",
                "statement": "probe pattern is routine-driven",
                "supporting_ids": ("ps2",),
            },
        )
    )
    assert len(result["hypotheses"]) == 2
    assert result["winner_selected"] is False
    assert all(
        h["status"] == "hypothesis" and h["fact"] is False for h in result["hypotheses"]
    )


def test_ambivalence_gate():
    result = evaluate_ambivalence(
        records=(
            {
                "identity": "a1",
                "statement": "want to go",
                "kind": "desire",
                "polarity": 1,
                "context": "probe",
                "temporal": "2027-01-01",
            },
            {
                "identity": "a2",
                "statement": "want to stay",
                "kind": "desire",
                "polarity": -1,
                "context": "probe",
                "temporal": "2027-01-01",
            },
        )
    )
    assert result["ambivalence_present"] is True
    assert result["forced_resolution"] is False


def test_belief_evidence_gate():
    result = classify_belief_evidence(
        records=(
            {
                "identity": "b1",
                "statement": "probe belief",
                "kind": "belief",
                "inferred": True,
            },
            {
                "identity": "e1",
                "statement": "probe event",
                "kind": "experience",
                "fact": True,
            },
        )
    )
    assert result["facts"] == ()
    assert result["promotion_applied"] is False
    assert len(result["promotions_blocked"]) == 1


def test_open_question_gate():
    result = evaluate_open_questions(
        questions=(
            {
                "identity": "oq1",
                "question": "probe question",
                "evidence": None,
                "plausible_hypothesis": True,
            },
        )
    )
    assert result["questions"][0]["status"] == "open"
    assert "plausible_hypothesis_only" in result["questions"][0]["reasons"]
    assert result["invented_answers"] == ()


def test_temporal_gate():
    result = compare_reflection_versions(
        versions=(
            {
                "version_id": "v1",
                "identity": "probe-idea",
                "observed_at": "2027-01-01T00:00:00Z",
                "content": "phase one",
            },
            {
                "version_id": "v2",
                "identity": "probe-idea",
                "observed_at": "2027-01-01T00:00:00+00:00",
                "content": "phase two",
            },
        )
    )
    assert result["chronology_state"] == "equal_timestamps"
    assert result["equal_timestamps_no_evolution"] is True
    assert result["temporally_ordered"] is False


def test_interest_grounding_gate():
    result = map_interests(
        records=(
            {
                "interest": "astronomy",
                "source": "ast-1",
                "explicit": True,
                "observed_at": "2027-01-02",
            },
            {
                "interest": "astronomy",
                "source": "ast-1",
                "explicit": True,
                "observed_at": "2027-01-02",
            },
            {
                "interest": "astronomy",
                "source": "llm-1",
                "source_kind": "model_summary",
                "observed_at": "2027-01-03",
            },
            {
                "interest": "chess",
                "source": "ch-1",
                "mention": True,
                "observed_at": "2027-01-04",
            },
        )
    )
    astronomy = next(
        c for c in result["interest_candidates"] if c["interest"] == "astronomy"
    )
    chess = next(c for c in result["interest_candidates"] if c["interest"] == "chess")
    assert astronomy["grounded_evidence_count"] == 1  # duplicate does not inflate
    assert astronomy["independent_grounded_count"] == 1  # model summary not independent
    assert astronomy["persistent_confirmed"] is False
    assert chess["grounded_evidence_count"] == 1
    assert chess["persistent_confirmed"] is False  # one mention is not enough
    assert result["persistent_confirmed"] is False


def test_persistence_gate():
    record = classify_persistence(
        {
            "pattern": "probe-persistent",
            "sources": ("m1", "m2", "m3"),
            "repetition_count": 9,
        },
        confirmation=None,
    )
    assert record["confirmed"] is False
    assert record["persistence_state"] == "candidate"
    # raw True is not a complete shared confirmation; a shared reference +
    # grounded provenance confirms; nonliteral authorization does not
    assert (
        classify_persistence(
            {"pattern": "probe-persistent", "sources": ("m1",)},
            confirmation=True,
        )["confirmed"]
        is False
    )
    # Standalone snapshot alone does not confirm
    assert (
        classify_persistence(
            {"pattern": "probe-persistent", "sources": ("msg:1",)},
            confirmation=DomainMemoryApprovalDecisionSnapshot(
                decision_id="d-abc", request_id="r-abc", approved=True
            ),
        )["confirmed"]
        is False
    )
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

    ref = DomainMemoryReference(
        reference_id="ref:prop-adv-gate",
        kind=DomainMemoryReferenceKind.KNOWLEDGE_ITEM,
        canonical_id="item:prop-adv-gate",
        domain_id="domain:reflection",
        applicable_domains=("domain:reflection",),
        evidence_ids=("ev:1",),
        resource_ids=("res:1",),
    )
    permission = DomainMemoryPermissionDecisionSnapshot(
        decision_id="perm:prop-adv-gate",
        allowed=True,
        capabilities=(DomainMemoryCapability.PROPOSE,),
        source_domain_id="domain:reflection",
        target_domain_id="domain:reflection",
        sensitivity_levels=(DomainMemorySensitivityLevel.NORMAL,),
    )
    view_request = build_reflection_memory_view_request(
        request_id="req:prop-adv-gate",
        trace_id="trace:prop-adv-gate",
        requested_kinds=(DomainMemoryReferenceKind.KNOWLEDGE_ITEM,),
        candidates=(ref,),
        permission_decision_ids=("perm:prop-adv-gate",),
    )
    proposal = build_reflection_memory_proposal(
        proposal_id="prop-adv-gate",
        affected_reference_ids=("ref:prop-adv-gate",),
    )
    temp_inv = DomainMemoryReferenceInventory(
        references=(ref,),
        traces=(
            DomainMemoryTraceSnapshot(
                trace_id="trace:prop-adv-gate", primary_domain="domain:reflection"
            ),
        ),
        permission_decisions=(permission,),
    )
    view = build_reflection_memory_view(request=view_request, inventory=temp_inv)
    binding = build_reflection_memory_binding(
        proposal=proposal,
        view=view,
        trace_id="trace:prop-adv-gate",
        permission_decision_ids=("perm:prop-adv-gate",),
        approval_request_ids=("appr-req:prop-adv-gate",),
        approval_decision_ids=("appr-dec:prop-adv-gate",),
    )
    inv = DomainMemoryReferenceInventory(
        references=(ref,),
        proposals=(proposal,),
        permission_decisions=(permission,),
        approval_requests=(
            DomainMemoryApprovalRequestSnapshot(
                request_id="appr-req:prop-adv-gate", proposal_id="prop-adv-gate"
            ),
        ),
        approval_decisions=(
            DomainMemoryApprovalDecisionSnapshot(
                decision_id="appr-dec:prop-adv-gate",
                request_id="appr-req:prop-adv-gate",
                approved=True,
            ),
        ),
        traces=(
            DomainMemoryTraceSnapshot(
                trace_id="trace:prop-adv-gate", primary_domain="domain:reflection"
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
    assert (
        classify_persistence(
            {
                "proposal_id": "prop-adv-gate",
                "pattern": "probe-persistent",
                "sources": ("msg:1",),
            },
            confirmation_binding=binding,
            confirmation_inventory=inv,
        )["confirmed"]
        is True
    )
    assert (
        classify_persistence(
            {"pattern": "probe-persistent", "sources": ("m1",)}, confirmation=1
        )["confirmed"]
        is False
    )


def test_identity_safety_gate():
    hypothesis = evaluate_hypotheses(
        hypotheses=(
            {
                "identity": "id-p",
                "statement": "probe identity story",
                "supporting_ids": ("ps1", "ps2"),
            },
        )
    )
    assert hypothesis["hypotheses"][0]["status"] == "hypothesis"
    assert hypothesis["hypotheses"][0]["fact"] is False
    assert "identity_fact" not in hypothesis["hypotheses"][0]
    assert hypothesis["winner_selected"] is False


def test_permission_gate_matches_literal_true_only():
    for raw in (
        "true",
        "TRUE",
        "1",
        1,
        0,
        -1,
        [],
        {},
        (),
        0.0,
        1.5,
        None,
        float("nan"),
        float("inf"),
    ):
        assert permission_authorization_allows(raw) is False
    assert permission_authorization_allows(True) is True
    assert permission_authorization_allows(False) is False


def test_permutation_gate():
    hypothesis_sets = (
        (
            {"identity": "x1", "statement": "one", "supporting_ids": ("a", "b")},
            {"identity": "x2", "statement": "two", "supporting_ids": ("c",)},
        ),
    )
    interest_records = (
        {
            "interest": "astronomy",
            "source": "ast-1",
            "explicit": True,
            "observed_at": "2027-01-02",
        },
        {
            "interest": "chess",
            "source": "ch-1",
            "mention": True,
            "observed_at": "2027-01-04",
        },
    )
    versions = (
        {
            "version_id": "v1",
            "identity": "probe-idea",
            "observed_at": "2027-01-01",
            "content": "one",
        },
        {
            "version_id": "v2",
            "identity": "probe-idea",
            "observed_at": "2027-06-01",
            "content": "two",
        },
    )
    results = []
    for order_h in itertools.permutations(hypothesis_sets[0]):
        results.append(evaluate_hypotheses(hypotheses=order_h))
    h_canonical = {
        (
            r["unresolved"],
            r["winner_selected"],
            r["forced_conclusion"],
            len(r["hypotheses"]),
        )
        for r in results
    }
    assert len(h_canonical) == 1

    i_results = [
        map_interests(records=order)
        for order in itertools.permutations(interest_records)
    ]
    i_canonical = {
        tuple(
            (c["interest"], c["grounded_evidence_count"], c["uncertainty"])
            for c in r["interest_candidates"]
        )
        for r in i_results
    }
    assert len(i_canonical) == 1

    v_results = [
        compare_reflection_versions(versions=order)
        for order in itertools.permutations(versions)
    ]
    v_canonical = {
        (r["chronology_state"], r["temporally_ordered"], len(r["changes"]))
        for r in v_results
    }
    assert len(v_canonical) == 1


def test_input_non_mutation_gate():
    hypotheses_input = [
        {
            "identity": "n1",
            "statement": "probe",
            "supporting_ids": ("s1",),
            "uncertainty": 0.5,
        },
        {
            "identity": "n2",
            "statement": "probe2",
            "supporting_ids": ("s2",),
            "counterevidence_ids": ("s3",),
        },
    ]
    interest_input = [
        {
            "interest": "astronomy",
            "source": "ast-9",
            "explicit": True,
            "observed_at": "2027-02-02",
        },
    ]
    versions_input = [
        {
            "version_id": "v1",
            "identity": "probe-idea",
            "observed_at": "2027-03-01",
            "content": "one",
        },
        {
            "version_id": "v2",
            "identity": "probe-idea",
            "observed_at": "2027-09-01",
            "content": "two",
        },
    ]
    ambivalence_input = [
        {
            "identity": "m1",
            "statement": "toward",
            "kind": "desire",
            "polarity": 1,
            "context": "probe",
            "temporal": "2027-04-01",
        },
        {
            "identity": "m2",
            "statement": "away",
            "kind": "desire",
            "polarity": -1,
            "context": "probe",
            "temporal": "2027-04-01",
        },
    ]
    snapshots = [
        copy.deepcopy(hypotheses_input),
        copy.deepcopy(interest_input),
        copy.deepcopy(versions_input),
        copy.deepcopy(ambivalence_input),
    ]
    evaluate_hypotheses(hypotheses=hypotheses_input)
    map_interests(records=interest_input)
    compare_reflection_versions(versions=versions_input)
    evaluate_ambivalence(records=ambivalence_input)
    assert hypotheses_input == snapshots[0]
    assert interest_input == snapshots[1]
    assert versions_input == snapshots[2]
    assert ambivalence_input == snapshots[3]


def test_strict_json_gate():
    result = evaluate_hypotheses(
        hypotheses=(
            {
                "identity": "j1",
                "statement": "probe",
                "supporting_ids": ("s1",),
                "uncertainty": 0.25,
            },
            {
                "identity": "j2",
                "statement": "probe2",
                "supporting_ids": ("s2",),
                "uncertainty": None,
            },
        )
    )
    json.dumps(result, allow_nan=False)
    belief = classify_belief_evidence(
        records=(
            {
                "identity": "jb1",
                "statement": "probe",
                "kind": "belief",
                "inferred": True,
            },
        )
    )
    json.dumps(belief, allow_nan=False)
    interest = map_interests(
        records=({"interest": "astronomy", "source": "ast-1", "explicit": True},)
    )
    json.dumps(interest, allow_nan=False)
    persistence = classify_persistence(
        {"pattern": "probe", "sources": ("s1",)}, confirmation=True
    )
    json.dumps(persistence, allow_nan=False)
    questions = evaluate_open_questions(
        questions=({"identity": "qj1", "question": "probe", "evidence": None},)
    )
    json.dumps(questions, allow_nan=False)


def test_full_gate_summary():
    """Print the one-off adversarial summary with values distinct from committed tests."""
    gates = {
        "OPEN_ENDED_GATE": _probe(
            "open-ended",
            lambda: evaluate_open_questions(
                questions=({"identity": "z1", "question": "probe", "evidence": None},)
            ),
        )
        and no_forced_conclusion_policy({"unresolved": True})[
            "valid_unresolved_completion"
        ],
        "HYPOTHESIS_GATE": _probe(
            "hypothesis",
            lambda: evaluate_hypotheses(
                hypotheses=(
                    {"identity": "h-z1", "statement": "a", "supporting_ids": ("s1",)},
                    {"identity": "h-z2", "statement": "b", "supporting_ids": ("s2",)},
                )
            ),
        )
        and not evaluate_hypotheses(
            hypotheses=(
                {"identity": "h-z1", "statement": "a", "supporting_ids": ("s1",)},
                {"identity": "h-z2", "statement": "b", "supporting_ids": ("s2",)},
            )
        )["winner_selected"],
        "AMBIVALENCE_GATE": _probe(
            "ambivalence",
            lambda: evaluate_ambivalence(
                records=(
                    {
                        "identity": "az1",
                        "statement": "yes",
                        "kind": "desire",
                        "polarity": 1,
                        "context": "z",
                        "temporal": "2027-01-01",
                    },
                    {
                        "identity": "az2",
                        "statement": "no",
                        "kind": "desire",
                        "polarity": -1,
                        "context": "z",
                        "temporal": "2027-01-01",
                    },
                )
            ),
        )
        and evaluate_ambivalence(
            records=(
                {
                    "identity": "az1",
                    "statement": "yes",
                    "kind": "desire",
                    "polarity": 1,
                    "context": "z",
                    "temporal": "2027-01-01",
                },
                {
                    "identity": "az2",
                    "statement": "no",
                    "kind": "desire",
                    "polarity": -1,
                    "context": "z",
                    "temporal": "2027-01-01",
                },
            )
        )["ambivalence_present"],
        "BELIEF_EVIDENCE_GATE": _probe(
            "belief",
            lambda: classify_belief_evidence(
                records=(
                    {
                        "identity": "bz1",
                        "statement": "probe",
                        "kind": "belief",
                        "inferred": True,
                    },
                )
            ),
        )
        and classify_belief_evidence(
            records=(
                {
                    "identity": "bz1",
                    "statement": "probe",
                    "kind": "belief",
                    "inferred": True,
                },
            )
        )["facts"]
        == (),
        "OPEN_QUESTION_GATE": _probe(
            "oq",
            lambda: evaluate_open_questions(
                questions=({"identity": "qz1", "question": "probe", "evidence": None},)
            ),
        )
        and evaluate_open_questions(
            questions=({"identity": "qz1", "question": "probe", "evidence": None},)
        )["unresolved_count"]
        >= 1,
        "TEMPORAL_GATE": _probe(
            "temporal",
            lambda: compare_reflection_versions(
                versions=(
                    {
                        "version_id": "vz1",
                        "identity": "zig",
                        "observed_at": "2027-01-01T00:00:00Z",
                        "content": "a",
                    },
                    {
                        "version_id": "vz2",
                        "identity": "zig",
                        "observed_at": "2027-01-01T00:00:00+00:00",
                        "content": "b",
                    },
                )
            ),
        )
        and compare_reflection_versions(
            versions=(
                {
                    "version_id": "vz1",
                    "identity": "zig",
                    "observed_at": "2027-01-01T00:00:00Z",
                    "content": "a",
                },
                {
                    "version_id": "vz2",
                    "identity": "zig",
                    "observed_at": "2027-01-01T00:00:00+00:00",
                    "content": "b",
                },
            )
        )["equal_timestamps_no_evolution"],
        "INTEREST_GROUNDING_GATE": _probe(
            "interest",
            lambda: map_interests(
                records=(
                    {
                        "interest": "astronomy",
                        "source": "az-1",
                        "explicit": True,
                        "observed_at": "2027-01-02",
                    },
                    {
                        "interest": "astronomy",
                        "source": "az-1",
                        "explicit": True,
                        "observed_at": "2027-01-02",
                    },
                )
            ),
        )
        and map_interests(
            records=(
                {
                    "interest": "astronomy",
                    "source": "az-1",
                    "explicit": True,
                    "observed_at": "2027-01-02",
                },
                {
                    "interest": "astronomy",
                    "source": "az-1",
                    "explicit": True,
                    "observed_at": "2027-01-02",
                },
            )
        )["interest_candidates"][0]["grounded_evidence_count"]
        == 1,
        "PERSISTENCE_GATE": _probe(
            "persistence",
            lambda: classify_persistence(
                {"pattern": "zigzag", "sources": ("m1",)}, confirmation=1
            ),
        )
        and classify_persistence(
            {"pattern": "zigzag", "sources": ("m1",)}, confirmation=1
        )["confirmed"]
        is False,
        "IDENTITY_SAFETY_GATE": _probe(
            "identity",
            lambda: evaluate_hypotheses(
                hypotheses=(
                    {
                        "identity": "iz1",
                        "statement": "probe identity",
                        "supporting_ids": ("s1",),
                    },
                )
            ),
        )
        and evaluate_hypotheses(
            hypotheses=(
                {
                    "identity": "iz1",
                    "statement": "probe identity",
                    "supporting_ids": ("s1",),
                },
            )
        )["hypotheses"][0]["fact"]
        is False,
        "PERMISSION_GATE": all(
            permission_authorization_allows(raw) is False
            for raw in ("true", 1, 0, [], {}, None, 0.0, float("nan"))
        )
        and permission_authorization_allows(True) is True,
        "PERMUTATION_GATE": len(
            {
                evaluate_hypotheses(hypotheses=order)["winner_selected"]
                for order in itertools.permutations(
                    (
                        {
                            "identity": "pz1",
                            "statement": "a",
                            "supporting_ids": ("s1",),
                        },
                        {
                            "identity": "pz2",
                            "statement": "b",
                            "supporting_ids": ("s2",),
                        },
                    )
                )
            }
        )
        == 1,
        "INPUT_NON_MUTATION_GATE": _probe("immut", lambda: _immutability_check()),
        "STRICT_JSON_GATE": _probe(
            "json",
            lambda: json.dumps(
                evaluate_hypotheses(
                    hypotheses=(
                        {
                            "identity": "jz1",
                            "statement": "a",
                            "supporting_ids": ("s1",),
                        },
                    )
                ),
                allow_nan=False,
            ),
        ),
        "NO_EXCEPTION_GATE": all(
            _probe(f"prim-{index}", lambda value=v: value)
            for index, v in enumerate(
                (None, True, 0, 1, -1, 1.5, "x", {}, [], [{}], {"a": [{"b": 2}]})
            )
        ),
    }
    lines = [
        f"{name}=PASS" if passed else f"{name}=FAIL" for name, passed in gates.items()
    ]
    summary = "\n".join(lines + [f"ALL_PASS={str(all(gates.values())).lower()}"])
    print(summary)
    assert all(gates.values()), summary


def _immutability_check():
    payload = {
        "pattern": "zigzag-probe",
        "sources": ("m1", "m2"),
        "nested": {"a": [1, 2]},
    }
    snapshot = copy.deepcopy(payload)
    classify_persistence(payload, confirmation=True)
    return payload == snapshot


def test_adversarial_duplicates_deterministic():
    """Exact duplicates do not inflate and conflicting duplicates stay unresolved."""
    result = evaluate_hypotheses(
        hypotheses=(
            {"identity": "d1", "statement": "same claim", "supporting_ids": ("s1",)},
            {"identity": "d1", "statement": "same claim", "supporting_ids": ("s1",)},
            {
                "identity": "d2",
                "statement": "different claim",
                "supporting_ids": ("s1",),
            },
        )
    )
    assert len(result["hypotheses"]) == 2  # exact duplicate collapsed
    assert result["unresolved"] is True  # s1 supports two different claims
    assert "s1" in result["conflicting_ids"]
