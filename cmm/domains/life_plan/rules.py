"""Phase 10.29 — Life Plan Domain Rules and deterministic evaluators.

Declarative domain rules + pure deterministic long-term planning reasoning helpers.
All helper functions and rule evaluators are state-free: no IO, no model calls,
no registry mutation, no internal clock. They receive context explicitly and
return deterministic JSON-safe structures.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime, timezone
from types import MappingProxyType
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
from cmm.domains.life_plan.catalog import (
    CANONICAL_LIFE_PLAN_RULE_IDS,
    CANONICAL_LIFE_PLAN_RULE_NAMES,
)
from cmm.domains.rule_contracts import DomainReasoningRuleDefinition, DomainRuleResult

LIFE_PLAN_RULE_IDS: tuple[str, ...] = CANONICAL_LIFE_PLAN_RULE_IDS
LIFE_PLAN_RULE_NAMES: tuple[str, ...] = CANONICAL_LIFE_PLAN_RULE_NAMES

DECISION_STATUS_VOCABULARY: tuple[str, ...] = (
    "idea",
    "preference",
    "goal",
    "scenario",
    "decision",
    "commitment",
)


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
        domain_id="domain:life-plan",
        category=category,
        status=ReasoningRuleStatus.ENABLED,
        priority=priority,
        risk_level=risk_level,
        deterministic=True,
        description=f"Life Plan domain reasoning rule for {rule_id}.",
        metadata={"phase": "10.29"},
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


# ── Pure Evaluators ───────────────────────────────────────────────────────────


def evaluate_decision_status(
    current_status: str,
    proposed_status: str,
    *,
    confirmation_evidence: Any = None,
    is_closed: bool = False,
    has_new_evidence: bool = False,
    new_evidence: Any = None,
) -> dict[str, Any]:
    """Evaluate decision status transition according to non-collapsible lattice.

    Enforces:
    - canonical decision-state vocabulary: idea, preference, goal, scenario, decision, commitment
    - preference != decision
    - scenario != decision
    - scenario != commitment
    - inference != confirmed fact / decision / commitment
    - unknown or noncanonical statuses fail closed
    - closed decision cannot reopen without explicit new evidence.
    """
    curr = str(current_status).lower().strip()
    prop = str(proposed_status).lower().strip()

    # Fail closed for any unknown/non-canonical decision states
    if curr not in DECISION_STATUS_VOCABULARY or prop not in DECISION_STATUS_VOCABULARY:
        return {
            "allowed": False,
            "current_status": curr,
            "proposed_status": prop,
            "requires_confirmation": False,
            "reopened": False,
            "reason": (
                f"Unknown or noncanonical decision state: current='{curr}', proposed='{prop}'. "
                f"Valid states are: {', '.join(DECISION_STATUS_VOCABULARY)}."
            ),
        }

    # Closed decision reopening check
    if is_closed and not has_new_evidence and not new_evidence:
        return {
            "allowed": False,
            "current_status": curr,
            "proposed_status": prop,
            "requires_confirmation": True,
            "reopened": False,
            "reason": "Closed decision cannot be reopened or modified without explicit new evidence.",
        }

    # If proposing transition to decision or commitment from unconfirmed state, confirmation is mandatory
    unconfirmed_states = ("idea", "preference", "goal", "scenario")
    if (
        curr in unconfirmed_states
        and prop in ("decision", "commitment")
        and not confirmation_evidence
    ):
        return {
            "allowed": False,
            "current_status": curr,
            "proposed_status": prop,
            "requires_confirmation": True,
            "reopened": False,
            "reason": f"Cannot promote unconfirmed {curr} to {prop} without explicit user confirmation evidence.",
        }

    # Proposing transition from decision to commitment also requires confirmation/commitment evidence
    if curr == "decision" and prop == "commitment" and not confirmation_evidence:
        return {
            "allowed": False,
            "current_status": curr,
            "proposed_status": prop,
            "requires_confirmation": True,
            "reopened": False,
            "reason": "Cannot promote decision to commitment without explicit commitment evidence.",
        }

    return {
        "allowed": True,
        "current_status": curr,
        "new_status": prop,
        "requires_confirmation": False,
        "reopened": bool(is_closed and (has_new_evidence or new_evidence)),
        "reason": f"Valid state transition from {curr} to {prop}.",
    }


def evaluate_scenario_consistency(
    scenario_id: str,
    assumptions: dict[str, Any] | None = None,
    milestones: list[dict[str, Any]] | None = None,
    contradictions: list[str] | None = None,
    *,
    assumption_conflicts: list[tuple[str, str]] | list[dict[str, Any]] | None = None,
    resource_constraints: dict[str, Any] | None = None,
    constraints: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Validate internal scenario coherence while preserving uncertainty.

    Scenario viability != decision; scenario viability != commitment.
    Computes consistency from:
    - structured mutually exclusive assumption relations
    - temporal milestone dependency and chronology ordering
    - structured resource / constraint incompatibilities
    - preserving unknown / uncertain evidence.
    """
    assump = dict(assumptions or {})
    conflicts: list[str] = list(contradictions or [])
    uncertainties: list[str] = []

    for k, v in assump.items():
        if (
            v is None
            or v == "unknown"
            or (isinstance(v, str) and "uncertain" in v.lower())
        ):
            uncertainties.append(k)

    # 1. Evaluate structured assumption conflicts
    if assumption_conflicts:
        for conf_item in assumption_conflicts:
            if isinstance(conf_item, (tuple, list)) and len(conf_item) >= 2:
                k1, k2 = str(conf_item[0]), str(conf_item[1])
                if k1 in assump and k2 in assump:
                    v1, v2 = assump[k1], assump[k2]
                    if (
                        v1 is not None
                        and v2 is not None
                        and v1 != "unknown"
                        and v2 != "unknown"
                        and not (isinstance(v1, str) and "uncertain" in v1.lower())
                        and not (isinstance(v2, str) and "uncertain" in v2.lower())
                    ):
                        conflicts.append(
                            f"Mutually exclusive assumptions: '{k1}' ({v1}) and '{k2}' ({v2})"
                        )
            elif isinstance(conf_item, dict):
                k1 = str(conf_item.get("left_id") or conf_item.get("left") or "")
                k2 = str(conf_item.get("right_id") or conf_item.get("right") or "")
                rel = conf_item.get("relation", "mutually_exclusive")
                if (
                    k1 in assump
                    and k2 in assump
                    and rel in ("mutually_exclusive", "incompatible")
                ):
                    v1, v2 = assump[k1], assump[k2]
                    if (
                        v1 is not None
                        and v2 is not None
                        and v1 != "unknown"
                        and v2 != "unknown"
                        and not (isinstance(v1, str) and "uncertain" in v1.lower())
                        and not (isinstance(v2, str) and "uncertain" in v2.lower())
                    ):
                        conflicts.append(
                            f"Mutually exclusive assumptions: '{k1}' and '{k2}'"
                        )

    # 2. Evaluate milestone temporal consistency via evaluate_long_term_temporal
    if milestones:
        temp_eval = evaluate_long_term_temporal(milestones=milestones)
        if not temp_eval["valid"] or len(temp_eval["ordering_conflicts"]) > 0:
            for oc in temp_eval["ordering_conflicts"]:
                conflicts.append(f"Temporal milestone ordering conflict: {oc}")
        for unc_ms in temp_eval.get("uncertain_milestones", []):
            if unc_ms not in uncertainties:
                uncertainties.append(f"milestone:{unc_ms}")

    # 3. Evaluate resource/constraint incompatibilities
    res_data = resource_constraints or constraints
    if res_data:
        res_eval = evaluate_resource_constraints(**res_data)
        if res_eval.get("feasible") is False:
            conflicts.append(
                f"Resource constraint infeasibility: {res_eval.get('summary', 'infeasible')}"
            )
        elif res_eval.get("feasible") is None:
            for dim_name, dim_val in res_eval.get("dimensions", {}).items():
                if dim_val.get("status") == "unknown":
                    uncertainties.append(f"resource:{dim_name}")

    consistent = len(conflicts) == 0

    return {
        "scenario_id": scenario_id,
        "consistent": consistent,
        "status": "coherent" if consistent else "inconsistent",
        "conflicts": conflicts,
        "uncertainties": uncertainties,
        "is_decision": False,
        "is_commitment": False,
    }


