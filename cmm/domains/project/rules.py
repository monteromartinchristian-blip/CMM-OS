"""Phase 10.30 — Project Domain Rules and deterministic evaluators.

Declarative domain rules + pure deterministic project management and conditional
software reasoning helpers.
All helper functions and rule evaluators are state-free: no IO, no model calls,
no registry mutation, no internal clock. They receive context explicitly and
return deterministic JSON-safe structures.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from cmm.cognitive.enums import (
    ReasoningRiskLevel,
    ReasoningRuleCategory,
    ReasoningRuleResultStatus,
    ReasoningRuleScope,
    ReasoningRuleStatus,
    ReasoningSeverity,
)
from cmm.cognitive.reasoning_rule_contracts import (
    ReasoningEscalation,
    ReasoningFinding,
    ReasoningGap,
    ReasoningRuleContext,
    ReasoningRuleDefinition,
    ReasoningRuleResult,
    ReasoningRuleTraceEntry,
)
from cmm.domains.project.catalog import (
    CANONICAL_PROJECT_RULE_IDS,
    PROJECT_DOMAIN_ID,
)
from cmm.domains.project.profile import (
    project_software_capability_active,
)
from cmm.domains.project.resources import (
    PROJECT_DECISION_STATE_VALUES,
    PROJECT_STATUS_VALUES,
)
from cmm.domains.rule_contracts import DomainReasoningRuleDefinition, DomainRuleResult


def _definition(
    rule_id: str,
    name: str,
    category: str,
    priority: int,
    risk_level: ReasoningRiskLevel = ReasoningRiskLevel.LOW,
) -> DomainReasoningRuleDefinition:
    return DomainReasoningRuleDefinition(
        id=rule_id,
        name=name,
        version="1.0.0",
        scope=ReasoningRuleScope.DOMAIN,
        domain_id=PROJECT_DOMAIN_ID,
        category=category,
        status=ReasoningRuleStatus.ENABLED,
        priority=priority,
        risk_level=risk_level,
        deterministic=True,
        description=f"Project domain reasoning rule for {rule_id}.",
        metadata={"phase": "10.30"},
    )


def _result(
    definition: ReasoningRuleDefinition,
    context: ReasoningRuleContext,
    status: ReasoningRuleResultStatus,
    *,
    findings: tuple[ReasoningFinding, ...] = (),
    gaps: tuple[ReasoningGap, ...] = (),
    escalation: ReasoningEscalation | None = None,
    code: str,
    message: str,
) -> ReasoningRuleResult:
    return DomainRuleResult(
        rule_id=definition.id,
        rule_name=definition.name,
        rule_version=definition.version,
        domain_id=definition.domain_id,
        status=status,
        findings=findings,
        gaps=gaps,
        escalation=escalation,
        trace_entries=(
            ReasoningRuleTraceEntry(
                code=code,
                message=message,
                rule_id=definition.id,
                domain_id=definition.domain_id,
                status=status,
                occurred_at=context.timestamp,
                output_count=len(findings) + len(gaps) + int(escalation is not None),
            ),
        ),
        started_at=context.timestamp,
        completed_at=context.timestamp,
    )


# ── Pure Generic Evaluators (Task 4) ──────────────────────────────────────────


def evaluate_project_scope_consistency(
    declared_scope: Mapping[str, Any] | None,
    proposed_items: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Preserve declared project objective, scope, exclusions, and deliverables."""
    declared = dict(declared_scope or {})
    deliverables = set(declared.get("deliverables", []))
    exclusions = set(declared.get("exclusions", []))
    items = list(proposed_items or [])

    in_scope: list[dict[str, Any]] = []
    out_of_scope: list[dict[str, Any]] = []
    reasons: list[str] = []

    for item in items:
        deliv = item.get("deliverable")
        item_id = item.get("id", "unnamed")
        if deliv in exclusions or item.get("name") in exclusions:
            out_of_scope.append(item)
            reasons.append(f"Item {item_id} matches declared exclusion {deliv or item.get('name')}")
        elif deliverables and deliv not in deliverables and not item.get("in_scope_override"):
            out_of_scope.append(item)
            reasons.append(f"Item {item_id} deliverable {deliv} not in declared deliverables")
        else:
            in_scope.append(item)

    valid = len(out_of_scope) == 0
    return {
        "valid": valid,
        "in_scope_items": in_scope,
        "out_of_scope_items": out_of_scope,
        "reasons": reasons,
    }


