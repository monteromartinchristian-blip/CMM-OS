from pathlib import Path

from cmm.validation.context import ValidationContext


def test_context_normalization_and_serialize():
    root = Path("/project")
    changed = (Path("/project/src/example.py"), Path("/other/path.py"))
    ctx = ValidationContext(
        project_root=root,
        changed_files=changed,
        change_type="small_change",
        execution_mode="local",
    )
    assert ctx.changed_files[0] == Path("src/example.py")
    assert ctx.changed_files[1] == Path("/other/path.py")
    ser = ctx.serialize()
    assert ser["project_root"] == "/project"
    assert "src/example.py" in ser["changed_files"]
