"""Phase 10.48 remediation — baseline-aware quality gate decision tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from scripts.audit.verify_phase_10_48_ruff_baseline import (
    BASELINE_HEAD,
    RuffDebtSnapshot,
    evaluate_gate,
)

_REPO_ROOT = Path(__file__).resolve().parents[2]
_VERIFIER = _REPO_ROOT / "scripts" / "audit" / "verify_phase_10_48_ruff_baseline.py"


def test_phase_10_48_baseline_head_is_pinned():
    assert BASELINE_HEAD == "35bf9d2b33c9e3c31ecd789c5d1237590eb31816"


def test_baseline_gate_passes_only_with_clean_changed_python_and_no_debt_growth():
    decision = evaluate_gate(
        baseline=RuffDebtSnapshot(lint_violations=839, format_files=340),
        current=RuffDebtSnapshot(lint_violations=839, format_files=340),
        changed_lint_violations=0,
        changed_format_files=0,
    )

    assert decision.passed is True


def test_baseline_gate_fails_if_changed_python_has_lint_debt():
    decision = evaluate_gate(
        baseline=RuffDebtSnapshot(lint_violations=839, format_files=340),
        current=RuffDebtSnapshot(lint_violations=839, format_files=340),
        changed_lint_violations=1,
        changed_format_files=0,
    )

    assert decision.passed is False
    assert decision.changed_python_ruff_pass is False


def test_baseline_gate_fails_if_changed_python_has_format_debt():
    decision = evaluate_gate(
        baseline=RuffDebtSnapshot(lint_violations=839, format_files=340),
        current=RuffDebtSnapshot(lint_violations=839, format_files=340),
        changed_lint_violations=0,
        changed_format_files=1,
    )

    assert decision.passed is False
    assert decision.changed_python_format_pass is False


def test_baseline_gate_fails_if_global_lint_debt_grows():
    decision = evaluate_gate(
        baseline=RuffDebtSnapshot(lint_violations=839, format_files=340),
        current=RuffDebtSnapshot(lint_violations=840, format_files=340),
        changed_lint_violations=0,
        changed_format_files=0,
    )

    assert decision.passed is False
    assert decision.no_new_ruff_regressions is False


def test_baseline_gate_fails_if_global_format_debt_grows():
    decision = evaluate_gate(
        baseline=RuffDebtSnapshot(lint_violations=839, format_files=340),
        current=RuffDebtSnapshot(lint_violations=839, format_files=341),
        changed_lint_violations=0,
        changed_format_files=0,
    )

    assert decision.passed is False
    assert decision.no_new_format_regressions is False


@pytest.mark.parametrize(
    "forbidden",
    (
        "git worktree",
        '"worktree"',
        "git stash",
        '"stash"',
        "git reset",
        '"reset"',
        "git clean",
        '"clean"',
        "shell=True",
    ),
)
def test_baseline_verifier_avoids_mutating_and_shell_constructs(forbidden: str):
    source = _VERIFIER.read_text(encoding="utf-8")

    assert forbidden not in source


def test_baseline_verifier_extracts_the_baseline_with_git_archive():
    source = _VERIFIER.read_text(encoding="utf-8")

    assert '"archive"' in source
