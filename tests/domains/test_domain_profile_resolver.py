"""Tests for Phase 10.11 – Domain Profile Resolver (Tasks 9, 10)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import runtime_checkable

import pytest

from cmm.domains.enums import DomainProfileResolutionStatus, DomainProfileSource
from cmm.domains.errors import DomainProfileResolutionError
from cmm.domains.identifiers import DomainId
from cmm.domains.profile_composition import DefaultDomainProfileComposer
from cmm.domains.profile_contracts import (
    DomainProfileDefinition,
    DomainProfileOverlay,
    DomainProfileResolutionRequest,
)
from cmm.domains.profile_resolver import (
    DefaultDomainProfileResolver,
    DomainProfileResolver,
    _is_overlay_mandatory,
)


def _global(**overrides) -> DomainProfileDefinition:
    defaults = {
        "id": "global-1",
        "domain_id": DomainId("general"),
        "profile_name": "GeneralProfile",
    }
    defaults.update(overrides)
    return DomainProfileDefinition(**defaults)


def _primary(**overrides) -> DomainProfileDefinition:
    defaults = {
        "id": "primary-1",
        "domain_id": DomainId("health"),
        "profile_name": "HealthProfile",
    }
    defaults.update(overrides)
    return DomainProfileDefinition(**defaults)


def _supporting(**overrides) -> DomainProfileDefinition:
    defaults = {
        "id": "supporting-1",
        "domain_id": DomainId("relationship"),
        "profile_name": "RelationshipProfile",
    }
    defaults.update(overrides)
    return DomainProfileDefinition(**defaults)


def _request(**overrides) -> DomainProfileResolutionRequest:
    defaults = {
        "id": "req-1",
        "primary_domain": DomainId("health"),
    }
    defaults.update(overrides)
    return DomainProfileResolutionRequest(**defaults)


def _overlay(**overrides) -> DomainProfileOverlay:
    defaults = {
        "id": "overlay-1",
        "source": DomainProfileSource.GLOBAL_POLICY,
    }
    defaults.update(overrides)
    return DomainProfileOverlay(**defaults)


# ═══════════════════════════════════════════════════════════════════════════════
# Protocol
# ═══════════════════════════════════════════════════════════════════════════════


def test_domain_profile_resolver_is_runtime_checkable_protocol():
    assert runtime_checkable(DomainProfileResolver) is DomainProfileResolver
    resolver = DefaultDomainProfileResolver()
    assert isinstance(resolver, DomainProfileResolver)


# ═══════════════════════════════════════════════════════════════════════════════
# Constructor validation
# ═══════════════════════════════════════════════════════════════════════════════


def test_constructor_rejects_non_composer():
    with pytest.raises(DomainProfileResolutionError):
        DefaultDomainProfileResolver(composer=object())


def test_constructor_rejects_uncallable_clock():
    with pytest.raises(DomainProfileResolutionError):
        DefaultDomainProfileResolver(clock="not-callable")


def test_constructor_rejects_uncallable_id_factory():
    with pytest.raises(DomainProfileResolutionError):
        DefaultDomainProfileResolver(id_factory="not-callable")


def test_constructor_rejects_uncallable_profile_id_factory():
    with pytest.raises(DomainProfileResolutionError):
        DefaultDomainProfileResolver(profile_id_factory="not-callable")


def test_constructor_rejects_uncallable_trace_id_factory():
    with pytest.raises(DomainProfileResolutionError):
        DefaultDomainProfileResolver(trace_id_factory="not-callable")


def test_constructor_accepts_explicit_composer():
    resolver = DefaultDomainProfileResolver(composer=DefaultDomainProfileComposer())
    result = resolver.resolve(
        request=_request(),
        global_profile=_global(),
        primary_profile=_primary(),
    )
    assert result.status == DomainProfileResolutionStatus.RESOLVED


def test_global_profile_applied_first():
    result = DefaultDomainProfileResolver().resolve(
        request=_request(), global_profile=_global(), primary_profile=_primary()
    )
    assert result.decisions[0].source == DomainProfileSource.GLOBAL_POLICY


def test_primary_profile_cannot_be_reused_as_global_silently():
    resolver = DefaultDomainProfileResolver()
    primary = _primary()
    with pytest.raises(DomainProfileResolutionError, match="global_profile"):
        resolver.resolve(
            request=_request(), global_profile=primary, primary_profile=primary
        )


# ═══════════════════════════════════════════════════════════════════════════════
# Profile-domain alignment and supporting-profile order
# ═══════════════════════════════════════════════════════════════════════════════


def test_resolve_rejects_primary_profile_domain_mismatch():
    resolver = DefaultDomainProfileResolver()
    with pytest.raises(DomainProfileResolutionError):
        resolver.resolve(
            request=_request(primary_domain=DomainId("health")),
            global_profile=_global(),
            primary_profile=_primary(domain_id=DomainId("university")),
        )


def test_resolve_rejects_supporting_profiles_order_mismatch():
    resolver = DefaultDomainProfileResolver()
    with pytest.raises(DomainProfileResolutionError):
        resolver.resolve(
            request=_request(supporting_domains=(DomainId("relationship"),)),
            global_profile=_global(),
            primary_profile=_primary(),
            supporting_profiles=(_supporting(domain_id=DomainId("nil")),),
        )


def test_resolve_accepts_matching_supporting_profiles_order():
    resolver = DefaultDomainProfileResolver()
    result = resolver.resolve(
        request=_request(supporting_domains=(DomainId("relationship"),)),
        global_profile=_global(),
        primary_profile=_primary(),
        supporting_profiles=(_supporting(),),
    )
    assert result.status == DomainProfileResolutionStatus.RESOLVED
    assert result.profile.supporting_domains == (DomainId("relationship"),)


# ═══════════════════════════════════════════════════════════════════════════════
# Factory outputs and aware clock
# ═══════════════════════════════════════════════════════════════════════════════


def test_resolve_uses_injected_clock_and_factories():
    fixed_time = datetime(2026, 1, 1, tzinfo=timezone.utc)
    resolver = DefaultDomainProfileResolver(
        clock=lambda: fixed_time,
        id_factory=lambda: "fixed-id",
        profile_id_factory=lambda: "fixed-profile-id",
        trace_id_factory=lambda: "fixed-trace-id",
    )
    result = resolver.resolve(
        request=_request(),
        global_profile=_global(),
        primary_profile=_primary(),
    )
    assert result.id == "fixed-id"
    assert result.trace_id == "fixed-trace-id"
    assert result.resolved_at == fixed_time
    assert result.profile.id == "fixed-profile-id"
    assert result.profile.trace_id == "fixed-trace-id"
    assert result.profile.resolved_at == fixed_time


def test_resolve_rejects_naive_clock_output():
    resolver = DefaultDomainProfileResolver(
        clock=lambda: datetime.fromisoformat("2026-01-01T00:00:00")
    )
    with pytest.raises(DomainProfileResolutionError):
        resolver.resolve(
            request=_request(), global_profile=_global(), primary_profile=_primary()
        )


def test_resolve_rejects_empty_id_factory_output():
    resolver = DefaultDomainProfileResolver(id_factory=lambda: "")
    with pytest.raises(DomainProfileResolutionError):
        resolver.resolve(
            request=_request(), global_profile=_global(), primary_profile=_primary()
        )


def test_resolve_propagates_factory_exceptions():
    def _failing_factory() -> str:
        raise RuntimeError("boom")

    resolver = DefaultDomainProfileResolver(trace_id_factory=_failing_factory)
    with pytest.raises(RuntimeError):
        resolver.resolve(
            request=_request(), global_profile=_global(), primary_profile=_primary()
        )


# ═══════════════════════════════════════════════════════════════════════════════
# Composer invocation and status derivation
# ═══════════════════════════════════════════════════════════════════════════════


def test_resolve_returns_resolved_when_no_conflicts_or_rejections():
    resolver = DefaultDomainProfileResolver()
    result = resolver.resolve(
        request=_request(), global_profile=_global(), primary_profile=_primary()
    )
    assert result.status == DomainProfileResolutionStatus.RESOLVED
    assert result.profile is not None
    assert result.conflicts == ()
    assert result.rejections == ()


def test_resolve_invokes_composer_with_relevant_overlays_only():
    resolver = DefaultDomainProfileResolver()
    relevant = _overlay(
        id="ov-relevant",
        source=DomainProfileSource.WORKFLOW,
        source_id="wf-1",
        prohibited_actions=("act1",),
    )
    result = resolver.resolve(
        request=_request(workflow_ids=("wf-1",)),
        global_profile=_global(),
        primary_profile=_primary(),
        overlays=(relevant,),
    )
    assert result.status == DomainProfileResolutionStatus.RESOLVED
    assert result.profile.prohibited_actions == ("act1",)


# ═══════════════════════════════════════════════════════════════════════════════
# Overlay relevance validation, per source
# ═══════════════════════════════════════════════════════════════════════════════


def test_global_policy_overlay_is_always_relevant():
    resolver = DefaultDomainProfileResolver()
    overlay = _overlay(
        source=DomainProfileSource.GLOBAL_POLICY, prohibited_actions=("g1",)
    )
    result = resolver.resolve(
        request=_request(),
        global_profile=_global(),
        primary_profile=_primary(),
        overlays=(overlay,),
    )
    assert result.profile.prohibited_actions == ("g1",)


def test_primary_domain_overlay_relevant_when_source_id_matches():
    resolver = DefaultDomainProfileResolver()
    overlay = _overlay(
        source=DomainProfileSource.PRIMARY_DOMAIN,
        source_id="health",
        prohibited_actions=("p1",),
    )
    result = resolver.resolve(
        request=_request(),
        global_profile=_global(),
        primary_profile=_primary(),
        overlays=(overlay,),
    )
    assert result.profile.prohibited_actions == ("p1",)


def test_primary_domain_overlay_irrelevant_when_source_id_mismatches_blocks():
    resolver = DefaultDomainProfileResolver()
    overlay = _overlay(
        source=DomainProfileSource.PRIMARY_DOMAIN,
        source_id="university",
        prohibited_actions=("p1",),
    )
    result = resolver.resolve(
        request=_request(),
        global_profile=_global(),
        primary_profile=_primary(),
        overlays=(overlay,),
    )
    assert result.status == DomainProfileResolutionStatus.BLOCKED
    assert result.profile is None
    assert result.rejections == ()


def test_supporting_domain_overlay_relevant_when_referring_supporting_domain():
    resolver = DefaultDomainProfileResolver()
    overlay = _overlay(
        source=DomainProfileSource.SUPPORTING_DOMAIN,
        source_id="relationship",
        prohibited_actions=("s1",),
    )
    result = resolver.resolve(
        request=_request(supporting_domains=(DomainId("relationship"),)),
        global_profile=_global(),
        primary_profile=_primary(),
        supporting_profiles=(_supporting(),),
        overlays=(overlay,),
    )
    assert result.profile.prohibited_actions == ("s1",)


def test_workflow_overlay_relevant_only_when_source_id_in_workflow_ids():
    resolver = DefaultDomainProfileResolver()
    relevant = _overlay(
        id="ov-a", source=DomainProfileSource.WORKFLOW, source_id="wf-1"
    )
    irrelevant = _overlay(
        id="ov-b", source=DomainProfileSource.WORKFLOW, source_id="wf-2"
    )
    result = resolver.resolve(
        request=_request(workflow_ids=("wf-1",)),
        global_profile=_global(),
        primary_profile=_primary(),
        overlays=(relevant, irrelevant),
    )
    assert result.status == DomainProfileResolutionStatus.PARTIAL
    assert len(result.rejections) == 1
    assert result.rejections[0].source_id == "wf-2"


def test_operation_overlay_relevant_only_when_source_id_in_operation_ids():
    resolver = DefaultDomainProfileResolver()
    overlay = _overlay(source=DomainProfileSource.OPERATION, source_id="op-1")
    result = resolver.resolve(
        request=_request(operation_ids=("op-1",)),
        global_profile=_global(),
        primary_profile=_primary(),
        overlays=(overlay,),
    )
    assert result.status == DomainProfileResolutionStatus.RESOLVED


def test_risk_overlay_relevant_only_when_source_id_matches_risk_level():
    resolver = DefaultDomainProfileResolver()
    overlay = _overlay(source=DomainProfileSource.RISK, source_id="high")
    result = resolver.resolve(
        request=_request(risk_level="high"),
        global_profile=_global(),
        primary_profile=_primary(),
        overlays=(overlay,),
    )
    assert result.status == DomainProfileResolutionStatus.RESOLVED


def test_risk_overlay_irrelevant_when_risk_level_mismatches():
    resolver = DefaultDomainProfileResolver()
    overlay = _overlay(source=DomainProfileSource.RISK, source_id="high")
    result = resolver.resolve(
        request=_request(risk_level="low"),
        global_profile=_global(),
        primary_profile=_primary(),
        overlays=(overlay,),
    )
    assert result.status == DomainProfileResolutionStatus.PARTIAL


def test_autonomy_overlay_relevant_only_when_source_id_matches_autonomy_level():
    resolver = DefaultDomainProfileResolver()
    overlay = _overlay(source=DomainProfileSource.AUTONOMY, source_id="supervised")
    result = resolver.resolve(
        request=_request(autonomy_level="supervised"),
        global_profile=_global(),
        primary_profile=_primary(),
        overlays=(overlay,),
    )
    assert result.status == DomainProfileResolutionStatus.RESOLVED


def test_explicit_request_overlay_relevant_when_source_id_matches_request_id():
    resolver = DefaultDomainProfileResolver()
    overlay = _overlay(source=DomainProfileSource.EXPLICIT_REQUEST, source_id="req-1")
    result = resolver.resolve(
        request=_request(id="req-1"),
        global_profile=_global(),
        primary_profile=_primary(),
        overlays=(overlay,),
    )
    assert result.status == DomainProfileResolutionStatus.RESOLVED


def test_actor_overlay_relevant_when_source_id_matches_actor_id():
    resolver = DefaultDomainProfileResolver()
    overlay = _overlay(source=DomainProfileSource.ACTOR, source_id="actor-1")
    result = resolver.resolve(
        request=_request(actor_context={"actor_id": "actor-1"}),
        global_profile=_global(),
        primary_profile=_primary(),
        overlays=(overlay,),
    )
    assert result.status == DomainProfileResolutionStatus.RESOLVED


def test_actor_overlay_relevant_when_source_id_in_actor_ids():
    resolver = DefaultDomainProfileResolver()
    overlay = _overlay(source=DomainProfileSource.ACTOR, source_id="actor-2")
    result = resolver.resolve(
        request=_request(actor_context={"actor_ids": ["actor-1", "actor-2"]}),
        global_profile=_global(),
        primary_profile=_primary(),
        overlays=(overlay,),
    )
    assert result.status == DomainProfileResolutionStatus.RESOLVED


def test_actor_overlay_irrelevant_when_actor_context_missing():
    resolver = DefaultDomainProfileResolver()
    overlay = _overlay(source=DomainProfileSource.ACTOR, source_id="actor-1")
    result = resolver.resolve(
        request=_request(),
        global_profile=_global(),
        primary_profile=_primary(),
        overlays=(overlay,),
    )
    assert result.status == DomainProfileResolutionStatus.PARTIAL


def test_actor_overlay_irrelevant_when_source_id_mismatches():
    resolver = DefaultDomainProfileResolver()
    overlay = _overlay(source=DomainProfileSource.ACTOR, source_id="actor-2")
    result = resolver.resolve(
        request=_request(actor_context={"actor_id": "actor-1"}),
        global_profile=_global(),
        primary_profile=_primary(),
        overlays=(overlay,),
    )
    assert result.status == DomainProfileResolutionStatus.PARTIAL


# ═══════════════════════════════════════════════════════════════════════════════
# Irrelevant optional overlays -> PARTIAL; irrelevant mandatory/global -> BLOCKED
# ═══════════════════════════════════════════════════════════════════════════════


def test_irrelevant_optional_overlay_yields_partial_with_rejection():
    resolver = DefaultDomainProfileResolver()
    overlay = _overlay(source=DomainProfileSource.WORKFLOW, source_id="wf-missing")
    result = resolver.resolve(
        request=_request(workflow_ids=()),
        global_profile=_global(),
        primary_profile=_primary(),
        overlays=(overlay,),
    )
    assert result.status == DomainProfileResolutionStatus.PARTIAL
    assert result.profile is not None
    assert len(result.rejections) == 1
    assert result.rejections[0].blocking is False


def test_irrelevant_primary_domain_overlay_blocks_without_required_rules():
    resolver = DefaultDomainProfileResolver()
    overlay = _overlay(
        source=DomainProfileSource.PRIMARY_DOMAIN,
        source_id="university",
    )
    result = resolver.resolve(
        request=_request(),
        global_profile=_global(),
        primary_profile=_primary(),
        overlays=(overlay,),
    )
    assert result.status == DomainProfileResolutionStatus.BLOCKED
    assert result.profile is None
    assert any(c.blocking for c in result.conflicts)


def test_irrelevant_workflow_overlay_with_required_rules_is_partial_not_blocked():
    overlay = _overlay(
        source=DomainProfileSource.WORKFLOW,
        source_id="wf-missing",
        required_rules=("rule-1",),
    )
    result = DefaultDomainProfileResolver().resolve(
        request=_request(),
        global_profile=_global(),
        primary_profile=_primary(),
        overlays=(overlay,),
    )
    assert result.status == DomainProfileResolutionStatus.PARTIAL
    assert result.profile is not None


def test_irrelevant_global_overlay_blocks():
    overlay = _overlay(source=DomainProfileSource.GLOBAL_POLICY)
    assert _is_overlay_mandatory(overlay) is True


def test_irrelevant_supporting_overlay_is_partial():
    overlay = _overlay(
        source=DomainProfileSource.SUPPORTING_DOMAIN, source_id="relationship"
    )
    result = DefaultDomainProfileResolver().resolve(
        request=_request(),
        global_profile=_global(),
        primary_profile=_primary(),
        overlays=(overlay,),
    )
    assert result.status == DomainProfileResolutionStatus.PARTIAL


def test_resolver_preserves_empty_request_permissions():
    result = DefaultDomainProfileResolver().resolve(
        request=_request(permissions=()),
        global_profile=_global(permissions=("read", "write")),
        primary_profile=_primary(),
    )
    assert result.profile.permissions == ()


def test_resolver_preserves_none_request_permissions():
    result = DefaultDomainProfileResolver().resolve(
        request=_request(permissions=None),
        global_profile=_global(permissions=("read", "write")),
        primary_profile=_primary(),
    )
    assert result.profile.permissions == ("read", "write")


def test_blocking_composer_conflict_yields_blocked():
    resolver = DefaultDomainProfileResolver()
    result = resolver.resolve(
        request=_request(),
        global_profile=_global(required_rules=("r1",), prohibited_rules=("r1",)),
        primary_profile=_primary(),
    )
    assert result.status == DomainProfileResolutionStatus.BLOCKED
    assert result.profile is None
