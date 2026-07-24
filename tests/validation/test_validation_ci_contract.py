"""Static validation of GitHub Actions CI configuration (Phase 7.12)."""

from __future__ import annotations

from pathlib import Path


def test_ci_workflow_file_exists() -> None:
    root = Path.cwd()
    workflow_file = root / ".github" / "workflows" / "continuous-validation.yml"
    assert workflow_file.exists()


def test_ci_workflow_content() -> None:
    root = Path.cwd()
    workflow_file = root / ".github" / "workflows" / "continuous-validation.yml"
    content = workflow_file.read_text(encoding="utf-8")

    assert "cmm validation run" in content
    assert "--policy ci" in content
    assert "--output json" in content
    assert "upload-artifact" in content
    assert "if: always()" in content

    # Verify no dangerous operations
    assert "git push" not in content
    assert "git commit" not in content
    assert "release" not in content
