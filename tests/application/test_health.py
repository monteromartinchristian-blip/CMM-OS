"""Phase 11.3 — health application service tests.

``HealthApplicationService`` projects the readiness of the application
composition.  It owns no health state: it reads the Phase 11.1
``ApplicationContainer`` state and projects only the allowlisted service IDs of
the ready composition snapshot.

These tests lock four boundaries:

- the constructor accepts a real ``ApplicationContainer`` only, so a
  structurally similar impostor can never claim the projection;
- a ready container reports safe readiness and its allowlisted service IDs;
- a container that is not ready reports ``degraded`` without leaking the raw
  container failure;
- no service is ever resolved per request: ``get_health()`` uses
  ``container.state`` and ``container.snapshot()`` only.

See ``docs/superpowers/specs/2026-09-16-phase-11.3-application-backend-design.md``.
"""

from __future__ import annotations

import json

import pytest

from cmm.application.contracts import APPLICATION_API_VERSION, ApplicationHealth
from cmm.application.health import HealthApplicationService
from cmm.platform.configuration import CompositionConfiguration
from cmm.platform.container import ApplicationContainer
from cmm.platform.contracts import (
    ContainerState,
    ContractMetadata,
    ErrorResult,
    ServiceBinding,
    ServiceDescriptor,
)
from cmm.platform.modules import StaticCompositionModule

MODULE_ID = "test-doubles"

SERVICE_IDS = ("application.gateway", "orchestration.orchestrator")

#: A raw composition failure that must never reach the public health value.
RAW_CONTAINER_FAILURE = "composition exploded at /private/tmp/cmm-internal-path"


class _Service:
    """One harmless stand-in implementation for a composition binding."""


def _binding(service_id: str) -> ServiceBinding:
    return ServiceBinding(
        descriptor=ServiceDescriptor(
            service_id=service_id,
            contract=ContractMetadata(
                contract_name=service_id,
                contract_version="1.0.0",
                schema_version="1",
                owner="cmm.test.doubles",
            ),
            implementation_id=f"tests.application.test_health.{service_id}",
        ),
        implementation=_Service(),
    )


def _ready_container(*service_ids: str) -> ApplicationContainer:
    module = StaticCompositionModule(
        MODULE_ID, tuple(_binding(service_id) for service_id in service_ids)
    )
    return ApplicationContainer.build(
        CompositionConfiguration(
            required_services=tuple(service_ids),
            enabled_modules=(MODULE_ID,),
        ),
        modules=(module,),
    )


def _failed_container() -> ApplicationContainer:
    return ApplicationContainer.failed(
        ErrorResult(
            code="COMPOSITION_FAILED",
            message=RAW_CONTAINER_FAILURE,
            category="composition",
        )
    )


class _DuckTypedContainer:
    """A container-shaped object that is not a real ``ApplicationContainer``."""

    @property
    def state(self) -> ContainerState:
        return ContainerState.READY

    def snapshot(self) -> object:
        raise AssertionError("an impostor container must never be projected")


class _LookupForbiddenContainer(ApplicationContainer):
    """A real container that fails the test if a service is resolved."""

    def get_service(self, service_id: str) -> object:
        raise AssertionError("health must not resolve a service per request")


# ── Constructor authority boundary ───────────────────────────────────────────


@pytest.mark.parametrize("container", [object(), _DuckTypedContainer(), None])
def test_constructor_requires_a_real_application_container(container: object) -> None:
    with pytest.raises(TypeError):
        HealthApplicationService(container)  # type: ignore[arg-type]


# ── Ready composition ────────────────────────────────────────────────────────


def test_ready_container_reports_ready_health() -> None:
    service = HealthApplicationService(_ready_container(*SERVICE_IDS))

    health = service.get_health()

    assert isinstance(health, ApplicationHealth)
    assert health.status == "ok"
    assert health.api_version == APPLICATION_API_VERSION
    assert health.platform_ready is True


def test_ready_health_projects_only_the_allowlisted_service_ids() -> None:
    service = HealthApplicationService(_ready_container(*SERVICE_IDS))

    health = service.get_health()

    assert health.services == SERVICE_IDS
    payload = json.dumps(health.to_dict(), sort_keys=True)
    for service_id in SERVICE_IDS:
        assert service_id in payload
    # Only stable service IDs are projected: never an implementation identity,
    # a contract owner or a runtime contract.
    assert "tests.application.test_health" not in payload
    assert "cmm.test.doubles" not in payload


def test_empty_composition_reports_ready_health_without_services() -> None:
    service = HealthApplicationService(_ready_container())

    health = service.get_health()

    assert health.status == "ok"
    assert health.platform_ready is True
    assert health.services == ()


def test_health_is_deterministic() -> None:
    service = HealthApplicationService(_ready_container(*SERVICE_IDS))

    assert service.get_health() == service.get_health()
    assert service.get_health().to_dict() == service.get_health().to_dict()


# ── Not-ready composition ────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "container",
    [
        _failed_container(),
        ApplicationContainer(
            state=ContainerState.BUILDING,
            registry=None,
            snapshot=None,
            failure=None,
        ),
    ],
)
def test_not_ready_container_reports_degraded_health(
    container: ApplicationContainer,
) -> None:
    health = HealthApplicationService(container).get_health()

    assert health.status == "degraded"
    assert health.platform_ready is False
    assert health.services == ()
    assert health.api_version == APPLICATION_API_VERSION


def test_not_ready_health_never_leaks_the_raw_container_failure() -> None:
    health = HealthApplicationService(_failed_container()).get_health()

    payload = json.dumps(health.to_dict(), sort_keys=True)

    assert RAW_CONTAINER_FAILURE not in payload
    assert "COMPOSITION_FAILED" not in payload
    assert "private" not in payload
    assert "tmp" not in payload


# ── No service-locator behavior ──────────────────────────────────────────────


def test_ready_health_never_resolves_a_service() -> None:
    container = _LookupForbiddenContainer.build(
        CompositionConfiguration(
            required_services=SERVICE_IDS,
            enabled_modules=(MODULE_ID,),
        ),
        modules=(
            StaticCompositionModule(
                MODULE_ID, tuple(_binding(service_id) for service_id in SERVICE_IDS)
            ),
        ),
    )

    health = HealthApplicationService(container).get_health()

    assert health.services == SERVICE_IDS


def test_not_ready_health_never_resolves_a_service_or_a_snapshot() -> None:
    container = _LookupForbiddenContainer(
        state=ContainerState.FAILED,
        registry=None,
        snapshot=None,
        failure=None,
    )

    health = HealthApplicationService(container).get_health()

    assert health.status == "degraded"
