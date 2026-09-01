"""Phase 10.38 — Pure Domain trust evaluation for activation.

``evaluate_domain_trust`` is a deterministic, fail-closed evaluator that
consumes already-canonical evidence:

- ``DomainCandidate`` (discovery evidence)
- ``DomainManifest`` (manifest facts incl. signature presence)
- ``DomainValidationResult`` (canonical validation evidence)
- ``DomainTrustPolicy`` (explicit caller/configuration declaration)
- ``manual_enable_requested`` (explicit activation evidence)

It never accesses the network, reads or writes files, queries a store,
mutates a registry/loader, consumes approval, caches authorization, or
executes code. It returns immutable ``DomainTrustDecision`` evidence.

``evaluate_domain_trust_permission`` is the pure trust permission ceiling:
it may return only DENY or ABSTAIN, and it never grants authority.
"""

from __future__ import annotations

from cmm.agent_runtime.agent_security_enums import SensitivityLevel
from cmm.agent_runtime.domain_permission_contracts import (
    PermissionCapability,
    PermissionLayer,
    PermissionLayerEvaluation,
    PermissionOutcome,
)
from cmm.domains.enums import DomainTrustLevel, DomainValidationStatus
from cmm.domains.permission_contracts import DomainPermissionRequest
from cmm.domains.trust_contracts import DomainTrustDecision, DomainTrustPolicy

# Canonical capability ceilings. Trust may only deny existing canonical
# permissions; it never grants.
_CODE_EXECUTION_CAPABILITIES: frozenset[str] = frozenset(
    {
        PermissionCapability.OPERATION_EXECUTE.value,
        PermissionCapability.WORKFLOW_EXECUTE.value,
    }
)

_EXTERNAL_ACCESS_CAPABILITIES: frozenset[str] = frozenset(
    {
        PermissionCapability.SEARCH_EXTERNAL.value,
        PermissionCapability.MODEL_EXTERNAL.value,
        PermissionCapability.COMMUNICATION_EXTERNAL.value,
        PermissionCapability.EXPORT.value,
        PermissionCapability.DOMAIN_CROSS_ACCESS.value,
    }
)

_MEMORY_WRITE_CAPABILITIES: frozenset[str] = frozenset(
    {PermissionCapability.MEMORY_WRITE.value}
)

_SENSITIVE_RESOURCE_CAPABILITIES: frozenset[str] = frozenset(
    {
        PermissionCapability.SENSITIVE_INFERENCE.value,
        PermissionCapability.SENSITIVE_INFERENCE_PERSIST.value,
    }
)

_DESTRUCTIVE_OPERATION_CAPABILITIES: frozenset[str] = frozenset(
    {
        PermissionCapability.FILE_MODIFY.value,
        PermissionCapability.TASK_CREATE.value,
        PermissionCapability.SCHEDULE_MODIFY.value,
        PermissionCapability.GOAL_UPDATE.value,
        PermissionCapability.PUBLICATION.value,
        PermissionCapability.KNOWLEDGE_DELETE.value,
        PermissionCapability.PERMISSION_MODIFY.value,
        PermissionCapability.IRREVERSIBLE_CHANGE.value,
        PermissionCapability.MEDICAL_ACTION.value,
        PermissionCapability.LEGAL_ACTION.value,
        PermissionCapability.FINANCIAL_ACTION.value,
        PermissionCapability.FINANCIAL_SPEND.value,
    }
)

_BLOCKING_VALIDATION_STATUSES = frozenset(
    {
        DomainValidationStatus.FAILED,
        DomainValidationStatus.ERROR,
    }
)


def _denied_capabilities_for(policy: DomainTrustPolicy) -> tuple[str, ...]:
    """Deterministic denied canonical capabilities derived from the policy."""
    denied: set[str] = set()
    if not policy.allow_code_execution:
        denied.update(_CODE_EXECUTION_CAPABILITIES)
    if not policy.allow_external_access:
        denied.update(_EXTERNAL_ACCESS_CAPABILITIES)
    if not policy.allow_memory_write:
        denied.update(_MEMORY_WRITE_CAPABILITIES)
    if not policy.allow_sensitive_resources:
        denied.update(_SENSITIVE_RESOURCE_CAPABILITIES)
    if not policy.allow_destructive_operations:
        denied.update(_DESTRUCTIVE_OPERATION_CAPABILITIES)
    return tuple(sorted(denied))


