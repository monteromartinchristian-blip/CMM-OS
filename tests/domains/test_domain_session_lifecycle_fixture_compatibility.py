"""Phase 10.36 BLOCKER-01 — historical fixture roadmap-label compatibility.

The Phase 10.34 portable lifecycle fixture rewrites a temporary copy of the
current repository ``ROADMAP.md`` into the historical Phase 10.34 documented
state. The rewriter originally accepted only the historical marker
``**Implemented through:**``. The canonical roadmap label later evolved to
``**Implemented and audited through:**`` (Phase 10.35 closure), which made the
strict rewriter fail closed before any Phase 10.34 acceptance/audit regression
could execute.

These regressions prove the helper accepts exactly the two canonical labels,
remains fail-closed for unrelated wording, preserves exactly-one-match
semantics, and never mutates the source repository ``ROADMAP.md``.
"""

from __future__ import annotations

import re
import shutil
from pathlib import Path

import pytest

from tests.domains.domain_session_lifecycle_test_support import (
    COMPLETE,
    PENDING,
    REPO_ROOT,
    _replace_once,
    set_phase_10_34_documented_state,
)

IMPLEMENTED_THROUGH_OLD = "**Implemented through:**"
IMPLEMENTED_THROUGH_NEW = "**Implemented and audited through:**"

# The compatibility contract: exactly the two canonical labels, nothing else.
COMPATIBILITY_PATTERN = r"^\*\*Implemented(?: and audited)? through:\*\*.*$"

FIXTURE_ROADMAP_FILES = (
    "ROADMAP.md",
    "docs/reference/domain-sessions.md",
    "docs/reference/domain-intelligence-requirements-matrix.md",
    "docs/roadmap/phase-10-domain-intelligence.md",
)


def _minimal_archive(tmp_path: Path) -> Path:
    """Minimal portable archive containing only the files the helper rewrites."""
    archive_root = tmp_path / "CMM-OS-phase-10.34"
    for relative in FIXTURE_ROADMAP_FILES:
        destination = archive_root / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(REPO_ROOT / relative, destination)
    return archive_root


# ── _replace_once compatibility contract ────────────────────────────────────


def test_replace_once_accepts_historical_implemented_through_marker(
    tmp_path: Path,
) -> None:
    path = tmp_path / "ROADMAP.md"
    path.write_text(
        f"{IMPLEMENTED_THROUGH_OLD} Phase 10.34 — Domain Sessions.\n",
        encoding="utf-8",
    )
    _replace_once(path, COMPATIBILITY_PATTERN, "rewritten")
    assert path.read_text(encoding="utf-8") == "rewritten\n"


def test_replace_once_accepts_current_implemented_and_audited_marker(
    tmp_path: Path,
) -> None:
    path = tmp_path / "ROADMAP.md"
    path.write_text(
        f"{IMPLEMENTED_THROUGH_NEW} Phase 10.35 — Domain SDK.\n",
        encoding="utf-8",
    )
    _replace_once(path, COMPATIBILITY_PATTERN, "rewritten")
    assert path.read_text(encoding="utf-8") == "rewritten\n"


def test_replace_once_fails_closed_for_unrelated_through_wording(
    tmp_path: Path,
) -> None:
    path = tmp_path / "ROADMAP.md"
    original = "**Planned through:** Phase 10.99 — Future Work.\n"
    path.write_text(original, encoding="utf-8")
    with pytest.raises(AssertionError, match="not found exactly once"):
        _replace_once(path, COMPATIBILITY_PATTERN, "rewritten")
    assert path.read_text(encoding="utf-8") == original


def test_replace_once_fails_closed_for_implemented_and_audited_without_through(
    tmp_path: Path,
) -> None:
    """The compatibility regex must not over-generalize to sibling labels."""
    path = tmp_path / "ROADMAP.md"
    original = (
        "**Implemented and audited:** Phases 0–9 plus Phase 10 through 10.35<br>\n"
    )
    path.write_text(original, encoding="utf-8")
    with pytest.raises(AssertionError, match="not found exactly once"):
        _replace_once(path, COMPATIBILITY_PATTERN, "rewritten")
    assert path.read_text(encoding="utf-8") == original


def test_replace_once_fails_closed_for_missing_marker(tmp_path: Path) -> None:
    path = tmp_path / "ROADMAP.md"
    original = "No roadmap marker on this line.\n"
    path.write_text(original, encoding="utf-8")
    with pytest.raises(AssertionError, match="not found exactly once"):
        _replace_once(path, COMPATIBILITY_PATTERN, "rewritten")
    assert path.read_text(encoding="utf-8") == original


def test_replace_once_replaces_only_the_first_match(tmp_path: Path) -> None:
    """count=1 semantics are preserved: exactly one replacement, first match."""
    path = tmp_path / "ROADMAP.md"
    path.write_text(
        f"{IMPLEMENTED_THROUGH_NEW} first\n{IMPLEMENTED_THROUGH_NEW} second\n",
        encoding="utf-8",
    )
    _replace_once(path, COMPATIBILITY_PATTERN, "rewritten")
    assert (
        path.read_text(encoding="utf-8")
        == f"rewritten\n{IMPLEMENTED_THROUGH_NEW} second\n"
    )


def test_replace_once_rewrites_only_the_marker_line(tmp_path: Path) -> None:
    path = tmp_path / "ROADMAP.md"
    path.write_text(
        f"before\n{IMPLEMENTED_THROUGH_NEW} Phase 10.35 — Domain SDK.\nafter\n",
        encoding="utf-8",
    )
    _replace_once(path, COMPATIBILITY_PATTERN, "rewritten")
    assert path.read_text(encoding="utf-8") == "before\nrewritten\nafter\n"


# ── Current repository roadmap compatibility ────────────────────────────────


def test_current_repo_roadmap_has_exactly_one_compatibility_marker() -> None:
    text = (REPO_ROOT / "ROADMAP.md").read_text(encoding="utf-8")
    matches = re.findall(COMPATIBILITY_PATTERN, text, flags=re.MULTILINE)
    assert len(matches) == 1
    assert matches[0].startswith(IMPLEMENTED_THROUGH_NEW)


# ── Full portable fixture from the current repository state ─────────────────


def test_portable_fixture_complete_state_from_current_roadmap_label(
    tmp_path: Path,
) -> None:
    archive_root = _minimal_archive(tmp_path)
    set_phase_10_34_documented_state(archive_root, status=COMPLETE)
    roadmap = (archive_root / "ROADMAP.md").read_text(encoding="utf-8")
    assert "**Implemented through:** Phase 10.34 — Domain Sessions" in roadmap
    assert IMPLEMENTED_THROUGH_NEW not in roadmap


def test_portable_fixture_pending_state_from_current_roadmap_label(
    tmp_path: Path,
) -> None:
    archive_root = _minimal_archive(tmp_path)
    set_phase_10_34_documented_state(
        archive_root, status=PENDING, pending_audit_version=11
    )
    roadmap = (archive_root / "ROADMAP.md").read_text(encoding="utf-8")
    assert "**Implemented through:** Phase 10.34 — Domain Sessions" in roadmap
    assert "independent re-audit V11 pending" in roadmap
    assert IMPLEMENTED_THROUGH_NEW not in roadmap


def test_portable_fixture_does_not_mutate_source_roadmap(
    tmp_path: Path,
) -> None:
    source_roadmap = REPO_ROOT / "ROADMAP.md"
    before = source_roadmap.read_bytes()
    archive_root = _minimal_archive(tmp_path)
    set_phase_10_34_documented_state(archive_root, status=COMPLETE)
    assert source_roadmap.read_bytes() == before
