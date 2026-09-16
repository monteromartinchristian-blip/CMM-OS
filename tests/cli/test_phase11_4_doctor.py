"""Phase 11.4 — ``cmm doctor`` as a read-only diagnostic aggregator.

Design Point: ``DP-104`` — Single-Front-Door Fail-Closed Operational CLI

Doctor aggregates canonical evidence and reports it.  It owns no authority and
no subsystem client: its only collaborator is the CLI application adapter, so
every real check is a projection of what the canonical application boundary
already reports, and every check whose owner does not exist is reported
``UNAVAILABLE`` rather than as hollow success.

These tests prove the frozen check set and ordering, that the real checks pass on
the canonical local runtime, that future checks stay honestly unavailable, that a
core failure is reported as a failure, and that a doctor run is read-only: it
issues queries only, opens no socket, reads no secret, and touches no file.
"""

from __future__ import annotations

import json
import socket
from dataclasses import FrozenInstanceError
from pathlib import Path
from typing import Any

import pytest

from cmm.application import ApplicationGateway
from cmm.application.local_runtime import build_local_application_runtime
from cmm.cli_application import CliApplicationAdapter
from cmm.cli_contracts import CliResult
from cmm.cli_doctor import (
    DOCTOR_CHECKS,
    CliDoctor,
    DoctorCheckSpec,
    DoctorCheckStatus,
)
from cmm.orchestration.contracts import OrchestrationRequest

#: The frozen doctor check ids, in the frozen order.
FROZEN_CHECK_IDS = (
    "application.health",
    "application.capabilities",
    "configuration",
    "database",
    "storage",
    "models",
    "services",
    "permissions",
    "migrations",
    "secrets",
    "network",
    "plugins",
    "kernel",
)

#: The checks Phase 11.4 backs with real canonical evidence.
REAL_CHECK_IDS = (
    "application.health",
    "application.capabilities",
    "services",
    "kernel",
)

#: The checks with no canonical owner in this build.
RESERVED_CHECK_IDS = tuple(
    check_id for check_id in FROZEN_CHECK_IDS if check_id not in REAL_CHECK_IDS
)

RAW_DEFECT_TEXT = "Traceback: internal defect at /private/tmp/secret AKIA-EXAMPLE"


class _RequestRecorder:
    """Records every public request one real gateway handles, and still runs it."""

    def __init__(self, gateway: ApplicationGateway) -> None:
        self.gateway = gateway
        self.requests: list[Any] = []

    def install(self, monkeypatch: pytest.MonkeyPatch) -> None:
        original = self.gateway.handle

        def recording(request: Any) -> Any:
            self.requests.append(request)
            return original(request)

        monkeypatch.setattr(self.gateway, "handle", recording)


