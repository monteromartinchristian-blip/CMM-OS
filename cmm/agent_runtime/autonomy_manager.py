"""Phase 9.9 – Autonomy Manager.

Governs the lifecycle of an :class:`AgentRun` ``autonomy_level`` during
execution. It implements explicit, auditable transitions between
levels with the following invariants:

* Reductions do not require approval.
* Escalations **must** carry ``authorized=True``; otherwise they are
  rejected with :class:`AutonomyEscalationNotAuthorizedError`.
* The new level cannot exceed the ``AgentDefinition``'s maximum
  (``0..4``).
* Invalid transitions raise :class:`AutonomyTransitionError`.
* Transitions never mutate the original :class:`AgentRun`; the manager
  produces a new contract and a transition record.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timezone
from typing import Any

from .autonomy_contracts import (
    AutonomyTransitionReason,
    AutonomyTransitionRecord,
    AutonomyTransitionRequest,
    AutonomyTransitionResult,
    coerce_autonomy_level,
    generate_autonomy_result_id,
    generate_autonomy_transition_id,
)
from .contracts import AgentRun
from .enums import AgentAutonomyLevel
from .errors import (
    AutonomyEscalationNotAuthorizedError,
    AutonomyTransitionError,
)


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


# ── Public API ──────────────────────────────────────────────────────────────


def apply_autonomy_transition(
    agent_run: AgentRun,
    request: AutonomyTransitionRequest,
) -> AutonomyTransitionResult:
    """Apply ``request`` to ``agent_run`` and return the transition result.

    This function does **not** mutate ``agent_run``; callers must
    construct the new run with the returned ``new_level``. The function
    is deterministic given the inputs.
    """
    if not isinstance(agent_run, AgentRun):
        raise AutonomyTransitionError(
            "apply_autonomy_transition requires an AgentRun instance"
        )
    if not isinstance(request, AutonomyTransitionRequest):
        raise AutonomyTransitionError(
            "apply_autonomy_transition requires an AutonomyTransitionRequest instance"
        )

    if request.agent_run_id != agent_run.id:
        raise AutonomyTransitionError(
            "transition request agent_run_id does not match the supplied AgentRun"
        )

    current = coerce_autonomy_level(agent_run.autonomy_level)
    target = coerce_autonomy_level(request.target_level)
    max_level = coerce_autonomy_level(request.agent_definition_max_level)

    # Run-level current is the source of truth.
    if int(request.current_level) != int(current):
        raise AutonomyTransitionError(
            f"transition request current_level {int(request.current_level)} "
            f"does not match the actual AgentRun level {int(current)}"
        )

    # Range checks (defensive; coerce already validates 0..4)
    if int(max_level) < 0 or int(max_level) > 4:
        raise AutonomyTransitionError(
            f"agent_definition_max_level must be in [0, 4], got {int(max_level)}"
        )

    if int(target) > int(max_level):
        raise AutonomyTransitionError(
            f"target level {int(target)} exceeds the AgentDefinition "
            f"maximum {int(max_level)}"
        )

    if int(target) > int(current) and not request.authorized:
        raise AutonomyEscalationNotAuthorizedError(
            f"escalation from level {int(current)} to {int(target)} "
            "requires authorized=True"
        )

    reason_codes: list[str] = []
    message = ""

    if int(target) == int(current):
        # No-op: still produce a successful record for auditability.
        reason_codes.append("autonomy.transition_noop")
        message = "autonomy level unchanged"
        new_level = current
    elif int(target) < int(current):
        # Reduction: always allowed, no authorization required.
        reason_codes.append("autonomy.transition_reduction")
        message = f"autonomy level reduced from {int(current)} to {int(target)}"
        new_level = target
    else:
        reason_codes.append("autonomy.transition_escalation")
        message = (
            f"autonomy level escalated from {int(current)} to "
            f"{int(target)} by authorized actor"
        )
        new_level = target

    result = AutonomyTransitionResult(
        id=generate_autonomy_result_id(),
        request_id=request.id,
        agent_run_id=agent_run.id,
        success=True,
        previous_level=current,
        new_level=new_level,
        authorized=bool(request.authorized) or int(target) <= int(current),
        reason_codes=tuple(reason_codes),
        message=message,
        decided_at=_now_utc(),
    )

    return result


def build_transition_record(
    result: AutonomyTransitionResult,
    *,
    actor_id: str | None = None,
    reason: AutonomyTransitionReason | str = AutonomyTransitionReason.MANUAL_REDUCTION,
    message: str = "",
) -> AutonomyTransitionRecord:
    """Build an :class:`AutonomyTransitionRecord` from a result."""
    if not isinstance(result, AutonomyTransitionResult):
        raise AutonomyTransitionError(
            "build_transition_record requires an AutonomyTransitionResult"
        )
    return AutonomyTransitionRecord(
        id=generate_autonomy_transition_id(),
        agent_run_id=result.agent_run_id,
        previous_level=result.previous_level,
        new_level=result.new_level,
        authorized=result.authorized,
        actor_id=actor_id,
        reason=reason,
        message=message or result.message,
        occurred_at=result.decided_at,
    )


def build_transition_request(
    *,
    agent_run: AgentRun,
    target_level: AgentAutonomyLevel | int,
    agent_definition_max_level: AgentAutonomyLevel | int,
    authorized: bool = False,
    actor_id: str | None = None,
    reason: AutonomyTransitionReason | str = AutonomyTransitionReason.MANUAL_REDUCTION,
    message: str = "",
    metadata: Mapping[str, Any] | None = None,
) -> AutonomyTransitionRequest:
    """Build a fully populated :class:`AutonomyTransitionRequest`.

    The current level is taken from the supplied :class:`AgentRun`.
    """
    if not isinstance(agent_run, AgentRun):
        raise AutonomyTransitionError("build_transition_request requires an AgentRun")
    return AutonomyTransitionRequest(
        id=generate_autonomy_transition_id(),
        agent_run_id=agent_run.id,
        current_level=agent_run.autonomy_level,
        target_level=target_level,
        agent_definition_max_level=agent_definition_max_level,
        authorized=authorized,
        actor_id=actor_id,
        reason=reason,
        message=message,
        metadata=metadata or {},
    )


def derive_new_agent_run(
    agent_run: AgentRun,
    new_level: AgentAutonomyLevel | int,
) -> AgentRun:
    """Return a new :class:`AgentRun` with ``autonomy_level`` set to ``new_level``.

    The original run is never mutated; the caller's
    ``replace(dataclass)`` semantics produce a fresh contract.
    """
    if not isinstance(agent_run, AgentRun):
        raise AutonomyTransitionError("derive_new_agent_run requires an AgentRun")
    coerced = coerce_autonomy_level(new_level)
    # AgentRun is frozen=True; use object.__setattr__ through dataclasses.replace
    # to keep this single-purpose helper free of the AgentRun internals.
    from dataclasses import replace

    return replace(
        agent_run,
        autonomy_level=coerced,
        updated_at=_now_utc(),
    )


__all__ = [
    "apply_autonomy_transition",
    "build_transition_record",
    "build_transition_request",
    "derive_new_agent_run",
]
