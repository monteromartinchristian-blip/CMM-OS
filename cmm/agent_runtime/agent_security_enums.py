"""Phase 9.25 – Agent Security, Permissions, and Isolation Enumerations.

Defines the security-specific enums for the authorization boundary,
including decisions, injection categories, kill switch lifecycle, sensitivity
levels, error codes, and reason codes.
"""

from __future__ import annotations

from enum import Enum


class PermissionEffect(str, Enum):
    """Authorization decision effects."""

    ALLOW = "allow"
    DENY = "deny"
    APPROVAL_REQUIRED = "approval_required"
    ALLOW_WITH_CONSTRAINTS = "allow_with_constraints"
    EXPIRED = "expired"
    ISOLATED = "isolated"
    KILL_SWITCH_ACTIVE = "kill_switch_active"


class ExternalActionCategory(str, Enum):
    """Classification of externally impactful actions."""

    EMAIL = "email"
    MESSAGE = "message"
    PUBLICATION = "publication"
    PAYMENT = "payment"
    HIRING = "hiring"
    TERMS_ACCEPTANCE = "terms_acceptance"
    COMMITMENT = "commitment"
    DELETION = "deletion"
    PERMISSION_CHANGE = "permission_change"
    DEPLOYMENT = "deployment"
    MEDICAL_ACTION = "medical_action"
    LEGAL_ACTION = "legal_action"
    FINANCIAL_ACTION = "financial_action"
    SENSITIVE_DATA_SHARE = "sensitive_data_share"


class PromptInjectionResult(str, Enum):
    """Prompt injection assessment outcomes."""

    CLEAN = "clean"
    SUSPICIOUS = "suspicious"
    BLOCKED = "blocked"


class PromptInjectionCategory(str, Enum):
    """Categories of prompt injection attempts detected."""

    INSTRUCTION_OVERRIDE = "instruction_override"
    ROLE_CHANGE = "role_change"
    GOAL_CHANGE = "goal_change"
    OPERATION_ADD = "operation_add"
    POLICY_MODIFICATION = "policy_modification"
    AUTONOMY_ELEVATION = "autonomy_elevation"
    PERMISSION_GRANT = "permission_grant"
    SECRET_REQUEST = "secret_request"
    VALIDATION_DISABLE = "validation_disable"
    AUTO_APPROVAL = "auto_approval"
    BUDGET_INCREASE = "budget_increase"
    COMMUNICATION_ORDER = "communication_order"
    RUNTIME_ALTERATION = "runtime_alteration"


class KillSwitchState(str, Enum):
    """Kill switch lifecycle states."""

    INACTIVE = "inactive"
    ACTIVATING = "activating"
    ACTIVE = "active"
    RECOVERING = "recovering"
    RELEASED = "released"
    FAILED = "failed"

    @property
    def is_blocking(self) -> bool:
        """Return True if the kill switch currently blocks new operations."""
        return self in {KillSwitchState.ACTIVATING, KillSwitchState.ACTIVE}


class KillSwitchScope(str, Enum):
    """Scope at which the kill switch applies."""

    GLOBAL = "global"
    AGENT = "agent"
    RUN = "run"
    GOAL = "goal"


class SensitivityLevel(str, Enum):
    """Data/operation sensitivity classification."""

    PUBLIC = "public"
    INTERNAL = "internal"
    CONFIDENTIAL = "confidential"
    RESTRICTED = "restricted"
    SECRET = "secret"


