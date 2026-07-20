from kernel.services.python_editor import PythonEditor


def test_rename_method(
    temp_python_file,
):

    sample = temp_python_file(
        "calculator.py"
    )

    editor = PythonEditor()

    editor.rename_method(
        sample,
        "Calculator",
        "add",
        "sum",
    )

    text = sample.read_text(
        encoding="utf-8"
    )

    assert "def sum" in text

    assert "def add" not in text