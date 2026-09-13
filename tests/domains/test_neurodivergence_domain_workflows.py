"""Tests for Phase 10.53 Neurodivergence Domain operations and workflows.

Task 3: eight declarative operations and eight shared-engine workflows.

Every workflow must use only canonical ``WorkflowNodeType`` values and must
never introduce a Neurodivergence workflow engine.  The sensitive-memory
workflow stops behind a real ``REQUEST_APPROVAL`` gate at a ``PROPOSE_MEMORY``
node: a proposal can never become a mutation, and no node type in this pack
performs a direct memory write.
"""

from __future__ import annotations

from cmm.domains.enums import DomainOperationType
from cmm.workflows.enums import WorkflowNodeType

EXPECTED_OPERATIONS = (
    "neurodivergence.analyze_differential_overlap",
    "neurodivergence.build_developmental_timeline",
    "neurodivergence.compare_assessment_sources",
    "neurodivergence.map_certainty_states",
    "neurodivergence.prepare_assessment_summary",
    "neurodivergence.propose_memory_update",
    "neurodivergence.review_evidence",
    "neurodivergence.review_functional_impact",
)

EXPECTED_WORKFLOWS = (
    "neurodivergence.developmental_history_review",
    "neurodivergence.evidence_consolidation_review",
    "neurodivergence.diagnostic_status_review",
    "neurodivergence.neuropsychological_assessment_preparation",
    "neurodivergence.assessment_result_integration",
    "neurodivergence.differential_overlap_review",
    "neurodivergence.functional_impact_review",
    "neurodivergence.sensitive_memory_proposal_review",
)

#: Minimum frozen input semantics per operation (plan Task 3, Step 2).
EXPECTED_REQUIRED_INPUTS = {
    "neurodivergence.build_developmental_timeline": ("source_refs", "periods"),
    "neurodivergence.review_evidence": ("evidence_refs", "objective"),
    "neurodivergence.compare_assessment_sources": ("source_refs",),
    "neurodivergence.map_certainty_states": ("claim_refs",),
    "neurodivergence.review_functional_impact": ("observation_refs", "domains"),
    "neurodivergence.analyze_differential_overlap": (
        "evidence_refs",
        "hypothesis_labels",
    ),
    "neurodivergence.prepare_assessment_summary": ("evidence_refs", "objective"),
    "neurodivergence.propose_memory_update": (
        "source_refs",
        "proposed_claim",
        "certainty_state",
    ),
}

#: Node types that would imply an autonomous mutation by a workflow.
_MUTATION_NODE_TYPES = frozenset(
    {
        WorkflowNodeType.PROPOSE_MEMORY,  # proposal only, never a write
    }
)

#: Second node id of each workflow after the canonical prefix.
EXPECTED_OPERATION_SEQUENCE = {
    "neurodivergence.developmental_history_review": (
        "neurodivergence.build_developmental_timeline",
    ),
    "neurodivergence.evidence_consolidation_review": (
        "neurodivergence.review_evidence",
        "neurodivergence.map_certainty_states",
    ),
    "neurodivergence.diagnostic_status_review": (
        "neurodivergence.map_certainty_states",
    ),
    "neurodivergence.neuropsychological_assessment_preparation": (
        "neurodivergence.review_evidence",
        "neurodivergence.compare_assessment_sources",
        "neurodivergence.prepare_assessment_summary",
    ),
    "neurodivergence.assessment_result_integration": (
        "neurodivergence.compare_assessment_sources",
        "neurodivergence.map_certainty_states",
    ),
    "neurodivergence.differential_overlap_review": (
        "neurodivergence.review_evidence",
        "neurodivergence.analyze_differential_overlap",
    ),
    "neurodivergence.functional_impact_review": (
        "neurodivergence.review_functional_impact",
    ),
    "neurodivergence.sensitive_memory_proposal_review": (
        "neurodivergence.propose_memory_update",
    ),
}


def _operations():
    from cmm.domains.neurodivergence.operations import (
        build_neurodivergence_operation_definitions,
    )

    return build_neurodivergence_operation_definitions()


def _workflows():
    from cmm.domains.neurodivergence.workflows import (
        build_neurodivergence_workflow_definitions,
    )

    return build_neurodivergence_workflow_definitions()


def _by_id(items, attribute: str):
    return {getattr(item, attribute): item for item in items}


# ═══════════════════════════════════════════════════════════════════════════════
# Operations
# ═══════════════════════════════════════════════════════════════════════════════


