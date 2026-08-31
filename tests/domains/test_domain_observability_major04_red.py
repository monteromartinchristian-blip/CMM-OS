"""Phase 10.37 — MAJOR-04 RED regressions: health validation must bind current
Domain version.

Audit defect: the health checker accepts manifest validation based only on a
PASS-like status. It must positively bind the validation to the currently
registered Domain definition:

- matching domain ID + matching current version + PASS → manifest=True
- wrong domain ID + PASS → manifest=False → non-healthy
- same domain ID + stale version + PASS → manifest=False → non-healthy
- same domain/current version + non-PASS → manifest=False
- missing validation → manifest=False → degraded/unverified
"""

from __future__ import annotations

from datetime import datetime, timezone

from cmm.domains.enums import DomainValidationStatus
from cmm.domains.health.bootstrap import (
    build_standard_health_domain_bootstrap,
)
from cmm.domains.observability_contracts import DomainHealthStatus
from cmm.domains.observability_health import DomainHealthChecker
from cmm.domains.validation_contracts import DomainValidationResult

NOW = datetime(2026, 8, 31, 12, 0, 0, tzinfo=timezone.utc)

HEALTH_DOMAIN_ID = "domain:health"
CURRENT_VERSION = "1.0.0"


def _validated_manifest(
    domain_id: str,
    *,
    version: str = CURRENT_VERSION,
    status: DomainValidationStatus = DomainValidationStatus.PASSED,
) -> DomainValidationResult:
    return DomainValidationResult(
        domain_id=domain_id,
        version=version,
        status=status,
        manifest_valid=True,
        compatibility_valid=True,
        dependencies_valid=True,
        contracts_valid=True,
        permissions_valid=True,
        operations_valid=True,
        workflows_valid=True,
        security_valid=True,
        fragmentation_valid=True,
        tests_valid=True,
        validated_at=NOW,
    )


def _checker_with_lookup(lookup) -> DomainHealthChecker:
    bootstrap = build_standard_health_domain_bootstrap()
    return DomainHealthChecker(
        domain_registry=bootstrap.domain_registry,
        resource_registry=bootstrap.resource_registry,
        rule_registry=bootstrap.rule_registry,
        operation_registry=bootstrap.operation_registry,
        workflow_registry=bootstrap.workflow_registry,
        permission_registry=bootstrap.permission_registry,
        manifest_validation_lookup=lookup,
        clock=lambda: NOW,
    )


def test_matching_domain_and_version_passes() -> None:
    """matching domain ID + current version + PASS → manifest=True."""
    valid = _validated_manifest(HEALTH_DOMAIN_ID)
    checker = _checker_with_lookup(lambda domain_id: valid)

    result = checker.check(HEALTH_DOMAIN_ID)

    assert result.manifest is True


def test_wrong_domain_id_with_pass_is_not_healthy() -> None:
    """wrong domain ID + PASS → manifest=False."""
    wrong_domain = _validated_manifest("domain:some-other")
    checker = _checker_with_lookup(lambda domain_id: wrong_domain)

    result = checker.check(HEALTH_DOMAIN_ID)

    assert result.manifest is False
    assert result.status is not DomainHealthStatus.HEALTHY


def test_stale_version_with_pass_is_not_healthy() -> None:
    """same domain + stale version + PASS → manifest=False."""
    stale = _validated_manifest(HEALTH_DOMAIN_ID, version="0.9.0")
    checker = _checker_with_lookup(lambda domain_id: stale)

    result = checker.check(HEALTH_DOMAIN_ID)

    assert result.manifest is False
    assert result.status is not DomainHealthStatus.HEALTHY


def test_non_pass_status_is_not_manifest() -> None:
    """same domain/current version + non-PASS → manifest=False."""
    failed = _validated_manifest(HEALTH_DOMAIN_ID, status=DomainValidationStatus.FAILED)
    checker = _checker_with_lookup(lambda domain_id: failed)

    result = checker.check(HEALTH_DOMAIN_ID)

    assert result.manifest is False


def test_missing_validation_is_degraded() -> None:
    """missing validation → manifest=False → degraded/unverified."""
    checker = _checker_with_lookup(lambda domain_id: None)

    result = checker.check(HEALTH_DOMAIN_ID)

    assert result.manifest is False
    assert result.status is DomainHealthStatus.DEGRADED
