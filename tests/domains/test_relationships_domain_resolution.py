"""Tests for Phase 10.21 fallback and resolution with Relationships Domain.

Section 15 invariant: General Domain must NOT silently absorb a signal
intended for Relationships when Relationships is unavailable / denied / not
allowed / unauthorized / disabled (degraded when disallowed).  The generic
resolver fallback guard enforces this; these tests prove it holds for
Relationships without weakening or special-casing the resolver.
"""

from __future__ import annotations

from datetime import datetime, timezone

from cmm.domains.enums import DomainResolutionStatus
from cmm.domains.identifiers import DomainId
from cmm.domains.resolution_contracts import (
    DomainResolutionContext,
    DomainResolutionPolicy,
    DomainResolutionSignal,
)
from cmm.domains.resolver import DefaultDomainResolver

NOW = datetime(2026, 8, 1, tzinfo=timezone.utc)
GENERAL = DomainId(slug="general")
RELATIONSHIPS = DomainId(slug="relationships")


def _context(
    *,
    available=(GENERAL,),
    authorized=(GENERAL,),
    explicit=(),
    objective="general request",
    policy=None,
    signals=(),
) -> DomainResolutionContext:
    return DomainResolutionContext(
        id="ctx1",
        objective=objective,
        available_domains=available,
        authorized_domains=authorized,
        explicit_domains=explicit,
        system_policy=policy,
        signals=signals,
        created_at=NOW,
    )


def _relationships_signal(value="relationships-signal", confidence=0.9):
    return DomainResolutionSignal(
        kind="intent",
        source="test",
        value=value,
        domain_ids=(RELATIONSHIPS,),
        confidence=confidence,
        provenance={"source": "test"},
    )


def _resolver() -> DefaultDomainResolver:
    return DefaultDomainResolver(
        fallback_domain=GENERAL,
        clock=lambda: NOW,
        id_factory=lambda: "id1",
    )


def test_relationships_signal_selects_relationships_when_authorized():
    result = _resolver().resolve(
        _context(
            available=(GENERAL, RELATIONSHIPS),
            authorized=(GENERAL, RELATIONSHIPS),
            objective="relationship question",
            signals=(_relationships_signal(),),
        )
    )
    assert result.primary_domain == RELATIONSHIPS


def test_relationships_signal_not_absorbed_when_unauthorized():
    """Relationships is not authorized: General must NOT silently take over."""
    result = _resolver().resolve(
        _context(
            available=(GENERAL, RELATIONSHIPS),
            authorized=(GENERAL,),
            objective="relationship question",
            signals=(_relationships_signal(),),
        )
    )
    assert result.status is DomainResolutionStatus.BLOCKED
    assert result.primary_domain is None
    assert result.fallback_used is False
    assert any(r.code == "DOMAIN_UNAUTHORIZED_REJECTED" for r in result.reasons)


def test_relationships_signal_not_absorbed_when_denied():
    """Relationships is policy-denied: its intent must not be converted via
    general."""
    policy = DomainResolutionPolicy(denied_domains=(RELATIONSHIPS,))
    result = _resolver().resolve(
        _context(
            available=(GENERAL, RELATIONSHIPS),
            authorized=(GENERAL,),
            policy=policy,
            objective="relationship question",
            signals=(_relationships_signal(),),
        )
    )
    assert result.status is DomainResolutionStatus.BLOCKED
    assert result.primary_domain is None
    assert result.fallback_used is False
    assert RELATIONSHIPS in result.rejected_domains
    assert any(r.code == "DOMAIN_POLICY_DENIED" for r in result.reasons)


def test_relationships_signal_not_absorbed_when_disabled():
    """Relationships is unavailable (not in the available set): General must
    not absorb."""
    result = _resolver().resolve(
        _context(
            available=(GENERAL,),
            authorized=(GENERAL,),
            objective="relationship question",
            signals=(_relationships_signal(),),
        )
    )
    # Relationships cannot be served here, but General must not silently absorb
    # the relationships-intent signal: the resolution is blocked / not served
    # as relationships.
    assert result.primary_domain is None
    assert result.fallback_used is False
    assert result.status is DomainResolutionStatus.BLOCKED
