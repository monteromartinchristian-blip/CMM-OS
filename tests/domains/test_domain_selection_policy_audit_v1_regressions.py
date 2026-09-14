"""Independent-audit V1 regression tests for Phase 10.31."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from cmm.domains.errors import DomainContractValidationError
from cmm.domains.identifiers import DomainId
from cmm.domains.resolution_contracts import (
    DomainResolutionContext,
    DomainResolutionPolicy,
    DomainResolutionSignal,
)
from cmm.domains.resolver import DefaultDomainResolver
from cmm.domains.resolver_contracts import DomainScoringPolicy
from cmm.domains.selection_contracts import (
    DomainSelectionPolicy,
    DomainSelectionTransition,
)

NOW = datetime(2026, 8, 28, 0, 15, tzinfo=timezone.utc)

GENERAL = DomainId.from_str("domain:general")
PROJECT = DomainId.from_str("domain:project")
LIFE_PLAN = DomainId.from_str("domain:life-plan")
REFLECTION = DomainId.from_str("domain:reflection")


def _signal(
    domain_id: DomainId,
    *,
    kind: str = "intent",
    confidence: float | None = 1.0,
    weight: float = 1.0,
) -> DomainResolutionSignal:
    return DomainResolutionSignal(
        kind=kind,
        source="phase10.31-audit-v1-regression",
        value=f"{kind}:{domain_id.slug}",
        domain_ids=(domain_id,),
        confidence=confidence,
        weight=weight,
        provenance={"source": "independent_audit_v1"},
    )


def _context(
    *,
    explicit_domains: tuple[DomainId, ...] = (),
    signals: tuple[DomainResolutionSignal, ...] = (),
    system_policy: DomainResolutionPolicy | None = None,
    available_domains: tuple[DomainId, ...] = (
        GENERAL,
        PROJECT,
        LIFE_PLAN,
        REFLECTION,
    ),
    authorized_domains: tuple[DomainId, ...] = (
        GENERAL,
        PROJECT,
        LIFE_PLAN,
        REFLECTION,
    ),
    context_id: str = "ctx-phase10.31-audit-v1",
) -> DomainResolutionContext:
    return DomainResolutionContext(
        id=context_id,
        user_input="Phase 10.31 independent-audit regression fixture",
        explicit_domains=explicit_domains,
        available_domains=available_domains,
        authorized_domains=authorized_domains,
        signals=signals,
        system_policy=system_policy,
        created_at=NOW,
    )


def _resolver(
    *,
    selection_policy: DomainSelectionPolicy | None = None,
    scoring_policy: DomainScoringPolicy | None = None,
    resolution_id: str = "resolution-phase10.31-audit-v1",
) -> DefaultDomainResolver:
    return DefaultDomainResolver(
        selection_policy=selection_policy,
        scoring_policy=scoring_policy,
        id_factory=lambda: resolution_id,
        clock=lambda: NOW,
    )


def _reason_codes(result) -> set[str]:
    return {reason.code for reason in result.reasons}


def test_audit_v1_explicit_denied_without_redundant_signal_blocks_fallback():
    """B1: an explicitly requested denied domain must block General fallback."""

    result = _resolver().resolve(
        _context(
            explicit_domains=(PROJECT,),
            signals=(),
            system_policy=DomainResolutionPolicy(
                denied_domains=(PROJECT,),
                require_authorization=False,
            ),
            available_domains=(GENERAL, PROJECT),
            authorized_domains=(),
            context_id="ctx-audit-v1-explicit-denied",
        )
    )

    assert result.status.value == "blocked"
    assert result.primary_domain is None
    assert result.fallback_used is False
    assert PROJECT in result.rejected_domains
    assert "DOMAIN_POLICY_DENIED" in _reason_codes(result)


def test_audit_v1_required_supporting_below_confidence_floor_fails_closed():
    """M1: required supporting domains must also satisfy selection confidence."""

    result = _resolver(
        selection_policy=DomainSelectionPolicy(
            minimum_supporting_confidence=0.55,
        ),
        scoring_policy=DomainScoringPolicy(
            intent_weight=1000.0,
            supporting_margin=1000.0,
            minimum_resolution_score=0.0,
        ),
        resolution_id="resolution-audit-v1-required-confidence",
    ).resolve(
        _context(
            explicit_domains=(PROJECT,),
            signals=(_signal(LIFE_PLAN, confidence=0.10),),
            system_policy=DomainResolutionPolicy(
                required_domains=(LIFE_PLAN,),
            ),
            available_domains=(GENERAL, PROJECT, LIFE_PLAN),
            authorized_domains=(GENERAL, PROJECT, LIFE_PLAN),
            context_id="ctx-audit-v1-required-confidence",
        )
    )

    assert result.status.value != "resolved"
    assert result.primary_domain is None
    assert result.supporting_domains == ()
    assert "DOMAIN_SELECTION_REQUIRED_SUPPORTING_CONFIDENCE_CONFLICT" in _reason_codes(
        result
    )


def test_audit_v1_disabled_goal_priority_cannot_cancel_enabled_session_priority():
    """M2: disabling goal priority removes goal from precedence arbitration."""

    result = _resolver(
        selection_policy=DomainSelectionPolicy(
            session_domain_priority=True,
            goal_domain_priority=False,
        ),
        scoring_policy=DomainScoringPolicy(
            session_weight=1.0,
            goal_weight=100.0,
            ambiguity_margin=0.0,
            minimum_resolution_score=0.0,
        ),
        resolution_id="resolution-audit-v1-session-enabled",
    ).resolve(
        _context(
            signals=(
                _signal(PROJECT, kind="session", weight=1.0),
                _signal(LIFE_PLAN, kind="goal", weight=20.0),
            ),
            context_id="ctx-audit-v1-session-enabled",
        )
    )

    assert result.status.value == "resolved"
    assert result.primary_domain == PROJECT


def test_audit_v1_disabled_session_and_goal_priorities_do_not_override_ordinary_evidence():
    """M2: shared session/goal evidence is not hard precedence when both flags are off."""

    result = _resolver(
        selection_policy=DomainSelectionPolicy(
            session_domain_priority=False,
            goal_domain_priority=False,
        ),
        scoring_policy=DomainScoringPolicy(
            intent_weight=100.0,
            session_weight=1.0,
            goal_weight=1.0,
            ambiguity_margin=0.0,
            minimum_resolution_score=0.0,
        ),
        resolution_id="resolution-audit-v1-structured-disabled",
    ).resolve(
        _context(
            signals=(
                _signal(PROJECT, kind="session", weight=1.0),
                _signal(PROJECT, kind="goal", weight=1.0),
                _signal(LIFE_PLAN, kind="intent", weight=20.0),
            ),
            context_id="ctx-audit-v1-structured-disabled",
        )
    )

    assert result.status.value == "resolved"
    assert result.primary_domain == LIFE_PLAN


def test_audit_v1_disabled_explicit_priority_allows_ordinary_score_resolution():
    """M2: explicit ambiguity is special only while explicit priority is enabled."""

    result = _resolver(
        selection_policy=DomainSelectionPolicy(
            explicit_domain_priority=False,
        ),
        scoring_policy=DomainScoringPolicy(
            intent_weight=100.0,
            ambiguity_margin=0.0,
            minimum_resolution_score=0.0,
        ),
        resolution_id="resolution-audit-v1-explicit-disabled",
    ).resolve(
        _context(
            explicit_domains=(PROJECT, LIFE_PLAN),
            signals=(_signal(LIFE_PLAN, kind="intent", weight=20.0),),
            available_domains=(PROJECT, LIFE_PLAN),
            authorized_domains=(PROJECT, LIFE_PLAN),
            context_id="ctx-audit-v1-explicit-disabled",
        )
    )

    assert result.status.value == "resolved"
    assert result.primary_domain == LIFE_PLAN
    assert result.requires_clarification is False


def test_audit_v1_inconsistent_transition_payload_is_rejected():
    """M3: serialized transitions may not contradict their own identities."""

    payload = {
        "previous_resolution_id": "resolution-before",
        "new_resolution_id": "resolution-after",
        "previous_primary_domain": str(PROJECT),
        "new_primary_domain": str(LIFE_PLAN),
        "previous_supporting_domains": [],
        "new_supporting_domains": [],
        "primary_changed": False,
        "supporting_changed": False,
        "reason_codes": [],
        "requires_recomposition": False,
        "requires_session_update": False,
        "metadata": {},
    }

    with pytest.raises(DomainContractValidationError):
        DomainSelectionTransition.from_dict(payload)


def test_audit_v1_explicit_priority_emits_selection_reason():
    """m1: explicit precedence must be visible in the resolution audit reasons."""

    result = _resolver(
        scoring_policy=DomainScoringPolicy(
            intent_weight=100.0,
            ambiguity_margin=0.0,
        ),
        resolution_id="resolution-audit-v1-explicit-reason",
    ).resolve(
        _context(
            explicit_domains=(PROJECT,),
            signals=(_signal(LIFE_PLAN, weight=20.0),),
            context_id="ctx-audit-v1-explicit-reason",
        )
    )

    assert result.primary_domain == PROJECT
    assert "DOMAIN_SELECTION_EXPLICIT_PRIORITY" in _reason_codes(result)


def test_audit_v1_session_priority_emits_selection_reason():
    """m1: session precedence must be visible in the resolution audit reasons."""

    result = _resolver(
        resolution_id="resolution-audit-v1-session-reason",
    ).resolve(
        _context(
            signals=(
                _signal(PROJECT, kind="session", weight=1.0),
                _signal(LIFE_PLAN, kind="intent", weight=20.0),
            ),
            context_id="ctx-audit-v1-session-reason",
        )
    )

    assert result.primary_domain == PROJECT
    assert "DOMAIN_SELECTION_SESSION_PRIORITY" in _reason_codes(result)


def test_audit_v1_goal_priority_emits_selection_reason():
    """m1: active-goal precedence must be visible in the resolution audit reasons."""

    result = _resolver(
        resolution_id="resolution-audit-v1-goal-reason",
    ).resolve(
        _context(
            signals=(
                _signal(REFLECTION, kind="goal", weight=1.0),
                _signal(LIFE_PLAN, kind="intent", weight=20.0),
            ),
            context_id="ctx-audit-v1-goal-reason",
        )
    )

    assert result.primary_domain == REFLECTION
    assert "DOMAIN_SELECTION_GOAL_PRIORITY" in _reason_codes(result)


def test_audit_v1_supporting_confidence_rejection_emits_selection_reason():
    """m1: optional supporting rejection by confidence must be auditable."""

    result = _resolver(
        selection_policy=DomainSelectionPolicy(
            minimum_supporting_confidence=0.55,
        ),
        scoring_policy=DomainScoringPolicy(
            intent_weight=1000.0,
            supporting_margin=1000.0,
            max_supporting_domains=3,
        ),
        resolution_id="resolution-audit-v1-support-confidence-reason",
    ).resolve(
        _context(
            explicit_domains=(PROJECT,),
            signals=(_signal(LIFE_PLAN, confidence=0.54),),
            available_domains=(GENERAL, PROJECT, LIFE_PLAN),
            authorized_domains=(GENERAL, PROJECT, LIFE_PLAN),
            context_id="ctx-audit-v1-support-confidence-reason",
        )
    )

    assert result.primary_domain == PROJECT
    assert LIFE_PLAN not in result.supporting_domains
    assert "DOMAIN_SELECTION_SUPPORTING_CONFIDENCE_REJECTED" in _reason_codes(result)


def test_audit_v1_multi_domain_disabled_emits_selection_reason():
    """m1: disabling multi-domain composition must be visible in audit reasons."""

    result = _resolver(
        selection_policy=DomainSelectionPolicy(
            allow_multi_domain=False,
        ),
        scoring_policy=DomainScoringPolicy(
            intent_weight=1000.0,
            supporting_margin=1000.0,
        ),
        resolution_id="resolution-audit-v1-multi-disabled-reason",
    ).resolve(
        _context(
            explicit_domains=(PROJECT,),
            signals=(_signal(LIFE_PLAN, confidence=1.0),),
            available_domains=(GENERAL, PROJECT, LIFE_PLAN),
            authorized_domains=(GENERAL, PROJECT, LIFE_PLAN),
            context_id="ctx-audit-v1-multi-disabled-reason",
        )
    )

    assert result.primary_domain == PROJECT
    assert result.supporting_domains == ()
    assert "DOMAIN_SELECTION_MULTI_DOMAIN_DISABLED" in _reason_codes(result)
