"""Tests for Phase 10.8 – Composition Serialization (JSON round-trip, unknown fields, strict types)."""

from __future__ import annotations

import json
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
from cmm.domains.enums import DomainCompositionStatus
from cmm.domains.errors import (
    DomainCompositionContractError,
    DomainCompositionSerializationError,
    DomainSerializationError,
)
from cmm.domains.identifiers import DomainId


def test_policy_json_dumps():
    p = DomainCompositionPolicy()
    d = p.to_dict()
    s = json.dumps(d)
    assert isinstance(s, str)
    loaded = json.loads(s)
    p2 = DomainCompositionPolicy.from_dict(loaded)
    assert p2.to_dict() == p.to_dict()


def test_composition_json_roundtrip_full():
    d1 = DomainId.from_str("domain:alpha")
    d2 = DomainId.from_str("domain:beta")

    profile = EffectiveReasoningProfile(base_profile="default")
    perm = PermissionComposition(
        required_permissions=("perm-a",),
        denied_permissions=("perm-b",),
    )
    pres = PresentationComposition(
        values={"theme": "dark"},
        provenance={"theme": ["domain:alpha"]},
    )
    item = DomainCompositionItem(
        category="rules",
        identifier="r1",
        contributing_domains=(d1,),
        primary_contributor=d1,
        precedence=0,
    )
    policy = DomainCompositionPolicy()

    comp = DomainComposition(
        id="comp-1",
        resolution_id="res-1",
        status=DomainCompositionStatus.COMPOSED,
        primary_domain=d1,
        supporting_domains=(d2,),
        effective_profile=profile,
        rules=(item,),
        permissions=perm,
        presentation=pres,
        policy=policy,
        composed_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
    )
    d = comp.to_dict()
    s = json.dumps(d)
    loaded = json.loads(s)
    comp2 = DomainComposition.from_dict(loaded)
    assert comp2.to_dict() == comp.to_dict()


def test_unknown_fields_on_composition():
    with pytest.raises(
        (
            DomainCompositionSerializationError,
            DomainCompositionContractError,
            DomainSerializationError,
        )
    ):
        DomainComposition.from_dict(
            {
                "id": "x",
                "resolution_id": "y",
                "status": "composed",
                "primary_domain": "domain:a",
                "composed_at": datetime.now(timezone.utc).isoformat(),
                "extra_field": 42,
            }
        )


def test_unknown_fields_on_item():
    with pytest.raises((DomainCompositionSerializationError, DomainSerializationError)):
        DomainCompositionItem.from_dict(
            {
                "category": "c",
                "identifier": "i",
                "contributing_domains": ["domain:a"],
                "primary_contributor": "domain:a",
                "precedence": 1,
                "extra": True,
            }
        )


def test_unknown_fields_on_policy():
    with pytest.raises(
        (
            DomainCompositionSerializationError,
            DomainCompositionContractError,
            DomainSerializationError,
        )
    ):
        DomainCompositionPolicy.from_dict(
            {"conflict_policy": "most_restrictive", "zzz": 1}
        )


def test_bool_rejected_as_int():
    """Bool-as-int for precedence must be rejected."""
    with pytest.raises(
        (DomainCompositionSerializationError, DomainCompositionContractError)
    ):
        DomainCompositionItem.from_dict(
            {
                "category": "rules",
                "identifier": "r1",
                "contributing_domains": ["domain:a"],
                "primary_contributor": "domain:a",
                "precedence": True,
            }
        )


def test_conflict_blocking_strict_bool():
    """blocking must be strict bool, not int."""
    with pytest.raises(DomainCompositionSerializationError):
        DomainCompositionConflict.from_dict(
            {
                "code": "X",
                "category": "c",
                "domains": ["domain:a"],
                "severity": "high",
                "message": "test",
                "blocking": 1,
            }
        )


def test_conflict_resolved_strict_bool():
    """resolved must be strict bool."""
    with pytest.raises(DomainCompositionSerializationError):
        DomainCompositionConflict.from_dict(
            {
                "code": "X",
                "category": "c",
                "domains": ["domain:a"],
                "severity": "high",
                "message": "test",
                "blocking": False,
                "resolved": 0,
            }
        )


def test_decision_blocking_strict_bool():
    """Decision.from_dict must reject int for blocking."""
    with pytest.raises(DomainCompositionSerializationError):
        DomainCompositionDecision.from_dict(
            {
                "code": "X",
                "category": "c",
                "action": "a",
                "blocking": 1,
            }
        )


def test_nan_inf_rejected():
    with pytest.raises(
        (DomainCompositionSerializationError, DomainCompositionContractError)
    ):
        EffectiveReasoningProfile.from_dict(
            {
                "base_profile": "p",
                "minimum_confidence": float("nan"),
            }
        )


def test_maximum_inference_depth_bool_rejected():
    """True is not a valid integer for maximum_inference_depth."""
    with pytest.raises(
        (DomainCompositionSerializationError, DomainCompositionContractError)
    ):
        DomainCompositionItem.from_dict(
            {
                "category": "rules",
                "identifier": "r1",
                "contributing_domains": ["domain:a"],
                "primary_contributor": "domain:a",
                "precedence": True,
            }
        )


def test_permissions_prefix_overlap_rejected():
    """Cross-group prefix overlap must be rejected."""
    with pytest.raises(
        (DomainCompositionSerializationError, DomainCompositionContractError)
    ):
        DomainCompositionPolicy.from_dict(
            {
                "denied_permission_prefixes": ["deny:"],
                "granted_permission_prefixes": ["deny:"],
            }
        )


def test_permissions_prefix_substring_overlap_allowed():
    """Prefixes where one is substring of another in different groups must be rejected."""
    with pytest.raises(
        (DomainCompositionSerializationError, DomainCompositionContractError)
    ):
        DomainCompositionPolicy.from_dict(
            {
                "denied_permission_prefixes": ["deny:"],
                "required_permission_prefixes": ["deny:"],
            }
        )
