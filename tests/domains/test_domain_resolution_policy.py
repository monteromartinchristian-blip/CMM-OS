"""Phase 10.6 — Tests for DomainResolutionPolicy."""

from __future__ import annotations

import json
from dataclasses import FrozenInstanceError

import pytest

from cmm.domains.errors import DomainContractValidationError
from cmm.domains.identifiers import DomainId
from cmm.domains.resolution_contracts import (
    DomainResolutionPolicy,
    DomainResolutionPolicyError,
    DomainResolutionSerializationError,
)


def _domain(slug: str) -> DomainId:
    return DomainId.from_str(f"domain:{slug}")


class TestDomainResolutionPolicy:
    def test_default_construction(self) -> None:
        p = DomainResolutionPolicy()
        assert p.allowed_domains == ()
        assert p.denied_domains == ()
        assert p.allow_degraded is True
        assert p.allow_experimental is False
        assert p.require_authorization is True
        assert p.minimum_confidence is None

    def test_allowed_denied_overlap_rejected(self) -> None:
        with pytest.raises(DomainResolutionPolicyError, match="overlap"):
            DomainResolutionPolicy(
                allowed_domains=[_domain("a")],
                denied_domains=[_domain("a")],
            )

    def test_required_denied_rejected(self) -> None:
        with pytest.raises(DomainResolutionPolicyError, match="denied"):
            DomainResolutionPolicy(
                required_domains=[_domain("a")],
                denied_domains=[_domain("a")],
            )

    def test_strict_bools_rejected(self) -> None:
        with pytest.raises(DomainContractValidationError, match="boolean"):
            DomainResolutionPolicy(allow_disabled=1)  # type: ignore[arg-type]

    def test_minimum_confidence_out_of_range(self) -> None:
        with pytest.raises(DomainContractValidationError, match="minimum_confidence"):
            DomainResolutionPolicy(minimum_confidence=1.5)

    def test_minimum_confidence_nan(self) -> None:
        with pytest.raises(DomainContractValidationError, match="minimum_confidence"):
            DomainResolutionPolicy(minimum_confidence=float("nan"))

    def test_high_impact_domains_unique(self) -> None:
        with pytest.raises(DomainContractValidationError, match="Duplicate"):
            DomainResolutionPolicy(
                high_impact_domains=[_domain("a"), _domain("a")],
            )

    def test_serialization_roundtrip(self) -> None:
        p = DomainResolutionPolicy(
            allowed_domains=[_domain("x")],
            denied_domains=[_domain("y")],
            required_domains=[_domain("z")],
            allow_degraded=False,
            high_impact_domains=[_domain("x")],
            minimum_confidence=0.8,
            metadata={"key": "val"},
        )
        d = p.to_dict()
        json.dumps(d)
        p2 = DomainResolutionPolicy.from_dict(d)
        assert p == p2

    def test_from_dict_strict_bools_rejected(self) -> None:
        d = {
            "allow_disabled": 1,
        }
        with pytest.raises(DomainResolutionSerializationError, match="boolean"):
            DomainResolutionPolicy.from_dict(d)

    def test_from_dict_minimum_confidence(self) -> None:
        d = {
            "minimum_confidence": 0.5,
        }
        p = DomainResolutionPolicy.from_dict(d)
        assert p.minimum_confidence == 0.5

    def test_immutable(self) -> None:
        p = DomainResolutionPolicy()
        with pytest.raises(FrozenInstanceError):
            p.allow_disabled = True  # type: ignore[misc]

    def test_credential_keys_rejected(self) -> None:
        with pytest.raises(DomainContractValidationError, match="Credential"):
            DomainResolutionPolicy(metadata={"api_key": "x"})

    def test_no_auto_grant(self) -> None:
        """Policy alone should not grant any domain; it's just restrictions."""
        p = DomainResolutionPolicy(allowed_domains=[_domain("x")])
        assert len(p.allowed_domains) == 1
        assert len(p.denied_domains) == 0
