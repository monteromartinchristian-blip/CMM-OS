"""Phase 10.34 — Domain Session Revalidation.

Pure, side-effect-free revalidation checks for Domain Session state on resumption.
Revalidates active domain definitions, version compatibility, resource/knowledge drift,
and temporal validity.
"""

from __future__ import annotations

from collections.abc import Mapping
from enum import Enum
from typing import TYPE_CHECKING

from cmm.domains.enums import DomainStatus
from cmm.domains.registry_contracts import parse_semver
from cmm.domains.session_contracts import (
    DomainSessionCheck,
    DomainSessionCheckStatus,
    DomainSessionContext,
    DomainSessionResumeRequest,
    DomainSessionResumeStatus,
)

if TYPE_CHECKING:
    from cmm.domains.knowledge_authority import DomainKnowledgeAuthority
    from cmm.domains.registry import DomainRegistry
    from cmm.domains.resource_authority import DomainResourceAuthority


def _extract_slug(domain_ref: str) -> str:
    """Extract canonical slug from a domain identifier string (e.g. 'domain:health' -> 'health')."""
    if domain_ref.startswith("domain:"):
        return domain_ref[len("domain:") :]
    return domain_ref


def _is_compatible_version(stored_version: str, current_version: str) -> bool:
    """Determine whether current_version is backward-compatible with stored_version."""
    if stored_version == current_version:
        return True
    try:
        s_semver = parse_semver(stored_version)
        c_semver = parse_semver(current_version)
        # Major version bump is breaking / incompatible
        if s_semver.major != c_semver.major:
            return False
        # If major == 0, minor version bump is breaking in SemVer
        return not (s_semver.major == 0 and s_semver.minor != c_semver.minor)
    except Exception:  # noqa: BLE001
        # Fallback: exact match if non-semver
        return stored_version == current_version


