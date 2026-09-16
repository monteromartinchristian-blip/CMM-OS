"""Phase 11.4 — ``cmm doctor``, the read-only canonical diagnostic aggregator.

Doctor answers one question — *what state is this platform in right now?* — by
aggregating evidence that canonical owners already publish.  It owns no
authority and no subsystem client: its only collaborator is the CLI application
adapter, so every real check is a projection of the canonical application
boundary, and a check whose owner does not exist in this build is reported
``UNAVAILABLE`` instead of as hollow success.

The frozen check set is declared once, in order, by
:data:`DOCTOR_CHECKS`:

``application.health`` / ``application.capabilities`` / ``services`` / ``kernel``
    backed by real canonical evidence;
``configuration`` / ``database`` / ``storage`` / ``models`` / ``permissions`` /
``migrations`` / ``secrets`` / ``network`` / ``plugins``
    reported ``UNAVAILABLE`` because no canonical owner exists in Phase 11.4.

Read-only is a hard rule, not a convention.  A run issues queries only (never a
session create, a message submit or a cancellation), reads no secret, resolves
no network address and mutates nothing: it does not repair, migrate, install,
rotate, restart or reconfigure anything.  A future explicit repair command would
need its own scope.

A doctor run fails closed when a **core** check fails: the result reports
``failed`` and the dispatcher maps it to the unhealthy-dependency exit code.  An
``UNAVAILABLE`` check is not a failure — an absent owner is a fact, not a defect.

See ``docs/reference/phase-11-cli.md``.
"""

from __future__ import annotations

import importlib.util
from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import Enum
from types import MappingProxyType
from typing import Any

from cmm.cli_application import CliApplicationAdapter
from cmm.cli_contracts import CliError, CliResult

__all__ = [
    "CORE_CHECK_IDS",
    "DOCTOR_CHECKS",
    "DOCTOR_FAILED_CODE",
    "CliDoctor",
    "DoctorCheck",
    "DoctorCheckSpec",
    "DoctorCheckStatus",
]

#: The stable public code of a doctor run that found a failing core check.
DOCTOR_FAILED_CODE = "DEPENDENCY_UNHEALTHY"

#: The public message of a doctor run that failed closed.  Presentation-owned.
DOCTOR_FAILED_MESSAGE = "Doctor reported failing canonical checks"

#: The public message of a check whose canonical owner does not exist yet.
UNAVAILABLE_CHECK_MESSAGE = "No canonical owner is available in this platform build"

#: The reason code carried by an unavailable check.
NO_OWNER_REASON = "NO_CANONICAL_OWNER"

#: The canonical kernel surface a local platform must be able to load.
KERNEL_MODULES: tuple[str, ...] = (
    "kernel",
    "kernel.end_to_end_runner",
    "kernel.llm.provider_registry",
)

#: The maximum length of the public check messages.
_MAX_MESSAGE_LENGTH = 512


class DoctorCheckStatus(str, Enum):
    """Closed set of stable diagnostic states of one doctor check."""

    PASS = "pass"
    WARN = "warn"
    FAIL = "fail"
    UNAVAILABLE = "unavailable"
    SKIPPED = "skipped"


def _bounded_text(value: object, field_name: str) -> str:
    if not isinstance(value, str):
        raise TypeError(f"{field_name} must be a string")
    if not value.strip():
        raise ValueError(f"{field_name} must be non-empty")
    if len(value) > _MAX_MESSAGE_LENGTH:
        raise ValueError(f"{field_name} must not exceed {_MAX_MESSAGE_LENGTH}")
    return value


def _freeze_details(value: object, field_name: str = "details") -> Mapping[str, Any]:
    """Freeze one check's details into an immutable mapping."""

    if not isinstance(value, Mapping):
        raise TypeError(f"{field_name} must be a mapping")
    frozen: dict[str, Any] = {}
    for key, item in value.items():
        if not isinstance(key, str):
            raise TypeError(f"{field_name} keys must be strings")
        frozen[key] = item
    return MappingProxyType(frozen)


@dataclass(frozen=True, slots=True)
class DoctorCheckSpec:
    """Immutable declaration of one doctor check.

    A declaration states the check identity, what it inspects and whether the
    platform requires it.  It inspects nothing on its own.
    """

    check_id: str
    description: str
    core: bool

    def __post_init__(self) -> None:
        object.__setattr__(self, "check_id", _bounded_text(self.check_id, "check_id"))
        object.__setattr__(
            self, "description", _bounded_text(self.description, "description")
        )
        if not isinstance(self.core, bool):
            raise TypeError("core must be a bool")


