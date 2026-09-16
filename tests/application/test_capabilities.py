"""Phase 11.3 — capability application service tests.

``CapabilityApplicationService`` projects the frozen public capability
declaration set of the v1 backend.  Capability discovery is descriptive: it
never infers that an owner exists because a route, a module or an import path
exists, and it never turns a deferred capability into an available one.

These tests lock the frozen declaration set, the unavailable/deferred
declarations, the immutable-declaration constructor boundary and the
absence of dynamic import inference.

See ``docs/superpowers/specs/2026-09-16-phase-11.3-application-backend-design.md``.
"""

from __future__ import annotations

import importlib

import pytest

from cmm.application.capabilities import (
    CapabilityApplicationService,
    build_default_capabilities,
)
from cmm.application.contracts import (
    APPLICATION_API_VERSION,
    ApplicationCapability,
    ApplicationOperation,
    CapabilityStatus,
)

#: The frozen initial v1 capability set.
EXPECTED_CAPABILITIES: dict[str, CapabilityStatus] = {
    "agents": CapabilityStatus.DEFERRED,
    "backups": CapabilityStatus.DEFERRED,
    "capabilities": CapabilityStatus.AVAILABLE,
    "domains": CapabilityStatus.DEFERRED,
    "health": CapabilityStatus.AVAILABLE,
    "messages": CapabilityStatus.AVAILABLE,
    "metrics": CapabilityStatus.DEFERRED,
    "model-routing": CapabilityStatus.DEFERRED,
    "plugins": CapabilityStatus.DEFERRED,
    "request-cancellation": CapabilityStatus.UNAVAILABLE,
    "sessions": CapabilityStatus.AVAILABLE,
    "streaming": CapabilityStatus.AVAILABLE,
}


def _default_service() -> CapabilityApplicationService:
    return CapabilityApplicationService(build_default_capabilities())


def _declarations_by_id() -> dict[str, ApplicationCapability]:
    return {
        declaration.capability_id: declaration
        for declaration in build_default_capabilities()
    }


# ── Frozen declaration set ───────────────────────────────────────────────────


def test_default_capabilities_freeze_the_initial_v1_set() -> None:
    declarations = _declarations_by_id()

    assert {
        capability_id: declaration.status
        for capability_id, declaration in declarations.items()
    } == EXPECTED_CAPABILITIES


def test_default_capabilities_are_a_tuple_of_public_declarations() -> None:
    capabilities = build_default_capabilities()

    assert isinstance(capabilities, tuple)
    assert all(
        isinstance(capability, ApplicationCapability) for capability in capabilities
    )
    assert len(capabilities) == len(EXPECTED_CAPABILITIES)


@pytest.mark.parametrize(
    "capability_id",
    sorted(
        capability_id
        for capability_id, status in EXPECTED_CAPABILITIES.items()
        if status is CapabilityStatus.AVAILABLE
    ),
)
def test_available_capabilities_are_available(capability_id: str) -> None:
    declaration = _declarations_by_id()[capability_id]

    assert declaration.status is CapabilityStatus.AVAILABLE
    assert declaration.reason_code is None


@pytest.mark.parametrize(
    "capability_id",
    sorted(
        capability_id
        for capability_id, status in EXPECTED_CAPABILITIES.items()
        if status is CapabilityStatus.DEFERRED
    ),
)
def test_deferred_capabilities_stay_deferred(capability_id: str) -> None:
    declaration = _declarations_by_id()[capability_id]

    assert declaration.status is CapabilityStatus.DEFERRED
    assert declaration.reason_code is not None
    assert declaration.operations == ()


def test_request_cancellation_stays_unavailable() -> None:
    declaration = _declarations_by_id()["request-cancellation"]

    assert declaration.status is CapabilityStatus.UNAVAILABLE
    assert declaration.reason_code is not None


def test_every_capability_declares_the_public_api_version() -> None:
    for declaration in build_default_capabilities():
        assert declaration.version == APPLICATION_API_VERSION


def test_no_capability_invents_an_operation_identity() -> None:
    frozen_operations = {operation.value for operation in ApplicationOperation}

    for declaration in build_default_capabilities():
        assert set(declaration.operations) <= frozen_operations


def test_no_deferred_capability_reports_an_owner_specific_operation() -> None:
    for declaration in build_default_capabilities():
        if declaration.status is CapabilityStatus.AVAILABLE:
            continue
        assert declaration.operations == ()


# ── Service boundary ─────────────────────────────────────────────────────────


def test_list_capabilities_returns_the_frozen_declarations() -> None:
    service = _default_service()

    listed = service.list_capabilities()

    assert isinstance(listed, tuple)
    assert listed == build_default_capabilities()
    assert listed == service.list_capabilities()


def test_list_capabilities_is_deterministically_ordered() -> None:
    identifiers = [
        declaration.capability_id for declaration in _default_service().list_capabilities()
    ]

    assert identifiers == sorted(identifiers)


@pytest.mark.parametrize("declarations", [[], ("not-a-capability",), [object()]])
def test_constructor_requires_an_immutable_tuple_of_declarations(
    declarations: object,
) -> None:
    with pytest.raises(TypeError):
        CapabilityApplicationService(declarations)  # type: ignore[arg-type]


def test_constructor_rejects_duplicate_capability_ids() -> None:
    declaration = ApplicationCapability(
        capability_id="health",
        status=CapabilityStatus.AVAILABLE,
        version=APPLICATION_API_VERSION,
    )

    with pytest.raises(ValueError):
        CapabilityApplicationService((declaration, declaration))


def test_constructor_accepts_an_empty_declaration_tuple() -> None:
    service = CapabilityApplicationService(())

    assert service.list_capabilities() == ()


# ── No dynamic import inference ──────────────────────────────────────────────


def test_discovery_never_infers_capabilities_from_import_state(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Capability discovery must not import any owner to decide availability."""

    def _forbidden_import(name: str, *args: object, **kwargs: object) -> object:
        raise AssertionError(f"capability discovery must not import {name}")

    monkeypatch.setattr(importlib, "import_module", _forbidden_import)

    declarations = build_default_capabilities()
    listed = CapabilityApplicationService(declarations).list_capabilities()

    assert {
        declaration.capability_id: declaration.status for declaration in listed
    } == EXPECTED_CAPABILITIES
