"""Phase 10.1 – Domain Enums.

Immutable enumerations for the Domain Intelligence subsystem.
"""

from __future__ import annotations

from enum import Enum


class DomainStatus(str, Enum):
    """Lifecycle states of a domain."""

    DISCOVERED = "discovered"
    REGISTERED = "registered"
    LOADING = "loading"
    ACTIVE = "active"
    DISABLED = "disabled"
    DEGRADED = "degraded"
    INCOMPATIBLE = "incompatible"
    INVALID = "invalid"
    FAILED = "failed"
    UNLOADED = "unloaded"


class DomainKind(str, Enum):
    """Kinds of domains that can coexist in the system."""

    CORE = "core"
    PERSONAL = "personal"
    PROFESSIONAL = "professional"
    PROJECT = "project"
    SYSTEM = "system"
    EXTERNAL = "external"
    EXPERIMENTAL = "experimental"


__all__ = [
    "DomainKind",
    "DomainStatus",
]