def revalidate_domains(
    context: DomainSessionContext, registry: DomainRegistry | None = None
) -> tuple[DomainSessionCheck, ...]:
    """Revalidate primary and supporting domains against registry for active status and version drift."""
    checks: list[DomainSessionCheck] = []

    if registry is None:
        checks.append(
            DomainSessionCheck(
                name="registry_check",
                status=DomainSessionCheckStatus.BLOCKING,
                message="Domain registry authority is required for resumption revalidation",
                blocking=True,
            )
        )
        return tuple(checks)

    # 1. Primary domain check
    p_slug = _extract_slug(context.primary_domain)
    p_record = registry.get_record(p_slug)

    if p_record is None:
        checks.append(
            DomainSessionCheck(
                name="primary_domain_status",
                status=DomainSessionCheckStatus.BLOCKING,
                message=f"Primary domain '{context.primary_domain}' is not registered",
                blocking=True,
                details={"primary_domain": context.primary_domain},
            )
        )
    elif p_record.status not in (DomainStatus.ACTIVE, DomainStatus.DEGRADED):
        checks.append(
            DomainSessionCheck(
                name="primary_domain_status",
                status=DomainSessionCheckStatus.BLOCKING,
                message=f"Primary domain '{context.primary_domain}' is not active (status={p_record.status.value})",
                blocking=True,
                details={
                    "primary_domain": context.primary_domain,
                    "status": p_record.status.value,
                },
            )
        )
    else:
        checks.append(
            DomainSessionCheck(
                name="primary_domain_status",
                status=DomainSessionCheckStatus.PASS,
                message=f"Primary domain '{context.primary_domain}' is active",
                blocking=False,
                details={"primary_domain": context.primary_domain},
            )
        )
        # Check version drift
        stored_v = context.domain_versions.get(
            context.primary_domain
        ) or context.domain_versions.get(p_slug)
        if stored_v is not None:
            current_v = str(p_record.definition.version)
            if stored_v == current_v:
                checks.append(
                    DomainSessionCheck(
                        name=f"domain_version_{context.primary_domain}",
                        status=DomainSessionCheckStatus.PASS,
                        message=f"Primary domain version matches ({current_v})",
                        details={
                            "domain": context.primary_domain,
                            "version": current_v,
                        },
                    )
                )
            elif _is_compatible_version(stored_v, current_v):
                checks.append(
                    DomainSessionCheck(
                        name=f"domain_version_{context.primary_domain}",
                        status=DomainSessionCheckStatus.CHANGED,
                        message=f"Primary domain version changed from {stored_v} to {current_v} (compatible)",
                        blocking=False,
                        details={
                            "domain": context.primary_domain,
                            "stored_version": stored_v,
                            "current_version": current_v,
                        },
                    )
                )
            else:
                checks.append(
                    DomainSessionCheck(
                        name=f"domain_version_{context.primary_domain}",
                        status=DomainSessionCheckStatus.INCOMPATIBLE,
                        message=f"Primary domain version changed from {stored_v} to {current_v} (incompatible major version)",
                        blocking=True,
                        details={
                            "domain": context.primary_domain,
                            "stored_version": stored_v,
                            "current_version": current_v,
                        },
                    )
                )

    # 2. Supporting domains check
    for sup in context.supporting_domains:
        s_slug = _extract_slug(sup)
        s_record = registry.get_record(s_slug)
        if s_record is None or s_record.status not in (
            DomainStatus.ACTIVE,
            DomainStatus.DEGRADED,
        ):
            checks.append(
                DomainSessionCheck(
                    name=f"supporting_domain_status_{sup}",
                    status=DomainSessionCheckStatus.CHANGED,
                    message=f"Supporting domain '{sup}' is no longer active",
                    blocking=False,
                    details={"domain": sup},
                )
            )
        else:
            checks.append(
                DomainSessionCheck(
                    name=f"supporting_domain_status_{sup}",
                    status=DomainSessionCheckStatus.PASS,
                    message=f"Supporting domain '{sup}' is active",
                    blocking=False,
                    details={"domain": sup},
                )
            )
            stored_sv = context.domain_versions.get(sup) or context.domain_versions.get(
                s_slug
            )
            if stored_sv is not None:
                curr_sv = str(s_record.definition.version)
                if stored_sv == curr_sv:
                    checks.append(
                        DomainSessionCheck(
                            name=f"domain_version_{sup}",
                            status=DomainSessionCheckStatus.PASS,
                            message=f"Supporting domain '{sup}' version matches ({curr_sv})",
                            details={"domain": sup, "version": curr_sv},
                        )
                    )
                elif _is_compatible_version(stored_sv, curr_sv):
                    checks.append(
                        DomainSessionCheck(
                            name=f"domain_version_{sup}",
                            status=DomainSessionCheckStatus.CHANGED,
                            message=f"Supporting domain '{sup}' version changed from {stored_sv} to {curr_sv} (compatible)",
                            blocking=False,
                            details={
                                "domain": sup,
                                "stored_version": stored_sv,
                                "current_version": curr_sv,
                            },
                        )
                    )
                else:
                    checks.append(
                        DomainSessionCheck(
                            name=f"domain_version_{sup}",
                            status=DomainSessionCheckStatus.INCOMPATIBLE,
                            message=f"Supporting domain '{sup}' version changed from {stored_sv} to {curr_sv} (incompatible)",
                            blocking=True,
                            details={
                                "domain": sup,
                                "stored_version": stored_sv,
                                "current_version": curr_sv,
                            },
                        )
                    )

    return tuple(checks)