def evaluate_domain_trust(
    *,
    candidate,
    manifest,
    validation,
    policy: DomainTrustPolicy,
    manual_enable_requested: bool,
) -> DomainTrustDecision:
    """Evaluate the trust boundary for explicit activation.

    Returns an immutable ``DomainTrustDecision`` that is evidence only.
    ``activation_allowed`` never authorizes runtime operations; the canonical
    permission/approval system remains authoritative.
    """
    denied_capabilities = _denied_capabilities_for(policy)

    # ── Identity coherence ──────────────────────────────────────────────
    identity_ok = True
    if policy.domain_id != candidate.domain_id:
        identity_ok = False
    if validation.domain_id != candidate.domain_id:
        identity_ok = False
    if validation.version != candidate.detected_version:
        identity_ok = False
    if str(manifest.domain_id) != candidate.domain_id:
        identity_ok = False
    if manifest.package_version != candidate.detected_version:
        identity_ok = False
    if not identity_ok:
        return DomainTrustDecision(
            domain_id=candidate.domain_id,
            candidate_id=candidate.candidate_id,
            source_id=candidate.source_id,
            trust_level=policy.trust_level,
            activation_allowed=False,
            manual_enable_required=policy.require_manual_enable,
            denied_capabilities=denied_capabilities,
            reason_codes=("trust.validation_failed",),
            metadata={"identity_incoherent": True},
        )

    # ── Canonical validation evidence ───────────────────────────────────
    validation_ok = True
    if validation.status in _BLOCKING_VALIDATION_STATUSES:
        validation_ok = False
    if validation.has_blocking_findings:
        validation_ok = False
    if not validation.security_valid:
        validation_ok = False
    if not validation_ok:
        return DomainTrustDecision(
            domain_id=candidate.domain_id,
            candidate_id=candidate.candidate_id,
            source_id=candidate.source_id,
            trust_level=policy.trust_level,
            activation_allowed=False,
            manual_enable_required=policy.require_manual_enable,
            denied_capabilities=denied_capabilities,
            reason_codes=("trust.validation_failed",),
        )

    # ── Blocked policy ──────────────────────────────────────────────────
    if policy.trust_level is DomainTrustLevel.BLOCKED:
        return DomainTrustDecision(
            domain_id=candidate.domain_id,
            candidate_id=candidate.candidate_id,
            source_id=candidate.source_id,
            trust_level=policy.trust_level,
            activation_allowed=False,
            manual_enable_required=policy.require_manual_enable,
            denied_capabilities=denied_capabilities,
            reason_codes=("trust.blocked",),
        )

    # ── Authorized source ───────────────────────────────────────────────
    if candidate.source_id not in policy.authorized_source_ids:
        return DomainTrustDecision(
            domain_id=candidate.domain_id,
            candidate_id=candidate.candidate_id,
            source_id=candidate.source_id,
            trust_level=policy.trust_level,
            activation_allowed=False,
            manual_enable_required=policy.require_manual_enable,
            denied_capabilities=denied_capabilities,
            reason_codes=("trust.source_not_authorized",),
        )

    # ── Signature presence policy ───────────────────────────────────────
    if policy.require_signature and not manifest.signature:
        return DomainTrustDecision(
            domain_id=candidate.domain_id,
            candidate_id=candidate.candidate_id,
            source_id=candidate.source_id,
            trust_level=policy.trust_level,
            activation_allowed=False,
            manual_enable_required=policy.require_manual_enable,
            denied_capabilities=denied_capabilities,
            reason_codes=("trust.signature_required",),
        )

    # ── Manual enablement ───────────────────────────────────────────────
    if policy.require_manual_enable and not manual_enable_requested:
        return DomainTrustDecision(
            domain_id=candidate.domain_id,
            candidate_id=candidate.candidate_id,
            source_id=candidate.source_id,
            trust_level=policy.trust_level,
            activation_allowed=False,
            manual_enable_required=True,
            denied_capabilities=denied_capabilities,
            reason_codes=("trust.manual_enable_required",),
        )

    return DomainTrustDecision(
        domain_id=candidate.domain_id,
        candidate_id=candidate.candidate_id,
        source_id=candidate.source_id,
        trust_level=policy.trust_level,
        activation_allowed=True,
        manual_enable_required=policy.require_manual_enable,
        denied_capabilities=denied_capabilities,
        reason_codes=(),
        metadata={"signature_present": bool(manifest.signature)},
    )


