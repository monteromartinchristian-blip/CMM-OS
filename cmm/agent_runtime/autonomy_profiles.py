"""Phase 9.9 – Autonomy Profiles.

Canonical, deterministic, infrastructure-independent autonomy profiles
for the five supported levels.

These profiles are derived purely from the level and never consult
external state. The matrix is intentionally explicit; the explicit
permission/approval/prohibition split makes the level semantics
auditable and supports strict ``deny-overrides`` composition.
"""

from __future__ import annotations

from .autonomy_contracts import AutonomyProfile
from .enums import AgentAutonomyLevel, AutonomyCapability

# ── Helpers ─────────────────────────────────────────────────────────────────


_OBSERVE_AND_REASON: tuple[AutonomyCapability, ...] = (
    AutonomyCapability.OBSERVE,
    AutonomyCapability.LOAD_KNOWLEDGE,
    AutonomyCapability.REASON,
    AutonomyCapability.RECOMMEND,
    AutonomyCapability.REQUEST_APPROVAL,
)

_PROPOSE_EXTRA: tuple[AutonomyCapability, ...] = (
    AutonomyCapability.PROPOSE_PLAN,
    AutonomyCapability.PROPOSE_OPERATION,
)

_REVERSIBLE_EXEC_EXTRA: tuple[AutonomyCapability, ...] = (
    AutonomyCapability.EXECUTE_READ_ONLY,
    AutonomyCapability.EXECUTE_VALIDATION,
    AutonomyCapability.EXECUTE_REVERSIBLE,
)

_SUPERVISED_EXEC_EXTRA: tuple[AutonomyCapability, ...] = (
    AutonomyCapability.EXECUTE_WORKFLOW,
    # High-impact capabilities are *not* allowed by the profile; they
    # are only reachable through explicit approval at this level, which
    # the autonomy manager handles via transitions.
    AutonomyCapability.PUBLISH,
    AutonomyCapability.COMMUNICATE_EXTERNAL,
    AutonomyCapability.SPEND_BUDGET,
    AutonomyCapability.MODIFY_PERMISSIONS,
    AutonomyCapability.MODIFY_POLICY,
    AutonomyCapability.EXECUTE_IRREVERSIBLE,
)

_NEVER_AT_BASE_LEVEL: tuple[AutonomyCapability, ...] = (
    AutonomyCapability.EXECUTE_IRREVERSIBLE,
    AutonomyCapability.PUBLISH,
    AutonomyCapability.COMMUNICATE_EXTERNAL,
    AutonomyCapability.MODIFY_PERMISSIONS,
    AutonomyCapability.MODIFY_POLICY,
    AutonomyCapability.SPEND_BUDGET,
)


def _build_profile(
    level: AgentAutonomyLevel,
    *,
    name: str,
    description: str,
    allowed: tuple[AutonomyCapability, ...],
    requires_approval: tuple[AutonomyCapability, ...] = (),
    prohibited: tuple[AutonomyCapability, ...] = (),
    allow_execution: bool = False,
    requires_rollback_for_mutation: bool = False,
    requires_supervision: bool = False,
) -> AutonomyProfile:
    """Internal helper to build a profile with consistent defaults."""
    return AutonomyProfile(
        level=level,
        name=name,
        description=description,
        allowed=allowed,
        requires_approval=requires_approval,
        prohibited=prohibited,
        allow_execution=allow_execution,
        requires_rollback_for_mutation=requires_rollback_for_mutation,
        requires_supervision=requires_supervision,
    )


# ── Canonical profiles ──────────────────────────────────────────────────────


def _level0_profile() -> AutonomyProfile:
    """Level 0 — Analyze Only.

    Pure observation and reasoning. No side effects. May still detect
    gaps and recommend decisions or plans.
    """
    return _build_profile(
        AgentAutonomyLevel.ANALYZE_ONLY,
        name="Analyze Only",
        description=(
            "Observe, load knowledge, reason, and produce recommendations. "
            "No execution and no external side effects of any kind."
        ),
        allowed=(
            AutonomyCapability.OBSERVE,
            AutonomyCapability.LOAD_KNOWLEDGE,
            AutonomyCapability.REASON,
            AutonomyCapability.RECOMMEND,
            AutonomyCapability.PROPOSE_PLAN,
            AutonomyCapability.REQUEST_APPROVAL,
        ),
        allow_execution=False,
        requires_rollback_for_mutation=False,
        requires_supervision=False,
    )


