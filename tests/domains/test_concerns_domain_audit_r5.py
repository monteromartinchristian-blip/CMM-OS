"""Phase 10.25 — Audit-remediation regression tests for the sibling-domain
import boundary.

Remediates I-004: Concerns must not import private code from any sibling
specialized domain package.  Performs an AST import scan across all 14
Concerns production modules.
"""

from __future__ import annotations

import ast
from pathlib import Path

_CONCERNS_PACKAGE = Path(__file__).resolve().parents[2] / "cmm" / "domains" / "concerns"

_SPECIALIZED_DOMAIN_PACKAGES = (
    "cmm.domains.reflection",
    "cmm.domains.relationships",
    "cmm.domains.health",
    "cmm.domains.university",
    "cmm.domains.oppositions",
    "cmm.domains.life_plan",
    "cmm.domains.project",
    "cmm.domains.finance",
    "cmm.domains.languages",
)

# General is the canonical shared composition fallback: the frozen design
# (spec §94) requires the "General + Concerns" bootstrap composition, so
# bootstrap.py consumes the General bootstrap factory through its public API.
# This is NOT private-specialized-domain code: General is a shared foundation
# pack, and every sibling domain bootstrap (Relationships, Health, ...) uses
# the same canonical path.  The I-004 boundary scan scopes to specialized
# sibling domain PRIVATE packages (rules/operations/state) which Concerns must
# never import.
_COMPOSITION_EXCEPTIONS = {"bootstrap.py"}


def _concerns_modules() -> list[Path]:
    return sorted(path for path in _CONCERNS_PACKAGE.glob("*.py") if path.suffix == ".py")


def test_concerns_package_has_no_import_from_any_specialized_domain_package():
    """AST import scan over all 14 Concerns modules: zero imports from any
    sibling specialized domain package (I-004)."""
    modules = _concerns_modules()
    assert len(modules) == 14, [m.name for m in modules]
    violations: list[str] = []
    for module in modules:
        tree = ast.parse(module.read_text(encoding="utf-8"), filename=str(module))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name.startswith(_SPECIALIZED_DOMAIN_PACKAGES):
                        violations.append(f"{module.name}: import {alias.name}")
            elif isinstance(node, ast.ImportFrom) and node.module and node.module.startswith(
                _SPECIALIZED_DOMAIN_PACKAGES
            ):
                violations.append(f"{module.name}: from {node.module} import ...")
    assert violations == [], "\n".join(violations)


def test_concerns_hypothesis_exploration_uses_shared_generic_contract():
    """Concerns hypothesis exploration consumes the shared
    cmm.cognitive.hypothesis_evaluation contract (same shared module Reflection
    consumes), never a Reflection private helper."""
    from cmm.cognitive.hypothesis_evaluation import (
        evaluate_hypotheses as shared_evaluate_hypotheses,
    )
    from cmm.domains.concerns.operations import explore_hypotheses_result

    hypotheses = (
        {"identity": "h1", "statement": "fatigue explains it", "supporting_ids": ("s1",)},
        {"identity": "h2", "statement": "stress explains it", "supporting_ids": ("s2",)},
    )
    concerns_view = explore_hypotheses_result(hypotheses=hypotheses)
    canonical = shared_evaluate_hypotheses(hypotheses=hypotheses, diagnostic_signal=None)
    assert concerns_view["winner_selected"] == canonical["winner_selected"]
    assert len(concerns_view["hypotheses"]) == len(canonical["hypotheses"])
    assert concerns_view["no_diagnosis"] is True


def test_shared_evaluator_preserves_diagnostic_hook_for_reflection():
    """The shared evaluator's diagnostic hook keeps Reflection behavior:
    when a caller supplies a diagnostic classifier, statements matching it are
    flagged and never ranked stronger; the shared default (None) never
    diagnoses."""
    from cmm.cognitive.hypothesis_evaluation import evaluate_hypotheses

    flagged = evaluate_hypotheses(
        hypotheses=(
            {"identity": "h1", "statement": "I think I have depression", "supporting_ids": ("a",)},
        ),
        diagnostic_signal=lambda statement: "depression" in str(statement),
    )
    assert flagged["no_diagnosis"] is False
    assert flagged["hypotheses"][0]["diagnostic"] is True
    assert flagged["hypotheses"][0]["relative_strength"] is None

    default = evaluate_hypotheses(
        hypotheses=(
            {"identity": "h1", "statement": "I think I have depression", "supporting_ids": ("a",)},
        ),
        diagnostic_signal=None,
    )
    assert default["no_diagnosis"] is True
    assert default["hypotheses"][0]["diagnostic"] is False