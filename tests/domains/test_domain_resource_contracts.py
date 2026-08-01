"""Tests for Phase 10.10 – Domain Resource enums and error hierarchy (Task 1)."""

from __future__ import annotations

from cmm.domains.enums import (
    DomainResourceDecisionCode,
    DomainResourceResolutionStatus,
    DomainResourceValidationOperator,
    DomainResourceValidationSeverity,
)


def test_domain_resource_resolution_status_exact_values():
    assert {item.value for item in DomainResourceResolutionStatus} == {
        "resolved",
        "partial",
        "blocked",
        "rejected",
        "failed",
    }


def test_domain_resource_decision_code_exact_values():
    assert {item.value for item in DomainResourceDecisionCode} == {
        "definition_selected",
        "definition_skipped",
        "domain_not_applicable",
        "permission_denied",
        "sensitivity_restricted",
        "temporal_policy_failed",
        "validation_failed",
        "resource_shared",
        "derivation_recorded",
        "source_priority_applied",
        "reliability_applied",
    }


def test_domain_resource_validation_severity_exact_values():
    assert {item.value for item in DomainResourceValidationSeverity} == {
        "info",
        "warning",
        "error",
        "blocking",
    }


def test_domain_resource_validation_operator_exact_values():
    assert {item.value for item in DomainResourceValidationOperator} == {
        "exists",
        "equals",
        "not_equals",
        "contains",
        "in",
        "minimum",
        "maximum",
    }


def test_domain_resource_enums_are_str_enums():
    assert isinstance(DomainResourceResolutionStatus.RESOLVED, str)
    assert isinstance(DomainResourceDecisionCode.DEFINITION_SELECTED, str)
    assert isinstance(DomainResourceValidationSeverity.INFO, str)
    assert isinstance(DomainResourceValidationOperator.EXISTS, str)


def test_domain_resource_error_inheritance():
    from cmm.domains.errors import (
        DomainError,
        DomainResourceConfigurationError,
        DomainResourceContractError,
        DomainResourceDerivationError,
        DomainResourceError,
        DomainResourceRegistryError,
        DomainResourceResolutionError,
        DomainResourceSerializationError,
    )

    assert issubclass(DomainResourceError, DomainError)
    assert issubclass(DomainResourceContractError, DomainResourceError)
    assert issubclass(DomainResourceContractError, ValueError)
    assert issubclass(DomainResourceSerializationError, DomainResourceError)
    assert issubclass(DomainResourceConfigurationError, DomainResourceError)
    assert issubclass(DomainResourceRegistryError, DomainResourceError)
    assert issubclass(DomainResourceResolutionError, DomainResourceError)
    assert issubclass(DomainResourceDerivationError, DomainResourceError)


def test_domain_resource_error_codes_are_stable():
    from cmm.domains.errors import (
        DomainResourceConfigurationError,
        DomainResourceContractError,
        DomainResourceDerivationError,
        DomainResourceError,
        DomainResourceRegistryError,
        DomainResourceResolutionError,
        DomainResourceSerializationError,
    )

    assert DomainResourceError.code == "DOMAIN_RESOURCE_ERROR"
    assert DomainResourceContractError.code == "DOMAIN_RESOURCE_CONTRACT_ERROR"
    assert (
        DomainResourceSerializationError.code == "DOMAIN_RESOURCE_SERIALIZATION_ERROR"
    )
    assert (
        DomainResourceConfigurationError.code == "DOMAIN_RESOURCE_CONFIGURATION_ERROR"
    )
    assert DomainResourceRegistryError.code == "DOMAIN_RESOURCE_REGISTRY_ERROR"
    assert DomainResourceResolutionError.code == "DOMAIN_RESOURCE_RESOLUTION_ERROR"
    assert DomainResourceDerivationError.code == "DOMAIN_RESOURCE_DERIVATION_ERROR"


def test_domain_resource_error_carries_message_and_details():
    from cmm.domains.errors import DomainResourceContractError

    err = DomainResourceContractError("bad field", field="kind", details={"a": 1})
    assert err.message == "bad field"
    assert err.field == "kind"
    assert err.details["a"] == 1


# ── Task 2: Temporal policy, validation rule and checksum ──────────────────

from datetime import datetime, timezone

