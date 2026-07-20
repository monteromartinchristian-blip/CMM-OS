"""Strategies for converting goals into execution plans."""

from __future__ import annotations

import json
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from kernel.planner.execution_plan import ExecutionPlan
from kernel.planner.exceptions import PlannerError
from kernel.planner.llm_provider import LLMProvider
from kernel.planner.operation_catalog import OperationCatalog
from kernel.planner.operations import Operation, registered_operation_classes
from kernel.planner.planner_response_parser import parse as parse_planner_response


class PlannerStrategy(ABC):
    """Abstract strategy for goal-to-plan conversion."""

    @abstractmethod
    def plan(self, goal: str, catalog: OperationCatalog) -> ExecutionPlan:
        """Convert a goal and catalog into an execution plan."""


@dataclass(slots=True)
class RuleBasedPlannerStrategy(PlannerStrategy):
    """Deterministic planner strategy based on simple heuristics."""

    _operations_by_name: dict[str, type[Operation]] = field(init=False, repr=False, compare=False, default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "_operations_by_name",
            {
                operation.operation_metadata().name: operation
                for operation in registered_operation_classes()
            },
        )

    def plan(self, goal: str, catalog: OperationCatalog) -> ExecutionPlan:
        """Create a deterministic execution plan for a natural-language goal."""

        if not isinstance(goal, str) or not goal.strip():
            raise PlannerError("Goal must be a non-empty string.")

        normalized_goal = goal.strip()
        lowered_goal = normalized_goal.lower()

        if self._supports(catalog, "create_class") and self._looks_like_create_class(lowered_goal):
            return self._plan_create_class(normalized_goal)

        if self._supports(catalog, "replace_method") and self._looks_like_replace_method(lowered_goal):
            return self._plan_replace_method(normalized_goal)

        if self._supports(catalog, "insert_method") and self._looks_like_insert_method(lowered_goal):
            return self._plan_insert_method(normalized_goal)

        if self._supports(catalog, "ensure_import") and self._looks_like_ensure_import(lowered_goal):
            return self._plan_ensure_import(normalized_goal)

        raise PlannerError(f"Unable to interpret goal: {goal}")

    def _supports(self, catalog: OperationCatalog, operation_name: str) -> bool:
        """Return whether the catalog exposes a given operation name."""

        return catalog.get(operation_name) is not None

    def _create_operation(self, operation_name: str, **kwargs: object) -> Operation:
        """Instantiate an operation using its metadata-driven schema."""

        operation_cls = self._operations_by_name.get(operation_name)
        if operation_cls is None:
            raise PlannerError(f"Unsupported operation: {operation_name}")

        schema = operation_cls.schema()
        expected_parameters = {parameter["name"] for parameter in schema["parameters"]}
        missing_parameters = expected_parameters - set(kwargs)
        if missing_parameters:
            missing = ", ".join(sorted(missing_parameters))
            raise PlannerError(f"Missing parameters for {operation_name}: {missing}")

        return operation_cls(**kwargs)

    def _plan_create_class(self, goal: str) -> ExecutionPlan:
        class_name = self._extract_class_name(goal)
        plan = ExecutionPlan()
        plan.add(self._create_operation("create_class", class_name=class_name, module=None))

        if self._has_composite_method_hint(goal):
            method_name = self._extract_method_name(goal)
            plan.add(
                self._create_operation(
                    "insert_method",
                    target_class=class_name,
                    method_name=method_name,
                    source_code=f"def {method_name}(self):\n    pass",
                )
            )

        return plan

    def _plan_insert_method(self, goal: str) -> ExecutionPlan:
        class_name = self._extract_class_name(goal)
        method_name = self._extract_method_name(goal)

        return self._build_single_operation_plan(
            "insert_method",
            target_class=class_name,
            method_name=method_name,
            source_code=f"def {method_name}(self):\n    pass",
        )

    def _plan_replace_method(self, goal: str) -> ExecutionPlan:
        class_name = self._extract_class_name(goal)
        method_name = self._extract_method_name(goal)

        return self._build_single_operation_plan(
            "replace_method",
            target_class=class_name,
            method_name=method_name,
            source_code=f"def {method_name}(self):\n    pass",
        )

    def _plan_ensure_import(self, goal: str) -> ExecutionPlan:
        module = self._extract_module_name(goal)

        return self._build_single_operation_plan(
            "ensure_import",
            module=module,
            name=None,
        )

    def _build_single_operation_plan(self, operation_name: str, **kwargs: object) -> ExecutionPlan:
        plan = ExecutionPlan()
        plan.add(self._create_operation(operation_name, **kwargs))
        return plan

    @staticmethod
    def _looks_like_create_class(goal: str) -> bool:
        return bool(re.search(r"\b(create|crea|crear)\b.*\b(class|clase)\b", goal))

    @staticmethod
    def _looks_like_insert_method(goal: str) -> bool:
        return bool(re.search(r"\b(insert|add|añade|agrega)\b.*\b(method|m[eé]todo)\b", goal))

    @staticmethod
    def _looks_like_replace_method(goal: str) -> bool:
        return bool(re.search(r"\b(replace|reemplaza)\b.*\b(method|m[eé]todo)\b", goal))

    @staticmethod
    def _looks_like_ensure_import(goal: str) -> bool:
        return bool(re.search(r"\b(ensure|asegura)\b.*\bimport\b", goal))

    @staticmethod
    def _has_composite_method_hint(goal: str) -> bool:
        return bool(re.search(r"\b(with|con)\b.*\b(method|m[eé]todo)\b", goal))

    @staticmethod
    def _extract_class_name(goal: str) -> str:
        match = re.search(r"\b(?:class|clase|to)\s+([A-Za-z_][A-Za-z0-9_]*)\b", goal)
        if match:
            return match.group(1)

        fallback = re.search(r"\b([A-Z][A-Za-z0-9_]*)\b", goal)
        if fallback:
            return fallback.group(1)

        raise PlannerError(f"Unable to determine class name from goal: {goal}")

    @staticmethod
    def _extract_method_name(goal: str) -> str:
        match = re.search(r"\b(?:method|m[eé]todo)\s+([A-Za-z_][A-Za-z0-9_]*)\b", goal)
        if match:
            return match.group(1)

        fallback = re.search(r"\b([a-z_][A-Za-z0-9_]*)\s*(?:\(|$)", goal)
        if fallback:
            return fallback.group(1)

        raise PlannerError(f"Unable to determine method name from goal: {goal}")

    @staticmethod
    def _extract_module_name(goal: str) -> str:
        match = re.search(r"\bimport\s+([A-Za-z_][A-Za-z0-9_.]*)\b", goal)
        if match:
            return match.group(1)

        fallback = re.search(r"\b(?:module|modulo)\s+([A-Za-z_][A-Za-z0-9_.]*)\b", goal)
        if fallback:
            return fallback.group(1)

        raise PlannerError(f"Unable to determine import module from goal: {goal}")


@dataclass(slots=True)
class LLMPlannerStrategy(PlannerStrategy):
    """LLM-backed planner strategy using a plain-text interchange format."""

    provider: LLMProvider

    def plan(self, goal: str, catalog: OperationCatalog) -> ExecutionPlan:
        if not isinstance(goal, str) or not goal.strip():
            raise PlannerError("Goal must be a non-empty string.")

        prompt = self._build_prompt(goal.strip(), catalog)
        response = self.provider.complete(prompt)
        return parse_planner_response(response, catalog)

    @staticmethod
    def _build_prompt(goal: str, catalog: OperationCatalog) -> str:
        catalog_json = json.dumps(catalog.to_dict(), ensure_ascii=False, sort_keys=True)
        return (
            "You are an operation planner.\n"
            f"Goal: {goal}\n"
            f"Available operations: {catalog_json}\n"
            "Respond using blocks in this format:\n"
            "OPERATION <operation_type>\n"
            "CLASS <class_name>\n"
            "METHOD <method_name>\n"
            "MODULE <module_name>\n"
            "NAME <import_name>\n"
            "SOURCE_CODE <source_code>"
        )
