from __future__ import annotations

from typing import Optional
import pytest

from cmm.memory import (
    KnowledgeGraph,
    KnowledgeNode,
    ProjectIndexer,
    TechnicalMemory,
)
from cmm.memory.repository import KnowledgeRepository


class InMemoryKnowledgeRepository:
    """Mock repository for testing TechnicalMemory without file system persistence."""

    def __init__(self, graph: KnowledgeGraph) -> None:
        self.graph = graph

    def load(self) -> KnowledgeGraph:
        return self.graph

    def save(self, graph: KnowledgeGraph) -> None:
        self.graph = graph


def test_technical_memory_load_and_query(tmp_path) -> None:
    (tmp_path / "app").mkdir()
    (tmp_path / "app" / "__init__.py").write_text("", encoding="utf-8")
    (tmp_path / "app" / "service.py").write_text(
        """
def helper():
    return 42


def build():
    return helper()


class UserService:
    def process(self):
        return helper()
""",
        encoding="utf-8",
    )

    indexer = ProjectIndexer(tmp_path)
    graph = indexer.build()
    repo = InMemoryKnowledgeRepository(graph)
    memory = TechnicalMemory(repo)

    with pytest.raises(RuntimeError, match="TechnicalMemory is not loaded"):
        memory.find_symbol("helper")

    memory.load()

    # Test find_symbol
    symbols = memory.find_symbol("helper")
    assert len(symbols) == 1
    assert symbols[0].kind == "Function"
    assert symbols[0].title == "helper"

    # Test find_module
    module_node = memory.find_module("app.service")
    assert module_node is not None
    assert module_node.kind == "Module"

    # Test find_class
    class_node = memory.find_class("UserService")
    assert class_node is not None
    assert class_node.kind == "Class"

    # Test find_function
    func_node = memory.find_function("build")
    assert func_node is not None
    assert func_node.kind == "Function"

    # Test find_method
    method_node = memory.find_method("process")
    assert method_node is not None
    assert method_node.kind == "Method"

    # Test find_callers and find_callees
    callers_of_helper = memory.find_callers(symbols[0])
    caller_titles = {c.title for c in callers_of_helper}
    assert "build" in caller_titles
    assert "process" in caller_titles

    callees_of_build = memory.find_callees(func_node)
    assert len(callees_of_build) == 1
    assert callees_of_build[0].title == "helper"


def test_technical_memory_project_summary(tmp_path) -> None:
    (tmp_path / "pkg").mkdir()
    (tmp_path / "pkg" / "__init__.py").write_text("", encoding="utf-8")
    (tmp_path / "pkg" / "models.py").write_text(
        """
class Base:
    pass


class Item(Base):
    def validate(self):
        pass
""",
        encoding="utf-8",
    )
    (tmp_path / "pkg" / "utils.py").write_text(
        """
def parse():
    pass
""",
        encoding="utf-8",
    )

    indexer = ProjectIndexer(tmp_path)
    graph = indexer.build()
    repo = InMemoryKnowledgeRepository(graph)
    memory = TechnicalMemory(repo)
    memory.load()

    summary = memory.project_summary()
    assert summary["modules"] == 3  # pkg, pkg.__init__, pkg.models, pkg.utils
    assert summary["classes"] == 2  # Base, Item
    assert summary["functions"] == 1  # parse
    assert summary["methods"] == 1  # validate
    assert summary["relationships"] == len(graph.edges)


def test_technical_memory_finds_all_supported_symbol_types_and_missing_symbols(tmp_path) -> None:
    (tmp_path / "sample.py").write_text(
        """
class Sample:
    def run(self):
        pass


def run():
    pass
""",
        encoding="utf-8",
    )

    memory = TechnicalMemory(InMemoryKnowledgeRepository(ProjectIndexer(tmp_path).build()))
    memory.load()

    run_symbols = memory.find_symbol("run")

    assert {(node.kind, node.title) for node in run_symbols} == {
        ("Function", "run"),
        ("Method", "run"),
    }
    assert memory.find_symbol("missing") == []
    assert memory.find_module("missing") is None
    assert memory.find_class("missing") is None
    assert memory.find_function("missing") is None
    assert memory.find_method("missing") is None


def test_technical_memory_accepts_symbol_identifiers_for_call_queries(tmp_path) -> None:
    (tmp_path / "sample.py").write_text(
        """
def helper():
    pass


def build():
    helper()
""",
        encoding="utf-8",
    )

    memory = TechnicalMemory(InMemoryKnowledgeRepository(ProjectIndexer(tmp_path).build()))
    memory.load()

    helper = memory.find_function("helper")
    build = memory.find_function("build")

    assert helper is not None
    assert build is not None
    assert memory.find_callers(helper.identifier) == [build]
    assert memory.find_callees(build.identifier) == [helper]
