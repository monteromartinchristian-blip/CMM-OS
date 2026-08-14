"""Phase 10.23 — Opposition Domain package audit.

Confirms the canonical 14-module boundary and the exact canonical counts and
identifiers, and that no forbidden parallel infrastructure was introduced.
"""

from __future__ import annotations

import pathlib

from cmm.domains.oppositions.catalog import (
    CANONICAL_OPPOSITION_ENTITY_TYPES,
    CANONICAL_OPPOSITION_OPERATION_IDS,
    CANONICAL_OPPOSITION_RESOURCE_IDS,
    CANONICAL_OPPOSITION_RULE_IDS,
    CANONICAL_OPPOSITION_WORKFLOW_IDS,
)

EXPECTED_MODULES = (
    "__init__.py",
    "bootstrap.py",
    "catalog.py",
    "definition.py",
    "integration.py",
    "memory.py",
    "operations.py",
    "permissions.py",
    "presentation.py",
    "profile.py",
    "resources.py",
    "rules.py",
    "trace.py",
    "workflows.py",
)

FORBIDDEN_PARALLEL_INFRASTRUCTURE = (
    "OppositionMemoryStore",
    "OppositionKnowledgeStore",
    "OppositionVectorStore",
    "OppositionGraphStore",
    "OppositionReasoningEngine",
    "OppositionProfileRegistry",
    "OppositionWorkflowEngine",
    "OppositionPermissionGate",
    "OppositionSourceResolver",
    "OppositionTemporalEngine",
    "OppositionExternalSearchClient",
    "OppositionScheduler",
    "OppositionNotifier",
    "OppositionCalendarEngine",
    "OppositionTaskEngine",
)


def test_exact_14_module_boundary():
    """The package follows the shared 14-module specialized-domain boundary."""
    import cmm.domains.oppositions as _pkg

    package_dir = pathlib.Path(_pkg.__file__).resolve().parent
    modules = {p.name for p in package_dir.glob("*.py")}
    for expected in EXPECTED_MODULES:
        assert expected in modules, f"Missing canonical module {expected}"


def test_no_forbidden_parallel_infrastructure():
    """No forbidden parallel subsystem exists in the package."""
    import pathlib

    package_dir = pathlib.Path(__file__).resolve().parents[3] / "cmm" / "domains" / "oppositions"
    concatenated = "\n".join(p.read_text(encoding="utf-8") for p in package_dir.glob("*.py"))
    for name in FORBIDDEN_PARALLEL_INFRASTRUCTURE:
        assert f"class {name}" not in concatenated, (
            f"Forbidden parallel infrastructure {name} declared"
        )


def test_exact_canonical_counts():
    """Exact contractual counts: 14 entities, 11 resources, 6 rules, 10 ops, 7 workflows."""
    assert len(CANONICAL_OPPOSITION_ENTITY_TYPES) == 14
    assert len(CANONICAL_OPPOSITION_RESOURCE_IDS) == 11
    assert len(CANONICAL_OPPOSITION_RULE_IDS) == 6
    assert len(CANONICAL_OPPOSITION_OPERATION_IDS) == 10
    assert len(CANONICAL_OPPOSITION_WORKFLOW_IDS) == 7


def test_entity_types_exact():
    """The 14 canonical entity semantics are exact."""
    assert set(CANONICAL_OPPOSITION_ENTITY_TYPES) == {
        "opposition",
        "public_body",
        "call",
        "exam",
        "syllabus",
        "topic",
        "block",
        "mock_exam",
        "score",
        "study_session",
        "deadline",
        "requirement",
        "merit",
        "alternative_route",
    }


def test_no_duplicate_ids():
    """No duplicate IDs within any canonical set."""
    assert len(CANONICAL_OPPOSITION_OPERATION_IDS) == len(
        set(CANONICAL_OPPOSITION_OPERATION_IDS)
    )
    assert len(CANONICAL_OPPOSITION_RULE_IDS) == len(
        set(CANONICAL_OPPOSITION_RULE_IDS)
    )
    assert len(CANONICAL_OPPOSITION_RESOURCE_IDS) == len(
        set(CANONICAL_OPPOSITION_RESOURCE_IDS)
    )
    assert len(CANONICAL_OPPOSITION_WORKFLOW_IDS) == len(
        set(CANONICAL_OPPOSITION_WORKFLOW_IDS)
    )
    assert len(CANONICAL_OPPOSITION_ENTITY_TYPES) == len(
        set(CANONICAL_OPPOSITION_ENTITY_TYPES)
    )


def test_operation_prefix():
    """Every canonical operation uses the ``oppositions.`` domain prefix."""
    for operation_id in CANONICAL_OPPOSITION_OPERATION_IDS:
        assert operation_id.startswith("oppositions."), operation_id


def test_rule_prefix():
    """Every canonical rule uses the ``oppositions.`` domain prefix."""
    for rule_id in CANONICAL_OPPOSITION_RULE_IDS:
        assert rule_id.startswith("oppositions."), rule_id


def test_workflow_prefix():
    """Every canonical workflow uses the ``oppositions.`` domain prefix."""
    for workflow_id in CANONICAL_OPPOSITION_WORKFLOW_IDS:
        assert workflow_id.startswith("oppositions."), workflow_id


def test_resource_prefix():
    """Every canonical resource uses the ``oppositions.`` prefix."""
    for resource_id in CANONICAL_OPPOSITION_RESOURCE_IDS:
        assert resource_id.startswith("oppositions."), resource_id


def test_canonical_order_deterministic():
    """Canonical sets are in deterministic sorted order."""
    assert CANONICAL_OPPOSITION_OPERATION_IDS == tuple(
        sorted(CANONICAL_OPPOSITION_OPERATION_IDS)
    )
    assert CANONICAL_OPPOSITION_RULE_IDS == tuple(
        sorted(CANONICAL_OPPOSITION_RULE_IDS)
    )
    assert CANONICAL_OPPOSITION_RESOURCE_IDS == tuple(
        sorted(CANONICAL_OPPOSITION_RESOURCE_IDS)
    )
    assert CANONICAL_OPPOSITION_WORKFLOW_IDS == tuple(
        sorted(CANONICAL_OPPOSITION_WORKFLOW_IDS)
    )
    assert CANONICAL_OPPOSITION_ENTITY_TYPES == tuple(
        sorted(CANONICAL_OPPOSITION_ENTITY_TYPES)
    )