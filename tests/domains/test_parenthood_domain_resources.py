"""Tests for Phase 10.27 Parenthood Domain Resources."""

from __future__ import annotations

from cmm.cognitive.enums import SensitivityLevel
from cmm.domains.parenthood.catalog import (
    CANONICAL_PARENTHOOD_RESOURCE_IDS,
    PARENTHOOD_RESOURCE_KINDS,
)
from cmm.domains.parenthood.resources import build_parenthood_resource_definitions


def test_parenthood_resource_definitions_count_and_ids() -> None:
    """Verify exact count and canonical IDs of resource definitions."""
    definitions = build_parenthood_resource_definitions()
    assert len(definitions) == 19
    resource_ids = tuple(d.id for d in definitions)
    assert resource_ids == CANONICAL_PARENTHOOD_RESOURCE_IDS

    kinds = tuple(d.kind for d in definitions)
    assert kinds == PARENTHOOD_RESOURCE_KINDS


def test_parenthood_resource_definitions_domain_id() -> None:
    """Verify all resources belong to domain:parenthood."""
    definitions = build_parenthood_resource_definitions()
    for d in definitions:
        assert str(d.domain_id) == "domain:parenthood"


def test_parenthood_resource_definitions_sensitivities() -> None:
    """Verify sensitive resources have appropriate sensitivity classifications."""
    defs_by_id = {d.id: d for d in build_parenthood_resource_definitions()}

    # Medical, legal, parenting notes, health summaries, and memory entries must be SENSITIVE
    assert (
        defs_by_id["parenthood.resource.medical_report"].default_sensitivity
        == SensitivityLevel.SENSITIVE
    )
    assert (
        defs_by_id["parenthood.resource.legal_document"].default_sensitivity
        == SensitivityLevel.SENSITIVE
    )
    assert (
        defs_by_id["parenthood.resource.parenting_note"].default_sensitivity
        == SensitivityLevel.SENSITIVE
    )
    assert (
        defs_by_id["parenthood.resource.health_summary"].default_sensitivity
        == SensitivityLevel.SENSITIVE
    )
    assert (
        defs_by_id["parenthood.resource.memory_entry"].default_sensitivity
        == SensitivityLevel.SENSITIVE
    )


def test_parenthood_resource_temporal_policies() -> None:
    """Verify temporal requirements on legal and jurisdiction resources."""
    defs_by_id = {d.id: d for d in build_parenthood_resource_definitions()}

    legal_doc = defs_by_id["parenthood.resource.legal_document"]
    assert legal_doc.temporal_policy.effective_date_required is True

    jurisdiction_info = defs_by_id["parenthood.resource.jurisdiction_information"]
    assert jurisdiction_info.temporal_policy.effective_date_required is True
