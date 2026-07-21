"""Build deterministic, non-executing action queues from engineering plans."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from types import MappingProxyType
from typing import Mapping

from cmm.planner.task_planner import ExecutionPlan, TaskPlanner


class ActionType(str, Enum):
    """Supported atomic technical-analysis and preparation actions."""

    READ_MODULE = "READ_MODULE"
    READ_CLASS = "READ_CLASS"
    READ_FUNCTION = "READ_FUNCTION"
    READ_METHOD = "READ_METHOD"
    ANALYZE_DEPENDENCIES = "ANALYZE_DEPENDENCIES"
    ANALYZE_CALLERS = "ANALYZE_CALLERS"
    ANALYZE_CALLEES = "ANALYZE_CALLEES"
    ANALYZE_IMPACT = "ANALYZE_IMPACT"
    PREPARE_MODIFICATION = "PREPARE_MODIFICATION"
    FILESYSTEM_EXISTS = "filesystem.exists"
    FILESYSTEM_IS_FILE = "filesystem.is_file"
    FILESYSTEM_IS_DIRECTORY = "filesystem.is_directory"
    FILESYSTEM_READ_FILE = "filesystem.read_file"
    FILESYSTEM_LIST_DIRECTORY = "filesystem.list_directory"
    FILESYSTEM_CREATE_FILE = "filesystem.create_file"
    FILESYSTEM_WRITE_FILE = "filesystem.write_file"
    FILESYSTEM_APPEND_FILE = "filesystem.append_file"
    FILESYSTEM_DELETE_FILE = "filesystem.delete_file"
    FILESYSTEM_MOVE_FILE = "filesystem.move_file"
    FILESYSTEM_CREATE_DIRECTORY = "filesystem.create_directory"
    FILESYSTEM_DELETE_DIRECTORY = "filesystem.delete_directory"
    PYTHON_LIST_CLASSES = "python.list_classes"
    PYTHON_LIST_FUNCTIONS = "python.list_functions"
    PYTHON_LIST_METHODS = "python.list_methods"
    PYTHON_LIST_IMPORTS = "python.list_imports"
    PYTHON_DESCRIBE_MODULE = "python.describe_module"
    PYTHON_FIND_SYMBOL = "python.find_symbol"
    PYTHON_INSERT_METHOD = "python.insert_method"
    PYTHON_REPLACE_METHOD = "python.replace_method"
    PYTHON_DELETE_METHOD = "python.delete_method"
    PYTHON_RENAME_METHOD = "python.rename_method"
    PYTHON_ADD_IMPORT = "python.add_import"
    PYTHON_REMOVE_IMPORT = "python.remove_import"
    PYTHON_CREATE_CLASS = "python.create_class"
    PYTHON_RENAME_CLASS = "python.rename_class"
    PYTHON_DELETE_CLASS = "python.delete_class"
    GIT_STATUS = "git.status"
    GIT_CURRENT_BRANCH = "git.current_branch"
    GIT_LIST_BRANCHES = "git.list_branches"
    GIT_LOG = "git.log"
    GIT_DIFF = "git.diff"
    GIT_SHOW = "git.show"
    GIT_LIST_TAGS = "git.list_tags"
    GIT_CREATE_BRANCH = "git.create_branch"
    GIT_SWITCH_BRANCH = "git.switch_branch"
    GIT_RESTORE_WORKTREE = "git.restore_worktree"
    GIT_LIST_CHANGED_FILES = "git.list_changed_files"


@dataclass(frozen=True)
class Action:
    """One immutable, non-executing action in an action queue."""

    id: str
    order: int
    action_type: ActionType
    target: str
    description: str
    metadata: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Prevent mutation through the action metadata mapping."""
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))


