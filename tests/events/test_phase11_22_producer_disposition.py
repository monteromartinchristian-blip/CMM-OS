"""Phase 11.22 — executable producer-disposition matrix.

Every one of the twenty catalog events must carry exactly one disposition, and a
``CONNECTED_EXISTING_OWNER`` claim is only allowed when the repository actually
contains the executable evidence that connects it.  These tests turn the
documented matrix into a gate, so the documentation cannot drift away from the
code and no catalog event can be marked connected without proof.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from cmm.events.event_catalog import (
    PLATFORM_EVENT_CATALOG,
    ProducerDisposition,
    canonical_registration_names,
    catalog_spec,
    specs_by_disposition,
)

REPO_ROOT = Path(__file__).resolve().parents[2]

CONNECTED = ProducerDisposition.CONNECTED_EXISTING_OWNER
CANONICAL = ProducerDisposition.CANONICAL_EXISTING_RUNTIME_EVENT
RESERVED = ProducerDisposition.REGISTERED_RESERVED_OWNER_NOT_YET_AVAILABLE

#: The frozen disposition of every catalog event.  Changing this table is a
#: deliberate architectural act and must be accompanied by real connection
#: evidence, not by a documentation edit.
EXPECTED_DISPOSITIONS: dict[str, ProducerDisposition] = {
    "session.created": RESERVED,
    "message.received": CONNECTED,
    "intent.resolved": CONNECTED,
    "domain.selected": CONNECTED,
    "reasoning.completed": RESERVED,
    "goal.created": CANONICAL,
    "goal.updated": CANONICAL,
    "workflow.started": CONNECTED,
    "workflow.paused": CONNECTED,
    "workflow.completed": CONNECTED,
    "workflow.failed": CONNECTED,
    "operation.executed": CONNECTED,
    "validation.completed": CONNECTED,
    "approval.requested": CONNECTED,
    "approval.resolved": CONNECTED,
    "knowledge.updated": RESERVED,
    "memory.updated": CONNECTED,
    "backup.created": RESERVED,
    "plugin.failed": RESERVED,
    "security.alert": RESERVED,
}

#: The exact canonical owner of every non-reserved catalog event.
EXPECTED_OWNERS: dict[str, str] = {
    "message.received": "cmm.orchestration",
    "intent.resolved": "cmm.orchestration",
    "domain.selected": "cmm.orchestration",
    "goal.created": "cmm.agent_runtime",
    "goal.updated": "cmm.agent_runtime",
    "workflow.started": "cmm.workflows",
    "workflow.paused": "cmm.workflows",
    "workflow.completed": "cmm.workflows",
    "workflow.failed": "cmm.workflows",
    "operation.executed": "cmm.agent_runtime",
    "validation.completed": "cmm.validation",
    "approval.requested": "cmm.orchestration",
    "approval.resolved": "cmm.domains",
    "memory.updated": "cmm.domains",
}


def test_matrix_covers_every_catalog_event_exactly_once() -> None:
    assert set(EXPECTED_DISPOSITIONS) == {spec.name for spec in PLATFORM_EVENT_CATALOG}
    assert len(EXPECTED_DISPOSITIONS) == len(PLATFORM_EVENT_CATALOG)


@pytest.mark.parametrize("name", sorted(EXPECTED_DISPOSITIONS))
def test_catalog_disposition_matches_the_frozen_matrix(name: str) -> None:
    assert catalog_spec(name).disposition is EXPECTED_DISPOSITIONS[name]


@pytest.mark.parametrize("name", sorted(EXPECTED_OWNERS))
def test_connected_events_name_their_real_owner(name: str) -> None:
    spec = catalog_spec(name)

    assert spec.owner == EXPECTED_OWNERS[name]
    assert spec.disposition in (CONNECTED, CANONICAL)


def test_every_catalog_event_has_exactly_one_status() -> None:
    statuses = [spec.disposition for spec in PLATFORM_EVENT_CATALOG]

    assert len(statuses) == len(PLATFORM_EVENT_CATALOG)
    assert all(isinstance(status, ProducerDisposition) for status in statuses)


def test_disposition_counts_are_the_frozen_counts() -> None:
    assert len(specs_by_disposition(CONNECTED)) == 12
    assert len(specs_by_disposition(CANONICAL)) == 2
    assert len(specs_by_disposition(RESERVED)) == 6


def test_reserved_events_are_never_emitted_by_phase11_22() -> None:
    """No Phase 11.22 mapping may target a reserved catalog event."""

    from cmm.events.event_translation import (
        KERNEL_SOURCE_TRANSLATIONS,
        ORCHESTRATION_SOURCE_TRANSLATIONS,
    )

    reserved = {spec.name for spec in specs_by_disposition(RESERVED)}
    targets = {
        translation.platform_event_type
        for translation in (
            *KERNEL_SOURCE_TRANSLATIONS,
            *ORCHESTRATION_SOURCE_TRANSLATIONS,
        )
    }

    assert reserved & targets == set()


def test_reserved_events_have_no_producer_code_in_the_repository() -> None:
    """No module may create a platform event for a reserved capability.

    The only places a reserved name may legitimately appear are the catalog that
    declares it and the canonical registration map that makes the name valid while
    leaving it un-emitted.
    """

    reserved = sorted(spec.name for spec in specs_by_disposition(RESERVED))
    allowed_files = {
        REPO_ROOT / "cmm" / "events" / "event_catalog.py",
        REPO_ROOT / "cmm" / "agent_runtime" / "runtime_event_types.py",
        REPO_ROOT / "cmm" / "events" / "event_payload_safety.py",
        REPO_ROOT / "cmm" / "events" / "storage.py",
        REPO_ROOT / "cmm" / "events" / "__init__.py",
    }

    offenders: list[str] = []
    for path in sorted((REPO_ROOT / "cmm").rglob("*.py")):
        if "__pycache__" in path.parts or path in allowed_files:
            continue
        text = path.read_text()
        for name in reserved:
            if f'"{name}"' in text:
                offenders.append(f"{path.relative_to(REPO_ROOT)}:{name}")

    assert not offenders, f"reserved events must have no producer: {offenders}"


@pytest.mark.parametrize(
    "name",
    sorted(spec.name for spec in specs_by_disposition(CONNECTED)),
)
def test_connected_events_cite_evidence_that_actually_exists(name: str) -> None:
    spec = catalog_spec(name)

    assert spec.connected_evidence
    evidence = REPO_ROOT / spec.connected_evidence
    assert evidence.is_file(), f"missing connection evidence {evidence}"

    text = evidence.read_text()
    # The evidence must actually exercise the mapped platform event name.
    assert name in text, f"{spec.connected_evidence} does not exercise {name}"


def test_canonical_runtime_events_need_no_adapter_evidence() -> None:
    for spec in specs_by_disposition(CANONICAL):
        assert spec.owner == "cmm.agent_runtime"
        assert spec.connected_evidence is None


def test_every_catalog_name_is_registered_through_the_canonical_authority() -> None:
    assert set(canonical_registration_names()) == set(EXPECTED_DISPOSITIONS)


def test_matrix_owners_exist_as_real_packages() -> None:
    for owner in set(EXPECTED_OWNERS.values()):
        package = REPO_ROOT / owner.replace(".", "/")
        assert package.is_dir(), f"owner package {owner} does not exist"


def test_no_connected_event_lacks_an_integration_test() -> None:
    """A connected claim without executable proof is not allowed."""

    for spec in specs_by_disposition(CONNECTED):
        assert spec.connected_evidence is not None
        evidence = REPO_ROOT / spec.connected_evidence
        assert evidence.is_file()
        assert "adapter" in evidence.name or "acceptance" in evidence.name
