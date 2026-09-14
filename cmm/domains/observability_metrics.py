"""Phase 10.37 — Domain Observability Metrics.

Pure, deterministic calculation of canonical Domain observability metrics from
existing canonical Domain evidence only.

Core laws:
- ``no evidence != zero != guess``: every metric is either OBSERVED (exact
  canonical value) or UNAVAILABLE (insufficient canonical evidence);
- never infer fallback, transfers, knowledge reuse, avoided questions or
  duplicate prevention by proxy;
- never encode UNAVAILABLE as ``0``/``0.0``;
- no registry lookups, no event publication, no resolver calls, no persistence
  and no current-time reads inside ``calculate``.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from cmm.agent_runtime.domain_permission_contracts import (
    PermissionApprovalRequirement,
    PermissionOutcome,
)
from cmm.domains.composition_contracts import (
    DomainComposition,
    DomainCompositionStatus,
)
from cmm.domains.conflict_resolution_contracts import DomainConflictCase
from cmm.domains.contracts import DomainDefinition, DomainId
from cmm.domains.cross_domain_contracts import CrossDomainContextTransfer
from cmm.domains.enums import (
    DomainLoadStatus,
    DomainResolutionStatus,
    DomainStatus,
)
from cmm.domains.errors import InvalidDomainObservabilityEvidenceError
from cmm.domains.event_contracts import DomainEvent
from cmm.domains.loader_contracts import DomainLoadResult
from cmm.domains.observability_contracts import (
    DomainMetricBucket,
    DomainMetricMeasurement,
    DomainMetricsSnapshot,
    DomainMetricStatus,
)
from cmm.domains.operation_contracts import DomainOperationResult
from cmm.domains.permission_adapters import DomainOperationPermissionDecision
from cmm.domains.registry_contracts import DomainRegistryRecord
from cmm.domains.resolver_contracts import DomainResolutionResult
from cmm.domains.resource_contracts import (
    DomainResourceBinding,
    DomainResourceResolution,
)
from cmm.domains.rule_contracts import DomainRuleExecutionResult
from cmm.domains.session_contracts import (
    DomainSessionContext,
    DomainSessionResumeResult,
    DomainSessionResumeStatus,
)
from cmm.domains.trace_contracts import (
    DomainTrace,
    DomainTraceReferenceKind,
    DomainTraceStatus,
)
from cmm.domains.workflow_contracts import DomainWorkflowResult

# ── Canonical metric catalog ──────────────────────────────────────────────────

CANONICAL_DOMAIN_OBSERVABILITY_METRICS: tuple[str, ...] = (
    "domains.installed",
    "domains.active",
    "loading.duration.mean_ms",
    "loading.failures",
    "resolution.decisions_by_domain",
    "resolution.confidence.mean",
    "resolution.ambiguous",
    "resolution.fallback",
    "execution.multi_domain",
    "execution.domains.mean",
    "conflicts.detected",
    "permissions.rejected",
    "approvals.requested",
    "operations.by_domain",
    "workflows.by_domain",
    "workflows.duration.mean_ms",
    "rules.applied_by_domain",
    "resources.loaded_by_domain",
    "cross_domain.transfers",
    "knowledge.reused",
    "questions.avoided_shared_context",
    "duplicates.prevented",
    "errors.by_domain_pack",
    "sessions.degraded",
    "external_domains.active",
)

# Stable unavailability reason codes. Unavailable is never encoded as zero.
NO_REGISTRY_EVIDENCE = "NO_REGISTRY_EVIDENCE"
NO_LOAD_DURATION_EVIDENCE = "NO_LOAD_DURATION_EVIDENCE"
NO_LOAD_EVIDENCE = "NO_LOAD_EVIDENCE"
NO_RESOLUTION_EVIDENCE = "NO_RESOLUTION_EVIDENCE"
NO_FALLBACK_EVIDENCE = "NO_FALLBACK_EVIDENCE"
NO_EXECUTION_EVIDENCE = "NO_EXECUTION_EVIDENCE"
NO_CONFLICT_EVIDENCE = "NO_CONFLICT_EVIDENCE"
NO_PERMISSION_EVIDENCE = "NO_PERMISSION_EVIDENCE"
NO_APPROVAL_EVIDENCE = "NO_APPROVAL_EVIDENCE"
NO_OPERATION_EVIDENCE = "NO_OPERATION_EVIDENCE"
NO_WORKFLOW_EVIDENCE = "NO_WORKFLOW_EVIDENCE"
NO_WORKFLOW_DURATION_EVIDENCE = "NO_WORKFLOW_DURATION_EVIDENCE"
NO_RULE_EVIDENCE = "NO_RULE_EVIDENCE"
NO_RESOURCE_EVIDENCE = "NO_RESOURCE_EVIDENCE"
NO_TRANSFER_EVIDENCE = "NO_TRANSFER_EVIDENCE"
NO_KNOWLEDGE_REUSE_EVIDENCE = "NO_KNOWLEDGE_REUSE_EVIDENCE"
NO_AVOIDED_QUESTION_EVIDENCE = "NO_AVOIDED_QUESTION_EVIDENCE"
NO_DUPLICATE_PREVENTION_EVIDENCE = "NO_DUPLICATE_PREVENTION_EVIDENCE"
NO_ERROR_EVIDENCE = "NO_ERROR_EVIDENCE"
NO_SESSION_EVIDENCE = "NO_SESSION_EVIDENCE"
NO_EXTERNAL_DOMAIN_EVIDENCE = "NO_EXTERNAL_DOMAIN_EVIDENCE"


# ── Canonical permission / approval evidence types ───────────────────────────

_PERMISSION_DECISION_KINDS = frozenset(
    {"allow", "deny", "abstain", "approval_required"}
)


# ── Evidence aggregate ──────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class DomainObservabilityEvidence:
    """Frozen, reference-only input aggregate for observability projection.

    This is not a registry, not a store and is never persisted. It simply
    carries whatever canonical evidence a caller already owns so the pure
    calculator can derive exact metrics from it.
    """

    registry_definitions: tuple[DomainDefinition, ...] = ()
    registry_records: tuple[DomainRegistryRecord, ...] = ()
    load_results: tuple[DomainLoadResult, ...] = ()
    resolution_results: tuple[DomainResolutionResult, ...] = ()
    compositions: tuple[DomainComposition, ...] = ()
    conflict_results: tuple[DomainConflictCase, ...] = ()
    events: tuple[DomainEvent, ...] = ()
    traces: tuple[DomainTrace, ...] = ()
    sessions: tuple[DomainSessionContext, ...] = ()
    session_resume_results: tuple[DomainSessionResumeResult, ...] = ()
    permission_evidence: tuple[DomainOperationPermissionDecision, ...] = ()
    approval_evidence: tuple[PermissionApprovalRequirement, ...] = ()
    operation_evidence: tuple[DomainOperationResult, ...] = ()
    workflow_evidence: tuple[DomainWorkflowResult, ...] = ()
    rule_evidence: tuple[DomainRuleExecutionResult, ...] = ()
    resource_evidence: tuple[DomainResourceResolution | DomainResourceBinding, ...] = ()
    cross_domain_transfers: tuple[CrossDomainContextTransfer, ...] = ()

    def __post_init__(self) -> None:
        for name in (
            "registry_definitions",
            "registry_records",
            "load_results",
            "resolution_results",
            "compositions",
            "conflict_results",
            "events",
            "traces",
            "sessions",
            "session_resume_results",
            "permission_evidence",
            "approval_evidence",
            "operation_evidence",
            "workflow_evidence",
            "rule_evidence",
            "resource_evidence",
            "cross_domain_transfers",
        ):
            value = getattr(self, name)
            if value is None:
                raise InvalidDomainObservabilityEvidenceError(
                    f"{name} must be a tuple", field=name
                )
            object.__setattr__(self, name, tuple(value))
        _validate_evidence_element_types(self)


# ── Evidence identity helpers ────────────────────────────────────────────────


def _validate_evidence_element_types(evidence: DomainObservabilityEvidence) -> None:
    """Runtime-validate evidence tuple element types against canonical contracts.

    Type annotations are not runtime validation. Every evidence field whose
    canonical element contract exists must reject malformed elements in
    ``__post_init__``: invalid elements fail closed with a safe
    ``InvalidDomainObservabilityEvidenceError`` instead of silently passing a
    hint-only declared type and raising unrelated ``AttributeError``/
    ``TypeError`` from later normalization. Malformed content is never echoed.
    """
    _check_elements(
        evidence.registry_definitions,
        (DomainDefinition,),
        field="registry_definitions",
        source_type="DomainDefinition",
    )
    _check_elements(
        evidence.registry_records,
        (DomainRegistryRecord,),
        field="registry_records",
        source_type="DomainRegistryRecord",
    )
    _check_elements(
        evidence.load_results,
        (DomainLoadResult,),
        field="load_results",
        source_type="DomainLoadResult",
    )
    _check_elements(
        evidence.resolution_results,
        (DomainResolutionResult,),
        field="resolution_results",
        source_type="DomainResolutionResult",
    )
    _check_elements(
        evidence.compositions,
        (DomainComposition,),
        field="compositions",
        source_type="DomainComposition",
    )
    _check_elements(
        evidence.conflict_results,
        (DomainConflictCase,),
        field="conflict_results",
        source_type="DomainConflictCase",
    )
    _check_elements(
        evidence.events,
        (DomainEvent,),
        field="events",
        source_type="DomainEvent",
    )
    _check_elements(
        evidence.traces,
        (DomainTrace,),
        field="traces",
        source_type="DomainTrace",
    )
    _check_elements(
        evidence.sessions,
        (DomainSessionContext,),
        field="sessions",
        source_type="DomainSessionContext",
    )
    _check_elements(
        evidence.session_resume_results,
        (DomainSessionResumeResult,),
        field="session_resume_results",
        source_type="DomainSessionResumeResult",
    )
    _check_elements(
        evidence.permission_evidence,
        (DomainOperationPermissionDecision,),
        field="permission_evidence",
        source_type="DomainOperationPermissionDecision",
    )
    _check_elements(
        evidence.approval_evidence,
        (PermissionApprovalRequirement,),
        field="approval_evidence",
        source_type="PermissionApprovalRequirement",
    )
    _check_elements(
        evidence.operation_evidence,
        (DomainOperationResult,),
        field="operation_evidence",
        source_type="DomainOperationResult",
    )
    _check_elements(
        evidence.workflow_evidence,
        (DomainWorkflowResult,),
        field="workflow_evidence",
        source_type="DomainWorkflowResult",
    )
    _check_elements(
        evidence.rule_evidence,
        (DomainRuleExecutionResult,),
        field="rule_evidence",
        source_type="DomainRuleExecutionResult",
    )
    _check_elements(
        evidence.resource_evidence,
        (DomainResourceResolution, DomainResourceBinding),
        field="resource_evidence",
        source_type="DomainResourceResolution|DomainResourceBinding",
    )
    _check_elements(
        evidence.cross_domain_transfers,
        (CrossDomainContextTransfer,),
        field="cross_domain_transfers",
        source_type="CrossDomainContextTransfer",
    )
    _validate_permission_identity_conflicts(evidence.permission_evidence)
    _validate_approval_identity_conflicts(evidence.approval_evidence)


def _approval_constraints_items(
    constraints: Mapping[str, Any],
) -> tuple[tuple[str, Any], ...]:
    """Deterministic canonical comparison payload for approval constraints.

    ``PermissionApprovalRequirement.constraints`` is validated, canonicalized
    and frozen by the public contract; the public ``to_dict()`` materializes
    plain JSON-safe contents (frozensets/sets become sorted lists in canonical
    order), so key-sorting the items compares canonical normalized contents —
    never object identity and never ``repr()``. Keys are unique strings, so
    the key sort is deterministic and never compares mixed-type values.
    """
    return tuple(sorted(constraints.items()))


def _validate_approval_identity_conflicts(
    requirements: Sequence[Any],
) -> None:
    """Fail closed on materially conflicting approvals for one requirement_id.

    The canonical observability occurrence identity of a
    ``PermissionApprovalRequirement`` is ``requirement_id``. Two canonical
    requirements carrying that same identity but materially different public
    approval semantics (action, actor, session, domain, resource, operation,
    workflow, node, scope, one-time/reusable, expiry, fingerprint,
    reason_code, risk, purpose, sensitivity, constraints) are conflicting
    evidence for one identity and must be rejected before any
    projection/occurrence grouping. Identical duplicates collapse to one;
    different requirement_ids remain distinct occurrences. The error carries
    only the safe source type and identity — never actor/session payload,
    fingerprint contents, risk/sensitivity/purpose/constraint detail or a
    repr of the object.
    """
    seen: dict[str, tuple[Any, ...]] = {}
    for requirement in requirements:
        if not isinstance(requirement, PermissionApprovalRequirement):
            continue  # element type failures are reported by _check_elements
        identity = requirement.requirement_id
        material = (
            requirement.action,
            requirement.actor_id,
            requirement.session_id,
            requirement.domain_id,
            requirement.resource_id,
            requirement.resource_kind,
            requirement.operation_id,
            requirement.operation_version,
            requirement.workflow_id,
            requirement.workflow_version,
            requirement.node_id,
            requirement.source_domain,
            requirement.target_domain,
            requirement.fingerprint,
            requirement.expires_at,
            requirement.scope,
            requirement.one_time,
            requirement.reusable,
            requirement.reason_code,
            requirement.risk,
            requirement.purpose,
            requirement.sensitivity,
            _approval_constraints_items(requirement.constraints),
        )
        previous = seen.get(identity)
        if previous is not None and previous != material:
            raise InvalidDomainObservabilityEvidenceError(
                "conflicting approval requirement evidence for the same "
                "canonical identity "
                f"(source=PermissionApprovalRequirement "
                f"id={identity})",
                field="approval_evidence",
                details={
                    "source_type": "PermissionApprovalRequirement",
                    "source_id": identity,
                },
            )
        seen[identity] = material


def _validate_permission_identity_conflicts(
    decisions: Sequence[Any],
) -> None:
    """Fail closed on contradictory decisions for one canonical identity.

    The synthetic canonical observability identity of a
    ``DomainOperationPermissionDecision`` is ``operation_id`` +
    ``operation_version``. Two canonical decisions carrying that same
    identity but contradictory ``decision`` values (for example ALLOW and
    DENY) are conflicting evidence for one identity and must be rejected
    before any projection/occurrence grouping. Identical duplicates collapse
    to one; distinct versions remain distinct identities. The error carries
    only the safe source type and identity — never the decision value or
    reason text.
    """
    decision_by_identity: dict[tuple[str, str], PermissionOutcome] = {}
    for index, decision in enumerate(decisions):
        if not isinstance(decision, DomainOperationPermissionDecision):
            continue  # element type failures are reported by _check_elements
        identity = (decision.operation_id, decision.operation_version)
        seen = decision_by_identity.get(identity)
        if seen is not None and seen is not decision.decision:
            raise InvalidDomainObservabilityEvidenceError(
                "conflicting permission decision evidence for the same "
                "canonical identity "
                f"(source=DomainOperationPermissionDecision "
                f"id={decision.operation_id}@{decision.operation_version})",
                field="permission_evidence",
                details={
                    "source_type": "DomainOperationPermissionDecision",
                    "source_id": (
                        f"{decision.operation_id}@{decision.operation_version}"
                    ),
                },
            )
        decision_by_identity[identity] = decision.decision


def _check_elements(
    items: Sequence[Any],
    allowed: tuple[type, ...],
    *,
    field: str,
    source_type: str,
) -> None:
    for index, item in enumerate(items):
        if isinstance(item, allowed):
            continue
        raise InvalidDomainObservabilityEvidenceError(
            f"{field} element {index} is not valid canonical {source_type} evidence",
            field=field,
            details={
                "source_type": source_type,
                "source_id": f"{field}[{index}]",
            },
        )


class _EvidenceIdentity:
    """Expose authoritative stable IDs for each canonical evidence type."""

    @staticmethod
    def event_id(event: DomainEvent) -> str:
        return event.event_id

    @staticmethod
    def trace_id(trace: DomainTrace) -> str:
        return trace.id

    @staticmethod
    def resolution_id(result: DomainResolutionResult) -> str:
        return result.id

    @staticmethod
    def composition_id(composition: DomainComposition) -> str:
        return composition.id

    @staticmethod
    def conflict_id(conflict: DomainConflictCase) -> str:
        return conflict.id

    @staticmethod
    def operation_id(result: DomainOperationResult) -> str:
        return result.result_id

    @staticmethod
    def workflow_id(result: DomainWorkflowResult) -> str:
        return result.run_id

    @staticmethod
    def rule_execution_id(result: DomainRuleExecutionResult) -> str:
        return result.id

    @staticmethod
    def session_id(session: DomainSessionContext) -> str:
        return session.session_id

    @staticmethod
    def resume_id(result: DomainSessionResumeResult) -> str:
        return result.session_id

    @staticmethod
    def transfer_id(transfer: CrossDomainContextTransfer) -> str:
        return _transfer_occurrence_id(transfer)


def _canonical_domain_id(value: DomainId | str | None) -> str | None:
    if value is None:
        return None
    if isinstance(value, DomainId):
        return str(value)
    return str(value)


def _evidence_ids(
    evidence: DomainObservabilityEvidence,
) -> dict[str, tuple[str, ...]]:
    """Authoritative identity groups for the snapshot's evidence reference IDs."""
    return {
        "events": tuple(
            sorted({_EvidenceIdentity.event_id(event) for event in evidence.events})
        ),
        "traces": tuple(
            sorted({_EvidenceIdentity.trace_id(trace) for trace in evidence.traces})
        ),
        "sessions": tuple(
            sorted(
                {_EvidenceIdentity.session_id(session) for session in evidence.sessions}
            )
        ),
    }


