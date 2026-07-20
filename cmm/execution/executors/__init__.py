"""Action executor contracts for CMM OS."""

from cmm.execution.executors.base import (
    ActionExecutor,
    ExecutionContext,
    ExecutionResult,
    NoOpExecutor,
)

__all__ = [
    "ActionExecutor",
    "ExecutionContext",
    "ExecutionResult",
    "NoOpExecutor",
    "ReadOnlyFilesystemExecutor",
]


def __getattr__(name: str):
    if name == "ReadOnlyFilesystemExecutor":
        from cmm.execution.executors.read_only_filesystem import ReadOnlyFilesystemExecutor

        return ReadOnlyFilesystemExecutor
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
