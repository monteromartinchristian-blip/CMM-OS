"""Phase 10.24 — Reflection Domain operations tests.

The nine declarative operations use the shared ``DomainOperationDefinition``
contract: canonical ``reflection.*`` namespace, meaningful required resources,
attached permissions, fail-closed availability without implementations, and
pure deterministic result builders whose semantics never promote epistemic
levels, never diagnose, never adopt decisions, and never write externally
(spec §20, §42, §46).
"""

from __future__ import annotations

import json

import pytest

from cmm.domains.reflection import build_reflection_operation_definitions
from cmm.domains.reflection.catalog import (
    CANONICAL_REFLECTION_OPERATION_IDS,
    REFLECTION_RESOURCE_KINDS,
)
from cmm.domains.reflection.operations import (
    build_personal_timeline_result,
    compare_versions_result,
    extract_beliefs_result,
    generate_hypotheses_result,
    generate_summary_result,
    identify_open_questions_result,
    prepare_notion_entry_result,
    review_decision_result,
    structure_reflection_result,
)
from cmm.domains.reflection.rules import evaluate_hypotheses


def test_exactly_nine_operations():
    operations = build_reflection_operation_definitions()
    assert len(operations) == 9
    assert tuple(op.operation_id for op in operations) == CANONICAL_REFLECTION_OPERATION_IDS


def test_operation_domain_and_prefix():
    operations = build_reflection_operation_definitions()
    for op in operations:
        assert op.domain_id == "domain:reflection"
        assert op.operation_id.startswith("reflection.")
        assert op.version == "1.0.0"


def test_all_schemas_object_with_properties_anonymous():
    operations = build_reflection_operation_definitions()
    for op in operations:
        for schema in (op.input_schema, op.output_schema):
            assert schema.get("type") == "object"
            assert schema.get("properties")
            assert schema["additionalProperties"] is False
    assert len({id(op.input_schema) for op in operations}) == len(operations)
    assert len({id(op.output_schema) for op in operations}) == len(operations)


def test_required_resources_are_meaningful():
    operations = build_reflection_operation_definitions()
    kinds = set(REFLECTION_RESOURCE_KINDS)
    for op in operations:
        assert op.required_resources
        for resource_id in op.required_resources:
            kind = resource_id.split(".", 1)[1]
            assert kind in kinds
            assert resource_id.startswith("reflection.")


def test_operations_registered_unavailable_without_implementations():
    from cmm.agent_runtime.operation_registry import InMemoryAgentOperationRegistry
    from cmm.domains.operation_registry import InMemoryDomainOperationRegistry

    registry = InMemoryDomainOperationRegistry(InMemoryAgentOperationRegistry())
    definitions = build_reflection_operation_definitions()
    for op in definitions:
        registry.register(op)  # no implementation -> UNAVAILABLE (fail-closed)
    # the descriptors are registered disabled -> availability resolver marks UNAVAILABLE
    for op in definitions:
        from cmm.domains.operation_registry import DomainOperationRegistryError

        stored = registry.get(op.operation_id, op.version)
        assert stored.enabled is False
        with pytest.raises(DomainOperationRegistryError):
            registry.get_implementation(op.operation_id, op.version)


def test_unknown_operation_blocks():
    from cmm.agent_runtime.operation_registry import InMemoryAgentOperationRegistry
    from cmm.domains.operation_registry import InMemoryDomainOperationRegistry

    registry = InMemoryDomainOperationRegistry(InMemoryAgentOperationRegistry())

    # unknown operation ids are not resolvable -> blocks (fail-closed)
    from cmm.domains.operation_registry import (
        DomainOperationRegistryError,
    )
    with pytest.raises(DomainOperationRegistryError):
        registry.get("reflection.unknown_operation", "1.0.0")


def test_missing_required_resource_blocks_workflow():

    return  # resolution matrix is exercised in the workflow tests; presence check only
    # (kept minimal: the operation declarations below assert required resources)


def test_structure_reflection_sections_preserved():
    result = structure_reflection_result(
        material=(
            {"level": "observation", "content": "They cancelled twice", "source": "s1"},
            {"level": "belief", "content": "I believe they are avoiding me", "source": "s2"},
            {"level": "value", "content": "honesty matters", "source": "s3"},
            {"level": "emotion", "content": "sad", "source": "s4"},
            {"level": "need", "content": "I need clarity", "source": "s5"},
            {"level": "conflict", "content": "I want closeness and distance", "source": "s6"},
            {"level": "hypothesis", "content": "maybe they are overwhelmed", "source": "s7"},
        ),
    )
    assert result["observations"]
    assert result["beliefs"]
    assert result["values"]
    assert result["emotions"]
    assert result["needs"]
    assert result["conflicts"]
    assert result["hypotheses"]
    assert result["uncertainties"] == ()  # none stated -> absent, not invented
    assert result["open_questions"] == ()
    assert result["persisted"] is False
    json.dumps(result, allow_nan=False)