def _deduplicate_events(events: Sequence[DomainEvent]) -> tuple[DomainEvent, ...]:
    seen: dict[str, DomainEvent] = {}
    for event in events:
        identity = _EvidenceIdentity.event_id(event)
        if identity in seen:
            expected = seen[identity]
            if (
                expected.event_type != event.event_type
                or expected.domain_id != event.domain_id
                or expected.occurred_at != event.occurred_at
                or expected.sensitivity != event.sensitivity
            ):
                raise InvalidDomainObservabilityEvidenceError(
                    "duplicate event ID with materially different public content",
                    field="events",
                    details={
                        "source_type": "DomainEvent",
                        "source_id": identity,
                    },
                )
            continue
        seen[identity] = event
    return tuple(sorted(seen.values(), key=lambda item: item.event_id))


def _deduplicate_results(
    results: Sequence[DomainResolutionResult],
) -> tuple[DomainResolutionResult, ...]:
    seen: dict[str, DomainResolutionResult] = {}
    for result in results:
        identity = _EvidenceIdentity.resolution_id(result)
        if identity in seen:
            expected = seen[identity]
            if (
                expected.status != result.status
                or expected.primary_domain != result.primary_domain
                or expected.confidence != result.confidence
                or expected.fallback_used != result.fallback_used
            ):
                raise InvalidDomainObservabilityEvidenceError(
                    "duplicate resolution ID with materially different public content",
                    field="resolution_results",
                    details={
                        "source_type": "DomainResolutionResult",
                        "source_id": identity,
                    },
                )
            continue
        seen[identity] = result
    return tuple(sorted(seen.values(), key=lambda item: item.id))


