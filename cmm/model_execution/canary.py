"""CMMChat Wave E0 — the live real-model execution canary.

This is the E0 acceptance entry point.  One run proves the whole canonical path
against the *real* CMMChat Router:

```text
CMM OS canonical runtime (Phase 11.4 composition)
  → ConversationService → ApplicationGateway → RequestApplicationService
  → Orchestrator (canonical decision persisted)
  → CanonicalModelExecutor (this seam)
  → ModelRouter → ProviderFactory → OpenAICompatibleProvider
  → OpenAICompatibleClient → http://127.0.0.1:8790/v1
  → real model → normalized CMM OS result
```

Run it as a module::

    CMM_ROUTER_TOKEN=… python -m cmm.model_execution.canary \\
        --model chatgpt/chatgpt-web/medium

The bearer is read from the environment variable the canonical ``ProviderSpec``
names (``CMM_ROUTER_TOKEN``); it is never printed, logged or stored.  The
endpoint is the loopback router root; the model identity comes from ``--model``,
the canonical ``CMM_ROUTER_MODEL`` environment variable or the running router's
own ``/v1/models`` advertisement.

Every report line is a safe fact: no credential, no authorization header, no
provider payload and no raw exception text can be reported.  The exit code is
``0`` only for a real, complete inference.

See ``docs/reference/phase-11-model-execution-canary.md``.
"""

from __future__ import annotations

import argparse
import time
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from cmm.application.contracts import (
    APPLICATION_API_VERSION,
    ApplicationChannel,
    ApplicationCommand,
    ApplicationOperation,
    ApplicationStatus,
)
from cmm.application.local_runtime import build_local_application_runtime
from cmm.conversation.capabilities import ConversationCapabilityResolver
from cmm.conversation.projection import ConversationResponseProjector
from cmm.conversation.service import ConversationService
from cmm.conversation.state import SharedSessionConversationAdapter
from cmm.model_execution.composition import (
    CHAT_ONLY_ROUTER_BASE_URL,
    PROVIDER_REGISTRY_SERVICE_ID,
    LocalModelExecution,
    build_local_model_execution,
)
from cmm.model_execution.executor import CanonicalModelExecutor
from cmm.model_execution.turn import (
    ModelTurnRequest,
    ModelTurnResult,
    execute_conversational_turn,
)

__all__ = [
    "CANARY_FAILED",
    "CANARY_PASSED",
    "DEFAULT_CANARY_PROMPT",
    "CanaryReport",
    "main",
    "run_canary",
]

#: The suggested E0 canary prompt: literal compliance is helpful, real inference
#: is what the gate measures.
DEFAULT_CANARY_PROMPT = "Reply with exactly: CMM_OS_ROUTER_CANARY_OK"

CANARY_PASSED = "PASS"
CANARY_FAILED = "FAIL"

#: The reader-facing bound of a reported answer.  A longer answer is reported
#: truncated with an explicit marker; the execution result itself is never
#: truncated.
REPORT_TEXT_LIMIT = 600


def _utc_timestamp() -> str:
    """Return one ISO-8601 UTC timestamp with an explicit offset."""

    return datetime.now(timezone.utc).isoformat()


def _single_line(value: str, *, limit: int = REPORT_TEXT_LIMIT) -> str:
    """Return *value* as one safe, bounded report line."""

    collapsed = " ".join(value.split())
    if len(collapsed) > limit:
        return f"{collapsed[:limit]}…(truncated)"
    return collapsed


@dataclass(frozen=True, slots=True)
class CanaryReport:
    """The safe evidence of one E0 canary run."""

    requested_model: str | None
    resolved_model: str | None
    endpoint: str
    response_text: str | None
    elapsed_ms: int
    passed: bool
    accepted_request_id: str | None = None
    decision_id: str | None = None
    decision_route: str | None = None
    decision_intent: str | None = None
    routing_decision_id: str | None = None
    provider_id: str | None = None
    finish_reason: str | None = None
    total_tokens: int | None = None
    failure_code: str | None = None
    failure_message: str | None = None
    evidence: tuple[str, ...] = field(default=())

    def lines(self) -> tuple[str, ...]:
        """Return the required E0 evidence lines in a frozen order."""

        lines = [
            f"CANARY_REQUESTED_MODEL={self.requested_model or 'discovered'}",
            f"CANARY_RESOLVED_MODEL={self.resolved_model or 'unresolved'}",
            f"CANARY_ROUTER_ENDPOINT={self.endpoint}",
            f"CANARY_RESPONSE={_single_line(self.response_text) if self.response_text else ''}",
            f"CANARY_ELAPSED_MS={self.elapsed_ms}",
            f"CANARY_RESULT={'PASS' if self.passed else 'FAIL'}",
        ]
        if self.failure_code:
            lines.append(f"CANARY_FAILURE_CODE={self.failure_code}")
        if self.failure_message:
            lines.append(f"CANARY_FAILURE_MESSAGE={_single_line(self.failure_message)}")
        lines.extend(self.evidence)
        return tuple(lines)