def _doctor(
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[CliDoctor, CliApplicationAdapter, _RequestRecorder]:
    runtime = build_local_application_runtime()
    adapter = CliApplicationAdapter(runtime.gateway)
    recorder = _RequestRecorder(runtime.gateway)
    recorder.install(monkeypatch)
    return CliDoctor(adapter), adapter, recorder


def _checks(result: CliResult) -> dict[str, Any]:
    return {check["check_id"]: check for check in result.data["checks"]}


# ── Authority boundary ───────────────────────────────────────────────────────


def test_doctor_owns_only_the_adapter(monkeypatch: pytest.MonkeyPatch) -> None:
    doctor, adapter, _ = _doctor(monkeypatch)

    assert set(vars(doctor)) == {"_application"}
    assert vars(doctor)["_application"] is adapter


def test_doctor_rejects_anything_but_the_adapter() -> None:
    with pytest.raises(TypeError):
        CliDoctor(object())  # type: ignore[arg-type]


def test_doctor_check_metadata_is_a_static_immutable_tuple() -> None:
    assert isinstance(DOCTOR_CHECKS, tuple)
    assert all(isinstance(entry, DoctorCheckSpec) for entry in DOCTOR_CHECKS)
    assert [entry.check_id for entry in DOCTOR_CHECKS] == list(FROZEN_CHECK_IDS)
    with pytest.raises(FrozenInstanceError):
        DOCTOR_CHECKS[0].check_id = "changed"  # type: ignore[misc]


def test_doctor_check_status_vocabulary_is_frozen() -> None:
    assert {member.value for member in DoctorCheckStatus} == {
        "pass",
        "warn",
        "fail",
        "unavailable",
        "skipped",
    }


# ── The frozen check set ─────────────────────────────────────────────────────


def test_every_frozen_check_is_reported_in_order(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    doctor, _, _ = _doctor(monkeypatch)

    result = doctor.run()

    assert [check["check_id"] for check in result.data["checks"]] == list(
        FROZEN_CHECK_IDS
    )
    assert set(result.data) == {"checks", "summary", "failed"}
    assert set(result.to_dict()["data"]) == {"checks", "summary", "failed"}


def test_real_checks_report_real_canonical_evidence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    doctor, _, _ = _doctor(monkeypatch)

    checks = _checks(doctor.run())

    for check_id in REAL_CHECK_IDS:
        assert checks[check_id]["status"] == DoctorCheckStatus.PASS.value, check_id
        assert checks[check_id]["message"].strip()

    assert checks["application.health"]["details"]["platform_ready"] is True
    assert checks["application.capabilities"]["details"]["total"] > 0
    assert checks["services"]["details"]["count"] > 0
    assert "orchestration.orchestrator" in checks["services"]["details"]["services"]
    assert set(checks["kernel"]["details"]["modules"]) == {
        "kernel",
        "kernel.end_to_end_runner",
        "kernel.llm.provider_registry",
    }


def test_future_checks_are_honestly_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    doctor, _, _ = _doctor(monkeypatch)

    checks = _checks(doctor.run())

    for check_id in RESERVED_CHECK_IDS:
        assert checks[check_id]["status"] == DoctorCheckStatus.UNAVAILABLE.value
        assert checks[check_id]["message"].strip()
        assert checks[check_id]["details"] == {"reason_code": "NO_CANONICAL_OWNER"}


def test_doctor_reports_at_least_one_pass_and_one_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    doctor, _, _ = _doctor(monkeypatch)

    statuses = [check["status"] for check in doctor.run().data["checks"]]

    assert DoctorCheckStatus.PASS.value in statuses
    assert DoctorCheckStatus.UNAVAILABLE.value in statuses
    assert DoctorCheckStatus.FAIL.value not in statuses
    assert DoctorCheckStatus.SKIPPED.value not in statuses


def test_the_summary_counts_every_check(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    doctor, _, _ = _doctor(monkeypatch)

    data = doctor.run().to_dict()["data"]
    summary = data["summary"]

    assert set(summary) == {"pass", "warn", "fail", "unavailable", "skipped"}
    assert sum(summary.values()) == len(FROZEN_CHECK_IDS)
    assert summary["pass"] == len(REAL_CHECK_IDS)
    assert summary["unavailable"] == len(RESERVED_CHECK_IDS)
    assert summary["fail"] == 0
    assert data["failed"] == []


def test_a_healthy_run_reports_ok_and_a_safe_quiet_value(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    doctor, _, _ = _doctor(monkeypatch)

    result = doctor.run()

    assert result.ok is True
    assert result.status == "ok"
    assert result.error is None
    assert result.command == "doctor"
    assert set(result.to_dict()["metadata"]) == {
        "request_id",
        "api_version",
        "quiet_value",
    }
    assert result.metadata["quiet_value"] == "ok"


def test_doctor_is_deterministic_across_runs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    doctor, _, _ = _doctor(monkeypatch)

    first = doctor.run().to_dict()
    second = doctor.run().to_dict()

    first["metadata"] = second["metadata"] = {}
    assert first == second


# ── Failure semantics ────────────────────────────────────────────────────────


def test_a_core_application_failure_is_reported_as_a_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    doctor, _, _ = _doctor(monkeypatch)
    gateway = vars(vars(doctor)["_application"])["_gateway"]

    def _defective_health() -> Any:
        raise RuntimeError(RAW_DEFECT_TEXT)

    monkeypatch.setattr(vars(gateway)["_health"], "get_health", _defective_health)

    result = doctor.run()

    assert result.ok is False
    assert result.status == "failed"
    assert result.error is not None
    assert result.data["failed"]
    checks = _checks(result)
    assert checks["application.health"]["status"] == DoctorCheckStatus.FAIL.value
    assert checks["application.health"]["details"]["error_code"] == "INTERNAL_FAILURE"

    rendered = json.dumps(result.to_dict())
    assert RAW_DEFECT_TEXT not in rendered
    assert "Traceback" not in rendered
    assert "AKIA-EXAMPLE" not in rendered


def test_a_failed_run_does_not_claim_the_other_checks_passed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    doctor, _, _ = _doctor(monkeypatch)
    gateway = vars(vars(doctor)["_application"])["_gateway"]

    def _defective_health() -> Any:
        raise RuntimeError(RAW_DEFECT_TEXT)

    monkeypatch.setattr(vars(gateway)["_health"], "get_health", _defective_health)

    checks = _checks(doctor.run())

    # The dependent reads can not be certified once the boundary failed closed.
    assert checks["application.capabilities"]["status"] != DoctorCheckStatus.PASS.value
    assert checks["services"]["status"] != DoctorCheckStatus.PASS.value


# ── Read-only guarantees ─────────────────────────────────────────────────────


def test_doctor_issues_queries_only(monkeypatch: pytest.MonkeyPatch) -> None:
    doctor, _, recorder = _doctor(monkeypatch)

    doctor.run()

    assert recorder.requests
    for request in recorder.requests:
        assert request.operation.value in {
            "health.get",
            "capabilities.list",
            "sessions.get",
        }
    assert not [
        request
        for request in recorder.requests
        if request.operation.value
        in {"sessions.create", "messages.submit", "requests.cancel"}
    ]


def test_doctor_creates_no_session_and_submits_no_message(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runtime = build_local_application_runtime()
    adapter = CliApplicationAdapter(runtime.gateway)
    orchestration_requests: list[OrchestrationRequest] = []
    original = runtime.orchestrator.orchestrate

    def recording(request: OrchestrationRequest) -> Any:
        orchestration_requests.append(request)
        return original(request)

    monkeypatch.setattr(runtime.orchestrator, "orchestrate", recording)

    CliDoctor(adapter).run()

    assert orchestration_requests == []


def test_doctor_touches_no_file(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    doctor, _, _ = _doctor(monkeypatch)
    monkeypatch.chdir(tmp_path)
    before = sorted(path.name for path in tmp_path.iterdir())

    doctor.run()

    assert sorted(path.name for path in tmp_path.iterdir()) == before
    assert before == []


def test_doctor_opens_no_socket(monkeypatch: pytest.MonkeyPatch) -> None:
    doctor, _, _ = _doctor(monkeypatch)

    def _forbidden_socket(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError("doctor must not open a socket")

    monkeypatch.setattr(socket, "socket", _forbidden_socket)
    monkeypatch.setattr(socket, "create_connection", _forbidden_socket)

    result = doctor.run()

    assert result.status == "ok"


def test_doctor_reveals_no_secret_from_the_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    doctor, _, _ = _doctor(monkeypatch)
    monkeypatch.setenv("CMM_API_TOKEN", "AKIA-EXAMPLE-SECRET-KEY")
    monkeypatch.setenv("CMM_DB_PASSWORD", "hunter2-secret")

    rendered = json.dumps(doctor.run().to_dict())

    assert "AKIA-EXAMPLE-SECRET-KEY" not in rendered
    assert "hunter2-secret" not in rendered
    assert "AKIA" not in rendered


def test_doctor_result_is_structurally_renderable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    doctor, _, _ = _doctor(monkeypatch)

    document = doctor.run().to_dict()

    assert json.loads(json.dumps(document, sort_keys=True)) == document
    assert "\x1b" not in json.dumps(document)