class ActionPlanner:
    """Transform execution plans into deterministic atomic action queues."""

    def __init__(self, planner: TaskPlanner) -> None:
        """Initialize the action planner with the public task-planning facade."""
        self._planner = planner

    def create_actions(self, plan: ExecutionPlan) -> list[Action]:
        """Create an ordered, non-executing action queue for ``plan``."""
        actions = []
        targets = self._targets(plan)

        for step in plan.steps:
            if "entry point" in step.title.lower():
                for symbol in plan.entry_points:
                    target = getattr(symbol, "title", "")
                    if not isinstance(target, str) or not target.strip():
                        continue

                    actions.append(
                        Action(
                            id=f"action-{len(actions) + 1}",
                            order=len(actions) + 1,
                            action_type=self._read_action_type(symbol),
                            target=target,
                            description=step.description,
                            metadata={
                                "goal": plan.goal,
                                "plan_step_order": step.order,
                            },
                        )
                    )
                continue

            for action_type in self._action_types_for_step(step.title):
                for target in targets:
                    actions.append(
                        Action(
                            id=f"action-{len(actions) + 1}",
                            order=len(actions) + 1,
                            action_type=action_type,
                            target=target,
                            description=step.description,
                            metadata={
                                "goal": plan.goal,
                                "plan_step_order": step.order,
                            },
                        )
                    )

        return actions

    def create_operation_actions(self, operations: list[object]) -> list[Action]:
        """Convert structured provider operations into ordered executable actions."""
        actions: list[Action] = []
        for operation in operations:
            domain = getattr(operation, "domain", "")
            operation_type = getattr(operation, "operation_type", "")
            parameters = dict(getattr(operation, "parameters", {}) or {})
            qualified = f"{domain}.{operation_type}"
            try:
                action_type = ActionType(qualified)
            except ValueError as error:
                raise ValueError(f"Unsupported operation action: {qualified}") from error
            target = str(parameters.get("path", "."))
            actions.append(
                Action(
                    id=f"action-{len(actions) + 1}",
                    order=len(actions) + 1,
                    action_type=action_type,
                    target=target,
                    description=getattr(operation, "reason", "") or qualified,
                    metadata=parameters,
                )
            )
        return actions

    def optimize(self, actions: list[Action]) -> list[Action]:
        """Remove duplicate actions while preserving first occurrence and meaning."""
        unique_actions = []
        seen_actions = set()

        for action in actions:
            key = (action.action_type, action.target)
            if key in seen_actions:
                continue

            seen_actions.add(key)
            unique_actions.append(action)

        return [
            Action(
                id=f"action-{order}",
                order=order,
                action_type=action.action_type,
                target=action.target,
                description=action.description,
                metadata=action.metadata,
            )
            for order, action in enumerate(unique_actions, start=1)
        ]

    def validate(self, actions: list[Action]) -> dict[str, object]:
        """Validate action identity, ordering, targets, and action types."""
        errors = []
        identifiers = set()

        for expected_order, action in enumerate(actions, start=1):
            if not isinstance(action, Action):
                errors.append(f"Action at position {expected_order} is invalid.")
                continue

            if not isinstance(action.id, str) or not action.id:
                errors.append(f"Action at position {expected_order} has an invalid id.")
            elif action.id in identifiers:
                errors.append(f"Duplicate action id: {action.id}.")
            else:
                identifiers.add(action.id)

            if action.order != expected_order:
                errors.append(
                    f"Action {action.id} has order {action.order}; expected {expected_order}."
                )
            if not isinstance(action.target, str) or not action.target.strip():
                errors.append(f"Action {action.id} has an invalid target.")
            if not isinstance(action.action_type, ActionType):
                errors.append(f"Action {action.id} has an invalid action type.")

        return {"valid": not errors, "errors": errors}

    def _targets(self, plan: ExecutionPlan) -> list[str]:
        return [
            title
            for title in (getattr(symbol, "title", "") for symbol in plan.entry_points)
            if isinstance(title, str) and title.strip()
        ]

    def _action_types_for_step(self, title: str) -> list[ActionType]:
        normalized_title = title.lower()

        if "dependenc" in normalized_title:
            return [ActionType.ANALYZE_DEPENDENCIES]
        if "call graph" in normalized_title:
            return [ActionType.ANALYZE_CALLERS, ActionType.ANALYZE_CALLEES]
        if "impact" in normalized_title or "risk" in normalized_title:
            return [ActionType.ANALYZE_IMPACT]
        if "prepare" in normalized_title or "modif" in normalized_title:
            return [ActionType.PREPARE_MODIFICATION]

        return []

    def _read_action_type(self, symbol: object) -> ActionType:
        kind = getattr(symbol, "kind", "")
        action_types = {
            "Module": ActionType.READ_MODULE,
            "Class": ActionType.READ_CLASS,
            "Function": ActionType.READ_FUNCTION,
            "Method": ActionType.READ_METHOD,
        }
        return action_types.get(kind, ActionType.READ_MODULE)