def _deduplicate_traces(traces: Sequence[DomainTrace]) -> tuple[DomainTrace, ...]:
    seen: dict[str, DomainTrace] = {}
    for trace in traces:
        identity = _EvidenceIdentity.trace_id(trace)
        if identity in seen:
            expected = seen[identity]
            if (
                expected.status != trace.status
                or expected.primary_domain != trace.primary_domain
                or expected.duration_ms != trace.duration_ms
            ):
                raise InvalidDomainObservabilityEvidenceError(
                    "duplicate trace ID with materially different public content",
                    field="traces",
                    details={
                        "source_type": "DomainTrace",
                        "source_id": identity,
                    },
                )
            continue
        seen[identity] = trace
    return tuple(sorted(seen.values(), key=lambda item: item.id))


def _deduplicate_compositions(
    compositions: Sequence[DomainComposition],
) -> tuple[DomainComposition, ...]:
    seen: dict[str, DomainComposition] = {}
    for composition in compositions:
        identity = _EvidenceIdentity.composition_id(composition)
        if identity in seen:
            expected = seen[identity]
            if (
                expected.status != composition.status
                or expected.primary_domain != composition.primary_domain
                or expected.supporting_domains != composition.supporting_domains
            ):
                raise InvalidDomainObservabilityEvidenceError(
                    "duplicate composition ID with materially different public content",
                    field="compositions",
                    details={
                        "source_type": "DomainComposition",
                        "source_id": identity,
                    },
                )
            continue
        seen[identity] = composition
    return tuple(sorted(seen.values(), key=lambda item: item.id))


