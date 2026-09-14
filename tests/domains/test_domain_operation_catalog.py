from __future__ import annotations

from cmm.agent_runtime.operation_execution_contracts import AgentOperationRequest
from cmm.agent_runtime.operation_registry import InMemoryAgentOperationRegistry
from cmm.domains import (
    INITIAL_DOMAIN_OPERATION_IDS,
    DomainOperationType,
    build_initial_domain_operation_catalog,
)

EXPECTED = {
    "general.read_resources",
    "general.prepare_structured_summary",
    "general.create_plan",
    "general.propose_memory_update",
    "health.prepare_medical_appointment",
    "health.build_symptom_timeline",
    "health.build_medication_timeline",
    "health.prepare_clinical_questions",
    "university.build_deadline_calendar",
    "university.assess_workload",
    "university.prepare_exam_plan",
    "university.prepare_academic_summary",
    "relationships.build_event_timeline",
    "relationships.separate_facts_interpretations",
    "relationships.prepare_reflection",
    "relationships.identify_needs_boundaries",
    "project.analyse_architecture",
    "project.create_implementation_plan",
    "project.run_validation",
    "project.prepare_change_review",
}


def test_catalog_contains_exactly_twenty_conservative_definitions() -> None:
    registry = build_initial_domain_operation_catalog(InMemoryAgentOperationRegistry())
    definitions = registry.list_definitions()
    assert len(definitions) == 20
    assert set(INITIAL_DOMAIN_OPERATION_IDS) == EXPECTED
    assert {item.operation_id for item in definitions} == EXPECTED
    assert all(item.version == "1.0.0" for item in definitions)
    assert all(
        item.operation_type
        not in {DomainOperationType.DESTRUCTIVE, DomainOperationType.EXTERNAL}
        for item in definitions
    )


def test_catalog_never_claims_unconfigured_deep_execution() -> None:
    registry = build_initial_domain_operation_catalog(InMemoryAgentOperationRegistry())
    for definition in registry.list_definitions():
        implementation = registry.get_implementation(
            definition.operation_id, definition.version
        )
        request = AgentOperationRequest(
            id=f"request:{definition.operation_id}",
            agent_run_id="run:catalog",
            workflow_id="workflow:catalog",
            task_id="task:catalog",
            operation_name=definition.operation_id,
            operation_version=definition.version,
            parameters={},
            idempotency_key=f"idem:{definition.operation_id}",
        )
        result = implementation.execute(request)
        assert result["success"] is True
        assert result["output"]["status"] in {"completed", "not_applicable"}
        if result["output"]["status"] == "completed":
            assert definition.operation_id in {
                "general.read_resources",
                "general.prepare_structured_summary",
            }


def test_catalog_builds_independent_registries_without_global_singleton() -> None:
    first = build_initial_domain_operation_catalog(InMemoryAgentOperationRegistry())
    second = build_initial_domain_operation_catalog(InMemoryAgentOperationRegistry())
    assert first is not second
    assert first.common_registry is not second.common_registry
