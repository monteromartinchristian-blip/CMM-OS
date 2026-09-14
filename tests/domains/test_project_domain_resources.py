"""Phase 10.30 — Project Domain Resources Tests."""

from __future__ import annotations

import pytest

from cmm.domains.project.catalog import (
    CANONICAL_PROJECT_RESOURCE_IDS,
    CANONICAL_PROJECT_RESOURCE_KINDS,
)
from cmm.domains.project.resources import (
    GENERIC_PROJECT_RESOURCE_KINDS,
    PROJECT_DECISION_STATE_VALUES,
    PROJECT_STATUS_VALUES,
    SOFTWARE_PROJECT_RESOURCE_KINDS,
    build_project_resource_definitions,
    validate_project_decision_state,
    validate_project_status,
)


def test_build_project_resource_definitions() -> None:
    resources = build_project_resource_definitions()
    assert len(resources) == 22
    assert tuple(r.id for r in resources) == CANONICAL_PROJECT_RESOURCE_IDS
    assert all(str(r.domain_id) == "domain:project" for r in resources)
    assert len({r.id for r in resources}) == 22


def test_generic_and_software_resource_partition() -> None:
    assert len(GENERIC_PROJECT_RESOURCE_KINDS) == 10
    assert len(SOFTWARE_PROJECT_RESOURCE_KINDS) == 12
    assert set(GENERIC_PROJECT_RESOURCE_KINDS) | set(
        SOFTWARE_PROJECT_RESOURCE_KINDS
    ) == set(CANONICAL_PROJECT_RESOURCE_KINDS)
    assert not (
        set(GENERIC_PROJECT_RESOURCE_KINDS) & set(SOFTWARE_PROJECT_RESOURCE_KINDS)
    )

    assert "source_code" in SOFTWARE_PROJECT_RESOURCE_KINDS
    assert "project_brief" in GENERIC_PROJECT_RESOURCE_KINDS
    assert "git_history" in SOFTWARE_PROJECT_RESOURCE_KINDS
    assert "milestone_record" in GENERIC_PROJECT_RESOURCE_KINDS


def test_project_status_validation() -> None:
    expected_statuses = (
        "planned",
        "active",
        "blocked",
        "paused",
        "completed",
        "failed",
        "cancelled",
    )
    assert PROJECT_STATUS_VALUES == expected_statuses

    for s in expected_statuses:
        assert validate_project_status(s) == s

    with pytest.raises(ValueError, match="Invalid project status"):
        validate_project_status("mostly_done")

    with pytest.raises(ValueError):
        validate_project_status("ACTIVE")  # strict, no auto-normalization


def test_project_decision_state_validation() -> None:
    expected_states = (
        "option",
        "proposal",
        "decided",
        "approved",
        "applied",
        "rejected",
        "deferred",
        "cancelled",
    )
    assert PROJECT_DECISION_STATE_VALUES == expected_states

    for st in expected_states:
        assert validate_project_decision_state(st) == st

    with pytest.raises(ValueError, match="Invalid project decision state"):
        validate_project_decision_state("in_progress")