def _deduplicate_load_results(
    loads: Sequence[DomainLoadResult],
) -> tuple[DomainLoadResult, ...]:
    seen: dict[tuple[str, str], DomainLoadResult] = {}
    for load in loads:
        identity = (
            load.candidate.candidate_id,
            load.loaded_at.isoformat(),
        )
        if identity in seen:
            expected = seen[identity]
            if expected.status != load.status or expected.errors != load.errors:
                raise InvalidDomainObservabilityEvidenceError(
                    "duplicate load result ID with materially different public content",
                    field="load_results",
                    details={
                        "source_type": "DomainLoadResult",
                        "source_id": identity[0],
                    },
                )
            continue
        seen[identity] = load
    return tuple(
        sorted(
            seen.values(),
            key=lambda item: (item.candidate.candidate_id, item.loaded_at),
        )
    )


def _deduplicate_generic(
    items: Sequence[Any],
    *,
    identity_fn: Any,
    source_type: str,
    field_name: str,
) -> tuple[Any, ...]:
    seen: dict[str, Any] = {}
    for item in items:
        identity = str(identity_fn(item))
        if identity in seen:
            expected = seen[identity]
            if expected != item:
                raise InvalidDomainObservabilityEvidenceError(
                    f"duplicate evidence ID with materially different public "
                    f"content (source={source_type} id={identity})",
                    field=field_name,
                    details={
                        "source_type": source_type,
                        "source_id": identity,
                    },
                )
            continue
        seen[identity] = item
    return tuple(sorted(seen.values(), key=lambda item: str(identity_fn(item))))


def _deduplicate_conflicts(
    conflicts: Sequence[DomainConflictCase],
) -> tuple[DomainConflictCase, ...]:
    return _deduplicate_generic(
        conflicts,
        identity_fn=_EvidenceIdentity.conflict_id,
        source_type="DomainConflictCase",
        field_name="conflict_results",
    )


def _deduplicate_operations(
    results: Sequence[DomainOperationResult],
) -> tuple[DomainOperationResult, ...]:
    return _deduplicate_generic(
        results,
        identity_fn=_EvidenceIdentity.operation_id,
        source_type="DomainOperationResult",
        field_name="operation_evidence",
    )


def _deduplicate_workflows(
    results: Sequence[DomainWorkflowResult],
) -> tuple[DomainWorkflowResult, ...]:
    return _deduplicate_generic(
        results,
        identity_fn=_EvidenceIdentity.workflow_id,
        source_type="DomainWorkflowResult",
        field_name="workflow_evidence",
    )


def _deduplicate_rules(
    results: Sequence[DomainRuleExecutionResult],
) -> tuple[DomainRuleExecutionResult, ...]:
    return _deduplicate_generic(
        results,
        identity_fn=_EvidenceIdentity.rule_execution_id,
        source_type="DomainRuleExecutionResult",
        field_name="rule_evidence",
    )


def _deduplicate_sessions(
    sessions: Sequence[DomainSessionContext],
) -> tuple[DomainSessionContext, ...]:
    return _deduplicate_generic(
        sessions,
        identity_fn=_EvidenceIdentity.session_id,
        source_type="DomainSessionContext",
        field_name="sessions",
    )


def _deduplicate_resumes(
    resumes: Sequence[DomainSessionResumeResult],
) -> tuple[DomainSessionResumeResult, ...]:
    return _deduplicate_generic(
        resumes,
        identity_fn=_EvidenceIdentity.resume_id,
        source_type="DomainSessionResumeResult",
        field_name="session_resume_results",
    )


def _transfer_occurrence_id(transfer: CrossDomainContextTransfer) -> str:
    """Deterministic occurrence identity for one canonical transfer.

    The canonical engine reuses the same finding/reference ``identifier``
    across coordination iterations (``iteration`` distinguishes transfer
    occurrences). The identity therefore binds the canonical occurrence
    dimensions exposed by ``CrossDomainContextTransfer``:

    ``source_domain / target_domain / kind / identifier / iteration``

    Raw ``value``, free-text ``reason`` and private payload content are never
    part of a public occurrence identity.
    """
    return "|".join(
        (
            "transfer",
            str(transfer.source_domain),
            str(transfer.target_domain),
            transfer.kind,
            transfer.identifier,
            str(transfer.iteration),
        )
    )


def _deduplicate_transfers(
    transfers: Sequence[CrossDomainContextTransfer],
) -> tuple[CrossDomainContextTransfer, ...]:
    """Deduplicate transfers by their canonical occurrence identity.

    The stable occurrence identity of a CrossDomainContextTransfer is the
    derived occurrence identity over
    ``source_domain / target_domain / kind / identifier / iteration`` — NOT
    the `identifier` alone, because the canonical engine reuses an identifier
    across iterations. Two transfers with the same identifier but distinct
    iterations are distinct occurrences and are both retained; two transfers
    with the same occurrence identity but conflicting canonical content fail
    closed.
    """
    seen: dict[str, CrossDomainContextTransfer] = {}
    for transfer in transfers:
        identity = _transfer_occurrence_id(transfer)
        if identity in seen:
            expected = seen[identity]
            if expected != transfer:
                raise InvalidDomainObservabilityEvidenceError(
                    f"duplicate transfer occurrence with materially different "
                    f"public content (source=CrossDomainContextTransfer "
                    f"id={transfer.identifier})",
                    field="cross_domain_transfers",
                    details={
                        "source_type": "CrossDomainContextTransfer",
                        "source_id": transfer.identifier,
                    },
                )
            continue
        seen[identity] = transfer
    return tuple(
        sorted(
            seen.values(),
            key=lambda item: (
                str(item.source_domain),
                str(item.target_domain),
                item.kind,
                item.identifier,
                item.iteration,
            ),
        )
    )


def _normalize_evidence(
    evidence: DomainObservabilityEvidence,
) -> DomainObservabilityEvidence:
    """Deduplicate all evidence by stable authoritative IDs before counting."""
    return DomainObservabilityEvidence(
        registry_definitions=evidence.registry_definitions,
        registry_records=evidence.registry_records,
        load_results=_deduplicate_load_results(evidence.load_results),
        resolution_results=_deduplicate_results(evidence.resolution_results),
        compositions=_deduplicate_compositions(evidence.compositions),
        conflict_results=_deduplicate_conflicts(evidence.conflict_results),
        events=_deduplicate_events(evidence.events),
        traces=_deduplicate_traces(evidence.traces),
        sessions=_deduplicate_sessions(evidence.sessions),
        session_resume_results=_deduplicate_resumes(evidence.session_resume_results),
        permission_evidence=evidence.permission_evidence,
        approval_evidence=evidence.approval_evidence,
        operation_evidence=_deduplicate_operations(evidence.operation_evidence),
        workflow_evidence=_deduplicate_workflows(evidence.workflow_evidence),
        rule_evidence=_deduplicate_rules(evidence.rule_evidence),
        resource_evidence=evidence.resource_evidence,
        cross_domain_transfers=_deduplicate_transfers(evidence.cross_domain_transfers),
    )


# ── Pure calculator ──────────────────────────────────────────────────────────


