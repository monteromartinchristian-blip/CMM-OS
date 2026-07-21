from __future__ import annotations

from dataclasses import dataclass

from cmm.execution import (
    CreateFileExecutor,
    DeleteFileExecutor,
    ExecutionPipeline,
    ExecutionResult,
    OperationExecutor,
    OperationExecutorRegistry,
)
from cmm.execution.python import (
    PythonCreateModuleExecutor,
    PythonDeleteSymbolExecutor,
    PythonProjectParser,
    SemanticContextBuilder,
)
from cmm.transformations import (
    CreateFileOperation,
    CreateModuleOperation,
    DeleteFileOperation,
    DeleteSymbolOperation,
    ExecutionPlanner,
    FileExistsPrecondition,
    TransformationOperation,
    TransformationPlan,
    TransformationStep,
    ValidateProjectOperation,
)
from cmm.transformations.execution_request import ExecutionRequest


@dataclass(frozen=True)
class WriteInvalidPythonOperation(TransformationOperation):
    path: str

    @property
    def name(self) -> str:
        return "write_invalid_python"

    def describe(self) -> str:
        return f"Write invalid Python to {self.path}."

    def metadata(self) -> dict[str, object]:
        return {"path": self.path}


class WriteInvalidPythonExecutor(OperationExecutor):
    @property
    def operation_type(self) -> type[TransformationOperation]:
        return WriteInvalidPythonOperation

    def execute(self, request: ExecutionRequest) -> ExecutionResult:
        context = request.metadata["execution_context"]
        path = context.resolve_project_path(request.operation.path)
        path.write_text("def broken(:\n", encoding="utf-8")
        return ExecutionResult(success=True, operation=request.operation, created_paths=(path,))


def _registry() -> OperationExecutorRegistry:
    registry = OperationExecutorRegistry()
    registry.register_many(
        [
            CreateFileExecutor(),
            DeleteFileExecutor(),
            PythonCreateModuleExecutor(),
            PythonDeleteSymbolExecutor(),
            WriteInvalidPythonExecutor(),
        ]
    )
    return registry


def _pipeline(tmp_path) -> ExecutionPipeline:
    snapshot = PythonProjectParser().parse(tmp_path)
    context = SemanticContextBuilder().build(snapshot, build_reference_index=True)
    return ExecutionPipeline(_registry(), context, tmp_path)


def _execute(tmp_path, plan: TransformationPlan):
    execution_plan = ExecutionPlanner().build(plan)
    return _pipeline(tmp_path).execute(execution_plan)


def test_precondition_failure_stops_before_mutation(tmp_path) -> None:
    result = _execute(
        tmp_path,
        TransformationPlan(
            id="precondition-failure",
            steps=(
                TransformationStep(
                    id="create",
                    operation=CreateFileOperation("created.py"),
                    preconditions=(FileExistsPrecondition("missing.py"),),
                ),
            ),
        ),
    )

    assert not result.success
    assert result.error.code == "precondition_failed"
    assert result.executed_steps == ()
    assert not (tmp_path / "created.py").exists()


def test_path_traversal_operation_is_rejected_before_mutation(tmp_path) -> None:
    result = _execute(
        tmp_path,
        TransformationPlan(
            id="path-traversal",
            steps=(
                TransformationStep(
                    id="create",
                    operation=CreateFileOperation("../outside.py"),
                ),
            ),
        ),
    )

    assert not result.success
    assert result.error.code == "path_error"
    assert not (tmp_path.parent / "outside.py").exists()


def test_execution_is_sequential_and_stops_on_first_failure(tmp_path) -> None:
    (tmp_path / "existing.py").write_text("value = 1\n", encoding="utf-8")
    result = _execute(
        tmp_path,
        TransformationPlan(
            id="stop-on-failure",
            steps=(
                TransformationStep("first", CreateFileOperation("first.py")),
                TransformationStep("fail", CreateFileOperation("existing.py"), ("first",)),
                TransformationStep("never", CreateFileOperation("never.py"), ("fail",)),
            ),
        ),
    )

    assert not result.success
    assert result.executed_steps == ("first", "fail")
    assert result.failed_step == "fail"
    assert [item.step_id for item in result.operation_results] == ["first", "fail"]
    assert not (tmp_path / "first.py").exists()
    assert not (tmp_path / "never.py").exists()


def test_rollback_restores_modified_file(tmp_path) -> None:
    module = tmp_path / "sample.py"
    original = b"def keep():\n    return 1\n\ndef remove_me():\n    return 2\n"
    module.write_bytes(original)
    (tmp_path / "existing.py").write_text("value = 1\n", encoding="utf-8")

    result = _execute(
        tmp_path,
        TransformationPlan(
            id="rollback-modified",
            steps=(
                TransformationStep("delete-symbol", DeleteSymbolOperation("remove_me", "sample")),
                TransformationStep(
                    "fail",
                    CreateFileOperation("existing.py"),
                    ("delete-symbol",),
                ),
            ),
        ),
    )

    assert not result.success
    assert result.rollback_attempted
    assert result.rollback_applied
    assert module.read_bytes() == original
    assert module in result.rollback_restored_paths
    assert module in result.modified_paths


def test_rollback_removes_created_file(tmp_path) -> None:
    (tmp_path / "existing.py").write_text("value = 1\n", encoding="utf-8")

    result = _execute(
        tmp_path,
        TransformationPlan(
            id="rollback-created",
            steps=(
                TransformationStep("create", CreateFileOperation("created.py")),
                TransformationStep("fail", CreateFileOperation("existing.py"), ("create",)),
            ),
        ),
    )

    assert not result.success
    assert not (tmp_path / "created.py").exists()
    assert tmp_path / "created.py" in result.rollback_restored_paths
    assert tmp_path / "created.py" in result.created_paths


