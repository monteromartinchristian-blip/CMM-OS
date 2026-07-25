from __future__ import annotations

from cmm.validation.impact import ChangeType, diff_python_sources


def test_python_diff_detects_signature_decorator_and_import_changes() -> None:
    before = """\
from pkg.helpers import helper

def func(x):
    return helper(x)
"""
    after = """\
from pkg.helpers import helper
from pkg.more import extra

@staticmethod
def func(x, y=1):
    return helper(x) + extra(y)
"""

    diff = diff_python_sources(
        module_name="pkg.module",
        before_source=before,
        after_source=after,
    )

    assert diff.change_type == ChangeType.STRUCTURAL_CHANGE
    assert diff.signature_changed is True
    assert diff.decorator_changed is True
    assert [item.kind for item in diff.import_changes]
    assert diff.symbol_changes[0].symbol == "func"
    assert diff.symbol_changes[0].after_decorators == ("staticmethod",)