def _unavailable(name: str, unit: str, reason: str) -> DomainMetricMeasurement:
    return DomainMetricMeasurement(
        name=name,
        status=DomainMetricStatus.UNAVAILABLE,
        unit=unit,
        unavailable_reason=reason,
    )


_COUNT = "count"
_MS = "ms"
_RATIO = "ratio"


def _observed_scalar(
    name: str,
    unit: str,
    value: float,
    *,
    evidence_reference_ids: Sequence[str] = (),
) -> DomainMetricMeasurement:
    return DomainMetricMeasurement(
        name=name,
        status=DomainMetricStatus.OBSERVED,
        unit=unit,
        value=value,
        evidence_reference_ids=tuple(evidence_reference_ids),
    )


def _observed_buckets(
    name: str,
    unit: str,
    buckets: Sequence[DomainMetricBucket],
    *,
    evidence_reference_ids: Sequence[str] = (),
) -> DomainMetricMeasurement:
    return DomainMetricMeasurement(
        name=name,
        status=DomainMetricStatus.OBSERVED,
        unit=unit,
        buckets=tuple(buckets),
        evidence_reference_ids=tuple(evidence_reference_ids),
    )


def _mean(values: Sequence[int | float]) -> float | None:
    samples = [value for value in values if isinstance(value, (int, float))]
    if not samples:
        return None
    return sum(samples) / len(samples)


def _counts_by_domain(values: Sequence[str | None]) -> dict[str, int]:
    result: dict[str, int] = {}
    for value in values:
        if value is None:
            continue
        result[value] = result.get(value, 0) + 1
    return result


def _buckets_from_counts(counts: Mapping[str, int]) -> tuple[DomainMetricBucket, ...]:
    return tuple(
        DomainMetricBucket(key=key, value=value)
        for key, value in sorted(counts.items())
    )


def _active_external_domains(
    records: Sequence[DomainRegistryRecord],
) -> tuple[str, ...]:
    external: list[str] = []
    for record in records:
        if (
            record.status == DomainStatus.ACTIVE
            and record.definition.kind.value == "external"
        ):
            external.append(record.domain_id)
    return tuple(sorted(external))


