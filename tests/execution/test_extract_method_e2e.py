from __future__ import annotations

from pathlib import Path

from cmm.execution import ExecutionPipeline, ExecutionResult, OperationExecutorRegistry
from cmm.execution.python import (
    PythonExtractMethodExecutor,
    PythonProjectParser,
    PythonValidateProjectExecutor,
    SemanticContextBuilder,
)
from cmm.transformations import ExecutionPlanner, ExtractMethodTransformation
from cmm.transformations.execution_request import ExecutionRequest


def _execute(root: Path, *, validate_executor=None, new_name="helper", start=0, end=2):
    registry = OperationExecutorRegistry()
    registry.register_many([
        PythonExtractMethodExecutor(),
        validate_executor or PythonValidateProjectExecutor(),
    ])
    context = SemanticContextBuilder().build(
        PythonProjectParser().parse(root), build_reference_index=True
    )
    plan = ExecutionPlanner().build(
        ExtractMethodTransformation("package.module", "Service", "run", new_name, start, end)
        .create_plan("extract")
    )
    return ExecutionPipeline(registry, context, root).execute(plan)


def _write(root: Path, code: str) -> Path:
    package = root / "package"
    package.mkdir()
    (package / "__init__.py").write_text("", encoding="utf-8")
    path = package / "module.py"
    path.write_text(code, encoding="utf-8")
    return path


def test_extract_method_simple_without_output(tmp_path) -> None:
    path = _write(
        tmp_path,
        "class Service:\n"
        "    def run(self, value):\n"
        "        doubled = value * 2\n"
        "        self.total = doubled\n"
        "        return self.total\n",
    )
    result = _execute(tmp_path)
    code = path.read_text(encoding="utf-8")
    assert result.success
    assert "self.helper(value)" in code
    assert "def helper(self, value):" in code
    assert "self.total = doubled" in code


def test_extract_method_with_input_and_single_output(tmp_path) -> None:
    path = _write(
        tmp_path,
        "class Service:\n"
        "    def run(self, value):\n"
        "        first = value + 1\n"
        "        result = first * 2\n"
        "        return result\n",
    )
    result = _execute(tmp_path)
    code = path.read_text(encoding="utf-8")
    assert result.success
    assert "result = self.helper(value)" in code
    assert "return result" in code
    assert "return result" in code.split("def helper", 1)[1]


def test_extract_method_async_and_self_access(tmp_path) -> None:
    path = _write(
        tmp_path,
        "class Service:\n"
        "    async def run(self, value: int) -> int:\n"
        "        result = await self.compute(value)\n"
        "        self.last = result\n"
        "        return result\n",
    )
    result = _execute(tmp_path)
    code = path.read_text(encoding="utf-8")
    assert result.success
    assert "result = await self.helper(value)" in code
    assert "async def helper(self, value: int) -> int:" in code


def test_extract_method_supports_cls_and_classmethod(tmp_path) -> None:
    path = _write(
        tmp_path,
        "class Service:\n"
        "    @classmethod\n"
        "    def run(cls, *, value):\n"
        "        result = value + 1\n"
        "        return result\n",
    )
    result = _execute(tmp_path, end=1)
    code = path.read_text(encoding="utf-8")
    assert result.success
    assert "result = cls.helper(value=value)" in code
    assert "@classmethod\n    def run" in code
    assert "def helper(cls, *, value):" in code


def test_extract_method_preserves_original_decorator_without_decorating_helper(tmp_path) -> None:
    path = _write(
        tmp_path,
        "class Service:\n"
        "    @property\n"
        "    def run(self):\n"
        "        value = 1\n"
        "        return value\n",
    )
    result = _execute(tmp_path, end=1)
    code = path.read_text(encoding="utf-8")
    assert result.success
    assert "@property\n    def run" in code
    assert "def helper(self):" in code
    assert "@property\n    def helper" not in code


def test_extract_method_keeps_read_before_write_as_input(tmp_path) -> None:
    path = _write(
        tmp_path,
        "class Service:\n"
        "    def run(self, value):\n"
        "        value += 1\n"
        "        return value\n",
    )
    result = _execute(tmp_path, end=1)
    code = path.read_text(encoding="utf-8")
    assert result.success
    assert "value = self.helper(value)" in code
    assert "def helper(self, value):" in code


def test_extract_method_rejects_match_without_mutation(tmp_path) -> None:
    path = _write(
        tmp_path,
        "class Service:\n"
        "    def run(self, value):\n"
        "        match value:\n"
        "            case 1:\n"
        "                return 1\n",
    )
    before = path.read_bytes()
    result = _execute(tmp_path)
    assert not result.success
    assert path.read_bytes() == before


def test_extract_method_rejects_unsupported_block_without_mutation(tmp_path) -> None:
    path = _write(tmp_path, "class Service:\n    def run(self):\n        return 1\n")
    before = path.read_bytes()
    result = _execute(tmp_path, start=0, end=1)
    assert not result.success
    assert result.error.code == "precondition_failed"
    assert path.read_bytes() == before


def test_extract_method_rejects_name_conflict_without_mutation(tmp_path) -> None:
    path = _write(
        tmp_path,
        "class Service:\n"
        "    def run(self):\n"
        "        value = 1\n"
        "        return value\n"
        "    def helper(self):\n"
        "        return 2\n",
    )
    before = path.read_bytes()
    result = _execute(tmp_path)
    assert not result.success
    assert result.error.code == "precondition_failed"
    assert path.read_bytes() == before


class CorruptingValidationExecutor(PythonValidateProjectExecutor):
    def execute(self, request: ExecutionRequest) -> ExecutionResult:
        result = super().execute(request)
        request.metadata["execution_context"].module_path("package.module").write_text(
            "def broken(:\n", encoding="utf-8"
        )
        return result


def test_extract_method_validation_failure_rolls_back_bytes(tmp_path) -> None:
    path = _write(
        tmp_path,
        "class Service:\n"
        "    def run(self):\n"
        "        value = 1\n"
        "        result = value + 1\n"
        "        return result\n",
    )
    before = path.read_bytes()
    result = _execute(tmp_path, validate_executor=CorruptingValidationExecutor())
    assert not result.success
    assert result.error.code == "final_validation_failed"
    assert result.rollback_attempted and result.rollback_applied
    assert path.read_bytes() == before