def test_rollback_restores_deleted_file(tmp_path) -> None:
    target = tmp_path / "delete_me.py"
    original = b"value = 1\n"
    target.write_bytes(original)
    (tmp_path / "existing.py").write_text("value = 1\n", encoding="utf-8")

    result = _execute(
        tmp_path,
        TransformationPlan(
            id="rollback-deleted",
            steps=(
                TransformationStep("delete", DeleteFileOperation("delete_me.py")),
                TransformationStep("fail", CreateFileOperation("existing.py"), ("delete",)),
            ),
        ),
    )

    assert not result.success
    assert target.read_bytes() == original
    assert target in result.rollback_restored_paths
    assert target in result.deleted_paths


def test_final_validation_failure_triggers_rollback(tmp_path) -> None:
    target = tmp_path / "broken.py"

    result = _execute(
        tmp_path,
        TransformationPlan(
            id="final-validation",
            steps=(TransformationStep("break", WriteInvalidPythonOperation("broken.py")),),
        ),
    )

    assert not result.success
    assert result.error.code == "final_validation_failed"
    assert result.validations
    assert result.rollback_attempted
    assert result.validations[-1].success
    assert not target.exists()


def test_structured_result_contains_required_fields(tmp_path) -> None:
    (tmp_path / "ready.py").write_text("value = 1\n", encoding="utf-8")

    result = _execute(
        tmp_path,
        TransformationPlan(
            id="structured-result",
            preconditions=(FileExistsPrecondition("ready.py"),),
            steps=(TransformationStep("create", CreateFileOperation("created.py")),),
        ),
    )

    assert result.success
    assert result.plan_id == "structured-result"
    assert result.transformation_id == "structured-result"
    assert result.planned_steps == ("create",)
    assert result.executed_steps == ("create",)
    assert result.failed_step is None
    assert result.error is None
    assert result.precondition_results[0].success
    assert result.operation_results[0].operation == "create_file"
    assert result.validations[0].success
    assert not result.rollback_attempted
    assert result.created_paths == (tmp_path / "created.py",)
    assert result.modified_paths == ()
    assert result.deleted_paths == ()


def test_e2e_real_successful_dag_with_preconditions(tmp_path) -> None:
    (tmp_path / "ready.py").write_text("value = 1\n", encoding="utf-8")

    result = _execute(
        tmp_path,
        TransformationPlan(
            id="e2e-success",
            preconditions=(FileExistsPrecondition("ready.py"),),
            steps=(
                TransformationStep("create-file", CreateFileOperation("alpha.py")),
                TransformationStep(
                    "create-module",
                    CreateModuleOperation("pkg.beta"),
                    ("create-file",),
                ),
            ),
        ),
    )

    assert result.success
    assert result.executed_steps == ("create-file", "create-module")
    assert (tmp_path / "alpha.py").is_file()
    assert (tmp_path / "pkg" / "beta.py").is_file()
    assert result.validations[0].success


def test_e2e_real_failure_restores_bytes(tmp_path) -> None:
    module = tmp_path / "sample.py"
    original = b"def keep():\n    return 1\n\ndef remove_me():\n    return 2\n"
    module.write_bytes(original)
    (tmp_path / "existing.py").write_text("value = 1\n", encoding="utf-8")

    result = _execute(
        tmp_path,
        TransformationPlan(
            id="e2e-failure",
            steps=(
                TransformationStep("create", CreateFileOperation("new_file.py")),
                TransformationStep(
                    "delete-symbol",
                    DeleteSymbolOperation("remove_me", "sample"),
                    ("create",),
                ),
                TransformationStep(
                    "fail",
                    CreateFileOperation("existing.py"),
                    ("delete-symbol",),
                ),
            ),
        ),
    )

    assert not result.success
    assert module.read_bytes() == original
    assert not (tmp_path / "new_file.py").exists()
    assert result.executed_steps == ("create", "delete-symbol", "fail")


def test_step_precondition_is_evaluated_after_previous_step(tmp_path) -> None:
    result = _execute(
        tmp_path,
        TransformationPlan(
            id="dynamic-precondition",
            steps=(
                TransformationStep("create", CreateFileOperation("marker.py")),
                TransformationStep(
                    "dependent",
                    CreateFileOperation("dependent.py"),
                    ("create",),
                    (FileExistsPrecondition("marker.py"),),
                ),
            ),
        ),
    )

    assert result.success
    assert result.precondition_results[-1].success
    assert (tmp_path / "dependent.py").exists()


def test_create_module_rollback_removes_generated_package_artifacts(tmp_path) -> None:
    (tmp_path / "existing.py").write_text("value = 1\n", encoding="utf-8")

    result = _execute(
        tmp_path,
        TransformationPlan(
            id="module-rollback",
            steps=(
                TransformationStep("module", CreateModuleOperation("pkg.deep.module")),
                TransformationStep("fail", CreateFileOperation("existing.py"), ("module",)),
            ),
        ),
    )

    assert not result.success
    assert not (tmp_path / "pkg").exists()
    assert result.rollback_applied


def test_unsupported_operation_returns_structured_failure(tmp_path) -> None:
    (tmp_path / "existing.py").write_text("value = 1\n", encoding="utf-8")

    result = _execute(
        tmp_path,
        TransformationPlan(
            id="unsupported",
            steps=(
                TransformationStep("create", CreateFileOperation("created.py")),
                TransformationStep("unsupported", ValidateProjectOperation("project"), ("create",)),
            ),
        ),
    )

    assert not result.success
    assert result.error.code == "unsupported_operation"
    assert not (tmp_path / "created.py").exists()