class DomainMetricsCalculator:
    """Pure calculator producing deterministic DomainMetricsSnapshot."""

    def calculate(
        self,
        evidence: DomainObservabilityEvidence,
        *,
        generated_at: datetime,
    ) -> DomainMetricsSnapshot:
        normalized = _normalize_evidence(evidence)
        ids = _evidence_ids(normalized)

        event_ids, trace_ids, session_ids = (
            ids["events"],
            ids["traces"],
            ids["sessions"],
        )

        measurements: list[DomainMetricMeasurement] = []

        # domains.installed
        registry_definitions = normalized.registry_definitions
        installed_ids: set[str] = set()
        for definition in registry_definitions:
            installed_ids.add(str(definition.id))
        for record in normalized.registry_records:
            installed_ids.add(record.domain_id)
        if installed_ids:
            measurements.append(
                _observed_scalar(
                    "domains.installed",
                    _COUNT,
                    len(installed_ids),
                    evidence_reference_ids=tuple(sorted(installed_ids)),
                )
            )
        else:
            measurements.append(
                _unavailable("domains.installed", _COUNT, NO_REGISTRY_EVIDENCE)
            )

        # domains.active
        registry_records = normalized.registry_records
        if registry_records:
            active_ids = tuple(
                sorted(
                    {
                        record.domain_id
                        for record in registry_records
                        if record.status == DomainStatus.ACTIVE
                        or record.status == DomainStatus.DEGRADED
                    }
                )
            )
            measurements.append(
                _observed_scalar(
                    "domains.active",
                    _COUNT,
                    len(active_ids),
                    evidence_reference_ids=active_ids,
                )
            )
        else:
            measurements.append(
                _unavailable("domains.active", _COUNT, NO_REGISTRY_EVIDENCE)
            )

        # loading.duration.mean_ms
        load_results = normalized.load_results
        explicit_durations: list[int | float] = []
        for load in load_results:
            raw = load.metadata.get("duration_ms")
            if isinstance(raw, (int, float)) and not isinstance(raw, bool):
                explicit_durations.append(raw)
        mean_load_duration = _mean(explicit_durations)
        if mean_load_duration is not None:
            measurements.append(
                _observed_scalar(
                    "loading.duration.mean_ms",
                    _MS,
                    mean_load_duration,
                    evidence_reference_ids=tuple(
                        sorted({load.candidate.candidate_id for load in load_results})
                    ),
                )
            )
        elif load_results:
            measurements.append(
                _unavailable("loading.duration.mean_ms", _MS, NO_LOAD_DURATION_EVIDENCE)
            )
        else:
            measurements.append(
                _unavailable("loading.duration.mean_ms", _MS, NO_LOAD_EVIDENCE)
            )

        # loading.failures
        if load_results:
            failed_loads = tuple(
                sorted(
                    {
                        f"{load.candidate.candidate_id}@{load.loaded_at.isoformat()}"
                        for load in load_results
                        if load.status
                        in (DomainLoadStatus.FAILED, DomainLoadStatus.REJECTED)
                    }
                )
            )
            measurements.append(
                _observed_scalar(
                    "loading.failures",
                    _COUNT,
                    len(failed_loads),
                    evidence_reference_ids=failed_loads,
                )
            )
        else:
            measurements.append(
                _unavailable("loading.failures", _COUNT, NO_LOAD_EVIDENCE)
            )

        # resolution.decisions_by_domain
        resolution_results = normalized.resolution_results
        if resolution_results:
            decisions = _counts_by_domain(
                tuple(
                    _canonical_domain_id(result.primary_domain)
                    for result in resolution_results
                    if result.status == DomainResolutionStatus.RESOLVED
                )
            )
            reference_ids = tuple(sorted({item.id for item in resolution_results}))
            if decisions:
                measurements.append(
                    _observed_buckets(
                        "resolution.decisions_by_domain",
                        _COUNT,
                        _buckets_from_counts(decisions),
                        evidence_reference_ids=reference_ids,
                    )
                )
            else:
                # Authoritative resolution evidence exists and zero RESOLVED
                # decisions occurred: this is observed zero, not unavailable.
                measurements.append(
                    _observed_scalar(
                        "resolution.decisions_by_domain",
                        _COUNT,
                        0,
                        evidence_reference_ids=reference_ids,
                    )
                )
        else:
            measurements.append(
                _unavailable(
                    "resolution.decisions_by_domain", _COUNT, NO_RESOLUTION_EVIDENCE
                )
            )

        # resolution.confidence.mean
        confidences = [
            float(result.confidence)
            for result in resolution_results
            if result.confidence is not None
        ]
        mean_confidence = _mean(confidences)
        if mean_confidence is not None:
            measurements.append(
                _observed_scalar(
                    "resolution.confidence.mean",
                    _RATIO,
                    mean_confidence,
                    evidence_reference_ids=tuple(
                        sorted({item.id for item in resolution_results})
                    ),
                )
            )
        elif resolution_results:
            measurements.append(
                _unavailable(
                    "resolution.confidence.mean", _RATIO, NO_RESOLUTION_EVIDENCE
                )
            )
        else:
            measurements.append(
                _unavailable(
                    "resolution.confidence.mean", _RATIO, NO_RESOLUTION_EVIDENCE
                )
            )

        # resolution.ambiguous
        if resolution_results:
            ambiguous_ids = tuple(
                sorted(
                    {
                        item.id
                        for item in resolution_results
                        if item.status == DomainResolutionStatus.AMBIGUOUS
                    }
                )
            )
            measurements.append(
                _observed_scalar(
                    "resolution.ambiguous",
                    _COUNT,
                    len(ambiguous_ids),
                    evidence_reference_ids=ambiguous_ids,
                )
            )
        else:
            measurements.append(
                _unavailable("resolution.ambiguous", _COUNT, NO_RESOLUTION_EVIDENCE)
            )

        # resolution.fallback (explicit fallback evidence only)
        if resolution_results:
            explicit_fallback_ids = tuple(
                sorted(
                    {
                        item.id
                        for item in resolution_results
                        if item.fallback_used is True
                    }
                )
            )
            # Only results that explicitly claim fallback are fallback
            # evidence. A primary domain of ``domain:general`` is NOT
            # fallback evidence, and supporting domains are NOT transfer
            # evidence. If no fallback evidence category exists at all, the
            # metric is UNAVAILABLE — absence of a fallback is not zero.
            if any(item.fallback_used is True for item in resolution_results):
                measurements.append(
                    _observed_scalar(
                        "resolution.fallback",
                        _COUNT,
                        len(explicit_fallback_ids),
                        evidence_reference_ids=explicit_fallback_ids,
                    )
                )
            else:
                measurements.append(
                    _unavailable("resolution.fallback", _COUNT, NO_FALLBACK_EVIDENCE)
                )
        else:
            measurements.append(
                _unavailable("resolution.fallback", _COUNT, NO_FALLBACK_EVIDENCE)
            )

        # execution.multi_domain + execution.domains.mean
        participant_counts: list[int] = []
        multi_domain_ids: list[str] = []
        # Source precedence for execution occurrences: a DomainTrace that
        # references a composition already represents that occurrence, so the
        # composition must not be double-counted.
        trace_referenced_composition_ids = {
            trace.references.composition_id
            for trace in normalized.traces
            if trace.status in (DomainTraceStatus.COMPLETED, DomainTraceStatus.PARTIAL)
        }
        for composition in normalized.compositions:
            if composition.status in (
                DomainCompositionStatus.COMPOSED,
                DomainCompositionStatus.PARTIAL,
            ):
                if composition.id in trace_referenced_composition_ids:
                    continue
                participants = {
                    str(composition.primary_domain),
                    *(str(domain) for domain in composition.supporting_domains),
                }
                participant_counts.append(len(participants))
                if len(participants) > 1:
                    multi_domain_ids.append(composition.id)
        for trace in normalized.traces:
            if trace.status in (DomainTraceStatus.COMPLETED, DomainTraceStatus.PARTIAL):
                participants = {
                    str(trace.primary_domain),
                    *(str(domain) for domain in trace.supporting_domains),
                }
                participant_counts.append(len(participants))
                if len(participants) > 1:
                    multi_domain_ids.append(trace.id)
        if participant_counts:
            measurements.append(
                _observed_scalar(
                    "execution.multi_domain",
                    _COUNT,
                    len(set(multi_domain_ids)),
                    evidence_reference_ids=tuple(sorted(set(multi_domain_ids))),
                )
            )
            mean_participants = sum(participant_counts) / len(participant_counts)
            measurements.append(
                _observed_scalar(
                    "execution.domains.mean",
                    _COUNT,
                    mean_participants,
                    evidence_reference_ids=tuple(sorted(set(multi_domain_ids))),
                )
            )
        else:
            measurements.append(
                _unavailable("execution.multi_domain", _COUNT, NO_EXECUTION_EVIDENCE)
            )
            measurements.append(
                _unavailable("execution.domains.mean", _COUNT, NO_EXECUTION_EVIDENCE)
            )

        # conflicts.detected
        if normalized.conflict_results:
            conflict_ids = tuple(
                sorted({item.id for item in normalized.conflict_results})
            )
            measurements.append(
                _observed_scalar(
                    "conflicts.detected",
                    _COUNT,
                    len(conflict_ids),
                    evidence_reference_ids=conflict_ids,
                )
            )
        else:
            measurements.append(
                _unavailable("conflicts.detected", _COUNT, NO_CONFLICT_EVIDENCE)
            )

        # permissions.rejected
        if normalized.permission_evidence:
            rejected_ids: list[str] = []
            for permission in normalized.permission_evidence:
                rejected_ids.extend(_permission_rejected_ids(permission))
            rejected_unique = tuple(sorted(set(rejected_ids)))
            measurements.append(
                _observed_scalar(
                    "permissions.rejected",
                    _COUNT,
                    len(rejected_unique),
                    evidence_reference_ids=rejected_unique,
                )
            )
        else:
            measurements.append(
                _unavailable("permissions.rejected", _COUNT, NO_PERMISSION_EVIDENCE)
            )

        # approvals.requested
        if normalized.approval_evidence:
            approval_ids: list[str] = []
            for approval in normalized.approval_evidence:
                approval_ids.extend(_approval_requested_ids(approval))
            approval_unique = tuple(sorted(set(approval_ids)))
            measurements.append(
                _observed_scalar(
                    "approvals.requested",
                    _COUNT,
                    len(approval_unique),
                    evidence_reference_ids=approval_unique,
                )
            )
        else:
            measurements.append(
                _unavailable("approvals.requested", _COUNT, NO_APPROVAL_EVIDENCE)
            )

        # operations.by_domain
        if normalized.operation_evidence:
            operation_counts = _counts_by_domain(
                tuple(item.domain_id for item in normalized.operation_evidence)
            )
            measurements.append(
                _observed_buckets(
                    "operations.by_domain",
                    _COUNT,
                    _buckets_from_counts(operation_counts),
                    evidence_reference_ids=tuple(
                        sorted(
                            {item.result_id for item in normalized.operation_evidence}
                        )
                    ),
                )
            )
        else:
            measurements.append(
                _unavailable("operations.by_domain", _COUNT, NO_OPERATION_EVIDENCE)
            )

        # workflows.by_domain + workflows.duration.mean_ms
        if normalized.workflow_evidence:
            workflow_counts = _counts_by_domain(
                tuple(item.domain_id for item in normalized.workflow_evidence)
            )
            measurements.append(
                _observed_buckets(
                    "workflows.by_domain",
                    _COUNT,
                    _buckets_from_counts(workflow_counts),
                    evidence_reference_ids=tuple(
                        sorted({item.run_id for item in normalized.workflow_evidence})
                    ),
                )
            )
            workflow_durations: list[int | float] = []
            for workflow in normalized.workflow_evidence:
                run = workflow.common_result.run
                started = run.started_at
                completed = run.completed_at
                if started is not None and completed is not None:
                    workflow_durations.append(
                        (completed - started).total_seconds() * 1000
                    )
            mean_workflow_duration = _mean(workflow_durations)
            if mean_workflow_duration is not None:
                measurements.append(
                    _observed_scalar(
                        "workflows.duration.mean_ms",
                        _MS,
                        mean_workflow_duration,
                        evidence_reference_ids=tuple(
                            sorted(
                                {item.run_id for item in normalized.workflow_evidence}
                            )
                        ),
                    )
                )
            else:
                measurements.append(
                    _unavailable(
                        "workflows.duration.mean_ms",
                        _MS,
                        NO_WORKFLOW_DURATION_EVIDENCE,
                    )
                )
        else:
            measurements.append(
                _unavailable("workflows.by_domain", _COUNT, NO_WORKFLOW_EVIDENCE)
            )
            measurements.append(
                _unavailable(
                    "workflows.duration.mean_ms", _MS, NO_WORKFLOW_DURATION_EVIDENCE
                )
            )

        # rules.applied_by_domain
        if normalized.rule_evidence:
            rule_counts = _counts_by_domain(
                tuple(
                    _rule_execution_domain(result)
                    for result in normalized.rule_evidence
                )
            )
            if rule_counts:
                measurements.append(
                    _observed_buckets(
                        "rules.applied_by_domain",
                        _COUNT,
                        _buckets_from_counts(rule_counts),
                        evidence_reference_ids=tuple(
                            sorted({item.id for item in normalized.rule_evidence})
                        ),
                    )
                )
            else:
                # Direct rule evidence exists but none can be attributed to a
                # Domain. No bucket may be fabricated: the trace-derived path
                # (the authoritative route) is attempted next, otherwise the
                # metric is UNAVAILABLE.
                rule_counts_by_domain = _rule_counts_from_traces(normalized.traces)
                if rule_counts_by_domain:
                    measurements.append(
                        _observed_buckets(
                            "rules.applied_by_domain",
                            _COUNT,
                            _buckets_from_counts(rule_counts_by_domain),
                            evidence_reference_ids=tuple(
                                sorted({trace.id for trace in normalized.traces})
                            ),
                        )
                    )
                else:
                    measurements.append(
                        _unavailable(
                            "rules.applied_by_domain", _COUNT, NO_RULE_EVIDENCE
                        )
                    )
        elif normalized.traces:
            # Derive applied-rule references from DomainTrace contributions.
            rule_counts_by_domain = _rule_counts_from_traces(normalized.traces)
            if rule_counts_by_domain:
                measurements.append(
                    _observed_buckets(
                        "rules.applied_by_domain",
                        _COUNT,
                        _buckets_from_counts(rule_counts_by_domain),
                        evidence_reference_ids=tuple(
                            sorted({trace.id for trace in normalized.traces})
                        ),
                    )
                )
            else:
                measurements.append(
                    _unavailable("rules.applied_by_domain", _COUNT, NO_RULE_EVIDENCE)
                )
        else:
            measurements.append(
                _unavailable("rules.applied_by_domain", _COUNT, NO_RULE_EVIDENCE)
            )

        # resources.loaded_by_domain
        # Canonical attribution lives in accepted DomainResourceBinding
        # (domain_id). A DomainResourceResolution contributes the domains of
        # its accepted bindings; a bare DomainResourceBinding contributes its
        # own domain. Bindings are deduplicated by binding id.
        bound_by_id: dict[str, DomainResourceBinding] = {}
        for item in normalized.resource_evidence:
            if isinstance(item, DomainResourceResolution):
                for binding in item.bindings:
                    bound_by_id[binding.id] = binding
            elif isinstance(item, DomainResourceBinding):
                bound_by_id.setdefault(item.id, item)
        if bound_by_id:
            resource_counts = _counts_by_domain(
                tuple(str(binding.domain_id) for binding in bound_by_id.values())
            )
            measurements.append(
                _observed_buckets(
                    "resources.loaded_by_domain",
                    _COUNT,
                    _buckets_from_counts(resource_counts),
                    evidence_reference_ids=tuple(sorted(bound_by_id)),
                )
            )
        elif normalized.resource_evidence:
            measurements.append(
                _unavailable("resources.loaded_by_domain", _COUNT, NO_RESOURCE_EVIDENCE)
            )
        else:
            measurements.append(
                _unavailable("resources.loaded_by_domain", _COUNT, NO_RESOURCE_EVIDENCE)
            )

        # cross_domain.transfers (explicit transfer evidence only)
        if normalized.cross_domain_transfers:
            transfer_ids = tuple(
                sorted(
                    {
                        _EvidenceIdentity.transfer_id(transfer)
                        for transfer in normalized.cross_domain_transfers
                    }
                )
            )
            measurements.append(
                _observed_scalar(
                    "cross_domain.transfers",
                    _COUNT,
                    len(transfer_ids),
                    evidence_reference_ids=transfer_ids,
                )
            )
        else:
            measurements.append(
                _unavailable("cross_domain.transfers", _COUNT, NO_TRANSFER_EVIDENCE)
            )

        # knowledge.reused (explicit reuse evidence only)
        if normalized.resource_evidence and _has_knowledge_reuse_evidence(
            normalized.resource_evidence
        ):
            reuse_ids = tuple(
                sorted(
                    {
                        item
                        for item in normalized.resource_evidence
                        if _is_knowledge_reuse_evidence(item)
                    }
                )
            )
            measurements.append(
                _observed_scalar(
                    "knowledge.reused",
                    _COUNT,
                    len(reuse_ids),
                    evidence_reference_ids=reuse_ids,
                )
            )
        else:
            measurements.append(
                _unavailable("knowledge.reused", _COUNT, NO_KNOWLEDGE_REUSE_EVIDENCE)
            )

        # questions.avoided_shared_context (explicit evidence only)
        measurements.append(
            _unavailable(
                "questions.avoided_shared_context",
                _COUNT,
                NO_AVOIDED_QUESTION_EVIDENCE,
            )
        )

        # duplicates.prevented (explicit evidence only)
        measurements.append(
            _unavailable(
                "duplicates.prevented", _COUNT, NO_DUPLICATE_PREVENTION_EVIDENCE
            )
        )

        # errors.by_domain_pack
        if normalized.load_results:
            error_buckets = _load_error_buckets(normalized.load_results)
            reference_ids = tuple(
                sorted(
                    {item.candidate.candidate_id for item in normalized.load_results}
                )
            )
            if error_buckets:
                measurements.append(
                    _observed_buckets(
                        "errors.by_domain_pack",
                        _COUNT,
                        error_buckets,
                        evidence_reference_ids=reference_ids,
                    )
                )
            else:
                # Load evidence exists and zero load errors occurred.
                measurements.append(
                    _observed_scalar(
                        "errors.by_domain_pack",
                        _COUNT,
                        0,
                        evidence_reference_ids=reference_ids,
                    )
                )
        else:
            measurements.append(
                _unavailable("errors.by_domain_pack", _COUNT, NO_ERROR_EVIDENCE)
            )

        # sessions.degraded
        # Degradation evidence is explicit: a session is degraded only through
        # canonical degradation-bearing resume statuses. References such as
        # approval_refs / pending_domain_question_refs are NOT degradation
        # evidence. The metric counts unique degraded sessions.
        degraded_session_ids: list[str] = []
        for resume in normalized.session_resume_results:
            if resume.status in (
                DomainSessionResumeStatus.BLOCKED,
                DomainSessionResumeStatus.INCOMPATIBLE,
                DomainSessionResumeStatus.FAILED,
                DomainSessionResumeStatus.WAITING_FOR_APPROVAL,
            ):
                degraded_session_ids.append(resume.session_id)
        if degraded_session_ids:
            degraded_unique = tuple(sorted(set(degraded_session_ids)))
            measurements.append(
                _observed_scalar(
                    "sessions.degraded",
                    _COUNT,
                    len(degraded_unique),
                    evidence_reference_ids=degraded_unique,
                )
            )
        elif normalized.sessions or normalized.session_resume_results:
            # Session evidence exists but no explicit degradation evidence.
            measurements.append(
                _unavailable("sessions.degraded", _COUNT, NO_SESSION_EVIDENCE)
            )
        else:
            measurements.append(
                _unavailable("sessions.degraded", _COUNT, NO_SESSION_EVIDENCE)
            )

        # external_domains.active
        if registry_records:
            external_ids = _active_external_domains(registry_records)
            measurements.append(
                _observed_scalar(
                    "external_domains.active",
                    _COUNT,
                    len(external_ids),
                    evidence_reference_ids=external_ids,
                )
            )
        else:
            measurements.append(
                _unavailable(
                    "external_domains.active", _COUNT, NO_EXTERNAL_DOMAIN_EVIDENCE
                )
            )

        # Canonical catalog order
        by_name = {measurement.name: measurement for measurement in measurements}
        ordered = tuple(
            by_name[name]
            for name in CANONICAL_DOMAIN_OBSERVABILITY_METRICS
            if name in by_name
        )

        return DomainMetricsSnapshot(
            generated_at=generated_at,
            measurements=ordered,
            evidence_event_ids=event_ids,
            evidence_trace_ids=trace_ids,
            evidence_session_ids=session_ids,
        )


