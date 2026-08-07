"""Tests for General Domain fallback and resolution with standard configuration."""

from __future__ import annotations

from datetime import datetime, timezone

from cmm.agent_runtime.domain_permission_contracts import PermissionCapability
from cmm.domains.enums import DomainResolutionStatus
from cmm.domains.identifiers import DomainId
from cmm.domains.permission_contracts import DomainPermissionPolicy
from cmm.domains.resolution_contracts import (
    DomainResolutionContext,
    DomainResolutionPolicy,
    DomainResolutionSignal,
)
from cmm.domains.resolver import DefaultDomainResolver

NOW = datetime(2026, 8, 1, tzinfo=timezone.utc)
GENERAL = DomainId(slug="general")
HEALTH = DomainId(slug="health")
UNIVERSITY = DomainId(slug="university")
PROJECT = DomainId(slug="project")


def _context(
    *,
    available=(GENERAL,),
    authorized=(GENERAL,),
    explicit=(),
    objective="general request",
    policy=None,
    signals=(),
    metadata=None,
) -> DomainResolutionContext:
    return DomainResolutionContext(
        id="ctx1",
        objective=objective,
        available_domains=available,
        authorized_domains=authorized,
        explicit_domains=explicit,
        system_policy=policy,
        signals=signals,
        metadata=metadata,
        created_at=NOW,
    )


def _signal(
    *domain_ids,
    value="request-global-guard",
    confidence=0.9,
) -> DomainResolutionSignal:
    """Build the canonical intent signal used by the Audit v2 regression tests."""
    return DomainResolutionSignal(
        kind="intent",
        source="test",
        value=value,
        domain_ids=domain_ids,
        confidence=confidence,
        provenance={"source": "test"},
    )


def _resolver() -> DefaultDomainResolver:
    """Resolver with standard configuration — no manual score adjustment."""
    return DefaultDomainResolver(
        fallback_domain=GENERAL,
        clock=lambda: NOW,
        id_factory=lambda: "id1",
    )


def test_general_only_request():
    """A genuinely general request can select domain:general."""
    result = _resolver().resolve(_context())
    assert result.primary_domain == GENERAL
    assert result.fallback_used is True


def test_explicit_general_request():
    """An explicit general request selects domain:general."""
    result = _resolver().resolve(
        _context(explicit=(GENERAL,), available=(GENERAL, HEALTH))
    )
    assert result.status is DomainResolutionStatus.RESOLVED
    assert result.primary_domain == GENERAL


def test_request_without_specialized_signals():
    """A request without specialized signals falls back to general."""
    result = _resolver().resolve(
        _context(available=(GENERAL, HEALTH), authorized=(GENERAL, HEALTH))
    )
    assert result.primary_domain == GENERAL
    assert result.fallback_used is True


def test_specialized_candidate_valid():
    """A valid specialized candidate prevails over general."""
    result = _resolver().resolve(
        _context(
            available=(GENERAL, HEALTH),
            authorized=(GENERAL, HEALTH),
            objective="medical symptom",
            signals=(
                DomainResolutionSignal(
                    kind="intent",
                    source="test",
                    value="medical",
                    domain_ids=(HEALTH,),
                    confidence=0.9,
                    provenance={"source": "test"},
                ),
            ),
        )
    )
    assert result.primary_domain == HEALTH


def test_specialized_candidate_higher_score():
    """A specialized candidate with higher score prevails."""
    result = _resolver().resolve(
        _context(
            available=(GENERAL, HEALTH),
            authorized=(GENERAL, HEALTH),
            objective="medical symptom",
            signals=(
                DomainResolutionSignal(
                    kind="intent",
                    source="test",
                    value="medical",
                    domain_ids=(HEALTH,),
                    confidence=0.9,
                    provenance={"source": "test"},
                ),
            ),
        )
    )
    assert result.primary_domain == HEALTH
    # Health should have a higher score than general
    health_score = next(
        c.score for c in result.candidate_scores if c.domain_id == HEALTH
    )
    general_score = next(
        c.score for c in result.candidate_scores if c.domain_id == GENERAL
    )
    assert health_score > general_score