def revalidate_resource_and_knowledge_drift(
    context: DomainSessionContext,
    request: DomainSessionResumeRequest | None = None,
    resource_authority: DomainResourceAuthority | None = None,
    knowledge_authority: DomainKnowledgeAuthority | None = None,
) -> tuple[DomainSessionCheck, ...]:
    """Revalidate resource and knowledge references against native authorities or snapshot metadata."""
    checks: list[DomainSessionCheck] = []

    res_versions: dict[str, str] = (
        dict(request.current_resource_versions) if request is not None else {}
    )
    know_versions: dict[str, str] = (
        dict(request.current_knowledge_versions) if request is not None else {}
    )

    now_ts = (
        request.temporal_reference
        if request is not None and request.temporal_reference is not None
        else context.updated_at
    )

    # 1. Resource references
    for domain, res_tuple in context.domain_resource_refs.items():
        for res_id in res_tuple:
            if resource_authority is not None:
                # Authoritative native evaluation
                verdict = resource_authority.resolve_resource_freshness(
                    res_id, domain=domain, at=now_ts
                )
                is_blocking = verdict.is_blocking or (
                    verdict.status
                    in (
                        DomainSessionCheckStatus.BLOCKING,
                        DomainSessionCheckStatus.INCOMPATIBLE,
                        DomainSessionCheckStatus.FAILED,
                    )
                )
                checks.append(
                    DomainSessionCheck(
                        name=f"resource_drift_{res_id}",
                        status=verdict.status,
                        message=verdict.message
                        or f"Resource '{res_id}' in domain '{domain}' evaluated by authority",
                        blocking=is_blocking,
                        details=dict(verdict.details),
                    )
                )
            elif res_id in res_versions:
                # Historical/snapshot version fallback
                v = res_versions[res_id]
                if isinstance(v, str):
                    v_upper = v.upper().strip()
                    if v_upper in ("MISSING", "INVALIDATED", "EXPIRED"):
                        checks.append(
                            DomainSessionCheck(
                                name=f"resource_drift_{res_id}",
                                status=DomainSessionCheckStatus.BLOCKING,
                                message=f"Resource '{res_id}' in domain '{domain}' is {v_upper.lower()}",
                                blocking=True,
                                details={
                                    "resource_id": res_id,
                                    "domain": domain,
                                    "status": v_upper,
                                },
                            )
                        )
                    elif (
                        v_upper in ("STALE", "DRIFT", "CHANGED")
                        or "drift" in v.lower()
                        or "changed" in v.lower()
                    ):
                        checks.append(
                            DomainSessionCheck(
                                name=f"resource_drift_{res_id}",
                                status=DomainSessionCheckStatus.DRIFT,
                                message=f"Resource '{res_id}' in domain '{domain}' has drifted",
                                blocking=False,
                                details={
                                    "resource_id": res_id,
                                    "domain": domain,
                                    "current_version": v,
                                },
                            )
                        )
                    else:
                        checks.append(
                            DomainSessionCheck(
                                name=f"resource_drift_{res_id}",
                                status=DomainSessionCheckStatus.PASS,
                                message=f"Resource '{res_id}' is current",
                                blocking=False,
                                details={
                                    "resource_id": res_id,
                                    "domain": domain,
                                    "current_version": v,
                                },
                            )
                        )
                else:
                    checks.append(
                        DomainSessionCheck(
                            name=f"resource_drift_{res_id}",
                            status=DomainSessionCheckStatus.BLOCKING,
                            message=f"Resource '{res_id}' in domain '{domain}' has invalid version metadata (fail-closed)",
                            blocking=True,
                            details={"resource_id": res_id, "domain": domain},
                        )
                    )
            else:
                # Missing/unverified authority for referenced resource -> conservative fail-closed
                checks.append(
                    DomainSessionCheck(
                        name=f"resource_drift_{res_id}",
                        status=DomainSessionCheckStatus.BLOCKING,
                        message=f"Resource '{res_id}' in domain '{domain}' has no authoritative verification (fail-closed)",
                        blocking=True,
                        details={
                            "resource_id": res_id,
                            "domain": domain,
                            "status": "UNKNOWN",
                        },
                    )
                )

    # 2. Knowledge references
    for domain, know_tuple in context.domain_knowledge_refs.items():
        for know_id in know_tuple:
            if knowledge_authority is not None:
                # Authoritative native evaluation
                k_verdict = knowledge_authority.resolve_knowledge_freshness(
                    know_id, domain=domain, at=now_ts
                )
                is_k_blocking = k_verdict.is_blocking or (
                    k_verdict.status
                    in (
                        DomainSessionCheckStatus.BLOCKING,
                        DomainSessionCheckStatus.INCOMPATIBLE,
                        DomainSessionCheckStatus.FAILED,
                    )
                )
                checks.append(
                    DomainSessionCheck(
                        name=f"knowledge_drift_{know_id}",
                        status=k_verdict.status,
                        message=k_verdict.message
                        or f"Knowledge '{know_id}' in domain '{domain}' evaluated by authority",
                        blocking=is_k_blocking,
                        details=dict(k_verdict.details),
                    )
                )
            elif know_id in know_versions:
                v = know_versions[know_id]
                if isinstance(v, str):
                    v_upper = v.upper().strip()
                    if v_upper in ("MISSING", "INVALIDATED", "EXPIRED"):
                        checks.append(
                            DomainSessionCheck(
                                name=f"knowledge_drift_{know_id}",
                                status=DomainSessionCheckStatus.BLOCKING,
                                message=f"Knowledge '{know_id}' in domain '{domain}' is {v_upper.lower()}",
                                blocking=True,
                                details={
                                    "knowledge_id": know_id,
                                    "domain": domain,
                                    "status": v_upper,
                                },
                            )
                        )
                    elif (
                        v_upper in ("STALE", "DRIFT", "CHANGED")
                        or "drift" in v.lower()
                        or "changed" in v.lower()
                    ):
                        checks.append(
                            DomainSessionCheck(
                                name=f"knowledge_drift_{know_id}",
                                status=DomainSessionCheckStatus.DRIFT,
                                message=f"Knowledge '{know_id}' in domain '{domain}' is stale/drifted",
                                blocking=False,
                                details={
                                    "knowledge_id": know_id,
                                    "domain": domain,
                                    "current_version": v,
                                },
                            )
                        )
                    else:
                        checks.append(
                            DomainSessionCheck(
                                name=f"knowledge_drift_{know_id}",
                                status=DomainSessionCheckStatus.PASS,
                                message=f"Knowledge '{know_id}' is current",
                                blocking=False,
                                details={
                                    "knowledge_id": know_id,
                                    "domain": domain,
                                    "current_version": v,
                                },
                            )
                        )
                else:
                    checks.append(
                        DomainSessionCheck(
                            name=f"knowledge_drift_{know_id}",
                            status=DomainSessionCheckStatus.BLOCKING,
                            message=f"Knowledge '{know_id}' in domain '{domain}' has invalid metadata (fail-closed)",
                            blocking=True,
                            details={"knowledge_id": know_id, "domain": domain},
                        )
                    )
            else:
                # Missing/unverified authority for referenced knowledge -> conservative fail-closed
                checks.append(
                    DomainSessionCheck(
                        name=f"knowledge_drift_{know_id}",
                        status=DomainSessionCheckStatus.BLOCKING,
                        message=f"Knowledge '{know_id}' in domain '{domain}' has no authoritative verification (fail-closed)",
                        blocking=True,
                        details={
                            "knowledge_id": know_id,
                            "domain": domain,
                            "status": "UNKNOWN",
                        },
                    )
                )

    return tuple(checks)


