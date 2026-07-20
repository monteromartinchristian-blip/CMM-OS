"""Planning rules for the rule-based planner."""

from __future__ import annotations

import re
from abc import ABC, abstractmethod
from typing import Any

from kernel.planner.execution_plan import ExecutionPlan
from kernel.planner.exceptions import PlannerError
from kernel.planner.operations import (
    CreateClassOperation,
    EnsureImportOperation,
    InsertMethodOperation,
    Operation,
    ReplaceMethodOperation,
)


class PlanningRule(ABC):
    """Abstract rule that transforms an intent into one or more operations."""

    @abstractmethod
    def matches(self, intent: str) -> bool:
        """Return whether the rule applies to the given intent."""

    @abstractmethod
    def build(self, intent: str) -> list[Operation]:
        """Build one or more operations for the given intent."""


class CreateClassRule(PlanningRule):
    """Create a class operation for simple class-creation intents."""

    def matches(self, intent: str) -> bool:
        return bool(re.search(r"\b(crea|crear)\s+(una|una nueva)?\s*clase\s+([A-Za-z_][A-Za-z0-9_]*)\b", intent, re.IGNORECASE))

    def build(self, intent: str) -> list[Operation]:
        match = re.search(r"\b(crea|crear)\s+(una|una nueva)?\s*clase\s+([A-Za-z_][A-Za-z0-9_]*)\b", intent, re.IGNORECASE)
        if not match:
            raise PlannerError("CreateClassRule could not build an operation.")
        return [CreateClassOperation(class_name=match.group(3))]


class InsertMethodRule(PlanningRule):
    """Create an insert-method operation for simple method-addition intents."""

    def matches(self, intent: str) -> bool:
        return bool(re.search(r"\b(a(?:ñ|n)ade|agrega)\s+un\s+m(?:é|e)todo\s+([A-Za-z_][A-Za-z0-9_]*)\s+a\s+([A-Za-z_][A-Za-z0-9_]*)\b", intent, re.IGNORECASE))

    def build(self, intent: str) -> list[Operation]:
        match = re.search(r"\b(a(?:ñ|n)ade|agrega)\s+un\s+m(?:é|e)todo\s+([A-Za-z_][A-Za-z0-9_]*)\s+a\s+([A-Za-z_][A-Za-z0-9_]*)\b", intent, re.IGNORECASE)
        if not match:
            raise PlannerError("InsertMethodRule could not build an operation.")
        return [
            InsertMethodOperation(
                target_class=match.group(3).lower(),
                method_name=match.group(2),
                source_code=f"def {match.group(2)}(self):\n    pass",
            )
        ]


class ReplaceMethodRule(PlanningRule):
    """Create a replace-method operation for simple replacement intents."""

    def matches(self, intent: str) -> bool:
        return bool(re.search(r"\breemplaza(?: el)?\s+m(?:é|e)todo\s+([A-Za-z_][A-Za-z0-9_]*)\s+de\s+([A-Za-z_][A-Za-z0-9_]*)\b", intent, re.IGNORECASE))

    def build(self, intent: str) -> list[Operation]:
        match = re.search(r"\breemplaza(?: el)?\s+m(?:é|e)todo\s+([A-Za-z_][A-Za-z0-9_]*)\s+de\s+([A-Za-z_][A-Za-z0-9_]*)\b", intent, re.IGNORECASE)
        if not match:
            raise PlannerError("ReplaceMethodRule could not build an operation.")
        return [
            ReplaceMethodOperation(
                target_class=match.group(2).lower(),
                method_name=match.group(1),
                source_code=f"def {match.group(1)}(self):\n    pass",
            )
        ]


class EnsureImportRule(PlanningRule):
    """Create an ensure-import operation for import-related intents."""

    def matches(self, intent: str) -> bool:
        return bool(re.search(r"\basegura\s+el\s+import\s+([A-Za-z_][A-Za-z0-9_.]*)\b", intent, re.IGNORECASE))

    def build(self, intent: str) -> list[Operation]:
        match = re.search(r"\basegura\s+el\s+import\s+([A-Za-z_][A-Za-z0-9_.]*)\b", intent, re.IGNORECASE)
        if not match:
            raise PlannerError("EnsureImportRule could not build an operation.")
        return [EnsureImportOperation(module=match.group(1))]


class CompositeCreateClassWithMethodRule(PlanningRule):
    """Build a create-class plus insert-method plan for composite intents."""

    def matches(self, intent: str) -> bool:
        return bool(re.search(r"\bclase\b.*\bm(?:é|e)todo\b|\bcon\s+un\s+m(?:é|e)todo\b", intent, re.IGNORECASE))

    def build(self, intent: str) -> list[Operation]:
        class_match = re.search(r"\bclase\s+([A-Za-z_][A-Za-z0-9_]*)\b", intent, re.IGNORECASE)
        method_match = re.search(r"\bm(?:é|e)todo\s+([A-Za-z_][A-Za-z0-9_]*)\b", intent, re.IGNORECASE)
        if not class_match or not method_match:
            raise PlannerError("CompositeCreateClassWithMethodRule could not build an operation list.")

        return [
            CreateClassOperation(class_name=class_match.group(1)),
            InsertMethodOperation(
                target_class=class_match.group(1).lower(),
                method_name=method_match.group(1),
                source_code=f"def {method_match.group(1)}(self):\n    pass",
            ),
        ]


__all__ = [
    "CompositeCreateClassWithMethodRule",
    "CreateClassRule",
    "EnsureImportRule",
    "InsertMethodRule",
    "PlanningRule",
    "ReplaceMethodRule",
]