def evaluate_domain_trust_permission(
    policy: DomainTrustPolicy,
    request: DomainPermissionRequest,
) -> PermissionLayerEvaluation:
    """Evaluate one request against the trust permission ceiling.

    Returns exactly:

    - ``DENY`` when the requested authority is outside the trust ceiling;
    - ``ABSTAIN`` when the trust policy does not deny the request.

    It never returns ``ALLOW`` or ``APPROVAL_REQUIRED``: the canonical
    Domain permission policy and gate remain responsible for those outcomes.
    """
    reasons: list[str] = []
    denied = False

    if request.action is PermissionCapability.OPERATION_EXECUTE or (
        request.action is PermissionCapability.WORKFLOW_EXECUTE
    ):
        if not policy.allow_code_execution:
            denied = True
            reasons.append("trust.code_execution_denied")
    elif request.action is PermissionCapability.MEMORY_WRITE:
        if not policy.allow_memory_write:
            denied = True
            reasons.append("trust.memory_write_denied")
    elif request.action in (
        PermissionCapability.SEARCH_EXTERNAL,
        PermissionCapability.MODEL_EXTERNAL,
        PermissionCapability.COMMUNICATION_EXTERNAL,
        PermissionCapability.EXPORT,
        PermissionCapability.DOMAIN_CROSS_ACCESS,
    ):
        if not policy.allow_external_access:
            denied = True
            reasons.append("trust.external_access_denied")
    elif request.action in (
        PermissionCapability.SENSITIVE_INFERENCE,
        PermissionCapability.SENSITIVE_INFERENCE_PERSIST,
    ):
        if not policy.allow_sensitive_resources:
            denied = True
            reasons.append("trust.sensitive_resource_denied")
    elif request.action is PermissionCapability.RESOURCE_READ:
        if (
            request.sensitivity_level is not None
            and request.sensitivity_level is not SensitivityLevel.PUBLIC
            and not policy.allow_sensitive_resources
        ):
            denied = True
            reasons.append("trust.sensitive_resource_denied")
    elif (
        request.action
        in (
            PermissionCapability.FILE_MODIFY,
            PermissionCapability.TASK_CREATE,
            PermissionCapability.SCHEDULE_MODIFY,
            PermissionCapability.GOAL_UPDATE,
            PermissionCapability.PUBLICATION,
            PermissionCapability.KNOWLEDGE_DELETE,
            PermissionCapability.PERMISSION_MODIFY,
            PermissionCapability.IRREVERSIBLE_CHANGE,
            PermissionCapability.MEDICAL_ACTION,
            PermissionCapability.LEGAL_ACTION,
            PermissionCapability.FINANCIAL_ACTION,
            PermissionCapability.FINANCIAL_SPEND,
        )
        and not policy.allow_destructive_operations
    ):
        denied = True
        reasons.append("trust.destructive_operation_denied")

    if not denied:
        return PermissionLayerEvaluation(
            source=PermissionLayer.DOMAIN,
            effect=PermissionOutcome.ABSTAIN,
            source_id=f"domain-trust:{policy.domain_id}",
            reasons=(),
            metadata={"trust_level": policy.trust_level.value},
        )
    return PermissionLayerEvaluation(
        source=PermissionLayer.DOMAIN,
        effect=PermissionOutcome.DENY,
        source_id=f"domain-trust:{policy.domain_id}",
        reasons=tuple(reasons),
        metadata={"trust_level": policy.trust_level.value},
    )


__all__ = ["evaluate_domain_trust", "evaluate_domain_trust_permission"]
