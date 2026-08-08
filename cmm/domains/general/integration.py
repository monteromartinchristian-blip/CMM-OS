"""Phase 10.19 — General Domain Integration.

Provides atomic, deterministic registration of the complete General Domain
across all relevant registries.  Registration is **validation-first** and
**rollback-capable**: all inputs are validated against every registry before
the first mutation, and snapshots of every registry are captured before any
mutation.  If any registration raises after a mutation, all registries are
restored to their exact prior state via public ``restore_state()`` APIs.
"""

from __future__ import annotations

from cmm.domains.errors import DomainPermissionRegistryError
from cmm.domains.general.definition import (
    build_general_domain_definition,
)
from cmm.domains.general.operations import build_general_operation_definitions
from cmm.domains.general.permissions import build_general_permission_policy
from cmm.domains.general.profile import build_general_profile
from cmm.domains.general.resources import build_general_resource_definitions
from cmm.domains.general.rules import build_general_rules
from cmm.domains.general.workflows import build_general_workflow_definitions
from cmm.domains.operation_registry import validate_domain_operation_implementation


class GeneralDomainIntegrationResult:
    """Compact result container for a General Domain registration."""

    __slots__ = (
        "definition",
        "operations",
        "permission_policy",
        "profile",
        "resources",
        "rules",
        "workflows",
    )

    def __init__(
        self,
        *,
        definition,
        profile,
        resources,
        rules,
        operations,
        workflows,
        permission_policy,
    ) -> None:
        self.definition = definition
        self.profile = profile
        self.resources = resources
        self.rules = rules
        self.operations = operations
        self.workflows = workflows
        self.permission_policy = permission_policy


def _validate_operation_implementations(
    operations,
    operation_implementations: dict | None,
) -> None:
    """Validate that every provided implementation matches a declared operation.

    Operations without an implementation are allowed and are registered as
    **UNAVAILABLE** (fail-closed).  This is the canonical behavior: a declared
    operation that is not yet implemented must not appear available.

    Any *provided* implementation is validated against its declared
    ``DomainOperationDefinition`` using the canonical public validator.  This
    runs during ``_validate_all()``, i.e. before the first registry mutation.
    """
    implementations = operation_implementations or {}
    operations_by_id = {
        operation.operation_id: operation for operation in operations
    }
    unknown = tuple(
        operation_id
        for operation_id in implementations
        if operation_id not in operations_by_id
    )
    if unknown:
        raise ValueError(
            "Operation implementations reference undeclared operations: "
            + ", ".join(sorted(unknown))
        )
    for operation_id, implementation in implementations.items():
        validate_domain_operation_implementation(
            operations_by_id[operation_id], implementation
        )


def _validate_no_duplicate_operations(
    operation_registry,
    operations,
) -> None:
    """Validate that no operation key is already registered in the domain or
    nested common registry.

    Two layers are checked, both deterministically before the first mutation:

    - the Domain operation registry (``list_definitions()``), and
    - the nested common ``AgentOperationRegistry`` (public ``contains()``),
      which ``InMemoryDomainOperationRegistry.register()`` would reject
      otherwise after the earlier mutations.
    """
    existing_ids = {
        definition.operation_id
        for definition in operation_registry.list_definitions()
    }
    duplicates = tuple(
        operation.operation_id
        for operation in operations
        if operation.operation_id in existing_ids
    )
    if duplicates:
        from cmm.domains.errors import DomainOperationRegistryError

        raise DomainOperationRegistryError(
            "Operation already registered: " + ", ".join(sorted(duplicates)),
            details={"operation_ids": sorted(duplicates)},
        )

    # The nested common registry may hold a descriptor with the same exact
    # (operation_id, version) key without any corresponding Domain definition.
    # ``DomainOperationRegistry.register()`` would reject that key inside
    # ``common_registry.register()``; reproduce that deterministic rejection
    # here via the public API before any mutation.
    common_collisions = tuple(
        operation.operation_id
        for operation in operations
        if operation_registry.common_registry.contains(
            operation.operation_id,
            operation.version,
        )
    )
    if common_collisions:
        from cmm.domains.errors import DomainOperationRegistryError

        raise DomainOperationRegistryError(
            "Operation already registered in the common registry: "
            + ", ".join(sorted(common_collisions)),
            details={"operation_ids": sorted(common_collisions)},
        )