def _level1_profile() -> AutonomyProfile:
    """Level 1 — Propose Actions.

    Includes everything from level 0. Additionally proposes concrete
    operations and prepares approval requests. Never executes.
    """
    return _build_profile(
        AgentAutonomyLevel.PROPOSE_ACTIONS,
        name="Propose Actions",
        description=(
            "Includes level 0 capabilities plus explicit proposal of "
            "operations and plans. May prepare approval requests but "
            "must not execute any operation with side effects."
        ),
        allowed=(
            AutonomyCapability.OBSERVE,
            AutonomyCapability.LOAD_KNOWLEDGE,
            AutonomyCapability.REASON,
            AutonomyCapability.RECOMMEND,
            AutonomyCapability.PROPOSE_PLAN,
            AutonomyCapability.PROPOSE_OPERATION,
            AutonomyCapability.REQUEST_APPROVAL,
        ),
        prohibited=(
            AutonomyCapability.EXECUTE_READ_ONLY,
            AutonomyCapability.EXECUTE_VALIDATION,
            AutonomyCapability.EXECUTE_REVERSIBLE,
            AutonomyCapability.EXECUTE_WORKFLOW,
            AutonomyCapability.EXECUTE_IRREVERSIBLE,
            AutonomyCapability.PUBLISH,
            AutonomyCapability.COMMUNICATE_EXTERNAL,
            AutonomyCapability.SPEND_BUDGET,
            AutonomyCapability.MODIFY_PERMISSIONS,
            AutonomyCapability.MODIFY_POLICY,
        ),
        allow_execution=False,
        requires_rollback_for_mutation=False,
        requires_supervision=False,
    )


def _level2_profile() -> AutonomyProfile:
    """Level 2 — Reversible Execution.

    May execute read-only operations, validations, and reversible
    mutations under checkpoint/rollback. Anything irreversible is
    structurally denied at the profile layer.
    """
    return _build_profile(
        AgentAutonomyLevel.REVERSIBLE_EXECUTION,
        name="Reversible Execution",
        description=(
            "Includes level 1 capabilities plus execution of read-only, "
            "validation, and reversible operations under explicit "
            "checkpoint and rollback. Irreversible and external "
            "operations are denied at the profile layer."
        ),
        allowed=(
            AutonomyCapability.OBSERVE,
            AutonomyCapability.LOAD_KNOWLEDGE,
            AutonomyCapability.REASON,
            AutonomyCapability.RECOMMEND,
            AutonomyCapability.PROPOSE_PLAN,
            AutonomyCapability.PROPOSE_OPERATION,
            AutonomyCapability.REQUEST_APPROVAL,
            AutonomyCapability.EXECUTE_READ_ONLY,
            AutonomyCapability.EXECUTE_VALIDATION,
            AutonomyCapability.EXECUTE_REVERSIBLE,
        ),
        prohibited=(
            AutonomyCapability.EXECUTE_IRREVERSIBLE,
            AutonomyCapability.PUBLISH,
            AutonomyCapability.COMMUNICATE_EXTERNAL,
            AutonomyCapability.SPEND_BUDGET,
            AutonomyCapability.MODIFY_PERMISSIONS,
            AutonomyCapability.MODIFY_POLICY,
            AutonomyCapability.EXECUTE_WORKFLOW,
        ),
        allow_execution=True,
        requires_rollback_for_mutation=True,
        requires_supervision=False,
    )


def _level3_profile() -> AutonomyProfile:
    """Level 3 — Supervised Autonomy.

    May execute full workflows under supervision. Operations that are
    destructive, irreversible, external, sensitive, costly, or that
    change permissions or policy require explicit human approval.
    """
    return _build_profile(
        AgentAutonomyLevel.SUPERVISED_AUTONOMY,
        name="Supervised Autonomy",
        description=(
            "Includes level 2 capabilities plus execution of complete "
            "workflows under supervision. Destructive, irreversible, "
            "external, sensitive, costly operations, and any change to "
            "permissions or policy require explicit human approval."
        ),
        allowed=(
            AutonomyCapability.OBSERVE,
            AutonomyCapability.LOAD_KNOWLEDGE,
            AutonomyCapability.REASON,
            AutonomyCapability.RECOMMEND,
            AutonomyCapability.PROPOSE_PLAN,
            AutonomyCapability.PROPOSE_OPERATION,
            AutonomyCapability.REQUEST_APPROVAL,
            AutonomyCapability.EXECUTE_READ_ONLY,
            AutonomyCapability.EXECUTE_VALIDATION,
            AutonomyCapability.EXECUTE_REVERSIBLE,
            AutonomyCapability.EXECUTE_WORKFLOW,
        ),
        requires_approval=(
            AutonomyCapability.EXECUTE_IRREVERSIBLE,
            AutonomyCapability.PUBLISH,
            AutonomyCapability.COMMUNICATE_EXTERNAL,
            AutonomyCapability.SPEND_BUDGET,
            AutonomyCapability.MODIFY_PERMISSIONS,
            AutonomyCapability.MODIFY_POLICY,
        ),
        allow_execution=True,
        requires_rollback_for_mutation=True,
        requires_supervision=True,
    )


