"""Phase 10.23 — University → Oppositions minimal projection tests (§43)."""

from __future__ import annotations

import pathlib

from cmm.domains import oppositions
from cmm.domains.oppositions.rules import evaluate_study_feasibility


def test_oppositions_package_never_reads_university_store_directly():
    package_dir = pathlib.Path(oppositions.__file__).resolve().parent
    coupling_markers = (
        "import cmm.domains.university",
        "from cmm.domains.university",
        "university_registry",
        "university_resource",
        "AcademicDeadlineRule",
        "AcademicSourceAuthorityRule",
        "AcademicWorkloadRule",
    )
    for module in package_dir.glob("*.py"):
        src = module.read_text(encoding="utf-8")
        for marker in coupling_markers:
            assert marker not in src, (
                f"{module.name} directly couples to a University store/semantics "
                f"via {marker!r}"
            )


def test_only_authorized_availability_load_deadline_projection_consumed():
    record = evaluate_study_feasibility(
        remaining_hours=20,
        available_hours=30,
        university_projection={
            "authorized": True,
            "available_hours": 10,
            "workload_hours": 4,
            "subject_notes": ["unrelated detail"],  # must not be consumed
        },
    )
    assert record["university_authorized"] is True
    # capacity narrowed to the authorized availability minus workload
    assert record["capacity_hours"] == min(30, 10) - 4
    assert record["university_state_merged"] is False


def test_unrelated_academic_payload_rejected_not_consumed():
    record = evaluate_study_feasibility(
        remaining_hours=20,
        available_hours=30,
        university_projection={"authorized": True, "available_hours": 10},
    )
    assert record["university_authorized"] is True


def test_malformed_projection_remains_unresolved():
    record = evaluate_study_feasibility(
        remaining_hours=20,
        available_hours=30,
        university_projection={"authorized": 1, "available_hours": 10},
    )
    assert record["university_authorized"] is False


def test_malformed_authorized_workload_fails_closed():
    record = evaluate_study_feasibility(
        remaining_hours=8,
        available_hours=10,
        university_projection={"authorized": True, "workload_hours": "many"},
    )
    assert record["university_authorized"] is True
    assert record["capacity_unknown"] is True
    assert record["feasible"] is False
    assert record["unresolved"] is True


def test_valid_availability_malformed_workload_unresolved():
    record = evaluate_study_feasibility(
        remaining_hours=8,
        available_hours=10,
        university_projection={
            "authorized": True,
            "available_hours": 6,
            "workload_hours": "many",
        },
    )
    assert record["capacity_unknown"] is True
    assert record["unresolved"] is True


def test_malformed_availability_valid_workload_unresolved():
    record = evaluate_study_feasibility(
        remaining_hours=8,
        available_hours=10,
        university_projection={
            "authorized": True,
            "available_hours": "many",
            "workload_hours": 2,
        },
    )
    assert record["capacity_unknown"] is True
    assert record["unresolved"] is True


def test_most_restrictive_policy_wins():
    # Health cap 15, University availability 10 -> most restrictive wins
    record = evaluate_study_feasibility(
        remaining_hours=20,
        available_hours=30,
        health_constraint={"authorized": True, "functional_cap_hours": 15},
        university_projection={"authorized": True, "available_hours": 10},
    )
    assert record["capacity_hours"] == 10


def test_supporting_domain_cannot_widen_permissions():
    policy = oppositions.build_oppositions_permission_policy()
    assert policy.allow_export is False
    assert policy.allow_memory_write is False