def test_eight_operations_are_declarative_and_canonical():
    operations = _operations()

    assert tuple(item.operation_id for item in operations) == EXPECTED_OPERATIONS
    assert len(operations) == 8
    assert all(item.domain_id == "domain:neurodivergence" for item in operations)
    assert all(item.version == "1.0.0" for item in operations)
    assert all(item.enabled is True for item in operations)
    # Declarative and fail-closed: no operation claims reversibility.
    assert all(item.reversible is False for item in operations)


def test_operations_never_embed_an_implementation_or_a_raw_source_body():
    for operation in _operations():
        assert not hasattr(operation, "implementation")
        assert not hasattr(operation, "executor")
        for schema in (operation.input_schema, operation.output_schema):
            properties = schema.get("properties", {})
            assert "body" not in properties
            assert "content" not in properties
            assert "text" not in properties


def test_operation_input_schemas_match_the_frozen_minimum_semantics():
    by_id = _by_id(_operations(), "operation_id")

    for operation_id, required in EXPECTED_REQUIRED_INPUTS.items():
        schema = by_id[operation_id].input_schema
        assert set(schema["required"]) == set(required), operation_id
        assert schema["additionalProperties"] is False
        for name in required:
            assert name in schema["properties"], (operation_id, name)


def test_propose_memory_update_is_proposal_only():
    by_id = _by_id(_operations(), "operation_id")
    operation = by_id["neurodivergence.propose_memory_update"]

    assert operation.operation_type is DomainOperationType.MEMORY
    assert operation.requires_approval is True
    assert operation.metadata["proposal_only"] is True
    assert operation.metadata["direct_memory_write"] is False
    # It carries the canonical certainty state so a proposal can never
    # silently upgrade a hypothesis.
    assert "certainty_state" in operation.input_schema["properties"]


def test_no_operation_is_destructive_or_autonomously_external():
    for operation in _operations():
        assert operation.operation_type is not DomainOperationType.DESTRUCTIVE
        assert operation.operation_type is not DomainOperationType.EXTERNAL
        assert operation.metadata["direct_memory_write"] is False
        assert operation.metadata["autonomous_external_action"] is False


def test_operations_that_touch_sensitive_assessment_material_require_approval():
    by_id = _by_id(_operations(), "operation_id")

    for operation_id in (
        "neurodivergence.propose_memory_update",
        "neurodivergence.prepare_assessment_summary",
    ):
        assert by_id[operation_id].requires_approval is True


# ═══════════════════════════════════════════════════════════════════════════════
# Workflows
# ═══════════════════════════════════════════════════════════════════════════════


def test_eight_workflows_use_only_shared_node_types():
    from cmm.domains.neurodivergence.catalog import (
        NEURODIVERGENCE_WORKFLOW_NAMES_BY_ID,
    )

    workflows = _workflows()

    assert tuple(item.workflow_id for item in workflows) == EXPECTED_WORKFLOWS
    assert len(workflows) == 8
    for workflow in workflows:
        assert workflow.domain_id == "domain:neurodivergence"
        assert workflow.version == "1.0.0"
        assert (
            workflow.name == NEURODIVERGENCE_WORKFLOW_NAMES_BY_ID[workflow.workflow_id]
        )
        assert workflow.sensitivity is not None
        for node in workflow.nodes:
            assert isinstance(node.node_type, WorkflowNodeType)


def test_every_workflow_starts_with_the_canonical_load_profile_reason_prefix():
    for workflow in _workflows():
        node_types = tuple(node.node_type for node in workflow.nodes[:3])
        assert node_types == (
            WorkflowNodeType.LOAD_RESOURCE,
            WorkflowNodeType.APPLY_PROFILE,
            WorkflowNodeType.REASON,
        ), workflow.workflow_id
        # The prefix is a real dependency chain, not three independent nodes.
        assert workflow.nodes[1].dependencies == (workflow.nodes[0].node_id,)
        assert workflow.nodes[2].dependencies == (workflow.nodes[1].node_id,)


def test_every_workflow_ends_in_complete_via_a_validate_node():
    for workflow in _workflows():
        nodes = _by_id(workflow.nodes, "node_id")
        complete = [
            node
            for node in workflow.nodes
            if node.node_type is WorkflowNodeType.COMPLETE
        ]
        assert len(complete) == 1, workflow.workflow_id
        # A terminal COMPLETE node must transitively depend on a VALIDATE node.
        reached: set[str] = set()
        frontier = list(complete[0].dependencies)
        while frontier:
            node_id = frontier.pop()
            if node_id in reached:
                continue
            reached.add(node_id)
            frontier.extend(nodes[node_id].dependencies)
        validate_ids = {
            node.node_id
            for node in workflow.nodes
            if node.node_type is WorkflowNodeType.VALIDATE
        }
        assert validate_ids & reached, workflow.workflow_id
        # Exactly one terminal step feeds COMPLETE.
        assert len(complete[0].dependencies) == 1, workflow.workflow_id


