"""Phase 10.9 – Source-level boundary checks for the Cross-Domain Engine.

Verifies that the Phase 10.9 modules never import concrete subsystem
implementations, never touch the filesystem/network/process primitives
directly, and never use a blanket ``except Exception``.
"""

from __future__ import annotations

from pathlib import Path

import pytest

PHASE_10_9_MODULES = [
    "cross_domain_contracts.py",
    "cross_domain_ports.py",
    "cross_domain_context.py",
    "cross_domain_limits.py",
    "cross_domain_aggregation.py",
    "cross_domain_engine.py",
]

FORBIDDEN_IMPORTS = (
    "cmm.agent_runtime",
    "cmm.cognitive",
    "cmm.execution",
    "cmm.workflows",
    "cmm.memory",
    "cmm.domains.registry",
    "requests",
    "httpx",
    "urllib",
    "socket",
)

FORBIDDEN_PATTERNS = (
    "except Exception",
    "open(",
    "Path(",
    "asyncio",
    "threading",
    "multiprocessing",
    "subprocess",
)


def _domains_dir() -> Path:
    return Path(__file__).resolve().parents[2] / "cmm" / "domains"


@pytest.fixture(params=PHASE_10_9_MODULES)
def module_source(request: pytest.FixtureRequest) -> tuple[str, str]:
    path = _domains_dir() / request.param
    return request.param, path.read_text(encoding="utf-8")


def _import_lines(source: str) -> list[str]:
    return [
        line.strip()
        for line in source.splitlines()
        if line.strip().startswith(("import ", "from "))
    ]


class TestForbiddenImports:
    def test_no_forbidden_subsystem_imports(
        self, module_source: tuple[str, str]
    ) -> None:
        name, source = module_source
        imports = _import_lines(source)
        for forbidden in FORBIDDEN_IMPORTS:
            offending = [line for line in imports if forbidden in line]
            assert not offending, f"{name} imports forbidden module: {offending}"


class TestForbiddenPatterns:
    def test_no_forbidden_patterns(self, module_source: tuple[str, str]) -> None:
        name, source = module_source
        for pattern in FORBIDDEN_PATTERNS:
            assert pattern not in source, (
                f"{name} contains forbidden pattern: {pattern}"
            )


class TestNoBroadCatch:
    def test_all_modules_free_of_bare_except(self) -> None:
        for filename in PHASE_10_9_MODULES:
            source = (_domains_dir() / filename).read_text(encoding="utf-8")
            assert "except Exception" not in source
            assert "except:" not in source


class TestEngineDoesNotAccessRegistryDirectly:
    def test_engine_module_has_no_store_or_registry_references(self) -> None:
        source = (_domains_dir() / "cross_domain_engine.py").read_text(encoding="utf-8")
        assert "DomainRegistry(" not in source
        assert "registry_store" not in source
        assert "InMemoryDomainRegistryStore" not in source
