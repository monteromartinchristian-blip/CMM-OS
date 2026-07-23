from __future__ import annotations

from pathlib import Path

from cmm.validation.catalog import change_impact_step
from cmm.validation.context import ValidationContext
from cmm.validation.impact import ChangeSet, ChangeType, FileChange, FileChangeKind, FileVersion, PublicAPIChange
from cmm.validation.static_analysis import (
    StaticAnalysisPlan,
    StaticAnalysisScope,
    build_static_analysis_plan,
    default_static_analysis_steps,
)


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_static_analysis_plan_uses_affected_scope(tmp_path: Path) -> None:
    _write(tmp_path / "pkg" / "module.py", "def func(x):\n    return x\n")
    change_set = ChangeSet(
        project_root=tmp_path,
        before_root=None,
        after_root=tmp_path,
        file_changes=(
            FileChange(
                before_path=None,
                after_path=Path("pkg/module.py"),
                kind=FileChangeKind.ADDED,
                after=FileVersion(
                    path=Path("pkg/module.py"),
                    exists=True,
                    content_hash="abc",
                    source="after",
                    content="def func(x):\n    return x\n",
                ),
                confidence=0.9,
            ),
        ),
        change_type=ChangeType.NEW_FILE,
        confidence=0.9,
        requires_full_suite=False,
    )

    plan = build_static_analysis_plan(project_root=tmp_path, change_set=change_set)

    assert isinstance(plan, StaticAnalysisPlan)
    assert plan.scope == StaticAnalysisScope.AFFECTED
    assert plan.files == (Path("pkg/module.py"),)
    assert plan.complete is True


def test_static_analysis_plan_escalates_on_public_api_change(tmp_path: Path) -> None:
    _write(tmp_path / "pkg" / "module.py", "def func(x):\n    return x\n")
    change_set = ChangeSet(
        project_root=tmp_path,
        before_root=None,
        after_root=tmp_path,
        file_changes=(),
        change_type=ChangeType.PUBLIC_API_CHANGE,
        confidence=0.95,
        requires_full_suite=False,
        public_api_changes=(
            PublicAPIChange(
                module="pkg.module",
                added=("func",),
                removed=(),
                changed=(),
                confidence=0.9,
            ),
        ),
    )

    plan = build_static_analysis_plan(project_root=tmp_path, change_set=change_set)

    assert plan.scope == StaticAnalysisScope.FULL
    assert plan.reason == "public_api_change"


def test_default_static_analysis_steps_reuse_change_impact_metadata(tmp_path: Path) -> None:
    _write(tmp_path / "pkg" / "module.py", "def func(x):\n    return x\n")
    context = ValidationContext(project_root=tmp_path, changed_files=(Path("pkg/module.py"),))
    impact_step = change_impact_step(context)

    steps = default_static_analysis_steps(context, change_impact_step=impact_step)

    assert [step.name for step in steps] == ["type_check", "dead_code"]
    assert steps[0].metadata["analysis_scope"] == "full"
    assert steps[0].metadata["analysis_complete"] is True
    assert steps[0].metadata["analysis_plan"]["change_type"] == impact_step.metadata["change_type"]