def revalidate_temporal(
    context: DomainSessionContext,
    request: DomainSessionResumeRequest | None = None,
) -> tuple[DomainSessionCheck, ...]:
    """Revalidate temporal reference and validity."""
    checks: list[DomainSessionCheck] = []
    if request is not None and request.temporal_reference is not None:
        ref = request.temporal_reference
        if ref < context.updated_at:
            checks.append(
                DomainSessionCheck(
                    name="temporal_validity",
                    status=DomainSessionCheckStatus.INCOMPATIBLE,
                    message="Temporal reference is in the past relative to session state",
                    blocking=True,
                    details={
                        "temporal_reference": ref.isoformat(),
                        "session_updated_at": context.updated_at.isoformat(),
                    },
                )
            )
        else:
            max_age = (
                request.metadata.get("max_session_age_seconds")
                if request.metadata
                else None
            )
            elapsed = (ref - context.updated_at).total_seconds()
            if max_age is not None and elapsed > float(max_age):
                checks.append(
                    DomainSessionCheck(
                        name="temporal_validity",
                        status=DomainSessionCheckStatus.DRIFT,
                        message=(
                            f"Session temporal freshness exceeded max age "
                            f"({elapsed:.0f}s > {max_age}s)"
                        ),
                        blocking=False,
                        details={
                            "elapsed_seconds": elapsed,
                            "max_age_seconds": max_age,
                        },
                    )
                )
            else:
                checks.append(
                    DomainSessionCheck(
                        name="temporal_validity",
                        status=DomainSessionCheckStatus.PASS,
                        message="Temporal reference is fresh and timezone-aware",
                        blocking=False,
                        details={"temporal_reference": ref.isoformat()},
                    )
                )
    else:
        checks.append(
            DomainSessionCheck(
                name="temporal_validity",
                status=DomainSessionCheckStatus.WARNING,
                message="No current temporal reference provided; temporal validity unverified",
                blocking=False,
            )
        )
    return tuple(checks)


def revalidate_session_state(
    context: DomainSessionContext,
    registry: DomainRegistry | None = None,
    request: DomainSessionResumeRequest | None = None,
    resource_authority: DomainResourceAuthority | None = None,
    knowledge_authority: DomainKnowledgeAuthority | None = None,
) -> tuple[DomainSessionCheck, ...]:
    """Run all pure revalidation checks deterministically on the domain session."""
    checks: list[DomainSessionCheck] = []
    checks.extend(revalidate_domains(context, registry))
    checks.extend(
        revalidate_resource_and_knowledge_drift(
            context,
            request,
            resource_authority=resource_authority,
            knowledge_authority=knowledge_authority,
        )
    )
    checks.extend(revalidate_temporal(context, request))
    return tuple(checks)


