"""Tests for Phase 10.27 Parenthood Workspaces and Isolation Contracts."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from cmm.domains.parenthood.workspaces import (
    build_child_workspace,
    ensure_sibling_identity_isolation,
    parse_parenthood_scope,
    select_journey_transfer_candidates,
    validate_child_workspace,
)


def test_parse_parenthood_scope_journey() -> None:
    """Verify parsing journey scope."""
    scope = parse_parenthood_scope("parenthood.journey")
    assert scope.kind == "journey"
    assert scope.child_id is None
    assert scope.scope_id == "parenthood.journey"


def test_parse_parenthood_scope_child() -> None:
    """Verify parsing child scope."""
    scope = parse_parenthood_scope("parenthood.child:child_001")
    assert scope.kind == "child"
    assert scope.child_id == "child_001"
    assert scope.scope_id == "parenthood.child:child_001"


def test_parse_parenthood_scope_invalid() -> None:
    """Verify invalid scope formats are rejected."""
    with pytest.raises(ValueError):
        parse_parenthood_scope("invalid.scope")
    with pytest.raises(ValueError):
        parse_parenthood_scope("parenthood.child:")
    with pytest.raises(ValueError):
        parse_parenthood_scope("parenthood.unknown")


def test_child_workspace_creation_and_validation() -> None:
    """Verify ChildParentingWorkspace creation and invariants."""
    ws = build_child_workspace(
        id="child:001",
        display_name="Sofía",
        developmental_stage="infant",
        created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        metadata={"notes": "healthy"},
    )
    assert ws.id == "child:001"
    assert ws.domain_id == "domain:parenthood"
    assert ws.display_name == "Sofía"
    assert ws.status == "active"
    assert ws.developmental_stage == "infant"
    assert validate_child_workspace(ws) is True


def test_child_display_name_mutation_preserves_internal_id() -> None:
    """Verify display name can change without altering stable internal workspace identity."""
    ws1 = build_child_workspace(
        id="child:001",
        display_name="Baby A",
    )
    ws2 = build_child_workspace(
        id="child:001",
        display_name="Lucas",
    )
    assert ws1.id == ws2.id == "child:001"
    assert ws1.display_name != ws2.display_name
    assert ws1.domain_id == ws2.domain_id == "domain:parenthood"


def test_sibling_identity_isolation() -> None:
    """Verify strict isolation between different sibling workspaces."""
    child_b = build_child_workspace(id="child:002", display_name="Mateo")

    # Record scoped to child_a
    record_a = {
        "child_id": "child:001",
        "data": "allergy to penicillin",
        "is_shared_family_context": False,
    }

    # Accessing record_a from child_b context must be rejected
    isolation_check = ensure_sibling_identity_isolation(
        target_workspace=child_b,
        record=record_a,
    )
    assert isolation_check["isolated"] is True
    assert isolation_check["access_allowed"] is False
    assert isolation_check["reason"] == "sibling_identity_mismatch"

    # Explicit shared family context is allowed
    shared_record = {
        "child_id": None,
        "data": "family holiday residence in Valencia",
        "is_shared_family_context": True,
    }
    shared_check = ensure_sibling_identity_isolation(
        target_workspace=child_b,
        record=shared_record,
    )
    assert shared_check["access_allowed"] is True


def test_journey_to_child_selective_transfer() -> None:
    """Verify explicit candidate selection requirement for journey -> child transfer."""
    journey_ctx = {
        "pediatrician": {
            "category": "contact",
            "name": "Dr. Miller",
            "clinic": "Valencia Pediatrics",
        },
        "donor_medical_history": {
            "category": "clinical_history",
            "blood_type": "O+",
        },
    }

    # Bulk transfer without explicit selection is rejected
    with pytest.raises(ValueError, match="bulk copy prohibited"):
        select_journey_transfer_candidates(
            journey_context=journey_ctx,
            selected_keys=None,
            target_child_id="child:001",
            allow_bulk_transfer=True,
        )

    # Explicit selective transfer succeeds
    transfers = select_journey_transfer_candidates(
        journey_context=journey_ctx,
        selected_keys=("pediatrician",),
        target_child_id="child:001",
    )
    assert len(transfers) == 1
    assert transfers[0]["key"] == "pediatrician"
    assert transfers[0]["category"] == "contact"
    assert transfers[0]["target_child_id"] == "child:001"
    assert transfers[0]["provenance"]["transfer_authorized"] is True
