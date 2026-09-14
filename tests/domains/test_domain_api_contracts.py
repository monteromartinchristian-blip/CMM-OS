"""Phase 10.36 — Domain API facade contract tests.

Covers protocol shape, constructor wiring, public exports, import safety,
and canonical exception propagation.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

from cmm.domains.api import DefaultDomainAPI, DomainAPI
from cmm.domains.conflict_resolution import DomainConflictResolver
from cmm.domains.contracts import DomainCapability
from cmm.domains.discovery import DomainDiscovery, FileSystemDomainDiscovery
from cmm.domains.interface_integration import (
    DefaultDomainInterfaceIntegrator,
    DomainInterfaceIntegrator,
)
from cmm.domains.loader import DeclarativeDomainLoader
from cmm.domains.manifest_reader import JsonDomainManifestReader
from cmm.domains.memory_knowledge_integration import (
    DefaultDomainMemoryKnowledgeIntegrator,
)
from cmm.domains.memory_knowledge_integration_contracts import (
    DomainMemoryKnowledgeIntegrator,
)
from cmm.domains.registry import DomainRegistry
from cmm.domains.resolver import DefaultDomainResolver, DomainResolver
from cmm.domains.session_persistence import SharedSessionDomainAdapter
from cmm.domains.session_resumer import DomainSessionResumer
from cmm.domains.trace_assembler import DomainTraceAssembler
from cmm.domains.trace_validation import (
    DefaultDomainTraceReferenceValidator,
    DomainTraceReferenceValidator,
)
from cmm.domains.validation import PipelineDomainValidator
from cmm.domains.workflow_execution import DomainWorkflowExecutor
from cmm.domains.workflow_registry import InMemoryDomainWorkflowRegistry

APPROVED_METHODS = (
    "list_domains",
    "get_domain",
    "discover_domains",
    "validate_domain",
    "install_domain",
    "enable_domain",
    "disable_domain",
    "resolve_domain",
    "get_capabilities",
    "get_resources",
    "get_rules",
    "get_operations",
    "get_workflows",
    "execute_operation",
    "start_workflow",
    "get_session",
    "resume_session",
    "resolve_conflict",
    "assemble_trace",
    "validate_trace",
    "project_memory_knowledge",
    "project_interface",
    "submit_interface_intent",
)


def _make_collaborators() -> dict[str, object]:
    registry = DomainRegistry()
    return {
        "domain_registry": registry,
        "discovery": FileSystemDomainDiscovery(),
        "validator": PipelineDomainValidator(),
        "loader": DeclarativeDomainLoader(
            manifest_reader=JsonDomainManifestReader(), registry=registry
        ),
        "resolver": DefaultDomainResolver(),
        "operation_orchestrator": object(),
        "workflow_registry": InMemoryDomainWorkflowRegistry(),
        "workflow_executor": DomainWorkflowExecutor(id_factory=lambda: "wf-run-1"),
        "session_adapter": SharedSessionDomainAdapter(store=_InMemoryStoreForWiring()),
        "session_resumer": DomainSessionResumer(),
        "conflict_resolver": DomainConflictResolver(),
        "trace_assembler": DomainTraceAssembler(),
        "trace_validator": DefaultDomainTraceReferenceValidator(),
        "trust_policy_lookup": None,
        "memory_knowledge_integrator": DefaultDomainMemoryKnowledgeIntegrator(),
        "interface_integrator": DefaultDomainInterfaceIntegrator(),
    }


class _InMemoryStoreForWiring:
    """Minimal shared-session store double for wiring-only tests."""

    def load(self, session_id: str) -> object | None:
        return None

    def save(self, state: object) -> object:
        return state


class TestProtocolShape:
    def test_default_api_satisfies_protocol(self) -> None:
        api = DefaultDomainAPI(**_make_collaborators())
        assert isinstance(api, DomainAPI)

    def test_protocol_is_runtime_checkable(self) -> None:
        import typing

        assert getattr(DomainAPI, "_is_runtime_protocol", False) is True
        assert typing.runtime_checkable is not None

    def test_all_approved_methods_declared(self) -> None:
        for name in APPROVED_METHODS:
            assert callable(getattr(DomainAPI, name, None)), name

    def test_no_invented_surface(self) -> None:
        forbidden = (
            "list_all_domain_sessions",
            "search_domain_sessions",
            "get_trace",
            "get_trace_by_id",
            "list_traces",
            "uninstall_domain",
            "publish_domain",
            "install_package_archive",
            "grant_domain_permission",
        )
        for name in forbidden:
            assert getattr(DomainAPI, name, None) is None, name
            assert not hasattr(DefaultDomainAPI, name), name


class TestConstructorWiring:
    def test_construction_stores_collaborator_references(self) -> None:
        collaborators = _make_collaborators()
        api = DefaultDomainAPI(**collaborators)
        assert api._domain_registry is collaborators["domain_registry"]
        assert api._discovery is collaborators["discovery"]
        assert api._validator is collaborators["validator"]
        assert api._loader is collaborators["loader"]
        assert api._resolver is collaborators["resolver"]
        assert api._operation_orchestrator is collaborators["operation_orchestrator"]
        assert api._workflow_registry is collaborators["workflow_registry"]
        assert api._workflow_executor is collaborators["workflow_executor"]
        assert api._session_adapter is collaborators["session_adapter"]
        assert api._session_resumer is collaborators["session_resumer"]
        assert api._conflict_resolver is collaborators["conflict_resolver"]
        assert api._trace_assembler is collaborators["trace_assembler"]
        assert api._trace_validator is collaborators["trace_validator"]
        assert (
            api._memory_knowledge_integrator
            is collaborators["memory_knowledge_integrator"]
        )
        assert api._interface_integrator is collaborators["interface_integrator"]

    def test_default_memory_knowledge_integrator_created_if_omitted(self) -> None:
        collaborators = _make_collaborators()
        del collaborators["memory_knowledge_integrator"]
        api = DefaultDomainAPI(**collaborators)
        assert isinstance(
            api._memory_knowledge_integrator, DefaultDomainMemoryKnowledgeIntegrator
        )

    def test_default_interface_integrator_created_if_omitted(self) -> None:
        collaborators = _make_collaborators()
        del collaborators["interface_integrator"]
        api = DefaultDomainAPI(**collaborators)
        assert isinstance(api._interface_integrator, DefaultDomainInterfaceIntegrator)

    def test_missing_required_collaborator_rejected(self) -> None:
        collaborators = _make_collaborators()
        del collaborators["domain_registry"]
        with pytest.raises((TypeError, ValueError)):
            DefaultDomainAPI(**collaborators)

    def test_none_collaborator_rejected(self) -> None:
        collaborators = _make_collaborators()
        collaborators["loader"] = None
        with pytest.raises((TypeError, ValueError)):
            DefaultDomainAPI(**collaborators)

    def test_no_hidden_singleton_construction(self) -> None:
        collaborators = _make_collaborators()
        api = DefaultDomainAPI(**collaborators)
        # The facade must not own independent mutable domain state.
        for attr in vars(api):
            assert attr.startswith("_"), attr
        injected = set(collaborators.values())
        for value in vars(api).values():
            assert value in injected


class TestImportSafety:
    def test_fresh_import_is_side_effect_free(self, tmp_path: Path) -> None:
        before = sorted(p.name for p in tmp_path.iterdir())
        code = "import cmm.domains\nimport cmm.domains.api\nprint('OK')\n"
        result = subprocess.run(
            [sys.executable, "-c", code],
            cwd=tmp_path,
            capture_output=True,
            text=True,
            check=False,
            env={"PYTHONDONTWRITEBYTECODE": "1", "PATH": "/usr/bin:/bin"},
        )
        assert result.returncode == 0, result.stderr
        assert "OK" in result.stdout
        after = sorted(p.name for p in tmp_path.iterdir())
        assert after == before

    def test_import_does_not_mutate_registry(self) -> None:
        import cmm.domains as domains_pkg

        assert not hasattr(domains_pkg, "_default_api")
        assert not hasattr(domains_pkg, "default_domain_api")


class TestPublicExports:
    def test_domain_api_exported_from_package(self) -> None:
        import cmm.domains as domains_pkg

        assert domains_pkg.DomainAPI is DomainAPI
        assert domains_pkg.DefaultDomainAPI is DefaultDomainAPI

    def test_exports_listed_in_all(self) -> None:
        import cmm.domains as domains_pkg

        assert "DomainAPI" in domains_pkg.__all__
        assert "DefaultDomainAPI" in domains_pkg.__all__


class TestCanonicalProtocolTyping:
    """MAJOR-01 remediation — stable public boundary uses canonical protocols."""

    def test_constructor_annotations_use_canonical_protocols(self) -> None:
        import typing

        from cmm.domains.operation_execution import DefaultDomainOperationOrchestrator

        # ``DefaultDomainOperationOrchestrator`` is imported under TYPE_CHECKING
        # in api.py; supply it so get_type_hints can evaluate all annotations.
        hints = typing.get_type_hints(
            DefaultDomainAPI.__init__,
            localns={
                "DefaultDomainOperationOrchestrator": DefaultDomainOperationOrchestrator
            },
        )
        assert hints["discovery"] is DomainDiscovery
        assert hints["resolver"] is DomainResolver
        assert hints["trace_validator"] is DomainTraceReferenceValidator
        assert (
            hints["memory_knowledge_integrator"]
            == DomainMemoryKnowledgeIntegrator | None
        )
        assert hints["interface_integrator"] == DomainInterfaceIntegrator | None

    def test_constructor_signature_parameter_names_present(self) -> None:
        import inspect

        params = inspect.signature(DefaultDomainAPI.__init__).parameters
        for name in (
            "discovery",
            "resolver",
            "trace_validator",
            "memory_knowledge_integrator",
            "interface_integrator",
        ):
            assert name in params, name

    def test_get_capabilities_annotation_is_canonical_capability_tuple(self) -> None:
        import typing

        for owner in (DomainAPI, DefaultDomainAPI):
            hints = typing.get_type_hints(owner.get_capabilities)
            assert hints["return"] == tuple[DomainCapability, ...], owner
            assert hints["return"] != tuple[Any, ...], owner

    def test_alternate_protocol_implementations_are_injectable(self) -> None:
        class _AltDiscovery:
            def discover(self, sources):  # type: ignore[no-untyped-def]
                raise AssertionError("not called in wiring test")

        class _AltResolver:
            def resolve(self, context):  # type: ignore[no-untyped-def]
                raise AssertionError("not called in wiring test")

        class _AltTraceValidator:
            def validate(self, trace, inventory):  # type: ignore[no-untyped-def]
                raise AssertionError("not called in wiring test")

        class _AltMemoryKnowledgeIntegrator:
            def project(self, *args, **kwargs):  # type: ignore[no-untyped-def]
                raise AssertionError("not called in wiring test")

        class _AltInterfaceIntegrator:
            def project(self, **kwargs):  # type: ignore[no-untyped-def]
                raise AssertionError("not called in wiring test")

            def submit_intent(self, **kwargs):  # type: ignore[no-untyped-def]
                raise AssertionError("not called in wiring test")

        collaborators = _make_collaborators()
        collaborators["discovery"] = _AltDiscovery()
        collaborators["resolver"] = _AltResolver()
        collaborators["trace_validator"] = _AltTraceValidator()
        collaborators["memory_knowledge_integrator"] = _AltMemoryKnowledgeIntegrator()
        collaborators["interface_integrator"] = _AltInterfaceIntegrator()
        api = DefaultDomainAPI(**collaborators)
        assert api._discovery is collaborators["discovery"]
        assert api._resolver is collaborators["resolver"]
        assert api._trace_validator is collaborators["trace_validator"]
        assert (
            api._memory_knowledge_integrator
            is collaborators["memory_knowledge_integrator"]
        )
        assert api._interface_integrator is collaborators["interface_integrator"]

    def test_concrete_defaults_still_satisfy_constructor_boundary(self) -> None:
        collaborators = _make_collaborators()
        api = DefaultDomainAPI(**collaborators)
        assert isinstance(api._discovery, FileSystemDomainDiscovery)
        assert isinstance(api._resolver, DefaultDomainResolver)
        assert isinstance(api._trace_validator, DefaultDomainTraceReferenceValidator)
        assert isinstance(
            api._memory_knowledge_integrator, DefaultDomainMemoryKnowledgeIntegrator
        )
        assert isinstance(api._interface_integrator, DefaultDomainInterfaceIntegrator)


class _RecordingMemoryKnowledgeIntegrator:
    """Recording integrator double verifying exact identity forwarding."""

    def __init__(self, result: object) -> None:
        self.result = result
        self.recorded_args: dict[str, object] = {}

    def project(
        self,
        request: Any,
        *,
        memory_request: Any,
        view: Any,
        memory_inventory: Any,
        inventory: Any,
        resolution: Any = None,
        composition: Any = None,
    ) -> Any:
        self.recorded_args = {
            "request": request,
            "memory_request": memory_request,
            "view": view,
            "memory_inventory": memory_inventory,
            "inventory": inventory,
            "resolution": resolution,
            "composition": composition,
        }
        return self.result


class TestMemoryKnowledgeProjectionDelegation:
    def test_project_memory_knowledge_delegates_to_injected_integrator(self) -> None:
        fixed_projection = object()
        recorder = _RecordingMemoryKnowledgeIntegrator(fixed_projection)
        collaborators = _make_collaborators()
        collaborators["memory_knowledge_integrator"] = recorder
        api = DefaultDomainAPI(**collaborators)

        req = object()
        mem_req = object()
        view = object()
        mem_inv = object()
        inv = object()

        resolution = object()
        composition = object()
        res = api.project_memory_knowledge(
            req,  # type: ignore[arg-type]
            memory_request=mem_req,  # type: ignore[arg-type]
            view=view,  # type: ignore[arg-type]
            memory_inventory=mem_inv,  # type: ignore[arg-type]
            inventory=inv,  # type: ignore[arg-type]
            resolution=resolution,  # type: ignore[arg-type]
            composition=composition,  # type: ignore[arg-type]
        )

        assert res is fixed_projection
        assert recorder.recorded_args["request"] is req
        assert recorder.recorded_args["memory_request"] is mem_req
        assert recorder.recorded_args["view"] is view
        assert recorder.recorded_args["memory_inventory"] is mem_inv
        assert recorder.recorded_args["inventory"] is inv
        assert recorder.recorded_args["resolution"] is resolution
        assert recorder.recorded_args["composition"] is composition
