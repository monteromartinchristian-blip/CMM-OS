import ast

from kernel.services.python_editor import PythonEditor
from kernel.services.python_locator import PythonLocator


def test_insert_method(temp_python_file):

    sample = temp_python_file(
        "calculator.py"
    )

    editor = PythonEditor()

    editor.insert_method(
        sample,
        "Calculator",
        "end",
        "def mul(self, a, b):\n    return a * b",
    )

    text = sample.read_text(
        encoding="utf-8"
    )

    assert text.count("def mul") == 1
    assert "def mul(self, a, b):" in text
    assert "return a * b" in text

    ast.parse(text)

    locator = PythonLocator()
    method = locator.find_method(
        sample,
        "Calculator",
        "mul",
    )

    assert method is not None
    assert method["name"] == "mul"