import pytest

from cmm.domains.errors import DomainResourceContractError
from cmm.domains.identifiers import DomainId
from cmm.domains.resource_contracts import (
    DomainResourceBinding,
    DomainResourceChecksum,
    DomainResourceContext,
    DomainResourceDecision,
    DomainResourceDefinition,
    DomainResourceDerivation,
    DomainResourceRejection,
    DomainResourceResolution,
    DomainResourceTemporalPolicy,
    DomainResourceValidationRule,
)


def test_temporal_policy_rejects_negative_validity_window():
    with pytest.raises(DomainResourceContractError):
        DomainResourceTemporalPolicy(validity_window_seconds=-1)


def test_temporal_policy_rejects_bool_as_int_validity_window():
    with pytest.raises(DomainResourceContractError):
        DomainResourceTemporalPolicy(validity_window_seconds=True)


def test_temporal_policy_rejects_non_strict_bool():
    with pytest.raises(DomainResourceContractError):
        DomainResourceTemporalPolicy(effective_date_required=1)


def test_validation_rule_rejects_unsupported_operator():
    with pytest.raises(DomainResourceContractError):
        DomainResourceValidationRule(
            id="rule-1",
            field="sensitivity",
            operator="eval",
            expected="x",
            severity="error",
            message="bad",
        )


def test_validation_rule_accepts_all_declared_operators():
    for op in (
        "exists",
        "equals",
        "not_equals",
        "contains",
        "in",
        "minimum",
        "maximum",
    ):
        rule = DomainResourceValidationRule(
            id=f"rule-{op}",
            field="sensitivity",
            operator=op,
            expected="x",
            severity="warning",
            message="check",
        )
        assert rule.operator.value == op


def test_checksum_rejects_unknown_algorithm():
    with pytest.raises(DomainResourceContractError):
        DomainResourceChecksum(algorithm="md5", value="a" * 32)


def test_checksum_rejects_wrong_length_for_algorithm():
    with pytest.raises(DomainResourceContractError):
        DomainResourceChecksum(algorithm="sha256", value="a" * 10)


def test_checksum_accepts_valid_sha256():
    checksum = DomainResourceChecksum(algorithm="sha256", value="a" * 64)
    assert checksum.algorithm == "sha256"


# ── Task 3: Definition and context contracts ────────────────────────────────


def test_definition_rejects_negative_source_priority():
    with pytest.raises(DomainResourceContractError):
        DomainResourceDefinition(
            id="def-1",
            kind="calendar-event",
            domain_id=DomainId("health"),
            adapter="health.calendar",
            source_priority=-1,
        )


def test_definition_rejects_reliability_out_of_range():
    with pytest.raises(DomainResourceContractError):
        DomainResourceDefinition(
            id="def-1",
            kind="calendar-event",
            domain_id=DomainId("health"),
            adapter="health.calendar",
            default_reliability=1.5,
        )


def test_definition_rejects_duplicate_entity_types():
    with pytest.raises(DomainResourceContractError):
        DomainResourceDefinition(
            id="def-1",
            kind="calendar-event",
            domain_id=DomainId("health"),
            adapter="health.calendar",
            entity_types=("event", "event"),
        )


def test_context_requires_provenance():
    with pytest.raises(DomainResourceContractError):
        DomainResourceContext(resource_id="res-1", kind="calendar-event", provenance=())


def test_context_is_not_payload_bearing():
    ctx = DomainResourceContext(
        resource_id="res-1", kind="calendar-event", provenance=("src-a",)
    )
    assert not hasattr(ctx, "content")
    assert not hasattr(ctx, "payload")


def test_context_applicable_domains_are_hints_only():
    ctx = DomainResourceContext(
        resource_id="res-1",
        kind="calendar-event",
        provenance=("src-a",),
        applicable_domains=(DomainId("health"), DomainId("university")),
    )
    assert ctx.applicable_domains == (DomainId("health"), DomainId("university"))


# ── Task 4: Binding, rejection, decision and resolution contracts ──────────


def test_binding_requires_provenance():
    with pytest.raises(DomainResourceContractError):
        DomainResourceBinding(
            id="bind-1",
            resource_id="res-1",
            definition_id="def-1",
            domain_id=DomainId("health"),
            adapter="health.calendar",
            provenance=(),
        )