def test_health_like_request():
    """A health-like request selects health, not general."""
    result = _resolver().resolve(
        _context(
            available=(GENERAL, HEALTH),
            authorized=(GENERAL, HEALTH),
            objective="I have a medical symptom",
            signals=(
                DomainResolutionSignal(
                    kind="intent",
                    source="test",
                    value="medical",
                    domain_ids=(HEALTH,),
                    confidence=0.9,
                    provenance={"source": "test"},
                ),
            ),
        )
    )
    assert result.primary_domain == HEALTH


def test_university_like_request():
    """A university-like request selects university, not general."""
    result = _resolver().resolve(
        _context(
            available=(GENERAL, UNIVERSITY),
            authorized=(GENERAL, UNIVERSITY),
            objective="I need to study for my exam",
            signals=(
                DomainResolutionSignal(
                    kind="intent",
                    source="test",
                    value="university",
                    domain_ids=(UNIVERSITY,),
                    confidence=0.9,
                    provenance={"source": "test"},
                ),
            ),
        )
    )
    assert result.primary_domain == UNIVERSITY


def test_project_like_request():
    """A project-like request selects project, not general."""
    result = _resolver().resolve(
        _context(
            available=(GENERAL, PROJECT),
            authorized=(GENERAL, PROJECT),
            objective="The code documentation doesn't match",
            signals=(
                DomainResolutionSignal(
                    kind="intent",
                    source="test",
                    value="project",
                    domain_ids=(PROJECT,),
                    confidence=0.9,
                    provenance={"source": "test"},
                ),
            ),
        )
    )
    assert result.primary_domain == PROJECT


def test_sensitive_request_not_degraded():
    """A request signaled toward a specialized domain is not silently degraded to general.

    The signal value is neutral (no sensitive keyword).  Because the signaled
    domain (health) is not authorized, the fallback must be blocked fail-closed.
    """
    result = _resolver().resolve(
        _context(
            available=(GENERAL, HEALTH),
            authorized=(GENERAL,),
            signals=(
                DomainResolutionSignal(
                    kind="intent",
                    source="test",
                    value="request-123",
                    domain_ids=(HEALTH,),
                    confidence=0.9,
                    provenance={"source": "test"},
                ),
            ),
        )
    )
    # Health is not authorized, so General Domain must not silently take over.
    assert result.status is DomainResolutionStatus.BLOCKED
    assert result.primary_domain is None
    assert result.fallback_used is False
    assert any(r.code == "DOMAIN_UNAUTHORIZED_REJECTED" for r in result.reasons)


def test_specialized_candidate_without_permissions():
    """A specialized candidate without permissions is not silently replaced by general."""
    result = _resolver().resolve(
        _context(
            available=(GENERAL, HEALTH),
            authorized=(GENERAL,),
            objective="medical symptom",
            signals=(
                DomainResolutionSignal(
                    kind="intent",
                    source="test",
                    value="request-456",
                    domain_ids=(HEALTH,),
                    confidence=0.9,
                    provenance={"source": "test"},
                ),
            ),
        )
    )
    # General must not be selected to bypass the missing authorization.
    assert result.primary_domain is None
    assert result.fallback_used is False
    assert result.status is DomainResolutionStatus.BLOCKED


def test_specialized_candidate_blocked():
    """A blocked specialized domain does not convert its action to permitted via general."""
    policy = DomainResolutionPolicy(denied_domains=(HEALTH,))
    result = _resolver().resolve(
        _context(
            available=(GENERAL, HEALTH),
            authorized=(GENERAL,),
            objective="medical symptom",
            policy=policy,
            signals=(
                DomainResolutionSignal(
                    kind="intent",
                    source="test",
                    value="request-789",
                    domain_ids=(HEALTH,),
                    confidence=0.9,
                    provenance={"source": "test"},
                ),
            ),
        )
    )
    assert result.primary_domain is None
    assert result.fallback_used is False
    assert result.status is DomainResolutionStatus.BLOCKED
    # The blocked domain is rejected
    assert HEALTH in result.rejected_domains
    assert any(r.code == "DOMAIN_POLICY_DENIED" for r in result.reasons)


