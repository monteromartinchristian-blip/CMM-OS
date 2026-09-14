"""Phase 10.23 — Health → Oppositions minimal projection tests (§43)."""

from __future__ import annotations

import pathlib

from cmm.domains import oppositions
from cmm.domains.oppositions.rules import evaluate_study_feasibility


def test_oppositions_package_never_reads_health_store_directly():
    package_dir = pathlib.Path(oppositions.__file__).resolve().parent
    coupling_markers = (
        "import cmm.domains.health",
        "from cmm.domains.health",
        "health_registry",
        "health_resource",
        "HealthResolver",
        "HealthMemoryStore",
    )
    for module in package_dir.glob("*.py"):
        src = module.read_text(encoding="utf-8")
        for marker in coupling_markers:
            assert marker not in src, (
                f"{module.name} directly couples to a Health store via {marker!r}"
            )


def test_only_authorized_minimal_functional_constraint_consumed():
    record = evaluate_study_feasibility(
        remaining_hours=20,
        available_hours=30,
        health_constraint={
            "authorized": True,
            "functional_cap_hours": 15,
            "diagnosis": "x",  # unrelated detail must not be consumed/emitted
            "medication": ["y"],  # unrelated clinical detail
        },
    )
    # minimal functional constraint applied, clinical detail never emitted
    assert record["health_authorized"] is True
    assert record["capacity_hours"] == 15
    assert record["clinical_details_consumed"] is False


def test_strict_boolean_authorization():
    """``"true"``/``"false"``/``1``/``0`` never authorize transfer."""
    for bad in ("true", "false", 1, 0):
        record = evaluate_study_feasibility(
            remaining_hours=20,
            available_hours=30,
            health_constraint={"authorized": bad, "functional_cap_hours": 5},
        )
        assert record["health_authorized"] is False, bad


def test_malformed_authorized_cap_fails_closed():
    # authorized is literally True but the cap is malformed -> unknown, not
    # permissive.
    record = evaluate_study_feasibility(
        remaining_hours=20,
        available_hours=30,
        health_constraint={"authorized": True, "functional_cap_hours": "many"},
    )
    assert record["capacity_unknown"] is True


def test_health_cap_cannot_widen_known_availability():
    """A supporting-domain Health cap must never widen a known primary-domain
    capacity (most-restrictive constraint wins)."""
    record = evaluate_study_feasibility(
        remaining_hours=12,
        available_hours=10,
        health_constraint={
            "authorized": True,
            "functional_cap_hours": 15,
        },
    )
    # known availability (10) is more restrictive than the looser Health cap
    # (15); the effective capacity must stay at 10 and the plan infeasible.
    assert record["capacity_hours"] == 10
    assert record["infeasible"] is True


def test_health_cap_can_narrow_capacity():
    """An authorized Health cap below known availability narrows capacity."""
    record = evaluate_study_feasibility(
        remaining_hours=5,
        available_hours=10,
        health_constraint={"authorized": True, "functional_cap_hours": 6},
    )
    assert record["capacity_hours"] == 6


def test_health_cannot_widen_opposition_permissions():
    policy = oppositions.build_oppositions_permission_policy()
    from cmm.agent_runtime.domain_permission_contracts import PermissionCapability

    assert PermissionCapability.MEMORY_WRITE in policy.prohibited_capabilities
    assert PermissionCapability.SENSITIVE_INFERENCE in policy.prohibited_capabilities
    assert policy.allow_inbound_cross_domain_access is True


def test_wider_health_cap_does_not_change_binding_source():
    """A non-binding (wider) Health cap must not claim provenance: the binding
    constraint is still the user capacity."""
    record = evaluate_study_feasibility(
        remaining_hours=5,
        available_hours=8,
        health_constraint={"authorized": True, "functional_cap_hours": 20},
    )
    assert record["capacity_hours"] == 8
    assert record["capacity_source"] == "user"


def test_equal_health_cap_keeps_primary_source():
    """Equal caps use a deterministic convention: primary (user) source wins."""
    record = evaluate_study_feasibility(
        remaining_hours=5,
        available_hours=8,
        health_constraint={"authorized": True, "functional_cap_hours": 8},
    )
    assert record["capacity_hours"] == 8
    assert record["capacity_source"] == "user"