def _validate_no_duplicate_workflows(
    workflow_registry,
    workflows,
) -> None:
    """Validate that no workflow key is already registered in the domain or
    nested common registry.

    Two layers are checked, both deterministically before the first mutation:

    - the Domain workflow registry (``list_for_domain()``), and
    - the nested common ``InMemoryWorkflowRegistry`` (public
      ``list_definitions()``), which ``InMemoryDomainWorkflowRegistry.register()``
      would reject otherwise after the earlier mutations.
    """
    existing_ids = {
        definition.workflow_id
        for definition in workflow_registry.list_for_domain("domain:general")
    }
    duplicates = tuple(
        workflow.workflow_id
        for workflow in workflows
        if workflow.workflow_id in existing_ids
    )
    if duplicates:
        from cmm.workflows.errors import WorkflowRegistryError

        raise WorkflowRegistryError(
            "Workflow already registered: " + ", ".join(sorted(duplicates))
        )

    # The nested common registry may hold a WorkflowDefinition with the same
    # exact (workflow_id, version) key without any corresponding Domain
    # definition.  ``InMemoryDomainWorkflowRegistry.register()`` registers the
    # common definition first and would reject that key; reproduce that
    # deterministic rejection here before any mutation.
    existing_common_keys = {
        (definition.workflow_id, definition.version)
        for definition in workflow_registry.common_registry.list_definitions()
    }
    common_collisions = tuple(
        workflow.workflow_id
        for workflow in workflows
        if (workflow.workflow_id, workflow.version) in existing_common_keys
    )
    if common_collisions:
        from cmm.workflows.errors import WorkflowRegistryError

        raise WorkflowRegistryError(
            "Workflow already registered in the common registry: "
            + ", ".join(sorted(common_collisions))
        )


def _validate_all(
    *,
    definition,
    profile,
    resources,
    rules,
    operations,
    workflows,
    permission_policy,
    domain_registry,
    profile_registry,
    resource_registry,
    rule_registry,
    operation_registry,
    workflow_registry,
    permission_registry,
    operation_implementations,
) -> None:
    """Validate all inputs against every registry before any mutation."""
    if domain_registry is not None:
        existing = domain_registry.get(str(definition.id))
        if existing is not None:
            from cmm.domains.errors import DomainRegistryConflict

            raise DomainRegistryConflict(
                f"Domain {definition.id} is already registered",
                field="domain_id",
                details={"domain_id": str(definition.id)},
            )

    if profile_registry is not None:
        existing = profile_registry.get(profile.id)
        if existing is not None:
            from cmm.domains.errors import DomainProfileRegistryError

            raise DomainProfileRegistryError(
                f"Profile {profile.id!r} is already registered",
                field="id",
                details={"id": profile.id},
            )
        existing_for_domain = profile_registry.get_by_domain(profile.domain_id)
        if existing_for_domain is not None:
            from cmm.domains.errors import DomainProfileRegistryError

            raise DomainProfileRegistryError(
                f"Domain {str(profile.domain_id)!r} already has an active base profile",
                field="domain_id",
                details={
                    "domain_id": str(profile.domain_id),
                    "profile_id": profile.id,
                    "existing_profile_id": existing_for_domain.id,
                },
            )

    if resource_registry is not None:
        existing_ids = {r.id for r in resource_registry.list_all()}
        duplicates = tuple(
            resource.id for resource in resources if resource.id in existing_ids
        )
        if duplicates:
            from cmm.domains.errors import DomainResourceRegistryError

            raise DomainResourceRegistryError(
                "Resource already registered: " + ", ".join(sorted(duplicates)),
                field="id",
                details={"ids": sorted(duplicates)},
            )

    if rule_registry is not None:
        existing_rule_ids = {
            rule.definition.id for rule in rule_registry.list_all()
        }
        duplicates = tuple(
            rule.definition.id for rule in rules if rule.definition.id in existing_rule_ids
        )
        if duplicates:
            from cmm.cognitive.errors import ReasoningRuleRegistryError

            raise ReasoningRuleRegistryError(
                "Rule already registered: " + ", ".join(sorted(duplicates)),
                field="id",
                details={"ids": sorted(duplicates)},
            )

    if operation_registry is not None:
        _validate_operation_implementations(operations, operation_implementations)
        _validate_no_duplicate_operations(operation_registry, operations)

    if workflow_registry is not None:
        _validate_no_duplicate_workflows(workflow_registry, workflows)

    if permission_registry is not None:
        try:
            permission_registry.get(permission_policy.policy_id)
        except DomainPermissionRegistryError:
            # Not registered yet — safe to proceed.  Only the canonical
            # not-found error is swallowed; any other exception (a genuine
            # error raised by ``get``) propagates instead of being treated as
            # "not registered yet".
            pass
        else:
            raise DomainPermissionRegistryError(
                "Permission policy already registered",
                details={"policy_id": permission_policy.policy_id},
            )


