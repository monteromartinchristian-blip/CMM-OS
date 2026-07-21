from __future__ import annotations

from cmm.execution import ExecutionContext
from cmm.transformations import (
    CreateFileOperation,
    DeleteFileOperation,
    FileExistsPrecondition,
    GraphValidationResult,
    ModuleExistsPrecondition,
    SymbolExistsPrecondition,
    TransformationGraph,
    TransformationGraphNode,
    TransformationPlan,
    TransformationStep,
)


def _step(
    step_id: str,
    dependencies: tuple[str, ...] = (),
) -> TransformationStep:
    return TransformationStep(
        id=step_id,
        operation=CreateFileOperation(path=f"{step_id}.py"),
        dependencies=dependencies,
    )


def test_valid_dag_produces_topological_order() -> None:
    plan = TransformationPlan(
        id="valid",
        steps=(
            _step("prepare"),
            _step("write", ("prepare",)),
            _step("cleanup", ("write",)),
        ),
    )

    result = TransformationGraph.validate_plan(plan)

    assert result == GraphValidationResult(
        success=True,
        topological_order=("prepare", "write", "cleanup"),
    )


def test_missing_dependency_is_structured() -> None:
    result = TransformationGraph.validate_plan(
        TransformationPlan(id="missing", steps=(_step("write", ("prepare",)),))
    )

    assert not result.success
    assert result.errors[0].code == "missing_dependency"
    assert result.errors[0].step_id == "write"
    assert result.errors[0].dependency_id == "prepare"


def test_duplicate_step_id_is_structured() -> None:
    result = TransformationGraph.validate_plan(
        TransformationPlan(id="duplicate", steps=(_step("same"), _step("same")))
    )

    assert not result.success
    assert result.errors[0].code == "duplicate_step_id"
    assert result.errors[0].step_id == "same"


def test_direct_cycle_is_structured() -> None:
    graph = TransformationGraph(
        nodes={
            "a": TransformationGraphNode(step=_step("a"), dependencies=("a",)),
        }
    )

    result = graph.validate()

    assert not result.success
    assert result.errors[0].code == "cycle_detected"
    assert "a -> a" in result.errors[0].message


def test_indirect_cycle_is_structured() -> None:
    graph = TransformationGraph(
        nodes={
            "a": TransformationGraphNode(step=_step("a"), dependencies=("c",)),
            "b": TransformationGraphNode(step=_step("b"), dependencies=("a",)),
            "c": TransformationGraphNode(step=_step("c"), dependencies=("b",)),
        }
    )

    result = graph.validate()

    assert not result.success
    assert result.errors[0].code == "cycle_detected"
    assert result.errors[0].message.endswith("a -> b -> c -> a.")


def test_topological_order_is_deterministic() -> None:
    graph = TransformationGraph(
        nodes={
            "write-b": TransformationGraphNode(
                step=_step("write-b"),
                dependencies=("prepare",),
            ),
            "write-a": TransformationGraphNode(
                step=_step("write-a"),
                dependencies=("prepare",),
            ),
            "prepare": TransformationGraphNode(step=_step("prepare")),
        }
    )

    assert [node.step.id for node in graph.topological_order()] == [
        "prepare",
        "write-a",
        "write-b",
    ]


def test_file_module_and_symbol_preconditions_pass(tmp_path) -> None:
    (tmp_path / "pkg").mkdir()
    (tmp_path / "pkg" / "__init__.py").write_text("", encoding="utf-8")
    (tmp_path / "pkg" / "mod.py").write_text("def build():\n    return 1\n", encoding="utf-8")
    context = ExecutionContext(tmp_path)

    results = [
        FileExistsPrecondition("pkg/mod.py").evaluate(context, "s1"),
        ModuleExistsPrecondition("pkg.mod").evaluate(context, "s1"),
        SymbolExistsPrecondition("pkg.mod", "build").evaluate(context, "s1"),
    ]

    assert all(result.success for result in results)
    assert [result.step_id for result in results] == ["s1", "s1", "s1"]


def test_precondition_failure_is_structured(tmp_path) -> None:
    result = FileExistsPrecondition("missing.py").evaluate(ExecutionContext(tmp_path), "s1")

    assert not result.success
    assert result.name == "file_exists"
    assert result.step_id == "s1"
    assert "not found" in result.message


def test_project_root_is_normalized(tmp_path) -> None:
    context = ExecutionContext(tmp_path / ".")

    assert context.project_root == tmp_path.resolve()


def test_path_traversal_is_rejected(tmp_path) -> None:
    context = ExecutionContext(tmp_path)

    try:
        context.resolve_project_path("../outside.py")
    except ValueError as error:
        assert "escapes project_root" in str(error)
    else:
        raise AssertionError("Expected path traversal rejection.")


def test_symlink_escape_is_rejected(tmp_path) -> None:
    outside = tmp_path.parent / "phase6-outside"
    outside.mkdir(exist_ok=True)
    link = tmp_path / "linked"
    link.symlink_to(outside, target_is_directory=True)

    context = ExecutionContext(tmp_path)

    try:
        context.resolve_project_path("linked/file.py")
    except ValueError as error:
        assert "escapes project_root" in str(error)
    else:
        raise AssertionError("Expected symlink escape rejection.")
