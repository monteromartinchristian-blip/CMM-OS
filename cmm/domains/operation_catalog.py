"""Conservative initial catalog for Phase 10.13."""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Any

from cmm.agent_runtime.enums import PolicyRiskLevel
from cmm.agent_runtime.operation_execution_contracts import AgentOperationRequest
from cmm.agent_runtime.operation_registry import AgentOperationRegistry
from cmm.domains.enums import DomainOperationType
from cmm.domains.operation_contracts import DomainOperationDefinition
from cmm.domains.operation_registry import InMemoryDomainOperationRegistry

INITIAL_DOMAIN_OPERATION_IDS = (
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
)


_SAFE_EXECUTABLE = frozenset(
    {
        "general.read_resources",
        "general.prepare_structured_summary",
    }
)


_TYPE_BY_ID = MappingProxyType(
    {
        "general.read_resources": DomainOperationType.READ,
        "general.prepare_structured_summary": DomainOperationType.PREPARATION,
        "general.create_plan": DomainOperationType.PLANNING,
        "general.propose_memory_update": DomainOperationType.MEMORY,
        "health.prepare_medical_appointment": DomainOperationType.SENSITIVE,
        "health.build_symptom_timeline": DomainOperationType.ANALYSIS,
        "health.build_medication_timeline": DomainOperationType.ANALYSIS,
        "health.prepare_clinical_questions": DomainOperationType.SENSITIVE,
        "university.build_deadline_calendar": DomainOperationType.PLANNING,
        "university.assess_workload": DomainOperationType.ANALYSIS,
        "university.prepare_exam_plan": DomainOperationType.PLANNING,
        "university.prepare_academic_summary": DomainOperationType.PREPARATION,
        "relationships.build_event_timeline": DomainOperationType.ANALYSIS,
        "relationships.separate_facts_interpretations": DomainOperationType.ANALYSIS,
        "relationships.prepare_reflection": DomainOperationType.PREPARATION,
        "relationships.identify_needs_boundaries": DomainOperationType.SENSITIVE,
        "project.analyse_architecture": DomainOperationType.ANALYSIS,
        "project.create_implementation_plan": DomainOperationType.PLANNING,
        "project.run_validation": DomainOperationType.ANALYSIS,
        "project.prepare_change_review": DomainOperationType.PREPARATION,
    }
)


def _definition(operation_id: str) -> DomainOperationDefinition:
    slug, operation_name = operation_id.split(".", 1)
    operation_type = _TYPE_BY_ID[operation_id]
    is_sensitive = operation_type is DomainOperationType.SENSITIVE
    return DomainOperationDefinition(
        operation_id=operation_id,
        domain_id=f"domain:{slug}",
        version="1.0.0",
        name=operation_name.replace("_", " ").title(),
        description=f"Conservative structured operation for {operation_id}.",
        operation_type=operation_type,
        input_schema={"type": "object"},
        output_schema={
            "type": "object",
            "required": ["status", "operation_id"],
            "properties": {
                "status": {"type": "string", "enum": ["completed", "not_applicable"]},
                "operation_id": {"type": "string"},
                "reason_code": {"type": "string"},
                "resources": {"type": "array"},
                "items": {"type": "array"},
            },
            "additionalProperties": True,
        },
        risk_level=(
            PolicyRiskLevel.HIGH
            if slug == "health" or is_sensitive
            else PolicyRiskLevel.MEDIUM
            if slug == "relationships"
            else PolicyRiskLevel.LOW
        ),
        requires_approval=is_sensitive,
        enabled=True,
        metadata={
            "catalog": "phase-10.13",
            "demonstration": True,
            "deep_capability_configured": operation_id in _SAFE_EXECUTABLE,
        },
    )


@dataclass
class _CatalogImplementation:
    definition: DomainOperationDefinition

    def execute(self, request: AgentOperationRequest) -> dict[str, Any]:
        if self.definition.operation_id == "general.read_resources":
            raw_resources = request.parameters.get("resources", ())
            resources = (
                list(raw_resources) if isinstance(raw_resources, (tuple, list)) else []
            )
            output = {
                "status": "completed",
                "operation_id": self.definition.operation_id,
                "resources": resources,
            }
        elif self.definition.operation_id == "general.prepare_structured_summary":
            raw_items = request.parameters.get("items", ())
            items = list(raw_items) if isinstance(raw_items, (tuple, list)) else []
            output = {
                "status": "completed",
                "operation_id": self.definition.operation_id,
                "items": items,
            }
        else:
            output = {
                "status": "not_applicable",
                "operation_id": self.definition.operation_id,
                "reason_code": "capability_not_configured",
            }
        return {"success": True, "output": output, "effects": ()}


def build_initial_domain_operation_catalog(
    common_registry: AgentOperationRegistry,
) -> InMemoryDomainOperationRegistry:
    registry = InMemoryDomainOperationRegistry(common_registry)
    for operation_id in INITIAL_DOMAIN_OPERATION_IDS:
        definition = _definition(operation_id)
        registry.register(definition, _CatalogImplementation(definition))
    return registry


__all__ = ["INITIAL_DOMAIN_OPERATION_IDS", "build_initial_domain_operation_catalog"]
