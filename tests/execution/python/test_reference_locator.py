from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory

import libcst as cst

from cmm.execution.python import PythonProjectParser, SemanticContextBuilder
from cmm.execution.python.visitors import ReferenceLocator


def test_locates_simple_function_call() -> None:
    module = cst.parse_module("foo()\n")

    locations = ReferenceLocator().find("module", module, "foo")

    assert len(locations) == 1
    assert locations[0].module_name == "module"
    assert (locations[0].line, locations[0].column) == (1, 0)
    assert locations[0].node.value == "foo"


def test_locates_multiple_simple_function_calls() -> None:
    module = cst.parse_module("foo()\nfoo()\n")

    locations = ReferenceLocator().find("module", module, "foo")

    assert [(location.line, location.column) for location in locations] == [
        (1, 0),
        (2, 0),
    ]


def test_returns_no_locations_for_missing_function_or_partial_name() -> None:
    module = cst.parse_module("foobar()\n")
    locator = ReferenceLocator()

    assert locator.find("module", module, "missing") == []
    assert locator.find("module", module, "foo") == []


def test_reference_index_aggregates_references_from_all_modules() -> None:
    with TemporaryDirectory() as directory:
        project_root = Path(directory)
        (project_root / "first.py").write_text("foo()\n", encoding="utf-8")
        (project_root / "second.py").write_text("foo()\nfoo()\n", encoding="utf-8")
        snapshot = PythonProjectParser().parse(project_root)

        context = SemanticContextBuilder().build(
            snapshot,
            build_reference_index=True,
        )

        assert context.reference_index is not None
        locations = context.reference_index.find("foo")
        assert [location.module_name for location in locations] == [
            "first",
            "second",
            "second",
        ]
