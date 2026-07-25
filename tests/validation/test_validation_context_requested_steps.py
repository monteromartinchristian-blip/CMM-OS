from pathlib import Path

from cmm.validation.context import ValidationContext


def test_context_requested_steps_serialization():
    ctx = ValidationContext(
        project_root=Path("/project"), requested_steps=("lint", "tests")
    )
    ser = ctx.serialize()
    assert ser["requested_steps"] == ["lint", "tests"]
