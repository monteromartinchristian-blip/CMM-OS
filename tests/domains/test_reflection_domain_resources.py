"""Phase 10.24 — Reflection Domain resource tests.

Nine resource definitions over the shared resource contracts.  Resources are
definitions only; a resource existing is never the same as a fact being
authoritative, and ``relationship_event`` is consumed only as an authorized
minimal projection (spec §24, §30, §35).
"""

from __future__ import annotations

from cmm.cognitive.enums import SensitivityLevel
from cmm.domains.reflection import build_reflection_resource_definitions
from cmm.domains.reflection.catalog import (
    CANONICAL_REFLECTION_RESOURCE_IDS,
    REFLECTION_RESOURCE_KINDS,
)


def test_exactly_9_resources():
    resources = build_reflection_resource_definitions()
    assert len(resources) == 9
    assert [r.id for r in resources] == list(CANONICAL_REFLECTION_RESOURCE_IDS)


def test_resource_ids_and_kinds():
    resources = build_reflection_resource_definitions()
    by_id = {r.id: r for r in resources}
    assert set(by_id) == set(CANONICAL_REFLECTION_RESOURCE_IDS)
    for resource in resources:
        assert str(resource.domain_id) == "domain:reflection"
        assert resource.kind == resource.id.split(".", 1)[1]
    assert tuple(r.kind for r in resources) == REFLECTION_RESOURCE_KINDS


def test_shared_adapter_resources_reused():
    resources = build_reflection_resource_definitions()
    by_id = {r.id: r for r in resources}
    assert by_id["reflection.user_message"].adapter == "cognitive.message"
    assert by_id["reflection.conversation"].adapter == "cognitive.conversation"
    assert by_id["reflection.note"].adapter == "cognitive.note"
    assert by_id["reflection.journal_entry"].adapter == "cognitive.note"
    assert by_id["reflection.memory_entry"].adapter == "cognitive.memory"
    assert by_id["reflection.relationship_event"].adapter == "cognitive.event"
    assert by_id["reflection.life_event"].adapter == "cognitive.event"
    assert by_id["reflection.goal"].adapter == "cognitive.goal"
    assert by_id["reflection.decision"].adapter == "cognitive.goal"


def test_high_sensitivity_relationship_and_journal_sources():
    resources = build_reflection_resource_definitions()
    by_id = {r.id: r for r in resources}
    assert by_id["reflection.relationship_event"].default_sensitivity is (
        SensitivityLevel.HIGHLY_SENSITIVE
    )
    assert by_id["reflection.journal_entry"].default_sensitivity is (
        SensitivityLevel.SENSITIVE
    )
    assert by_id["reflection.decision"].default_sensitivity is (
        SensitivityLevel.SENSITIVE
    )


def test_memory_entry_is_provenance_not_current_truth():
    resources = build_reflection_resource_definitions()
    memory = {r.id: r for r in resources}["reflection.memory_entry"]
    assert memory.metadata.get("memory_integration") is True
    assert memory.metadata.get("proposal_only") is True
    assert memory.metadata.get("provenance_not_truth") is True


def test_relationship_event_projection_boundary():
    resources = build_reflection_resource_definitions()
    event = {r.id: r for r in resources}["reflection.relationship_event"]
    assert event.metadata.get("cross_domain_projection") is True
    assert event.metadata.get("minimal_authorized_projection") is True
    assert event.metadata.get("no_relationships_store_merge") is True


def test_deterministic_order():
    a = build_reflection_resource_definitions()
    b = build_reflection_resource_definitions()
    assert [r.id for r in a] == [r.id for r in b]