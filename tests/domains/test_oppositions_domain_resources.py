"""Phase 10.23 — Opposition Domain Resources tests."""

from __future__ import annotations

from cmm.domains.oppositions import build_oppositions_resource_definitions
from cmm.domains.oppositions.catalog import CANONICAL_OPPOSITION_RESOURCE_IDS


def test_exactly_11_resources():
    resources = build_oppositions_resource_definitions()
    assert len(resources) == 11
    assert [r.id for r in resources] == list(CANONICAL_OPPOSITION_RESOURCE_IDS)


def test_resource_ids_and_kinds():
    resources = build_oppositions_resource_definitions()
    by_id = {r.id: r for r in resources}
    assert set(by_id) == set(CANONICAL_OPPOSITION_RESOURCE_IDS)
    for resource in resources:
        assert resource.domain_id == "domain:oppositions"
        assert resource.kind == resource.id.split(".", 1)[1]


def test_official_capable_resources():
    resources = build_oppositions_resource_definitions()
    by_id = {r.id: r for r in resources}
    for resource_id in (
        "oppositions.official_call",
        "oppositions.syllabus",
        "oppositions.regulation",
        "oppositions.external_official_source",
    ):
        assert by_id[resource_id].metadata.get("official_capable") is True


def test_shared_adapter_resources_reused():
    """Shared calendar/note/message/memory resources reuse shared adapters."""
    resources = build_oppositions_resource_definitions()
    by_id = {r.id: r for r in resources}
    assert by_id["oppositions.calendar_event"].adapter == "cognitive.calendar"
    assert by_id["oppositions.note"].adapter == "cognitive.note"
    assert by_id["oppositions.user_message"].adapter == "cognitive.message"
    assert by_id["oppositions.memory_entry"].adapter == "cognitive.memory"


def test_resource_metadata_does_not_create_truth():
    """Resource metadata never creates truth; a resource existing is not an
    authoritative fact."""
    resources = build_oppositions_resource_definitions()
    by_id = {r.id: r for r in resources}
    # memory_entry is proposal-only/not official; it must never carry official
    # authority simply by existing.
    memory = by_id["oppositions.memory_entry"]
    assert memory.metadata.get("not_official_state") is True
    assert memory.metadata.get("proposal_only") is True


def test_deterministic_order():
    a = build_oppositions_resource_definitions()
    b = build_oppositions_resource_definitions()
    assert [r.id for r in a] == [r.id for r in b]
    assert [r.id for r in a] == sorted([r.id for r in a])


def test_provenance_and_temporal_metadata():
    resources = build_oppositions_resource_definitions()
    by_id = {r.id: r for r in resources}
    call = by_id["oppositions.official_call"]
    assert call.metadata.get("provenance") is True
    assert call.metadata.get("temporality") is True
    assert call.temporal_policy.effective_date_required is True
