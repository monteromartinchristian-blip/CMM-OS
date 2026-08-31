"""Tests for Phase 10.22 fallback and resolution with University Domain.

Section 15 invariant: General Domain must NOT silently absorb a signal
intended for University when University is unavailable / denied / not allowed /
unauthorized / disabled (degraded when disallowed).  The generic resolver
fallback guard enforces this; these tests prove it holds for University without
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
UNIVERSITY = DomainId(slug="university")


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


def _university_signal(value="university-signal", confidence=0.9):
    return DomainResolutionSignal(
        kind="intent",
        source="test",
        value=value,
        domain_ids=(UNIVERSITY,),
        confidence=confidence,
        provenance={"source": "test"},
    )


def _resolver() -> DefaultDomainResolver:
    return DefaultDomainResolver(
        fallback_domain=GENERAL,
        clock=lambda: NOW,
        id_factory=lambda: "id1",
    )


def test_university_signal_selects_university_when_authorized():
    result = _resolver().resolve(
        _context(
            available=(GENERAL, UNIVERSITY),
            authorized=(GENERAL, UNIVERSITY),
            objective="academic question",
            signals=(_university_signal(),),
        )
    )
    assert result.primary_domain == UNIVERSITY


def test_university_signal_not_absorbed_when_unauthorized():
    """University is not authorized: General must NOT silently take over."""
    result = _resolver().resolve(
        _context(
            available=(GENERAL, UNIVERSITY),
            authorized=(GENERAL,),
            objective="academic question",
            signals=(_university_signal(),),
        )
    )
    assert result.status is DomainResolutionStatus.BLOCKED
    assert result.primary_domain is None
    assert result.fallback_used is False
    assert any(r.code == "DOMAIN_UNAUTHORIZED_REJECTED" for r in result.reasons)


def test_university_signal_not_absorbed_when_denied():
    """University is policy-denied: its intent must not be converted via
    general."""
    policy = DomainResolutionPolicy(denied_domains=(UNIVERSITY,))
    result = _resolver().resolve(
        _context(
            available=(GENERAL, UNIVERSITY),
            authorized=(GENERAL,),
            policy=policy,
            objective="academic question",
            signals=(_university_signal(),),
        )
    )
    assert result.status is DomainResolutionStatus.BLOCKED
    assert result.primary_domain is None
    assert result.fallback_used is False
    assert UNIVERSITY in result.rejected_domains
    assert any(r.code == "DOMAIN_POLICY_DENIED" for r in result.reasons)


def test_university_signal_not_absorbed_when_disabled():
    """University is unavailable (not in the available set): General must not
    absorb."""
    result = _resolver().resolve(
        _context(
            available=(GENERAL,),
            authorized=(GENERAL,),
            objective="academic question",
            signals=(_university_signal(),),
        )
    )
    assert result.primary_domain is None
    assert result.fallback_used is False
    assert result.status is DomainResolutionStatus.BLOCKED
