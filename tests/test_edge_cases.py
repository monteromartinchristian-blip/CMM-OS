import ast
from pathlib import Path

from kernel.services.python_editor import PythonEditor
from kernel.services.python_locator import PythonLocator


def test_decorators_and_docstrings_are_preserved(temp_python_file):

    sample = temp_python_file(
        "calculator.py"
    )

    editor = PythonEditor()

    source = """
class Example:

    @staticmethod
    def helper():
        \"\"\"Return something.\"\"\"
        return 1
"""

    sample.write_text(source, encoding="utf-8")

    editor.replace_method(
        sample,
        "Example",
        "helper",
        """
@staticmethod
def helper():
    \"\"\"Return another value.\"\"\"
    return 2
""",
    )

    text = sample.read_text(encoding="utf-8")
    assert "@staticmethod" in text
    assert '"""Return another value."""' in text
    ast.parse(text)

    editor.rename_method(
        sample,
        "Example",
        "helper",
        "helper_value",
    )

    renamed_text = sample.read_text(encoding="utf-8")
    assert "def helper_value" in renamed_text
    assert "@staticmethod" in renamed_text
    ast.parse(renamed_text)


def test_async_methods_support_insert_replace_and_rename(tmp_path):

    sample = tmp_path / "async_example.py"
    sample.write_text(
        "class Example:\n    pass\n",
        encoding="utf-8",
    )

    editor = PythonEditor()

    editor.insert_method(
        sample,
        "Example",
        "end",
        "async def foo():\n    return 1",
    )

    editor.replace_method(
        sample,
        "Example",
        "foo",
        "async def foo():\n    return 2",
    )

    editor.rename_method(
        sample,
        "Example",
        "foo",
        "bar",
    )

    text = sample.read_text(encoding="utf-8")
    assert "async def bar" in text
    assert "return 2" in text
    ast.parse(text)

    locator = PythonLocator()
    method = locator.find_method(sample, "Example", "bar")
    assert method is not None
    assert method["name"] == "bar"


def test_type_hints_and_docstrings_survive_transformations(temp_python_file):

    sample = temp_python_file(
        "calculator.py"
    )

    editor = PythonEditor()

    editor.replace_method(
        sample,
        "Calculator",
        "add",
        """
def add(a: int) -> str:
    \"\"\"Add two values.\"\"\"
    return str(a)
""",
    )

    text = sample.read_text(encoding="utf-8")
    assert "def add(a: int) -> str" in text
    assert '"""Add two values."""' in text
    ast.parse(text)


def test_create_replace_class_with_inheritance_and_multiple_classes(temp_python_file):

    sample = temp_python_file(
        "calculator.py"
    )

    editor = PythonEditor()

    created = editor.create_class(
        sample,
        "Child",
        base_classes=["Base"],
        methods=["def greet(self):\n    return 'hi'"],
    )

    assert created is True

    replaced = editor.replace_class(
        sample,
        "Calculator",
        """
class Calculator:

    def multiply(self, a, b):
        return a * b
""",
    )

    assert replaced is True

    text = sample.read_text(encoding="utf-8")
    assert "class Child" in text
    assert "class Calculator" in text
    assert "def multiply" in text
    assert "def add" not in text
    ast.parse(text)

    locator = PythonLocator()
    child = locator.find_class(sample, "Child")
    calculator = locator.find_class(sample, "Calculator")
    assert child is not None
    assert calculator is not None


def test_empty_file_and_comments_are_supported(tmp_path):

    sample = tmp_path / "empty.py"
    sample.write_text("# comment\n", encoding="utf-8")

    editor = PythonEditor()

    created = editor.create_class(
        sample,
        "EmptyClass",
        methods=["def value(self):\n    return 1"],
    )

    assert created is True

    inserted = editor.ensure_import(
        sample,
        "os",
    )

    assert inserted is True

    text = sample.read_text(encoding="utf-8")
    assert "class EmptyClass" in text
    assert "import os" in text
    ast.parse(text)

    locator = PythonLocator()
    found = locator.find_class(sample, "EmptyClass")
    assert found is not None
