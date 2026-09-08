"""Phase 10.45 — DefaultDomainAPI interface-integration seam tests.

Covers facade forwarding of canonical interface projection inputs, selector
intent submission delegation, error preservation, return types, and protocol
surface declarations for the injected ``DomainInterfaceIntegrator``.
"""

from __future__ import annotations

import typing
from typing import Any

import pytest

from cmm.domains.api import DefaultDomainAPI, DomainAPI
from cmm.domains.errors import DomainInterfaceAuthorityError
from cmm.domains.interface_integration import DomainInterfaceIntegrator
from cmm.domains.interface_integration_contracts import (
    DomainInterfaceIntentResult,
    DomainInterfaceProjection,
)
from tests.domains.test_domain_api_contracts import _make_collaborators


class _RecordingInterfaceIntegrator:
    """Recording integrator double verifying exact identity forwarding."""

    def __init__(self, projection: Any = None, intent_result: Any = None) -> None:
        self.projection = projection
        self.intent_result = intent_result
        self.recorded_project: dict[str, Any] = {}
        self.recorded_submit: dict[str, Any] = {}

    def project(
        self,
        *,
        request: Any,
        resolution: Any,
        composition: Any,
        presentation: Any = None,
        session: Any = None,
        memory_knowledge: Any = None,
        registry: Any = None,
        observability_report: Any = None,
        cross_domain_result: Any = None,
        cross_domain_snapshot: Any = None,
        approvals: Any = None,
    ) -> Any:
        self.recorded_project = {
            "request": request,
            "resolution": resolution,
            "composition": composition,
            "presentation": presentation,
            "session": session,
            "memory_knowledge": memory_knowledge,
            "registry": registry,
            "observability_report": observability_report,
            "cross_domain_result": cross_domain_result,
            "cross_domain_snapshot": cross_domain_snapshot,
            "approvals": approvals,
        }
        return self.projection

    def submit_intent(
        self,
        *,
        intent: Any,
        resolution: Any,
        composition: Any,
        resolution_context: Any,
        permission_request: Any = None,
    ) -> Any:
        self.recorded_submit = {
            "intent": intent,
            "resolution": resolution,
            "composition": composition,
            "resolution_context": resolution_context,
            "permission_request": permission_request,
        }
        return self.intent_result


class _RaisingInterfaceIntegrator:
    """Integrator double that fails closed with the canonical error."""

    def project(self, **kwargs: Any) -> Any:  # type: ignore[no-untyped-def]
        raise DomainInterfaceAuthorityError("projection authority failure")

    def submit_intent(self, **kwargs: Any) -> Any:  # type: ignore[no-untyped-def]
        raise DomainInterfaceAuthorityError("intent authority failure")


def _make_api(integrator: Any = None) -> DefaultDomainAPI:
    collaborators = _make_collaborators()
    if integrator is not None:
        collaborators["interface_integrator"] = integrator
    return DefaultDomainAPI(**collaborators)


class TestInterfaceProjectionDelegation:
    def test_project_interface_forwards_canonical_inputs_unchanged(self) -> None:
        fixed_projection = object()
        recorder = _RecordingInterfaceIntegrator(projection=fixed_projection)
        assert isinstance(recorder, DomainInterfaceIntegrator)
        api = _make_api(recorder)

        request = object()
        resolution = object()
        composition = object()
        presentation = object()
        session = object()
        memory_knowledge = object()
        registry = object()
        observability_report = object()
        cross_domain_result = object()
        cross_domain_snapshot = object()
        approvals = object()

        result = api.project_interface(  # type: ignore[arg-type]
            request,
            resolution=resolution,  # type: ignore[arg-type]
            composition=composition,  # type: ignore[arg-type]
            presentation=presentation,  # type: ignore[arg-type]
            session=session,  # type: ignore[arg-type]
            memory_knowledge=memory_knowledge,  # type: ignore[arg-type]
            registry=registry,  # type: ignore[arg-type]
            observability_report=observability_report,  # type: ignore[arg-type]
            cross_domain_result=cross_domain_result,  # type: ignore[arg-type]
            cross_domain_snapshot=cross_domain_snapshot,  # type: ignore[arg-type]
            approvals=approvals,  # type: ignore[arg-type]
        )

        assert result is fixed_projection
        recorded = recorder.recorded_project
        assert recorded["request"] is request
        assert recorded["resolution"] is resolution
        assert recorded["composition"] is composition
        assert recorded["presentation"] is presentation
        assert recorded["session"] is session
        assert recorded["memory_knowledge"] is memory_knowledge
        assert recorded["registry"] is registry
        assert recorded["observability_report"] is observability_report
        assert recorded["cross_domain_result"] is cross_domain_result
        assert recorded["cross_domain_snapshot"] is cross_domain_snapshot
        assert recorded["approvals"] is approvals

    def test_project_interface_forwards_omitted_optionals_as_none(self) -> None:
        recorder = _RecordingInterfaceIntegrator()
        api = _make_api(recorder)

        request = object()
        resolution = object()
        composition = object()
        api.project_interface(  # type: ignore[arg-type]
            request,
            resolution=resolution,  # type: ignore[arg-type]
            composition=composition,  # type: ignore[arg-type]
        )

        recorded = recorder.recorded_project
        assert recorded["request"] is request
        assert recorded["resolution"] is resolution
        assert recorded["composition"] is composition
        for name in (
            "presentation",
            "session",
            "memory_knowledge",
            "registry",
            "observability_report",
            "cross_domain_result",
            "cross_domain_snapshot",
            "approvals",
        ):
            assert recorded[name] is None, name

    def test_project_interface_return_type_is_canonical_projection(self) -> None:
        hints = typing.get_type_hints(DefaultDomainAPI.project_interface)
        assert hints["return"] is DomainInterfaceProjection


