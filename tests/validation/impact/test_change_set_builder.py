from __future__ import annotations

from pathlib import Path

from cmm.validation.impact import ChangeSetBuilder, ChangeType, FileChangeKind


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_change_set_builder_from_snapshots_detects_modified_and_renamed_files(
    tmp_path: Path,
) -> None:
    before_root = tmp_path / "before"
    after_root = tmp_path / "after"
    _write(before_root / "pkg" / "old_name.py", "def kept():\n    return 1\n")
    _write(before_root / "pkg" / "stable.py", "def stable():\n    return 1\n")
    _write(after_root / "pkg" / "new_name.py", "def kept():\n    return 1\n")
    _write(after_root / "pkg" / "stable.py", "def stable():\n    return 2\n")

    change_set = ChangeSetBuilder().build(
        project_root=tmp_path,
        before_root=before_root,
        after_root=after_root,
    )

    kinds = {item.kind for item in change_set.file_changes}
    renamed = [
        item for item in change_set.file_changes if item.kind == FileChangeKind.RENAMED
    ]
    modified = [
        item for item in change_set.file_changes if item.kind == FileChangeKind.MODIFIED
    ]

    assert change_set.change_type in {
        ChangeType.RENAMED_FILE,
        ChangeType.STRUCTURAL_CHANGE,
    }
    assert kinds == {FileChangeKind.RENAMED, FileChangeKind.MODIFIED}
    assert renamed[0].before_path == Path("pkg/old_name.py")
    assert renamed[0].after_path == Path("pkg/new_name.py")
    assert modified[0].after_path == Path("pkg/stable.py")


def test_change_set_builder_from_explicit_changed_files(tmp_path: Path) -> None:
    _write(tmp_path / "pkg" / "changed.py", "print('hi')\n")

    change_set = ChangeSetBuilder().build(
        project_root=tmp_path,
        changed_files=(Path("pkg/changed.py"), Path("README.md")),
    )

    assert tuple(str(path) for path in change_set.changed_files) == (
        "README.md",
        "pkg/changed.py",
    )
    assert change_set.source == "explicit"
    assert change_set.change_type == ChangeType.STRUCTURAL_CHANGE