class PermissionReasonCode(str, Enum):
    """Stable reason codes used in PermissionDecision / audit entries."""

    GRANTED = "granted"
    GRANTED_WITH_CONSTRAINTS = "granted_with_constraints"
    KILL_SWITCH_ACTIVE = "kill_switch_active"
    CONTEXT_EXPIRED = "context_expired"
    POLICY_DENY = "policy_deny"
    POLICY_ERROR = "policy_error"
    POLICY_APPROVAL_REQUIRED = "policy_approval_required"
    NO_CONTEXT = "no_context"
    IDENTITY_MISMATCH = "identity_mismatch"
    AUTONOMY_EXCEEDED = "autonomy_exceeded"
    SENSITIVITY_NOT_ALLOWED = "sensitivity_not_allowed"
    RESOURCE_NOT_AUTHORIZED = "resource_not_authorized"
    OPERATION_NOT_PERMITTED = "operation_not_permitted"
    DOMAIN_NOT_ALLOWED = "domain_not_allowed"
    EXTERNAL_ACCESS_NOT_ALLOWED = "external_access_not_allowed"
    EXTERNAL_MODEL_NOT_ALLOWED = "external_model_not_allowed"
    MEMORY_WRITE_NOT_ALLOWED = "memory_write_not_allowed"
    GOAL_CREATION_NOT_ALLOWED = "goal_creation_not_allowed"
    DELEGATION_NOT_ALLOWED = "delegation_not_allowed"
    PUBLICATION_NOT_ALLOWED = "publication_not_allowed"
    COMMUNICATIONS_NOT_ALLOWED = "communications_not_allowed"
    DESTRUCTIVE_ACTION_NOT_ALLOWED = "destructive_action_not_allowed"
    PERMISSION_ELEVATION_NOT_ALLOWED = "permission_elevation_not_allowed"
    EXTERNAL_ACTION_RESTRICTED = "external_action_restricted"
    CONSTRAINT_VIOLATION = "constraint_violation"
    AGENT_MISMATCH = "agent_mismatch"
    RUN_MISMATCH = "run_mismatch"
    GOAL_MISMATCH = "goal_mismatch"
    ACTOR_MISMATCH = "actor_mismatch"
    OWNER_MISMATCH = "owner_mismatch"
    DELEGATION_PERMISSION_ESCALATION = "delegation_permission_escalation"


class SecurityErrorCode(str, Enum):
    """Stable error codes for security subsystem."""

    INTERNAL_ERROR = "internal_error"
    INVALID_CONTRACT = "invalid_contract"
    EVALUATION_ERROR = "evaluation_error"
    PERMISSION_DENIED = "permission_denied"
    APPROVAL_REQUIRED = "approval_required"
    APPROVAL_NOT_FOUND = "approval_not_found"
    APPROVAL_NOT_AUTHORIZED = "approval_not_authorized"
    APPROVAL_EXPIRED = "approval_expired"
    DUPLICATE_APPROVAL = "duplicate_approval"
    PERMISSION_CONTEXT_NOT_FOUND = "permission_context_not_found"
    PERMISSION_CONTEXT_EXPIRED = "permission_context_expired"
    INVALID_PERMISSION_CONTEXT = "invalid_permission_context"
    AUTONOMY_LEVEL_EXCEEDED = "autonomy_level_exceeded"
    SENSITIVITY_LEVEL_NOT_ALLOWED = "sensitivity_level_not_allowed"
    RESOURCE_NOT_AUTHORIZED = "resource_not_authorized"
    OPERATION_NOT_PERMITTED = "operation_not_permitted"
    EXTERNAL_ACCESS_NOT_ALLOWED = "external_access_not_allowed"
    EXTERNAL_MODEL_NOT_ALLOWED = "external_model_not_allowed"
    MEMORY_WRITE_NOT_ALLOWED = "memory_write_not_allowed"
    GOAL_CREATION_NOT_ALLOWED = "goal_creation_not_allowed"
    DELEGATION_NOT_ALLOWED = "delegation_not_allowed"
    PUBLICATION_NOT_ALLOWED = "publication_not_allowed"
    COMMUNICATION_NOT_ALLOWED = "communication_not_allowed"
    DESTRUCTIVE_ACTION_NOT_ALLOWED = "destructive_action_not_allowed"
    PERMISSION_ELEVATION_NOT_ALLOWED = "permission_elevation_not_allowed"
    PROMPT_INJECTION_DETECTED = "prompt_injection_detected"
    PROMPT_INJECTION_BLOCKED = "prompt_injection_blocked"
    EXTERNAL_ACTION_NOT_ALLOWED = "external_action_not_allowed"
    EXTERNAL_ACTION_NOT_REGISTERED = "external_action_not_registered"
    EXTERNAL_ACTION_CHECKPOINT_REQUIRED = "external_action_checkpoint_required"
    KILL_SWITCH_ACTIVATION_FAILED = "kill_switch_activation_failed"
    KILL_SWITCH_ALREADY_ACTIVE = "kill_switch_already_active"
    KILL_SWITCH_NOT_ACTIVE = "kill_switch_not_active"
    KILL_SWITCH_RELEASE_UNAUTHORIZED = "kill_switch_release_unauthorized"


__all__ = [
    "ExternalActionCategory",
    "KillSwitchScope",
    "KillSwitchState",
    "PermissionEffect",
    "PermissionReasonCode",
    "PromptInjectionCategory",
    "PromptInjectionResult",
    "SecurityErrorCode",
    "SensitivityLevel",
]