# ── Permission / approval / helper extractors (read-only, public fields only) ─


def _permission_rejected_ids(evidence: Any) -> tuple[str, ...]:
    """Extract denied permission decision IDs from canonical decision types.

    The canonical ``DomainOperationPermissionDecision`` contract carries no
    ``decision_id``/``id``; its stable occurrence identity is the pair
    ``operation_id`` + ``operation_version``. Two DENY decisions for the same
    operation at distinct semantic versions are distinct canonical decisions.
    Only that canonical form is accepted; no generic duck-typed fallback is
    allowed.
    """
    if isinstance(evidence, DomainOperationPermissionDecision):
        if evidence.decision is PermissionOutcome.DENY:
            return (f"{evidence.operation_id}@{evidence.operation_version}",)
        return ()
    return ()


def _approval_requested_ids(evidence: Any) -> tuple[str, ...]:
    """Extract approval-request IDs from canonical approval evidence."""
    if evidence is None:
        return ()
    requirement_id = getattr(evidence, "requirement_id", None)
    if requirement_id:
        return (str(requirement_id),)
    request_id = getattr(evidence, "request_id", None)
    if request_id:
        return (str(request_id),)
    approval_request_id = getattr(evidence, "approval_request_id", None)
    if approval_request_id:
        return (str(approval_request_id),)
    return ()