def _evidence_lines(
    *,
    task: ModelTurnRequest | None,
    turn: ModelTurnResult | None,
    execution: LocalModelExecution,
    executor: CanonicalModelExecutor,
) -> tuple[str, ...]:
    """Return the safe path evidence of one run."""

    lines: list[str] = []
    if task is not None:
        lines.append(f"CMM_OS_ACCEPTED_REQUEST={task.request_id}")
    if task is not None:
        lines.append(f"CANONICAL_SESSION={task.session_id}")
    if turn is not None:
        lines.append(
            "ORCHESTRATOR_PATH_REACHED="
            f"{turn.decision.decision_id}|route={turn.decision.execution_route.value}"
            f"|intent={turn.decision.intent.value}"
        )
    lines.append(f"EXECUTION_SEAM_REACHED={type(executor).__name__}")
    if turn is not None and turn.execution.routing_decision_id:
        lines.append(
            "MODEL_ROUTER_SELECTION="
            f"{turn.execution.routing_decision_id}"
            f"|provider={turn.execution.provider_id or 'unresolved'}"
            f"|model={turn.execution.model_id or 'unresolved'}"
        )
    if turn is not None and turn.execution.provider_id:
        lines.append(
            "PROVIDER_MATERIALIZED="
            f"{turn.execution.provider_id}|model={turn.execution.model_id}"
        )
    lines.append(f"ROUTER_REQUEST_SENT={CHAT_ONLY_ROUTER_BASE_URL}")
    if turn is not None and turn.execution.is_successful:
        lines.append(
            "ROUTER_RESPONSE_RECEIVED="
            f"finish_reason={turn.execution.finish_reason}"
            f"|tokens={turn.execution.total_tokens}"
        )
        lines.append(
            "NORMALIZED_ASSISTANT_RESULT="
            f"succeeded|chars={len(turn.execution.text or '')}"
        )
    lines.append(
        f"COMPOSED_ROUTER_MODELS={','.join(model.id for model in execution.models)}"
    )
    return tuple(lines)


def _execute_canary(
    *,
    model_ids: tuple[str, ...] | None,
    prompt: str,
    client: Any | None,
) -> tuple[LocalModelExecution, ModelTurnRequest, ModelTurnResult]:
    """Compose the canonical path, run one turn and return its real artifacts."""

    runtime = build_local_application_runtime()
    provider_registry = runtime.container.get_service(PROVIDER_REGISTRY_SERVICE_ID)
    execution = build_local_model_execution(
        provider_registry=provider_registry, model_ids=model_ids, client=client
    )
    gateway = runtime.gateway
    conversation = ConversationService(
        gateway=gateway,
        state=SharedSessionConversationAdapter(runtime.session_store),
        capabilities=ConversationCapabilityResolver(),
        projector=ConversationResponseProjector(),
    )
    decisions = runtime.container.get_service("orchestration.decision_repository")

    session_id = f"wave-e0-canary-{uuid4()}"
    request_id = f"wave-e0-canary-request-{uuid4()}"
    revision = _create_canary_session(gateway, session_id=session_id)
    task = ModelTurnRequest(
        session_id=session_id,
        user_message_id=f"wave-e0-canary-user-{uuid4()}",
        content=prompt,
        user_created_at=_utc_timestamp(),
        request_id=request_id,
        expected_session_revision=revision,
        assistant_message_id=f"wave-e0-canary-assistant-{uuid4()}",
        assistant_created_at=_utc_timestamp(),
    )
    turn = execute_conversational_turn(
        conversation=conversation,
        decisions=decisions,
        executor=execution.executor,
        turn=task,
    )
    return execution, task, turn


