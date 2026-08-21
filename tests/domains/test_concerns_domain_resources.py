"""Phase 10.25 — Concerns Domain resource tests.

Ten resource definitions over the shared resource contracts.  Resources are
definitions only; a resource existing is never the same as a fact being
authoritative, ``domain_result`` is the authorized cross-domain projection
boundary, ``memory_entry`` is provenance (not current truth), and
``external_source`` is NOT external-search authorization.
"""

from __future__ import annotations

from cmm.cognitive.enums import SensitivityLevel
from cmm.domains.concerns.catalog import (
    CANONICAL_CONCERNS_RESOURCE_IDS,
    CONCERNS_RESOURCE_KINDS,
)
from cmm.domains.concerns.resources import build_concerns_resource_definitions


def test_exactly_10_resources():
    resources = build_concerns_resource_definitions()
    assert len(resources) == 10
    assert [r.id for r in resources] == list(CANONICAL_CONCERNS_RESOURCE_IDS)


def test_resource_ids_and_kinds():
    resources = build_concerns_resource_definitions()
    by_id = {r.id: r for r in resources}
    assert set(by_id) == set(CANONICAL_CONCERNS_RESOURCE_IDS)
    for resource in resources:
        assert str(resource.domain_id) == "domain:concerns"
        assert resource.kind == resource.id.split(".", 1)[1]
    assert tuple(r.kind for r in resources) == CONCERNS_RESOURCE_KINDS


def test_shared_adapter_resources_reused():
    """Every resource reuses the shared cognitive adapters; no new store."""
    resources = build_concerns_resource_definitions()
    by_id = {r.id: r for r in resources}
    assert by_id["concerns.user_message"].adapter == "cognitive.message"
    assert by_id["concerns.conversation"].adapter == "cognitive.conversation"
    assert by_id["concerns.note"].adapter == "cognitive.note"
    assert by_id["concerns.journal_entry"].adapter == "cognitive.note"
    assert by_id["concerns.memory_entry"].adapter == "cognitive.memory"
    assert by_id["concerns.event"].adapter == "cognitive.event"
    assert by_id["concerns.goal"].adapter == "cognitive.goal"
    assert by_id["concerns.decision"].adapter == "cognitive.goal"
    assert by_id["concerns.domain_result"].adapter == "cognitive.event"
    assert by_id["concerns.external_source"].adapter == "cognitive.note"


def test_high_sensitivity_sources():
    resources = build_concerns_resource_definitions()
    by_id = {r.id: r for r in resources}
    # Concerns is sensitive/high sensitivity: user messages and journals carry
    # fears/vulnerabilities; domain results are sensitive projections.
    for resource_id in (
        "concerns.user_message",
        "concerns.journal_entry",
        "concerns.memory_entry",
        "concerns.domain_result",
    ):
        assert by_id[resource_id].default_sensitivity is SensitivityLevel.SENSITIVE


def test_domain_result_is_cross_domain_projection_boundary():
    resources = build_concerns_resource_definitions()
    projection = {r.id for r in resources}["x"] if False else None
    del projection
    by_id = {r.id: r for r in resources}
    boundary = by_id["concerns.domain_result"]
    assert boundary.metadata.get("cross_domain_projection") is True
    assert boundary.metadata.get("minimal_authorized_projection") is True
    assert boundary.metadata.get("no_private_store_merge") is True


def test_memory_entry_is_provenance_not_truth():
    resources = build_concerns_resource_definitions()
    memory = {r.id: r for r in resources}["concerns.memory_entry"]
    assert memory.metadata.get("memory_integration") is True
    assert memory.metadata.get("proposal_only") is True
    assert memory.metadata.get("provenance_not_truth") is True


def test_external_source_is_not_search_authorization():
    resources = build_concerns_resource_definitions()
    external = {r.id: r for r in resources}["concerns.external_source"]
    assert external.metadata.get("external_search_authorized") is False
    assert external.metadata.get("unverified") is True
    assert external.metadata.get("provenance_not_authorization") is True


def test_entity_type_vocabulary_is_canonical():
    """Resource entity types draw from the canonical 17-entity vocabulary."""
    from cmm.domains.concerns.catalog import CANONICAL_CONCERNS_ENTITY_TYPES

    allowed = set(CANONICAL_CONCERNS_ENTITY_TYPES)
    for resource in build_concerns_resource_definitions():
        assert set(resource.entity_types) <= allowed


def test_deterministic_order():
    a = build_concerns_resource_definitions()
    b = build_concerns_resource_definitions()
    assert [r.id for r in a] == [r.id for r in b]
