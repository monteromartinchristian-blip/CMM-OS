"""Phase 10.37 — Architectural boundary guards.

Proves Phase 10.37 creates no parallel observability infrastructure, never
couples operational Domain components to observability, keeps Domain Events at
their Phase 10.33 23/23 closure and preserves the Phase 10.36 DomainAPI.
"""

from __future__ import annotations

import importlib
import inspect
import pkgutil
from pathlib import Path

import cmm.domains

ROOT = Path(cmm.domains.__file__).parent

FORBIDDEN_OBSERVABILITY_FILES = (
    "observability_store.py",
    "observability_repository.py",
    "observability_event_bus.py",
    "observability_runtime.py",
    "observability_engine.py",
    "observability_registry.py",
    "observability_loader.py",
    "observability_trace.py",
)

FORBIDDEN_OBSERVABILITY_CLASSES = (
    "DomainObservabilityStore",
    "DomainObservabilityRepository",
    "DomainObservabilityEventBus",
    "DomainObservabilityRuntime",
    "DomainObservabilityEngine",
    "DomainObservabilityRegistry",
    "DomainObservabilityLoader",
    "DomainObservabilityTrace",
)


def test_no_parallel_observability_infrastructure_files() -> None:
    present = [name for name in FORBIDDEN_OBSERVABILITY_FILES if (ROOT / name).exists()]
    assert present == []


def test_no_parallel_observability_infrastructure_classes() -> None:
    for module_name in (
        "cmm.domains.observability_contracts",
        "cmm.domains.observability_metrics",
        "cmm.domains.observability_health",
        "cmm.domains.observability_service",
    ):
        module = importlib.import_module(module_name)
        for name, value in vars(module).items():
            if inspect.isclass(value) and value.__module__ == module_name:
                assert name not in FORBIDDEN_OBSERVABILITY_CLASSES, name


def test_operational_domain_components_do_not_import_observability() -> None:
    """Resolver/composer/conflict/runtime must never depend on observability."""
    operational_modules = (
        "cmm.domains.resolver",
        "cmm.domains.resolver_scoring",
        "cmm.domains.composer",
        "cmm.domains.conflict_resolution",
        "cmm.domains.operation_execution",
        "cmm.domains.workflow_execution",
        "cmm.domains.registry",
    )
    for module_name in operational_modules:
        module = importlib.import_module(module_name)
        source = inspect.getsource(module)
        assert "observability_" not in source, module_name


def test_no_domain_observability_trace_class() -> None:
    module = importlib.import_module("cmm.domains.observability_contracts")
    assert not hasattr(module, "DomainObservabilityTrace")


def test_no_new_session_repository_or_enumeration() -> None:
    forbidden = (
        "DomainSessionRepository",
        "DomainObservabilitySessionStore",
        "SessionEnumeration",
    )
    for symbol in forbidden:
        assert not hasattr(cmm.domains, symbol)


def test_domain_events_catalog_stays_23_of_23() -> None:
    from cmm.domains.event_catalog import CANONICAL_DOMAIN_EVENTS

    assert len(CANONICAL_DOMAIN_EVENTS) == 23
    assert len(set(CANONICAL_DOMAIN_EVENTS)) == 23


def test_phase_10_37_modules_do_not_import_agent_observability_stores() -> None:
    """Observability must not derive Domain truth from Agent Runtime stores."""
    forbidden_imports = (
        "cmm.agent_runtime.observability",
        "cmm.agent_runtime.metrics",
    )
    for module_name in (
        "cmm.domains.observability_contracts",
        "cmm.domains.observability_metrics",
        "cmm.domains.observability_health",
        "cmm.domains.observability_service",
    ):
        module = importlib.import_module(module_name)
        source = inspect.getsource(module)
        for forbidden in forbidden_imports:
            assert forbidden not in source, module_name


def test_no_trace_persistence_store_created() -> None:
    assert not (ROOT / "observability_trace.py").exists()
    module = importlib.import_module("cmm.domains.observability_contracts")
    assert not hasattr(module, "DomainObservabilityTrace")


def test_no_observability_persistence_modules() -> None:
    """Observability projections must never persist state."""
    names = {module.name for module in pkgutil.iter_modules([ROOT.as_posix()])}
    assert "observability_store" not in names
    assert "observability_repository" not in names
    assert "observability_persistence" not in names