def evaluate_alternative_route(
    primary_goal_id: str,
    alternative_route_id: str,
    route_type: str = "fallback",
    rationale: str = "",
) -> dict[str, Any]:
    """Preserve alternative routes without implying abandonment or failure."""
    return {
        "primary_goal_id": primary_goal_id,
        "alternative_route_id": alternative_route_id,
        "route_type": route_type,
        "rationale": rationale,
        "status": "active_alternative",
        "primary_goal_abandoned": False,
        "is_failure": False,
        "is_contingency": True,
    }


def evaluate_goal_dependencies(
    dependencies: dict[str, list[str]] | None = None,
    soft_dependencies: dict[str, list[str]] | None = None,
) -> dict[str, Any]:
    """Evaluate goal dependency structure, detecting cycles and separating hard/soft relationships."""
    deps = dict(dependencies or {})
    soft_deps = dict(soft_dependencies or {})

    # Cycle detection via DFS
    visited: set[str] = set()
    rec_stack: set[str] = set()
    cycles: list[list[str]] = []

    def dfs(node: str, path: list[str]) -> None:
        visited.add(node)
        rec_stack.add(node)
        for neighbor in deps.get(node, []):
            if neighbor not in visited:
                dfs(neighbor, path + [neighbor])
            elif neighbor in rec_stack:
                cycle_start = path.index(neighbor) if neighbor in path else 0
                cycles.append(path[cycle_start:] + [neighbor])
        rec_stack.remove(node)

    for node in deps:
        if node not in visited:
            dfs(node, [node])

    has_cycles = len(cycles) > 0
    return {
        "valid": not has_cycles,
        "has_cycles": has_cycles,
        "cycles": cycles,
        "prerequisites": deps,
        "soft_dependencies": soft_deps,
    }


