from kernel.llm.exceptions import ParserError
from kernel.llm.operation_parsers import (
    CreateClassOperationParser,
    EnsureImportOperationParser,
    InsertMethodOperationParser,
    OperationParserRegistry,
)
from kernel.planner.operations import CreateClassOperation, EnsureImportOperation, InsertMethodOperation


def test_registry_registers_and_resolves_parsers() -> None:
    registry = OperationParserRegistry()
    parser = CreateClassOperationParser()

    registry.register("create_class", parser)

    assert registry.has_parser("create_class") is True
    assert registry.resolve("create_class") is parser


def test_parser_uses_registry_for_create_class() -> None:
    registry = OperationParserRegistry()
    registry.register("create_class", CreateClassOperationParser())

    parser = registry.resolve("create_class")
    operation = parser.parse({"type": "create_class", "module": "models.py", "name": "User"})

    assert isinstance(operation, CreateClassOperation)
    assert operation.class_name == "User"


def test_create_class_parser_still_works() -> None:
    parser = CreateClassOperationParser()

    operation = parser.parse({"type": "create_class", "module": "models.py", "name": "User"})

    assert isinstance(operation, CreateClassOperation)
    assert operation.module == "models.py"


def test_insert_method_parser_builds_operation() -> None:
    parser = InsertMethodOperationParser()

    operation = parser.parse(
        {
            "type": "insert_method",
            "module": "models.py",
            "class": "User",
            "name": "full_name",
            "code": "def full_name(self):\n    return self.name",
        }
    )

    assert isinstance(operation, InsertMethodOperation)
    assert operation.target_class == "User"
    assert operation.method_name == "full_name"
    assert operation.source_code == "def full_name(self):\n    return self.name"


def test_insert_method_parser_requires_module() -> None:
    parser = InsertMethodOperationParser()

    try:
        parser.parse({"type": "insert_method", "class": "User", "name": "full_name", "code": "pass"})
    except ParserError as exc:
        assert "module" in str(exc)
    else:
        raise AssertionError("Expected ParserError")


def test_insert_method_parser_requires_class() -> None:
    parser = InsertMethodOperationParser()

    try:
        parser.parse({"type": "insert_method", "module": "models.py", "name": "full_name", "code": "pass"})
    except ParserError as exc:
        assert "class" in str(exc)
    else:
        raise AssertionError("Expected ParserError")


def test_insert_method_parser_requires_name() -> None:
    parser = InsertMethodOperationParser()

    try:
        parser.parse({"type": "insert_method", "module": "models.py", "class": "User", "code": "pass"})
    except ParserError as exc:
        assert "name" in str(exc)
    else:
        raise AssertionError("Expected ParserError")


def test_insert_method_parser_requires_code() -> None:
    parser = InsertMethodOperationParser()

    try:
        parser.parse({"type": "insert_method", "module": "models.py", "class": "User", "name": "full_name"})
    except ParserError as exc:
        assert "code" in str(exc)
    else:
        raise AssertionError("Expected ParserError")


def test_ensure_import_parser_builds_operation() -> None:
    parser = EnsureImportOperationParser()

    operation = parser.parse({"type": "ensure_import", "module": "models.py", "import": "from typing import Optional"})

    assert isinstance(operation, EnsureImportOperation)
    assert operation.module == "models.py"
    assert operation.name == "from typing import Optional"


def test_ensure_import_parser_requires_module() -> None:
    parser = EnsureImportOperationParser()

    try:
        parser.parse({"type": "ensure_import", "import": "from typing import Optional"})
    except ParserError as exc:
        assert "module" in str(exc)
    else:
        raise AssertionError("Expected ParserError")


def test_ensure_import_parser_requires_import() -> None:
    parser = EnsureImportOperationParser()

    try:
        parser.parse({"type": "ensure_import", "module": "models.py"})
    except ParserError as exc:
        assert "import" in str(exc)
    else:
        raise AssertionError("Expected ParserError")


def test_ensure_import_parser_rejects_empty_import() -> None:
    parser = EnsureImportOperationParser()

    try:
        parser.parse({"type": "ensure_import", "module": "models.py", "import": "   "})
    except ParserError as exc:
        assert "import" in str(exc)
    else:
        raise AssertionError("Expected ParserError")


def test_unknown_operation_type_produces_parser_error() -> None:
    registry = OperationParserRegistry()

    try:
        registry.resolve("unknown")
    except ParserError as exc:
        assert "Unsupported operation type" in str(exc)
    else:
        raise AssertionError("Expected ParserError")
