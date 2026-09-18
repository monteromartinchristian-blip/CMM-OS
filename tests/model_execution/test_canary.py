"""CMMChat Wave E0 — deterministic tests of the live canary entry point.

The canary's self-tests run the *real* canonical runtime end to end with a
scripted transport client, so they prove the same path the live run walks without
requiring live inference.  Two properties matter as much as the success path:

* every required E0 evidence line is reported, and the endpoint line is the
  documented loopback router root;
* a failed or unavailable path reports ``FAIL`` with a safe reason and never
  prints a credential, an authorization header or a provider payload.
"""

from __future__ import annotations

from typing import Any

import pytest

from cmm.model_execution import canary
from cmm.model_execution.canary import (
    DEFAULT_CANARY_PROMPT,
    CanaryReport,
    main,
    run_canary,
)

MODEL_ID = "chatgpt/chatgpt-web/medium"
CANNED_TEXT = "CMM_OS_ROUTER_CANARY_OK"


class _ScriptedClient:
    """The canonical factory's injected transport client, scripted per test."""

    def __init__(
        self, *, result: Any = None, error: BaseException | None = None
    ) -> None:
        self.calls: list[dict[str, Any]] = []
        self._result = result if result is not None else (CANNED_TEXT, 21, 8, "stop")
        self._error = error

    def generate(
        self,
        *,
        model: str,
        system: str | None,
        prompt: str,
        temperature: float = 0.0,
        max_tokens: int | None = None,
    ) -> Any:
        self.calls.append(
            {"model": model, "prompt": prompt, "temperature": temperature}
        )
        if self._error is not None:
            raise self._error
        return self._result


def _lines(report: CanaryReport) -> dict[str, str]:
    """Return the report lines keyed by their evidence name."""

    parsed: dict[str, str] = {}
    for line in report.lines():
        name, _, value = line.partition("=")
        parsed[name] = value
    return parsed


# ── The successful canary ────────────────────────────────────────────────────


def test_a_real_canonical_turn_reports_the_required_e0_evidence() -> None:
    report = run_canary(model_ids=(MODEL_ID,), client=_ScriptedClient())

    lines = _lines(report)

    assert report.passed is True
    assert lines["CANARY_REQUESTED_MODEL"] == MODEL_ID
    assert lines["CANARY_RESOLVED_MODEL"] == MODEL_ID
    assert lines["CANARY_ROUTER_ENDPOINT"] == "http://127.0.0.1:8790/v1"
    assert lines["CANARY_RESPONSE"] == CANNED_TEXT
    assert int(lines["CANARY_ELAPSED_MS"]) >= 0
    assert lines["CANARY_RESULT"] == "PASS"


def test_the_report_carries_the_safe_canonical_path_evidence() -> None:
    report = run_canary(model_ids=(MODEL_ID,), client=_ScriptedClient())

    lines = _lines(report)

    assert lines["CMM_OS_ACCEPTED_REQUEST"].startswith("wave-e0-canary-request-")
    assert lines["CANONICAL_SESSION"].startswith("wave-e0-canary-")
    assert lines["ORCHESTRATOR_PATH_REACHED"].startswith("orchestration-decision:")
    assert "route=direct_response" in lines["ORCHESTRATOR_PATH_REACHED"]
    assert "intent=question" in lines["ORCHESTRATOR_PATH_REACHED"]
    assert lines["EXECUTION_SEAM_REACHED"] == "CanonicalModelExecutor"
    assert lines["MODEL_ROUTER_SELECTION"].startswith("routing-")
    assert f"model={MODEL_ID}" in lines["MODEL_ROUTER_SELECTION"]
    assert lines["PROVIDER_MATERIALIZED"] == f"cmmchat-router|model={MODEL_ID}"
    assert lines["ROUTER_REQUEST_SENT"] == "http://127.0.0.1:8790/v1"
    assert lines["ROUTER_RESPONSE_RECEIVED"] == "finish_reason=stop|tokens=29"
    assert lines["NORMALIZED_ASSISTANT_RESULT"].startswith("succeeded|chars=")
    assert lines["COMPOSED_ROUTER_MODELS"] == MODEL_ID


def test_the_canary_asks_a_real_inference_with_the_documented_prompt() -> None:
    client = _ScriptedClient()

    run_canary(model_ids=(MODEL_ID,), client=client)

    assert client.calls == [
        {"model": MODEL_ID, "prompt": DEFAULT_CANARY_PROMPT, "temperature": 0.0}
    ]


# ── The failed canary ────────────────────────────────────────────────────────


def test_an_unavailable_router_reports_fail_without_leaking_a_secret(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("CMM_ROUTER_TOKEN", raising=False)

    report = run_canary(model_ids=(MODEL_ID,))

    lines = _lines(report)

    assert report.passed is False
    assert lines["CANARY_RESULT"] == "FAIL"
    assert lines["CANARY_RESPONSE"] == ""
    assert lines["CANARY_FAILURE_CODE"] == "PROVIDER_FAILURE"
    joined = "\n".join(report.lines())
    assert "authorization" not in joined.lower()
    assert "bearer " not in joined.lower()


def test_a_normalized_failure_is_reported_as_fail() -> None:
    from kernel.llm.exceptions import ProviderError

    report = run_canary(
        model_ids=(MODEL_ID,),
        client=_ScriptedClient(error=ProviderError("request failed: host unreachable")),
    )

    lines = _lines(report)

    assert report.passed is False
    assert lines["CANARY_RESULT"] == "FAIL"
    assert lines["CANARY_FAILURE_CODE"] == "PROVIDER_FAILURE"
    assert "host unreachable" not in "\n".join(report.lines()).lower()


def test_an_internal_fail_closed_defect_is_reported_as_fail(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _boom(**_: Any) -> Any:
        from cmm.model_execution.errors import ModelExecutionError

        raise ModelExecutionError("canonical session unavailable", code="TEST_DEFECT")

    monkeypatch.setattr(canary, "build_local_application_runtime", _boom)

    report = run_canary(model_ids=(MODEL_ID,))

    assert report.passed is False
    assert report.failure_code == "TEST_DEFECT"


# ── The module entry point ───────────────────────────────────────────────────


def test_the_module_entry_point_returns_a_non_zero_status_on_failure(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.delenv("CMM_ROUTER_TOKEN", raising=False)

    status = main(["--model", MODEL_ID])

    captured = capsys.readouterr().out
    assert status == 1
    assert "CANARY_RESULT=FAIL" in captured
    assert f"CANARY_REQUESTED_MODEL={MODEL_ID}" in captured


def test_the_module_entry_point_accepts_a_custom_prompt(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    recorded: dict[str, Any] = {}

    def _run(**kwargs: Any) -> CanaryReport:
        recorded.update(kwargs)
        return CanaryReport(
            requested_model=kwargs["model_ids"][0] if kwargs["model_ids"] else None,
            resolved_model=MODEL_ID,
            endpoint="http://127.0.0.1:8790/v1",
            response_text=CANNED_TEXT,
            elapsed_ms=12,
            passed=True,
        )

    monkeypatch.setattr(canary, "run_canary", _run)

    status = main(["--model", MODEL_ID, "--prompt", "say hi"])

    assert status == 0
    assert recorded == {"model_ids": (MODEL_ID,), "prompt": "say hi"}
    assert "CANARY_RESULT=PASS" in capsys.readouterr().out
