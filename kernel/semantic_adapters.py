"""Adapters between legacy CMM models and semantic kernel contracts."""

from __future__ import annotations

from typing import Any

from kernel.actions.filesystem import (
    CreateDirectoryAction,
    InsertAfterAction,
    InsertBeforeAction,
    InsertMethodAction,
    ReplaceMethodAction,
    DeleteMethodAction,
    RenameMethodAction,
    AddImportAction,
    RemoveImportAction,
    CreateClassAction,
    RenameClassAction,
    DeleteClassAction,
    ReadFileAction,
    ReplaceBlockAction,
    WriteFileAction,
)
from kernel.semantic import SemanticOperation


def operation_from_legacy_action(action: object) -> SemanticOperation:
    """Adapt legacy protocol actions into semantic operations."""

    metadata = {"legacy_action": action}
    if isinstance(action, WriteFileAction):
        return SemanticOperation("write_file", "filesystem", {"path": action.path, "content": action.content}, metadata)
    if isinstance(action, ReadFileAction):
        return SemanticOperation("read_file", "filesystem", {"path": action.path}, metadata)
    if isinstance(action, CreateDirectoryAction):
        return SemanticOperation("create_directory", "filesystem", {"path": action.path}, metadata)
    if isinstance(action, ReplaceBlockAction):
        return SemanticOperation("replace_block", "diff", {"path": action.path, "old": action.old, "new": action.new}, metadata)
    if isinstance(action, InsertAfterAction):
        return SemanticOperation("insert_after", "diff", {"path": action.path, "anchor": action.anchor, "content": action.content}, metadata)
    if isinstance(action, InsertBeforeAction):
        return SemanticOperation("insert_before", "diff", {"path": action.path, "anchor": action.anchor, "content": action.content}, metadata)
    if isinstance(action, InsertMethodAction):
        return SemanticOperation(
            "insert_method",
            "python",
            {
                "path": action.path,
                "class_name": action.class_name,
                "position": action.position,
                "code": action.code,
                "scope": action.scope,
            },
            metadata,
        )
    if isinstance(action, ReplaceMethodAction):
        return SemanticOperation(
            "replace_method",
            "python",
            {
                "path": action.path,
                "class_name": action.class_name,
                "method_name": action.method_name,
                "code": action.code,
                "scope": action.scope,
            },
            metadata,
        )
    if isinstance(action, DeleteMethodAction):
        return SemanticOperation(
            "delete_method",
            "python",
            {
                "path": action.path,
                "class_name": action.class_name,
                "method_name": action.method_name,
                "scope": action.scope,
            },
            metadata,
        )
    if isinstance(action, RenameMethodAction):
        return SemanticOperation(
            "rename_method",
            "python",
            {
                "path": action.path,
                "class_name": action.class_name,
                "old_name": action.old_name,
                "new_name": action.new_name,
                "scope": action.scope,
            },
            metadata,
        )
    if isinstance(action, AddImportAction):
        return SemanticOperation(
            "add_import",
            "python",
            {
                "path": action.path,
                "module": action.module,
                "name": action.name,
                "alias": action.alias,
                "level": action.level,
            },
            metadata,
        )
    if isinstance(action, RemoveImportAction):
        return SemanticOperation(
            "remove_import",
            "python",
            {
                "path": action.path,
                "module": action.module,
                "name": action.name,
                "alias": action.alias,
                "level": action.level,
            },
            metadata,
        )
    if isinstance(action, CreateClassAction):
        return SemanticOperation(
            "create_class",
            "python",
            {
                "path": action.path,
                "class_name": action.class_name,
                "scope": action.scope,
                "base_classes": action.base_classes,
                "methods": action.methods,
            },
            metadata,
        )
    if isinstance(action, RenameClassAction):
        return SemanticOperation(
            "rename_class",
            "python",
            {
                "path": action.path,
                "class_name": action.class_name,
                "new_name": action.new_name,
                "scope": action.scope,
            },
            metadata,
        )
    if isinstance(action, DeleteClassAction):
        return SemanticOperation(
            "delete_class",
            "python",
            {
                "path": action.path,
                "class_name": action.class_name,
                "scope": action.scope,
            },
            metadata,
        )

    tool = getattr(action, "tool", None)
    name = getattr(action, "action", None)
    if isinstance(tool, str) and isinstance(name, str):
        parameters = {
            key: value
            for key, value in vars(action).items()
            if key not in {"tool", "action"}
        }
        return SemanticOperation(name, tool, parameters, metadata)

    raise TypeError(f"Unsupported legacy action: {type(action).__name__}")


def operation_from_transformation(operation: object) -> SemanticOperation:
    """Adapt a transformation operation to a semantic operation envelope."""

    name = getattr(operation, "name", None)
    metadata = operation.metadata() if callable(getattr(operation, "metadata", None)) else {}
    if not isinstance(name, str) or not name.strip():
        raise TypeError("Transformation operation must expose a non-empty name.")
    if not isinstance(metadata, dict):
        raise TypeError("Transformation operation metadata must be a dictionary.")
    return SemanticOperation(
        operation_type=name,
        domain="transformation",
        parameters=metadata,
        metadata={"transformation_operation": operation},
    )


def legacy_value_from_result(data: dict[str, Any]) -> Any:
    """Return the legacy raw value stored by compatibility executors."""

    return data.get("legacy_result")
