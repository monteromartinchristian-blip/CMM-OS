from __future__ import annotations

from cmm.memory import KnowledgeGraph, ProjectIndexer, TechnicalMemory, TechnicalReasoner
from cmm.planner import ExecutionPlan, PlanStep, TaskPlanner


class InMemoryKnowledgeRepository:
    """Repository double that supplies a prebuilt technical graph."""

    def __init__(self, graph: KnowledgeGraph) -> None:
        self._graph = graph

    def load(self) -> KnowledgeGraph:
        """Return the configured graph."""
        return self._graph

    def save(self, graph: KnowledgeGraph) -> None:
        """Replace the configured graph."""
        self._graph = graph


def test_create_plan_returns_ordered_structured_steps(tmp_path) -> None:
    planner = _build_planner(tmp_path)

    plan = planner.create_plan("Modificar AuthenticationService")

    assert isinstance(plan, ExecutionPlan)
    assert plan.goal == "Modificar AuthenticationService"
    assert plan.summary == "Plan work for: Modificar AuthenticationService"
    assert plan.estimated_complexity == "MEDIUM"
    assert [symbol.title for symbol in plan.entry_points] == ["AuthenticationService"]
    assert {symbol.title for symbol in plan.impacted_components} == {"Controller", "Session"}
    assert all(isinstance(step, PlanStep) for step in plan.steps)
    assert [step.order for step in plan.steps] == [1, 2, 3, 4, 5, 6]
    assert plan.steps[0].title == "Analyze entry points"


def test_estimate_complexity_uses_reasoner_impact(tmp_path) -> None:
    planner = _build_planner(tmp_path)

    assert planner.estimate_complexity("AuthenticationService") == "MEDIUM"
    assert planner.estimate_complexity("missing") == "LOW"


def test_estimate_complexity_detects_many_direct_dependents(tmp_path) -> None:
    (tmp_path / "sample.py").write_text(
        """
class AuthenticationService:
    pass


class ConsumerOne:
    service: AuthenticationService


class ConsumerTwo:
    service: AuthenticationService


class ConsumerThree:
    service: AuthenticationService


class ConsumerFour:
    service: AuthenticationService


class ConsumerFive:
    service: AuthenticationService
""",
        encoding="utf-8",
    )
    memory = TechnicalMemory(InMemoryKnowledgeRepository(ProjectIndexer(tmp_path).build()))
    memory.load()
    planner = TaskPlanner(TechnicalReasoner(memory))

    assert planner.estimate_complexity("AuthenticationService") == "HIGH"


def test_identify_entry_points_prefers_exact_symbol_matches(tmp_path) -> None:
    planner = _build_planner(tmp_path)

    entry_points = planner.identify_entry_points("Update AuthenticationService")

    assert [symbol.title for symbol in entry_points] == ["AuthenticationService"]


def test_identify_impacted_components_returns_unique_dependents_and_callees(tmp_path) -> None:
    planner = _build_planner(tmp_path)

    components = planner.identify_impacted_components("AuthenticationService")

    assert {symbol.title for symbol in components} == {"Controller", "Session"}
    assert planner.identify_impacted_components("missing") == []


def _build_planner(tmp_path) -> TaskPlanner:
    (tmp_path / "app").mkdir()
    (tmp_path / "app" / "__init__.py").write_text("", encoding="utf-8")
    (tmp_path / "app" / "auth.py").write_text(
        """
class Session:
    pass


class AuthenticationService:
    session: Session

    def authenticate(self):
        return self.session


class Controller:
    service: AuthenticationService
""",
        encoding="utf-8",
    )
    memory = TechnicalMemory(InMemoryKnowledgeRepository(ProjectIndexer(tmp_path).build()))
    memory.load()
    return TaskPlanner(TechnicalReasoner(memory))
