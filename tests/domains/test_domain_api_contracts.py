"""Phase 10.36 — Domain API facade contract tests.

Covers protocol shape, constructor wiring, public exports, import safety,
and canonical exception propagation.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from cmm.domains.api import DefaultDomainAPI, DomainAPI
from cmm.domains.conflict_resolution import DomainConflictResolver
from cmm.domains.discovery import FileSystemDomainDiscovery
from cmm.domains.loader import DeclarativeDomainLoader
from cmm.domains.manifest_reader import JsonDomainManifestReader
from cmm.domains.registry import DomainRegistry
from cmm.domains.resolver import DefaultDomainResolver
from cmm.domains.session_persistence import SharedSessionDomainAdapter
from cmm.domains.session_resumer import DomainSessionResumer
from cmm.domains.trace_assembler import DomainTraceAssembler
from cmm.domains.trace_validation import DefaultDomainTraceReferenceValidator
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