@dataclass(frozen=True, slots=True)
class DoctorCheck:
    """One diagnostic result of a single doctor run."""

    check_id: str
    status: DoctorCheckStatus
    message: str
    details: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "check_id", _bounded_text(self.check_id, "check_id"))
        if not isinstance(self.status, DoctorCheckStatus):
            raise TypeError("status must be a DoctorCheckStatus")
        object.__setattr__(self, "message", _bounded_text(self.message, "message"))
        object.__setattr__(self, "details", _freeze_details(self.details))

    def to_dict(self) -> dict[str, Any]:
        """Return the deterministic public representation of this check."""

        return {
            "check_id": self.check_id,
            "status": self.status.value,
            "message": self.message,
            "details": {
                key: list(value) if isinstance(value, tuple) else value
                for key, value in self.details.items()
            },
        }


#: The frozen, ordered doctor check declarations.  Module-level and immutable.
DOCTOR_CHECKS: tuple[DoctorCheckSpec, ...] = (
    DoctorCheckSpec(
        check_id="application.health",
        description="Canonical application readiness",
        core=True,
    ),
    DoctorCheckSpec(
        check_id="application.capabilities",
        description="Canonical declared capability state",
        core=True,
    ),
    DoctorCheckSpec(
        check_id="configuration",
        description="Configuration inspection",
        core=False,
    ),
    DoctorCheckSpec(
        check_id="database",
        description="Database connectivity",
        core=False,
    ),
    DoctorCheckSpec(
        check_id="storage",
        description="Storage availability",
        core=False,
    ),
    DoctorCheckSpec(
        check_id="models",
        description="Model availability",
        core=False,
    ),
    DoctorCheckSpec(
        check_id="services",
        description="Canonical service readiness",
        core=True,
    ),
    DoctorCheckSpec(
        check_id="permissions",
        description="Permission readiness",
        core=False,
    ),
    DoctorCheckSpec(
        check_id="migrations",
        description="Pending migrations",
        core=False,
    ),
    DoctorCheckSpec(
        check_id="secrets",
        description="Secret configuration presence",
        core=False,
    ),
    DoctorCheckSpec(
        check_id="network",
        description="Bounded network reachability",
        core=False,
    ),
    DoctorCheckSpec(
        check_id="plugins",
        description="Installed plugins",
        core=False,
    ),
    DoctorCheckSpec(
        check_id="kernel",
        description="Canonical kernel surface readiness",
        core=True,
    ),
)

#: The identities of the checks this platform requires.
CORE_CHECK_IDS: frozenset[str] = frozenset(
    spec.check_id for spec in DOCTOR_CHECKS if spec.core
)

#: Every declared check status, for the summary document.
_SUMMARY_STATUSES: tuple[DoctorCheckStatus, ...] = (
    DoctorCheckStatus.PASS,
    DoctorCheckStatus.WARN,
    DoctorCheckStatus.FAIL,
    DoctorCheckStatus.UNAVAILABLE,
    DoctorCheckStatus.SKIPPED,
)


