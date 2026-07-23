from __future__ import annotations

from pathlib import Path

import pytest

from cmm.validation.context import ValidationContext
from cmm.validation.testing.escalation import TestEscalationDecision as _TestEscalationDecision, decide_test_escalation
from cmm.validation.testing.selection import TestSelection as _TestSelection


def test_test_escalation_decision_rejects_invalid_confidence() -> None:
    with pytest.raises(Exception):
        _TestEscalationDecision(
            include_affected_tests=True,
            include_unit_tests=False,
            include_integration_tests=False,
            requires_full_suite=False,
            confidence=1.5,
        )


def test_low_confidence_selection_requires_full_suite(tmp_path: Path) -> None:
    context = ValidationContext(project_root=tmp_path)
    selection = _TestSelection(
        selected_tests=(Path("tests/test_sample.py"),),
        confidence=0.5,
        reasons=("token_match_partial",),
    )

    decision = decide_test_escalation(context, selection)

    assert decision.requires_full_suite
    assert "low_confidence" in decision.reasons


def test_explicit_full_suite_request_wins(tmp_path: Path) -> None:
    context = ValidationContext(project_root=tmp_path, requested_steps=("full_suite",))
    selection = _TestSelection(selected_tests=(Path("tests/test_sample.py"),), confidence=0.95)

    decision = decide_test_escalation(context, selection)

    assert decision.requires_full_suite
    assert "explicit_full_suite_request" in decision.reasons