def _rule_execution_domain(result: DomainRuleExecutionResult) -> str | None:
    return None


def _rule_counts_from_traces(
    traces: Sequence[DomainTrace],
) -> dict[str, int]:
    """Derive applied-rule counts per Domain from DomainTrace contributions.

    Only explicit canonical rule references (RULE_RESULT / APPLIED_RULE_TRACE)
    are counted. This is the authoritative trace-owned path for
    ``rules.applied_by_domain``.
    """
    rule_counts_by_domain: dict[str, int] = {}
    for trace in traces:
        for contribution in trace.contributions:
            domain_slug = _canonical_domain_id(contribution.domain_id)
            if domain_slug is None:
                continue
            applied = (
                reference
                for reference in contribution.references
                if reference.kind
                in (
                    DomainTraceReferenceKind.RULE_RESULT,
                    DomainTraceReferenceKind.APPLIED_RULE_TRACE,
                )
            )
            count = sum(1 for _ in applied)
            rule_counts_by_domain[domain_slug] = (
                rule_counts_by_domain.get(domain_slug, 0) + count
            )
    return rule_counts_by_domain


def _resource_evidence_domain(item: Any) -> str | None:
    """Attribution domain for a resource evidence item.

    Canonical attribution is carried by accepted ``DomainResourceBinding``
    (``domain_id``). A ``DomainResourceResolution`` contributes the domain of
    each of its bindings. No top-level ``domain_id`` duck-typing is used.
    """
    if isinstance(item, DomainResourceBinding):
        return str(item.domain_id)
    if isinstance(item, DomainResourceResolution):
        return None  # attribution comes from its bindings, not the resolution
    return None


def _resource_evidence_ids(item: Any) -> tuple[str, ...]:
    """Stable public reference IDs for a resource evidence item."""
    if isinstance(item, DomainResourceBinding):
        return (item.id,)
    if isinstance(item, DomainResourceResolution):
        return tuple(binding.id for binding in item.bindings)
    return ()


def _resource_evidence_id(item: Any) -> str:
    """Deprecated single-id helper; kept for compatibility but never falls
    back to ``id(item)`` -- process-memory addresses are forbidden as public
    evidence identity."""
    ids = _resource_evidence_ids(item)
    if ids:
        return ids[0]
    raise InvalidDomainObservabilityEvidenceError(
        "resource evidence without a canonical reference identity",
        field="resource_evidence",
    )


def _has_knowledge_reuse_evidence(items: Sequence[Any]) -> bool:
    return any(_is_knowledge_reuse_evidence(item) for item in items)


def _is_knowledge_reuse_evidence(item: Any) -> bool:
    """There is no stable canonical knowledge-reuse contract in the repository.

    Duck-typed ``reused``/``reuse_count`` objects are NOT acceptable reuse
    evidence, so this always returns False: the metric stays UNAVAILABLE.
    """
    return False


def _load_error_buckets(
    loads: Sequence[DomainLoadResult],
) -> tuple[DomainMetricBucket, ...]:
    counts: dict[str, int] = {}
    for load in loads:
        if load.status in (DomainLoadStatus.FAILED, DomainLoadStatus.REJECTED):
            counts[load.candidate.domain_id] = (
                counts.get(load.candidate.domain_id, 0) + 1
            )
    return _buckets_from_counts(counts)


def _degraded_session_ids(session: DomainSessionContext) -> tuple[str, ...]:
    """Extract degradation evidence for a session context.

    ``approval_refs`` and ``pending_domain_question_refs`` are references, not
    degradation status. A session is degraded only through explicit canonical
    degradation evidence; a plain session carrying only references is not
    degraded.
    """
    return ()


__all__ = [
    "CANONICAL_DOMAIN_OBSERVABILITY_METRICS",
    "DomainMetricsCalculator",
    "DomainObservabilityEvidence",
]
