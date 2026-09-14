"""Phase 10.33 — Domain Event Catalog and Namespace Helpers.

Defines the exact 23 canonical general domain events and utilities for
validating domain event names and specialized namespaces.
"""

from __future__ import annotations

import re
from typing import Final

from cmm.domains.identifiers import DomainId

# ── Canonical General Domain Events (Exact 23) ────────────────────────────────

CANONICAL_DOMAIN_EVENTS: Final[tuple[str, ...]] = (
    "domain.resolution.started",
    "domain.resolution.completed",
    "domain.resolution.ambiguous",
    "domain.composition.created",
    "domain.composition.updated",
    "domain.execution.started",
    "domain.execution.completed",
    "domain.execution.failed",
    "domain.conflict.detected",
    "domain.conflict.resolved",
    "domain.permission.requested",
    "domain.permission.denied",
    "domain.approval.requested",
    "domain.approval.received",
    "domain.memory.proposed",
    "domain.memory.updated",
    "domain.workflow.started",
    "domain.workflow.paused",
    "domain.workflow.resumed",
    "domain.workflow.completed",
    "domain.operation.started",
    "domain.operation.completed",
    "domain.operation.failed",
)

CANONICAL_DOMAIN_EVENTS_SET: Final[frozenset[str]] = frozenset(CANONICAL_DOMAIN_EVENTS)

_EVENT_NAME_RE = re.compile(r"^[a-z][a-z0-9_]*(\.[a-z0-9_]+)+$")


def get_canonical_domain_namespace(domain: DomainId | str) -> str:
    """Return the canonical event namespace for a domain.

    Hyphens in domain slugs are converted to underscores (e.g. ``life-plan`` -> ``life_plan``).
    """
    if isinstance(domain, DomainId):
        slug = domain.slug
    elif isinstance(domain, str):
        if domain.startswith("domain:"):
            slug = domain[len("domain:") :]
        else:
            slug = domain
    else:
        raise TypeError(f"Expected DomainId or str, got {type(domain).__name__}")

    return slug.replace("-", "_")


def is_canonical_general_event(event_type: str) -> bool:
    """Check if an event type is one of the 23 built-in general domain events."""
    return event_type in CANONICAL_DOMAIN_EVENTS_SET


def validate_event_type_syntax(event_type: str) -> bool:
    """Validate that an event type follows dotted lowercase naming conventions."""
    if not isinstance(event_type, str):
        return False
    return bool(_EVENT_NAME_RE.match(event_type))


def validate_specialized_event_namespace(
    event_type: str, domain: DomainId | str
) -> bool:
    """Check if a specialized event type matches the owning domain's namespace."""
    if not validate_event_type_syntax(event_type):
        return False
    if is_canonical_general_event(event_type):
        return False
    expected_ns = get_canonical_domain_namespace(domain)
    prefix = f"{expected_ns}."
    return event_type.startswith(prefix)
