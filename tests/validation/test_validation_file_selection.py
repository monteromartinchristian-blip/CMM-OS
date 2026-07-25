from __future__ import annotations

from pathlib import Path

from cmm.validation.catalog import select_python_files
from cmm.validation.context import ValidationContext


def test_select_python_files_prefers_changed_python(tmp_path: Path):
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "a.py").write_text("print('ok')\n", encoding="utf-8")
    (tmp_path / "src" / "b.txt").write_text("skip\n", encoding="utf-8")
    ctx = ValidationContext(
        project_root=tmp_path, changed_files=(Path("src/a.py"), Path("src/b.txt"))
    )

    files = select_python_files(ctx)

    assert files == [Path("src/a.py")]


def test_select_python_files_falls_back_to_project(tmp_path: Path):
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "a.py").write_text("print('ok')\n", encoding="utf-8")
    (tmp_path / "src" / "b.py").write_text("print('ok')\n", encoding="utf-8")
    ctx = ValidationContext(project_root=tmp_path, changed_files=(Path("src/b.txt"),))

    files = select_python_files(ctx)

    assert files == [Path("src/a.py"), Path("src/b.py")]


def test_select_python_files_excludes_common_dirs_and_is_deterministic(tmp_path: Path):
    (tmp_path / ".venv").mkdir()
    (tmp_path / ".venv" / "ignored.py").write_text("x = 1\n", encoding="utf-8")
    (tmp_path / "__pycache__").mkdir()
    (tmp_path / "__pycache__" / "ignored.py").write_text("x = 1\n", encoding="utf-8")
    (tmp_path / "pkg").mkdir()
    (tmp_path / "pkg" / "b.py").write_text("print('b')\n", encoding="utf-8")
    (tmp_path / "pkg" / "a.py").write_text("print('a')\n", encoding="utf-8")
    ctx = ValidationContext(project_root=tmp_path)

    files = select_python_files(ctx)

    assert files == [Path("pkg/a.py"), Path("pkg/b.py")]


def test_select_python_files_handles_missing_and_outside_project(
    tmp_path: Path, monkeypatch
):
    (tmp_path / "pkg").mkdir()
    (tmp_path / "pkg" / "ok.py").write_text("print('ok')\n", encoding="utf-8")
    ctx = ValidationContext(
        project_root=tmp_path,
        changed_files=(Path("pkg/ok.py"), Path("missing.py"), Path("../outside.py")),
    )

    files = select_python_files(ctx)

    assert files == [Path("pkg/ok.py")]
