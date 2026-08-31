"""Tests for Phase 10.22 University Domain resources."""

from __future__ import annotations

from cmm.cognitive.enums import SensitivityLevel
from cmm.domains import university
from cmm.domains.university.catalog import CANONICAL_UNIVERSITY_RESOURCE_IDS


def test_twelve_resources_and_sorted_ids():
    resources = university.build_university_resource_definitions()
    assert len(resources) == 12
    assert [r.id for r in resources] == list(CANONICAL_UNIVERSITY_RESOURCE_IDS)


def test_sensitivity_contracts():
    resources = {r.id: r for r in university.build_university_resource_definitions()}
    # Official-capable academic state records are SENSITIVE.
    assert (
        resources["university.academic_record"].default_sensitivity
        is SensitivityLevel.SENSITIVE
    )
    assert (
        resources["university.grade"].default_sensitivity is SensitivityLevel.SENSITIVE
    )
    # Non-official, user-reported resources are PERSONAL (never HIGHLY_SENSITIVE).
    assert resources["university.note"].default_sensitivity is SensitivityLevel.PERSONAL
    assert (
        resources["university.memory_entry"].default_sensitivity
        is SensitivityLevel.PERSONAL
    )


def test_domain_and_kind():
    for resource in university.build_university_resource_definitions():
        assert resource.domain_id == "domain:university"
        assert resource.kind == resource.id.split(".", 1)[1]


def test_entity_types_subset_of_catalog():
    from cmm.domains.university.catalog import CANONICAL_UNIVERSITY_ENTITY_TYPES

    allowed = set(CANONICAL_UNIVERSITY_ENTITY_TYPES)
    for resource in university.build_university_resource_definitions():
        assert set(resource.entity_types) <= allowed


def test_email_resource_no_authorization_send():
    """university.email represents an existing email/email context; it must
    never authorize sending."""
    resources = {r.id: r for r in university.build_university_resource_definitions()}
    email = resources["university.email"]
    assert email.metadata.get("no_authorization_send") is True
    assert email.metadata.get("preparation_only") is True


def test_memory_entry_never_overrides_academic_state():
    """university.memory_entry represents personal memory and must never be
    Academic State."""
    resources = {r.id: r for r in university.build_university_resource_definitions()}
    memory_entry = resources["university.memory_entry"]
    assert memory_entry.metadata.get("not_academic_state") is True
    assert memory_entry.metadata.get("proposal_only") is True


def test_academic_record_is_academic_state_official_capable():
    """university.academic_record is Academic State and official-capable."""
    resources = {r.id: r for r in university.build_university_resource_definitions()}
    academic_record = resources["university.academic_record"]
    assert academic_record.metadata.get("academic_state") is True
    assert academic_record.metadata.get("official_capable") is True


def test_regulation_has_expiration_required():
    """university.regulation is a temporal regulation with expiration."""
    resources = {r.id: r for r in university.build_university_resource_definitions()}
    regulation = resources["university.regulation"]
    assert regulation.temporal_policy.expiration_required is True
    assert regulation.temporal_policy.effective_date_required is True
    assert regulation.metadata.get("regulation") is True
