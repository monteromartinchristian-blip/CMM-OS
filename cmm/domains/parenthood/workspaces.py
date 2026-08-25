"""Phase 10.27 — Parenthood Workspaces and Functional Scope Isolation.

Contracts and helpers for managing:
1. Functional scopes: ``parenthood.journey`` and isolated ``parenthood.child:<child_id>``.
2. Isolated child parenting workspaces with stable internal identities.
3. Sibling identity isolation (no cross-sibling record contamination).
4. Selective, provenance-preserving journey-to-child context transfer.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime, timezone
from types import MappingProxyType
from typing import Any, Literal

PARENTHOOD_DOMAIN_ID = "domain:parenthood"

ALLOWED_TRANSFER_CATEGORIES: frozenset[str] = frozenset(
    {
        "identity_civil_documentation",
        "birth_information",
        "medical_history",
        "health_summary",
        "genetic_family_history",
        "milestone",
        "family_context",
        "parenting_decision",
    }
)


@dataclass(frozen=True, slots=True)
class ParenthoodScope:
    """Represents a functional scope in the Parenthood domain."""

    kind: Literal["journey", "child"]
    child_id: str | None = None

    @property
    def scope_id(self) -> str:
        if self.kind == "journey":
            return "parenthood.journey"
        return f"parenthood.child:{self.child_id}"


def parse_parenthood_scope(scope_str: str) -> ParenthoodScope:
    """Parse a functional scope string into a ``ParenthoodScope``."""
    if not isinstance(scope_str, str):
        raise ValueError(f"Scope must be a string, got {type(scope_str)}")

    if scope_str == "parenthood.journey":
        return ParenthoodScope(kind="journey", child_id=None)

    if scope_str.startswith("parenthood.child:"):
        child_id = scope_str.split(":", 1)[1].strip()
        if not child_id:
            raise ValueError("Child ID cannot be empty in parenthood.child:<child_id>")
        return ParenthoodScope(kind="child", child_id=child_id)

    raise ValueError(f"Invalid parenthood scope: '{scope_str}'")


@dataclass(frozen=True, slots=True)
class ChildParentingWorkspace:
    """Represents an isolated child workspace under ``domain:parenthood``."""

    id: str
    domain_id: str
    display_name: str
    status: str
    developmental_stage: str | None
    created_at: datetime
    metadata: MappingProxyType[str, Any] = field(
        default_factory=lambda: MappingProxyType({})
    )


def build_child_workspace(
    *,
    id: str,
    display_name: str,
    domain_id: str = PARENTHOOD_DOMAIN_ID,
    status: str = "active",
    developmental_stage: str | None = None,
    created_at: datetime | None = None,
    metadata: Mapping[str, Any] | None = None,
) -> ChildParentingWorkspace:
    """Build a ``ChildParentingWorkspace`` deterministically."""
    if not id or not isinstance(id, str):
        raise ValueError("Child workspace id must be a non-empty string")
    if not display_name or not isinstance(display_name, str):
        raise ValueError("Child display name must be a non-empty string")

    return ChildParentingWorkspace(
        id=id,
        domain_id=domain_id,
        display_name=display_name,
        status=status,
        developmental_stage=developmental_stage,
        created_at=created_at or datetime.now(timezone.utc),
        metadata=MappingProxyType(dict(metadata or {})),
    )


def validate_child_workspace(workspace: ChildParentingWorkspace) -> bool:
    """Validate workspace invariants."""
    if not isinstance(workspace, ChildParentingWorkspace):
        return False
    if not workspace.id or not workspace.display_name:
        return False
    if workspace.domain_id != PARENTHOOD_DOMAIN_ID:
        return False
    return True


def ensure_sibling_identity_isolation(
    *,
    target_workspace: ChildParentingWorkspace,
    record: Mapping[str, Any],
) -> dict[str, Any]:
    """Ensure a record accessed in a child workspace belongs to that child or is shared."""
    is_shared = record.get("is_shared_family_context", False)
    record_child_id = record.get("child_id")

    if is_shared:
        return {
            "isolated": True,
            "access_allowed": True,
            "reason": "explicit_shared_family_context",
        }

    if record_child_id == target_workspace.id:
        return {
            "isolated": True,
            "access_allowed": True,
            "reason": "child_identity_match",
        }

    return {
        "isolated": True,
        "access_allowed": False,
        "reason": "sibling_identity_mismatch",
        "target_child_id": target_workspace.id,
        "record_child_id": record_child_id,
    }


def select_journey_transfer_candidates(
    *,
    journey_context: Mapping[str, Any],
    selected_keys: Sequence[str] | None = None,
    target_child_id: str | None = None,
    allow_bulk_transfer: bool = False,
) -> tuple[dict[str, Any], ...]:
    """Select and transform journey context for transfer into a child workspace.

    Bulk copy is strictly prohibited; explicit selection is required.
    """
    if allow_bulk_transfer or selected_keys is None:
        raise ValueError("bulk copy prohibited: explicit candidate selection required")

    candidates: list[dict[str, Any]] = []
    now_iso = datetime.now(timezone.utc).isoformat()

    for key in selected_keys:
        if key not in journey_context:
            continue
        data = journey_context[key]
        category = data.get("category", "general_context")
        item = {
            "key": key,
            "source_scope": "parenthood.journey",
            "target_child_id": target_child_id,
            "transferred_at": now_iso,
            "category": category,
            "data": dict(data),
            "provenance": {
                "origin_domain": PARENTHOOD_DOMAIN_ID,
                "origin_scope": "parenthood.journey",
                "transfer_approved": True,
                "transfer_timestamp": now_iso,
            },
        }
        candidates.append(item)

    return tuple(candidates)


__all__ = [
    "ALLOWED_TRANSFER_CATEGORIES",
    "ChildParentingWorkspace",
    "PARENTHOOD_DOMAIN_ID",
    "ParenthoodScope",
    "build_child_workspace",
    "ensure_sibling_identity_isolation",
    "parse_parenthood_scope",
    "select_journey_transfer_candidates",
    "validate_child_workspace",
]