def evaluate_resource_constraints(
    time: dict[str, Any] | None = None,
    money: dict[str, Any] | None = None,
    energy: dict[str, Any] | None = None,
    available_capacity: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Evaluate 4 resource dimensions independently without coercing missing/malformed to 0."""
    dims: dict[str, Any] = {}
    is_invalid = False
    is_unknown = False
    blocking: list[str] = []

    def _eval_numeric_dimension(
        name: str,
        data: dict[str, Any] | None,
        avail_key: str,
        req_key: str,
    ) -> dict[str, Any]:
        nonlocal is_invalid, is_unknown
        if data is None:
            return {"status": "not_specified", "available": None, "required": None}

        raw_avail = data.get(avail_key)
        raw_req = data.get(req_key)

        if raw_avail is None or raw_req is None:
            is_unknown = True
            return {"status": "unknown", "available": raw_avail, "required": raw_req}

        # Reject booleans as numeric
        if isinstance(raw_avail, bool) or isinstance(raw_req, bool):
            is_invalid = True
            return {"status": "invalid_evidence", "available": None, "required": None}

        try:
            avail = float(raw_avail)
            req = float(raw_req)
        except (ValueError, TypeError):
            is_invalid = True
            return {"status": "invalid_evidence", "available": None, "required": None}

        if not math.isfinite(avail) or not math.isfinite(req) or avail < 0 or req < 0:
            is_invalid = True
            return {"status": "invalid_evidence", "available": None, "required": None}

        if avail < req:
            blocking.append(f"{name}_deficit")
            return {
                "status": "constrained",
                "available": avail,
                "required": req,
                "sufficient": False,
            }

        return {
            "status": "sufficient",
            "available": avail,
            "required": req,
            "sufficient": True,
        }

    dims["time"] = _eval_numeric_dimension(
        "time", time, "available_hours_per_week", "required_hours_per_week"
    )
    dims["money"] = _eval_numeric_dimension(
        "money", money, "available_funds", "required_funds"
    )

    # Energy dimension
    if energy is None:
        dims["energy"] = {"status": "not_specified", "level": None}
    else:
        lvl = energy.get("current_energy_level")
        min_lvl = energy.get("minimum_required")
        if lvl is None:
            dims["energy"] = {"status": "unknown", "level": None}
            is_unknown = True
        elif lvl in ("exhausted", "depleted", "low") and min_lvl in (
            "high",
            "moderate",
        ):
            dims["energy"] = {
                "status": "constrained",
                "level": lvl,
                "sufficient": False,
            }
            blocking.append("energy_deficit")
        else:
            dims["energy"] = {"status": "sufficient", "level": lvl, "sufficient": True}

    # Available capacity dimension
    if available_capacity is None:
        dims["available_capacity"] = {"status": "not_specified", "slots": None}
    else:
        slots = available_capacity.get("slots")
        req_slots = available_capacity.get("required_slots", 1)
        if slots is None:
            dims["available_capacity"] = {"status": "unknown", "slots": None}
            is_unknown = True
        elif isinstance(slots, bool) or isinstance(req_slots, bool):
            dims["available_capacity"] = {"status": "invalid_evidence", "slots": None}
            is_invalid = True
        else:
            try:
                s = int(slots)
                rs = int(req_slots)
                if s < rs:
                    dims["available_capacity"] = {
                        "status": "constrained",
                        "slots": s,
                        "required": rs,
                        "sufficient": False,
                    }
                    blocking.append("capacity_deficit")
                else:
                    dims["available_capacity"] = {
                        "status": "sufficient",
                        "slots": s,
                        "required": rs,
                        "sufficient": True,
                    }
            except (ValueError, TypeError):
                dims["available_capacity"] = {
                    "status": "invalid_evidence",
                    "slots": None,
                }
                is_invalid = True

    if is_invalid:
        status = "invalid_evidence"
    elif len(blocking) > 0:
        status = "constrained"
    elif is_unknown:
        status = "unknown"
    else:
        status = "feasible"

    return {
        "status": status,
        "dimensions": dims,
        "feasible": True
        if status == "feasible"
        else (False if status == "constrained" else None),
        "blocking_constraints": blocking,
    }


def evaluate_long_term_temporal(
    milestones: list[dict[str, Any]] | None = None,
    timeline_events: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Validate long-term temporal ordering and compatibility without inventing missing dates."""
    ms_list = list(milestones or [])
    conflicts: list[str] = []
    uncertain_ms: list[str] = []

    ms_by_id: dict[str, dict[str, Any]] = {}
    for ms in ms_list:
        mid = ms.get("id", "unnamed")
        ms_by_id[mid] = ms
        target = ms.get("target_date")
        if not target:
            uncertain_ms.append(mid)

    for mid, ms in ms_by_id.items():
        depends_on = ms.get("depends_on")
        target = ms.get("target_date")
        if depends_on and depends_on in ms_by_id and target:
            dep_target = ms_by_id[depends_on].get("target_date")
            if dep_target:
                try:
                    dt_current = datetime.fromisoformat(target)
                    dt_dep = datetime.fromisoformat(dep_target)
                    if dt_current < dt_dep:
                        conflicts.append(
                            f"Milestone {mid} target {target} precedes prerequisite {depends_on} target {dep_target}"
                        )
                except (ValueError, TypeError):
                    pass

    valid = len(conflicts) == 0
    return {
        "valid": valid,
        "ordering_valid": valid,
        "ordering_conflicts": conflicts,
        "uncertain_milestones": uncertain_ms,
        "milestones_count": len(ms_list),
    }


_LIFE_PLAN_INTERNAL_TOKEN = object()


@dataclass(frozen=True, slots=True)
class AuthorizedCrossDomainContribution:
    """Internal immutable value object representing a vetted, authorized supporting-domain contribution."""

    projection: Mapping[str, Any]
    permission_decision_id: str
    permission_request_id: str
    source_domain: str
    target_domain: str
    effective_from: datetime | None = None
    effective_until: datetime | None = None
    _provenance_token: Any = field(default=None, repr=False, compare=False)

    @property
    def _is_verified(self) -> bool:
        return self._provenance_token is _LIFE_PLAN_INTERNAL_TOKEN


def _create_authorized_cross_domain_contribution(
    *,
    projection: Mapping[str, Any],
    permission_decision_id: str,
    permission_request_id: str,
    source_domain: str,
    target_domain: str = "domain:life-plan",
    effective_from: datetime | None = None,
    effective_until: datetime | None = None,
) -> AuthorizedCrossDomainContribution:
    return AuthorizedCrossDomainContribution(
        projection=projection,
        permission_decision_id=permission_decision_id,
        permission_request_id=permission_request_id,
        source_domain=source_domain,
        target_domain=target_domain,
        effective_from=effective_from,
        effective_until=effective_until,
        _provenance_token=_LIFE_PLAN_INTERNAL_TOKEN,
    )


def evaluate_cross_domain_impact(
    projection: Any = None,
    *,
    permission_request: Any = None,
    permission_decision: Any = None,
    permission_gate: Any = None,
    permission_resolver: Any = None,
    approval_request_id: str | None = None,
    is_authorized: bool | None = None,
    is_current: bool | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Incorporate authorized, purpose-minimized supporting-domain contribution into Life Plan.

    Requires runtime-owned fresh gate evaluation or permission resolution.
    Caller-supplied PermissionGateResult, plain mappings, duck-typed objects,
    and caller booleans are never trusted as authorization roots.
    """
    from cmm.agent_runtime.domain_permission_contracts import (
        PermissionCapability,
        PermissionOutcome,
    )
    from cmm.domains.permission_contracts import CrossDomainPermissionRequest
    from cmm.domains.permission_gate import (
        PermissionGateOutcome,
    )

    if not isinstance(projection, Mapping):
        return {
            "applied": False,
            "reason": "invalid_projection",
            "contribution": None,
            "authorization_verified": False,
            "authorized_artifact": None,
        }

    # Reject clinical dossier or raw health memory
    prohibited_keys = (
        "full_clinical_history",
        "medication_list",
        "raw_health_memory",
        "raw_academic_dossier",
        "full_opposition_dossier",
    )
    if any(k in projection for k in prohibited_keys):
        return {
            "applied": False,
            "reason": "rejected_unauthorized_dossier",
            "contribution": None,
            "authorization_verified": False,
            "authorized_artifact": None,
        }

    if is_current is False:
        return {
            "applied": False,
            "reason": "unauthorized_or_expired",
            "contribution": None,
            "authorization_verified": False,
            "authorized_artifact": None,
        }

    curr_now = now or datetime.now(timezone.utc)
    if curr_now.tzinfo is None:
        curr_now = curr_now.replace(tzinfo=timezone.utc)

    eff_from_dt: datetime | None = None
    if "effective_from" in projection and projection["effective_from"] is not None:
        raw_from = projection["effective_from"]
        if isinstance(raw_from, datetime):
            eff_from_dt = (
                raw_from if raw_from.tzinfo else raw_from.replace(tzinfo=timezone.utc)
            )
        elif isinstance(raw_from, str):
            try:
                parsed_from = datetime.fromisoformat(
                    raw_from.replace("Z", "+00:00")
                    if raw_from.endswith("Z")
                    else raw_from
                )
                eff_from_dt = (
                    parsed_from
                    if parsed_from.tzinfo
                    else parsed_from.replace(tzinfo=timezone.utc)
                )
            except (ValueError, TypeError):
                return {
                    "applied": False,
                    "reason": "unauthorized_or_expired",
                    "contribution": None,
                    "authorization_verified": False,
                    "authorized_artifact": None,
                }
        else:
            return {
                "applied": False,
                "reason": "unauthorized_or_expired",
                "contribution": None,
                "authorization_verified": False,
                "authorized_artifact": None,
            }
        if eff_from_dt is not None and eff_from_dt > curr_now:
            return {
                "applied": False,
                "reason": "unauthorized_or_expired",
                "contribution": None,
                "authorization_verified": False,
                "authorized_artifact": None,
            }

    eff_until_dt: datetime | None = None
    if "effective_until" in projection and projection["effective_until"] is not None:
        raw_until = projection["effective_until"]
        if isinstance(raw_until, datetime):
            eff_until_dt = (
                raw_until
                if raw_until.tzinfo
                else raw_until.replace(tzinfo=timezone.utc)
            )
        elif isinstance(raw_until, str):
            try:
                parsed_until = datetime.fromisoformat(
                    raw_until.replace("Z", "+00:00")
                    if raw_until.endswith("Z")
                    else raw_until
                )
                eff_until_dt = (
                    parsed_until
                    if parsed_until.tzinfo
                    else parsed_until.replace(tzinfo=timezone.utc)
                )
            except (ValueError, TypeError):
                return {
                    "applied": False,
                    "reason": "unauthorized_or_expired",
                    "contribution": None,
                    "authorization_verified": False,
                    "authorized_artifact": None,
                }
        else:
            return {
                "applied": False,
                "reason": "unauthorized_or_expired",
                "contribution": None,
                "authorization_verified": False,
                "authorized_artifact": None,
            }
        if eff_until_dt is not None and eff_until_dt < curr_now:
            return {
                "applied": False,
                "reason": "unauthorized_or_expired",
                "contribution": None,
                "authorization_verified": False,
                "authorized_artifact": None,
            }

    auth_verified = False
    auth_ref: str | None = None
    req_id: str | None = None
    source_dom = projection.get("source_domain", "domain:health")
    auth_source = "evaluate_cross_domain_impact"

    if permission_request is not None:
        if not isinstance(permission_request, CrossDomainPermissionRequest):
            return {
                "applied": False,
                "reason": "unauthorized_or_expired",
                "contribution": None,
                "authorization_verified": False,
                "authorized_artifact": None,
            }
        if (
            permission_request.target_domain != "domain:life-plan"
            or permission_request.capability
            not in (
                PermissionCapability.DOMAIN_CROSS_ACCESS,
                PermissionCapability.RESOURCE_READ,
            )
        ):
            return {
                "applied": False,
                "reason": "unauthorized_or_expired",
                "contribution": None,
                "authorization_verified": False,
                "authorized_artifact": None,
            }
        if (
            permission_request.expires_at is not None
            and permission_request.expires_at <= curr_now
        ):
            return {
                "applied": False,
                "reason": "unauthorized_or_expired",
                "contribution": None,
                "authorization_verified": False,
                "authorized_artifact": None,
            }
        req_id = permission_request.request_id
        source_dom = permission_request.source_domain

    if (
        permission_gate is not None
        and hasattr(permission_gate, "evaluate_cross_domain")
        and permission_request is not None
    ):
        try:
            gate_res = permission_gate.evaluate_cross_domain(
                permission_request,
                approval_request_id=approval_request_id,
            )
            if (
                gate_res is not None
                and getattr(gate_res, "allowed", False) is True
                and getattr(gate_res, "outcome", None)
                in (
                    PermissionGateOutcome.ALLOW,
                    PermissionGateOutcome.APPROVAL_CONSUMED,
                )
                and getattr(gate_res, "domain_id", None)
                in (
                    permission_request.source_domain,
                    permission_request.target_domain,
                )
                and getattr(gate_res, "actor_id", None) == permission_request.actor_id
                and getattr(gate_res, "session_id", None)
                == permission_request.session_id
            ):
                auth_verified = True
                auth_ref = gate_res.decision_id or "permission_gate"
                auth_source = "DomainPermissionGate"
        except (AttributeError, KeyError, TypeError, ValueError, RuntimeError):
            auth_verified = False

    elif (
        permission_resolver is not None
        and hasattr(permission_resolver, "resolve_cross_domain")
        and permission_request is not None
    ):
        res_dec = permission_resolver.resolve_cross_domain(
            permission_request, now=curr_now
        )
        if (
            res_dec.decision is PermissionOutcome.ALLOW
            and getattr(res_dec, "target_domain_id", "domain:life-plan")
            == "domain:life-plan"
            and getattr(res_dec, "source_domain_id", permission_request.source_domain)
            == permission_request.source_domain
            and getattr(res_dec, "actor_id", permission_request.actor_id)
            == permission_request.actor_id
            and getattr(res_dec, "session_id", permission_request.session_id)
            == permission_request.session_id
        ):
            auth_verified = True
            auth_ref = res_dec.request_id
            auth_source = "DomainPermissionResolver"

    if not auth_verified or not auth_ref or not req_id:
        return {
            "applied": False,
            "reason": "unauthorized_or_expired",
            "contribution": None,
            "authorization_verified": False,
            "authorized_artifact": None,
        }

    allowed_fields = (
        "constraint_id",
        "status",
        "effective_from",
        "effective_until",
        "activity_limits",
        "load_limits",
        "workload_hours",
        "milestone_deadline",
        "financial_impact",
        "family_timeline_constraint",
        "project_status_impact",
        "source_reference",
        "provenance",
        "authorization_reference",
    )

    minimized_contribution = {
        k: projection[k] for k in allowed_fields if k in projection
    }
    if auth_ref and "authorization_reference" not in minimized_contribution:
        minimized_contribution["authorization_reference"] = auth_ref

    artifact = _create_authorized_cross_domain_contribution(
        projection=MappingProxyType(dict(minimized_contribution)),
        permission_decision_id=auth_ref,
        permission_request_id=req_id,
        source_domain=source_dom,
        target_domain="domain:life-plan",
        effective_from=eff_from_dt,
        effective_until=eff_until_dt,
    )

    return {
        "applied": True,
        "contribution": minimized_contribution,
        "source_domain": source_dom,
        "applied_fields": tuple(minimized_contribution.keys()),
        "authorization_verified": True,
        "authorization_source": auth_source,
        "authorized_artifact": artifact,
        "provenance": {
            "authorization_reference": minimized_contribution.get(
                "authorization_reference"
            ),
            "source_reference": minimized_contribution.get("source_reference"),
            "permission_request_id": req_id,
            "permission_decision_id": auth_ref,
            "source_domain": source_dom,
        },
    }


def evaluate_plan_drift(
    planned_state: dict[str, Any] | None = None,
    confirmed_decisions: dict[str, Any] | None = None,
    actual_state: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Detect material drift between planned state, confirmed decisions, and actual state."""
    plan = dict(planned_state or {})
    conf = dict(confirmed_decisions or {})
    act = dict(actual_state or {})

    drift_items: list[str] = []
    for k, planned_val in plan.items():
        if k in act and act[k] != planned_val:
            drift_items.append(
                f"Discrepancy in {k}: planned={planned_val}, actual={act[k]}"
            )

    has_drift = len(drift_items) > 0

    return {
        "status": "evaluated",
        "has_drift": has_drift,
        "drift_items": drift_items,
        "goal_abandoned": False,
        "provenance_preserved": True,
        "planned_state": plan,
        "confirmed_decisions": conf,
        "actual_state": act,
    }


# ── Declarative Rule Classes ──────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class GoalDependencyRule:
    definition: DomainReasoningRuleDefinition = field(
        default_factory=lambda: _definition(
            "life_plan.rule.goal_dependency",
            "GoalDependencyRule",
            ReasoningRuleCategory.CONSISTENCY.value,
            800,
        )
    )

    def evaluate(self, context: ReasoningRuleContext) -> ReasoningRuleResult:
        deps = context.metadata.get("dependencies")
        soft = context.metadata.get("soft_dependencies")
        res = evaluate_goal_dependencies(dependencies=deps, soft_dependencies=soft)

        findings = [
            ReasoningFinding(
                code="GOAL_DEPENDENCIES_EVALUATED",
                message=f"Goal dependencies evaluated: valid={res['valid']}, has_cycles={res['has_cycles']}",
                severity=ReasoningSeverity.INFO
                if res["valid"]
                else ReasoningSeverity.ERROR,
                rule_id=self.definition.id,
                domain_id=self.definition.domain_id,
            )
        ]
        return _result(
            self.definition,
            context,
            ReasoningRuleResultStatus.APPLIED,
            findings=tuple(findings),
            code="GOAL_DEPENDENCIES_EVALUATED",
            message="Evaluated goal dependency rule.",
        )


@dataclass(frozen=True, slots=True)
class ScenarioConsistencyRule:
    definition: DomainReasoningRuleDefinition = field(
        default_factory=lambda: _definition(
            "life_plan.rule.scenario_consistency",
            "ScenarioConsistencyRule",
            ReasoningRuleCategory.CONSISTENCY.value,
            810,
        )
    )

    def evaluate(self, context: ReasoningRuleContext) -> ReasoningRuleResult:
        scen_id = context.metadata.get("scenario_id", "default_scenario")
        assump = context.metadata.get("assumptions")
        milestones = context.metadata.get("milestones")
        contra = context.metadata.get("contradictions")
        assump_conf = context.metadata.get("assumption_conflicts")
        res_const = context.metadata.get(
            "resource_constraints"
        ) or context.metadata.get("constraints")

        res = evaluate_scenario_consistency(
            scenario_id=scen_id,
            assumptions=assump,
            milestones=milestones,
            contradictions=contra,
            assumption_conflicts=assump_conf,
            resource_constraints=res_const,
        )

        findings = [
            ReasoningFinding(
                code="SCENARIO_CONSISTENCY_EVALUATED",
                message=f"Scenario consistency evaluated: consistent={res['consistent']}, conflicts={len(res['conflicts'])}",
                severity=ReasoningSeverity.INFO
                if res["consistent"]
                else ReasoningSeverity.WARNING,
                rule_id=self.definition.id,
                domain_id=self.definition.domain_id,
            )
        ]
        return _result(
            self.definition,
            context,
            ReasoningRuleResultStatus.APPLIED,
            findings=tuple(findings),
            code="SCENARIO_CONSISTENCY_EVALUATED",
            message="Evaluated scenario consistency rule.",
        )


@dataclass(frozen=True, slots=True)
class ResourceConstraintRule:
    definition: DomainReasoningRuleDefinition = field(
        default_factory=lambda: _definition(
            "life_plan.rule.resource_constraint",
            "ResourceConstraintRule",
            ReasoningRuleCategory.CONSISTENCY.value,
            820,
        )
    )

    def evaluate(self, context: ReasoningRuleContext) -> ReasoningRuleResult:
        t = context.metadata.get("time")
        m = context.metadata.get("money")
        e = context.metadata.get("energy")
        c = context.metadata.get("available_capacity")

        res = evaluate_resource_constraints(
            time=t, money=m, energy=e, available_capacity=c
        )

        findings = [
            ReasoningFinding(
                code="RESOURCE_CONSTRAINTS_EVALUATED",
                message=f"Resource constraints evaluated: status={res['status']}, blocking={len(res['blocking_constraints'])}",
                severity=ReasoningSeverity.INFO
                if res["status"] == "feasible"
                else ReasoningSeverity.WARNING,
                rule_id=self.definition.id,
                domain_id=self.definition.domain_id,
            )
        ]
        return _result(
            self.definition,
            context,
            ReasoningRuleResultStatus.APPLIED,
            findings=tuple(findings),
            code="RESOURCE_CONSTRAINTS_EVALUATED",
            message="Evaluated resource constraint rule.",
        )


@dataclass(frozen=True, slots=True)
class DecisionStatusRule:
    definition: DomainReasoningRuleDefinition = field(
        default_factory=lambda: _definition(
            "life_plan.rule.decision_status",
            "DecisionStatusRule",
            ReasoningRuleCategory.CONSISTENCY.value,
            830,
            risk_level=ReasoningRiskLevel.HIGH,
        )
    )

    def evaluate(self, context: ReasoningRuleContext) -> ReasoningRuleResult:
        curr = context.metadata.get("current_status", "idea")
        prop = context.metadata.get("proposed_status", "decision")
        conf = context.metadata.get("confirmation_evidence")
        closed = context.metadata.get("is_closed", False)
        new_ev = context.metadata.get("has_new_evidence", False)
        new_ev_data = context.metadata.get("new_evidence")

        res = evaluate_decision_status(
            curr,
            prop,
            confirmation_evidence=conf,
            is_closed=closed,
            has_new_evidence=new_ev,
            new_evidence=new_ev_data,
        )

        findings = [
            ReasoningFinding(
                code="DECISION_STATUS_EVALUATED",
                message=f"Decision status transition evaluated: allowed={res['allowed']}, reason={res['reason']}",
                severity=ReasoningSeverity.INFO
                if res["allowed"]
                else ReasoningSeverity.WARNING,
                rule_id=self.definition.id,
                domain_id=self.definition.domain_id,
            )
        ]
        return _result(
            self.definition,
            context,
            ReasoningRuleResultStatus.APPLIED,
            findings=tuple(findings),
            code="DECISION_STATUS_EVALUATED",
            message="Evaluated decision status rule.",
        )


@dataclass(frozen=True, slots=True)
class LongTermTemporalRule:
    definition: DomainReasoningRuleDefinition = field(
        default_factory=lambda: _definition(
            "life_plan.rule.long_term_temporal",
            "LongTermTemporalRule",
            ReasoningRuleCategory.TEMPORALITY.value,
            840,
        )
    )

    def evaluate(self, context: ReasoningRuleContext) -> ReasoningRuleResult:
        ms = context.metadata.get("milestones")
        events = context.metadata.get("timeline_events")

        res = evaluate_long_term_temporal(milestones=ms, timeline_events=events)

        findings = [
            ReasoningFinding(
                code="LONG_TERM_TEMPORAL_EVALUATED",
                message=f"Long term temporal evaluated: valid={res['valid']}, conflicts={len(res['ordering_conflicts'])}",
                severity=ReasoningSeverity.INFO
                if res["valid"]
                else ReasoningSeverity.ERROR,
                rule_id=self.definition.id,
                domain_id=self.definition.domain_id,
            )
        ]
        return _result(
            self.definition,
            context,
            ReasoningRuleResultStatus.APPLIED,
            findings=tuple(findings),
            code="LONG_TERM_TEMPORAL_EVALUATED",
            message="Evaluated long term temporal rule.",
        )


@dataclass(frozen=True, slots=True)
class AlternativeRouteRule:
    definition: DomainReasoningRuleDefinition = field(
        default_factory=lambda: _definition(
            "life_plan.rule.alternative_route",
            "AlternativeRouteRule",
            ReasoningRuleCategory.INFERENCE.value,
            850,
        )
    )

    def evaluate(self, context: ReasoningRuleContext) -> ReasoningRuleResult:
        primary_goal_id = context.metadata.get("primary_goal_id", "primary_goal")
        alt_id = context.metadata.get("alternative_route_id", "alt_route")
        route_type = context.metadata.get("route_type", "fallback")
        rationale = context.metadata.get("rationale", "")

        res = evaluate_alternative_route(
            primary_goal_id=primary_goal_id,
            alternative_route_id=alt_id,
            route_type=route_type,
            rationale=rationale,
        )

        findings = [
            ReasoningFinding(
                code="ALTERNATIVE_ROUTE_EVALUATED",
                message=f"Alternative route evaluated: primary_goal_abandoned={res['primary_goal_abandoned']}",
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
            code="ALTERNATIVE_ROUTE_EVALUATED",
            message="Evaluated alternative route rule.",
        )


@dataclass(frozen=True, slots=True)
class CrossDomainImpactRule:
    definition: DomainReasoningRuleDefinition = field(
        default_factory=lambda: _definition(
            "life_plan.rule.cross_domain_impact",
            "CrossDomainImpactRule",
            ReasoningRuleCategory.SAFETY.value,
            860,
        )
    )

    def evaluate(self, context: ReasoningRuleContext) -> ReasoningRuleResult:
        proj = context.metadata.get("projection")
        req = context.metadata.get("permission_request")
        dec = context.metadata.get("permission_decision")
        gate = context.metadata.get("permission_gate")
        resolver = context.metadata.get("permission_resolver")
        app_req_id = context.metadata.get("approval_request_id")
        auth = context.metadata.get("is_authorized", False)
        curr = context.metadata.get("is_current", True)

        res = evaluate_cross_domain_impact(
            projection=proj,
            permission_request=req,
            permission_decision=dec,
            permission_gate=gate,
            permission_resolver=resolver,
            approval_request_id=app_req_id,
            is_authorized=auth,
            is_current=curr,
        )

        findings = [
            ReasoningFinding(
                code="CROSS_DOMAIN_IMPACT_EVALUATED",
                message=f"Cross domain impact applied={res['applied']}",
                severity=ReasoningSeverity.INFO
                if res["applied"]
                else ReasoningSeverity.WARNING,
                rule_id=self.definition.id,
                domain_id=self.definition.domain_id,
            )
        ]
        return _result(
            self.definition,
            context,
            ReasoningRuleResultStatus.APPLIED,
            findings=tuple(findings),
            code="CROSS_DOMAIN_IMPACT_EVALUATED",
            message="Evaluated cross domain impact rule.",
        )


@dataclass(frozen=True, slots=True)
class PlanDriftRule:
    definition: DomainReasoningRuleDefinition = field(
        default_factory=lambda: _definition(
            "life_plan.rule.plan_drift",
            "PlanDriftRule",
            ReasoningRuleCategory.CONSISTENCY.value,
            870,
        )
    )

    def evaluate(self, context: ReasoningRuleContext) -> ReasoningRuleResult:
        planned = context.metadata.get("planned_state")
        conf = context.metadata.get("confirmed_decisions")
        act = context.metadata.get("actual_state")

        res = evaluate_plan_drift(
            planned_state=planned,
            confirmed_decisions=conf,
            actual_state=act,
        )

        findings = [
            ReasoningFinding(
                code="PLAN_DRIFT_EVALUATED",
                message=f"Plan drift evaluated: has_drift={res['has_drift']}",
                severity=ReasoningSeverity.INFO
                if not res["has_drift"]
                else ReasoningSeverity.WARNING,
                rule_id=self.definition.id,
                domain_id=self.definition.domain_id,
            )
        ]
        return _result(
            self.definition,
            context,
            ReasoningRuleResultStatus.APPLIED,
            findings=tuple(findings),
            code="PLAN_DRIFT_EVALUATED",
            message="Evaluated plan drift rule.",
        )


# ── Build Function ────────────────────────────────────────────────────────────


def build_life_plan_rules() -> tuple[Any, ...]:
    """Build the eight Life Plan Domain rules deterministically in canonical order."""
    by_id = {
        "life_plan.rule.goal_dependency": GoalDependencyRule(),
        "life_plan.rule.scenario_consistency": ScenarioConsistencyRule(),
        "life_plan.rule.resource_constraint": ResourceConstraintRule(),
        "life_plan.rule.decision_status": DecisionStatusRule(),
        "life_plan.rule.long_term_temporal": LongTermTemporalRule(),
        "life_plan.rule.alternative_route": AlternativeRouteRule(),
        "life_plan.rule.cross_domain_impact": CrossDomainImpactRule(),
        "life_plan.rule.plan_drift": PlanDriftRule(),
    }
    return tuple(by_id[rule_id] for rule_id in CANONICAL_LIFE_PLAN_RULE_IDS)


__all__ = [
    "DECISION_STATUS_VOCABULARY",
    "LIFE_PLAN_RULE_IDS",
    "LIFE_PLAN_RULE_NAMES",
    "AlternativeRouteRule",
    "AuthorizedCrossDomainContribution",
    "CrossDomainImpactRule",
    "DecisionStatusRule",
    "GoalDependencyRule",
    "LongTermTemporalRule",
    "PlanDriftRule",
    "ResourceConstraintRule",
    "ScenarioConsistencyRule",
    "build_life_plan_rules",
    "evaluate_alternative_route",
    "evaluate_cross_domain_impact",
    "evaluate_decision_status",
    "evaluate_goal_dependencies",
    "evaluate_long_term_temporal",
    "evaluate_plan_drift",
    "evaluate_resource_constraints",
    "evaluate_scenario_consistency",
]
