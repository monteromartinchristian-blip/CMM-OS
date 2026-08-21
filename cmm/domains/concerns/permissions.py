"""Phase 10.25 — Concerns Domain Permissions.

A fail-closed permission policy for the Concerns Domain.  Denied by default:
anything that could write semantic memory, persist sensitive inference, adopt
a personal decision, perform an external write/communication, start
monitoring, or modify permissions.  The autonomous surface is read +
memory-read + execute only.

Concerns is high sensitivity: fears, support needs, emotional patterns,
recurring-concern patterns, psychological interpretations, risk
interpretations and third-party motives are never silently persisted.
Most-restrictive policy wins under composition; unknown or malformed
permission state denies; only literal boolean ``True`` authorizes a boolean
permission gate.
"""

from __future__ import annotations

from cmm.agent_runtime.domain_permission_contracts import PermissionCapability
from cmm.domains.concerns.resources import CONCERNS_RESOURCE_KINDS
from cmm.domains.permission_contracts import (
    DomainAutonomyLimits,
    DomainPermissionPolicy,
)

CONCERNS_PERMISSION_POLICY_ID = "domain-permission:concerns:1.0.0"

# Denied by default: everything that could autonomously act on psychological
# state, memory, external systems, or personal decisions (frozen design §73).
CONCERNS_PROHIBITED_CAPABILITIES: tuple[PermissionCapability, ...] = (
    PermissionCapability.SEARCH_EXTERNAL,
    PermissionCapability.MODEL_EXTERNAL,
    PermissionCapability.MEMORY_WRITE,
    PermissionCapability.FILE_MODIFY,
    PermissionCapability.TASK_CREATE,
    PermissionCapability.SCHEDULE_MODIFY,
    PermissionCapability.GOAL_UPDATE,
    PermissionCapability.COMMUNICATION_EXTERNAL,
    PermissionCapability.SENSITIVE_INFERENCE,
    PermissionCapability.SENSITIVE_INFERENCE_PERSIST,
    PermissionCapability.EXPORT,
    PermissionCapability.PUBLICATION,
    PermissionCapability.EXTERNAL_DOMAIN_ACTIVATE,
    PermissionCapability.IRREVERSIBLE_CHANGE,
    PermissionCapability.KNOWLEDGE_DELETE,
    PermissionCapability.PERMISSION_MODIFY,
    PermissionCapability.MEDICAL_DECISION,
    PermissionCapability.MEDICAL_ACTION,
    PermissionCapability.LEGAL_DECISION,
    PermissionCapability.LEGAL_ACTION,
    PermissionCapability.FINANCIAL_DECISION,
    PermissionCapability.FINANCIAL_ACTION,
    PermissionCapability.FINANCIAL_SPEND,
)


def permission_authorization_allows(value) -> bool:
    """Strict runtime authorization: only the literal ``True`` authorizes.

    Strings (``"true"``), numerics (``1``, ``0``), collections (``[]``,
    ``{}``), ``None`` and arbitrary objects never authorize.  No coercion and
    no string parsing.
    """
    return value is True