def _level4_profile() -> AutonomyProfile:
    """Level 4 — Policy-Bounded Autonomy.

    May operate autonomously within explicit, authorized limits
    (scope, resources, budget, time, permissions, policies,
    validations, recovery, risk). Policy Engine, permissions,
    prohibitions and safety limits remain binding. High-impact
    capabilities still require Policy Engine authorization but are
    not auto-denied at the profile layer; the autonomy evaluator
    composes them with policy outcomes.
    """
    return _build_profile(
        AgentAutonomyLevel.POLICY_BOUNDED_AUTONOMY,
        name="Policy-Bounded Autonomy",
        description=(
            "Autonomous operation inside explicit, authorized limits: "
            "scope, resources, budget, time, permissions, policies, "
            "validations, recovery and risk. Policy Engine remains a "
            "binding constraint. May execute irreversible, external, "
            "sensitive, budget-impacting and policy-changing operations "
            "only when policy, permissions, approvals and validations "
            "all authorize them."
        ),
        allowed=(
            AutonomyCapability.OBSERVE,
            AutonomyCapability.LOAD_KNOWLEDGE,
            AutonomyCapability.REASON,
            AutonomyCapability.RECOMMEND,
            AutonomyCapability.PROPOSE_PLAN,
            AutonomyCapability.PROPOSE_OPERATION,
            AutonomyCapability.REQUEST_APPROVAL,
            AutonomyCapability.EXECUTE_READ_ONLY,
            AutonomyCapability.EXECUTE_VALIDATION,
            AutonomyCapability.EXECUTE_REVERSIBLE,
            AutonomyCapability.EXECUTE_WORKFLOW,
            AutonomyCapability.EXECUTE_IRREVERSIBLE,
            AutonomyCapability.PUBLISH,
            AutonomyCapability.COMMUNICATE_EXTERNAL,
            AutonomyCapability.SPEND_BUDGET,
            AutonomyCapability.MODIFY_PERMISSIONS,
            AutonomyCapability.MODIFY_POLICY,
        ),
        allow_execution=True,
        requires_rollback_for_mutation=True,
        requires_supervision=True,
    )


# ── Public registry ─────────────────────────────────────────────────────────


_CANONICAL_PROFILES: dict[AgentAutonomyLevel, AutonomyProfile] = {
    AgentAutonomyLevel.ANALYZE_ONLY: _level0_profile(),
    AgentAutonomyLevel.PROPOSE_ACTIONS: _level1_profile(),
    AgentAutonomyLevel.REVERSIBLE_EXECUTION: _level2_profile(),
    AgentAutonomyLevel.SUPERVISED_AUTONOMY: _level3_profile(),
    AgentAutonomyLevel.POLICY_BOUNDED_AUTONOMY: _level4_profile(),
}


def get_autonomy_profile(
    level: AgentAutonomyLevel | int,
) -> AutonomyProfile:
    """Return the canonical :class:`AutonomyProfile` for ``level``.

    Profiles are static, deterministic and never mutate. The result is
    reused across calls.
    """
    from .autonomy_contracts import coerce_autonomy_level

    lvl = coerce_autonomy_level(level)
    profile = _CANONICAL_PROFILES.get(lvl)
    if profile is None:  # pragma: no cover - guarded by coerce
        raise ValueError(f"No canonical profile for level {lvl!r}")
    return profile


def list_canonical_levels() -> tuple[AgentAutonomyLevel, ...]:
    """Return the ordered tuple of canonical autonomy levels."""
    return tuple(_CANONICAL_PROFILES.keys())


__all__ = [
    "get_autonomy_profile",
    "list_canonical_levels",
]