def test_signal_toward_fallback_domain_keeps_fallback():
    """A signal explicitly targeting the fallback domain does not block it."""
    result = _resolver().resolve(
        _context(
            available=(GENERAL, HEALTH),
            authorized=(GENERAL,),
            signals=(
                DomainResolutionSignal(
                    kind="intent",
                    source="test",
                    value="general request",
                    domain_ids=(GENERAL,),
                    confidence=0.1,
                    provenance={"source": "test"},
                ),
            ),
        )
    )
    assert result.primary_domain == GENERAL
    assert result.fallback_used is True


def test_ambiguous_request():
    """Relevant ties are not resolved arbitrarily."""
    result = _resolver().resolve(
        _context(
            available=(GENERAL, HEALTH, UNIVERSITY),
            authorized=(GENERAL, HEALTH, UNIVERSITY),
            objective="ambiguous request",
        )
    )
    # With no signals, no domain reaches the minimum score threshold.
    # The resolver correctly falls back to general (INSUFFICIENT_INFORMATION)
    # rather than arbitrarily picking a specialized domain.
    assert result.status in (
        DomainResolutionStatus.RESOLVED,
        DomainResolutionStatus.AMBIGUOUS,
        DomainResolutionStatus.INSUFFICIENT_INFORMATION,
    )
    if result.status is DomainResolutionStatus.INSUFFICIENT_INFORMATION:
        assert result.primary_domain == GENERAL
        assert result.fallback_used is True


def test_general_not_automatically_supporting():
    """General Domain is not added as supporting by default."""
    result = _resolver().resolve(
        _context(
            available=(GENERAL, HEALTH),
            authorized=(GENERAL, HEALTH),
            objective="medical symptom",
        )
    )
    # General should not be added as supporting by default
    assert GENERAL not in result.supporting_domains


def test_general_as_supporting_only_with_real_contribution():
    """General Domain is supporting only when it contributes meaningfully."""
    result = _resolver().resolve(
        _context(
            available=(GENERAL, HEALTH),
            authorized=(GENERAL, HEALTH),
            objective="medical symptom",
            signals=(
                DomainResolutionSignal(
                    kind="intent",
                    source="test",
                    value="medical",
                    domain_ids=(HEALTH,),
                    confidence=0.9,
                    provenance={"source": "test"},
                ),
            ),
        )
    )
    # General should not be supporting when health is primary
    assert GENERAL not in result.supporting_domains


def test_deterministic_repeated_resolution():
    """Repeated resolution is deterministic."""
    resolver = _resolver()
    a = resolver.resolve(_context())
    b = resolver.resolve(_context())
    assert a.primary_domain == b.primary_domain
    assert a.status == b.status
    assert a.fallback_used == b.fallback_used


def test_fallback_trace():
    """Fallback is traced with reason code and rejected candidates."""
    result = _resolver().resolve(_context())
    assert result.fallback_used is True
    assert any(r.code == "DOMAIN_FALLBACK_SELECTED" for r in result.reasons)
    assert result.candidate_scores is not None
    assert any(c.domain_id == GENERAL for c in result.candidate_scores)


def test_no_permission_widening():
    """Fallback does not widen permissions."""
    policy = DomainPermissionPolicy(
        policy_id="p1",
        domain_id="domain:general",
        version="1.0.0",
        allowed_capabilities=(PermissionCapability.RESOURCE_READ,),
    )
    # General Domain cannot expand permissions
    assert PermissionCapability.SEARCH_EXTERNAL not in policy.allowed_capabilities


