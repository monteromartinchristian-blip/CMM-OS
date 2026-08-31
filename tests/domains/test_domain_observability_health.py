"""Phase 10.37 — Read-only Domain health checker tests.

Proves positive-verification health semantics: every boolean means verified by
canonical evidence, missing registry records are blocking, broken required
dependencies make a domain non-healthy, optional unavailable operations stay
structurally healthy, and health checks never mutate state.
"""

from __future__ import annotations

from datetime import datetime, timezone

from cmm.domains.contracts import DomainDefinition, DomainDependency, DomainId
from cmm.domains.enums import DomainValidationStatus
from cmm.domains.health.bootstrap import (
    build_standard_health_domain_bootstrap,
)
from cmm.domains.observability_contracts import DomainHealthStatus
from cmm.domains.observability_health import DomainHealthChecker
from cmm.domains.validation_contracts import (
    DomainValidationResult,
)

NOW = datetime(2026, 8, 31, 12, 0, 0, tzinfo=timezone.utc)

HEALTH_DOMAIN_ID = "domain:health"
GENERAL_DOMAIN_ID = "domain:general"


def _validated_manifest(domain_id: str) -> DomainValidationResult:
    return DomainValidationResult(
        domain_id=domain_id,
        version="1.0.0",
        status=DomainValidationStatus.PASSED,
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


VALIDATED_LOOKUP = {
    HEALTH_DOMAIN_ID: _validated_manifest(HEALTH_DOMAIN_ID),
    GENERAL_DOMAIN_ID: _validated_manifest(GENERAL_DOMAIN_ID),
}


def _checker_for(
    bootstrap,
    *,
    manifest_lookup=None,
    clock=None,
) -> DomainHealthChecker:
    """Build a checker wired to the standard canonical registries."""
    return DomainHealthChecker(
        domain_registry=bootstrap.domain_registry,
        resource_registry=bootstrap.resource_registry,
        rule_registry=bootstrap.rule_registry,
        operation_registry=bootstrap.operation_registry,
        workflow_registry=bootstrap.workflow_registry,
        permission_registry=bootstrap.permission_registry,
        manifest_validation_lookup=manifest_lookup
        or (lambda domain_id: VALIDATED_LOOKUP.get(domain_id)),
        clock=clock or (lambda: NOW),
    )


def test_healthy_registered_domain_verifies_all_dimensions() -> None:
    bootstrap = build_standard_health_domain_bootstrap()

    checker = _checker_for(bootstrap)
    result = checker.check(HEALTH_DOMAIN_ID)

    assert result.domain_id == HEALTH_DOMAIN_ID
    assert result.status is DomainHealthStatus.HEALTHY
    assert result.manifest is True
    assert result.registry is True
    assert result.resources is True
    assert result.rules is True
    assert result.operations is True
    assert result.workflows is True
    assert result.permissions is True
    assert result.dependencies is True
    assert result.findings == ()


def test_missing_registry_record_is_blocking() -> None:
    bootstrap = build_standard_health_domain_bootstrap()

    checker = _checker_for(bootstrap)
    result = checker.check("domain:does-not-exist")

    assert result.registry is False
    assert result.status is not DomainHealthStatus.HEALTHY
    assert any(
        finding.blocking and finding.component == "registry"
        for finding in result.findings
    )


def _definition_with_dependencies(
    *,
    domain_id: str,
    required_dependencies: tuple[str, ...] = (),
    optional_dependencies: tuple[str, ...] = (),
) -> DomainDefinition:
    slug = domain_id.removeprefix("domain:")
    return DomainDefinition(
        id=DomainId.from_str(domain_id),
        name=slug,
        display_name=slug.title(),
        version="1.0.0",
        kind="system",
        description=f"Description of {domain_id}",
        manifest_id=f"manifest:{slug}:1.0.0",
        dependencies=tuple(
            DomainDependency(domain_id=DomainId.from_str(dep), required=True)
            for dep in required_dependencies
        ),
        optional_dependencies=tuple(
            DomainDependency(domain_id=DomainId.from_str(dep), required=False)
            for dep in optional_dependencies
        ),
    )


def test_broken_required_dependency_is_blocking() -> None:
    bootstrap = build_standard_health_domain_bootstrap()
    # Register a domain whose required dependency is missing from the registry.
    definition = _definition_with_dependencies(
        domain_id="domain:missing-dep-test",
        required_dependencies=("domain:not-registered",),
    )
    bootstrap.domain_registry.register(definition)

    checker = _checker_for(bootstrap)
    result = checker.check("domain:missing-dep-test")

    assert result.dependencies is False
    assert result.status is DomainHealthStatus.UNHEALTHY
    assert any(
        finding.blocking and finding.component == "dependencies"
        for finding in result.findings
    )


def test_unavailable_optional_dependency_does_not_falsely_block() -> None:
    bootstrap = build_standard_health_domain_bootstrap()
    definition = _definition_with_dependencies(
        domain_id="domain:opt-dep-test",
        optional_dependencies=("domain:not-registered",),
    )
    bootstrap.domain_registry.register(definition)

    checker = _checker_for(bootstrap)
    result = checker.check("domain:opt-dep-test")

    # Optional dependency absence must not be promoted to required → non-blocking.
    assert result.status is not DomainHealthStatus.UNHEALTHY


def test_intentionally_unavailable_operation_stays_structurally_healthy() -> None:
    bootstrap = build_standard_health_domain_bootstrap()

    checker = _checker_for(bootstrap)
    result = checker.check(GENERAL_DOMAIN_ID)

    # General domain is registered and structurally consistent.
    assert result.operations is True


def test_missing_manifest_evidence_is_degraded_not_healthy() -> None:
    bootstrap = build_standard_health_domain_bootstrap()

    checker = _checker_for(
        bootstrap,
        manifest_lookup=lambda domain_id: None,
    )
    result = checker.check(HEALTH_DOMAIN_ID)

    assert result.manifest is False
    assert result.status is DomainHealthStatus.DEGRADED


def test_health_check_does_not_mutate_state() -> None:
    bootstrap = build_standard_health_domain_bootstrap()

    before_domain = bootstrap.domain_registry.list_records()
    before_resources = bootstrap.resource_registry.list_all()
    before_rules = tuple(r for r in bootstrap.rule_registry.list_all())
    before_workflows = bootstrap.workflow_registry.list_for_domain(HEALTH_DOMAIN_ID)

    checker = _checker_for(bootstrap)
    checker.check(HEALTH_DOMAIN_ID)
    checker.check(GENERAL_DOMAIN_ID)

    after_domain = bootstrap.domain_registry.list_records()
    after_resources = bootstrap.resource_registry.list_all()
    after_rules = tuple(r for r in bootstrap.rule_registry.list_all())
    after_workflows = bootstrap.workflow_registry.list_for_domain(HEALTH_DOMAIN_ID)

    assert after_domain == before_domain
    assert after_resources == before_resources
    assert after_rules == before_rules
    assert after_workflows == before_workflows
