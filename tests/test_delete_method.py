import ast

from kernel.services.python_editor import PythonEditor


def test_delete_method(temp_python_file):

    sample = temp_python_file(
        "calculator.py"
    )

    editor = PythonEditor()

    editor.delete_method(
        sample,
        "Calculator",
        "add",
    )

    text = sample.read_text(
        encoding="utf-8"
    )

    assert "def add" not in text
    assert "class Calculator" in text

    ast.parse(text)
