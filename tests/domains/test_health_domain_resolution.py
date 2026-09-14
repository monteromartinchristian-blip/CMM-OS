"""Tests for Phase 10.20 fallback and resolution with Health Domain.

Section 15 invariant: General Domain must NOT silently absorb a signal
intended for Health when Health is unavailable / denied / not allowed /
unauthorized / disabled (degraded when disallowed).  The generic resolver
fallback guard enforces this; these tests prove it holds for Health without
weakening or special-casing the resolver.
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
HEALTH = DomainId(slug="health")


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


def _health_signal(value="health-signal", confidence=0.9) -> DomainResolutionSignal:
    return DomainResolutionSignal(
        kind="intent",
        source="test",
        value=value,
        domain_ids=(HEALTH,),
        confidence=confidence,
        provenance={"source": "test"},
    )


def _resolver() -> DefaultDomainResolver:
    return DefaultDomainResolver(
        fallback_domain=GENERAL,
        clock=lambda: NOW,
        id_factory=lambda: "id1",
    )


def test_health_signal_selects_health_when_authorized():
    result = _resolver().resolve(
        _context(
            available=(GENERAL, HEALTH),
            authorized=(GENERAL, HEALTH),
            objective="medical symptom",
            signals=(_health_signal(),),
        )
    )
    assert result.primary_domain == HEALTH


def test_health_signal_not_absorbed_when_health_unauthorized():
    """Health is not authorized: General must NOT silently take over."""
    result = _resolver().resolve(
        _context(
            available=(GENERAL, HEALTH),
            authorized=(GENERAL,),
            objective="medical symptom",
            signals=(_health_signal(),),
        )
    )
    assert result.status is DomainResolutionStatus.BLOCKED
    assert result.primary_domain is None
    assert result.fallback_used is False
    assert any(r.code == "DOMAIN_UNAUTHORIZED_REJECTED" for r in result.reasons)


def test_health_signal_not_absorbed_when_health_denied():
    """Health is policy-denied: its action must not be converted via general."""
    policy = DomainResolutionPolicy(denied_domains=(HEALTH,))
    result = _resolver().resolve(
        _context(
            available=(GENERAL, HEALTH),
            authorized=(GENERAL,),
            policy=policy,
            objective="medical symptom",
            signals=(_health_signal(),),
        )
    )
    assert result.status is DomainResolutionStatus.BLOCKED
    assert result.primary_domain is None
    assert result.fallback_used is False
    assert HEALTH in result.rejected_domains
    assert any(r.code == "DOMAIN_POLICY_DENIED" for r in result.reasons)


def test_health_signal_not_absorbed_when_health_disabled():
    """Health is unavailable (not in the available set): General must not absorb."""
    result = _resolver().resolve(
        _context(
            available=(GENERAL,),
            authorized=(GENERAL,),
            objective="medical symptom",
            signals=(_health_signal(),),
        )
    )
    # Health cannot be served here, but General must not silently absorb the
    # health-intent signal: the resolution is blocked / not served as health.
    assert result.primary_domain is None
    assert result.fallback_used is False
    assert result.status is DomainResolutionStatus.BLOCKED