class CliDoctor:
    """Read-only diagnostic aggregation over the canonical application boundary."""

    def __init__(self, application: CliApplicationAdapter) -> None:
        if not isinstance(application, CliApplicationAdapter):
            raise TypeError(
                "application must be the official CliApplicationAdapter, "
                f"not {type(application).__name__}"
            )
        self._application = application

    def run(self) -> CliResult:
        """Run every declared check once and aggregate the result."""

        status_result = self._application.status()
        checks = tuple(self._evaluate(spec, status_result) for spec in DOCTOR_CHECKS)
        failed = tuple(
            check.check_id for check in checks if check.status is DoctorCheckStatus.FAIL
        )
        core_failed = tuple(
            check_id for check_id in failed if check_id in CORE_CHECK_IDS
        )
        summary = {
            status.value: sum(1 for check in checks if check.status is status)
            for status in _SUMMARY_STATUSES
        }
        data = {
            "checks": [check.to_dict() for check in checks],
            "summary": summary,
            "failed": list(failed),
        }
        metadata = {
            "request_id": status_result.metadata.get("request_id"),
            "api_version": status_result.metadata.get("api_version"),
            "quiet_value": self._overall_status(core_failed, checks),
        }

        if core_failed:
            return CliResult(
                command="doctor",
                ok=False,
                status="failed",
                data=data,
                error=CliError(
                    code=DOCTOR_FAILED_CODE,
                    message=DOCTOR_FAILED_MESSAGE,
                    details={"failed": list(core_failed)},
                ),
                metadata=metadata,
            )

        return CliResult(
            command="doctor",
            ok=True,
            status=metadata["quiet_value"],
            data=data,
            metadata=metadata,
        )

    # ── Aggregation ──────────────────────────────────────────────────────────

    @staticmethod
    def _overall_status(
        core_failed: tuple[str, ...], checks: tuple[DoctorCheck, ...]
    ) -> str:
        if core_failed:
            return "failed"
        if any(check.status is DoctorCheckStatus.WARN for check in checks):
            return "degraded"
        return "ok"

    def _evaluate(
        self,
        spec: DoctorCheckSpec,
        status_result: CliResult,
    ) -> DoctorCheck:
        if spec.check_id == "kernel":
            return self._kernel_check(spec)
        if spec.check_id == "application.health":
            return self._health_check(spec, status_result)
        if spec.check_id == "application.capabilities":
            return self._capabilities_check(spec, status_result)
        if spec.check_id == "services":
            return self._services_check(spec, status_result)
        return DoctorCheck(
            check_id=spec.check_id,
            status=DoctorCheckStatus.UNAVAILABLE,
            message=UNAVAILABLE_CHECK_MESSAGE,
            details={"reason_code": NO_OWNER_REASON},
        )

    @staticmethod
    def _failure(spec: DoctorCheckSpec, status_result: CliResult) -> DoctorCheck:
        error_code = (
            status_result.error.code
            if status_result.error is not None
            else "INTERNAL_FAILURE"
        )
        return DoctorCheck(
            check_id=spec.check_id,
            status=DoctorCheckStatus.FAIL,
            message=f"{spec.description} could not be certified",
            details={"error_code": error_code},
        )

    def _health_check(
        self, spec: DoctorCheckSpec, status_result: CliResult
    ) -> DoctorCheck:
        if status_result.error is not None:
            return self._failure(spec, status_result)

        data = status_result.data
        ready = data.get("platform_ready") if isinstance(data, Mapping) else None
        if ready is not True:
            return DoctorCheck(
                check_id=spec.check_id,
                status=DoctorCheckStatus.FAIL,
                message="The canonical platform is not ready",
                details={"platform_ready": ready if isinstance(ready, bool) else False},
            )

        return DoctorCheck(
            check_id=spec.check_id,
            status=DoctorCheckStatus.PASS,
            message="The canonical platform reports ready",
            details={
                "platform_ready": True,
                "platform_state": str(data.get("platform_state", "")),
                "api_version": str(data.get("application_api_version", "")),
            },
        )

    def _capabilities_check(
        self, spec: DoctorCheckSpec, status_result: CliResult
    ) -> DoctorCheck:
        if status_result.error is not None:
            return self._failure(spec, status_result)

        capabilities = self._declared_capabilities(status_result)
        if capabilities is None or not capabilities:
            return DoctorCheck(
                check_id=spec.check_id,
                status=DoctorCheckStatus.FAIL,
                message="The canonical capability declaration is missing",
                details={"total": 0},
            )

        by_status: dict[str, int] = {}
        for capability in capabilities:
            key = str(capability.get("status", "unknown"))
            by_status[key] = by_status.get(key, 0) + 1

        return DoctorCheck(
            check_id=spec.check_id,
            status=DoctorCheckStatus.PASS,
            message="The canonical capability declaration was read",
            details={
                "total": len(capabilities),
                **{f"{key}": value for key, value in sorted(by_status.items())},
            },
        )

    def _services_check(
        self, spec: DoctorCheckSpec, status_result: CliResult
    ) -> DoctorCheck:
        if status_result.error is not None:
            return self._failure(spec, status_result)

        data = status_result.data
        services = data.get("services") if isinstance(data, Mapping) else None
        if not isinstance(services, list | tuple) or not services:
            return DoctorCheck(
                check_id=spec.check_id,
                status=DoctorCheckStatus.FAIL,
                message="The canonical service set could not be read",
                details={"count": 0},
            )

        return DoctorCheck(
            check_id=spec.check_id,
            status=DoctorCheckStatus.PASS,
            message="The canonical service set is ready",
            details={"count": len(services), "services": tuple(services)},
        )

    @staticmethod
    def _kernel_check(spec: DoctorCheckSpec) -> DoctorCheck:
        """Report whether the canonical kernel surface can be loaded.

        Only module resolution is inspected: nothing is executed, mutated or
        configured, and no version claim is invented when the kernel publishes
        none.
        """

        missing = tuple(
            module
            for module in KERNEL_MODULES
            if importlib.util.find_spec(module) is None
        )
        if missing:
            return DoctorCheck(
                check_id=spec.check_id,
                status=DoctorCheckStatus.FAIL,
                message="The canonical kernel surface is incomplete",
                details={"missing": missing},
            )

        return DoctorCheck(
            check_id=spec.check_id,
            status=DoctorCheckStatus.PASS,
            message="The canonical kernel surface is loadable",
            details={"modules": KERNEL_MODULES},
        )

    @staticmethod
    def _declared_capabilities(
        status_result: CliResult,
    ) -> list[Mapping[str, Any]] | None:
        data = status_result.data
        declared = data.get("capabilities") if isinstance(data, Mapping) else None
        if not isinstance(declared, list | tuple):
            return None
        return [entry for entry in declared if isinstance(entry, Mapping)]
