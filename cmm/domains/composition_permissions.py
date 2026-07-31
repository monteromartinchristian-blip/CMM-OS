"""Phase 10.8 – Composition Permissions.

Declarative restrictive permission composition with prefix-based parsing.
"""

from __future__ import annotations

from collections.abc import Mapping
from types import MappingProxyType
from typing import Any

from cmm.domains.composition_contracts import (
    DomainCompositionConflict,
    DomainCompositionDecision,
    DomainCompositionItem,
    DomainCompositionPolicy,
    PermissionComposition,
)
from cmm.domains.contracts import DomainDefinition
from cmm.domains.enums import DomainConflictPolicy
from cmm.domains.errors import DomainCompositionContractError
from cmm.domains.identifiers import DomainId


def compose_permissions(
    definitions: tuple[DomainDefinition, ...],
    policy: DomainCompositionPolicy,
) -> tuple[
    PermissionComposition,
    tuple[DomainCompositionDecision, ...],
    tuple[DomainCompositionConflict, ...],
]:
    """Compose permissions from ordered definitions using configured prefix rules."""
    if not definitions:
        return (
            PermissionComposition(),
            (),
            (),
        )

    # Collect permissions with classification
    required: set[str] = set()
    granted: set[str] = set()
    denied: set[str] = set()
    unresolved: set[str] = set()
    decisions: list[DomainCompositionDecision] = []
    conflicts: list[DomainCompositionConflict] = []

    # Track per-permission domain attributions
    perm_domains: dict[str, dict[str, list[str]]] = {}  # perm -> {type: [domains]}

    for defn in definitions:
        for perm_str in defn.permissions:
            domain_slug = str(defn.id)

            # Classify by prefix
            ptype, pname = _classify_permission(
                perm_str,
                policy.denied_permission_prefixes,
                policy.required_permission_prefixes,
                policy.granted_permission_prefixes,
            )

            if pname is None:
                raise DomainCompositionContractError(
                    f"Empty permission name after prefix stripping: {perm_str!r}",
                    field="permissions",
                )

            if pname not in perm_domains:
                perm_domains[pname] = {
                    "required": [],
                    "granted": [],
                    "denied": [],
                    "unresolved": [],
                }

            if ptype == "denied":
                denied.add(pname)
                perm_domains[pname]["denied"].append(domain_slug)
            elif ptype == "required":
                required.add(pname)
                perm_domains[pname]["required"].append(domain_slug)
            elif ptype == "granted":
                granted.add(pname)
                perm_domains[pname]["granted"].append(domain_slug)
            elif ptype == "unresolved":
                unresolved.add(pname)
                perm_domains[pname]["unresolved"].append(domain_slug)

    # Resolve conflicts and build effective permission set
    effective_required: set[str] = set(required)
    effective_granted: set[str] = set(granted)
    effective_denied: set[str] = set(denied)
    effective_unresolved: set[str] = set(unresolved)

    # Permissions that are both granted and denied
    granted_and_denied = granted & denied
    required_and_denied = required & denied
    granted_and_required_and_denied = granted & required & denied

    all_conflict_perms = (
        granted_and_denied | required_and_denied | granted_and_required_and_denied
    )

    for pname in sorted(all_conflict_perms):
        contributing_domains: list[str] = []
        for ptype_key in ("required", "granted", "denied"):
            contributing_domains.extend(perm_domains.get(pname, {}).get(ptype_key, []))

        domain_ids = tuple(
            DomainId.from_str(s if s.startswith("domain:") else f"domain:{s}")
            for s in sorted(set(contributing_domains))
        )

        if policy.conflict_policy == DomainConflictPolicy.BLOCK_ON_CONFLICT:
            # Unresolved blocking conflict
            conflicts.append(
                DomainCompositionConflict(
                    code="DOMAIN_COMPOSITION_CONFLICT_BLOCKED",
                    category="permissions",
                    domains=domain_ids,
                    severity="blocking",
                    message=f"Permission conflict on '{pname}' with BLOCK_ON_CONFLICT",
                    blocking=True,
                    resolved=False,
                )
            )
            # Remove from effective granted
            effective_granted.discard(pname)
            effective_required.discard(pname)
            effective_denied.add(pname)

        elif policy.conflict_policy == DomainConflictPolicy.PRIMARY_PRECEDENCE:
            # Primary declaration wins
            primary_slug = str(definitions[0].id)
            primary_declaration = None
            for ptype_key in ("required", "granted", "denied"):
                if primary_slug in perm_domains.get(pname, {}).get(ptype_key, []):
                    primary_declaration = ptype_key
                    break

            if primary_declaration is not None:
                # Primary wins
                conflicts.append(
                    DomainCompositionConflict(
                        code="DOMAIN_COMPOSITION_CONFLICT_RESOLVED",
                        category="permissions",
                        domains=domain_ids,
                        severity="warning",
                        message=f"Permission conflict on '{pname}' resolved by primary precedence",
                        blocking=False,
                        resolved=True,
                        resolution="primary_precedence",
                    )
                )
                decisions.append(
                    DomainCompositionDecision(
                        code="DOMAIN_COMPOSITION_PRIMARY_PRECEDENCE",
                        category="permissions",
                        identifier=pname,
                        action="primary_wins",
                        domains=domain_ids,
                        reason=f"Primary domain declaration ({primary_declaration}) prevails",
                    )
                )
                # Apply primary declaration
                effective_granted.discard(pname)
                effective_required.discard(pname)
                effective_denied.discard(pname)
                if primary_declaration == "denied":
                    effective_denied.add(pname)
                elif primary_declaration == "required":
                    effective_required.add(pname)
                elif primary_declaration == "granted":
                    effective_granted.add(pname)
            else:
                # Primary didn't declare: denied wins by default
                conflicts.append(
                    DomainCompositionConflict(
                        code="DOMAIN_COMPOSITION_CONFLICT_RESOLVED",
                        category="permissions",
                        domains=domain_ids,
                        severity="warning",
                        message=f"Permission conflict on '{pname}', denied by default (primary not involved)",
                        blocking=False,
                        resolved=True,
                        resolution="deny_default",
                    )
                )
                effective_granted.discard(pname)
                effective_required.discard(pname)
                effective_denied.add(pname)

        else:
            # MOST_RESTRICTIVE: denied wins
            conflicts.append(
                DomainCompositionConflict(
                    code="DOMAIN_COMPOSITION_CONFLICT_RESOLVED",
                    category="permissions",
                    domains=domain_ids,
                    severity="warning",
                    message=f"Permission conflict on '{pname}' resolved by MOST_RESTRICTIVE (deny wins)",
                    blocking=False,
                    resolved=True,
                    resolution="most_restrictive",
                )
            )
            decisions.append(
                DomainCompositionDecision(
                    code="DOMAIN_COMPOSITION_PERMISSION_DENIED",
                    category="permissions",
                    identifier=pname,
                    action="denied",
                    domains=domain_ids,
                    reason="Denied permission prevails under MOST_RESTRICTIVE",
                )
            )
            effective_granted.discard(pname)
            effective_required.discard(pname)
            effective_denied.add(pname)

    # Build provenance
    provenance_dict: dict[str, Any] = {}
    for pname in sorted(
        effective_required | effective_granted | effective_denied | effective_unresolved
    ):
        prov_entries = []
        for ptype_key in ("required", "granted", "denied", "unresolved"):
            prov_entries.extend(perm_domains.get(pname, {}).get(ptype_key, []))
        provenance_dict[pname] = sorted(set(prov_entries))

    return (
        PermissionComposition(
            required_permissions=tuple(sorted(effective_required)),
            granted_permissions=tuple(sorted(effective_granted)),
            denied_permissions=tuple(sorted(effective_denied)),
            unresolved_permissions=tuple(sorted(effective_unresolved)),
            provenance=MappingProxyType(provenance_dict),
        ),
        tuple(decisions),
        tuple(conflicts),
    )