def _capture_snapshots(
    *,
    domain_registry,
    profile_registry,
    resource_registry,
    rule_registry,
    operation_registry,
    workflow_registry,
    permission_registry,
) -> dict[str, object]:
    """Capture snapshots of all registries before the first mutation."""
    snapshots: dict[str, object] = {}
    if domain_registry is not None:
        snapshots["domain_registry"] = domain_registry.snapshot_state()
    if profile_registry is not None:
        snapshots["profile_registry"] = profile_registry.snapshot_state()
    if resource_registry is not None:
        snapshots["resource_registry"] = resource_registry.snapshot_state()
    if rule_registry is not None:
        snapshots["rule_registry"] = rule_registry.snapshot_state()
    if operation_registry is not None:
        snapshots["operation_registry"] = operation_registry.snapshot_state()
    if workflow_registry is not None:
        snapshots["workflow_registry"] = workflow_registry.snapshot_state()
    if permission_registry is not None:
        snapshots["permission_registry"] = permission_registry.snapshot_state()
    return snapshots


def _rollback(
    snapshots: dict[str, object],
    *,
    domain_registry,
    profile_registry,
    resource_registry,
    rule_registry,
    operation_registry,
    workflow_registry,
    permission_registry,
    original_error: Exception,
) -> None:
    """Restore all registries in reverse order.

    If any restore fails, raises a composite sanitized error.
    """
    rollback_errors: list[str] = []

    # Restore in reverse registration order
    if permission_registry is not None and "permission_registry" in snapshots:
        try:
            permission_registry.restore_state(snapshots["permission_registry"])
        except Exception as exc:  # noqa: BLE001 -- rollback boundary
            rollback_errors.append(f"permission_registry: {type(exc).__name__}")
    if workflow_registry is not None and "workflow_registry" in snapshots:
        try:
            workflow_registry.restore_state(snapshots["workflow_registry"])
        except Exception as exc:  # noqa: BLE001 -- rollback boundary
            rollback_errors.append(f"workflow_registry: {type(exc).__name__}")
    if operation_registry is not None and "operation_registry" in snapshots:
        try:
            operation_registry.restore_state(snapshots["operation_registry"])
        except Exception as exc:  # noqa: BLE001 -- rollback boundary
            rollback_errors.append(f"operation_registry: {type(exc).__name__}")
    if rule_registry is not None and "rule_registry" in snapshots:
        try:
            rule_registry.restore_state(snapshots["rule_registry"])
        except Exception as exc:  # noqa: BLE001 -- rollback boundary
            rollback_errors.append(f"rule_registry: {type(exc).__name__}")
    if resource_registry is not None and "resource_registry" in snapshots:
        try:
            resource_registry.restore_state(snapshots["resource_registry"])
        except Exception as exc:  # noqa: BLE001 -- rollback boundary
            rollback_errors.append(f"resource_registry: {type(exc).__name__}")
    if profile_registry is not None and "profile_registry" in snapshots:
        try:
            profile_registry.restore_state(snapshots["profile_registry"])
        except Exception as exc:  # noqa: BLE001 -- rollback boundary
            rollback_errors.append(f"profile_registry: {type(exc).__name__}")
    if domain_registry is not None and "domain_registry" in snapshots:
        try:
            domain_registry.restore_state(snapshots["domain_registry"])
        except Exception as exc:  # noqa: BLE001 -- rollback boundary
            rollback_errors.append(f"domain_registry: {type(exc).__name__}")

    if rollback_errors:
        from cmm.domains.errors import DomainError

        raise DomainError(
            "General Domain registration failed and rollback was incomplete: "
            + "; ".join(rollback_errors)
        ) from original_error


