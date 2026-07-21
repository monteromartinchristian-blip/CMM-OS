from __future__ import annotations

from dataclasses import FrozenInstanceError
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

from cmm.execution.python import (
    PythonProjectParser,
    PythonProjectSnapshot,
    PythonValidateProjectExecutor,
    SemanticContext,
    SemanticContextBuilder,
)
from cmm.transformations import ExecutionRequest, ValidateProjectOperation


def _snapshot() -> PythonProjectSnapshot:
    with TemporaryDirectory() as directory:
        project_root = Path(directory)
        (project_root / "module.py").write_text("value = 1\n", encoding="utf-8")
        return PythonProjectParser().parse(project_root)


def test_semantic_context_is_immutable() -> None:
    context = SemanticContextBuilder().build(_snapshot())

    with pytest.raises(FrozenInstanceError):
        context.snapshot = _snapshot()
    with pytest.raises(TypeError):
        context.cache["key"] = "value"


def test_builder_wraps_snapshot_without_analysis() -> None:
    snapshot = _snapshot()

    context = SemanticContextBuilder().build(snapshot)

    assert isinstance(context, SemanticContext)
    assert context.snapshot is snapshot
    assert context.symbol_index is None
    assert context.reference_index is None
    assert context.import_graph is None
    assert context.type_index is None


def test_validate_executor_returns_semantic_context_and_snapshot() -> None:
    with TemporaryDirectory() as directory:
        project_root = Path(directory)
        (project_root / "module.py").write_text("value = 1\n", encoding="utf-8")
        request = ExecutionRequest(
            operation=ValidateProjectOperation(scope="project"),
            metadata={"project_root": str(project_root)},
        )

        result = PythonValidateProjectExecutor().execute(request)

        context = result.metadata["semantic_context"]
        assert isinstance(context, SemanticContext)
        assert result.metadata["snapshot"] is context.snapshot
