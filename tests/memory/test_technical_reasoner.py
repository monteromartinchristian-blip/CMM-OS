from __future__ import annotations

from cmm.memory import (
    KnowledgeGraph,
    ProjectIndexer,
    TechnicalMemory,
    TechnicalReasoner,
)


class InMemoryKnowledgeRepository:
    """Repository double that supplies a prebuilt knowledge graph."""

    def __init__(self, graph: KnowledgeGraph) -> None:
        self._graph = graph

    def load(self) -> KnowledgeGraph:
        """Return the configured graph."""
        return self._graph

    def save(self, graph: KnowledgeGraph) -> None:
        """Replace the configured graph."""
        self._graph = graph


def test_summarize_symbol_returns_structure_and_relationships(tmp_path) -> None:
    reasoner = _build_reasoner(tmp_path)

    summary = reasoner.summarize_symbol("FeatureService")

    assert summary is not None
    assert summary["type"] == "Class"
    assert summary["location"] == tmp_path / "app" / "service.py"
    assert summary["parent"].title == "app.service"
    assert [node.title for node in summary["children"]] == ["run"]
    assert [node.title for node in summary["relationships"]["uses"]] == ["Feature"]
    assert reasoner.summarize_symbol("missing") is None


def test_explain_dependencies_organizes_import_usage_and_inheritance(tmp_path) -> None:
    reasoner = _build_reasoner(tmp_path)

    module_dependencies = reasoner.explain_dependencies("app.service")
    feature_dependencies = reasoner.explain_dependencies("Feature")

    assert module_dependencies is not None
    assert feature_dependencies is not None
    assert [node.title for node in module_dependencies["imports"]] == ["app.models"]
    assert [node.title for node in feature_dependencies["used_by"]] == ["FeatureService"]
    assert [node.title for node in feature_dependencies["inherits_from"]] == ["Base"]
    assert reasoner.explain_dependencies("missing") is None


def test_explain_call_graph_and_impact_analysis_are_deterministic(tmp_path) -> None:
    reasoner = _build_reasoner(tmp_path)

    call_graph = reasoner.explain_call_graph("helper")
    impact = reasoner.impact_analysis("helper")

    assert call_graph is not None
    assert impact is not None
    assert {node.title for node in call_graph["callers"]} == {"build", "run"}
    assert call_graph["callees"] == []
    assert {node.title for node in impact["direct_dependents"]} == {"build", "run"}
    assert impact["risk"] == "medium"
    assert reasoner.explain_call_graph("missing") is None
    assert reasoner.impact_analysis("missing") is None


def test_impact_analysis_assigns_high_risk_to_dense_call_graphs(tmp_path) -> None:
    (tmp_path / "sample.py").write_text(
        """
def dependency_one():
    pass


def dependency_two():
    pass


def dependency_three():
    pass


def target():
    dependency_one()
    dependency_two()
    dependency_three()


def caller_one():
    target()


def caller_two():
    target()


def caller_three():
    target()
""",
        encoding="utf-8",
    )
    memory = TechnicalMemory(InMemoryKnowledgeRepository(ProjectIndexer(tmp_path).build()))
    memory.load()

    impact = TechnicalReasoner(memory).impact_analysis("target")

    assert impact is not None
    assert impact["risk"] == "high"


def test_locate_feature_searches_symbols_case_insensitively(tmp_path) -> None:
    reasoner = _build_reasoner(tmp_path)

    symbols = reasoner.locate_feature("SERVICE")

    assert {node.title for node in symbols} == {"app.service", "FeatureService"}
    assert reasoner.locate_feature("missing") == []


def _build_reasoner(tmp_path) -> TechnicalReasoner:
    (tmp_path / "app").mkdir()
    (tmp_path / "app" / "__init__.py").write_text("", encoding="utf-8")
    (tmp_path / "app" / "models.py").write_text(
        """
class Base:
    pass


class Feature(Base):
    pass
""",
        encoding="utf-8",
    )
    (tmp_path / "app" / "service.py").write_text(
        """
from app.models import Feature


def helper():
    pass


def build():
    return helper()


class FeatureService:
    feature: Feature

    def run(self):
        return helper()
""",
        encoding="utf-8",
    )
    memory = TechnicalMemory(InMemoryKnowledgeRepository(ProjectIndexer(tmp_path).build()))
    memory.load()
    return TechnicalReasoner(memory)