def register_general_domain(
    *,
    domain_registry=None,
    profile_registry=None,
    resource_registry=None,
    rule_registry=None,
    operation_registry=None,
    workflow_registry=None,
    permission_registry=None,
    operation_implementations: dict | None = None,
) -> GeneralDomainIntegrationResult:
    """Register the complete General Domain atomically.

    Each registry is optional; ``None`` skips that registration. Operations
    are registered as **UNAVAILABLE** (fail-closed) unless an implementation
    is provided via ``operation_implementations`` mapping
    ``operation_id -> implementation``.

    Registration is **atomic**: all inputs are validated against every
    registry *before* the first mutation, and snapshots of every registry
    are captured before any mutation.  If any registration raises after a
    mutation, all registries are restored to their exact prior state via
    public ``restore_state()`` APIs.  If a restore fails, a composite
    sanitized error is raised.

    No global mutable state is modified.
    """
    definition = build_general_domain_definition()
    profile = build_general_profile()
    resources = build_general_resource_definitions()
    rules = build_general_rules()
    operations = build_general_operation_definitions()
    workflows = build_general_workflow_definitions()
    permission_policy = build_general_permission_policy()

    # ── Phase 1: Complete validation before any mutation ────────────────────
    _validate_all(
        definition=definition,
        profile=profile,
        resources=resources,
        rules=rules,
        operations=operations,
        workflows=workflows,
        permission_policy=permission_policy,
        domain_registry=domain_registry,
        profile_registry=profile_registry,
        resource_registry=resource_registry,
        rule_registry=rule_registry,
        operation_registry=operation_registry,
        workflow_registry=workflow_registry,
        permission_registry=permission_registry,
        operation_implementations=operation_implementations,
    )

    # ── Phase 2: Capture snapshots before any mutation ──────────────────────
    snapshots = _capture_snapshots(
        domain_registry=domain_registry,
        profile_registry=profile_registry,
        resource_registry=resource_registry,
        rule_registry=rule_registry,
        operation_registry=operation_registry,
        workflow_registry=workflow_registry,
        permission_registry=permission_registry,
    )

    # ── Phase 3: Perform actual registrations ───────────────────────────────
    try:
        if domain_registry is not None:
            domain_registry.register(definition)
        if profile_registry is not None:
            profile_registry.register(profile)
        if resource_registry is not None:
            for resource in resources:
                resource_registry.register(resource)
        if rule_registry is not None:
            for rule in rules:
                rule_registry.register(rule)
        if operation_registry is not None:
            implementations = operation_implementations or {}
            for operation in operations:
                implementation = implementations.get(operation.operation_id)
                operation_registry.register(operation, implementation)
        if workflow_registry is not None:
            for workflow in workflows:
                workflow_registry.register(workflow)
        if permission_registry is not None:
            permission_registry.register(permission_policy)
    except Exception as exc:
        _rollback(
            snapshots,
            domain_registry=domain_registry,
            profile_registry=profile_registry,
            resource_registry=resource_registry,
            rule_registry=rule_registry,
            operation_registry=operation_registry,
            workflow_registry=workflow_registry,
            permission_registry=permission_registry,
            original_error=exc,
        )
        raise

    return GeneralDomainIntegrationResult(
        definition=definition,
        profile=profile,
        resources=resources,
        rules=rules,
        operations=operations,
        workflows=workflows,
        permission_policy=permission_policy,
    )


__all__ = ["GeneralDomainIntegrationResult", "register_general_domain"]