class TestInterfaceIntentDelegation:
    def test_submit_interface_intent_forwards_inputs_unchanged(self) -> None:
        fixed_result = object()
        recorder = _RecordingInterfaceIntegrator(intent_result=fixed_result)
        assert isinstance(recorder, DomainInterfaceIntegrator)
        api = _make_api(recorder)

        intent = object()
        resolution = object()
        composition = object()
        resolution_context = object()
        permission_request = object()

        result = api.submit_interface_intent(  # type: ignore[arg-type]
            intent=intent,
            resolution=resolution,
            composition=composition,
            resolution_context=resolution_context,
            permission_request=permission_request,
        )

        assert result is fixed_result
        recorded = recorder.recorded_submit
        assert recorded["intent"] is intent
        assert recorded["resolution"] is resolution
        assert recorded["composition"] is composition
        assert recorded["resolution_context"] is resolution_context
        assert recorded["permission_request"] is permission_request

    def test_submit_interface_intent_forwards_omitted_permission_request(self) -> None:
        recorder = _RecordingInterfaceIntegrator()
        api = _make_api(recorder)

        intent = object()
        resolution = object()
        composition = object()
        resolution_context = object()
        api.submit_interface_intent(  # type: ignore[arg-type]
            intent=intent,
            resolution=resolution,
            composition=composition,
            resolution_context=resolution_context,
        )

        recorded = recorder.recorded_submit
        assert recorded["intent"] is intent
        assert recorded["resolution"] is resolution
        assert recorded["composition"] is composition
        assert recorded["resolution_context"] is resolution_context
        assert recorded["permission_request"] is None

    def test_submit_interface_intent_return_type_is_canonical_result(self) -> None:
        hints = typing.get_type_hints(DefaultDomainAPI.submit_interface_intent)
        assert hints["return"] is DomainInterfaceIntentResult


class TestInterfaceAuthorityErrorPreservation:
    def test_project_interface_error_is_not_swallowed(self) -> None:
        api = _make_api(_RaisingInterfaceIntegrator())

        with pytest.raises(DomainInterfaceAuthorityError):
            api.project_interface(  # type: ignore[arg-type]
                object(),
                resolution=object(),  # type: ignore[arg-type]
                composition=object(),  # type: ignore[arg-type]
            )

    def test_submit_interface_intent_error_is_not_swallowed(self) -> None:
        api = _make_api(_RaisingInterfaceIntegrator())

        with pytest.raises(DomainInterfaceAuthorityError):
            api.submit_interface_intent(  # type: ignore[arg-type]
                intent=object(),
                resolution=object(),
                composition=object(),
                resolution_context=object(),
            )


class TestApiProtocolSurface:
    def test_protocol_declares_interface_seam_methods(self) -> None:
        assert callable(getattr(DomainAPI, "project_interface", None))
        assert callable(getattr(DomainAPI, "submit_interface_intent", None))

    def test_default_api_annotations_use_canonical_protocol(self) -> None:
        from cmm.domains.operation_execution import DefaultDomainOperationOrchestrator

        params = typing.get_type_hints(
            DefaultDomainAPI.__init__,
            localns={
                "DefaultDomainOperationOrchestrator": DefaultDomainOperationOrchestrator
            },
        )
        assert params["interface_integrator"] == DomainInterfaceIntegrator | None
