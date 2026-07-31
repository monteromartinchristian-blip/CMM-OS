"""Tests for Phase 10.8 – Composition Contracts (enums, contract invariants)."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from cmm.domains.composition_contracts import (
    DomainComposition,
    DomainCompositionConflict,
    DomainCompositionDecision,
    DomainCompositionItem,
    DomainCompositionPolicy,
    EffectiveReasoningProfile,
    PermissionComposition,
    PresentationComposition,
)
from cmm.domains.enums import DomainCompositionStatus, DomainConflictPolicy
from cmm.domains.errors import (
    DomainCompositionContractError,
    DomainCompositionSerializationError,
    DomainContractValidationError,
    DomainSerializationError,
)
from cmm.domains.identifiers import DomainId

# ── Enum tests ─────────────────────────────────────────────────────────────────


def test_domain_composition_status_exact_values():
    assert {item.value for item in DomainCompositionStatus} == {
        "composed",
        "partial",
        "blocked",
        "failed",
    }


def test_domain_conflict_policy_exact_values():
    assert {item.value for item in DomainConflictPolicy} == {
        "most_restrictive",
        "primary_precedence",
        "block_on_conflict",
    }


# ── Error hierarchy tests ──────────────────────────────────────────────────────


def test_composition_error_inheritance():
    from cmm.domains.errors import (
        DomainCompositionConfigurationError,
        DomainCompositionContractError,
        DomainCompositionError,
        DomainCompositionExecutionError,
        DomainCompositionSerializationError,
    )

    assert issubclass(DomainCompositionError, Exception)
    assert issubclass(DomainCompositionContractError, DomainCompositionError)
    assert issubclass(DomainCompositionContractError, ValueError)
    assert issubclass(DomainCompositionSerializationError, DomainCompositionError)
    assert issubclass(DomainCompositionConfigurationError, DomainCompositionError)
    assert issubclass(DomainCompositionExecutionError, DomainCompositionError)


# ── DomainCompositionPolicy tests ──────────────────────────────────────────────


def test_policy_defaults():
    p = DomainCompositionPolicy()
    assert p.conflict_policy == DomainConflictPolicy.MOST_RESTRICTIVE
    # Defaults are sorted by _freeze_str_tuple order (preserves input order)
    assert set(p.blocking_severities) == {"critical", "high", "blocking"}
    assert set(p.partial_severities) == {"medium", "warning"}
    assert "deny:" in p.denied_permission_prefixes
    assert "require:" in p.required_permission_prefixes
    assert "allow:" in p.granted_permission_prefixes


def test_policy_str_coercion():
    p = DomainCompositionPolicy(conflict_policy="block_on_conflict")
    assert p.conflict_policy == DomainConflictPolicy.BLOCK_ON_CONFLICT


def test_policy_invalid_conflict_policy():
    with pytest.raises((DomainCompositionContractError, ValueError)):
        DomainCompositionPolicy(conflict_policy="invalid")


def test_policy_overlapping_severities():
    with pytest.raises(DomainCompositionContractError):
        DomainCompositionPolicy(
            blocking_severities=("critical",),
            partial_severities=("critical",),
        )


def test_policy_overlapping_prefixes():
    with pytest.raises(DomainCompositionContractError):
        DomainCompositionPolicy(
            denied_permission_prefixes=("deny:",),
            required_permission_prefixes=("deny:",),
        )


def test_policy_to_dict_roundtrip():
    p = DomainCompositionPolicy()
    d = p.to_dict()
    p2 = DomainCompositionPolicy.from_dict(d)
    assert p.to_dict() == p2.to_dict()


def test_policy_unknown_fields():
    with pytest.raises((DomainCompositionSerializationError, DomainSerializationError)):
        DomainCompositionPolicy.from_dict(
            {"conflict_policy": "most_restrictive", "extra_field": 123}
        )


# ── DomainCompositionItem tests ────────────────────────────────────────────────


def test_item_valid():
    d1 = DomainId.from_str("domain:primary")
    item = DomainCompositionItem(
        category="rules",
        identifier="rule-1",
        contributing_domains=(d1,),
        primary_contributor=d1,
        precedence=1,
    )
    assert item.category == "rules"
    assert item.identifier == "rule-1"


def test_item_empty_category():
    with pytest.raises((DomainCompositionContractError, DomainContractValidationError)):
        DomainCompositionItem(
            category="",
            identifier="x",
            contributing_domains=(DomainId.from_str("domain:a"),),
            primary_contributor=DomainId.from_str("domain:a"),
            precedence=0,
        )


def test_item_empty_contributing_domains():
    with pytest.raises(DomainCompositionContractError):
        DomainCompositionItem(
            category="x",
            identifier="x",
            contributing_domains=(),
            primary_contributor=DomainId.from_str("domain:a"),
            precedence=0,
        )


def test_item_primary_not_in_contributing():
    d1 = DomainId.from_str("domain:abc")
    d2 = DomainId.from_str("domain:xyz")
    with pytest.raises(DomainCompositionContractError):
        DomainCompositionItem(
            category="x",
            identifier="x",
            contributing_domains=(d1,),
            primary_contributor=d2,
            precedence=0,
        )


def test_item_precedence_not_bool():
    d1 = DomainId.from_str("domain:a")
    with pytest.raises(DomainCompositionContractError):
        DomainCompositionItem(
            category="x",
            identifier="x",
            contributing_domains=(d1,),
            primary_contributor=d1,
            precedence=True,
        )


def test_item_roundtrip():
    d1 = DomainId.from_str("domain:alpha")
    d2 = DomainId.from_str("domain:beta")
    item = DomainCompositionItem(
        category="rules",
        identifier="r1",
        contributing_domains=(d1, d2),
        primary_contributor=d1,
        precedence=10,
    )
    d = item.to_dict()
    item2 = DomainCompositionItem.from_dict(d)
    assert item.to_dict() == item2.to_dict()


# ── DomainCompositionDecision tests ────────────────────────────────────────────


def test_decision_valid():
    d = DomainCompositionDecision(
        code="DUMMY",
        category="test",
        identifier=None,
        action="tested",
    )
    assert d.code == "DUMMY"


def test_decision_empty_code():
    with pytest.raises((DomainCompositionContractError, DomainContractValidationError)):
        DomainCompositionDecision(
            code="", category="test", identifier=None, action="tested"
        )


def test_decision_non_string_identifier():
    with pytest.raises(DomainCompositionContractError):
        DomainCompositionDecision(code="X", category="c", identifier=123, action="a")


def test_decision_bool_blocking():
    d = DomainCompositionDecision(
        code="X", category="c", identifier=None, action="a", blocking=True
    )
    assert d.blocking is True


# ── DomainCompositionConflict tests ─────────────────────────────────────────────


def test_conflict_valid():
    d1 = DomainId.from_str("domain:a")
    d2 = DomainId.from_str("domain:b")
    c = DomainCompositionConflict(
        code="X",
        category="c",
        domains=(d1, d2),
        severity="high",
        message="Conflict",
        blocking=True,
    )
    assert c.blocking


def test_conflict_empty_domains():
    with pytest.raises(DomainCompositionContractError):
        DomainCompositionConflict(
            code="X",
            category="c",
            domains=(),
            severity="s",
            message="m",
            blocking=False,
        )


def test_conflict_unresolved_with_resolution():
    d1 = DomainId.from_str("domain:a")
    with pytest.raises(DomainCompositionContractError):
        DomainCompositionConflict(
            code="X",
            category="c",
            domains=(d1,),
            severity="s",
            message="m",
            blocking=False,
            resolved=False,
            resolution="something",
        )


def test_conflict_resolved():
    d1 = DomainId.from_str("domain:a")
    c = DomainCompositionConflict(
        code="X",
        category="c",
        domains=(d1,),
        severity="s",
        message="m",
        blocking=False,
        resolved=True,
        resolution="ok",
    )
    assert c.resolved is True


# ── EffectiveReasoningProfile tests ────────────────────────────────────────────


def test_profile_base_none():
    p = EffectiveReasoningProfile(base_profile=None)
    assert p.base_profile is None


def test_profile_minimum_confidence_range():
    with pytest.raises(DomainCompositionContractError):
        EffectiveReasoningProfile(base_profile=None, minimum_confidence=1.5)


def test_profile_rejects_naive_float_bool():
    with pytest.raises(DomainCompositionContractError):
        EffectiveReasoningProfile(base_profile=None, minimum_confidence=True)


# ── PermissionComposition tests ────────────────────────────────────────────────


def test_permission_defaults():
    p = PermissionComposition()
    assert p.required_permissions == ()
    assert p.granted_permissions == ()
    assert p.denied_permissions == ()
    assert p.unresolved_permissions == ()


# ── PresentationComposition tests ──────────────────────────────────────────────


def test_presentation_values_required():
    with pytest.raises((DomainCompositionContractError, TypeError)):
        PresentationComposition(values=123, provenance={})


# ── DomainComposition status invariants ────────────────────────────────────────


def make_dummy_composition(status, conflicts=()):
    """Helper to create a valid DomainComposition for testing."""
    return DomainComposition(
        id="comp-1",
        resolution_id="res-1",
        status=status,
        primary_domain=DomainId.from_str("domain:test"),
        composed_at=datetime.now(timezone.utc),
        conflicts=conflicts if isinstance(conflicts, tuple) else tuple(conflicts),
    )


def test_composed_rejects_blocking_conflict():
    d1 = DomainId.from_str("domain:a")
    blocking = DomainCompositionConflict(
        code="X",
        category="c",
        domains=(d1,),
        severity="critical",
        message="m",
        blocking=True,
        resolved=False,
    )
    with pytest.raises(DomainCompositionContractError):
        make_dummy_composition(DomainCompositionStatus.COMPOSED, conflicts=(blocking,))


def test_blocked_requires_blocking():
    with pytest.raises(DomainCompositionContractError):
        make_dummy_composition(DomainCompositionStatus.BLOCKED)


def test_composed_without_blocking():
    d1 = DomainId.from_str("domain:a")
    resolved = DomainCompositionConflict(
        code="X",
        category="c",
        domains=(d1,),
        severity="critical",
        message="m",
        blocking=True,
        resolved=True,
        resolution="ok",
    )
    c = make_dummy_composition(DomainCompositionStatus.COMPOSED, conflicts=(resolved,))
    assert c.status == DomainCompositionStatus.COMPOSED


def test_primary_not_in_supporting():
    d1 = DomainId.from_str("domain:test")
    with pytest.raises(DomainCompositionContractError):
        DomainComposition(
            id="comp-1",
            resolution_id="res-1",
            status=DomainCompositionStatus.COMPOSED,
            primary_domain=d1,
            supporting_domains=(d1,),
            composed_at=datetime.now(timezone.utc),
        )


def test_naive_datetime_rejected():
    with pytest.raises((DomainCompositionContractError, DomainContractValidationError)):
        DomainComposition(
            id="comp-1",
            resolution_id="res-1",
            status=DomainCompositionStatus.COMPOSED,
            primary_domain=DomainId.from_str("domain:test"),
            composed_at=datetime.fromisoformat("2024-01-01T00:00:00"),
        )
