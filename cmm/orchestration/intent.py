"""Phase 11.2 — deterministic intent resolution.

Phase 11.2 introduces one global request ``IntentResolver``.  It classifies a
request into the frozen :class:`~cmm.orchestration.contracts.IntentKind` set
using structured evidence only:

* an explicit ``intent_hint``;
* explicit structured request fields;
* explicit target references;
* safe categorical request metadata.

The resolver is a pure, stateless function of the request.  It performs no I/O,
no network access, no inference call and no provider selection, and it is not
the historical ``cmm_agent.router.IntentRouter`` (which keeps its own narrow
scope and is not repurposed here).

Fail-closed rule: when the evidence cannot safely distinguish an intent — or a
hinted side-effecting intent has no structured shape to support it — the
resolver returns ``IntentKind.UNKNOWN`` with ``needs_clarification=True``.  It
never guesses a side-effecting classification.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Protocol, runtime_checkable

from cmm.orchestration.contracts import (
    IntentKind,
    IntentResolution,
    OrchestrationRequest,
)

__all__ = [
    "DeterministicIntentResolver",
    "IntentResolver",
]

SOURCE_HINT = "intent_hint"
SOURCE_STRUCTURE = "structured_input"
SOURCE_UNRESOLVED = "unresolved"

#: A hinted intent that implies a side effect is honoured only when its own
#: structured shape is present in the request input.
SHAPE_BOUND_INTENTS: frozenset[IntentKind] = frozenset(
    {
        IntentKind.APPROVAL_RESPONSE,
        IntentKind.CANCELLATION,
        IntentKind.CONTINUATION,
        IntentKind.CONFIGURATION_CHANGE,
        IntentKind.INFORMATION_UPDATE,
        IntentKind.WORKFLOW_REQUEST,
        IntentKind.GOAL,
        IntentKind.COMMAND,
    }
)

#: Frozen classification precedence: the most explicit control/side-effect
#: signals are evaluated first.
PRECEDENCE: tuple[IntentKind, ...] = (
    IntentKind.APPROVAL_RESPONSE,
    IntentKind.CANCELLATION,
    IntentKind.CONTINUATION,
    IntentKind.CONFIGURATION_CHANGE,
    IntentKind.INFORMATION_UPDATE,
    IntentKind.WORKFLOW_REQUEST,
    IntentKind.GOAL,
    IntentKind.COMMAND,
    IntentKind.QUESTION,
    IntentKind.REFLECTION,
    IntentKind.UNKNOWN,
)

_TEXT_FIELDS: dict[IntentKind, str] = {
    IntentKind.CANCELLATION: "cancel_target_id",
    IntentKind.CONTINUATION: "continuation_id",
    IntentKind.QUESTION: "question",
    IntentKind.REFLECTION: "reflection",
}

_MAPPING_FIELDS: dict[IntentKind, tuple[str, str]] = {
    IntentKind.CONFIGURATION_CHANGE: ("configuration_change", "path"),
    IntentKind.INFORMATION_UPDATE: ("information_update", "subject_ref"),
    IntentKind.WORKFLOW_REQUEST: ("workflow_request", "workflow_type"),
    IntentKind.GOAL: ("goal", "title"),
    IntentKind.COMMAND: ("command", "operation"),
}


def _text_signal(payload: Mapping[str, object], key: str) -> bool:
    value = payload.get(key)
    return isinstance(value, str) and bool(value.strip())


def _mapping_signal(
    payload: Mapping[str, object], container_key: str, required_key: str
) -> bool:
    container = payload.get(container_key)
    if not isinstance(container, Mapping):
        return False
    value = container.get(required_key)
    return isinstance(value, str) and bool(value.strip())


def _detects(payload: Mapping[str, object], intent: IntentKind) -> bool:
    """Return whether *payload* carries the frozen structural shape of *intent*."""

    if intent is IntentKind.APPROVAL_RESPONSE:
        return _text_signal(payload, "approval_id") and _text_signal(
            payload, "decision"
        )
    if intent in _TEXT_FIELDS:
        return _text_signal(payload, _TEXT_FIELDS[intent])
    if intent in _MAPPING_FIELDS:
        container_key, required_key = _MAPPING_FIELDS[intent]
        return _mapping_signal(payload, container_key, required_key)
    return False


def _detected_signals(payload: Mapping[str, object]) -> tuple[IntentKind, ...]:
    """Return every structurally detected intent, in frozen precedence order."""

    return tuple(intent for intent in PRECEDENCE if _detects(payload, intent))


@runtime_checkable
class IntentResolver(Protocol):
    """Global Phase 11.2 request intent classification boundary."""

    def resolve(self, request: OrchestrationRequest) -> IntentResolution: ...


class DeterministicIntentResolver:
    """Deterministic, fail-closed, side-effect-free intent classification."""

    def resolve(self, request: OrchestrationRequest) -> IntentResolution:
        """Classify *request* without any external model call."""

        if not isinstance(request, OrchestrationRequest):
            raise TypeError(
                f"request must be an OrchestrationRequest, got {type(request).__name__}"
            )

        payload = request.input
        detected = _detected_signals(payload)
        hint = request.intent_hint

        if hint is not None:
            if hint is IntentKind.UNKNOWN:
                return self._clarification(detected, "INTENT_HINT_UNKNOWN", SOURCE_HINT)
            if hint not in SHAPE_BOUND_INTENTS:
                return self._resolved(
                    hint, SOURCE_HINT, detected, "INTENT_HINT_APPLIED"
                )
            if hint in detected:
                return self._resolved(
                    hint, SOURCE_HINT, detected, "INTENT_HINT_APPLIED"
                )
            if detected:
                return self._resolved(
                    detected[0],
                    SOURCE_STRUCTURE,
                    detected,
                    "INTENT_HINT_SHAPE_MISSING",
                )
            return self._clarification(
                detected, "INTENT_HINT_SHAPE_MISSING", SOURCE_UNRESOLVED
            )

        if detected:
            return self._resolved(
                detected[0],
                SOURCE_STRUCTURE,
                detected,
                "INTENT_RESOLVED_FROM_STRUCTURE",
            )

        return self._clarification(
            detected, "INTENT_UNKNOWN_NEEDS_CLARIFICATION", SOURCE_UNRESOLVED
        )

    # ── Resolution builders ──────────────────────────────────────────────────

    @staticmethod
    def _reason_codes(
        detected: tuple[IntentKind, ...], primary: str
    ) -> tuple[str, ...]:
        codes = [primary]
        if len(detected) > 1:
            codes.append("INTENT_MULTIPLE_SIGNALS")
        return tuple(codes)

    def _resolved(
        self,
        intent: IntentKind,
        source_kind: str,
        detected: tuple[IntentKind, ...],
        primary: str,
    ) -> IntentResolution:
        return IntentResolution(
            intent=intent,
            needs_clarification=False,
            source_kind=source_kind,
            reason_codes=self._reason_codes(detected, primary),
        )

    def _clarification(
        self,
        detected: tuple[IntentKind, ...],
        primary: str,
        source_kind: str,
    ) -> IntentResolution:
        return IntentResolution(
            intent=IntentKind.UNKNOWN,
            needs_clarification=True,
            source_kind=source_kind,
            reason_codes=self._reason_codes(detected, primary),
        )
