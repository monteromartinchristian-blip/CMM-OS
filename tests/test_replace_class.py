import ast

from kernel.services.python_editor import PythonEditor
from kernel.services.python_locator import PythonLocator


def test_replace_class(temp_python_file):

    sample = temp_python_file(
        "calculator.py"
    )

    editor = PythonEditor()

    replacement = """
class Calculator:

    def multiply(self, a, b):
        return a * b
"""

    replaced = editor.replace_class(
        sample,
        "Calculator",
        replacement,
    )

    assert replaced is True

    text = sample.read_text(
        encoding="utf-8"
    )

    assert "class Calculator" in text
    assert "def multiply" in text
    assert "def add" not in text
    assert "def sub" not in text

    ast.parse(text)

    locator = PythonLocator()
    found = locator.find_class(
        sample,
        "Calculator",
    )

    assert found is not None
    assert found["name"] == "Calculator"

    missing = editor.replace_class(
        sample,
        "MissingClass",
        replacement,
    )

    assert missing is False
