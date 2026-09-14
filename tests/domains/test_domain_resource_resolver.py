"""Tests for Phase 10.10 – Domain Resource Resolver (Tasks 7-9)."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import pytest

from cmm.cognitive.enums import SensitivityLevel as Sensitivity
from cmm.domains.enums import (
    DomainResourceDecisionCode,
    DomainResourceResolutionStatus,
)
from cmm.domains.errors import DomainResourceResolutionError
from cmm.domains.identifiers import DomainId
from cmm.domains.resource_contracts import (
    DomainResourceContext,
    DomainResourceDefinition,
    DomainResourceTemporalPolicy,
    DomainResourceValidationRule,
)
from cmm.domains.resource_resolver import (
    DefaultDomainResourceResolver,
    DefaultDomainResourceValidator,
    DomainResourceResolver,
    DomainResourceValidator,
)


def _make_context(**overrides) -> DomainResourceContext:
    defaults = {
        "resource_id": "res-1",
        "kind": "calendar-event",
        "provenance": ("src-a",),
        "permissions": ("read",),
    }
    defaults.update(overrides)
    return DomainResourceContext(**defaults)


def _make_definition(**overrides) -> DomainResourceDefinition:
    defaults = {
        "id": "def-1",
        "kind": "calendar-event",
        "domain_id": DomainId("health"),
        "adapter": "health.calendar",
        "default_permissions": ("read",),
    }
    defaults.update(overrides)
    return DomainResourceDefinition(**defaults)


# ── Task 7: Declarative validator ───────────────────────────────────────────


def test_validator_is_runtime_checkable_protocol():
    assert isinstance(DefaultDomainResourceValidator(), DomainResourceValidator)


@pytest.mark.parametrize(
    ("operator", "expected", "field", "context_kwargs", "should_pass"),
    [
        ("exists", None, "source_type", {"source_type": "device"}, True),
        ("exists", None, "source_type", {}, False),
        ("equals", "device", "source_type", {"source_type": "device"}, True),
        ("equals", "device", "source_type", {"source_type": "other"}, False),
        ("not_equals", "other", "source_type", {"source_type": "device"}, True),
        ("contains", "read", "permissions", {"permissions": ("read", "write")}, True),
        ("in", ["a", "b"], "source_type", {"source_type": "a"}, True),
        ("in", ["a", "b"], "source_type", {"source_type": "c"}, False),
    ],
)
def test_validator_operators(operator, expected, field, context_kwargs, should_pass):
    rule = DomainResourceValidationRule(
        id="rule-1",
        field=field,
        operator=operator,
        expected=expected,
        severity="warning",
        message="check",
    )
    definition = _make_definition(validation_rules=(rule,))
    context = _make_context(**context_kwargs)
    results = DefaultDomainResourceValidator().validate(
        context=context, definition=definition
    )
    assert results[0].passed is should_pass


def test_validator_minimum_and_maximum_operators():
    minimum_rule = DomainResourceValidationRule(
        id="r-min",
        field="score",
        operator="minimum",
        expected=5,
        severity="error",
        message="too low",
    )
    maximum_rule = DomainResourceValidationRule(
        id="r-max",
        field="score",
        operator="maximum",
        expected=5,
        severity="error",
        message="too high",
    )
    definition = _make_definition(validation_rules=(minimum_rule, maximum_rule))
    context = _make_context(metadata={"score": 5})
    results = DefaultDomainResourceValidator().validate(
        context=context, definition=definition
    )
    assert all(r.passed for r in results)


def test_validator_missing_field_fails_non_exists_operators():
    rule = DomainResourceValidationRule(
        id="rule-1",
        field="missing_field",
        operator="equals",
        expected="x",
        severity="warning",
        message="check",
    )
    definition = _make_definition(validation_rules=(rule,))
    context = _make_context()
    results = DefaultDomainResourceValidator().validate(
        context=context, definition=definition
    )
    assert results[0].passed is False


def test_validator_only_looks_at_explicit_fields_and_metadata():
    rule = DomainResourceValidationRule(
        id="rule-1",
        field="custom_meta",
        operator="equals",
        expected="value",
        severity="warning",
        message="check",
    )
    definition = _make_definition(validation_rules=(rule,))
    context = _make_context(metadata={"custom_meta": "value"})
    results = DefaultDomainResourceValidator().validate(
        context=context, definition=definition
    )
    assert results[0].passed is True


# ── Task 8: Permission, sensitivity and temporal helpers ───────────────────


def test_resolver_definitions_never_widen_permissions():
    resolver = DefaultDomainResourceResolver()
    definition = _make_definition(default_permissions=("read", "write"))
    context = _make_context(permissions=("read",))
    resolution = resolver.resolve(
        context=context,
        definitions=(definition,),
        requested_domains=(DomainId("health"),),
        request_permissions=("read", "write"),
    )
    assert resolution.bindings[0].permissions == ("read",)


def test_resolver_rejects_empty_effective_permissions():
    resolver = DefaultDomainResourceResolver()
    definition = _make_definition(default_permissions=("write",))
    context = _make_context(permissions=("read",))
    resolution = resolver.resolve(
        context=context,
        definitions=(definition,),
        requested_domains=(DomainId("health"),),
        request_permissions=("read",),
    )
    assert not resolution.bindings
    assert resolution.permission_denials


def test_resolver_explicit_deny_wins():
    resolver = DefaultDomainResourceResolver()
    definition = _make_definition(default_permissions=("read", "deny:read"))
    context = _make_context(permissions=("read", "deny:read"))
    resolution = resolver.resolve(
        context=context,
        definitions=(definition,),
        requested_domains=(DomainId("health"),),
        request_permissions=("read", "deny:read"),
    )
    assert not resolution.bindings
    assert resolution.permission_denials


def test_resolver_sensitivity_can_rise_but_not_fall():
    resolver = DefaultDomainResourceResolver()
    definition = _make_definition(default_sensitivity=Sensitivity.SENSITIVE)
    context = _make_context(sensitivity=Sensitivity.INTERNAL)
    resolution = resolver.resolve(
        context=context,
        definitions=(definition,),
        requested_domains=(DomainId("health"),),
        request_permissions=("read",),
    )
    assert resolution.bindings[0].sensitivity == Sensitivity.SENSITIVE


def test_resolver_temporal_effective_date_required():
    resolver = DefaultDomainResourceResolver()
    policy = DomainResourceTemporalPolicy(effective_date_required=True)
    definition = _make_definition(temporal_policy=policy)
    context = _make_context()
    resolution = resolver.resolve(
        context=context,
        definitions=(definition,),
        requested_domains=(DomainId("health"),),
        request_permissions=("read",),
    )
    assert not resolution.bindings
    assert any(r.blocking for r in resolution.rejections)


def test_resolver_temporal_validity_window_staleness():
    now = datetime(2026, 1, 1, tzinfo=timezone.utc)
    resolver = DefaultDomainResourceResolver(clock=lambda: now)
    policy = DomainResourceTemporalPolicy(validity_window_seconds=60)
    definition = _make_definition(temporal_policy=policy)
    context = _make_context(
        temporal_scope={"observed_at": now - timedelta(seconds=120)}
    )
    resolution = resolver.resolve(
        context=context,
        definitions=(definition,),
        requested_domains=(DomainId("health"),),
        request_permissions=("read",),
    )
    assert not resolution.bindings


def test_resolver_temporal_historical_use_disallowed():
    now = datetime(2026, 1, 1, tzinfo=timezone.utc)
    resolver = DefaultDomainResourceResolver(clock=lambda: now)
    policy = DomainResourceTemporalPolicy(historical_allowed=False)
    definition = _make_definition(temporal_policy=policy)
    context = _make_context(temporal_scope={"valid_until": now - timedelta(days=1)})
    resolution = resolver.resolve(
        context=context,
        definitions=(definition,),
        requested_domains=(DomainId("health"),),
        request_permissions=("read",),
    )
    assert not resolution.bindings


# ── Task 9: Resolver protocol and default resolver ──────────────────────────


def test_resolver_is_runtime_checkable_protocol():
    assert isinstance(DefaultDomainResourceResolver(), DomainResourceResolver)


def test_resolver_matches_kind_and_requested_domain():
    resolver = DefaultDomainResourceResolver()
    definition = _make_definition()
    other = _make_definition(id="def-other", kind="note")
    context = _make_context()
    resolution = resolver.resolve(
        context=context,
        definitions=(definition, other),
        requested_domains=(DomainId("health"),),
        request_permissions=("read",),
    )
    assert len(resolution.bindings) == 1
    assert resolution.bindings[0].definition_id == "def-1"


def test_resolver_shares_resource_across_domains_without_duplication():
    resolver = DefaultDomainResourceResolver()
    health_def = _make_definition(id="def-health", domain_id=DomainId("health"))
    university_def = _make_definition(
        id="def-university", domain_id=DomainId("university")
    )
    context = _make_context()
    resolution = resolver.resolve(
        context=context,
        definitions=(health_def, university_def),
        requested_domains=(DomainId("health"), DomainId("university")),
        request_permissions=("read",),
    )
    assert len(resolution.bindings) == 2
    assert resolution.status == DomainResourceResolutionStatus.RESOLVED
    assert set(resolution.shared_domains) == {
        DomainId("health"),
        DomainId("university"),
    }


def test_resolver_status_rejected_when_no_candidate_matches():
    resolver = DefaultDomainResourceResolver()
    definition = _make_definition(kind="note")
    context = _make_context()
    resolution = resolver.resolve(
        context=context,
        definitions=(definition,),
        requested_domains=(DomainId("health"),),
        request_permissions=("read",),
    )
    assert resolution.status == DomainResourceResolutionStatus.REJECTED
    assert not resolution.bindings


def test_resolver_status_blocked_when_blocking_rejection_and_no_bindings():
    resolver = DefaultDomainResourceResolver()
    definition = _make_definition(default_permissions=("write",))
    context = _make_context(permissions=("read",))
    resolution = resolver.resolve(
        context=context,
        definitions=(definition,),
        requested_domains=(DomainId("health"),),
        request_permissions=("read",),
    )
    assert resolution.status == DomainResourceResolutionStatus.BLOCKED


def test_resolver_status_partial_when_some_bindings_and_some_rejections():
    resolver = DefaultDomainResourceResolver()
    ok_def = _make_definition(
        id="def-ok", domain_id=DomainId("health"), default_permissions=("read",)
    )
    context = _make_context(permissions=("read",))
    resolution = resolver.resolve(
        context=context,
        definitions=(ok_def,),
        requested_domains=(DomainId("health"), DomainId("university")),
        request_permissions=("read",),
    )
    assert resolution.status == DomainResourceResolutionStatus.PARTIAL
    assert len(resolution.bindings) == 1


def test_resolver_status_blocked_even_with_an_independent_binding():
    resolver = DefaultDomainResourceResolver()
    ok_def = _make_definition(
        id="def-ok", domain_id=DomainId("health"), default_permissions=("read",)
    )
    denied_def = _make_definition(
        id="def-denied",
        domain_id=DomainId("university"),
        default_permissions=("write",),
    )
    context = _make_context(permissions=("read",))
    resolution = resolver.resolve(
        context=context,
        definitions=(ok_def, denied_def),
        requested_domains=(DomainId("health"), DomainId("university")),
        request_permissions=("read",),
    )
    assert resolution.status == DomainResourceResolutionStatus.BLOCKED
    assert len(resolution.bindings) == 1


def test_resolver_source_priority_orders_bindings_deterministically():
    resolver = DefaultDomainResourceResolver()
    low = _make_definition(
        id="def-low", domain_id=DomainId("university"), source_priority=1
    )
    high = _make_definition(
        id="def-high", domain_id=DomainId("health"), source_priority=10
    )
    context = _make_context()
    resolution = resolver.resolve(
        context=context,
        definitions=(low, high),
        requested_domains=(DomainId("health"), DomainId("university")),
        request_permissions=("read",),
    )
    assert [b.definition_id for b in resolution.bindings] == ["def-high", "def-low"]


def test_resolver_reliability_never_overrides_sensitivity():
    resolver = DefaultDomainResourceResolver()
    definition = _make_definition(
        default_reliability=0.1, default_sensitivity=Sensitivity.RESTRICTED
    )
    context = _make_context(sensitivity=Sensitivity.PUBLIC)
    resolution = resolver.resolve(
        context=context,
        definitions=(definition,),
        requested_domains=(DomainId("health"),),
        request_permissions=("read",),
    )
    assert resolution.bindings[0].sensitivity == Sensitivity.RESTRICTED
    assert resolution.bindings[0].reliability == 0.1


def test_resolver_applicable_domains_restrict_candidates():
    resolver = DefaultDomainResourceResolver()
    definition = _make_definition(domain_id=DomainId("university"))
    context = _make_context(applicable_domains=(DomainId("health"),))
    resolution = resolver.resolve(
        context=context,
        definitions=(definition,),
        requested_domains=(DomainId("university"),),
        request_permissions=("read",),
    )
    assert not resolution.bindings


def test_resolver_non_shareable_definition_rejected_for_second_domain():
    resolver = DefaultDomainResourceResolver()
    definition_a = _make_definition(
        id="def-a", domain_id=DomainId("health"), shareable=False
    )
    definition_b = _make_definition(
        id="def-b", domain_id=DomainId("university"), shareable=False
    )
    context = _make_context()
    resolution = resolver.resolve(
        context=context,
        definitions=(definition_a, definition_b),
        requested_domains=(DomainId("health"), DomainId("university")),
        request_permissions=("read",),
    )
    assert len(resolution.bindings) == 1
    assert resolution.bindings[0].definition_id == "def-a"
    skipped = [
        r
        for r in resolution.decisions
        if r.code == DomainResourceDecisionCode.DEFINITION_SKIPPED
    ]
    assert len(skipped) == 1
    assert skipped[0].definition_id == "def-b"


def test_resolve_is_deterministic_across_calls():
    resolver = DefaultDomainResourceResolver(
        clock=lambda: datetime(2026, 1, 1, tzinfo=timezone.utc),
        id_factory=lambda: "fixed-id",
        trace_id_factory=lambda: "fixed-trace",
    )
    definition = _make_definition()
    context = _make_context()
    resolution_a = resolver.resolve(
        context=context,
        definitions=(definition,),
        requested_domains=(DomainId("health"),),
        request_permissions=("read",),
    )
    resolution_b = resolver.resolve(
        context=context,
        definitions=(definition,),
        requested_domains=(DomainId("health"),),
        request_permissions=("read",),
    )
    assert resolution_a.to_dict() == resolution_b.to_dict()


# ── Section 1: multi-domain sharing with shareable=False ────────────────────


def test_non_shareable_definition_blocks_multidomain_binding():
    resolver = DefaultDomainResourceResolver()
    definition_a = _make_definition(
        id="def-a", domain_id=DomainId("health"), shareable=False
    )
    definition_b = _make_definition(
        id="def-b", domain_id=DomainId("university"), shareable=False
    )
    context = _make_context()
    resolution = resolver.resolve(
        context=context,
        definitions=(definition_a, definition_b),
        requested_domains=(DomainId("health"), DomainId("university")),
        request_permissions=("read",),
    )
    assert len(resolution.bindings) == 1
    assert resolution.bindings[0].definition_id == "def-a"


def test_non_shareable_definition_allows_single_domain_binding():
    resolver = DefaultDomainResourceResolver()
    definition = _make_definition(domain_id=DomainId("health"), shareable=False)
    context = _make_context()
    resolution = resolver.resolve(
        context=context,
        definitions=(definition,),
        requested_domains=(DomainId("health"),),
        request_permissions=("read",),
    )
    assert len(resolution.bindings) == 1
    assert resolution.bindings[0].domain_id == DomainId("health")


def test_two_non_shareable_definitions_in_different_domains_do_not_share():
    resolver = DefaultDomainResourceResolver()
    definition_a = _make_definition(
        id="def-a", domain_id=DomainId("health"), shareable=False
    )
    definition_b = _make_definition(
        id="def-b", domain_id=DomainId("university"), shareable=False
    )
    context = _make_context()
    resolution = resolver.resolve(
        context=context,
        definitions=(definition_a, definition_b),
        requested_domains=(DomainId("health"), DomainId("university")),
        request_permissions=("read",),
    )
    assert len(resolution.bindings) == 1
    assert len(resolution.shared_domains) <= 1


def test_shareable_definitions_bind_same_resource_without_duplication():
    resolver = DefaultDomainResourceResolver()
    definition_a = _make_definition(
        id="def-a", domain_id=DomainId("health"), shareable=True
    )
    definition_b = _make_definition(
        id="def-b", domain_id=DomainId("university"), shareable=True
    )
    context = _make_context()
    resolution = resolver.resolve(
        context=context,
        definitions=(definition_a, definition_b),
        requested_domains=(DomainId("health"), DomainId("university")),
        request_permissions=("read",),
    )
    assert len(resolution.bindings) == 2
    assert not resolution.rejections


# ── Section 2: preserve requested_domains order ─────────────────────────────


def test_bindings_preserve_requested_domain_order():
    resolver = DefaultDomainResourceResolver()
    health_def = _make_definition(id="def-health", domain_id=DomainId("health"))
    university_def = _make_definition(
        id="def-university", domain_id=DomainId("university")
    )
    context = _make_context()
    resolution = resolver.resolve(
        context=context,
        definitions=(health_def, university_def),
        requested_domains=(DomainId("university"), DomainId("health")),
        request_permissions=("read",),
    )
    assert [b.definition_id for b in resolution.bindings] == [
        "def-university",
        "def-health",
    ]


def test_shared_domains_preserve_requested_domain_order():
    resolver = DefaultDomainResourceResolver()
    health_def = _make_definition(id="def-health", domain_id=DomainId("health"))
    university_def = _make_definition(
        id="def-university", domain_id=DomainId("university")
    )
    context = _make_context()
    resolution = resolver.resolve(
        context=context,
        definitions=(health_def, university_def),
        requested_domains=(DomainId("university"), DomainId("health")),
        request_permissions=("read",),
    )
    assert resolution.shared_domains == (DomainId("university"), DomainId("health"))


# ── Section 3: unresolved requested domains ─────────────────────────────────


def test_requested_domain_without_definition_makes_resolution_partial():
    resolver = DefaultDomainResourceResolver()
    definition = _make_definition(domain_id=DomainId("health"))
    context = _make_context()
    resolution = resolver.resolve(
        context=context,
        definitions=(definition,),
        requested_domains=(DomainId("health"), DomainId("university")),
        request_permissions=("read",),
    )
    assert resolution.status == DomainResourceResolutionStatus.PARTIAL
    assert len(resolution.bindings) == 1
    unresolved = [
        r
        for r in resolution.rejections
        if r.code == DomainResourceDecisionCode.DOMAIN_NOT_APPLICABLE
    ]
    assert len(unresolved) == 1
    assert unresolved[0].blocking is False
    assert unresolved[0].domain_id == DomainId("university")


def test_all_requested_domains_without_definition_are_rejected():
    resolver = DefaultDomainResourceResolver()
    definition = _make_definition(kind="note", domain_id=DomainId("health"))
    context = _make_context()
    resolution = resolver.resolve(
        context=context,
        definitions=(definition,),
        requested_domains=(DomainId("health"), DomainId("university")),
        request_permissions=("read",),
    )
    assert resolution.status == DomainResourceResolutionStatus.REJECTED
    assert not resolution.bindings
    assert all(
        r.code == DomainResourceDecisionCode.DOMAIN_NOT_APPLICABLE
        for r in resolution.rejections
    )


# ── Section 4: effective reliability ────────────────────────────────────────


def test_context_reliability_restricts_definition_reliability():
    resolver = DefaultDomainResourceResolver()
    definition = _make_definition(default_reliability=0.9)
    context = _make_context(reliability=0.5)
    resolution = resolver.resolve(
        context=context,
        definitions=(definition,),
        requested_domains=(DomainId("health"),),
        request_permissions=("read",),
    )
    assert resolution.bindings[0].reliability == 0.5


def test_definition_reliability_restricts_context_reliability():
    resolver = DefaultDomainResourceResolver()
    definition = _make_definition(default_reliability=0.3)
    context = _make_context(reliability=0.9)
    resolution = resolver.resolve(
        context=context,
        definitions=(definition,),
        requested_domains=(DomainId("health"),),
        request_permissions=("read",),
    )
    assert resolution.bindings[0].reliability == 0.3


def test_missing_context_reliability_uses_definition_default():
    resolver = DefaultDomainResourceResolver()
    definition = _make_definition(default_reliability=0.42)
    context = _make_context()
    resolution = resolver.resolve(
        context=context,
        definitions=(definition,),
        requested_domains=(DomainId("health"),),
        request_permissions=("read",),
    )
    assert resolution.bindings[0].reliability == 0.42


def test_reliability_decision_is_recorded():
    resolver = DefaultDomainResourceResolver()
    definition = _make_definition()
    context = _make_context()
    resolution = resolver.resolve(
        context=context,
        definitions=(definition,),
        requested_domains=(DomainId("health"),),
        request_permissions=("read",),
    )
    applied = [
        d
        for d in resolution.decisions
        if d.code == DomainResourceDecisionCode.RELIABILITY_APPLIED
    ]
    assert len(applied) == 1
    assert applied[0].definition_id == definition.id


# ── Section 5: nested metadata path validator ───────────────────────────────


def test_validator_reads_nested_metadata_path():
    rule = DomainResourceValidationRule(
        id="rule-nested",
        field="metadata.source.kind",
        operator="equals",
        expected="manual",
        severity="warning",
        message="source kind mismatch",
    )
    definition = _make_definition(validation_rules=(rule,))
    context = _make_context(metadata={"source": {"kind": "manual"}})
    results = DefaultDomainResourceValidator().validate(
        context=context, definition=definition
    )
    assert results[0].passed is True


def test_validator_rejects_dunder_metadata_path():
    rule = DomainResourceValidationRule(
        id="rule-dunder",
        field="metadata.__class__",
        operator="exists",
        expected=None,
        severity="warning",
        message="dunder path must never resolve",
    )
    definition = _make_definition(validation_rules=(rule,))
    context = _make_context(metadata={"__class__": "leak"})
    results = DefaultDomainResourceValidator().validate(
        context=context, definition=definition
    )
    assert results[0].passed is False
    assert results[0].observed is None


def test_validator_missing_nested_path_fails_safely():
    rule = DomainResourceValidationRule(
        id="rule-missing-nested",
        field="metadata.source.details.version",
        operator="exists",
        expected=None,
        severity="warning",
        message="missing nested path",
    )
    definition = _make_definition(validation_rules=(rule,))
    context = _make_context(metadata={"source": {"kind": "manual"}})
    results = DefaultDomainResourceValidator().validate(
        context=context, definition=definition
    )
    assert results[0].passed is False


# ── Section 6: CONTAINS on mappings ──────────────────────────────────────────


def test_contains_mapping_checks_key():
    rule = DomainResourceValidationRule(
        id="rule-contains-key",
        field="metadata.tags",
        operator="contains",
        expected="read",
        severity="warning",
        message="tags must contain read",
    )
    definition = _make_definition(validation_rules=(rule,))
    context = _make_context(metadata={"tags": {"read": True}})
    results = DefaultDomainResourceValidator().validate(
        context=context, definition=definition
    )
    assert results[0].passed is True


def test_contains_mapping_does_not_check_value():
    rule = DomainResourceValidationRule(
        id="rule-contains-value",
        field="metadata.tags",
        operator="contains",
        expected="write",
        severity="warning",
        message="tags must contain write key regardless of its value",
    )
    definition = _make_definition(validation_rules=(rule,))
    context = _make_context(metadata={"tags": {"write": False}})
    results = DefaultDomainResourceValidator().validate(
        context=context, definition=definition
    )
    assert results[0].passed is True


# ── Section 7: status derivation ─────────────────────────────────────────────


def test_blocking_rejection_with_independent_binding_is_blocked():
    resolver = DefaultDomainResourceResolver()
    ok_def = _make_definition(id="def-ok", domain_id=DomainId("health"))
    denied_def = _make_definition(
        id="def-denied",
        domain_id=DomainId("university"),
        default_permissions=("write",),
    )
    context = _make_context(permissions=("read",))
    resolution = resolver.resolve(
        context=context,
        definitions=(ok_def, denied_def),
        requested_domains=(DomainId("health"), DomainId("university")),
        request_permissions=("read",),
    )
    assert resolution.status == DomainResourceResolutionStatus.BLOCKED
    assert len(resolution.bindings) == 1


def test_blocking_validation_with_independent_binding_is_blocked():
    resolver = DefaultDomainResourceResolver()
    blocking_rule = DomainResourceValidationRule(
        id="rule-blocking",
        field="source_type",
        operator="equals",
        expected="device",
        severity="blocking",
        message="source type must be device",
    )
    ok_def = _make_definition(id="def-ok", domain_id=DomainId("health"))
    failing_def = _make_definition(
        id="def-failing",
        domain_id=DomainId("university"),
        validation_rules=(blocking_rule,),
    )
    context = _make_context(source_type="human")
    resolution = resolver.resolve(
        context=context,
        definitions=(ok_def, failing_def),
        requested_domains=(DomainId("health"), DomainId("university")),
        request_permissions=("read",),
    )
    assert resolution.status == DomainResourceResolutionStatus.BLOCKED
    assert len(resolution.bindings) == 1


# ── Section 8: complete decision coverage ────────────────────────────────────


def test_definition_selected_decision_is_recorded():
    resolver = DefaultDomainResourceResolver()
    definition = _make_definition()
    context = _make_context()
    resolution = resolver.resolve(
        context=context,
        definitions=(definition,),
        requested_domains=(DomainId("health"),),
        request_permissions=("read",),
    )
    assert any(
        d.code == DomainResourceDecisionCode.DEFINITION_SELECTED
        for d in resolution.decisions
    )


def test_definition_skipped_decision_is_recorded():
    resolver = DefaultDomainResourceResolver()
    definition_a = _make_definition(
        id="def-a", domain_id=DomainId("health"), shareable=False
    )
    definition_b = _make_definition(
        id="def-b", domain_id=DomainId("university"), shareable=False
    )
    context = _make_context()
    resolution = resolver.resolve(
        context=context,
        definitions=(definition_a, definition_b),
        requested_domains=(DomainId("health"), DomainId("university")),
        request_permissions=("read",),
    )
    assert any(
        d.code == DomainResourceDecisionCode.DEFINITION_SKIPPED
        for d in resolution.decisions
    )


def test_domain_not_applicable_decision_is_recorded():
    resolver = DefaultDomainResourceResolver()
    definition = _make_definition(domain_id=DomainId("health"))
    context = _make_context()
    resolution = resolver.resolve(
        context=context,
        definitions=(definition,),
        requested_domains=(DomainId("health"), DomainId("university")),
        request_permissions=("read",),
    )
    assert any(
        d.code == DomainResourceDecisionCode.DOMAIN_NOT_APPLICABLE
        for d in resolution.decisions
    )


def test_permission_denied_decision_is_recorded():
    resolver = DefaultDomainResourceResolver()
    definition = _make_definition(default_permissions=("write",))
    context = _make_context(permissions=("read",))
    resolution = resolver.resolve(
        context=context,
        definitions=(definition,),
        requested_domains=(DomainId("health"),),
        request_permissions=("read",),
    )
    assert any(
        d.code == DomainResourceDecisionCode.PERMISSION_DENIED
        for d in resolution.decisions
    )


def test_sensitivity_restricted_decision_is_recorded():
    resolver = DefaultDomainResourceResolver()
    definition = _make_definition(default_sensitivity=Sensitivity.SENSITIVE)
    context = _make_context(sensitivity=Sensitivity.INTERNAL)
    resolution = resolver.resolve(
        context=context,
        definitions=(definition,),
        requested_domains=(DomainId("health"),),
        request_permissions=("read",),
    )
    assert any(
        d.code == DomainResourceDecisionCode.SENSITIVITY_RESTRICTED
        for d in resolution.decisions
    )


def test_temporal_policy_failed_decision_is_recorded():
    resolver = DefaultDomainResourceResolver()
    policy = DomainResourceTemporalPolicy(effective_date_required=True)
    definition = _make_definition(temporal_policy=policy)
    context = _make_context()
    resolution = resolver.resolve(
        context=context,
        definitions=(definition,),
        requested_domains=(DomainId("health"),),
        request_permissions=("read",),
    )
    assert any(
        d.code == DomainResourceDecisionCode.TEMPORAL_POLICY_FAILED
        for d in resolution.decisions
    )


def test_validation_failed_decision_is_recorded():
    resolver = DefaultDomainResourceResolver()
    blocking_rule = DomainResourceValidationRule(
        id="rule-blocking",
        field="source_type",
        operator="equals",
        expected="device",
        severity="blocking",
        message="source type must be device",
    )
    definition = _make_definition(validation_rules=(blocking_rule,))
    context = _make_context(source_type="human")
    resolution = resolver.resolve(
        context=context,
        definitions=(definition,),
        requested_domains=(DomainId("health"),),
        request_permissions=("read",),
    )
    assert any(
        d.code == DomainResourceDecisionCode.VALIDATION_FAILED
        for d in resolution.decisions
    )


def test_resource_shared_decision_is_recorded():
    resolver = DefaultDomainResourceResolver()
    health_def = _make_definition(id="def-health", domain_id=DomainId("health"))
    university_def = _make_definition(
        id="def-university", domain_id=DomainId("university")
    )
    context = _make_context()
    resolution = resolver.resolve(
        context=context,
        definitions=(health_def, university_def),
        requested_domains=(DomainId("health"), DomainId("university")),
        request_permissions=("read",),
    )
    assert any(
        d.code == DomainResourceDecisionCode.RESOURCE_SHARED
        for d in resolution.decisions
    )


def test_no_duplicate_exact_decisions():
    resolver = DefaultDomainResourceResolver()
    health_def = _make_definition(id="def-health", domain_id=DomainId("health"))
    university_def = _make_definition(
        id="def-university", domain_id=DomainId("university")
    )
    context = _make_context()
    resolution = resolver.resolve(
        context=context,
        definitions=(health_def, university_def),
        requested_domains=(DomainId("health"), DomainId("university")),
        request_permissions=("read",),
    )
    seen = [json.dumps(d.to_dict(), sort_keys=True) for d in resolution.decisions]
    assert len(set(seen)) == len(seen)


# ── Section 10: constructor and factory validation ───────────────────────────


def test_non_callable_clock_rejected():
    with pytest.raises(DomainResourceResolutionError):
        DefaultDomainResourceResolver(clock="not-callable")


def test_non_callable_id_factory_rejected():
    with pytest.raises(DomainResourceResolutionError):
        DefaultDomainResourceResolver(id_factory="not-callable")


def test_non_callable_trace_factory_rejected():
    with pytest.raises(DomainResourceResolutionError):
        DefaultDomainResourceResolver(trace_id_factory="not-callable")


def test_invalid_validator_rejected():
    with pytest.raises(DomainResourceResolutionError):
        DefaultDomainResourceResolver(validator=object())


def test_naive_clock_result_rejected():
    resolver = DefaultDomainResourceResolver(
        clock=lambda: datetime(2026, 1, 1)  # noqa: DTZ001
    )
    definition = _make_definition()
    context = _make_context()
    with pytest.raises(DomainResourceResolutionError):
        resolver.resolve(
            context=context,
            definitions=(definition,),
            requested_domains=(DomainId("health"),),
            request_permissions=("read",),
        )


def test_empty_resolution_id_rejected():
    ids = iter(["binding-id"])

    def id_factory() -> str:
        return next(ids, "")

    resolver = DefaultDomainResourceResolver(id_factory=id_factory)
    definition = _make_definition()
    context = _make_context()
    with pytest.raises(DomainResourceResolutionError):
        resolver.resolve(
            context=context,
            definitions=(definition,),
            requested_domains=(DomainId("health"),),
            request_permissions=("read",),
        )


def test_empty_trace_id_rejected():
    resolver = DefaultDomainResourceResolver(trace_id_factory=lambda: "")
    definition = _make_definition()
    context = _make_context()
    with pytest.raises(DomainResourceResolutionError):
        resolver.resolve(
            context=context,
            definitions=(definition,),
            requested_domains=(DomainId("health"),),
            request_permissions=("read",),
        )


def test_empty_binding_id_rejected():
    resolver = DefaultDomainResourceResolver(id_factory=lambda: "")
    definition = _make_definition()
    context = _make_context()
    with pytest.raises(DomainResourceResolutionError):
        resolver.resolve(
            context=context,
            definitions=(definition,),
            requested_domains=(DomainId("health"),),
            request_permissions=("read",),
        )


def test_factory_errors_propagate():
    class BoomError(Exception):
        pass

    def bad_id_factory() -> str:
        raise BoomError("boom")

    resolver = DefaultDomainResourceResolver(id_factory=bad_id_factory)
    definition = _make_definition()
    context = _make_context()
    with pytest.raises(BoomError):
        resolver.resolve(
            context=context,
            definitions=(definition,),
            requested_domains=(DomainId("health"),),
            request_permissions=("read",),
        )


# ── Section 11: deny by specific permission ──────────────────────────────────


def test_deny_write_does_not_remove_read():
    resolver = DefaultDomainResourceResolver()
    definition = _make_definition(default_permissions=("read", "write"))
    context = _make_context(permissions=("read", "write"))
    resolution = resolver.resolve(
        context=context,
        definitions=(definition,),
        requested_domains=(DomainId("health"),),
        request_permissions=("read", "deny:write"),
    )
    assert resolution.bindings[0].permissions == ("read",)


def test_deny_read_removes_read():
    resolver = DefaultDomainResourceResolver()
    definition = _make_definition(default_permissions=("read", "write"))
    context = _make_context(permissions=("read", "write"))
    resolution = resolver.resolve(
        context=context,
        definitions=(definition,),
        requested_domains=(DomainId("health"),),
        request_permissions=("write", "deny:read"),
    )
    assert resolution.bindings[0].permissions == ("write",)


def test_all_effective_permissions_denied_rejects_binding():
    resolver = DefaultDomainResourceResolver()
    definition = _make_definition(default_permissions=("read", "write"))
    context = _make_context(permissions=("read", "write"))
    resolution = resolver.resolve(
        context=context,
        definitions=(definition,),
        requested_domains=(DomainId("health"),),
        request_permissions=("read", "write", "deny:read", "deny:write"),
    )
    assert not resolution.bindings
    assert resolution.permission_denials


def test_definition_deny_cannot_be_lifted_by_request():
    resolver = DefaultDomainResourceResolver()
    definition = _make_definition(default_permissions=("read", "write", "deny:write"))
    context = _make_context(permissions=("read", "write"))
    resolution = resolver.resolve(
        context=context,
        definitions=(definition,),
        requested_domains=(DomainId("health"),),
        request_permissions=("read", "write"),
    )
    assert resolution.bindings[0].permissions == ("read",)


def test_resource_deny_cannot_be_lifted_by_definition():
    resolver = DefaultDomainResourceResolver()
    definition = _make_definition(default_permissions=("read", "write"))
    context = _make_context(permissions=("read", "write", "deny:write"))
    resolution = resolver.resolve(
        context=context,
        definitions=(definition,),
        requested_domains=(DomainId("health"),),
        request_permissions=("read", "write"),
    )
    assert resolution.bindings[0].permissions == ("read",)


# ── Section 12: source priority retains all valid bindings ──────────────────


def test_all_valid_same_domain_definitions_are_retained():
    resolver = DefaultDomainResourceResolver()
    low = _make_definition(
        id="def-low", domain_id=DomainId("health"), source_priority=1
    )
    high = _make_definition(
        id="def-high", domain_id=DomainId("health"), source_priority=10
    )
    context = _make_context()
    resolution = resolver.resolve(
        context=context,
        definitions=(low, high),
        requested_domains=(DomainId("health"),),
        request_permissions=("read",),
    )
    assert len(resolution.bindings) == 2
    assert {b.definition_id for b in resolution.bindings} == {"def-low", "def-high"}


def test_same_domain_bindings_follow_source_priority():
    resolver = DefaultDomainResourceResolver()
    low = _make_definition(
        id="def-low", domain_id=DomainId("health"), source_priority=1
    )
    high = _make_definition(
        id="def-high", domain_id=DomainId("health"), source_priority=10
    )
    context = _make_context()
    resolution = resolver.resolve(
        context=context,
        definitions=(low, high),
        requested_domains=(DomainId("health"),),
        request_permissions=("read",),
    )
    assert [b.definition_id for b in resolution.bindings] == ["def-high", "def-low"]


def test_source_priority_decision_is_recorded():
    resolver = DefaultDomainResourceResolver()
    low = _make_definition(
        id="def-low", domain_id=DomainId("health"), source_priority=1
    )
    high = _make_definition(
        id="def-high", domain_id=DomainId("health"), source_priority=10
    )
    context = _make_context()
    resolution = resolver.resolve(
        context=context,
        definitions=(low, high),
        requested_domains=(DomainId("health"),),
        request_permissions=("read",),
    )
    applied = [
        d
        for d in resolution.decisions
        if d.code == DomainResourceDecisionCode.SOURCE_PRIORITY_APPLIED
    ]
    assert len(applied) == 1
    assert applied[0].domain_id == DomainId("health")


# ── Final defect fixes: order-independent sharing (Section 1) ──────────────


def test_non_shareable_first_then_shareable_does_not_share():
    resolver = DefaultDomainResourceResolver()
    non_shareable = _make_definition(
        id="def-a", domain_id=DomainId("health"), shareable=False
    )
    shareable = _make_definition(
        id="def-b", domain_id=DomainId("university"), shareable=True
    )
    context = _make_context()
    resolution = resolver.resolve(
        context=context,
        definitions=(non_shareable, shareable),
        requested_domains=(DomainId("health"), DomainId("university")),
        request_permissions=("read",),
    )
    assert len(resolution.bindings) == 1
    assert resolution.bindings[0].definition_id == "def-a"


def test_shareable_first_then_non_shareable_does_not_share():
    resolver = DefaultDomainResourceResolver()
    shareable = _make_definition(
        id="def-b", domain_id=DomainId("university"), shareable=True
    )
    non_shareable = _make_definition(
        id="def-a", domain_id=DomainId("health"), shareable=False
    )
    context = _make_context()
    resolution = resolver.resolve(
        context=context,
        definitions=(shareable, non_shareable),
        requested_domains=(DomainId("health"), DomainId("university")),
        request_permissions=("read",),
    )
    assert len(resolution.bindings) == 1
    assert resolution.bindings[0].definition_id == "def-a"


def test_mixed_shareability_is_input_order_independent():
    resolver = DefaultDomainResourceResolver()
    non_shareable = _make_definition(
        id="def-a", domain_id=DomainId("health"), shareable=False
    )
    shareable = _make_definition(
        id="def-b", domain_id=DomainId("university"), shareable=True
    )
    context = _make_context()

    order_a = resolver.resolve(
        context=context,
        definitions=(non_shareable, shareable),
        requested_domains=(DomainId("health"), DomainId("university")),
        request_permissions=("read",),
    )
    order_b = resolver.resolve(
        context=context,
        definitions=(shareable, non_shareable),
        requested_domains=(DomainId("health"), DomainId("university")),
        request_permissions=("read",),
    )
    assert [b.definition_id for b in order_a.bindings] == [
        b.definition_id for b in order_b.bindings
    ]


def test_all_shareable_definitions_can_share():
    resolver = DefaultDomainResourceResolver()
    definition_a = _make_definition(
        id="def-a", domain_id=DomainId("health"), shareable=True
    )
    definition_b = _make_definition(
        id="def-b", domain_id=DomainId("university"), shareable=True
    )
    context = _make_context()
    resolution = resolver.resolve(
        context=context,
        definitions=(definition_a, definition_b),
        requested_domains=(DomainId("health"), DomainId("university")),
        request_permissions=("read",),
    )
    assert len(resolution.bindings) == 2


def test_non_shareable_same_domain_multiple_definitions_are_allowed():
    resolver = DefaultDomainResourceResolver()
    definition_a = _make_definition(
        id="def-a", domain_id=DomainId("health"), shareable=False, source_priority=1
    )
    definition_b = _make_definition(
        id="def-b", domain_id=DomainId("health"), shareable=False, source_priority=2
    )
    context = _make_context()
    resolution = resolver.resolve(
        context=context,
        definitions=(definition_a, definition_b),
        requested_domains=(DomainId("health"),),
        request_permissions=("read",),
    )
    assert len(resolution.bindings) == 2
    assert not resolution.rejections


# ── Final defect fixes: SOURCE_PRIORITY_APPLIED only for valid bindings ────
# (Section 2)


def test_source_priority_not_recorded_when_second_candidate_permission_denied():
    resolver = DefaultDomainResourceResolver()
    ok = _make_definition(
        id="def-ok", domain_id=DomainId("health"), default_permissions=("read",)
    )
    denied = _make_definition(
        id="def-denied", domain_id=DomainId("health"), default_permissions=("write",)
    )
    context = _make_context(permissions=("read",))
    resolution = resolver.resolve(
        context=context,
        definitions=(ok, denied),
        requested_domains=(DomainId("health"),),
        request_permissions=("read",),
    )
    applied = [
        d
        for d in resolution.decisions
        if d.code == DomainResourceDecisionCode.SOURCE_PRIORITY_APPLIED
    ]
    assert not applied


def test_source_priority_not_recorded_when_second_candidate_temporally_invalid():
    resolver = DefaultDomainResourceResolver()
    ok = _make_definition(id="def-ok", domain_id=DomainId("health"))
    policy = DomainResourceTemporalPolicy(effective_date_required=True)
    invalid = _make_definition(
        id="def-invalid", domain_id=DomainId("health"), temporal_policy=policy
    )
    context = _make_context()
    resolution = resolver.resolve(
        context=context,
        definitions=(ok, invalid),
        requested_domains=(DomainId("health"),),
        request_permissions=("read",),
    )
    applied = [
        d
        for d in resolution.decisions
        if d.code == DomainResourceDecisionCode.SOURCE_PRIORITY_APPLIED
    ]
    assert not applied


def test_source_priority_not_recorded_when_second_candidate_validation_blocked():
    resolver = DefaultDomainResourceResolver()
    ok = _make_definition(id="def-ok", domain_id=DomainId("health"))
    blocking_rule = DomainResourceValidationRule(
        id="rule-blocking",
        field="source_type",
        operator="equals",
        expected="device",
        severity="blocking",
        message="source type must be device",
    )
    blocked = _make_definition(
        id="def-blocked",
        domain_id=DomainId("health"),
        validation_rules=(blocking_rule,),
    )
    context = _make_context(source_type="human")
    resolution = resolver.resolve(
        context=context,
        definitions=(ok, blocked),
        requested_domains=(DomainId("health"),),
        request_permissions=("read",),
    )
    applied = [
        d
        for d in resolution.decisions
        if d.code == DomainResourceDecisionCode.SOURCE_PRIORITY_APPLIED
    ]
    assert not applied


def test_source_priority_recorded_for_two_accepted_same_domain_bindings():
    resolver = DefaultDomainResourceResolver()
    definition_a = _make_definition(id="def-a", domain_id=DomainId("health"))
    definition_b = _make_definition(id="def-b", domain_id=DomainId("health"))
    context = _make_context()
    resolution = resolver.resolve(
        context=context,
        definitions=(definition_a, definition_b),
        requested_domains=(DomainId("health"),),
        request_permissions=("read",),
    )
    applied = [
        d
        for d in resolution.decisions
        if d.code == DomainResourceDecisionCode.SOURCE_PRIORITY_APPLIED
    ]
    assert len(applied) == 1
    assert applied[0].domain_id == DomainId("health")


# ── Final defect fixes: resolver input validation (Section 5) ──────────────


def test_duplicate_requested_domains_rejected():
    resolver = DefaultDomainResourceResolver()
    definition = _make_definition()
    context = _make_context()
    with pytest.raises(DomainResourceResolutionError):
        resolver.resolve(
            context=context,
            definitions=(definition,),
            requested_domains=(DomainId("health"), DomainId("health")),
            request_permissions=("read",),
        )


def test_non_domain_requested_value_rejected():
    resolver = DefaultDomainResourceResolver()
    definition = _make_definition()
    context = _make_context()
    with pytest.raises(DomainResourceResolutionError):
        resolver.resolve(
            context=context,
            definitions=(definition,),
            requested_domains=("health",),
            request_permissions=("read",),
        )


def test_non_tuple_definitions_rejected():
    resolver = DefaultDomainResourceResolver()
    definition = _make_definition()
    context = _make_context()
    with pytest.raises(DomainResourceResolutionError):
        resolver.resolve(
            context=context,
            definitions=[definition],
            requested_domains=(DomainId("health"),),
            request_permissions=("read",),
        )


def test_duplicate_request_permissions_rejected():
    resolver = DefaultDomainResourceResolver()
    definition = _make_definition()
    context = _make_context()
    with pytest.raises(DomainResourceResolutionError):
        resolver.resolve(
            context=context,
            definitions=(definition,),
            requested_domains=(DomainId("health"),),
            request_permissions=("read", "read"),
        )


def test_empty_deny_permission_rejected():
    resolver = DefaultDomainResourceResolver()
    definition = _make_definition()
    context = _make_context()
    with pytest.raises(DomainResourceResolutionError):
        resolver.resolve(
            context=context,
            definitions=(definition,),
            requested_domains=(DomainId("health"),),
            request_permissions=("read", "deny:"),
        )