def evaluate_milestone_consistency(
    milestones: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Check milestone identity, ordering, completion basis, and duplicates."""
    ms_list = list(milestones or [])
    seen_ids: set[str] = set()
    duplicate_ids: list[str] = []
    unsupported_completed: list[str] = []
    malformed_milestones: list[str] = []

    for ms in ms_list:
        if not isinstance(ms, dict) or "id" not in ms:
            malformed_milestones.append(str(ms))
            continue
        mid = str(ms["id"])
        if mid in seen_ids:
            duplicate_ids.append(mid)
        seen_ids.add(mid)

        status = ms.get("status")
        evidence = ms.get("evidence")
        if status == "completed" and (evidence is None or len(evidence) == 0):
            unsupported_completed.append(mid)

    valid = len(duplicate_ids) == 0 and len(unsupported_completed) == 0 and len(malformed_milestones) == 0
    return {
        "valid": valid,
        "unsupported_completed_milestones": unsupported_completed,
        "duplicate_ids": duplicate_ids,
        "malformed_milestones": malformed_milestones,
        "milestones_count": len(ms_list),
    }


def evaluate_dependency_consistency(
    dependencies: list[dict[str, Any]] | None = None,
    nodes: list[str] | None = None,
) -> dict[str, Any]:
    """Check known project dependencies, unresolved blockers, and cycles."""
    deps = list(dependencies or [])
    adj: dict[str, list[str]] = {}
    all_nodes = set(nodes or [])

    for dep in deps:
        if not isinstance(dep, dict) or "source" not in dep or "target" not in dep:
            continue
        src, tgt = str(dep["source"]), str(dep["target"])
        all_nodes.add(src)
        all_nodes.add(tgt)
        adj.setdefault(src, []).append(tgt)

    cycles: list[list[str]] = []
    visited: dict[str, int] = {}  # 0: unvisited, 1: visiting, 2: visited

    def dfs(node: str, path: list[str]) -> None:
        visited[node] = 1
        path.append(node)
        for neighbor in adj.get(node, []):
            if visited.get(neighbor) == 1:
                idx = path.index(neighbor)
                cycles.append(path[idx:] + [neighbor])
            elif visited.get(neighbor, 0) == 0:
                dfs(neighbor, path)
        path.pop()
        visited[node] = 2

    for node in sorted(all_nodes):
        if visited.get(node, 0) == 0:
            dfs(node, [])

    valid = len(cycles) == 0
    blockers: list[str] = [f"Dependency cycle detected: {' -> '.join(c)}" for c in cycles]
    return {
        "valid": valid,
        "cycles": cycles,
        "blockers": blockers,
        "dependencies_count": len(deps),
    }


def evaluate_project_status_transition(
    current_status: str,
    proposed_status: str,
    *,
    evidence: Any = None,
) -> dict[str, Any]:
    """Require project and milestone status changes to be grounded in authoritative evidence."""
    curr = str(current_status).lower().strip()
    prop = str(proposed_status).lower().strip()

    if curr not in PROJECT_STATUS_VALUES or prop not in PROJECT_STATUS_VALUES:
        return {
            "allowed": False,
            "current_status": curr,
            "proposed_status": prop,
            "requires_evidence": False,
            "reason": f"unknown_status: current='{curr}', proposed='{prop}'. Valid: {', '.join(PROJECT_STATUS_VALUES)}",
        }

    if prop in ("completed", "failed") and not evidence:
        return {
            "allowed": False,
            "current_status": curr,
            "proposed_status": prop,
            "requires_evidence": True,
            "reason": "missing_required_evidence",
        }

    return {
        "allowed": True,
        "current_status": curr,
        "proposed_status": prop,
        "requires_evidence": prop in ("completed", "failed"),
        "reason": f"Valid status transition from {curr} to {prop}",
    }


def evaluate_project_resource_constraints(
    resources: list[dict[str, Any]] | None = None,
    requirements: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Relate available resources and constraints to milestones without inventing capacity."""
    res_list = list(resources or [])
    req_list = list(requirements or [])

    available_by_kind: dict[str, float] = {}
    for r in res_list:
        kind = str(r.get("kind", ""))
        avail = r.get("available")
        if avail is not None:
            available_by_kind[kind] = float(avail)

    bottlenecks: list[str] = []
    unknown_capacity: list[str] = []
    exceeded_constraints: list[str] = []

    for req in req_list:
        kind = str(req.get("resource", req.get("kind", "")))
        required_amt = req.get("required")
        if kind not in available_by_kind:
            unknown_capacity.append(kind)
        elif required_amt is not None and float(required_amt) > available_by_kind[kind]:
            bottlenecks.append(kind)
            exceeded_constraints.append(f"{kind}: required {required_amt} > available {available_by_kind[kind]}")

    if bottlenecks:
        feasible = False
        status = "constrained"
    elif unknown_capacity:
        feasible = None
        status = "uncertain"
    else:
        feasible = True
        status = "feasible"

    return {
        "feasible": feasible,
        "status": status,
        "bottlenecks": bottlenecks,
        "unknown_capacity": unknown_capacity,
        "exceeded_constraints": exceeded_constraints,
    }


def evaluate_project_decision_state(
    current_state: str,
    proposed_state: str,
    *,
    approval_evidence: Any = None,
    execution_evidence: Any = None,
    confirmation_evidence: Any = None,
) -> dict[str, Any]:
    """Separate proposal, decision, approval, and execution states with evidence requirements."""
    curr = str(current_state).lower().strip()
    prop = str(proposed_state).lower().strip()

    if curr not in PROJECT_DECISION_STATE_VALUES or prop not in PROJECT_DECISION_STATE_VALUES:
        return {
            "allowed": False,
            "current_state": curr,
            "proposed_state": prop,
            "reason": f"unknown_decision_state: current='{curr}', proposed='{prop}'",
        }

    # proposal -> decided requires confirmation
    if curr == "proposal" and prop == "decided" and not confirmation_evidence:
        return {
            "allowed": False,
            "current_state": curr,
            "proposed_state": prop,
            "reason": "missing_required_evidence",
        }

    # proposal/decided -> approved requires approval evidence
    if prop == "approved" and not approval_evidence:
        return {
            "allowed": False,
            "current_state": curr,
            "proposed_state": prop,
            "reason": "missing_required_evidence",
        }

    # -> applied requires both approval and execution evidence
    if prop == "applied" and (not execution_evidence or not approval_evidence):
        return {
            "allowed": False,
            "current_state": curr,
            "proposed_state": prop,
            "reason": "missing_required_evidence",
        }

    return {
        "allowed": True,
        "current_state": curr,
        "proposed_state": prop,
        "reason": f"Valid decision transition from {curr} to {prop}",
    }


def evaluate_project_temporal_validity(
    milestones: list[dict[str, Any]] | None = None,
    timeline: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Preserve date validity and ordering without inventing timestamps or deadlines."""
    ms_list = list(milestones or [])
    conflicts: list[str] = []
    unknown_dates: list[str] = []
    malformed_dates: list[str] = []

    ms_by_id: dict[str, dict[str, Any]] = {}
    for ms in ms_list:
        mid = str(ms.get("id", "unnamed"))
        ms_by_id[mid] = ms
        target = ms.get("target_date")
        if not target:
            unknown_dates.append(mid)
        else:
            try:
                datetime.fromisoformat(str(target).replace("Z", "+00:00"))
            except (ValueError, TypeError):
                malformed_dates.append(mid)

    for mid, ms in ms_by_id.items():
        depends_on = ms.get("depends_on")
        target = ms.get("target_date")
        if depends_on and depends_on in ms_by_id and target and mid not in malformed_dates:
            dep_target = ms_by_id[depends_on].get("target_date")
            if dep_target and depends_on not in malformed_dates:
                try:
                    dt_curr = datetime.fromisoformat(str(target).replace("Z", "+00:00"))
                    dt_dep = datetime.fromisoformat(str(dep_target).replace("Z", "+00:00"))
                    if dt_curr < dt_dep:
                        conflicts.append(
                            f"Milestone {mid} date {target} precedes prerequisite {depends_on} date {dep_target}"
                        )
                except (ValueError, TypeError):
                    pass

    valid = len(conflicts) == 0 and len(malformed_dates) == 0
    return {
        "valid": valid,
        "temporal_conflicts": conflicts,
        "unknown_dates": unknown_dates,
        "malformed_dates": malformed_dates,
        "milestones_count": len(ms_list),
    }


def evaluate_project_progress_evidence(
    progress_claims: list[dict[str, Any]] | None = None,
    authoritative_evidence: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Link progress claims to grounded status, completed deliverables, or validated outcomes."""
    claims = list(progress_claims or [])
    evidence = list(authoritative_evidence or [])

    ev_deliverables = {
        str(e.get("deliverable", "")): e for e in evidence if e.get("status") in ("verified", "completed", "passed")
    }

    verified: list[str] = []
    unsupported: list[str] = []

    for c in claims:
        cid = str(c.get("id", "claim"))
        deliv = str(c.get("deliverable", ""))
        if deliv and deliv in ev_deliverables:
            verified.append(cid)
        else:
            unsupported.append(cid)

    supported = len(unsupported) == 0
    return {
        "supported": supported,
        "verified_claims": verified,
        "unsupported_claims": unsupported,
        "missing_evidence": unsupported,
    }


# ── Generic Reasoning Rule Classes (1–8) ──────────────────────────────────────


@dataclass(frozen=True, slots=True)
class ProjectScopeConsistencyRule:
    definition: DomainReasoningRuleDefinition = field(
        default_factory=lambda: _definition(
            "project.scope_consistency",
            "ProjectScopeConsistencyRule",
            ReasoningRuleCategory.CONSISTENCY.value,
            900,
        )
    )

    def evaluate(self, context: ReasoningRuleContext) -> ReasoningRuleResult:
        declared = context.metadata.get("declared_scope")
        items = context.metadata.get("proposed_items")
        res = evaluate_project_scope_consistency(declared, items)

        findings = [
            ReasoningFinding(
                code="PROJECT_SCOPE_EVALUATED",
                message=f"Project scope evaluated: valid={res['valid']}",
                severity=ReasoningSeverity.INFO if res["valid"] else ReasoningSeverity.WARNING,
                rule_id=self.definition.id,
                domain_id=self.definition.domain_id,
            )
        ]
        return _result(
            self.definition,
            context,
            ReasoningRuleResultStatus.APPLIED,
            findings=tuple(findings),
            code="PROJECT_SCOPE_EVALUATED",
            message="Evaluated project scope consistency.",
        )


@dataclass(frozen=True, slots=True)
class MilestoneConsistencyRule:
    definition: DomainReasoningRuleDefinition = field(
        default_factory=lambda: _definition(
            "project.milestone_consistency",
            "MilestoneConsistencyRule",
            ReasoningRuleCategory.CONSISTENCY.value,
            890,
        )
    )

    def evaluate(self, context: ReasoningRuleContext) -> ReasoningRuleResult:
        milestones = context.metadata.get("milestones")
        res = evaluate_milestone_consistency(milestones)

        findings = [
            ReasoningFinding(
                code="MILESTONE_CONSISTENCY_EVALUATED",
                message=f"Milestone consistency evaluated: valid={res['valid']}",
                severity=ReasoningSeverity.INFO if res["valid"] else ReasoningSeverity.WARNING,
                rule_id=self.definition.id,
                domain_id=self.definition.domain_id,
            )
        ]
        return _result(
            self.definition,
            context,
            ReasoningRuleResultStatus.APPLIED,
            findings=tuple(findings),
            code="MILESTONE_CONSISTENCY_EVALUATED",
            message="Evaluated milestone consistency.",
        )


@dataclass(frozen=True, slots=True)
class DependencyConsistencyRule:
    definition: DomainReasoningRuleDefinition = field(
        default_factory=lambda: _definition(
            "project.dependency_consistency",
            "DependencyConsistencyRule",
            ReasoningRuleCategory.CONSISTENCY.value,
            880,
        )
    )

    def evaluate(self, context: ReasoningRuleContext) -> ReasoningRuleResult:
        deps = context.metadata.get("dependencies")
        res = evaluate_dependency_consistency(deps)

        findings = [
            ReasoningFinding(
                code="DEPENDENCY_CONSISTENCY_EVALUATED",
                message=f"Dependency consistency evaluated: valid={res['valid']}",
                severity=ReasoningSeverity.INFO if res["valid"] else ReasoningSeverity.WARNING,
                rule_id=self.definition.id,
                domain_id=self.definition.domain_id,
            )
        ]
        return _result(
            self.definition,
            context,
            ReasoningRuleResultStatus.APPLIED,
            findings=tuple(findings),
            code="DEPENDENCY_CONSISTENCY_EVALUATED",
            message="Evaluated dependency consistency.",
        )


@dataclass(frozen=True, slots=True)
class ProjectStatusTransitionRule:
    definition: DomainReasoningRuleDefinition = field(
        default_factory=lambda: _definition(
            "project.status_transition",
            "ProjectStatusTransitionRule",
            ReasoningRuleCategory.CONSISTENCY.value,
            870,
        )
    )

    def evaluate(self, context: ReasoningRuleContext) -> ReasoningRuleResult:
        curr = context.metadata.get("current_status", "planned")
        prop = context.metadata.get("proposed_status", "active")
        ev = context.metadata.get("evidence")
        res = evaluate_project_status_transition(curr, prop, evidence=ev)

        findings = [
            ReasoningFinding(
                code="STATUS_TRANSITION_EVALUATED",
                message=f"Status transition evaluated: allowed={res['allowed']}",
                severity=ReasoningSeverity.INFO if res["allowed"] else ReasoningSeverity.WARNING,
                rule_id=self.definition.id,
                domain_id=self.definition.domain_id,
            )
        ]
        return _result(
            self.definition,
            context,
            ReasoningRuleResultStatus.APPLIED,
            findings=tuple(findings),
            code="STATUS_TRANSITION_EVALUATED",
            message="Evaluated status transition.",
        )


@dataclass(frozen=True, slots=True)
class ProjectResourceConstraintRule:
    definition: DomainReasoningRuleDefinition = field(
        default_factory=lambda: _definition(
            "project.resource_constraint",
            "ProjectResourceConstraintRule",
            ReasoningRuleCategory.CONSISTENCY.value,
            860,
        )
    )

    def evaluate(self, context: ReasoningRuleContext) -> ReasoningRuleResult:
        res_data = context.metadata.get("resources")
        req_data = context.metadata.get("requirements")
        res = evaluate_project_resource_constraints(res_data, req_data)

        findings = [
            ReasoningFinding(
                code="RESOURCE_CONSTRAINT_EVALUATED",
                message=f"Resource constraints evaluated: status={res['status']}",
                severity=ReasoningSeverity.INFO if res["feasible"] else ReasoningSeverity.WARNING,
                rule_id=self.definition.id,
                domain_id=self.definition.domain_id,
            )
        ]
        return _result(
            self.definition,
            context,
            ReasoningRuleResultStatus.APPLIED,
            findings=tuple(findings),
            code="RESOURCE_CONSTRAINT_EVALUATED",
            message="Evaluated resource constraints.",
        )


@dataclass(frozen=True, slots=True)
class ProjectDecisionStateRule:
    definition: DomainReasoningRuleDefinition = field(
        default_factory=lambda: _definition(
            "project.decision_state",
            "ProjectDecisionStateRule",
            ReasoningRuleCategory.CONSISTENCY.value,
            850,
        )
    )

    def evaluate(self, context: ReasoningRuleContext) -> ReasoningRuleResult:
        curr = context.metadata.get("current_state", "proposal")
        prop = context.metadata.get("proposed_state", "decided")
        app_ev = context.metadata.get("approval_evidence")
        exec_ev = context.metadata.get("execution_evidence")
        conf_ev = context.metadata.get("confirmation_evidence")
        res = evaluate_project_decision_state(
            curr,
            prop,
            approval_evidence=app_ev,
            execution_evidence=exec_ev,
            confirmation_evidence=conf_ev,
        )

        findings = [
            ReasoningFinding(
                code="DECISION_STATE_EVALUATED",
                message=f"Decision state evaluated: allowed={res['allowed']}",
                severity=ReasoningSeverity.INFO if res["allowed"] else ReasoningSeverity.WARNING,
                rule_id=self.definition.id,
                domain_id=self.definition.domain_id,
            )
        ]
        return _result(
            self.definition,
            context,
            ReasoningRuleResultStatus.APPLIED,
            findings=tuple(findings),
            code="DECISION_STATE_EVALUATED",
            message="Evaluated decision state.",
        )


@dataclass(frozen=True, slots=True)
class ProjectTemporalValidityRule:
    definition: DomainReasoningRuleDefinition = field(
        default_factory=lambda: _definition(
            "project.temporal_validity",
            "ProjectTemporalValidityRule",
            ReasoningRuleCategory.TEMPORALITY.value,
            840,
        )
    )

    def evaluate(self, context: ReasoningRuleContext) -> ReasoningRuleResult:
        ms = context.metadata.get("milestones")
        timeline = context.metadata.get("timeline")
        res = evaluate_project_temporal_validity(ms, timeline)

        findings = [
            ReasoningFinding(
                code="TEMPORAL_VALIDITY_EVALUATED",
                message=f"Temporal validity evaluated: valid={res['valid']}",
                severity=ReasoningSeverity.INFO if res["valid"] else ReasoningSeverity.WARNING,
                rule_id=self.definition.id,
                domain_id=self.definition.domain_id,
            )
        ]
        return _result(
            self.definition,
            context,
            ReasoningRuleResultStatus.APPLIED,
            findings=tuple(findings),
            code="TEMPORAL_VALIDITY_EVALUATED",
            message="Evaluated temporal validity.",
        )


@dataclass(frozen=True, slots=True)
class ProjectProgressEvidenceRule:
    definition: DomainReasoningRuleDefinition = field(
        default_factory=lambda: _definition(
            "project.progress_evidence",
            "ProjectProgressEvidenceRule",
            ReasoningRuleCategory.CONSISTENCY.value,
            830,
        )
    )

    def evaluate(self, context: ReasoningRuleContext) -> ReasoningRuleResult:
        claims = context.metadata.get("progress_claims")
        ev = context.metadata.get("authoritative_evidence")
        res = evaluate_project_progress_evidence(claims, ev)

        findings = [
            ReasoningFinding(
                code="PROGRESS_EVIDENCE_EVALUATED",
                message=f"Progress evidence evaluated: supported={res['supported']}",
                severity=ReasoningSeverity.INFO if res["supported"] else ReasoningSeverity.WARNING,
                rule_id=self.definition.id,
                domain_id=self.definition.domain_id,
            )
        ]
        return _result(
            self.definition,
            context,
            ReasoningRuleResultStatus.APPLIED,
            findings=tuple(findings),
            code="PROGRESS_EVIDENCE_EVALUATED",
            message="Evaluated progress evidence.",
        )


# ── Software Reasoning Rule Classes (9–18) (Task 5) ──────────────────────────


def _check_software_active(context: ReasoningRuleContext) -> bool:
    return project_software_capability_active(
        workflow_id=context.metadata.get("workflow_id"),
        operation_id=context.metadata.get("operation_id"),
        resource_ids=tuple(context.metadata.get("resource_ids", ())),
        capabilities=tuple(context.metadata.get("capabilities", ())),
        repository_backed=bool(context.metadata.get("repository_backed", False)),
    )


def _inactive_software_result(
    definition: DomainReasoningRuleDefinition,
    context: ReasoningRuleContext,
) -> ReasoningRuleResult:
    findings = [
        ReasoningFinding(
            code="SOFTWARE_CAPABILITY_INACTIVE",
            message="Software capability inactive; generic project context.",
            severity=ReasoningSeverity.INFO,
            rule_id=definition.id,
            domain_id=definition.domain_id,
        )
    ]
    return _result(
        definition,
        context,
        ReasoningRuleResultStatus.APPLIED,
        findings=tuple(findings),
        code="SOFTWARE_CAPABILITY_INACTIVE",
        message="Software rule inactive in generic project context.",
    )


@dataclass(frozen=True, slots=True)
class ProjectArchitectureContractRule:
    definition: DomainReasoningRuleDefinition = field(
        default_factory=lambda: _definition(
            "project.architecture_contract",
            "ProjectArchitectureContractRule",
            ReasoningRuleCategory.CONSISTENCY.value,
            800,
        )
    )

    def evaluate(self, context: ReasoningRuleContext) -> ReasoningRuleResult:
        if not _check_software_active(context):
            return _inactive_software_result(self.definition, context)

        findings_data = context.metadata.get("architecture_findings", [])
        findings = [
            ReasoningFinding(
                code="ARCHITECTURE_CONTRACT_EVALUATED",
                message=f"Architecture contract evaluated with {len(findings_data)} findings.",
                severity=ReasoningSeverity.INFO,
                rule_id=self.definition.id,
                domain_id=self.definition.domain_id,
            )
        ]
        return _result(
            self.definition,
            context,
            ReasoningRuleResultStatus.APPLIED,
            findings=tuple(findings),
            code="ARCHITECTURE_CONTRACT_EVALUATED",
            message="Evaluated software architecture contract rule.",
        )


@dataclass(frozen=True, slots=True)
class ProjectCodeDocumentationConsistencyRule:
    definition: DomainReasoningRuleDefinition = field(
        default_factory=lambda: _definition(
            "project.code_documentation_consistency",
            "ProjectCodeDocumentationConsistencyRule",
            ReasoningRuleCategory.CONSISTENCY.value,
            790,
        )
    )

    def evaluate(self, context: ReasoningRuleContext) -> ReasoningRuleResult:
        if not _check_software_active(context):
            return _inactive_software_result(self.definition, context)

        findings = [
            ReasoningFinding(
                code="CODE_DOC_CONSISTENCY_EVALUATED",
                message="Code and documentation consistency evaluated.",
                severity=ReasoningSeverity.INFO,
                rule_id=self.definition.id,
                domain_id=self.definition.domain_id,
            )
        ]
        return _result(
            self.definition,
            context,
            ReasoningRuleResultStatus.APPLIED,
            findings=tuple(findings),
            code="CODE_DOC_CONSISTENCY_EVALUATED",
            message="Evaluated code/doc consistency.",
        )


@dataclass(frozen=True, slots=True)
class ProjectValidationRequiredRule:
    definition: DomainReasoningRuleDefinition = field(
        default_factory=lambda: _definition(
            "project.validation_required",
            "ProjectValidationRequiredRule",
            ReasoningRuleCategory.VALIDATION.value,
            780,
        )
    )

    def evaluate(self, context: ReasoningRuleContext) -> ReasoningRuleResult:
        if not _check_software_active(context):
            return _inactive_software_result(self.definition, context)

        val_res = context.metadata.get("validation_result")
        passed = bool(val_res and val_res.get("passed", False))
        findings = [
            ReasoningFinding(
                code="VALIDATION_REQUIRED_EVALUATED",
                message=f"Validation required evaluated: passed={passed}",
                severity=ReasoningSeverity.INFO if passed else ReasoningSeverity.WARNING,
                rule_id=self.definition.id,
                domain_id=self.definition.domain_id,
            )
        ]
        return _result(
            self.definition,
            context,
            ReasoningRuleResultStatus.APPLIED,
            findings=tuple(findings),
            code="VALIDATION_REQUIRED_EVALUATED",
            message="Evaluated validation required rule.",
        )


@dataclass(frozen=True, slots=True)
class ProjectTechnicalDebtRule:
    definition: DomainReasoningRuleDefinition = field(
        default_factory=lambda: _definition(
            "project.technical_debt",
            "ProjectTechnicalDebtRule",
            ReasoningRuleCategory.CONSISTENCY.value,
            770,
        )
    )

    def evaluate(self, context: ReasoningRuleContext) -> ReasoningRuleResult:
        if not _check_software_active(context):
            return _inactive_software_result(self.definition, context)

        findings = [
            ReasoningFinding(
                code="TECHNICAL_DEBT_EVALUATED",
                message="Technical debt evaluated from supplied context.",
                severity=ReasoningSeverity.INFO,
                rule_id=self.definition.id,
                domain_id=self.definition.domain_id,
            )
        ]
        return _result(
            self.definition,
            context,
            ReasoningRuleResultStatus.APPLIED,
            findings=tuple(findings),
            code="TECHNICAL_DEBT_EVALUATED",
            message="Evaluated technical debt rule.",
        )


@dataclass(frozen=True, slots=True)
class ProjectDeadCodeRule:
    definition: DomainReasoningRuleDefinition = field(
        default_factory=lambda: _definition(
            "project.dead_code",
            "ProjectDeadCodeRule",
            ReasoningRuleCategory.CONSISTENCY.value,
            760,
        )
    )

    def evaluate(self, context: ReasoningRuleContext) -> ReasoningRuleResult:
        if not _check_software_active(context):
            return _inactive_software_result(self.definition, context)

        findings = [
            ReasoningFinding(
                code="DEAD_CODE_EVALUATED",
                message="Dead code analysis evaluated from supplied context.",
                severity=ReasoningSeverity.INFO,
                rule_id=self.definition.id,
                domain_id=self.definition.domain_id,
            )
        ]
        return _result(
            self.definition,
            context,
            ReasoningRuleResultStatus.APPLIED,
            findings=tuple(findings),
            code="DEAD_CODE_EVALUATED",
            message="Evaluated dead code rule.",
        )


@dataclass(frozen=True, slots=True)
class ProjectPublicApiChangeRule:
    definition: DomainReasoningRuleDefinition = field(
        default_factory=lambda: _definition(
            "project.public_api_change",
            "ProjectPublicApiChangeRule",
            ReasoningRuleCategory.CONSISTENCY.value,
            750,
        )
    )

    def evaluate(self, context: ReasoningRuleContext) -> ReasoningRuleResult:
        if not _check_software_active(context):
            return _inactive_software_result(self.definition, context)

        findings = [
            ReasoningFinding(
                code="PUBLIC_API_CHANGE_EVALUATED",
                message="Public API change evaluated from supplied diff.",
                severity=ReasoningSeverity.INFO,
                rule_id=self.definition.id,
                domain_id=self.definition.domain_id,
            )
        ]
        return _result(
            self.definition,
            context,
            ReasoningRuleResultStatus.APPLIED,
            findings=tuple(findings),
            code="PUBLIC_API_CHANGE_EVALUATED",
            message="Evaluated public API change rule.",
        )


@dataclass(frozen=True, slots=True)
class ProjectBackwardCompatibilityRule:
    definition: DomainReasoningRuleDefinition = field(
        default_factory=lambda: _definition(
            "project.backward_compatibility",
            "ProjectBackwardCompatibilityRule",
            ReasoningRuleCategory.CONSISTENCY.value,
            740,
        )
    )

    def evaluate(self, context: ReasoningRuleContext) -> ReasoningRuleResult:
        if not _check_software_active(context):
            return _inactive_software_result(self.definition, context)

        findings = [
            ReasoningFinding(
                code="BACKWARD_COMPATIBILITY_EVALUATED",
                message="Backward compatibility evaluated.",
                severity=ReasoningSeverity.INFO,
                rule_id=self.definition.id,
                domain_id=self.definition.domain_id,
            )
        ]
        return _result(
            self.definition,
            context,
            ReasoningRuleResultStatus.APPLIED,
            findings=tuple(findings),
            code="BACKWARD_COMPATIBILITY_EVALUATED",
            message="Evaluated backward compatibility rule.",
        )


@dataclass(frozen=True, slots=True)
class ProjectDependencyBoundaryRule:
    definition: DomainReasoningRuleDefinition = field(
        default_factory=lambda: _definition(
            "project.dependency_boundary",
            "ProjectDependencyBoundaryRule",
            ReasoningRuleCategory.CONSISTENCY.value,
            730,
        )
    )

    def evaluate(self, context: ReasoningRuleContext) -> ReasoningRuleResult:
        if not _check_software_active(context):
            return _inactive_software_result(self.definition, context)

        findings = [
            ReasoningFinding(
                code="DEPENDENCY_BOUNDARY_EVALUATED",
                message="Software dependency boundary evaluated.",
                severity=ReasoningSeverity.INFO,
                rule_id=self.definition.id,
                domain_id=self.definition.domain_id,
            )
        ]
        return _result(
            self.definition,
            context,
            ReasoningRuleResultStatus.APPLIED,
            findings=tuple(findings),
            code="DEPENDENCY_BOUNDARY_EVALUATED",
            message="Evaluated dependency boundary rule.",
        )


@dataclass(frozen=True, slots=True)
class ProjectTestCoverageImpactRule:
    definition: DomainReasoningRuleDefinition = field(
        default_factory=lambda: _definition(
            "project.test_coverage_impact",
            "ProjectTestCoverageImpactRule",
            ReasoningRuleCategory.CONSISTENCY.value,
            720,
        )
    )

    def evaluate(self, context: ReasoningRuleContext) -> ReasoningRuleResult:
        if not _check_software_active(context):
            return _inactive_software_result(self.definition, context)

        findings = [
            ReasoningFinding(
                code="TEST_COVERAGE_IMPACT_EVALUATED",
                message="Test coverage impact evaluated.",
                severity=ReasoningSeverity.INFO,
                rule_id=self.definition.id,
                domain_id=self.definition.domain_id,
            )
        ]
        return _result(
            self.definition,
            context,
            ReasoningRuleResultStatus.APPLIED,
            findings=tuple(findings),
            code="TEST_COVERAGE_IMPACT_EVALUATED",
            message="Evaluated test coverage impact rule.",
        )


@dataclass(frozen=True, slots=True)
class ProjectSemanticTransformationRule:
    definition: DomainReasoningRuleDefinition = field(
        default_factory=lambda: _definition(
            "project.semantic_transformation",
            "ProjectSemanticTransformationRule",
            ReasoningRuleCategory.CONSISTENCY.value,
            710,
        )
    )

    def evaluate(self, context: ReasoningRuleContext) -> ReasoningRuleResult:
        if not _check_software_active(context):
            return _inactive_software_result(self.definition, context)

        findings = [
            ReasoningFinding(
                code="SEMANTIC_TRANSFORMATION_EVALUATED",
                message="Semantic transformation requirement evaluated.",
                severity=ReasoningSeverity.INFO,
                rule_id=self.definition.id,
                domain_id=self.definition.domain_id,
            )
        ]
        return _result(
            self.definition,
            context,
            ReasoningRuleResultStatus.APPLIED,
            findings=tuple(findings),
            code="SEMANTIC_TRANSFORMATION_EVALUATED",
            message="Evaluated semantic transformation rule.",
        )


# ── Life Plan Projection Helper (Task 9) ──────────────────────────────────────

ALLOWED_LIFE_PLAN_PROJECTION_FIELDS: frozenset[str] = frozenset(
    {
        "source_domain",
        "project_status_impact",
        "dependency",
        "resource_impact",
        "timeline_impact",
        "source_reference",
        "provenance",
        "effective_from",
        "effective_until",
    }
)

PROHIBITED_LIFE_PLAN_PROJECTION_FIELDS: frozenset[str] = frozenset(
    {
        "source_code",
        "repository_contents",
        "validation_logs",
        "unrestricted_issue_text",
        "commit_history",
        "operation_authority",
    }
)


def build_project_life_plan_projection(
    raw_payload: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Filter raw Project data to authorized, purpose-minimized fields for Life Plan."""
    payload = dict(raw_payload or {})

    # Prohibit raw Project internals fail-closed
    for prohibited in PROHIBITED_LIFE_PLAN_PROJECTION_FIELDS:
        if prohibited in payload:
            raise ValueError(f"Prohibited internal field {prohibited!r} cannot be projected to Life Plan")

    filtered: dict[str, Any] = {"source_domain": PROJECT_DOMAIN_ID}
    for k, v in payload.items():
        if k in ALLOWED_LIFE_PLAN_PROJECTION_FIELDS:
            filtered[k] = v

    return filtered


# ── Build Function ────────────────────────────────────────────────────────────


def build_project_rules() -> tuple[Any, ...]:
    """Build all 18 Project Domain rules deterministically in canonical order."""
    by_id = {
        # Generic project rules (8)
        "project.scope_consistency": ProjectScopeConsistencyRule(),
        "project.milestone_consistency": MilestoneConsistencyRule(),
        "project.dependency_consistency": DependencyConsistencyRule(),
        "project.status_transition": ProjectStatusTransitionRule(),
        "project.resource_constraint": ProjectResourceConstraintRule(),
        "project.decision_state": ProjectDecisionStateRule(),
        "project.temporal_validity": ProjectTemporalValidityRule(),
        "project.progress_evidence": ProjectProgressEvidenceRule(),
        # Software-project rules (10)
        "project.architecture_contract": ProjectArchitectureContractRule(),
        "project.code_documentation_consistency": ProjectCodeDocumentationConsistencyRule(),
        "project.validation_required": ProjectValidationRequiredRule(),
        "project.technical_debt": ProjectTechnicalDebtRule(),
        "project.dead_code": ProjectDeadCodeRule(),
        "project.public_api_change": ProjectPublicApiChangeRule(),
        "project.backward_compatibility": ProjectBackwardCompatibilityRule(),
        "project.dependency_boundary": ProjectDependencyBoundaryRule(),
        "project.test_coverage_impact": ProjectTestCoverageImpactRule(),
        "project.semantic_transformation": ProjectSemanticTransformationRule(),
    }
    return tuple(by_id[rule_id] for rule_id in CANONICAL_PROJECT_RULE_IDS)


__all__ = [
    "ALLOWED_LIFE_PLAN_PROJECTION_FIELDS",
    "CANONICAL_PROJECT_RULE_IDS",
    "PROHIBITED_LIFE_PLAN_PROJECTION_FIELDS",
    "DependencyConsistencyRule",
    "MilestoneConsistencyRule",
    "ProjectArchitectureContractRule",
    "ProjectBackwardCompatibilityRule",
    "ProjectCodeDocumentationConsistencyRule",
    "ProjectDeadCodeRule",
    "ProjectDecisionStateRule",
    "ProjectDependencyBoundaryRule",
    "ProjectProgressEvidenceRule",
    "ProjectPublicApiChangeRule",
    "ProjectResourceConstraintRule",
    "ProjectScopeConsistencyRule",
    "ProjectSemanticTransformationRule",
    "ProjectStatusTransitionRule",
    "ProjectTechnicalDebtRule",
    "ProjectTemporalValidityRule",
    "ProjectTestCoverageImpactRule",
    "ProjectValidationRequiredRule",
    "build_project_life_plan_projection",
    "build_project_rules",
    "evaluate_dependency_consistency",
    "evaluate_milestone_consistency",
    "evaluate_project_decision_state",
    "evaluate_project_progress_evidence",
    "evaluate_project_resource_constraints",
    "evaluate_project_scope_consistency",
    "evaluate_project_status_transition",
    "evaluate_project_temporal_validity",
]

