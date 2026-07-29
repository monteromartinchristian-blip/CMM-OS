"""Phase 9.8 – Policy Evaluator.

Defines the PolicyEvaluator protocol, safe attribute path resolution,
structured condition evaluation, combining algorithms, and DefaultPolicyEvaluator.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
from typing import Any, Protocol

from .enums import (
    PolicyCombiningAlgorithm,
    PolicyConditionOperator,
    PolicyDecision,
    PolicyEffect,
    PolicyEvaluationStatus,
    PolicyFailureMode,
    PolicyScope,
    PolicySeverity,
)
from .errors import (
    PolicyCombiningError,
    PolicyConditionEvaluationError,
)
from .policy_contracts import (
    Policy,
    PolicyAdvice,
    PolicyCondition,
    PolicyEvaluationContext,
    PolicyEvaluationRequest,
    PolicyEvaluationResult,
    PolicyObligation,
    PolicyRestriction,
    PolicyRule,
    PolicyRuleEvaluation,
    PolicySet,
    PolicyTarget,
    PolicyViolation,
    PolicyWarning,
)


class SentinelNotFound:
    """Sentinel object returned when a field path cannot be resolved in context."""


_NOT_FOUND = SentinelNotFound()


def _now_iso() -> str:
    """Return current timestamp in ISO 8601 UTC format."""
    return datetime.now(timezone.utc).isoformat()


def resolve_field_value(
    path: str, context: PolicyEvaluationContext | Mapping[str, Any]
) -> Any:
    """Safely resolve a dotted field path from context without calling methods or dynamic execution."""
    if not path or not isinstance(path, str):
        return _NOT_FOUND

    p_clean = path.strip()
    if p_clean.startswith("context.") and len(p_clean) > 8:
        p_clean = p_clean[8:]

    parts = p_clean.split(".")
    curr: Any = context

    for part in parts:
        if curr is _NOT_FOUND or curr is None:
            return _NOT_FOUND

        # Convert enum or custom object if needed
        if hasattr(curr, "value") and not isinstance(curr, type):
            # Check if enum value is dict or object
            pass

        # Check dictionary lookup
        if isinstance(curr, Mapping):
            if part in curr:
                curr = curr[part]
                continue
            # Try matching enum key name if string
            found = False
            for k, v in curr.items():
                if str(k) == part:
                    curr = v
                    found = True
                    break
            if found:
                continue
            return _NOT_FOUND

        # Check attribute lookup
        if hasattr(curr, part):
            # Security invariant: Reject private attributes or method calls
            if part.startswith("_"):
                return _NOT_FOUND
            val = getattr(curr, part)
            if callable(val):
                return _NOT_FOUND
            curr = val
            continue

        return _NOT_FOUND

    # Unpack enum values for raw comparison if applicable
    if hasattr(curr, "value") and not isinstance(curr, type):
        return curr.value

    return curr


def evaluate_condition(
    condition: PolicyCondition, context: PolicyEvaluationContext
) -> bool:
    """Evaluate a PolicyCondition safely against PolicyEvaluationContext."""
    val = resolve_field_value(condition.field, context)
    op = condition.operator
    exp = condition.value
    cs = condition.case_sensitive

    # Handle enum objects in expected value
    if hasattr(exp, "value") and not isinstance(exp, type):
        exp = exp.value

    raw_result = False

    if op == PolicyConditionOperator.EXISTS:
        raw_result = val is not _NOT_FOUND and val is not None
    elif op == PolicyConditionOperator.NOT_EXISTS:
        raw_result = val is _NOT_FOUND or val is None
    elif val is _NOT_FOUND:
        raw_result = False
    elif op == PolicyConditionOperator.EQUALS:
        if not cs and isinstance(val, str) and isinstance(exp, str):
            raw_result = val.lower() == exp.lower()
        else:
            raw_result = val == exp
    elif op == PolicyConditionOperator.NOT_EQUALS:
        if not cs and isinstance(val, str) and isinstance(exp, str):
            raw_result = val.lower() != exp.lower()
        else:
            raw_result = val != exp
    elif op == PolicyConditionOperator.IN:
        if isinstance(exp, (list, tuple, set)):
            exp_seq = [x.value if hasattr(x, "value") else x for x in exp]
            if not cs and isinstance(val, str):
                val_l = val.lower()
                raw_result = any(str(x).lower() == val_l for x in exp_seq)
            else:
                raw_result = val in exp_seq
        elif isinstance(exp, str) and isinstance(val, str):
            raw_result = val.lower() in exp.lower() if not cs else val in exp
        else:
            raw_result = False
    elif op == PolicyConditionOperator.NOT_IN:
        if isinstance(exp, (list, tuple, set)):
            exp_seq = [x.value if hasattr(x, "value") else x for x in exp]
            if not cs and isinstance(val, str):
                val_l = val.lower()
                raw_result = not any(str(x).lower() == val_l for x in exp_seq)
            else:
                raw_result = val not in exp_seq
        else:
            raw_result = True
    elif op == PolicyConditionOperator.CONTAINS:
        if isinstance(val, (list, tuple, set)):
            val_seq = [x.value if hasattr(x, "value") else x for x in val]
            if not cs and isinstance(exp, str):
                exp_l = exp.lower()
                raw_result = any(str(x).lower() == exp_l for x in val_seq)
            else:
                raw_result = exp in val_seq
        elif isinstance(val, str):
            exp_str = str(exp)
            raw_result = exp_str.lower() in val.lower() if not cs else exp_str in val
        else:
            raw_result = False
    elif op == PolicyConditionOperator.NOT_CONTAINS:
        if isinstance(val, (list, tuple, set)):
            val_seq = [x.value if hasattr(x, "value") else x for x in val]
            if not cs and isinstance(exp, str):
                exp_l = exp.lower()
                raw_result = not any(str(x).lower() == exp_l for x in val_seq)
            else:
                raw_result = exp not in val_seq
        elif isinstance(val, str):
            exp_str = str(exp)
            raw_result = (
                exp_str.lower() not in val.lower() if not cs else exp_str not in val
            )
        else:
            raw_result = True
    elif op == PolicyConditionOperator.GREATER_THAN:
        try:
            raw_result = val > exp
        except TypeError:
            raw_result = False
    elif op == PolicyConditionOperator.GREATER_THAN_OR_EQUAL:
        try:
            raw_result = val >= exp
        except TypeError:
            raw_result = False
    elif op == PolicyConditionOperator.LESS_THAN:
        try:
            raw_result = val < exp
        except TypeError:
            raw_result = False
    elif op == PolicyConditionOperator.LESS_THAN_OR_EQUAL:
        try:
            raw_result = val <= exp
        except TypeError:
            raw_result = False
    elif op == PolicyConditionOperator.MATCHES:
        try:
            pattern = str(exp)
            val_str = str(val)
            flags = re.IGNORECASE if not cs else 0
            raw_result = bool(re.search(pattern, val_str, flags))
        except re.error as err:
            raise PolicyConditionEvaluationError(
                f"Invalid regex pattern '{exp}' in condition field '{condition.field}': {err}"
            ) from err
    elif op == PolicyConditionOperator.STARTS_WITH:
        v_s, e_s = str(val), str(exp)
        raw_result = (
            v_s.lower().startswith(e_s.lower()) if not cs else v_s.startswith(e_s)
        )
    elif op == PolicyConditionOperator.ENDS_WITH:
        v_s, e_s = str(val), str(exp)
        raw_result = v_s.lower().endswith(e_s.lower()) if not cs else v_s.endswith(e_s)
    elif op == PolicyConditionOperator.INTERSECTS:
        val_set = set(val) if isinstance(val, (list, tuple, set)) else {val}
        exp_set = set(exp) if isinstance(exp, (list, tuple, set)) else {exp}
        if not cs:
            val_set = {str(x).lower() for x in val_set}
            exp_set = {str(x).lower() for x in exp_set}
        raw_result = bool(val_set & exp_set)
    elif op == PolicyConditionOperator.SUBSET_OF:
        val_set = set(val) if isinstance(val, (list, tuple, set)) else {val}
        exp_set = set(exp) if isinstance(exp, (list, tuple, set)) else {exp}
        if not cs:
            val_set = {str(x).lower() for x in val_set}
            exp_set = {str(x).lower() for x in exp_set}
        raw_result = val_set.issubset(exp_set)
    else:
        raise PolicyConditionEvaluationError(f"Unsupported operator: {op}")

    return not raw_result if condition.negate else raw_result


def matches_target(
    target: PolicyTarget | None, context: PolicyEvaluationContext
) -> bool:
    """Check if a PolicyTarget matches the given request context."""
    if target is None:
        return True

    # 1. Scopes check
    if target.scopes:
        # Check if context matches any of target scopes
        # Context scope can be derived from target or global
        matched_scope = False
        target_scope_vals = {s.value for s in target.scopes}
        if (
            PolicyScope.GLOBAL.value in target_scope_vals
            or context.resource
            and context.resource.kind.value in target_scope_vals
            or context.environment
            and context.environment.name in target_scope_vals
        ):
            matched_scope = True
        else:
            matched_scope = True  # Scope matches broadly unless explicitly excluded
        if not matched_scope:
            return False

    # 2. Subject kinds check
    if target.subject_kinds:
        sub_kinds = {sk.value for sk in target.subject_kinds}
        if context.subject.kind.value not in sub_kinds:
            return False

    # 3. Resource kinds check
    if target.resource_kinds:
        res_kinds = {rk.value for rk in target.resource_kinds}
        if context.resource.kind.value not in res_kinds:
            return False

    # 4. Action names check
    if target.action_names:
        action_matches = any(
            an == context.action.name or an == context.action.operation_name
            for an in target.action_names
        )
        if not action_matches:
            return False

    # 5. Target conditions check
    for cond in target.conditions:
        if not evaluate_condition(cond, context):
            return False

    return True


class PolicyEvaluator(Protocol):
    """Protocol for policy evaluation engines."""

    def evaluate(
        self,
        request: PolicyEvaluationRequest,
        policies: Sequence[Policy],
        policy_sets: Sequence[PolicySet] = (),
        fallback_mode: PolicyFailureMode = PolicyFailureMode.DENY,
    ) -> PolicyEvaluationResult:
        """Evaluate a policy evaluation request against given policies."""
        ...


class DefaultPolicyEvaluator:
    """Default deterministic policy evaluator implementing combining algorithms, rule evaluation, and obligation collection."""

    def evaluate(
        self,
        request: PolicyEvaluationRequest,
        policies: Sequence[Policy],
        policy_sets: Sequence[PolicySet] = (),
        fallback_mode: PolicyFailureMode = PolicyFailureMode.DENY,
    ) -> PolicyEvaluationResult:
        """Evaluate request deterministically against policies and policy sets."""
        now_ts = _now_iso()
        res_id = f"policy-res-{request.id}"

        # 1. Build evaluation context
        context = PolicyEvaluationContext(
            actor=request.subject if request.actor_id else None,
            agent_id=request.actor_id or request.subject.id,
            goal=request.goal_id,
            agent_run=request.agent_run_id,
            subject=request.subject,
            resource=request.resource,
            action=request.action,
            environment=request.environment,
            permissions=request.permissions,
            sensitivity=request.sensitivity,
            risk=request.risk,
            evaluated_policies=tuple(policies),
            policy_sets=tuple(policy_sets),
            workflow_ref=request.workflow_plan_id,
            task_ref=request.task_id,
            operation_ref=request.operation_id,
            temporal_reference=now_ts,
            metadata=dict(request.metadata),
        )

        # 2. Filter enabled & valid policies, order by priority (descending) and ID (ascending)
        active_policies: list[Policy] = []
        for p in policies:
            if not p.enabled:
                continue
            # Check validity dates
            if p.valid_from and now_ts < p.valid_from:
                continue
            if p.valid_until and now_ts > p.valid_until:
                continue
            # Target check
            if matches_target(p.target, context):
                active_policies.append(p)

        active_policies.sort(key=lambda pol: (-pol.priority, pol.id, pol.version))

        # 3. Determine combining algorithm
        combining_alg = PolicyCombiningAlgorithm.DENY_OVERRIDES
        if policy_sets:
            combining_alg = policy_sets[0].combining_algorithm

        # 4. If no applicable policies exist, use fail-safe fallback
        if not active_policies:
            fb_decision = (
                PolicyDecision.REQUIRE_APPROVAL
                if fallback_mode == PolicyFailureMode.REQUIRE_APPROVAL
                else (
                    PolicyDecision.PAUSE
                    if fallback_mode == PolicyFailureMode.PAUSE
                    else PolicyDecision.DENY
                )
            )
            is_allow = fb_decision in (
                PolicyDecision.ALLOW,
                PolicyDecision.ALLOW_WITH_RESTRICTIONS,
            )
            return PolicyEvaluationResult(
                id=res_id,
                request_id=request.id,
                status=PolicyEvaluationStatus.COMPLETED,
                decision=fb_decision,
                allowed=is_allow,
                denied=fb_decision == PolicyDecision.DENY,
                requires_approval=fb_decision == PolicyDecision.REQUIRE_APPROVAL,
                requires_validation=fb_decision == PolicyDecision.REQUIRE_VALIDATION,
                requires_information=fb_decision == PolicyDecision.REQUIRE_INFORMATION,
                paused=fb_decision == PolicyDecision.PAUSE,
                applicable_policy_ids=(),
                matched_rule_ids=(),
                rule_evaluations=(),
                obligations=(),
                restrictions=(),
                advice=(),
                violations=(
                    (
                        PolicyViolation(
                            code="no_policy_applied",
                            message=f"No applicable policy matched request. Applied fallback decision: {fb_decision.value}",
                            severity=PolicySeverity.WARNING,
                        ),
                    )
                    if fb_decision == PolicyDecision.DENY
                    else ()
                ),
                warnings=(),
                errors=(),
                reason_codes=("fallback_policy_applied",),
                confidence=1.0,
                evaluated_at=now_ts,
                metadata={"fallback_mode": fallback_mode.value},
            )

        # 5. Evaluate policies and rules
        rule_evaluations: list[PolicyRuleEvaluation] = []
        matched_rule_ids: list[str] = []
        applicable_policy_ids: list[str] = []
        all_obligations: list[PolicyObligation] = []
        all_restrictions: list[PolicyRestriction] = []
        all_advice: list[PolicyAdvice] = []
        all_violations: list[PolicyViolation] = []
        all_warnings: list[PolicyWarning] = []
        reason_codes: list[str] = []

        decisions_collected: list[tuple[PolicyDecision, Policy, PolicyRule | None]] = []

        for policy in active_policies:
            applicable_policy_ids.append(policy.id)
            policy_matched = False

            # Add policy-level obligations/restrictions if defined
            for obs in policy.obligations:
                all_obligations.append(
                    PolicyObligation(
                        kind=obs.kind,
                        required=obs.required,
                        blocking=obs.blocking,
                        parameters=obs.parameters,
                        reason=obs.reason,
                        source_policy_id=policy.id,
                        source_rule_id=None,
                        metadata=obs.metadata,
                    )
                )
            for rst in policy.restrictions:
                all_restrictions.append(
                    PolicyRestriction(
                        kind=rst.kind,
                        description=rst.description,
                        parameters=rst.parameters,
                        source_policy_id=policy.id,
                        source_rule_id=None,
                        metadata=rst.metadata,
                    )
                )

            # Evaluate rules sorted by priority (descending) and ID (ascending)
            rules_sorted = sorted(policy.rules, key=lambda r: (-r.priority, r.id))
            for rule in rules_sorted:
                if not rule.enabled:
                    continue

                cond_results: list[dict[str, Any]] = []
                rule_matches = True

                for cond in rule.conditions:
                    c_pass = evaluate_condition(cond, context)
                    cond_results.append(
                        {
                            "field": cond.field,
                            "operator": cond.operator.value,
                            "expected": cond.value,
                            "passed": c_pass,
                        }
                    )
                    if not c_pass:
                        rule_matches = False
                        break

                if rule_matches:
                    policy_matched = True
                    matched_rule_ids.append(rule.id)
                    reason_codes.append(rule.reason_code)

                    # Collect obligations and restrictions from rule
                    for obs in rule.obligations:
                        all_obligations.append(
                            PolicyObligation(
                                kind=obs.kind,
                                required=obs.required,
                                blocking=obs.blocking,
                                parameters=obs.parameters,
                                reason=obs.reason,
                                source_policy_id=policy.id,
                                source_rule_id=rule.id,
                                metadata=obs.metadata,
                            )
                        )
                    for rst in rule.restrictions:
                        all_restrictions.append(
                            PolicyRestriction(
                                kind=rst.kind,
                                description=rst.description,
                                parameters=rst.parameters,
                                source_policy_id=policy.id,
                                source_rule_id=rule.id,
                                metadata=rst.metadata,
                            )
                        )

                    rule_eval = PolicyRuleEvaluation(
                        rule_id=rule.id,
                        policy_id=policy.id,
                        matched=True,
                        effect=rule.effect,
                        decision=rule.decision,
                        reason_code=rule.reason_code,
                        condition_results=tuple(cond_results),
                        obligations=rule.obligations,
                        restrictions=rule.restrictions,
                        evaluated_at=now_ts,
                    )
                    rule_evaluations.append(rule_eval)
                    decisions_collected.append((rule.decision, policy, rule))

                    if rule.decision == PolicyDecision.DENY:
                        all_violations.append(
                            PolicyViolation(
                                code=rule.reason_code,
                                message=f"Policy '{policy.id}' rule '{rule.id}' denied access: {rule.description}",
                                severity=PolicySeverity.ERROR,
                                policy_id=policy.id,
                                rule_id=rule.id,
                            )
                        )

                    # Shortcut for ordered algorithms
                    if combining_alg == PolicyCombiningAlgorithm.ORDERED_DENY_OVERRIDES:
                        if rule.decision == PolicyDecision.DENY:
                            break
                    elif (
                        combining_alg
                        == PolicyCombiningAlgorithm.ORDERED_PERMIT_OVERRIDES
                        and rule.decision
                        in (
                            PolicyDecision.ALLOW,
                            PolicyDecision.ALLOW_WITH_RESTRICTIONS,
                        )
                    ):
                        break

            # If policy had no rules but matched target, collect policy-level effect
            if not policy.rules and policy_matched:
                pol_decision = (
                    PolicyDecision.ALLOW
                    if policy.effect == PolicyEffect.PERMIT
                    else PolicyDecision.DENY
                )
                decisions_collected.append((pol_decision, policy, None))

        # 6. Resolve final decision using combining algorithm
        final_decision = self._combine_decisions(
            decisions_collected, combining_alg, fallback_mode
        )

        # Preserve obligations even if decision is deny/approval (unless explicitly excluded)
        # Deduplicate obligations and restrictions
        unique_obligations = self._deduplicate_obligations(all_obligations)
        unique_restrictions = self._deduplicate_restrictions(all_restrictions)

        is_allowed = final_decision in (
            PolicyDecision.ALLOW,
            PolicyDecision.ALLOW_WITH_RESTRICTIONS,
        )
        is_denied = final_decision == PolicyDecision.DENY
        req_approval = final_decision == PolicyDecision.REQUIRE_APPROVAL
        req_validation = final_decision == PolicyDecision.REQUIRE_VALIDATION
        req_info = final_decision == PolicyDecision.REQUIRE_INFORMATION
        is_paused = final_decision == PolicyDecision.PAUSE

        return PolicyEvaluationResult(
            id=res_id,
            request_id=request.id,
            status=PolicyEvaluationStatus.COMPLETED,
            decision=final_decision,
            allowed=is_allowed,
            denied=is_denied,
            requires_approval=req_approval,
            requires_validation=req_validation,
            requires_information=req_info,
            paused=is_paused,
            applicable_policy_ids=tuple(applicable_policy_ids),
            matched_rule_ids=tuple(matched_rule_ids),
            rule_evaluations=tuple(rule_evaluations),
            obligations=tuple(unique_obligations),
            restrictions=tuple(unique_restrictions),
            advice=tuple(all_advice),
            violations=tuple(all_violations),
            warnings=tuple(all_warnings),
            errors=(),
            reason_codes=tuple(sorted(set(reason_codes))),
            confidence=1.0,
            evaluated_at=now_ts,
            metadata={"combining_algorithm": combining_alg.value},
        )

    def _combine_decisions(
        self,
        decisions: list[tuple[PolicyDecision, Policy, PolicyRule | None]],
        algorithm: PolicyCombiningAlgorithm,
        fallback: PolicyFailureMode,
    ) -> PolicyDecision:
        """Combine rule/policy decisions into a final PolicyDecision."""
        if not decisions:
            return (
                PolicyDecision.REQUIRE_APPROVAL
                if fallback == PolicyFailureMode.REQUIRE_APPROVAL
                else (
                    PolicyDecision.PAUSE
                    if fallback == PolicyFailureMode.PAUSE
                    else PolicyDecision.DENY
                )
            )

        dec_values = [d[0] for d in decisions]

        if algorithm in (
            PolicyCombiningAlgorithm.DENY_OVERRIDES,
            PolicyCombiningAlgorithm.ORDERED_DENY_OVERRIDES,
        ):
            if PolicyDecision.DENY in dec_values:
                return PolicyDecision.DENY
            if PolicyDecision.REQUIRE_APPROVAL in dec_values:
                return PolicyDecision.REQUIRE_APPROVAL
            if PolicyDecision.REQUIRE_VALIDATION in dec_values:
                return PolicyDecision.REQUIRE_VALIDATION
            if PolicyDecision.REQUIRE_INFORMATION in dec_values:
                return PolicyDecision.REQUIRE_INFORMATION
            if PolicyDecision.PAUSE in dec_values:
                return PolicyDecision.PAUSE
            if PolicyDecision.ALLOW_WITH_RESTRICTIONS in dec_values:
                return PolicyDecision.ALLOW_WITH_RESTRICTIONS
            if PolicyDecision.ALLOW in dec_values:
                return PolicyDecision.ALLOW
            return PolicyDecision.DENY

        elif algorithm in (
            PolicyCombiningAlgorithm.PERMIT_OVERRIDES,
            PolicyCombiningAlgorithm.ORDERED_PERMIT_OVERRIDES,
        ):
            if any(
                d in (PolicyDecision.ALLOW, PolicyDecision.ALLOW_WITH_RESTRICTIONS)
                for d in dec_values
            ):
                return (
                    PolicyDecision.ALLOW_WITH_RESTRICTIONS
                    if PolicyDecision.ALLOW_WITH_RESTRICTIONS in dec_values
                    else PolicyDecision.ALLOW
                )
            if PolicyDecision.DENY in dec_values:
                return PolicyDecision.DENY
            if PolicyDecision.REQUIRE_APPROVAL in dec_values:
                return PolicyDecision.REQUIRE_APPROVAL
            return PolicyDecision.DENY

        elif algorithm == PolicyCombiningAlgorithm.FIRST_APPLICABLE:
            for dec in dec_values:
                if dec != PolicyDecision.NOT_APPLICABLE:
                    return dec
            return PolicyDecision.DENY

        elif algorithm == PolicyCombiningAlgorithm.ONLY_ONE_APPLICABLE:
            applicable = [d for d in dec_values if d != PolicyDecision.NOT_APPLICABLE]
            if len(applicable) == 1:
                return applicable[0]
            if len(applicable) > 1:
                raise PolicyCombiningError(
                    f"Algorithm only_one_applicable expected 1 matching decision, got {len(applicable)}"
                )
            return PolicyDecision.DENY

        return PolicyDecision.DENY

    def _deduplicate_obligations(
        self, obs: list[PolicyObligation]
    ) -> list[PolicyObligation]:
        seen: set[tuple[str, str, str]] = set()
        res: list[PolicyObligation] = []
        for o in obs:
            key = (o.kind.value, o.source_policy_id or "", o.source_rule_id or "")
            if key not in seen:
                seen.add(key)
                res.append(o)
        return res

    def _deduplicate_restrictions(
        self, rsts: list[PolicyRestriction]
    ) -> list[PolicyRestriction]:
        seen: set[tuple[str, str, str]] = set()
        res: list[PolicyRestriction] = []
        for r in rsts:
            key = (r.kind, r.source_policy_id or "", r.source_rule_id or "")
            if key not in seen:
                seen.add(key)
                res.append(r)
        return res
