from kernel.actions.filesystem import (
    WriteFileAction,
    ReadFileAction,
    CreateDirectoryAction,
    ReplaceBlockAction,
    InsertAfterAction,
    InsertBeforeAction,
    InsertMethodAction,
)

from kernel.services.diff_engine import DiffEngine
from kernel.services.filesystem import FileSystemService
from kernel.services.python_editor import PythonEditor
from kernel.semantic import SemanticRuntime
from kernel.semantic_adapters import legacy_value_from_result, operation_from_legacy_action
from kernel.semantic_executors import create_default_semantic_registry


class Executor:

    def __init__(self, runtime=None):

        self.fs = FileSystemService()

        self.diff = DiffEngine()

        self.python = PythonEditor()
        self.runtime = runtime or SemanticRuntime(create_default_semantic_registry())

    def execute(self, action):
        """Execute a legacy action through the common semantic runtime."""

        try:
            operation = operation_from_legacy_action(action)
        except TypeError:
            operation = None

        if operation is not None:
            result = self.runtime.execute_operation(operation)
            if result.success:
                return legacy_value_from_result(dict(result.data))
            raise ValueError(result.message)

        if isinstance(action, WriteFileAction):
            self.fs.write(
                action.path,
                action.content,
            )
            return action.path

        if isinstance(action, ReadFileAction):
            return self.fs.read(
                action.path,
            )

        if isinstance(action, CreateDirectoryAction):
            self.fs.mkdir(
                action.path,
            )
            return action.path

        if isinstance(action, ReplaceBlockAction):
            return self.diff.replace_block(
                action.path,
                action.old,
                action.new,
            )

        if isinstance(action, InsertAfterAction):
            return self.diff.insert_after(
                action.path,
                action.anchor,
                action.content,
            )

        if isinstance(action, InsertBeforeAction):
            return self.diff.insert_before(
                action.path,
                action.anchor,
                action.content,
            )

        if isinstance(action, InsertMethodAction):
            return self.python.insert_method(
                action.path,
                action.class_name,
                action.position,
                action.code,
            )

        raise ValueError(
            f"Unsupported action: {type(action).__name__}"
        )
