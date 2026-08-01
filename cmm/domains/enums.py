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


class DomainResolutionStatus(str, Enum):
    """Status of a domain resolution operation (Phase 10.7).

    Does not include composition statuses (those belong to Phase 10.8).
    """

    RESOLVED = "resolved"
    AMBIGUOUS = "ambiguous"
    INSUFFICIENT_INFORMATION = "insufficient_information"
    UNSUPPORTED = "unsupported"
    BLOCKED = "blocked"
    FAILED = "failed"


class DomainCompositionStatus(str, Enum):
    """Status of a domain composition result (Phase 10.8)."""

    COMPOSED = "composed"
    PARTIAL = "partial"
    BLOCKED = "blocked"
    FAILED = "failed"


class DomainConflictPolicy(str, Enum):
    """Conflict resolution strategies for domain composition (Phase 10.8)."""

    MOST_RESTRICTIVE = "most_restrictive"
    PRIMARY_PRECEDENCE = "primary_precedence"
    BLOCK_ON_CONFLICT = "block_on_conflict"


class CrossDomainStatus(str, Enum):
    """Status of a Cross-Domain Engine execution (Phase 10.9).

    Final results may never use ``PENDING`` or ``RUNNING``.
    """

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    PARTIAL = "partial"
    BLOCKED = "blocked"
    FAILED = "failed"
    REQUIRES_REVIEW = "requires_review"
    LIMIT_REACHED = "limit_reached"


class CrossDomainSeverity(str, Enum):
    """Closed severity levels for cross-domain contradictions (Phase 10.9)."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class CrossDomainStage(str, Enum):
    """Closed coordination stages for cross-domain decisions (Phase 10.9)."""

    RESOLUTION = "resolution"
    COMPOSITION = "composition"
    KNOWLEDGE = "knowledge"
    PLANNING = "planning"
    DOMAIN_EXECUTION = "domain_execution"
    WORKFLOW_COORDINATION = "workflow_coordination"
    OPERATION_COORDINATION = "operation_coordination"
    AGGREGATION = "aggregation"


class DomainResourceResolutionStatus(str, Enum):
    """Status of a Domain Resource resolution operation (Phase 10.10)."""

    RESOLVED = "resolved"
    PARTIAL = "partial"
    BLOCKED = "blocked"
    REJECTED = "rejected"
    FAILED = "failed"


class DomainResourceDecisionCode(str, Enum):
    """Closed decision codes produced during Domain Resource resolution (Phase 10.10)."""

    DEFINITION_SELECTED = "definition_selected"
    DEFINITION_SKIPPED = "definition_skipped"
    DOMAIN_NOT_APPLICABLE = "domain_not_applicable"
    PERMISSION_DENIED = "permission_denied"
    SENSITIVITY_RESTRICTED = "sensitivity_restricted"
    TEMPORAL_POLICY_FAILED = "temporal_policy_failed"
    VALIDATION_FAILED = "validation_failed"
    RESOURCE_SHARED = "resource_shared"
    DERIVATION_RECORDED = "derivation_recorded"
    SOURCE_PRIORITY_APPLIED = "source_priority_applied"
    RELIABILITY_APPLIED = "reliability_applied"


class DomainResourceValidationSeverity(str, Enum):
    """Closed severity levels for Domain Resource validation results (Phase 10.10)."""

    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    BLOCKING = "blocking"


class DomainResourceValidationOperator(str, Enum):
    """Closed set of declarative validation operators for Domain Resources (Phase 10.10)."""

    EXISTS = "exists"
    EQUALS = "equals"
    NOT_EQUALS = "not_equals"
    CONTAINS = "contains"
    IN = "in"
    MINIMUM = "minimum"
    MAXIMUM = "maximum"


class DomainProfileResolutionStatus(str, Enum):
    """Closed status values for Domain Profile resolution outcomes (Phase 10.11)."""

    RESOLVED = "resolved"
    PARTIAL = "partial"
    BLOCKED = "blocked"
    FAILED = "failed"


class DomainProfileSource(str, Enum):
    """Closed set of sources that can contribute to a Domain Profile resolution (Phase 10.11)."""

    GLOBAL_POLICY = "global_policy"
    PRIMARY_DOMAIN = "primary_domain"
    SUPPORTING_DOMAIN = "supporting_domain"
    WORKFLOW = "workflow"
    OPERATION = "operation"
    RISK = "risk"
    ACTOR = "actor"
    AUTONOMY = "autonomy"
    EXPLICIT_REQUEST = "explicit_request"


class DomainProfileDecisionCode(str, Enum):
    """Closed decision codes produced during Domain Profile resolution (Phase 10.11)."""

    PROFILE_APPLIED = "profile_applied"
    OVERLAY_APPLIED = "overlay_applied"
    OVERLAY_SKIPPED = "overlay_skipped"
    MANDATORY_RULE_PRESERVED = "mandatory_rule_preserved"
    PROHIBITED_RULE_PREVAILED = "prohibited_rule_prevailed"
    RESOURCE_RESTRICTED = "resource_restricted"
    CONFIDENCE_RAISED = "confidence_raised"
    LIMIT_RESTRICTED = "limit_restricted"
    INFERENCE_PROHIBITED = "inference_prohibited"
    ACTION_PROHIBITED = "action_prohibited"
    PERMISSION_RESTRICTED = "permission_restricted"
    ESCALATION_ADDED = "escalation_added"
    POLICY_RESTRICTED = "policy_restricted"
    CONFLICT_RECORDED = "conflict_recorded"


class DomainProfileConflictSeverity(str, Enum):
    """Closed severity levels for Domain Profile conflicts (Phase 10.11)."""

    WARNING = "warning"
    ERROR = "error"
    BLOCKING = "blocking"


class DomainReasoningDepth(str, Enum):
    """Closed, ordered set of maximum permitted reasoning depths (Phase 10.11).

    Ordering (shallowest to deepest) is SHALLOW < STANDARD < DEEP < EXHAUSTIVE.
    This field represents a maximum permitted depth, so composition always
    selects the minimum (most restrictive) value across contributing sources.
    """

    SHALLOW = "shallow"
    STANDARD = "standard"
    DEEP = "deep"
    EXHAUSTIVE = "exhaustive"


__all__ = [
    "CrossDomainSeverity",
    "CrossDomainStage",
    "CrossDomainStatus",
    "DomainCompositionStatus",
    "DomainConflictPolicy",
    "DomainKind",
    "DomainLoadStatus",
    "DomainPackKind",
    "DomainPackStatus",
    "DomainProfileConflictSeverity",
    "DomainProfileDecisionCode",
    "DomainProfileResolutionStatus",
    "DomainProfileSource",
    "DomainReasoningDepth",
    "DomainResolutionStatus",
    "DomainResourceDecisionCode",
    "DomainResourceResolutionStatus",
    "DomainResourceValidationOperator",
    "DomainResourceValidationSeverity",
    "DomainSourceKind",
    "DomainStatus",
    "DomainValidationStatus",
]