def test_workflow_operation_sequences_match_the_approved_plan():
    for workflow in _workflows():
        referenced = tuple(
            node.operation_id
            for node in workflow.nodes
            if node.operation_id is not None
        )
        assert referenced == EXPECTED_OPERATION_SEQUENCE[workflow.workflow_id], (
            workflow.workflow_id
        )


def test_workflows_reference_only_declared_operations_and_resources():
    from cmm.domains.neurodivergence.catalog import (
        NEURODIVERGENCE_OPERATION_IDS,
        NEURODIVERGENCE_RESOURCE_IDS,
    )

    for workflow in _workflows():
        for node in workflow.nodes:
            if node.operation_id is not None:
                assert node.operation_id in NEURODIVERGENCE_OPERATION_IDS
        for resource_id in workflow.required_resources:
            assert resource_id in NEURODIVERGENCE_RESOURCE_IDS


def test_operation_nodes_depend_on_the_reasoning_prefix():
    for workflow in _workflows():
        for node in workflow.nodes:
            if node.operation_id is None:
                continue
            reached: set[str] = set()
            frontier = list(node.dependencies)
            while frontier:
                node_id = frontier.pop()
                if node_id in reached:
                    continue
                reached.add(node_id)
                parent = next(
                    (item for item in workflow.nodes if item.node_id == node_id),
                    None,
                )
                if parent is not None:
                    frontier.extend(parent.dependencies)
            assert "reason" in reached, (workflow.workflow_id, node.node_id)


def test_diagnostic_status_review_maps_certainty_then_applies_health_authority():
    workflows = _by_id(_workflows(), "workflow_id")
    workflow = workflows["neurodivergence.diagnostic_status_review"]
    node_ids = tuple(node.node_id for node in workflow.nodes)

    assert "map_certainty" in node_ids
    assert "health_authority" in node_ids
    assert node_ids.index("map_certainty") < node_ids.index("health_authority")
    nodes = _by_id(workflow.nodes, "node_id")
    assert nodes["health_authority"].node_type is WorkflowNodeType.REASON
    assert nodes["health_authority"].dependencies == ("map_certainty",)
    assert workflow.metadata["health_authority_applied"] is True
    assert workflow.metadata["clinical_status_created"] is False


def test_sensitive_memory_workflow_is_proposal_only_and_approval_gated():
    workflows = _by_id(_workflows(), "workflow_id")
    workflow = workflows["neurodivergence.sensitive_memory_proposal_review"]
    nodes = _by_id(workflow.nodes, "node_id")

    assert nodes["approval"].node_type is WorkflowNodeType.REQUEST_APPROVAL
    assert nodes["propose"].node_type is WorkflowNodeType.PROPOSE_MEMORY
    assert nodes["propose"].dependencies == ("approval",)
    assert nodes["approval"].approval_gate
    assert workflow.metadata["proposal_only"] is True
    assert workflow.metadata["direct_mutation"] is False
    assert "neurodivergence.sensitive_memory_persistence" in workflow.approval_gates
    # The PROPOSE_MEMORY node is the only mutation-adjacent node in the pack,
    # and no node performs a direct memory write.
    for item in _workflows():
        for node in item.nodes:
            if node.node_type in _MUTATION_NODE_TYPES:
                assert item.workflow_id == (
                    "neurodivergence.sensitive_memory_proposal_review"
                )
                assert node.node_type is WorkflowNodeType.PROPOSE_MEMORY


def test_workflows_do_not_autonomously_diagnose_or_communicate_externally():
    for workflow in _workflows():
        assert workflow.enabled is True
        assert workflow.metadata["phase"] == "10.53"
        assert workflow.metadata.get("autonomous_diagnosis") is not True
        assert workflow.metadata.get("external_communication") is not True
        for node in workflow.nodes:
            assert node.node_type is not WorkflowNodeType.INVOKE_SUBWORKFLOW


def test_workflows_declare_no_supporting_domain_implementation_dependency():
    """Cross-domain support stays registry/permission-driven, not an import."""
    for workflow in _workflows():
        assert workflow.supporting_domain_ids == ()
        assert workflow.metadata["cross_domain_support_required"] is False
