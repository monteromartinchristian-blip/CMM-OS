"""Tests for Phase 10.26 Languages Domain Resources."""

from __future__ import annotations

from cmm.domains.languages.catalog import (
    CANONICAL_LANGUAGES_RESOURCE_IDS,
    LANGUAGES_RESOURCE_KINDS,
)
from cmm.domains.languages.resources import (
    build_languages_resource_definitions,
)
from cmm.domains.resource_contracts import DomainResourceDefinition


def test_build_languages_resources_count_and_order() -> None:
    """Verify exact 15 resources in canonical catalog order."""
    definitions = build_languages_resource_definitions()
    assert len(definitions) == 15
    assert tuple(d.id for d in definitions) == CANONICAL_LANGUAGES_RESOURCE_IDS
    assert tuple(d.kind for d in definitions) == LANGUAGES_RESOURCE_KINDS


def test_languages_resources_domain_and_adapters() -> None:
    """Verify domain id and cognitive adapter assignments."""
    definitions = build_languages_resource_definitions()
    by_id = {d.id: d for d in definitions}

    for d in definitions:
        assert isinstance(d, DomainResourceDefinition)
        assert d.domain_id == "domain:languages"
        assert d.adapter.startswith("cognitive.")

    assert by_id["languages.user_message"].adapter == "cognitive.message"
    assert by_id["languages.conversation"].adapter == "cognitive.conversation"
    assert by_id["languages.writing_sample"].adapter == "cognitive.note"
    assert by_id["languages.audio_transcript"].adapter == "cognitive.note"
    assert by_id["languages.exercise_result"].adapter == "cognitive.event"
    assert by_id["languages.assessment_result"].adapter == "cognitive.event"
    assert by_id["languages.language_plan"].adapter == "cognitive.goal"
    assert by_id["languages.lesson_material"].adapter == "cognitive.note"
    assert by_id["languages.vocabulary_list"].adapter == "cognitive.note"
    assert by_id["languages.language_reference"].adapter == "cognitive.note"
    assert by_id["languages.certification_guide"].adapter == "cognitive.note"
    assert by_id["languages.official_certification_source"].adapter == "cognitive.event"
    assert by_id["languages.calendar_event"].adapter == "cognitive.event"
    assert by_id["languages.memory_entry"].adapter == "cognitive.memory"
    assert by_id["languages.domain_result"].adapter == "cognitive.event"


def test_languages_resources_key_invariants() -> None:
    """Verify specific metadata, reliability, and sensitivity requirements."""
    by_id = {d.id: d for d in build_languages_resource_definitions()}

    assert (
        by_id["languages.audio_transcript"].metadata["pronunciation_evidence"] is False
    )
    assert (
        by_id["languages.domain_result"].metadata["minimal_authorized_projection"]
        is True
    )
    assert by_id["languages.memory_entry"].metadata["provenance_not_truth"] is True
    assert (
        by_id["languages.official_certification_source"].default_reliability
        > by_id["languages.certification_guide"].default_reliability
    )
    assert (
        by_id["languages.assessment_result"].temporal_policy.effective_date_required
        is True
    )
    assert (
        by_id[
            "languages.official_certification_source"
        ].temporal_policy.effective_date_required
        is True
    )
    assert (
        by_id["languages.calendar_event"].temporal_policy.effective_date_required
        is True
    )
    assert (
        by_id["languages.language_plan"].temporal_policy.effective_date_required is True
    )


def test_languages_resources_serialization_roundtrip() -> None:
    """Verify that every resource definition produces deterministic to_dict."""
    for d in build_languages_resource_definitions():
        data = d.to_dict()
        assert data["id"] == d.id
        assert data["kind"] == d.kind
        assert data["domain_id"] == "domain:languages"
