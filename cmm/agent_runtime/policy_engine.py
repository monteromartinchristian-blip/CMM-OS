"""Phase 9.8 – Policy Engine.

Centralizes safety, authorization, compliance, and autonomy policy evaluations across the runtime.
"""

from __future__ import annotations

from collections.abc import Sequence

from .enums import (
    PolicyCombiningAlgorithm,
    PolicyConditionOperator,
    PolicyDecision,
    PolicyEffect,
    PolicyFailureMode,
    PolicyObligationKind,
    PolicyResourceKind,
    PolicyRiskLevel,
    PolicyScope,
)
from .errors import PolicyResolutionError
from .policy_contracts import (
    Policy,
    PolicyCondition,
    PolicyEvaluationRequest,
    PolicyEvaluationResult,
    PolicyObligation,
    PolicyRule,
    PolicySet,
)
from .policy_evaluator import DefaultPolicyEvaluator, PolicyEvaluator
from .policy_store import PolicyRepository


def build_initial_system_policies() -> tuple[list[Policy], list[PolicySet]]:
    """Build canonical initial policy sets for operational safety, permissions, sensitivity, autonomy, plans, and info acquisition."""
    policies: list[Policy] = []
    policy_sets: list[PolicySet] = []

    # 1. Operational Safety Policy
    pol_op_safety = Policy(
        id="policy-op-safety",
        name="Operational Safety Policy",
        description="Enforces operational safety rules for commands, shell, risk, and mutations.",
        priority=100,
        scope=PolicyScope.GLOBAL,
        effect=PolicyEffect.PERMIT,
        rules=(
            PolicyRule(
                id="rule-unregistered-op",
                policy_id="policy-op-safety",
                description="Deny unregistered operations",
                conditions=(
                    PolicyCondition(
                        field="action.name",
                        operator=PolicyConditionOperator.EQUALS,
                        value="execute_operation",
                    ),
                    PolicyCondition(
                        field="action.parameters.is_registered",
                        operator=PolicyConditionOperator.EQUALS,
                        value=False,
                    ),
                ),
                effect=PolicyEffect.DENY,
                decision=PolicyDecision.DENY,
                priority=100,
                reason_code="unregistered_operation",
            ),
            PolicyRule(
                id="rule-registered-low-risk-op",
                policy_id="policy-op-safety",
                description="Allow registered low-risk operations when no denying rule applies",
                conditions=(
                    PolicyCondition(
                        field="action.name",
                        operator=PolicyConditionOperator.EQUALS,
                        value="execute_operation",
                    ),
                    PolicyCondition(
                        field="action.parameters.is_registered",
                        operator=PolicyConditionOperator.EQUALS,
                        value=True,
                    ),
                    PolicyCondition(
                        field="context.risk",
                        operator=PolicyConditionOperator.IN,
                        value=(
                            PolicyRiskLevel.NONE.value,
                            PolicyRiskLevel.LOW.value,
                        ),
                    ),
                ),
                effect=PolicyEffect.PERMIT,
                decision=PolicyDecision.ALLOW,
                priority=60,
                reason_code="registered_low_risk_operation_allowed",
            ),
            PolicyRule(
                id="rule-prohibited-op",
                policy_id="policy-op-safety",
                description="Deny explicitly prohibited operations",
                conditions=(
                    PolicyCondition(
                        field="action.parameters.is_prohibited",
                        operator=PolicyConditionOperator.EQUALS,
                        value=True,
                    ),
                ),
                effect=PolicyEffect.DENY,
                decision=PolicyDecision.DENY,
                priority=95,
                reason_code="prohibited_operation",
            ),
            PolicyRule(
                id="rule-unauthorized-shell",
                policy_id="policy-op-safety",
                description="Deny unauthorized shell execution",
                conditions=(
                    PolicyCondition(
                        field="action.name",
                        operator=PolicyConditionOperator.EQUALS,
                        value="shell",
                    ),
                    PolicyCondition(
                        field="context.permissions",
                        operator=PolicyConditionOperator.NOT_CONTAINS,
                        value="exec_shell",
                    ),
                ),
                effect=PolicyEffect.DENY,
                decision=PolicyDecision.DENY,
                priority=90,
                reason_code="unauthorized_shell",
            ),
            PolicyRule(
                id="rule-critical-risk",
                policy_id="policy-op-safety",
                description="Require human approval for critical risk operations",
                conditions=(
                    PolicyCondition(
                        field="context.risk",
                        operator=PolicyConditionOperator.EQUALS,
                        value=PolicyRiskLevel.CRITICAL.value,
                    ),
                ),
                effect=PolicyEffect.OBLIGATION,
                decision=PolicyDecision.REQUIRE_APPROVAL,
                priority=85,
                reason_code="critical_risk_requires_approval",
                obligations=(
                    PolicyObligation(
                        kind=PolicyObligationKind.REQUIRE_APPROVAL,
                        required=True,
                        blocking=True,
                        reason="Critical risk level requires explicit user approval",
                    ),
                ),
            ),
            PolicyRule(
                id="rule-high-risk",
                policy_id="policy-op-safety",
                description="Require approval or reinforced validation for high risk operations",
                conditions=(
                    PolicyCondition(
                        field="context.risk",
                        operator=PolicyConditionOperator.EQUALS,
                        value=PolicyRiskLevel.HIGH.value,
                    ),
                ),
                effect=PolicyEffect.OBLIGATION,
                decision=PolicyDecision.REQUIRE_APPROVAL,
                priority=80,
                reason_code="high_risk_requires_approval",
                obligations=(
                    PolicyObligation(
                        kind=PolicyObligationKind.REQUIRE_VALIDATION,
                        required=True,
                        blocking=True,
                        reason="High risk operation requires validation",
                    ),
                ),
            ),
            PolicyRule(
                id="rule-unprotected-irreversible",
                policy_id="policy-op-safety",
                description="Require approval for irreversible mutations",
                conditions=(
                    PolicyCondition(
                        field="action.is_mutation",
                        operator=PolicyConditionOperator.EQUALS,
                        value=True,
                    ),
                    PolicyCondition(
                        field="action.is_reversible",
                        operator=PolicyConditionOperator.EQUALS,
                        value=False,
                    ),
                ),
                effect=PolicyEffect.OBLIGATION,
                decision=PolicyDecision.REQUIRE_APPROVAL,
                priority=75,
                reason_code="irreversible_mutation_requires_approval",
                obligations=(
                    PolicyObligation(
                        kind=PolicyObligationKind.REQUIRE_APPROVAL,
                        required=True,
                        blocking=True,
                        reason="Irreversible mutation action requires approval",
                    ),
                ),
            ),
            PolicyRule(
                id="rule-mandatory-rollback",
                policy_id="policy-op-safety",
                description="Enforce rollback capability on reversible mutations",
                conditions=(
                    PolicyCondition(
                        field="action.is_mutation",
                        operator=PolicyConditionOperator.EQUALS,
                        value=True,
                    ),
                    PolicyCondition(
                        field="action.is_reversible",
                        operator=PolicyConditionOperator.EQUALS,
                        value=True,
                    ),
                ),
                effect=PolicyEffect.OBLIGATION,
                decision=PolicyDecision.ALLOW_WITH_RESTRICTIONS,
                priority=70,
                reason_code="enforce_rollback_capability",
                obligations=(
                    PolicyObligation(
                        kind=PolicyObligationKind.ENFORCE_ROLLBACK,
                        required=True,
                        blocking=True,
                        reason="Reversible mutation requires rollback checkpoint",
                    ),
                ),
            ),
        ),
    )
    policies.append(pol_op_safety)

    # 2. Permissions Policy
    pol_permissions = Policy(
        id="policy-permissions",
        name="Permissions Policy",
        description="Enforces strict permission authorization checks.",
        priority=90,
        scope=PolicyScope.GLOBAL,
        effect=PolicyEffect.PERMIT,
        rules=(
            PolicyRule(
                id="rule-missing-perm",
                policy_id="policy-permissions",
                description="Deny missing required permission",
                conditions=(
                    PolicyCondition(
                        field="action.parameters.required_permission",
                        operator=PolicyConditionOperator.EXISTS,
                        value=True,
                    ),
                    PolicyCondition(
                        field="action.parameters.has_permission",
                        operator=PolicyConditionOperator.EQUALS,
                        value=False,
                    ),
                ),
                effect=PolicyEffect.DENY,
                decision=PolicyDecision.DENY,
                priority=100,
                reason_code="missing_required_permission",
            ),
            PolicyRule(
                id="rule-unauthorized-actor",
                policy_id="policy-permissions",
                description="Deny unauthorized actor",
                conditions=(
                    PolicyCondition(
                        field="subject.id",
                        operator=PolicyConditionOperator.EQUALS,
                        value="unauthorized",
                    ),
                ),
                effect=PolicyEffect.DENY,
                decision=PolicyDecision.DENY,
                priority=95,
                reason_code="unauthorized_actor",
            ),
            PolicyRule(
                id="rule-expired-perm",
                policy_id="policy-permissions",
                description="Deny expired temporary permission",
                conditions=(
                    PolicyCondition(
                        field="action.parameters.permission_expired",
                        operator=PolicyConditionOperator.EQUALS,
                        value=True,
                    ),
                ),
                effect=PolicyEffect.DENY,
                decision=PolicyDecision.DENY,
                priority=90,
                reason_code="permission_expired",
            ),
        ),
    )
    policies.append(pol_permissions)

    # 3. Data & Sensitivity Policy
    pol_sensitivity = Policy(
        id="policy-data-sensitivity",
        name="Data & Sensitivity Policy",
        description="Protects restricted and confidential resources.",
        priority=80,
        scope=PolicyScope.GLOBAL,
        effect=PolicyEffect.PERMIT,
        rules=(
            PolicyRule(
                id="rule-ext-transmission-restricted",
                policy_id="policy-data-sensitivity",
                description="Deny external transmission of restricted data",
                conditions=(
                    PolicyCondition(
                        field="resource.sensitivity",
                        operator=PolicyConditionOperator.EQUALS,
                        value="restricted",
                    ),
                    PolicyCondition(
                        field="action.name",
                        operator=PolicyConditionOperator.EQUALS,
                        value="search_external_source",
                    ),
                ),
                effect=PolicyEffect.DENY,
                decision=PolicyDecision.DENY,
                priority=100,
                reason_code="external_transmission_restricted",
            ),
            PolicyRule(
                id="rule-sensitive-ext-source",
                policy_id="policy-data-sensitivity",
                description="Deny sending sensitive data to external sources without authorization",
                conditions=(
                    PolicyCondition(
                        field="resource.sensitivity",
                        operator=PolicyConditionOperator.IN,
                        value=("restricted", "confidential"),
                    ),
                    PolicyCondition(
                        field="resource.kind",
                        operator=PolicyConditionOperator.EQUALS,
                        value=PolicyResourceKind.EXTERNAL.value,
                    ),
                ),
                effect=PolicyEffect.DENY,
                decision=PolicyDecision.DENY,
                priority=95,
                reason_code="sensitive_data_to_external_source",
            ),
        ),
    )
    policies.append(pol_sensitivity)

    # 4. Plans Policy
    pol_plans = Policy(
        id="policy-plans",
        name="Workflow Plans Policy",
        description="Enforces structural validation, non-prohibited operations, and plan state checks.",
        priority=70,
        scope=PolicyScope.WORKFLOW,
        effect=PolicyEffect.PERMIT,
        rules=(
            PolicyRule(
                id="rule-invalid-plan",
                policy_id="policy-plans",
                description="Deny invalid workflow plan",
                conditions=(
                    PolicyCondition(
                        field="action.parameters.plan_validation_status",
                        operator=PolicyConditionOperator.EQUALS,
                        value="failed",
                    ),
                ),
                effect=PolicyEffect.DENY,
                decision=PolicyDecision.DENY,
                priority=100,
                reason_code="invalid_workflow_plan",
            ),
            PolicyRule(
                id="rule-superseded-plan",
                policy_id="policy-plans",
                description="Deny superseded workflow plan",
                conditions=(
                    PolicyCondition(
                        field="action.parameters.plan_status",
                        operator=PolicyConditionOperator.EQUALS,
                        value="superseded",
                    ),
                ),
                effect=PolicyEffect.DENY,
                decision=PolicyDecision.DENY,
                priority=95,
                reason_code="superseded_workflow_plan",
            ),
        ),
    )
    policies.append(pol_plans)

    # 5. Information Acquisition Policy
    pol_info_acq = Policy(
        id="policy-info-acquisition",
        name="Information Acquisition Policy",
        description="Enforces authorization and safety for external search, inferences, and user questions.",
        priority=65,
        scope=PolicyScope.GLOBAL,
        effect=PolicyEffect.PERMIT,
        rules=(
            PolicyRule(
                id="rule-ext-search-no-perm",
                policy_id="policy-info-acquisition",
                description="Deny external search when sensitivity is restricted or external search unauthorized",
                conditions=(
                    PolicyCondition(
                        field="action.name",
                        operator=PolicyConditionOperator.EQUALS,
                        value="search_external_source",
                    ),
                    PolicyCondition(
                        field="context.permissions",
                        operator=PolicyConditionOperator.NOT_CONTAINS,
                        value="external_search",
                    ),
                ),
                effect=PolicyEffect.DENY,
                decision=PolicyDecision.DENY,
                priority=100,
                reason_code="external_search_unauthorized",
            ),
            PolicyRule(
                id="rule-uncertainty-blocking-gap",
                policy_id="policy-info-acquisition",
                description="Deny accepting uncertainty when gap is blocking",
                conditions=(
                    PolicyCondition(
                        field="action.name",
                        operator=PolicyConditionOperator.EQUALS,
                        value="accept_uncertainty",
                    ),
                    PolicyCondition(
                        field="action.parameters.is_blocking",
                        operator=PolicyConditionOperator.EQUALS,
                        value=True,
                    ),
                ),
                effect=PolicyEffect.DENY,
                decision=PolicyDecision.DENY,
                priority=95,
                reason_code="cannot_accept_uncertainty_on_blocking_gap",
            ),
            PolicyRule(
                id="rule-ask-secrets",
                policy_id="policy-info-acquisition",
                description="Deny questions that request user secrets",
                conditions=(
                    PolicyCondition(
                        field="action.name",
                        operator=PolicyConditionOperator.EQUALS,
                        value="ask_user",
                    ),
                    PolicyCondition(
                        field="action.parameters.requests_secret",
                        operator=PolicyConditionOperator.EQUALS,
                        value=True,
                    ),
                ),
                effect=PolicyEffect.DENY,
                decision=PolicyDecision.DENY,
                priority=90,
                reason_code="prohibit_asking_for_secrets",
            ),
        ),
    )
    policies.append(pol_info_acq)

    # 6. Cognitive Result Policy
    pol_cognitive = Policy(
        id="policy-cognitive-results",
        name="Cognitive Results Policy",
        description=(
            "Evaluates structured recommendations produced by the Cognitive Adapter "
            "without converting them into execution authority."
        ),
        priority=60,
        scope=PolicyScope.GLOBAL,
        effect=PolicyEffect.PERMIT,
        rules=(
            PolicyRule(
                id="rule-cognitive-blocked",
                policy_id="policy-cognitive-results",
                description="Pause when the cognitive result is blocked",
                conditions=(
                    PolicyCondition(
                        field="action.parameters.blocked",
                        operator=PolicyConditionOperator.EQUALS,
                        value=True,
                    ),
                ),
                effect=PolicyEffect.RESTRICTION,
                decision=PolicyDecision.PAUSE,
                priority=100,
                reason_code="cognitive_result_blocked",
            ),
            PolicyRule(
                id="rule-cognitive-needs-user",
                policy_id="policy-cognitive-results",
                description="Require information when user input is needed",
                conditions=(
                    PolicyCondition(
                        field="action.parameters.requires_user_input",
                        operator=PolicyConditionOperator.EQUALS,
                        value=True,
                    ),
                ),
                effect=PolicyEffect.OBLIGATION,
                decision=PolicyDecision.REQUIRE_INFORMATION,
                priority=95,
                reason_code="cognitive_result_requires_user_input",
            ),
            PolicyRule(
                id="rule-cognitive-needs-resource",
                policy_id="policy-cognitive-results",
                description="Require information when an additional resource is needed",
                conditions=(
                    PolicyCondition(
                        field="action.parameters.requires_resource",
                        operator=PolicyConditionOperator.EQUALS,
                        value=True,
                    ),
                ),
                effect=PolicyEffect.OBLIGATION,
                decision=PolicyDecision.REQUIRE_INFORMATION,
                priority=90,
                reason_code="cognitive_result_requires_resource",
            ),
            PolicyRule(
                id="rule-cognitive-plan-ready",
                policy_id="policy-cognitive-results",
                description="Allow a safe planning recommendation",
                conditions=(
                    PolicyCondition(
                        field="action.name",
                        operator=PolicyConditionOperator.EQUALS,
                        value="plan",
                    ),
                    PolicyCondition(
                        field="action.parameters.blocked",
                        operator=PolicyConditionOperator.EQUALS,
                        value=False,
                    ),
                    PolicyCondition(
                        field="action.parameters.requires_user_input",
                        operator=PolicyConditionOperator.EQUALS,
                        value=False,
                    ),
                    PolicyCondition(
                        field="action.parameters.requires_resource",
                        operator=PolicyConditionOperator.EQUALS,
                        value=False,
                    ),
                ),
                effect=PolicyEffect.PERMIT,
                decision=PolicyDecision.ALLOW,
                priority=80,
                reason_code="cognitive_plan_recommendation_allowed",
            ),
        ),
    )
    policies.append(pol_cognitive)

    # Policy Sets
    ps_global = PolicySet(
        id="policyset-global-system",
        name="Global System Policy Set",
        description="Default global policy set containing security, permissions, sensitivity, plans, and info acquisition policies.",
        priority=100,
        scope=PolicyScope.GLOBAL,
        combining_algorithm=PolicyCombiningAlgorithm.DENY_OVERRIDES,
        policy_ids=tuple(p.id for p in policies),
        policies=tuple(policies),
    )
    policy_sets.append(ps_global)

    return policies, policy_sets