def persistence_confirmation_accepted(
    *,
    confirmation=None,
    confirmation_binding=None,
    confirmation_inventory=None,
    proposal_id: str | None = None,
    content_kind: str | None = None,
    repetition_count: int = 0,
) -> dict:
    """Evaluate whether a memory-persistence confirmation is acceptable.

    Fail-closed semantics:

    - Raw booleans, numerics, strings and arbitrary mappings are malformed and
      never authorize; repetition count is never authorization;
    - A standalone ``DomainMemoryApprovalDecisionSnapshot`` is reference data,
      not a complete shared contract — it fails closed as malformed;
    - A complete chain requires binding + inventory + matching proposal id and
      passes shared validation;
    - Restricted content kinds (fear, support need, inferred patterns,
      psychological/risk interpretations, third-party motive) can NEVER be
      accepted regardless of chain validity — they must not be silently
      persisted at all.
    """
    restricted = is_persistence_restricted_content(content_kind)
    record: dict = {
        "accepted": False,
        "authorization_accepted": False,
        "authorization_malformed": False,
        "chain_valid": False,
        "content_restricted": restricted,
        "content_kind": content_kind if isinstance(content_kind, str) else None,
        "proposal_id": proposal_id,
        "repetition_is_not_authorization": True,
    }

    # Restricted content can never pass, whatever the chain says.
    if restricted:
        return normalize_record(record)

    if confirmation is not None:
        # Any direct confirmation object must be the full shared contract path
        # (binding + inventory).  A bare snapshot is reference data; raw
        # booleans, numerics, strings and mappings are malformed outright.

        record["authorization_malformed"] = True
        return normalize_record(record)

    if (
        confirmation_binding is None or confirmation_inventory is None
    ):
        record["authorization_malformed"] = (
            confirmation_binding is not None or confirmation_inventory is not None
        )
        return normalize_record(record)

    from cmm.domains.concerns.memory import validate_concerns_memory_binding

    validation = validate_concerns_memory_binding(
        binding=confirmation_binding, inventory=confirmation_inventory
    )
    record["chain_valid"] = bool(validation.is_valid)

    binding_matches = (
        proposal_id is not None
        and tuple(confirmation_binding.memory_proposal_ids) == (proposal_id,)
    )
    approvals = confirmation_inventory.approval_requests
    decisions = confirmation_inventory.approval_decisions
    linked = any(
        request.request_id in {decision.request_id for decision in decisions}
        for request in approvals
    )
    approved = any(
        decision.approved is True
        for decision in decisions
        if any(request.request_id == decision.request_id for request in approvals)
    )

    record["authorization_accepted"] = bool(
        record["chain_valid"] and binding_matches and linked and approved
    )
    if not record["authorization_accepted"]:
        record["authorization_malformed"] = True
    record["accepted"] = record["authorization_accepted"]
    return normalize_record(record)


def build_concerns_permission_policy() -> DomainPermissionPolicy:
    """Build the fail-closed Concerns Domain permission policy deterministically."""
    return DomainPermissionPolicy(
        policy_id=CONCERNS_PERMISSION_POLICY_ID,
        domain_id="domain:concerns",
        version="1.0.0",
        allowed_capabilities=(
            PermissionCapability.RESOURCE_READ,
            PermissionCapability.MEMORY_READ,
            PermissionCapability.OPERATION_EXECUTE,
            PermissionCapability.WORKFLOW_EXECUTE,
        ),
        prohibited_capabilities=CONCERNS_PROHIBITED_CAPABILITIES,
        approval_capabilities=(),
        allowed_resource_kinds=CONCERNS_RESOURCE_KINDS,
        # Most-restrictive policy wins; sensitivity levels remain restricted.
        allowed_sensitivity_levels=("restricted", "secret"),
        allow_memory_read=True,
        allow_memory_write=False,
        allow_external_search=False,
        allow_external_models=False,
        allow_external_communication=False,
        allow_file_modification=False,
        allow_task_creation=False,
        allow_schedule_modification=False,
        allow_goal_update=False,
        allow_export=False,
        allow_sensitive_inference=False,
        allow_cross_domain_access=False,
        allow_inbound_cross_domain_access=True,
        approval_requirements=(),
        autonomy_limits=DomainAutonomyLimits(
            maximum_autonomy_level=0,
            allow_reversible_changes=False,
            allow_irreversible_changes=False,
        ),
        enabled=True,
        metadata={"phase": "10.25"},
    )


def is_persistence_restricted_content(content_kind) -> bool:
    """True when ``content_kind`` names content that must never be silently
    persisted by Concerns (frozen design §71)."""
    if not isinstance(content_kind, str):
        return False
    return content_kind.strip().casefold() in _RESTRICTED_CONTENT_KINDS


_RESTRICTED_CONTENT_KINDS: frozenset[str] = frozenset(
    {
        "fear",
        "support_need",
        "support need",
        "inferred_emotional_pattern",
        "inferred emotional pattern",
        "emotional_pattern",
        "emotional pattern",
        "recurring_concern_pattern",
        "recurring concern pattern",
        "recurring_pattern",
        "psychological_interpretation",
        "psychological interpretation",
        "risk_interpretation",
        "risk interpretation",
        "third_party_motive",
        "third-party motive",
        "third_party_motive_inference",
    }
)


def normalize_record(record: dict) -> dict:
    """JSON-safe normalization boundary for permission-decision records."""
    from cmm.domains.concerns.rules import normalize_json_value

    return normalize_json_value(record)


__all__ = [
    "CONCERNS_PERMISSION_POLICY_ID",
    "CONCERNS_PROHIBITED_CAPABILITIES",
    "build_concerns_permission_policy",
    "is_persistence_restricted_content",
    "permission_authorization_allows",
    "persistence_confirmation_accepted",
]