def _safe_evidence(error: BaseException) -> tuple[str, ...]:
    """Return the safe identifiers a fail-closed defect may carry."""

    details = getattr(error, "details", None)
    if not isinstance(details, Mapping):
        return ()
    lines: list[str] = []
    session_id = details.get("session_id")
    request_id = details.get("request_id")
    if isinstance(session_id, str) and session_id:
        lines.append(f"CANONICAL_SESSION={session_id}")
    if isinstance(request_id, str) and request_id:
        lines.append(f"CMM_OS_ACCEPTED_REQUEST={request_id}")
    return tuple(lines)


def run_canary(
    *,
    model_ids: tuple[str, ...] | None = None,
    prompt: str = DEFAULT_CANARY_PROMPT,
    client: Any | None = None,
) -> CanaryReport:
    """Run one E0 canary turn against the composed canonical runtime.

    Nothing is faked: the canonical runtime, the canonical conversational
    service, the canonical orchestrator, the canonical decision repository, the
    canonical router/factory/provider stack and the canonical session store are
    all real.  ``client`` exists only so the canary's own self-tests can script
    the transport; the live run passes ``None`` and talks to the real router.

    The canary never raises: every defect — an unreachable router, a refused
    provider, a fail-closed internal condition — is reported as safe evidence
    with ``CANARY_RESULT=FAIL``.
    """

    started = time.perf_counter()
    try:
        execution, task, turn = _execute_canary(
            model_ids=model_ids, prompt=prompt, client=client
        )
    except Exception as error:  # noqa: BLE001 - the canary reports, never raises
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        code = getattr(error, "code", type(error).__name__)
        message = getattr(error, "message", None)
        return CanaryReport(
            requested_model=model_ids[0] if model_ids else None,
            resolved_model=None,
            endpoint=CHAT_ONLY_ROUTER_BASE_URL,
            response_text=None,
            elapsed_ms=elapsed_ms,
            passed=False,
            failure_code=str(code),
            failure_message=str(message) if message else type(error).__name__,
            evidence=_safe_evidence(error),
        )

    elapsed_ms = int((time.perf_counter() - started) * 1000)
    result = turn.execution
    return CanaryReport(
        requested_model=model_ids[0] if model_ids else None,
        resolved_model=result.model_id,
        endpoint=CHAT_ONLY_ROUTER_BASE_URL,
        response_text=result.text,
        elapsed_ms=elapsed_ms,
        passed=result.is_successful,
        accepted_request_id=task.request_id,
        decision_id=turn.decision.decision_id,
        decision_route=turn.decision.execution_route.value,
        decision_intent=turn.decision.intent.value,
        routing_decision_id=result.routing_decision_id,
        provider_id=result.provider_id,
        finish_reason=result.finish_reason,
        total_tokens=result.total_tokens,
        failure_code=None if result.error is None else result.error.code.value,
        failure_message=None if result.error is None else result.error.message,
        evidence=_evidence_lines(
            task=task, turn=turn, execution=execution, executor=execution.executor
        ),
    )


def _create_canary_session(gateway: Any, *, session_id: str) -> int:
    """Create one canonical session through the canonical gateway."""

    response = gateway.handle(
        ApplicationCommand(
            api_version=APPLICATION_API_VERSION,
            request_id=f"{session_id}-create",
            operation=ApplicationOperation.SESSION_CREATE,
            payload={"session_id": session_id},
            channel=ApplicationChannel.CONVERSATION,
        )
    )
    data = response.data
    if response.status is not ApplicationStatus.SUCCESS or not isinstance(
        data, Mapping
    ):
        raise RuntimeError("the canonical session could not be created")
    return int(data["revision"])


def _parse_args(argv: Sequence[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="cmm.model_execution.canary",
        description=(
            "Run one real model inference through the canonical CMM OS execution "
            "path and the CMMChat Router on 127.0.0.1:8790."
        ),
    )
    parser.add_argument(
        "--model",
        default=None,
        help=(
            "explicit router model identity (for example chatgpt/chatgpt-web/medium); "
            "when omitted, CMM_ROUTER_MODEL or the router's /v1/models is used"
        ),
    )
    parser.add_argument(
        "--prompt",
        default=DEFAULT_CANARY_PROMPT,
        help="the conversational text one real inference is asked to answer",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    """Run the canary and print its safe evidence; return the process status."""

    arguments = _parse_args(argv)
    model_ids = (arguments.model,) if arguments.model else None
    report = run_canary(model_ids=model_ids, prompt=arguments.prompt)
    for line in report.lines():
        print(line)
    return 0 if report.passed else 1


if __name__ == "__main__":  # pragma: no cover - module entry point
    raise SystemExit(main())