class PolicyEngine:
    """Main Policy Engine facade coordinating PolicyRepository, PolicyResolver, and PolicyEvaluator."""

    def __init__(
        self,
        repository: PolicyRepository | None = None,
        evaluator: PolicyEvaluator | None = None,
        fallback_mode: PolicyFailureMode = PolicyFailureMode.DENY,
        load_initial_policies: bool = True,
    ) -> None:
        self._repository = repository or PolicyRepository()
        self._evaluator = evaluator or DefaultPolicyEvaluator()
        self._fallback_mode = fallback_mode

        if load_initial_policies and not self._repository.list_policies(
            enabled_only=False
        ):
            initial_pols, initial_sets = build_initial_system_policies()
            for pol in initial_pols:
                self._repository.add_policy(pol)
            for pset in initial_sets:
                self._repository.add_policy_set(pset)

    @property
    def repository(self) -> PolicyRepository:
        return self._repository

    @property
    def evaluator(self) -> PolicyEvaluator:
        return self._evaluator

    @property
    def fallback_mode(self) -> PolicyFailureMode:
        return self._fallback_mode

    def register_policy(self, policy: Policy) -> Policy:
        """Register a policy in the repository."""
        return self._repository.add_policy(policy)

    def register_policy_set(self, policy_set: PolicySet) -> PolicySet:
        """Register a policy set in the repository."""
        return self._repository.add_policy_set(policy_set)

    def resolve_policies(
        self,
        policy_set_ids: Sequence[str] = (),
        scope: PolicyScope | str | None = None,
    ) -> tuple[list[Policy], list[PolicySet]]:
        """Resolve policy sets and policies in priority order according to scopes."""
        resolved_sets: list[PolicySet] = []
        set_ids_to_resolve = list(policy_set_ids)

        if not set_ids_to_resolve:
            # If no policy set specified, load active policy sets
            active_sets = self._repository.list_policy_sets(
                scope=scope, enabled_only=True
            )
            resolved_sets.extend(active_sets)
        else:
            for ps_id in set_ids_to_resolve:
                ps = self._repository.get_policy_set(ps_id)
                if ps is None:
                    raise PolicyResolutionError(
                        f"Required PolicySet '{ps_id}' not found."
                    )
                if ps.enabled:
                    resolved_sets.append(ps)

        # Collect policies from resolved sets
        policy_map: dict[tuple[str, int], Policy] = {}
        for pset in resolved_sets:
            # If policy_set has embedded policies
            for embedded_policy in pset.policies:
                if embedded_policy.enabled:
                    policy_map[(embedded_policy.id, embedded_policy.version)] = (
                        embedded_policy
                    )
            # Also resolve by policy_ids
            for policy_id in pset.policy_ids:
                referenced_policy = self._repository.get_policy(policy_id)
                if referenced_policy is not None and referenced_policy.enabled:
                    policy_map[(referenced_policy.id, referenced_policy.version)] = (
                        referenced_policy
                    )

        # Also load standalone policies matching scope if no policy set was explicitly specified
        if not set_ids_to_resolve:
            standalone = self._repository.list_policies(
                scope=scope, enabled_only=True, latest_only=True
            )
            for standalone_policy in standalone:
                policy_map[(standalone_policy.id, standalone_policy.version)] = (
                    standalone_policy
                )

        resolved_policies = list(policy_map.values())
        resolved_policies.sort(key=lambda p: (-p.priority, p.id, p.version))
        resolved_sets.sort(key=lambda ps: (-ps.priority, ps.id))

        return resolved_policies, resolved_sets

    def evaluate(self, request: PolicyEvaluationRequest) -> PolicyEvaluationResult:
        """Evaluate a PolicyEvaluationRequest deterministically."""
        policies, policy_sets = self.resolve_policies(
            policy_set_ids=request.policy_set_ids
        )
        return self._evaluator.evaluate(
            request=request,
            policies=policies,
            policy_sets=policy_sets,
            fallback_mode=self._fallback_mode,
        )
