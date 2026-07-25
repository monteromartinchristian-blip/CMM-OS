from __future__ import annotations

import subprocess
from pathlib import Path

from cmm.validation.impact import ChangeSetBuilder, GitChangeSetAdapter, FileChangeKind


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_change_set_builder_from_git_diff(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True, text=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo, check=True, capture_output=True, text=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=repo, check=True, capture_output=True, text=True)

    _write(repo / "pkg" / "module.py", "def func(x):\n    return x\n")
    subprocess.run(["git", "add", "."], cwd=repo, check=True, capture_output=True, text=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=repo, check=True, capture_output=True, text=True)

    _write(repo / "pkg" / "module.py", "def func(x, y=1):\n    return x + y\n")

    change_set = ChangeSetBuilder(git_adapter=GitChangeSetAdapter()).build(
        project_root=repo,
        git_ref="HEAD",
    )

    assert any(item.kind == FileChangeKind.MODIFIED for item in change_set.file_changes)
