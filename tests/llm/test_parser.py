import pytest

from kernel.llm.exceptions import ParserError
from kernel.llm.parser import OperationPlanParser
from kernel.planner.operations import CreateClassOperation, EnsureImportOperation, InsertMethodOperation


def test_parser_raises_on_invalid_json() -> None:
    parser = OperationPlanParser()

    with pytest.raises(ParserError, match="Invalid JSON"):
        parser.parse("{invalid json")


def test_parser_raises_when_operations_missing() -> None:
    parser = OperationPlanParser()

    with pytest.raises(ParserError, match="operations"):
        parser.parse('{"foo": "bar"}')


def test_parser_returns_empty_execution_plan_for_valid_json() -> None:
    parser = OperationPlanParser()

    plan = parser.parse('{"operations": []}')

    assert len(plan) == 0


def test_parser_builds_create_class_operation() -> None:
    parser = OperationPlanParser()

    plan = parser.parse('{"operations": [{"type": "create_class", "module": "models.py", "name": "User"}]}')

    assert len(plan) == 1
    assert isinstance(plan[0], CreateClassOperation)
    assert plan[0].module == "models.py"
    assert plan[0].class_name == "User"


def test_parser_raises_on_unknown_operation_type() -> None:
    parser = OperationPlanParser()

    with pytest.raises(ParserError, match="Unsupported operation type"):
        parser.parse('{"operations": [{"type": "unknown"}]}')


def test_parser_raises_when_module_missing() -> None:
    parser = OperationPlanParser()

    with pytest.raises(ParserError, match="module"):
        parser.parse('{"operations": [{"type": "create_class", "name": "User"}]}')


def test_parser_raises_when_name_missing() -> None:
    parser = OperationPlanParser()

    with pytest.raises(ParserError, match="name"):
        parser.parse('{"operations": [{"type": "create_class", "module": "models.py"}]}')


def test_parser_supports_multiple_create_class_operations() -> None:
    parser = OperationPlanParser()

    plan = parser.parse(
        '{"operations": [{"type": "create_class", "module": "models.py", "name": "User"}, {"type": "create_class", "module": "views.py", "name": "Admin"}]}'
    )

    assert len(plan) == 2
    assert [operation.class_name for operation in plan] == ["User", "Admin"]


def test_parser_supports_mixed_create_class_and_insert_method_operations() -> None:
    parser = OperationPlanParser()

    plan = parser.parse(
        '{"operations": [{"type": "create_class", "module": "models.py", "name": "User"}, {"type": "insert_method", "module": "models.py", "class": "User", "name": "full_name", "code": "def full_name(self):\\n    return self.name"}]}'
    )

    assert len(plan) == 2
    assert isinstance(plan[0], CreateClassOperation)
    assert isinstance(plan[1], InsertMethodOperation)
    assert plan[1].target_class == "User"


def test_parser_supports_mixed_create_class_insert_method_and_ensure_import_operations() -> None:
    parser = OperationPlanParser()

    plan = parser.parse(
        '{"operations": [{"type": "create_class", "module": "models.py", "name": "User"}, {"type": "insert_method", "module": "models.py", "class": "User", "name": "full_name", "code": "def full_name(self):\\n    return self.name"}, {"type": "ensure_import", "module": "models.py", "import": "from typing import Optional"}]}'
    )

    assert len(plan) == 3
    assert isinstance(plan[0], CreateClassOperation)
    assert isinstance(plan[1], InsertMethodOperation)
    assert isinstance(plan[2], EnsureImportOperation)