class DomainWorkflowClassification(str, Enum):
    """Classification of a resumed domain workflow reference."""

    CURRENT = "CURRENT"
    MIGRATED = "MIGRATED"
    REPLAN_REQUIRED = "REPLAN_REQUIRED"
    INCOMPATIBLE = "INCOMPATIBLE"
    MISSING = "MISSING"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"
    UNKNOWN = "UNKNOWN"


def revalidate_workflows(
    context: DomainSessionContext,
    workflow_statuses: Mapping[str, str] | None = None,
    workflow_migrations: Mapping[str, str] | None = None,
) -> tuple[
    tuple[DomainSessionCheck, ...],
    tuple[str, ...],
    DomainSessionResumeStatus | None,
]:
    """Revalidate and reconcile active workflow references for resumed session."""
    checks: list[DomainSessionCheck] = []
    active_refs: list[str] = []
    overall_status: DomainSessionResumeStatus | None = None

    statuses = dict(workflow_statuses) if workflow_statuses is not None else {}
    migrations = dict(workflow_migrations) if workflow_migrations is not None else {}

    for wf_id in context.active_workflow_refs:
        if wf_id in statuses:
            raw_status = statuses[wf_id]
            try:
                classification = DomainWorkflowClassification(str(raw_status).upper())
            except Exception:  # noqa: BLE001
                classification = DomainWorkflowClassification.INCOMPATIBLE
        else:
            classification = DomainWorkflowClassification.UNKNOWN

        if classification in (
            DomainWorkflowClassification.COMPLETED,
            DomainWorkflowClassification.CANCELLED,
        ):
            checks.append(
                DomainSessionCheck(
                    name=f"workflow_{wf_id}",
                    status=DomainSessionCheckStatus.PASS,
                    message=f"Workflow '{wf_id}' is {classification.value.lower()} and retired",
                    blocking=False,
                    details={
                        "workflow_id": wf_id,
                        "status": classification.value,
                    },
                )
            )
        elif classification is DomainWorkflowClassification.MIGRATED:
            target = migrations.get(wf_id, wf_id)
            active_refs.append(target)
            checks.append(
                DomainSessionCheck(
                    name=f"workflow_{wf_id}",
                    status=DomainSessionCheckStatus.CHANGED,
                    message=f"Workflow '{wf_id}' migrated to '{target}'",
                    blocking=False,
                    details={"workflow_id": wf_id, "migrated_to": target},
                )
            )
        elif classification is DomainWorkflowClassification.REPLAN_REQUIRED:
            active_refs.append(wf_id)
            checks.append(
                DomainSessionCheck(
                    name=f"workflow_{wf_id}",
                    status=DomainSessionCheckStatus.WARNING,
                    message=f"Workflow '{wf_id}' requires replanning",
                    blocking=False,
                    details={"workflow_id": wf_id},
                )
            )
            overall_status = DomainSessionResumeStatus.REPLAN_REQUIRED
        elif classification in (
            DomainWorkflowClassification.INCOMPATIBLE,
            DomainWorkflowClassification.MISSING,
            DomainWorkflowClassification.UNKNOWN,
        ):
            active_refs.append(wf_id)
            checks.append(
                DomainSessionCheck(
                    name=f"workflow_{wf_id}",
                    status=DomainSessionCheckStatus.INCOMPATIBLE,
                    message=f"Workflow '{wf_id}' is {classification.value.lower()}",
                    blocking=True,
                    details={
                        "workflow_id": wf_id,
                        "status": classification.value,
                    },
                )
            )
            overall_status = DomainSessionResumeStatus.INCOMPATIBLE
        else:
            active_refs.append(wf_id)
            checks.append(
                DomainSessionCheck(
                    name=f"workflow_{wf_id}",
                    status=DomainSessionCheckStatus.PASS,
                    message=f"Workflow '{wf_id}' is current",
                    blocking=False,
                    details={"workflow_id": wf_id},
                )
            )

    return tuple(checks), tuple(active_refs), overall_status


__all__ = [
    "DomainWorkflowClassification",
    "revalidate_domains",
    "revalidate_resource_and_knowledge_drift",
    "revalidate_session_state",
    "revalidate_temporal",
    "revalidate_workflows",
]