def _make_binding(**overrides):
    defaults = {
        "id": "bind-1",
        "resource_id": "res-1",
        "definition_id": "def-1",
        "domain_id": DomainId("health"),
        "adapter": "health.calendar",
        "provenance": ("src-a",),
    }
    defaults.update(overrides)
    return DomainResourceBinding(**defaults)


def test_resolution_resolved_requires_binding():
    with pytest.raises(DomainResourceContractError):
        DomainResourceResolution(
            id="res-res-1",
            resource_id="res-1",
            status="resolved",
            trace_id="trace-1",
            resolved_at=datetime.now(timezone.utc),
            bindings=(),
        )


def test_resolution_resolved_rejects_blocking_rejection():
    binding = _make_binding()
    rejection = DomainResourceRejection(
        definition_id="def-2",
        domain_id=DomainId("university"),
        code="validation_failed",
        reason="blocked field",
        blocking=True,
    )
    with pytest.raises(DomainResourceContractError):
        DomainResourceResolution(
            id="res-res-1",
            resource_id="res-1",
            status="resolved",
            trace_id="trace-1",
            resolved_at=datetime.now(timezone.utc),
            bindings=(binding,),
            rejections=(rejection,),
        )


def test_resolution_rejected_requires_no_bindings():
    binding = _make_binding()
    with pytest.raises(DomainResourceContractError):
        DomainResourceResolution(
            id="res-res-1",
            resource_id="res-1",
            status="rejected",
            trace_id="trace-1",
            resolved_at=datetime.now(timezone.utc),
            bindings=(binding,),
        )


def test_resolution_blocked_requires_blocking_condition():
    with pytest.raises(DomainResourceContractError):
        DomainResourceResolution(
            id="res-res-1",
            resource_id="res-1",
            status="blocked",
            trace_id="trace-1",
            resolved_at=datetime.now(timezone.utc),
        )


def test_resolution_shared_domains_must_match_bindings():
    binding = _make_binding()
    with pytest.raises(DomainResourceContractError):
        DomainResourceResolution(
            id="res-res-1",
            resource_id="res-1",
            status="resolved",
            trace_id="trace-1",
            resolved_at=datetime.now(timezone.utc),
            bindings=(binding,),
            shared_domains=(DomainId("university"),),
        )


def test_decision_optional_definition_and_domain():
    decision = DomainResourceDecision(
        code="resource_shared",
        resource_id="res-1",
        reason="shared across domains",
        blocking=False,
    )
    assert decision.definition_id is None
    assert decision.domain_id is None


# ── Task 5: Derivation contract ─────────────────────────────────────────────


def test_derivation_rejects_same_source_and_derived_id():
    with pytest.raises(DomainResourceContractError):
        DomainResourceDerivation(
            id="der-1",
            source_resource_id="res-1",
            derived_resource_id="res-1",
            definition_id="def-1",
            transformation="normalize",
            actor="system",
            created_at=datetime.now(timezone.utc),
            version="1",
        )


def test_derivation_rejects_naive_datetime():
    with pytest.raises(DomainResourceContractError):
        DomainResourceDerivation(
            id="der-1",
            source_resource_id="res-1",
            derived_resource_id="res-2",
            definition_id="def-1",
            transformation="normalize",
            actor="system",
            created_at=datetime(2026, 1, 1, 0, 0, 0),  # noqa: DTZ001
            version="1",
        )


def test_derivation_rejects_empty_actor():
    with pytest.raises(DomainResourceContractError):
        DomainResourceDerivation(
            id="der-1",
            source_resource_id="res-1",
            derived_resource_id="res-2",
            definition_id="def-1",
            transformation="normalize",
            actor="   ",
            created_at=datetime.now(timezone.utc),
            version="1",
        )


def test_derivation_carries_no_payload_attribute():
    derivation = DomainResourceDerivation(
        id="der-1",
        source_resource_id="res-1",
        derived_resource_id="res-2",
        definition_id="def-1",
        transformation="normalize",
        actor="system",
        created_at=datetime.now(timezone.utc),
        version="1",
        provenance=("res-1",),
    )
    assert not hasattr(derivation, "content")
    assert not hasattr(derivation, "payload")
