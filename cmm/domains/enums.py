"""Phase 10 – Domain Enums.

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


class DomainPackKind(str, Enum):
    """How a domain pack is distributed and what initial trust level it has.

    Distinct from DomainKind, which describes the functional nature of the domain.
    """

    INTERNAL = "internal"
    EXTERNAL = "external"
    EXPERIMENTAL = "experimental"


class DomainPackStatus(str, Enum):
    """States of a domain pack — not the full lifecycle of a registered domain."""

    DECLARED = "declared"
    VALID = "valid"
    INVALID = "invalid"
    INSTALLED = "installed"
    ENABLED = "enabled"
    DISABLED = "disabled"
    DEGRADED = "degraded"
    INCOMPATIBLE = "incompatible"


class DomainSourceKind(str, Enum):
    """Kinds of discovery sources for domain packs.

    Only INTERNAL, DIRECTORY, DEVELOPMENT, and TEST have real operational
    support in Phase 10.4. The remaining kinds are contractually
    representable but must not be treated as operationally supported.
    """

    INTERNAL = "internal"
    DIRECTORY = "directory"
    INSTALLED = "installed"
    PLUGIN = "plugin"
    REPOSITORY = "repository"
    USER = "user"
    DEVELOPMENT = "development"
    TEST = "test"


class DomainLoadStatus(str, Enum):
    """Lifecycle states of a single domain loader operation.

    Distinct from ``DomainStatus``, which represents registry lifecycle.
    """

    DISCOVERED = "discovered"
    VALIDATING = "validating"
    VALID = "valid"
    LOADING = "loading"
    LOADED = "loaded"
    RELOADING = "reloading"
    UNLOADING = "unloading"
    UNLOADED = "unloaded"
    DEGRADED = "degraded"
    FAILED = "failed"
    REJECTED = "rejected"


class DomainValidationStatus(str, Enum):
    """Validation status for domain packs (Phase 10.5).

    Maps to :class:`cmm.validation.enums.ValidationStatus`:
        PASSED    → PASSED
        WARNING   → WARNING
        FAILED    → FAILED
        ERROR     → ERROR
        CANCELLED → ERROR
        TIMED_OUT → ERROR
        SKIPPED   → ERROR (when mandatory)
    """

    PENDING = "pending"
    RUNNING = "running"
    PASSED = "passed"
    WARNING = "warning"
    FAILED = "failed"
    ERROR = "error"


__all__ = [
    "DomainKind",
    "DomainLoadStatus",
    "DomainPackKind",
    "DomainPackStatus",
    "DomainSourceKind",
    "DomainStatus",
    "DomainValidationStatus",
]
