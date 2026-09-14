"""Tests for Phase 10.10 – Domain Resource public API exports (Task 11)."""

from __future__ import annotations

import cmm.domains


def test_resource_contracts_exported():
    for name in (
        "DomainResourceBinding",
        "DomainResourceChecksum",
        "DomainResourceContext",
        "DomainResourceDecision",
        "DomainResourceDefinition",
        "DomainResourceDerivation",
        "DomainResourceRejection",
        "DomainResourceResolution",
        "DomainResourceTemporalPolicy",
        "DomainResourceValidationResult",
        "DomainResourceValidationRule",
    ):
        assert hasattr(cmm.domains, name), f"Missing symbol: {name}"


def test_domain_resource_validation_result_is_the_resource_contracts_class():
    from cmm.domains import DomainResourceValidationResult
    from cmm.domains.resource_contracts import (
        DomainResourceValidationResult as ContractResult,
    )

    assert DomainResourceValidationResult is ContractResult


def test_resource_enums_exported():
    for name in (
        "DomainResourceResolutionStatus",
        "DomainResourceDecisionCode",
        "DomainResourceValidationSeverity",
        "DomainResourceValidationOperator",
    ):
        assert hasattr(cmm.domains, name), f"Missing symbol: {name}"


def test_resource_errors_exported():
    for name in (
        "DomainResourceError",
        "DomainResourceContractError",
        "DomainResourceSerializationError",
        "DomainResourceConfigurationError",
        "DomainResourceRegistryError",
        "DomainResourceResolutionError",
        "DomainResourceDerivationError",
    ):
        assert hasattr(cmm.domains, name), f"Missing symbol: {name}"


def test_resource_registry_and_resolver_exported():
    for name in (
        "DomainResourceRegistry",
        "InMemoryDomainResourceRegistry",
        "DomainResourceValidator",
        "DefaultDomainResourceValidator",
        "DomainResourceResolver",
        "DefaultDomainResourceResolver",
        "DomainResourceDerivationService",
    ):
        assert hasattr(cmm.domains, name), f"Missing symbol: {name}"


def test_no_internal_resource_helpers_exported():
    forbidden = {
        "_coerce_sensitivity",
        "_coerce_resolution_status",
        "_coerce_decision_code",
        "_coerce_validation_severity",
        "_coerce_validation_operator",
        "_dedup_provenance",
        "_evaluate_temporal_policy",
        "_evaluate_operator",
        "_lookup_field",
        "_intersect_permissions",
        "_has_explicit_deny",
        "_order_by_source_priority",
        "_max_sensitivity",
        "_SENSITIVITY_RANK",
        "_validate_temporal_scope",
        "_temporal_scope_to_dict",
        "_temporal_scope_from_dict",
    }
    assert forbidden.isdisjoint(set(cmm.domains.__all__))


def test_prior_phase_10_apis_remain_stable():
    for name in (
        "DomainId",
        "DomainStatus",
        "DomainKind",
        "DomainResolver",
        "DefaultDomainResolver",
        "DomainComposer",
        "DefaultDomainComposer",
        "CrossDomainEngine",
        "DefaultCrossDomainEngine",
    ):
        assert hasattr(cmm.domains, name), f"Missing symbol: {name}"
