"""Phase 9.25 – Agent Security, Permissions, and Isolation Service.

Implements the authorization boundary for the Agent Runtime using restrictive
intersection of all available permission sources.
"""

from __future__ import annotations

import logging
import re
import uuid
from collections.abc import Mapping
from types import MappingProxyType
from typing import Any

from cmm.agent_runtime.agent_security_contracts import (
    AgentPermissionContext,
    KillSwitchReport,
    PermissionCheckRequest,
    PermissionDecision,
    PromptInjectionAssessment,
    SecurityAuditEntry,
    UntrustedContentFinding,
    _now_utc,
    generate_audit_entry_id,
    generate_kill_switch_report_id,
)
from cmm.agent_runtime.agent_security_enums import (
    ExternalActionCategory,
    KillSwitchState,
    PermissionEffect,
    PromptInjectionResult,
    SensitivityLevel,
)
from cmm.agent_runtime.agent_security_errors import (
    AgentSecurityError,
    ExternalActionNotRegisteredError,
    KillSwitchActivationError,
    KillSwitchNotActiveError,
    KillSwitchReleaseError,
    PermissionDeniedError,
    PermissionEvaluationError,
    PromptInjectionBlockedError,
)
from cmm.agent_runtime.agent_security_store import InMemorySecurityStore
from cmm.agent_runtime.errors import (
    AgentRuntimeEventBusClosedError,
    AgentRuntimeEventDuplicateError,
    AgentRuntimeEventQueueFullError,
)
from cmm.agent_runtime.runtime_event_contracts import (
    AgentRuntimeEvent,
    AgentRuntimeEventHeader,
    AgentRuntimeEventPayload,
)

logger = logging.getLogger(__name__)

# Deterministic patterns for prompt injection detection (conservative rules)
_PROMPT_INJECTION_PATTERNS: tuple[tuple[str, str], ...] = (
    (r"(?i)ignore\s+(all\s+)?previous\s+instructions", "instruction_override"),
    (
        r"(?i)disregard\s+(all\s+)?(prior|previous)\s+(instructions|rules|policies)",
        "instruction_override",
    ),
    (r"(?i)you\s+are\s+now\s+(a|an)\s+\w+", "role_change"),
    (r"(?i)new\s+(objective|goal)\s*:", "goal_change"),
    (
        r"(?i)add\s+(this\s+)?(operation|action)\s+to\s+(your|the)\s+(allowed|permitted)\s+list",
        "operation_add",
    ),
    (
        r"(?i)modify\s+(the\s+)?(policy|policies|permissions|rules)",
        "policy_modification",
    ),
    (r"(?i)elevate\s+(your\s+)?(autonomy|permission|privilege)", "autonomy_elevation"),
    (
        r"(?i)grant\s+(yourself\s+)?(permission|access|authorization)",
        "permission_grant",
    ),
    (
        r"(?i)(provide|reveal|give|show)\s+(me\s+)?(the\s+)?(secret|password|api_key|token|credential)",
        "secret_request",
    ),
    (
        r"(?i)disable\s+(the\s+)?(validation|validator|security|permission\s+check)",
        "validation_disable",
    ),
    (r"(?i)auto-?approve", "auto_approval"),
    (r"(?i)increase\s+(your\s+)?(budget|limit|quota)", "budget_increase"),
    (
        r"(?i)(send|forward)\s+(this\s+)?(message|email|communication)\s+to",
        "communication_order",
    ),
    (r"(?i)alter\s+(the\s+)?(runtime|system|agent)", "runtime_alteration"),
)

# External actions that require explicit flags and additional controls
_RESTRICTED_EXTERNAL_ACTIONS: frozenset[ExternalActionCategory] = frozenset(
    {
        ExternalActionCategory.DELETION,
        ExternalActionCategory.PERMISSION_CHANGE,
        ExternalActionCategory.DEPLOYMENT,
        ExternalActionCategory.MEDICAL_ACTION,
        ExternalActionCategory.LEGAL_ACTION,
        ExternalActionCategory.FINANCIAL_ACTION,
        ExternalActionCategory.SENSITIVE_DATA_SHARE,
    }
)

