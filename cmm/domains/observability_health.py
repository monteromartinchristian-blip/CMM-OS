"""Phase 10.37 — Read-only Domain health checker.

Produces per-domain ``DomainHealthResult`` entirely from existing canonical
registries and validation evidence. Health checks are observations, never
remediation: no install/load/reload/enable/disable/repair, no operation or
workflow execution, no session creation and no persistence.

Every boolean means "positively verified by canonical evidence", never "the
check merely did not raise an exception".
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime

from cmm.cognitive.reasoning_rule_registry import InMemoryReasoningRuleRegistry
from cmm.domains.enums import DomainValidationStatus
from cmm.domains.observability_contracts import (
    DomainHealthFinding,
    DomainHealthResult,
    DomainHealthStatus,
)
from cmm.domains.operation_registry import InMemoryDomainOperationRegistry
from cmm.domains.permission_registry import DomainPermissionRegistry
from cmm.domains.registry import DomainRegistry
from cmm.domains.resource_registry import InMemoryDomainResourceRegistry
from cmm.domains.validation_contracts import DomainValidationResult
from cmm.domains.workflow_registry import InMemoryDomainWorkflowRegistry

# Stable finding codes.
_REGISTRY_MISSING = "DOMAIN_HEALTH_REGISTRY_RECORD_MISSING"
_REGISTRY_CONTRADICTORY = "DOMAIN_HEALTH_REGISTRY_CONTRADICTORY"
_MANIFEST_UNVERIFIED = "DOMAIN_HEALTH_MANIFEST_UNVERIFIED"
_RESOURCES_UNRESOLVED = "DOMAIN_HEALTH_RESOURCES_UNRESOLVED"
_RULES_UNRESOLVED = "DOMAIN_HEALTH_RULES_UNRESOLVED"
_OPERATIONS_UNRESOLVED = "DOMAIN_HEALTH_OPERATIONS_UNRESOLVED"
_WORKFLOWS_UNRESOLVED = "DOMAIN_HEALTH_WORKFLOWS_UNRESOLVED"
_PERMISSION_POLICY_UNVERIFIED = "DOMAIN_HEALTH_PERMISSION_POLICY_UNVERIFIED"
_REQUIRED_DEPENDENCY_MISSING = "DOMAIN_HEALTH_REQUIRED_DEPENDENCY_MISSING"


class DomainHealthChecker:
    """Read-only per-domain health observer bound to canonical registries."""

    def __init__(
        self,
        *,
        domain_registry: DomainRegistry,
        resource_registry: InMemoryDomainResourceRegistry,
        rule_registry: InMemoryReasoningRuleRegistry,
        operation_registry: InMemoryDomainOperationRegistry,
        workflow_registry: InMemoryDomainWorkflowRegistry,
        permission_registry: DomainPermissionRegistry,
        manifest_validation_lookup: Callable[[str], object | None],
        clock: Callable[[], datetime],
    ) -> None:
        self._domain_registry = domain_registry
        self._resource_registry = resource_registry
        self._rule_registry = rule_registry
        self._operation_registry = operation_registry
        self._workflow_registry = workflow_registry
        self._permission_registry = permission_registry
        self._manifest_validation_lookup = manifest_validation_lookup
        self._clock = clock

    def check(self, domain_id: str) -> DomainHealthResult:
        """Evaluate read-only health for one canonical Domain ID."""
        checked_at = self._clock()

        definition = self._domain_registry.get(domain_id)
        if definition is None:
            return DomainHealthResult(
                domain_id=domain_id,
                status=DomainHealthStatus.UNKNOWN,
                manifest=False,
                registry=False,
                resources=False,
                rules=False,
                operations=False,
                workflows=False,
                permissions=False,
                dependencies=False,
                last_checked_at=checked_at,
                findings=(
                    DomainHealthFinding(
                        code=_REGISTRY_MISSING,
                        component="registry",
                        severity="critical",
                        message=(
                            "Domain registry record is missing; the domain "
                            "cannot be evaluated without inventing state"
                        ),
                        reference_ids=(domain_id,),
                        blocking=True,
                    ),
                ),
            )

        findings: list[DomainHealthFinding] = []
        dimensions: dict[str, bool] = {
            "manifest": False,
            "registry": False,
            "resources": False,
            "rules": False,
            "operations": False,
            "workflows": False,
            "permissions": False,
            "dependencies": False,
        }
        blocking = False

        # registry
        record = self._domain_registry.get_record(domain_id)
        if record is None:
            findings.append(
                DomainHealthFinding(
                    code=_REGISTRY_CONTRADICTORY,
                    component="registry",
                    severity="critical",
                    message="Registry resolve succeeded but record lookup failed",
                    reference_ids=(domain_id,),
                    blocking=True,
                )
            )
            blocking = True
        else:
            dimensions["registry"] = True

        # manifest
        validation = self._manifest_validation_lookup(domain_id)
        current_version = getattr(definition, "version", None)
        if (
            validation is not None
            and isinstance(validation, DomainValidationResult)
            and validation.status is DomainValidationStatus.PASSED
            and getattr(validation, "domain_id", None) == domain_id
            and getattr(validation, "version", None) == current_version
        ):
            dimensions["manifest"] = True
        else:
            if validation is None:
                findings.append(
                    DomainHealthFinding(
                        code=_MANIFEST_UNVERIFIED,
                        component="manifest",
                        severity="warning",
                        message=(
                            "Canonical manifest/validation evidence is not "
                            "available; manifest could not be positively verified"
                        ),
                        reference_ids=(domain_id,),
                        blocking=False,
                    )
                )
            else:
                findings.append(
                    DomainHealthFinding(
                        code=_MANIFEST_UNVERIFIED,
                        component="manifest",
                        severity="warning",
                        message=(
                            "Canonical manifest validation did not positively "
                            "bind the current registered Domain definition; "
                            "manifest could not be positively verified"
                        ),
                        reference_ids=(domain_id,),
                        blocking=False,
                    )
                )

        # resources
        resource_ids = definition.resources
        unresolved_resources: list[str] = []
        for resource_id in resource_ids:
            if self._resource_registry.get(resource_id) is None:
                unresolved_resources.append(resource_id)
        if unresolved_resources:
            findings.append(
                DomainHealthFinding(
                    code=_RESOURCES_UNRESOLVED,
                    component="resources",
                    severity="warning",
                    message=("Declared resource IDs could not be positively resolved"),
                    reference_ids=tuple(sorted(unresolved_resources)),
                    blocking=False,
                )
            )
        else:
            dimensions["resources"] = True

        # rules
        rule_ids = definition.rules
        unresolved_rules: list[str] = []
        for rule_id in rule_ids:
            if self._rule_registry.resolve(rule_id) is None:
                unresolved_rules.append(rule_id)
        if unresolved_rules:
            findings.append(
                DomainHealthFinding(
                    code=_RULES_UNRESOLVED,
                    component="rules",
                    severity="warning",
                    message="Declared required rules could not be positively resolved",
                    reference_ids=tuple(sorted(unresolved_rules)),
                    blocking=False,
                )
            )
        else:
            dimensions["rules"] = True

        # operations (structural registration only; availability is execution)
        operation_ids = definition.operations
        registered_operations = {
            item.operation_id for item in self._operation_registry.list_definitions()
        }
        unresolved_operations = [
            operation_id
            for operation_id in operation_ids
            if operation_id not in registered_operations
        ]
        if unresolved_operations:
            findings.append(
                DomainHealthFinding(
                    code=_OPERATIONS_UNRESOLVED,
                    component="operations",
                    severity="warning",
                    message=(
                        "Declared operation contracts could not be positively "
                        "resolved from the canonical operation registry"
                    ),
                    reference_ids=tuple(sorted(unresolved_operations)),
                    blocking=False,
                )
            )
        else:
            dimensions["operations"] = True

        # workflows (structural registration only; never executed)
        workflow_ids = definition.workflows
        registered_workflows = {
            item.workflow_id
            for item in self._workflow_registry.list_for_domain(domain_id)
        }
        unresolved_workflows = [
            workflow_id
            for workflow_id in workflow_ids
            if workflow_id not in registered_workflows
        ]
        if unresolved_workflows:
            findings.append(
                DomainHealthFinding(
                    code=_WORKFLOWS_UNRESOLVED,
                    component="workflows",
                    severity="warning",
                    message=(
                        "Declared workflow contracts could not be positively "
                        "resolved from the canonical workflow registry"
                    ),
                    reference_ids=tuple(sorted(unresolved_workflows)),
                    blocking=False,
                )
            )
        else:
            dimensions["workflows"] = True

        # permissions (structural policy availability, not user authorization)
        permission_ids = definition.permissions
        if permission_ids:
            try:
                resolved_permissions = tuple(
                    self._permission_registry.get(policy_id)
                    for policy_id in permission_ids
                )
                dimensions["permissions"] = all(
                    permission is not None for permission in resolved_permissions
                )
            except Exception:  # noqa: BLE001 -- structural read boundary
                dimensions["permissions"] = False
            if not dimensions["permissions"]:
                findings.append(
                    DomainHealthFinding(
                        code=_PERMISSION_POLICY_UNVERIFIED,
                        component="permissions",
                        severity="warning",
                        message=(
                            "Permission policy could not be positively "
                            "resolved from the canonical permission registry"
                        ),
                        reference_ids=tuple(sorted(permission_ids)),
                        blocking=False,
                    )
                )
        else:
            dimensions["permissions"] = True

        # dependencies
        required = [
            dependency for dependency in definition.dependencies if dependency.required
        ]
        missing_required = [
            str(dependency.domain_id)
            for dependency in required
            if self._domain_registry.get(str(dependency.domain_id)) is None
        ]
        optional = [
            dependency
            for dependency in definition.dependencies
            if not dependency.required
        ]
        optional_missing = [
            str(dependency.domain_id)
            for dependency in optional
            if self._domain_registry.get(str(dependency.domain_id)) is None
        ]
        also_optional = [
            str(dependency.domain_id)
            for dependency in definition.optional_dependencies
            if self._domain_registry.get(str(dependency.domain_id)) is None
        ]
        if missing_required:
            dimensions["dependencies"] = False
            blocking = True
            findings.append(
                DomainHealthFinding(
                    code=_REQUIRED_DEPENDENCY_MISSING,
                    component="dependencies",
                    severity="critical",
                    message="Required domain dependencies are missing from the registry",
                    reference_ids=tuple(sorted(set(missing_required))),
                    blocking=True,
                )
            )
        else:
            dimensions["dependencies"] = True
        # Optional dependency absence may only produce a warning, never a
        # fabricated required-dependency claim.
        optional_missing_all = tuple(sorted({*optional_missing, *also_optional}))
        if optional_missing_all and not missing_required:
            findings.append(
                DomainHealthFinding(
                    code="DOMAIN_HEALTH_OPTIONAL_DEPENDENCY_MISSING",
                    component="dependencies",
                    severity="info",
                    message="Optional domain dependencies are absent",
                    reference_ids=optional_missing_all,
                    blocking=False,
                )
            )

        # Status semantics: healthy requires every dimension positively
        # verified and no blocking finding; unhealthy when a blocking
        # prerequisite fails; otherwise degraded (usable but not fully
        # verified); unknown only when the domain itself is missing.
        if not blocking and all(dimensions.values()):
            status = DomainHealthStatus.HEALTHY
        elif blocking:
            status = DomainHealthStatus.UNHEALTHY
        else:
            status = DomainHealthStatus.DEGRADED

        return DomainHealthResult(
            domain_id=domain_id,
            status=status,
            manifest=dimensions["manifest"],
            registry=dimensions["registry"],
            resources=dimensions["resources"],
            rules=dimensions["rules"],
            operations=dimensions["operations"],
            workflows=dimensions["workflows"],
            permissions=dimensions["permissions"],
            dependencies=dimensions["dependencies"],
            last_checked_at=checked_at,
            findings=tuple(sorted(findings, key=lambda finding: finding.code)),
        )


__all__ = ["DomainHealthChecker"]
