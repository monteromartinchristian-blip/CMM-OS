"""Phase 10.49 — baseline-aware Ruff/format gate decision tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from scripts.audit.verify_phase_10_49_ruff_baseline import (
    BASELINE_HEAD,
    EXPECTED_RUFF_VERSION,
    RuffDebtSnapshot,
    evaluate_gate,
    ruff_version_matches,
)

_REPO_ROOT = Path(__file__).resolve().parents[2]
_VERIFIER = _REPO_ROOT / "scripts" / "audit" / "verify_phase_10_49_ruff_baseline.py"


def test_phase_10_49_baseline_head_is_pinned():
    assert BASELINE_HEAD == "6f9deeb37b6e3237bea4564c5e5607249eb12b70"


def test_phase_10_49_pins_the_ruff_version():
    assert EXPECTED_RUFF_VERSION == "0.16.2"


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


def test_ruff_version_matches_accepts_the_pinned_release():
    assert ruff_version_matches("ruff 0.16.2") is True


@pytest.mark.parametrize(
    "measured",
    ("ruff 0.16.1", "ruff 0.17.0", "ruff 0.16.20", ""),
)
def test_ruff_version_matches_fails_closed_on_any_other_release(measured: str):
    assert ruff_version_matches(measured) is False


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