# Categories severe enough to block content outright rather than merely flag it
_BLOCKING_INJECTION_CATEGORIES: frozenset[str] = frozenset(
    {
        "secret_request",
        "instruction_override",
        "auto_approval",
        "validation_disable",
    }
)

_INJECTION_RESULT_TO_EFFECT: dict[PromptInjectionResult, PermissionEffect] = {
    PromptInjectionResult.CLEAN: PermissionEffect.ALLOW,
    PromptInjectionResult.SUSPICIOUS: PermissionEffect.ALLOW_WITH_CONSTRAINTS,
    PromptInjectionResult.BLOCKED: PermissionEffect.DENY,
}

# Sentinel identity used to audit prompt-injection assessments taken outside
# of any agent run's permission context (e.g. pre-ingestion content scanning).
_SYSTEM_ACTOR_ID = "actor-security-system"
_SYSTEM_AGENT_ID = "agent-security-system"
_SYSTEM_RUN_ID = "run-security-system"


class AgentSecurityService:
    """
    Authorization boundary for the Agent Runtime.

    Evaluates permission checks using restrictive intersection:
    deny > allow, missing = deny, fail-closed on errors.
    """

    def __init__(
        self,
        store: InMemorySecurityStore | None = None,
        event_bus: Any | None = None,
    ) -> None:
        self._store = store or InMemorySecurityStore()
        self._event_bus = event_bus
        self._kill_switch_state = KillSwitchState.INACTIVE

    # ── Events (best-effort, never breaks the calling operation) ──────────────

    def _emit_event(
        self,
        event_type: str,
        *,
        agent_id: str | None = None,
        agent_run_id: str | None = None,
        goal_id: str | None = None,
        correlation_id: str | None = None,
        causation_id: str | None = None,
        payload: Mapping[str, Any] | None = None,
    ) -> None:
        if self._event_bus is None:
            return
        try:
            event = AgentRuntimeEvent(
                header=AgentRuntimeEventHeader(
                    event_id=f"evt-{uuid.uuid4().hex[:12]}",
                    event_type=event_type,
                    agent_id=agent_id,
                    agent_run_id=agent_run_id,
                    goal_id=goal_id,
                    correlation_id=correlation_id,
                    causation_id=causation_id,
                ),
                payload=AgentRuntimeEventPayload(data=dict(payload or {})),
            )
            self._event_bus.publish(event)
        except (
            AgentRuntimeEventBusClosedError,
            AgentRuntimeEventQueueFullError,
            AgentRuntimeEventDuplicateError,
        ):
            logger.exception("Security event emission failed for %s", event_type)

    # ── Prompt Injection ───────────────────────────────────────────────────────

    def assess_untrusted_content(
        self,
        content: str,
        content_id: str,
        assessor: str = "deterministic_rules",
        metadata: Mapping[str, Any] | None = None,
        context: AgentPermissionContext | None = None,
    ) -> PromptInjectionAssessment:
        """
        Assess untrusted content for prompt injection patterns.

        Uses deterministic conservative string matching rules. Untrusted content
        is always treated as data, never as instructions: a detection never
        mutates permissions by itself, and every assessment is audited.
        """
        if not isinstance(content, str):
            content = str(content)

        matched_patterns: list[str] = []
        categories: list[str] = []

        for pattern, category in _PROMPT_INJECTION_PATTERNS:
            if re.search(pattern, content):
                matched_patterns.append(pattern)
                if category not in categories:
                    categories.append(category)

        has_match = bool(matched_patterns)
        if has_match and any(
            cat in _BLOCKING_INJECTION_CATEGORIES for cat in categories
        ):
            result = PromptInjectionResult.BLOCKED
        elif has_match:
            result = PromptInjectionResult.SUSPICIOUS
        else:
            result = PromptInjectionResult.CLEAN

        finding = UntrustedContentFinding(
            result=result,
            categories=tuple(categories),
            matched_patterns=tuple(matched_patterns),
            confidence=1.0 if has_match else 0.0,
            metadata=MappingProxyType(dict(metadata or {})),
        )

        assessment = PromptInjectionAssessment(
            content_id=content_id,
            finding=finding,
            assessed_at=_now_utc(),
            assessor=assessor,
            metadata=MappingProxyType({}),
        )

        self._record_prompt_injection_audit(content_id, result, categories, context)

        if result == PromptInjectionResult.BLOCKED:
            raise PromptInjectionBlockedError(
                "Prompt injection detected and content blocked",
                {"content_id": content_id, "categories": categories},
            )

        return assessment

    def _record_prompt_injection_audit(
        self,
        content_id: str,
        result: PromptInjectionResult,
        categories: list[str],
        context: AgentPermissionContext | None,
    ) -> None:
        """Record an audit entry for every prompt-injection assessment.

        Never stores the assessed content itself, only the content identifier,
        matched category labels, and the resulting classification.
        """
        decision_effect = _INJECTION_RESULT_TO_EFFECT[result]
        entry = SecurityAuditEntry(
            id=generate_audit_entry_id(),
            permission_context_id=context.id if context else "no-context",
            actor_id=context.actor_id if context else _SYSTEM_ACTOR_ID,
            agent_id=context.agent_id if context else _SYSTEM_AGENT_ID,
            agent_run_id=context.agent_run_id if context else _SYSTEM_RUN_ID,
            goal_id=context.goal_id if context else None,
            action="prompt_injection_assessment",
            resources=(content_id,),
            decision=decision_effect,
            reason_codes=tuple(categories),
            sensitivity=None,
            requested_elevation=False,
            prompt_injection_finding=result,
            kill_switch_state=self._kill_switch_state,
            timestamp=_now_utc(),
        )
        self._store.add_audit_entry(entry)
        self._emit_event(
            "security.prompt_injection.assessed",
            agent_id=entry.agent_id,
            agent_run_id=entry.agent_run_id,
            goal_id=entry.goal_id,
            payload={
                "content_id": content_id,
                "result": result.value,
                "categories": list(categories),
            },
        )

    # ── Permission Evaluation ─────────────────────────────────────────────────

    def check_permission(
        self,
        request: PermissionCheckRequest,
        context: AgentPermissionContext | None = None,
        agent_capabilities: dict[str, Any] | None = None,
        policy_result: dict[str, Any] | None = None,
        has_valid_approval: bool = False,
        checkpoint_active: bool = False,
    ) -> PermissionDecision:
        """
        Evaluate a permission check request against the authorization boundary.

        Returns a PermissionDecision using restrictive intersection.
        """
        start_time = _now_utc()
        reason_codes: list[str] = []
        denied_dimensions: list[str] = []
        required_approvals: list[str] = []
        obligations: list[str] = []
        context_id = context.id if context else "no-context"

        try:
            # 1. Kill switch active check (highest priority)
            if self._kill_switch_state == KillSwitchState.ACTIVE:
                return PermissionDecision(
                    effect=PermissionEffect.KILL_SWITCH_ACTIVE,
                    reason_codes=("kill_switch_active",),
                    denied_dimensions=("kill_switch",),
                    required_approvals=(),
                    obligations=("pause_operations",),
                    effective_constraints=MappingProxyType({}),
                    evaluated_context_id=context_id,
                    timestamp=start_time,
                )

            # 2. Context required
            if context is None:
                denied_dimensions.append("missing_context")
                return PermissionDecision(
                    effect=PermissionEffect.DENY,
                    reason_codes=("no_context",),
                    denied_dimensions=tuple(denied_dimensions),
                    required_approvals=(),
                    obligations=(),
                    effective_constraints=MappingProxyType({}),
                    evaluated_context_id=context_id,
                    timestamp=start_time,
                )

            # 3. Expired context
            if context.is_expired:
                return PermissionDecision(
                    effect=PermissionEffect.EXPIRED,
                    reason_codes=("context_expired",),
                    denied_dimensions=("expiration",),
                    required_approvals=(),
                    obligations=("refresh_context",),
                    effective_constraints=MappingProxyType({}),
                    evaluated_context_id=context_id,
                    timestamp=start_time,
                )

            # 4. Policy error or explicit deny → fail-closed
            if policy_result is not None and policy_result.get("error"):
                denied_dimensions.append("policy_error")
                return PermissionDecision(
                    effect=PermissionEffect.DENY,
                    reason_codes=("policy_error",),
                    denied_dimensions=tuple(denied_dimensions),
                    required_approvals=(),
                    obligations=("retry_policy_evaluation",),
                    effective_constraints=MappingProxyType({}),
                    evaluated_context_id=context_id,
                    timestamp=start_time,
                )

            # 5. Explicit policy deny
            if policy_result is not None and policy_result.get("decision") == "deny":
                denied_dimensions.append("policy_deny")
                return PermissionDecision(
                    effect=PermissionEffect.DENY,
                    reason_codes=("policy_deny",),
                    denied_dimensions=tuple(denied_dimensions),
                    required_approvals=(),
                    obligations=(),
                    effective_constraints=MappingProxyType(
                        dict(policy_result.get("constraints", {}))
                    ),
                    evaluated_context_id=context_id,
                    timestamp=start_time,
                )

            # 6. Agent/run/goal mismatch
            if request.agent_id and request.agent_id != context.agent_id:
                denied_dimensions.append("agent_mismatch")
            if request.agent_run_id and request.agent_run_id != context.agent_run_id:
                denied_dimensions.append("run_mismatch")
            if request.goal_id and request.goal_id != context.goal_id:
                denied_dimensions.append("goal_mismatch")
            if request.actor_id and request.actor_id != context.actor_id:
                denied_dimensions.append("actor_mismatch")
            if request.actor_id and request.actor_id != context.owner_actor_id:
                denied_dimensions.append("owner_mismatch")

            if denied_dimensions:
                return PermissionDecision(
                    effect=PermissionEffect.DENY,
                    reason_codes=("identity_mismatch",),
                    denied_dimensions=tuple(denied_dimensions),
                    required_approvals=(),
                    obligations=(),
                    effective_constraints=MappingProxyType({}),
                    evaluated_context_id=context_id,
                    timestamp=start_time,
                )

            # 7. Autonomy required exceeds allowed
            if (
                request.required_autonomy_level is not None
                and request.required_autonomy_level > context.maximum_autonomy_level
            ):
                denied_dimensions.append("autonomy_exceeded")
                reason_codes.append("autonomy_exceeded")
                obligations.append("request_autonomy_elevation")

            # 8. Sensitivity not allowed
            if (
                request.sensitivity is not None
                and request.sensitivity not in context.allowed_sensitivity_levels
            ):
                denied_dimensions.append("sensitivity_not_allowed")
                reason_codes.append("sensitivity_not_allowed")

            # 9. Resources not authorized
            for resource in request.resources:
                domain = resource.split("/")[0] if "/" in resource else resource
                if (
                    resource not in context.allowed_resources
                    and domain not in context.allowed_domains
                ):
                    denied_dimensions.append("resource_not_authorized")
                    reason_codes.append("resource_not_authorized")
                    break

            # 10. Operation not in allowlist
            if (
                request.operation
                and request.operation not in context.allowed_operations
            ):
                denied_dimensions.append("operation_not_permitted")
                reason_codes.append("operation_not_permitted")

            # 11. Domain check
            if request.domain and request.domain not in context.allowed_domains:
                denied_dimensions.append("domain_not_allowed")
                reason_codes.append("domain_not_allowed")

            # Build constraint flags for the decision
            constraints: dict[str, Any] = {}

            # 12. External access
            if request.external_access and not context.allow_external_access:
                denied_dimensions.append("external_access_not_allowed")

            # 13. External models
            if request.external_model and not context.allow_external_models:
                denied_dimensions.append("external_model_not_allowed")

            # 14. Memory write
            if request.memory_write and not context.allow_memory_write:
                denied_dimensions.append("memory_write_not_allowed")

            # 15. Goal creation
            if request.goal_creation and not context.allow_goal_creation:
                denied_dimensions.append("goal_creation_not_allowed")

            # 16. Delegation
            if request.delegation and not context.allow_delegation:
                denied_dimensions.append("delegation_not_allowed")

            # 17. Publication
            if request.publication and not context.allow_publication:
                denied_dimensions.append("publication_not_allowed")

            # 18. Communications
            if request.communications and not context.allow_communications:
                denied_dimensions.append("communications_not_allowed")

            # 19. Destructive actions
            if request.destructive_action:
                if not context.allow_destructive_actions:
                    denied_dimensions.append("destructive_action_not_allowed")
                else:
                    required_approvals.append("destructive_action_approval")
                    constraints["requires_checkpoint"] = True

            # 20. Permission elevation
            if request.requested_elevation and not context.allow_permission_elevation:
                denied_dimensions.append("permission_elevation_not_allowed")

            # 21. External action classification and controls
            if request.operation:
                try:
                    action_category = ExternalActionCategory(request.operation)
                except ValueError:
                    action_category = None

                if action_category is not None:
                    # Check if operation is registered
                    if action_category in _RESTRICTED_EXTERNAL_ACTIONS:
                        if not context.allow_external_access:
                            denied_dimensions.append("external_action_restricted")
                        else:
                            required_approvals.append(
                                f"{action_category.value}_approval"
                            )
                            constraints["checkpoint_required"] = True
                    elif (
                        action_category
                        in {
                            ExternalActionCategory.EMAIL,
                            ExternalActionCategory.MESSAGE,
                            ExternalActionCategory.PUBLICATION,
                        }
                        and not context.allow_communications
                        and not context.allow_publication
                    ):
                        denied_dimensions.append("communication_not_allowed")

            # 22. Budget constraints
            if request.required_budget:
                constraints["required_budget"] = list(request.required_budget)

            # 23. Lock constraints
            if request.required_locks:
                constraints["required_locks"] = list(request.required_locks)

            # 24. Checkpoint constraints
            if request.required_checkpoints:
                constraints["required_checkpoints"] = list(request.required_checkpoints)

            if denied_dimensions:
                effect = (
                    PermissionEffect.APPROVAL_REQUIRED
                    if required_approvals
                    else PermissionEffect.DENY
                )
                return PermissionDecision(
                    effect=effect,
                    reason_codes=tuple(reason_codes) or ("constraint_violation",),
                    denied_dimensions=tuple(denied_dimensions),
                    required_approvals=tuple(required_approvals),
                    obligations=tuple(obligations),
                    effective_constraints=MappingProxyType(constraints),
                    evaluated_context_id=context_id,
                    timestamp=start_time,
                )

            # 25. Approval required via policy result
            if (
                policy_result is not None
                and policy_result.get("decision") == "approval_required"
            ):
                required_approvals.extend(policy_result.get("required_approvals", []))
                return PermissionDecision(
                    effect=PermissionEffect.APPROVAL_REQUIRED,
                    reason_codes=("policy_approval_required",),
                    denied_dimensions=(),
                    required_approvals=tuple(required_approvals),
                    obligations=tuple(obligations),
                    effective_constraints=MappingProxyType(constraints),
                    evaluated_context_id=context_id,
                    timestamp=start_time,
                )

            # 26. Allowed with constraints
            if constraints or required_approvals:
                return PermissionDecision(
                    effect=PermissionEffect.ALLOW_WITH_CONSTRAINTS,
                    reason_codes=("granted_with_constraints",),
                    denied_dimensions=(),
                    required_approvals=tuple(required_approvals),
                    obligations=tuple(obligations),
                    effective_constraints=MappingProxyType(constraints),
                    evaluated_context_id=context_id,
                    timestamp=start_time,
                )

            # 27. Plain allow
            return PermissionDecision(
                effect=PermissionEffect.ALLOW,
                reason_codes=("granted",),
                denied_dimensions=(),
                required_approvals=(),
                obligations=(),
                effective_constraints=MappingProxyType(constraints),
                evaluated_context_id=context_id,
                timestamp=start_time,
            )

        except PermissionDeniedError:
            raise
        except (AgentSecurityError, KeyError, ValueError, TypeError) as exc:
            raise PermissionEvaluationError(
                f"Permission evaluation failed: {exc}"
            ) from exc

    # ── Audit ──────────────────────────────────────────────────────────────────

    def record_audit(
        self,
        permission_context_id: str,
        actor_id: str,
        agent_id: str,
        agent_run_id: str,
        action: str,
        resources: tuple[str, ...],
        decision: PermissionDecision,
        sensitivity: SensitivityLevel | None = None,
        requested_elevation: bool = False,
        trace_id: str | None = None,
        correlation_id: str | None = None,
        metadata: Mapping[str, Any] | None = None,
    ) -> SecurityAuditEntry:
        """Create and store an audit entry for a permission evaluation."""
        goal_id = None
        ctx = self._store.get_permission_context(permission_context_id)
        if ctx:
            goal_id = ctx.goal_id

        entry = SecurityAuditEntry(
            id=generate_audit_entry_id(),
            permission_context_id=permission_context_id,
            actor_id=actor_id,
            agent_id=agent_id,
            agent_run_id=agent_run_id,
            goal_id=goal_id,
            action=action,
            resources=resources,
            decision=decision.effect,
            reason_codes=decision.reason_codes,
            sensitivity=sensitivity,
            requested_elevation=requested_elevation,
            prompt_injection_finding=PromptInjectionResult.CLEAN,
            kill_switch_state=self._kill_switch_state,
            timestamp=_now_utc(),
            trace_id=trace_id,
            correlation_id=correlation_id,
            metadata=MappingProxyType(dict(metadata or {})),
        )
        self._store.add_audit_entry(entry)
        self._emit_event(
            "security.audit.recorded",
            agent_id=entry.agent_id,
            agent_run_id=entry.agent_run_id,
            goal_id=entry.goal_id,
            correlation_id=correlation_id,
            payload={"audit_entry_id": entry.id, "decision": entry.decision.value},
        )

        return entry

    # ── Kill Switch ────────────────────────────────────────────────────────────

    def activate_kill_switch(
        self,
        activated_by: str,
        reason: str,
        affected_runs: tuple[str, ...] = (),
        blocked_operations: tuple[str, ...] = (),
    ) -> KillSwitchReport:
        """
        Activate the kill switch.

        Blocks new operations, preserves state, identifies affected runs,
        and emits events. Idempotent.
        """
        if self._kill_switch_state == KillSwitchState.ACTIVE:
            existing = self._store.get_kill_switch_report()
            if existing:
                return existing
            return KillSwitchReport(
                id=generate_kill_switch_report_id(),
                state=KillSwitchState.ACTIVE,
                affected_runs=(),
                blocked_operations=(),
                released_locks=(),
                canceled_reservations=(),
                in_progress_operations_marked=(),
                recovery_requested=False,
                errors=(),
                activated_at=_now_utc(),
                activated_by=activated_by,
                reason=reason,
            )

        self._kill_switch_state = KillSwitchState.ACTIVATING

        try:
            report = KillSwitchReport(
                id=generate_kill_switch_report_id(),
                state=KillSwitchState.ACTIVE,
                affected_runs=affected_runs,
                blocked_operations=blocked_operations,
                released_locks=(),
                canceled_reservations=(),
                in_progress_operations_marked=(),
                recovery_requested=True,
                errors=(),
                activated_at=_now_utc(),
                activated_by=activated_by,
                reason=reason,
            )
            self._store.set_kill_switch_report(report)
            self._kill_switch_state = KillSwitchState.ACTIVE

            self._emit_event(
                "security.kill_switch.activated",
                payload={
                    "report_id": report.id,
                    "activated_by": activated_by,
                    "affected_runs": list(affected_runs),
                },
            )

            return report

        except (AgentSecurityError, ValueError, TypeError) as exc:
            self._kill_switch_state = KillSwitchState.FAILED
            raise KillSwitchActivationError(
                f"Kill switch activation failed: {exc}"
            ) from exc

    def release_kill_switch(
        self,
        released_by: str,
    ) -> KillSwitchReport:
        """
        Release the kill switch.

        Requires authorized actor. Does not resume runs automatically.
        """
        if self._kill_switch_state != KillSwitchState.ACTIVE:
            raise KillSwitchNotActiveError(
                "Cannot release kill switch: not in active state",
                {"current_state": self._kill_switch_state.value},
            )

        existing = self._store.get_kill_switch_report()
        if existing is None:
            raise KillSwitchNotActiveError("No kill switch report found to release")

        if released_by != existing.activated_by:
            raise KillSwitchReleaseError(
                "released_by is not authorized to release this kill switch",
                {"activated_by": existing.activated_by, "released_by": released_by},
            )

        now = _now_utc()
        released_report = KillSwitchReport(
            id=existing.id,
            state=KillSwitchState.RELEASED,
            affected_runs=existing.affected_runs,
            blocked_operations=existing.blocked_operations,
            released_locks=existing.released_locks,
            canceled_reservations=existing.canceled_reservations,
            in_progress_operations_marked=existing.in_progress_operations_marked,
            recovery_requested=False,
            errors=existing.errors,
            activated_at=existing.activated_at,
            activated_by=existing.activated_by,
            reason=existing.reason,
            released_at=now,
            released_by=released_by,
        )
        self._store.set_kill_switch_report(released_report)
        self._kill_switch_state = KillSwitchState.RELEASED

        self._emit_event(
            "security.kill_switch.released",
            payload={"report_id": released_report.id, "released_by": released_by},
        )

        return released_report

    def request_kill_switch_recovery(self) -> None:
        """Request recovery after kill switch release.

        Never resumes runs automatically; callers must re-evaluate permissions
        via ``check_permission`` before allowing any operation to proceed.
        """
        if self._kill_switch_state != KillSwitchState.RELEASED:
            return
        self._kill_switch_state = KillSwitchState.RECOVERING

        self._emit_event("security.kill_switch.recovery_requested")

    # ── External Actions ───────────────────────────────────────────────────────

    def is_external_action_allowed(
        self,
        action: ExternalActionCategory,
        context: AgentPermissionContext,
        has_approval: bool = False,
        checkpoint_active: bool = False,
    ) -> tuple[bool, str]:
        """
        Check if an external action is allowed under the current context.

        Returns (allowed, reason).
        """
        if not isinstance(action, ExternalActionCategory):
            raise ExternalActionNotRegisteredError(
                f"Action is not a registered ExternalActionCategory: {action!r}"
            )

        # All external action categories are denied by default: the explicit
        # context flag is required regardless of category.
        if not context.allow_external_access:
            return False, "external_access_not_allowed"

        if action in _RESTRICTED_EXTERNAL_ACTIONS:
            if not has_approval:
                return False, "approval_required"
            if not checkpoint_active:
                return False, "checkpoint_required"

        return True, "allowed"

    # ── Properties ─────────────────────────────────────────────────────────────

    @property
    def kill_switch_state(self) -> KillSwitchState:
        """Current kill switch state."""
        return self._kill_switch_state

    @property
    def store(self) -> InMemorySecurityStore:
        """Underlying security store."""
        return self._store


__all__ = ["AgentSecurityService"]