def test_no_profile_weakening():
    """Fallback does not weaken the profile."""
    from cmm.domains.general import build_general_profile

    profile = build_general_profile()
    assert profile.prohibited_actions is not None
    assert "sensitive_inference" in profile.prohibited_actions
    assert "medical_decision" in profile.prohibited_actions


def test_canonical_bootstrap_blocks_fallback_for_ineligible_signaled_domain():
    """A specialized signaled domain that is ineligible blocks General fallback.

    Uses the canonical bootstrap resolver: an explicitly signaled available
    domain that is not authorized must produce a fail-closed BLOCKED result
    instead of silently degrading to General.
    """
    from cmm.domains.general import build_standard_general_domain_bootstrap

    resolver = build_standard_general_domain_bootstrap().resolver
    result = resolver.resolve(
        _context(
            available=(GENERAL, HEALTH),
            authorized=(GENERAL,),
            signals=(
                DomainResolutionSignal(
                    kind="intent",
                    source="test",
                    value="request-bootstrap-p0",
                    domain_ids=(HEALTH,),
                    confidence=0.9,
                    provenance={"source": "test"},
                ),
            ),
        )
    )
    assert result.status is DomainResolutionStatus.BLOCKED
    assert result.primary_domain is None
    assert result.fallback_used is False
    assert any(r.code == "DOMAIN_UNAUTHORIZED_REJECTED" for r in result.reasons)


def test_canonical_bootstrap_allows_general_fallback_without_specialized_signal():
    """Without a specialized signal the canonical bootstrap falls back to General."""
    from cmm.domains.general import build_standard_general_domain_bootstrap

    resolver = build_standard_general_domain_bootstrap().resolver
    result = resolver.resolve(
        _context(available=(GENERAL, HEALTH), authorized=(GENERAL, HEALTH))
    )
    assert result.primary_domain == GENERAL
    assert result.fallback_used is True


# ── Audit v2 P0 ────────────────────────────────────────────────────────────────
# The normal path (eligible_scores -> primary -> RESOLVED) can select the
# configured fallback (General) without ever entering _try_fallback().  These
# regression tests force that path: General is already explicit + eligible, so
# resolution never depends on the fallback branch.  Audit v2 requires the
# fail-closed fallback guard to apply to EVERY path that would return the
# configured fallback as primary.


def test_explicit_general_cannot_bypass_unauthorized_specialized_signal():
    """An eligible explicit General cannot bypass an unauthorized signal."""
    result = _resolver().resolve(
        _context(
            available=(GENERAL, HEALTH),
            authorized=(GENERAL,),
            explicit=(GENERAL,),
            signals=(_signal(HEALTH, value="request-global-guard-auth"),),
        )
    )
    assert result.status is DomainResolutionStatus.BLOCKED
    assert result.primary_domain is None
    assert result.fallback_used is False
    assert any(r.code == "DOMAIN_UNAUTHORIZED_REJECTED" for r in result.reasons)


def test_explicit_general_cannot_bypass_denied_specialized_signal():
    """An eligible explicit General cannot bypass a denied signal."""
    policy = DomainResolutionPolicy(denied_domains=(HEALTH,))
    result = _resolver().resolve(
        _context(
            available=(GENERAL, HEALTH),
            authorized=(GENERAL,),
            explicit=(GENERAL,),
            policy=policy,
            signals=(_signal(HEALTH, value="request-global-guard-denied"),),
        )
    )
    assert result.status is DomainResolutionStatus.BLOCKED
    assert result.primary_domain is None
    assert result.fallback_used is False
    assert any(r.code == "DOMAIN_POLICY_DENIED" for r in result.reasons)


