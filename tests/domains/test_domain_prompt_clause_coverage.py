"""Phase 10.48 — canonical clause-coverage ledger invariants."""

from __future__ import annotations

import re
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
LEDGER = _REPO_ROOT / "docs" / "audits" / "domain-prompt-clause-coverage.md"


def _coverage_body(text: str) -> str:
    return text.split(
        "## 3. Coverage of the fifteen prompts",
        1,
    )[1].split(
        "## 8. Final coverage check",
        1,
    )[0]


def _clause_ids(text: str) -> list[str]:
    ids = re.findall(r"^\| `([^`]+)` \|", _coverage_body(text), re.MULTILINE)
    return [clause_id for clause_id in ids if clause_id != "clause_id"]


def _counter(text: str, name: str) -> int:
    match = re.search(rf"^{name} = (\d+)$", text, re.MULTILINE)
    assert match is not None, f"missing coverage counter: {name}"
    return int(match.group(1))


def test_domain_prompt_clause_coverage_is_complete_and_self_consistent():
    text = LEDGER.read_text(encoding="utf-8")
    clause_ids = _clause_ids(text)

    assert clause_ids.count("R10-C48") == 1
    assert len(clause_ids) == len(set(clause_ids))

    assert _counter(text, "total_clauses") == len(clause_ids)
    assert _counter(text, "covered_clauses") == len(clause_ids)
    assert _counter(text, "unclassified_clauses") == 0
    assert _counter(text, "duplicate_primary_mappings") == 0