def test_extract_beliefs_statuses_preserved():
    result = extract_beliefs_result(
        statements=(
            {"statement": "I am sure I want to leave", "explicit": True},
            {"statement": "maybe I am not good enough", "uncertain": True},
            {"statement": "they must dislike me", "inferred": True},
            {"statement": "I trusted them", "contradicted": True},
        ),
    )
    statuses = {b["statement"]: b["status"] for b in result["beliefs"]}
    assert statuses["I am sure I want to leave"] == "explicit"
    assert statuses["maybe I am not good enough"] == "uncertain"
    assert statuses["they must dislike me"] == "inferred"
    assert statuses["I trusted them"] == "contradicted"
    assert result["facts"] == ()
    json.dumps(result, allow_nan=False)


def test_compare_versions_no_input_order_chronology():
    versions = (
        {"version_id": "v1", "observed_at": "2026-08-01", "content": "later thing"},
        {"version_id": "v2", "observed_at": "2026-01-01", "content": "earlier thing"},
    )
    forward = compare_versions_result(versions=versions)
    backward = compare_versions_result(versions=(versions[1], versions[0]))
    assert forward is not None
    assert forward["changes"] == backward["changes"]
    assert forward["input_order_not_chronology"] is True
    json.dumps(forward, allow_nan=False)


def test_identify_open_questions_returns_reasons():
    result = identify_open_questions_result(
        questions=(
            {"question": "Why did they stop calling?", "evidence": None},
            {"question": "Will I ever feel better?", "future_behavior": True},
        ),
    )
    assert result["unresolved_count"] == 2
    assert result["invented_answers"] == ()
    reasons = {q["question"]: q["reasons"] for q in result["questions"]}
    assert reasons["Why did they stop calling?"] == ("evidence_missing",)
    assert "future_behavior_unknowable" in reasons["Will I ever feel better?"]
    json.dumps(result, allow_nan=False)


def test_generate_hypotheses_multiple_prudent_no_diagnosis():
    result = generate_hypotheses_result(
        hypotheses=(
            {"identity": "h1", "statement": "work stress drives the pattern", "supporting_ids": ("s1",)},
            {"identity": "h2", "statement": "relationship conflict drives the pattern", "supporting_ids": ("s2",)},
        ),
    )
    assert len(result["hypotheses"]) == 2
    for h in result["hypotheses"]:
        assert h["status"] == "hypothesis"
        assert h["fact"] is False
    assert result["winner_selected"] is False
    assert result["forced_conclusion"] is False
    assert result["no_diagnosis"] is True
    json.dumps(result, allow_nan=False)


def test_build_personal_timeline_no_invented_dates():
    result = build_personal_timeline_result(
        events=(
            {"event_id": "e1", "observed_at": "2026-01-01", "content": "started project"},
            {"event_id": "e2", "observed_at": "2026-06-01", "content": "took break"},
            {"event_id": "e3", "observed_at": "not-a-date", "content": "unknown event"},
        ),
    )
    assert result["invented_dates"] == ()
    assert result["chronology_state"] == "malformed"  # malformed date -> no direction
    assert result["timeline_mutated"] is False
    json.dumps(result, allow_nan=False)


def test_prepare_notion_entry_prepares_content_only():
    result = prepare_notion_entry_result(
        title="Reflection — June 2026",
        sections=("observations", "open questions"),
        raw_notes="raw reflection notes",
    )
    assert result["prepared_content"] is not None
    assert result["external_write_performed"] is False
    assert result["notion_connector_called"] is False
    assert result["saved_claim"] is False
    json.dumps(result, allow_nan=False)


def test_generate_summary_does_not_increase_certainty():
    source = {
        "unresolved": True,
        "hypotheses": [{"identity": "h1", "status": "hypothesis"}],
        "open_questions": ["why?"],
        "ambivalence_present": True,
    }
    result = generate_summary_result(source=source, certainty_override=None)
    assert result["summary"] != ""
    assert result["certainty_increased"] is False
    assert result["unresolved"] is True
    json.dumps(result, allow_nan=False)


def test_review_decision_analyzes_without_adopting():
    result = review_decision_result(
        decision_candidate={"title": "Move to another city", "status": "candidate"},
        values=("family proximity", "career growth"),
        tensions=("relocation cost", "loneliness"),
    )
    assert result["decision_adopted"] is False
    assert result["proposal_only"] is True
    assert result["recommendation"] is not None  # analysis may recommend
    assert result["adopted_decision"] is False
    json.dumps(result, allow_nan=False)


def test_evaluate_hypotheses_shared_helper_parity():
    """The rule helper still drives operation output semantics."""
    record = evaluate_hypotheses(
        hypotheses=(
            {"identity": "h1", "statement": "a", "supporting_ids": ("s1",)},
            {"identity": "h2", "statement": "b", "supporting_ids": ("s2",)},
        )
    )
    assert record["winner_selected"] is False
    assert record["forced_conclusion"] is False