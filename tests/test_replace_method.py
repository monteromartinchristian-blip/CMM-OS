import ast

from kernel.services.python_editor import PythonEditor


def test_replace_method(temp_python_file):

    sample = temp_python_file(
        "calculator.py"
    )

    editor = PythonEditor()

    replacement = ast.parse(
        "def add(self, a, b):\n    return a * b"
    ).body[0]

    editor.replace_method(
        sample,
        "Calculator",
        "add",
        replacement,
    )

    text = sample.read_text(
        encoding="utf-8"
    )

    assert "return a * b" in text
    assert "def add(self, a, b):" in text

    ast.parse(text)