def _classify_permission(
    perm_str: str,
    denied_prefixes: tuple[str, ...],
    required_prefixes: tuple[str, ...],
    granted_prefixes: tuple[str, ...],
) -> tuple[str, str | None]:
    """Classify a permission string.

    Returns (type, name) where type is denied/required/granted/unresolved.
    """
    for prefix in denied_prefixes:
        if perm_str.startswith(prefix):
            name = perm_str[len(prefix) :]
            if not name:
                return ("denied", None)
            return ("denied", name)

    for prefix in required_prefixes:
        if perm_str.startswith(prefix):
            name = perm_str[len(prefix) :]
            if not name:
                return ("required", None)
            return ("required", name)

    for prefix in granted_prefixes:
        if perm_str.startswith(prefix):
            name = perm_str[len(prefix) :]
            if not name:
                return ("granted", None)
            return ("granted", name)

    # No prefix recognized: treat as required opaque
    if not perm_str:
        return ("unresolved", None)
    return ("unresolved", perm_str)


def filter_operations_by_permissions(
    operations: tuple[DomainCompositionItem, ...],
    permissions: PermissionComposition,
    definitions: tuple[DomainDefinition, ...],
) -> tuple[
    tuple[DomainCompositionItem, ...],
    tuple[DomainCompositionDecision, ...],
]:
    """Filter operations based on structured operation-permission metadata.

    Only filters if explicit operation_permissions metadata exists.
    Never infers relationships from names.
    """
    if not operations or not definitions:
        return operations, ()

    effective_denied = set(permissions.denied_permissions)
    effective_granted = set(permissions.granted_permissions)

    # Build a lookup of operation -> required/denied permissions
    # from definition metadata
    op_perms: dict[str, dict[str, set[str]]] = {}
    for defn in definitions:
        meta = defn.metadata
        if meta is None:
            continue
        # Access the free-form metadata within DomainMetadata
        free_meta = meta.metadata if hasattr(meta, "metadata") else meta
        op_meta = (
            free_meta.get("operation_permissions")
            if isinstance(free_meta, Mapping)
            else None
        )
        if op_meta is None or not isinstance(op_meta, Mapping):
            continue
        for op_id, perms in op_meta.items():
            if not isinstance(op_id, str) or not isinstance(perms, Mapping):
                raise DomainCompositionContractError(
                    "operation_permissions metadata must be a dict of str -> mapping",
                    field="metadata.operation_permissions",
                )
            if op_id not in op_perms:
                op_perms[op_id] = {"required": set(), "denied": set()}
            required = perms.get("required", ())
            denied = perms.get("denied", ())
            if isinstance(required, (list, tuple)):
                for r in required:
                    if isinstance(r, str) and r:
                        op_perms[op_id]["required"].add(r)
            if isinstance(denied, (list, tuple)):
                for d in denied:
                    if isinstance(d, str) and d:
                        op_perms[op_id]["denied"].add(d)

    kept: list[DomainCompositionItem] = []
    excluded: list[DomainCompositionDecision] = []

    for op_item in operations:
        op_id = op_item.identifier
        perms = op_perms.get(op_id)

        if perms is None:
            # No explicit operation_permissions metadata: keep the operation
            kept.append(op_item)
            continue

        required_set = perms.get("required", set())
        denied_set = perms.get("denied", set())

        # Check if any required perm is missing
        # required_permissions express obligations, NOT grants
        # Only granted (allow/grant) permissions authorize
        missing_required = required_set - effective_granted
        # Check if any denied perm is active
        active_denied = denied_set & effective_denied

        if missing_required:
            excluded.append(
                DomainCompositionDecision(
                    code="DOMAIN_COMPOSITION_OPERATION_EXCLUDED",
                    category="operations",
                    identifier=op_id,
                    action="excluded",
                    domains=op_item.contributing_domains,
                    reason=f"Missing required permissions: {sorted(missing_required)}",
                )
            )
        elif active_denied:
            excluded.append(
                DomainCompositionDecision(
                    code="DOMAIN_COMPOSITION_OPERATION_EXCLUDED",
                    category="operations",
                    identifier=op_id,
                    action="excluded",
                    domains=op_item.contributing_domains,
                    reason=f"Denied permissions active: {sorted(active_denied)}",
                )
            )
        else:
            kept.append(op_item)

    return tuple(kept), tuple(excluded)


__all__ = [
    "compose_permissions",
    "filter_operations_by_permissions",
]
