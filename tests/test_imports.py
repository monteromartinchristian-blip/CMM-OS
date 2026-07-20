import ast

from kernel.services.python_editor import PythonEditor


def test_import_operations(temp_python_file):

    sample = temp_python_file(
        "calculator.py"
    )

    editor = PythonEditor()

    inserted = editor.ensure_import(
        sample,
        "os",
    )
    assert inserted is True

    duplicated = editor.ensure_import(
        sample,
        "os",
    )
    assert duplicated is False

    inserted_from = editor.ensure_import(
        sample,
        "pathlib",
        name="Path",
    )
    assert inserted_from is True

    inserted_alias = editor.ensure_import(
        sample,
        "os",
        alias="operating_system",
    )
    assert inserted_alias is True

    removed = editor.remove_import(
        sample,
        "os",
    )
    assert removed is True

    removed_from = editor.remove_import(
        sample,
        "pathlib",
        name="Path",
    )
    assert removed_from is True

    text = sample.read_text(
        encoding="utf-8"
    )

    ast.parse(text)

    assert editor.has_import(sample, "os") is False
    assert editor.has_import(sample, "pathlib", name="Path") is False
