import ast

from kernel.services.python_editor import PythonEditor
from kernel.services.python_locator import PythonLocator


def test_create_class(temp_python_file):

    sample = temp_python_file(
        "calculator.py"
    )

    editor = PythonEditor()

    created = editor.create_class(
        sample,
        "NewCalculator",
        base_classes=["Calculator"],
        methods=["def add(self, a, b):\n    return a + b"],
    )

    assert created is True

    text = sample.read_text(
        encoding="utf-8"
    )

    assert "class NewCalculator" in text
    assert "def add(self, a, b):" in text

    ast.parse(text)

    locator = PythonLocator()
    found = locator.find_class(
        sample,
        "NewCalculator",
    )

    assert found is not None
    assert found["name"] == "NewCalculator"

    repeated = editor.create_class(
        sample,
        "NewCalculator",
        base_classes=["Calculator"],
        methods=["def add(self, a, b):\n    return a + b"],
    )

    assert repeated is False
