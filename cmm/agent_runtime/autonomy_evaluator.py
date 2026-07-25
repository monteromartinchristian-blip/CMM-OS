"""Phase 9.9 – Autonomy Evaluator.

Defines the :class:`AutonomyEvaluator` protocol and the deterministic
:class:`DefaultAutonomyEvaluator` implementation.

The evaluator implements the deny-overrides combining rule explicitly
required by the Phase 9.9 specification::

    effective permission =
        autonomy permits
        AND policy permits
        AND permissions satisfied
        AND validations satisfied
        AND approvals satisfied

No logic uses ``OR`` to elevate authority. When any layer cannot
authorize, the operation is denied, paused, or flagged for approval
or validation according to the level semantics.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Protocol

from .autonomy_contracts import (
    AutonomyDecision,
    AutonomyEvaluationRequest,
    AutonomyEvaluationResult,
    coerce_autonomy_level,
    generate_autonomy_request_id,
    generate_autonomy_result_id,
)
from .autonomy_profiles import get_autonomy_profile
from .enums import AgentAutonomyLevel, AutonomyCapability

# ── Reason codes (machine-readable) ─────────────────────────────────────────


RC_LEVEL_NOT_ALLOW_EXECUTION = "autonomy.level_does_not_allow_execution"
RC_CAPABILITY_PROHIBITED = "autonomy.capability_prohibited"
RC_LEVEL_DENIES_EXECUTION = "autonomy.level_denies_execution"
RC_MUTATION_REQUIRES_ROLLBACK = "autonomy.mutation_requires_rollback"
RC_MUTATION_REQUIRES_VALIDATION = "autonomy.mutation_requires_validation"
RC_IRREVERSIBLE_REQUIRES_APPROVAL = "autonomy.irreversible_requires_approval"
RC_PROFILE_REQUIRES_APPROVAL = "autonomy.profile_requires_approval"
RC_DESTRUCTIVE_REQUIRES_APPROVAL = "autonomy.destructive_requires_approval"
RC_EXTERNAL_REQUIRES_APPROVAL = "autonomy.external_requires_approval"
RC_SENSITIVE_REQUIRES_APPROVAL = "autonomy.sensitive_requires_approval"
RC_SPEND_REQUIRES_APPROVAL = "autonomy.spend_requires_approval"
RC_PERMISSION_CHANGE_REQUIRES_APPROVAL = "autonomy.permission_change_requires_approval"
RC_POLICY_CHANGE_REQUIRES_APPROVAL = "autonomy.policy_change_requires_approval"
RC_LEVEL4_REQUIRES_POLICY = "autonomy.level4_requires_policy_decision"
RC_POLICY_DENY = "autonomy.policy_deny"
RC_POLICY_REQUIRE_APPROVAL = "autonomy.policy_require_approval"
RC_POLICY_REQUIRE_VALIDATION = "autonomy.policy_require_validation"
RC_INVALID_REQUEST = "autonomy.invalid_request"
RC_FAILSAFE = "autonomy.failsafe"
RC_LEVEL2_NOT_IRREVERSIBLE = "autonomy.level2_not_irreversible"


# Decision values come from .enums AutonomyDecision; keep these as
# string sentinels for use in metadata and reason codes.


# ── Protocol ───────────────────────────────────────────────────────────────


class AutonomyEvaluator(Protocol):
    """Evaluator interface for an autonomy request."""

    def evaluate(
        self,
        request: AutonomyEvaluationRequest,
    ) -> AutonomyEvaluationResult: ...


# ── Default implementation ──────────────────────────────────────────────────


class DefaultAutonomyEvaluator:
    """Deterministic autonomy evaluator following the canonical rules."""

    __slots__ = ()

    def evaluate(
        self,
        request: AutonomyEvaluationRequest,
    ) -> AutonomyEvaluationResult:
        """Evaluate ``request`` and return a deterministic result."""
        if not isinstance(request, AutonomyEvaluationRequest):
            return _failsafe(
                request_id=getattr(request, "id", None)
                or generate_autonomy_request_id(),
                level=0,
                reason_codes=(RC_INVALID_REQUEST,),
                warnings=("request is not an AutonomyEvaluationRequest",),
            )

        level = coerce_autonomy_level(request.autonomy_level)
        try:
            profile = get_autonomy_profile(level)
        except (KeyError, TypeError, ValueError) as exc:
            return _failsafe(
                request_id=request.id,
                level=level,
                reason_codes=(RC_INVALID_REQUEST,),
                warnings=(f"profile resolution failed: {exc}",),
            )

        capability = _as_capability(request.capability)

        reason_codes: list[str] = []
        warnings: list[str] = []

        # 1. Resolve profile
        # (already done)

        # 2. Profile-level deny for prohibited capabilities
        if profile.prohibits(capability):
            return _deny_result(
                request=request,
                level=level,
                reason_codes=(RC_CAPABILITY_PROHIBITED,),
                warnings=(
                    (
                        f"capability '{capability.value}' is prohibited at "
                        f"level {int(level)}"
                    ),
                ),
            )

        # 3. Structural constraints: levels 0 and 1 must never execute
        if int(level) <= 1 and capability in _EXECUTION_CAPABILITIES:
            return _deny_result(
                request=request,
                level=level,
                reason_codes=(RC_LEVEL_DENIES_EXECUTION,),
                warnings=(
                    (
                        f"execution capability '{capability.value}' cannot be "
                        f"used at level {int(level)}"
                    ),
                ),
            )

        # 4. Level 2 must not allow irreversible execution
        if int(level) == 2 and capability == AutonomyCapability.EXECUTE_IRREVERSIBLE:
            return _deny_result(
                request=request,
                level=level,
                reason_codes=(RC_LEVEL2_NOT_IRREVERSIBLE,),
                warnings=(
                    (
                        "irreversible execution is denied at level 2 "
                        "(reversible execution)"
                    ),
                ),
            )

        # 5. Closed capability classification.
        #
        # A capability must be explicitly allowed or explicitly marked as
        # requiring approval. Anything else is denied fail-safe.
        profile_requires_approval = profile.requires_approval_for(capability)

        if not profile.allows(capability) and not profile_requires_approval:
            return _deny_result(
                request=request,
                level=level,
                reason_codes=(RC_CAPABILITY_PROHIBITED, RC_FAILSAFE),
                warnings=(
                    (
                        f"capability '{capability.value}' is not declared for "
                        f"autonomy level {int(level)}; fail-safe: denied"
                    ),
                ),
            )

        # 6. Structural request flags
        approval_needed = profile_requires_approval
        validation_needed = False
        rollback_needed = False

        if profile_requires_approval:
            reason_codes.append(RC_PROFILE_REQUIRES_APPROVAL)

        if request.is_mutation and profile.requires_rollback_for_mutation:
            rollback_needed = True
            if not request.rollback_available:
                reason_codes.append(RC_MUTATION_REQUIRES_ROLLBACK)

        if int(level) == 2 and request.is_mutation and not request.is_reversible:
            return _deny_result(
                request=request,
                level=level,
                reason_codes=(RC_LEVEL2_NOT_IRREVERSIBLE,),
                warnings=("irreversible mutation cannot be executed at level 2",),
            )

        if int(level) >= 2 and request.is_mutation and not request.validation_passed:
            validation_needed = True
            reason_codes.append(RC_MUTATION_REQUIRES_VALIDATION)

        # 6. Supervised level requirements
        if int(level) >= 3:
            if request.is_destructive:
                approval_needed = True
                reason_codes.append(RC_DESTRUCTIVE_REQUIRES_APPROVAL)
            if request.is_external:
                approval_needed = True
                reason_codes.append(RC_EXTERNAL_REQUIRES_APPROVAL)
            if request.is_sensitive:
                approval_needed = True
                reason_codes.append(RC_SENSITIVE_REQUIRES_APPROVAL)
            if request.requires_spend:
                approval_needed = True
                reason_codes.append(RC_SPEND_REQUIRES_APPROVAL)
            if request.changes_permissions:
                approval_needed = True
                reason_codes.append(RC_PERMISSION_CHANGE_REQUIRES_APPROVAL)
            if request.changes_policy:
                approval_needed = True
                reason_codes.append(RC_POLICY_CHANGE_REQUIRES_APPROVAL)
            if capability == AutonomyCapability.EXECUTE_IRREVERSIBLE:
                approval_needed = True
                reason_codes.append(RC_IRREVERSIBLE_REQUIRES_APPROVAL)

        # 7. Level 4 high-impact handling: not auto-allowed; composition with
        #    policy will produce the final decision.
        if (
            int(level) == 4
            and capability in _HIGH_IMPACT_CAPABILITIES
            and request.policy_decision is None
        ):
            reason_codes.append(RC_LEVEL4_REQUIRES_POLICY)

        # 8. Compose with policy decision
        policy_decision = (request.policy_decision or "").strip().lower() or None

        if policy_decision is not None:
            if policy_decision == "deny":
                return _deny_result(
                    request=request,
                    level=level,
                    reason_codes=(RC_POLICY_DENY,),
                    warnings=("policy engine denied the operation",),
                )
            if policy_decision in ("require_approval", "require_approval_for"):
                approval_needed = True
                reason_codes.append(RC_POLICY_REQUIRE_APPROVAL)
            if policy_decision == "require_validation":
                validation_needed = True
                reason_codes.append(RC_POLICY_REQUIRE_VALIDATION)
            if policy_decision in ("pause",):
                return _pause_result(
                    request=request,
                    level=level,
                    reason_codes=(RC_FAILSAFE, "autonomy.policy_pause"),
                    warnings=("policy engine requested pause",),
                )
            if policy_decision in (
                "not_applicable",
                "indeterminate",
            ):
                warnings.append(
                    f"policy decision was '{policy_decision}'; treated as "
                    "non-authoritative for autonomy"
                )

        # Level 4 high-impact without any policy decision: fail-safe
        if (
            int(level) == 4
            and capability in _HIGH_IMPACT_CAPABILITIES
            and policy_decision is None
            and "deny" in policy_decision_default(level, capability, request)
        ):
            return _deny_result(
                request=request,
                level=level,
                reason_codes=(RC_LEVEL4_REQUIRES_POLICY, RC_FAILSAFE),
                warnings=(
                    (
                        "level 4 high-impact operation requires an explicit "
                        "policy decision; fail-safe: denied"
                    ),
                ),
            )

        # 9. Final composition
        if approval_needed and not request.approval_present:
            return AutonomyEvaluationResult(
                id=generate_autonomy_result_id(),
                request_id=request.id,
                level=level,
                decision=AutonomyDecision.REQUIRE_APPROVAL,
                allowed=False,
                requires_approval=True,
                requires_validation=validation_needed,
                requires_rollback=rollback_needed,
                denied=False,
                reason_codes=tuple(reason_codes),
                warnings=tuple(warnings),
                evaluated_at=_now_utc(),
            )

        if validation_needed and not request.validation_passed:
            return AutonomyEvaluationResult(
                id=generate_autonomy_result_id(),
                request_id=request.id,
                level=level,
                decision=AutonomyDecision.REQUIRE_VALIDATION,
                allowed=False,
                requires_approval=approval_needed,
                requires_validation=True,
                requires_rollback=rollback_needed,
                denied=False,
                reason_codes=tuple(reason_codes),
                warnings=tuple(warnings),
                evaluated_at=_now_utc(),
            )

        if rollback_needed and not request.rollback_available:
            return AutonomyEvaluationResult(
                id=generate_autonomy_result_id(),
                request_id=request.id,
                level=level,
                decision=AutonomyDecision.REQUIRE_ROLLBACK,
                allowed=False,
                requires_approval=approval_needed,
                requires_validation=validation_needed,
                requires_rollback=True,
                denied=False,
                reason_codes=tuple(reason_codes),
                warnings=tuple(warnings),
                evaluated_at=_now_utc(),
            )

        # Allow
        return AutonomyEvaluationResult(
            id=generate_autonomy_result_id(),
            request_id=request.id,
            level=level,
            decision=AutonomyDecision.ALLOW,
            allowed=True,
            requires_approval=False,
            requires_validation=False,
            requires_rollback=rollback_needed,
            denied=False,
            reason_codes=tuple(reason_codes),
            warnings=tuple(warnings),
            evaluated_at=_now_utc(),
        )


# ── Helpers ─────────────────────────────────────────────────────────────────


_EXECUTION_CAPABILITIES: frozenset[AutonomyCapability] = frozenset(
    {
        AutonomyCapability.EXECUTE_READ_ONLY,
        AutonomyCapability.EXECUTE_VALIDATION,
        AutonomyCapability.EXECUTE_REVERSIBLE,
        AutonomyCapability.EXECUTE_WORKFLOW,
        AutonomyCapability.EXECUTE_IRREVERSIBLE,
    }
)

_HIGH_IMPACT_CAPABILITIES: frozenset[AutonomyCapability] = frozenset(
    {
        AutonomyCapability.EXECUTE_IRREVERSIBLE,
        AutonomyCapability.PUBLISH,
        AutonomyCapability.COMMUNICATE_EXTERNAL,
        AutonomyCapability.SPEND_BUDGET,
        AutonomyCapability.MODIFY_PERMISSIONS,
        AutonomyCapability.MODIFY_POLICY,
    }
)


def _as_capability(value: object) -> AutonomyCapability:
    """Coerce ``value`` to :class:`AutonomyCapability` for evaluator use."""
    if isinstance(value, AutonomyCapability):
        return value
    if isinstance(value, str):
        return AutonomyCapability(value)
    raise ValueError(f"Unknown capability: {value!r}")


def _now_utc():
    """Return current UTC datetime."""
    from datetime import datetime, timezone

    return datetime.now(timezone.utc)


def _deny_result(
    *,
    request: AutonomyEvaluationRequest,
    level: AgentAutonomyLevel,
    reason_codes: Iterable[str],
    warnings: Iterable[str],
) -> AutonomyEvaluationResult:
    return AutonomyEvaluationResult(
        id=generate_autonomy_result_id(),
        request_id=request.id,
        level=level,
        decision=AutonomyDecision.DENY,
        allowed=False,
        requires_approval=False,
        requires_validation=False,
        requires_rollback=False,
        denied=True,
        reason_codes=tuple(reason_codes),
        warnings=tuple(warnings),
        evaluated_at=_now_utc(),
    )


def _pause_result(
    *,
    request: AutonomyEvaluationRequest,
    level: AgentAutonomyLevel,
    reason_codes: Iterable[str],
    warnings: Iterable[str],
) -> AutonomyEvaluationResult:
    return AutonomyEvaluationResult(
        id=generate_autonomy_result_id(),
        request_id=request.id,
        level=level,
        decision=AutonomyDecision.PAUSE,
        allowed=False,
        requires_approval=True,
        requires_validation=False,
        requires_rollback=False,
        denied=False,
        reason_codes=tuple(reason_codes),
        warnings=tuple(warnings),
        evaluated_at=_now_utc(),
    )


def _failsafe(
    *,
    request_id: str,
    level: int,
    reason_codes: Iterable[str],
    warnings: Iterable[str],
) -> AutonomyEvaluationResult:
    return AutonomyEvaluationResult(
        id=generate_autonomy_result_id(),
        request_id=request_id or generate_autonomy_request_id(),
        level=coerce_autonomy_level(level),
        decision=AutonomyDecision.DENY,
        allowed=False,
        requires_approval=False,
        requires_validation=False,
        requires_rollback=False,
        denied=True,
        reason_codes=tuple(reason_codes),
        warnings=tuple(warnings),
        evaluated_at=_now_utc(),
    )


def policy_decision_default(
    level: AgentAutonomyLevel,
    capability: AutonomyCapability,
    request: AutonomyEvaluationRequest,
) -> str:
    """Compute a textual default describing whether to fail-safe-deny.

    Used by the level-4 high-impact branch: when no policy decision is
    provided, the function returns the literal string ``"deny"`` to
    signal fail-safe behavior, otherwise ``""``. Pure function.
    """
    if (
        int(level) == 4
        and capability in _HIGH_IMPACT_CAPABILITIES
        and (request.is_destructive or request.is_external or request.changes_policy)
    ):
        return "deny"
    return ""


__all__ = [
    "RC_CAPABILITY_PROHIBITED",
    "RC_DESTRUCTIVE_REQUIRES_APPROVAL",
    "RC_EXTERNAL_REQUIRES_APPROVAL",
    "RC_FAILSAFE",
    "RC_INVALID_REQUEST",
    "RC_IRREVERSIBLE_REQUIRES_APPROVAL",
    "RC_LEVEL2_NOT_IRREVERSIBLE",
    "RC_LEVEL4_REQUIRES_POLICY",
    "RC_LEVEL_DENIES_EXECUTION",
    "RC_LEVEL_NOT_ALLOW_EXECUTION",
    "RC_MUTATION_REQUIRES_ROLLBACK",
    "RC_MUTATION_REQUIRES_VALIDATION",
    "RC_PERMISSION_CHANGE_REQUIRES_APPROVAL",
    "RC_POLICY_CHANGE_REQUIRES_APPROVAL",
    "RC_POLICY_DENY",
    "RC_POLICY_REQUIRE_APPROVAL",
    "RC_POLICY_REQUIRE_VALIDATION",
    "RC_PROFILE_REQUIRES_APPROVAL",
    "RC_SENSITIVE_REQUIRES_APPROVAL",
    "RC_SPEND_REQUIRES_APPROVAL",
    "AutonomyEvaluator",
    "DefaultAutonomyEvaluator",
]
