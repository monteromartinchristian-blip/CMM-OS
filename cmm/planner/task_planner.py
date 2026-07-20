"""Deterministic task planning built on technical reasoning."""

from __future__ import annotations

import re
from dataclasses import dataclass

from cmm.memory.technical_reasoner import TechnicalReasoner


@dataclass(frozen=True)
class PlanStep:
    """One ordered, deterministic action in an engineering plan."""

    order: int
    title: str
    description: str
    rationale: str


@dataclass(frozen=True)
class ExecutionPlan:
    """Structured deterministic plan for an engineering goal."""

    goal: str
    summary: str
    estimated_complexity: str
    entry_points: list[object]
    impacted_components: list[object]
    steps: list[PlanStep]


class TaskPlanner:
    """Transform engineering goals into plans using only technical reasoning."""

    def __init__(self, reasoner: TechnicalReasoner) -> None:
        """Initialize the planner with the public technical reasoning facade."""
        self._reasoner = reasoner

    def create_plan(self, goal: str) -> ExecutionPlan:
        """Create a deterministic engineering plan for ``goal``."""
        entry_points = self.identify_entry_points(goal)
        impacted_components = self.identify_impacted_components(goal)
        complexity = self.estimate_complexity(goal)

        return ExecutionPlan(
            goal=goal,
            summary=f"Plan work for: {goal}",
            estimated_complexity=complexity,
            entry_points=entry_points,
            impacted_components=impacted_components,
            steps=[
                PlanStep(
                    order=1,
                    title="Analyze entry points",
                    description="Review the symbols identified from the goal.",
                    rationale="Establishes the scope of the requested change.",
                ),
                PlanStep(
                    order=2,
                    title="Identify dependencies",
                    description="Review direct usage, import, and inheritance relationships.",
                    rationale="Dependencies can require coordinated changes.",
                ),
                PlanStep(
                    order=3,
                    title="Review call graph",
                    description="Inspect direct callers and callees of each entry point.",
                    rationale="Call paths reveal behavior affected by the change.",
                ),
                PlanStep(
                    order=4,
                    title="Evaluate impacted components",
                    description="Review direct dependents and related components.",
                    rationale="Dependents are the most likely integration points.",
                ),
                PlanStep(
                    order=5,
                    title="Estimate risk",
                    description=f"Treat the change as {complexity} complexity.",
                    rationale="The estimate prioritizes validation effort.",
                ),
                PlanStep(
                    order=6,
                    title="Prepare modifications",
                    description="Implement the scoped change and update affected components.",
                    rationale="The preceding analysis provides a bounded implementation scope.",
                ),
            ],
        )

    def estimate_complexity(self, goal: str) -> str:
        """Estimate goal complexity as ``LOW``, ``MEDIUM``, or ``HIGH``."""
        impacts = self._impacts_for(goal)
        impacted_count = len(self.identify_impacted_components(goal))

        if any(impact["risk"] == "high" for impact in impacts) or impacted_count >= 5:
            return "HIGH"
        if (
            any(impact["risk"] == "medium" for impact in impacts)
            or impacted_count >= 2
        ):
            return "MEDIUM"
        return "LOW"

    def identify_entry_points(self, goal: str) -> list[object]:
        """Return symbols whose names best match the engineering goal."""
        candidates = [goal, *self._goal_keywords(goal)]

        for candidate in candidates:
            matches = self._reasoner.locate_feature(candidate)
            exact_matches = [
                symbol
                for symbol in matches
                if getattr(symbol, "title").lower() == candidate.lower()
            ]
            if exact_matches:
                return self._unique_symbols(exact_matches)

        matches = []
        for candidate in self._goal_keywords(goal):
            matches.extend(self._reasoner.locate_feature(candidate))

        return self._unique_symbols(matches)

    def identify_impacted_components(self, goal: str) -> list[object]:
        """Return direct dependents and call neighbors of matching entry points."""
        components = []

        for symbol in self.identify_entry_points(goal):
            impact = self._reasoner.impact_analysis(getattr(symbol, "title"))
            if impact is None:
                continue

            components.extend(impact["direct_dependents"])
            components.extend(impact["callers"])
            components.extend(impact["callees"])
            dependencies = self._reasoner.explain_dependencies(getattr(symbol, "title"))
            if dependencies is not None:
                components.extend(dependencies["uses"])
                components.extend(dependencies["imports"])
                components.extend(dependencies["inherits_from"])

        return self._unique_symbols(components)

    def _impacts_for(self, goal: str) -> list[dict[str, object]]:
        impacts = []
        for symbol in self.identify_entry_points(goal):
            impact = self._reasoner.impact_analysis(getattr(symbol, "title"))
            if impact is not None:
                impacts.append(impact)
        return impacts

    def _goal_keywords(self, goal: str) -> list[str]:
        ignored_words = {
            "add",
            "analyze",
            "change",
            "create",
            "delete",
            "feature",
            "implement",
            "modify",
            "remove",
            "update",
            "actualizar",
            "agregar",
            "analizar",
            "crear",
            "eliminar",
            "implementar",
            "modificar",
        }
        return [
            word
            for word in re.findall(r"[A-Za-z_][A-Za-z0-9_]*", goal)
            if word.lower() not in ignored_words
        ]

    def _unique_symbols(self, symbols: list[object]) -> list[object]:
        seen_identifiers = set()
        unique_symbols = []

        for symbol in symbols:
            identifier = getattr(symbol, "identifier")
            if identifier in seen_identifiers:
                continue

            seen_identifiers.add(identifier)
            unique_symbols.append(symbol)

        return unique_symbols
