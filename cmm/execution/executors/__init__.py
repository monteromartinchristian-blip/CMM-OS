"""Action executor contracts for CMM OS."""

from cmm.execution.executors.base import (
    ActionExecutor,
    ExecutionContext,
    ExecutionResult,
    NoOpExecutor,
)

__all__ = [
    "ActionExecutor",
    "CompositeExecutor",
    "ExecutionContext",
    "ExecutionResult",
    "NoOpExecutor",
    "ReadOnlyFilesystemExecutor",
    "PythonExecutor",
    "GitExecutor",
]


def __getattr__(name: str):
    if name == "CompositeExecutor":
        from cmm.execution.executors.composite_executor import CompositeExecutor

        return CompositeExecutor
    if name == "ReadOnlyFilesystemExecutor":
        from cmm.execution.executors.read_only_filesystem import ReadOnlyFilesystemExecutor

        return ReadOnlyFilesystemExecutor
    if name == "PythonExecutor":
        from cmm.execution.executors.python_executor import PythonExecutor

        return PythonExecutor
    if name == "GitExecutor":
        from cmm.execution.executors.git_executor import GitExecutor

        return GitExecutor
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