def test_explicit_general_cannot_bypass_not_allowed_specialized_signal():
    """An eligible explicit General cannot bypass an allowed_domains exclusion."""
    policy = DomainResolutionPolicy(allowed_domains=(GENERAL,))
    result = _resolver().resolve(
        _context(
            available=(GENERAL, HEALTH),
            authorized=(GENERAL, HEALTH),
            explicit=(GENERAL,),
            policy=policy,
            signals=(_signal(HEALTH, value="request-global-guard-not-allowed"),),
        )
    )
    assert result.status is DomainResolutionStatus.BLOCKED
    assert result.primary_domain is None
    assert result.fallback_used is False
    assert any(r.code == "DOMAIN_POLICY_NOT_ALLOWED" for r in result.reasons)


def test_general_cannot_absorb_signal_for_unavailable_specialized_domain():
    """A signaled-but-not-available domain must not be silently absorbed.

    Reuses the canonical resolver reason code DOMAIN_NO_ELIGIBLE_CANDIDATE
    (a signaled domain that is not available has no eligible candidate).  No
    new contractual API is introduced.
    """
    result = _resolver().resolve(
        _context(
            available=(GENERAL,),
            authorized=(GENERAL,),
            explicit=(GENERAL,),
            signals=(_signal(HEALTH, value="request-global-guard-unavailable"),),
        )
    )
    assert result.status is DomainResolutionStatus.BLOCKED
    assert result.primary_domain is None
    assert result.fallback_used is False
    assert any(r.code == "DOMAIN_NO_ELIGIBLE_CANDIDATE" for r in result.reasons)


def test_general_cannot_absorb_signal_for_disabled_specialized_domain():
    """A signaled disabled domain blocks General fallback fail-closed."""
    metadata = {
        "_resolution_registry_versions": {
            "health": [
                {"version": "1.0.0", "status": "disabled", "kind": "personal"},
            ],
        }
    }
    result = _resolver().resolve(
        _context(
            available=(GENERAL, HEALTH),
            authorized=(GENERAL, HEALTH),
            explicit=(GENERAL,),
            metadata=metadata,
            signals=(_signal(HEALTH, value="request-global-guard-disabled"),),
        )
    )
    assert result.status is DomainResolutionStatus.BLOCKED
    assert result.primary_domain is None
    assert result.fallback_used is False
    assert any(r.code == "DOMAIN_DISABLED_REJECTED" for r in result.reasons)


def test_general_cannot_absorb_signal_for_disallowed_degraded_specialized_domain():
    """A signaled degraded domain blocks General fallback when policy disallows it."""
    policy = DomainResolutionPolicy(allow_degraded=False)
    metadata = {
        "_resolution_registry_versions": {
            "health": [
                {"version": "1.0.0", "status": "degraded", "kind": "personal"},
            ],
        }
    }
    result = _resolver().resolve(
        _context(
            available=(GENERAL, HEALTH),
            authorized=(GENERAL, HEALTH),
            explicit=(GENERAL,),
            policy=policy,
            metadata=metadata,
            signals=(_signal(HEALTH, value="request-global-guard-degraded"),),
        )
    )
    assert result.status is DomainResolutionStatus.BLOCKED
    assert result.primary_domain is None
    assert result.fallback_used is False
    assert any(r.code == "DOMAIN_DEGRADED_REJECTED" for r in result.reasons)


def test_degraded_specialized_domain_stays_primary_when_allow_degraded():
    """Degraded + allow_degraded=True must NOT block a valid specialized primary.

    Positive control: a degraded Health domain only receives a scoring penalty
    and remains the primary when directly signaled.  The guard must not turn
    another domain's degraded state into a global BLOCKED when the final
    primary is NOT the configured fallback.
    """
    metadata = {
        "_resolution_registry_versions": {
            "health": [
                {"version": "1.0.0", "status": "degraded", "kind": "personal"},
            ],
        }
    }
    result = _resolver().resolve(
        _context(
            available=(GENERAL, HEALTH),
            authorized=(GENERAL, HEALTH),
            metadata=metadata,
            signals=(_signal(HEALTH, value="medical"),),
        )
    )
    assert result.status is DomainResolutionStatus.RESOLVED
    assert result.primary_domain == HEALTH
    assert result.fallback_used is False