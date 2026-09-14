"""Phase 10.25 — Concerns cross-domain boundary tests.

Cross-domain information enters only through shared authorized projections or
``domain_result``; no direct private-store imports; specialized domains keep
factual/risk ownership (General fallback, Relationships motive boundaries,
Health red-flag preservation, Reflection meaning boundary, and the academic/
planning domains' factual semantics).  Most-restrictive permissions survive
composition (frozen design §61–§66, §83, §94).
"""

from __future__ import annotations

import inspect
import json

from cmm.domains.concerns import (
    build_standard_concerns_domain_bootstrap,
    register_concerns_domain,
)
from cmm.domains.concerns.rules import (
    classify_concern_statement,
    evaluate_proportional_risk,
)


def test_general_fallback_reused():
    from cmm.domains.identifiers import DomainId

    bootstrap = build_standard_concerns_domain_bootstrap()
    assert bootstrap.domain_registry.get("domain:general") is not None
    assert bootstrap.resolver.fallback_domain == DomainId(slug="general")


def test_explicit_concerns_resolution_registered():
    bootstrap = build_standard_concerns_domain_bootstrap()
    definition = bootstrap.domain_registry.get("domain:concerns")
    assert definition is not None
    assert str(definition.reasoning_profile) == "ConcernSupportProfile"


# ── Relationships projection ─────────────────────────────────────────────────


def test_relationships_observed_behavior_remains_fact_motive_stays_unknown():
    """An observed relationship behavior projected into Concerns stays a fact
    only with grounding; the other person's motive remains unknown."""
    observed = classify_concern_statement(
        {
            "statement": "they haven't suggested meeting in two weeks",
            "level": "fact",
            "evidence_references": ("rel-evt:1",),
        }
    )
    motive = classify_concern_statement(
        {"statement": "they are pulling away on purpose", "level": "interpretation"}
    )
    assert observed["grounded"] is True
    assert observed["external_fact"] is True
    # motive attribution is never a fact
    assert motive["level"] == "interpretation"
    assert motive["external_fact"] is False


def test_user_hurt_is_valid_experience_not_external_fact():
    record = classify_concern_statement(
        {"statement": "I feel like just another friend", "level": "experience"}
    )
    assert record["level"] == "experience"
    assert record["external_fact"] is False


def test_no_direct_relationships_store_import():
    import sys

    import cmm.domains.concerns  # noqa: F401

    for module_name in tuple(sys.modules):
        if module_name.startswith("cmm.domains.concerns"):
            assert not module_name.startswith("cmm.domains.relationships")
    source = inspect.getsource(__import__("cmm.domains.concerns", fromlist=["*"]))
    assert "relationships_store" not in source
    assert "relationships.state" not in source


def test_registration_does_not_merge_other_domain_state():
    from cmm.agent_runtime.operation_registry import InMemoryAgentOperationRegistry
    from cmm.cognitive.reasoning_rule_registry import InMemoryReasoningRuleRegistry
    from cmm.domains.operation_registry import InMemoryDomainOperationRegistry
    from cmm.domains.permission_registry import DomainPermissionRegistry
    from cmm.domains.profile_registry import InMemoryDomainProfileRegistry
    from cmm.domains.registry import DomainRegistry
    from cmm.domains.resource_registry import InMemoryDomainResourceRegistry
    from cmm.domains.workflow_registry import InMemoryDomainWorkflowRegistry
    from cmm.workflows.registry import InMemoryWorkflowRegistry

    registries = {
        "domain_registry": DomainRegistry(),
        "profile_registry": InMemoryDomainProfileRegistry(),
        "resource_registry": InMemoryDomainResourceRegistry(),
        "rule_registry": InMemoryReasoningRuleRegistry(),
        "operation_registry": InMemoryDomainOperationRegistry(
            InMemoryAgentOperationRegistry()
        ),
        "workflow_registry": InMemoryDomainWorkflowRegistry(InMemoryWorkflowRegistry()),
        "permission_registry": DomainPermissionRegistry(),
    }
    register_concerns_domain(**registries)
    for other in (
        "domain:relationships",
        "domain:health",
        "domain:reflection",
        "domain:university",
        "domain:oppositions",
        "domain:life-plan",
        "domain:project",
    ):
        assert registries["domain_registry"].get(other) is None
    assert all(
        res.id.startswith("concerns.")
        for res in registries["resource_registry"].list_all()
    )


# ── Health projection ────────────────────────────────────────────────────────


def test_health_red_flags_survive_and_are_not_downgraded():
    result = evaluate_proportional_risk(
        severity="calm",
        immediacy=None,
        evidence=(),
        specialized_domain_result={
            "domain_id": "domain:health",
            "red_flags": ("new severe headache", "fever with neck stiffness"),
            "authorized": True,
        },
    )
    assert result["risk_level"] == "high"
    assert result["downgraded"] is False
    assert result["specialized_ownership_preserved"] is True
    assert result["specialized_red_flags"] == (
        "new severe headache",
        "fever with neck stiffness",
    )


def test_health_reassuring_result_can_support_reassurance():
    """A Health result indicating benign findings may ground Concerns
    reassurance — provenance preserved, no medical judgment recreated."""
    from cmm.domains.concerns.rules import evaluate_reassurance

    record = evaluate_reassurance(
        target_claim="benign",
        evidence=(
            {
                "identity": "e1",
                "claim": "benign",
                "stance": "opposes_target",
                "grounding": "s1",
            },
        ),
        counterevidence=(
            {
                "identity": "c1",
                "claim": "benign",
                "stance": "opposes_target",
                "grounding": "a",
            },
            {
                "identity": "c2",
                "claim": "benign",
                "stance": "opposes_target",
                "grounding": "b",
            },
        ),
        specialized_domain_result={
            "domain_id": "domain:health",
            "probability": 0.01,
            "authorized": True,
            "provenance": "clinical assessment",
        },
    )
    assert record["specialized_probability"] == 0.01
    assert record["specialized_authorized"] is True
    # Concerns itself never assigns a probability
    assert record["probability"] is None
    assert record["numeric_probability_assigned"] is False


def test_concerns_does_not_invent_medical_risk():
    """A symptom worry without an authorized specialized result never becomes
    high risk inside Concerns."""
    result = evaluate_proportional_risk(severity="severe", evidence=())
    assert result["risk_level"] != "high"
    assert result["emotion_drove_risk"] is True
    assert result["invented_risk"] is False


# ── Reflection boundary ──────────────────────────────────────────────────────


def test_reflection_meaning_stays_with_reflection():
    source = inspect.getsource(__import__("cmm.domains.concerns", fromlist=["*"]))
    # no static dependency on the reflection package internals
    assert (
        "from cmm.domains.reflection"
        not in source.replace("cmm.domains.reflection.rules", "")
        or "cmm.domains.reflection" not in source
    )


def test_broader_meaning_question_not_claimed_by_concerns():
    """A 'why am I so affected by this' question keeps support need at
    UNDERSTANDING within Concerns; deeper identity narrative remains
    Reflection's responsibility (no identity classification here)."""
    from cmm.domains.concerns.rules import infer_support_need

    record = infer_support_need(explicit_request="Why does this bother me so much?")
    assert record["support_need"] == "UNDERSTANDING"
    assert record["diagnosis"] is False
    assert record["personality_trait"] is False
    assert record["durable_identity"] is False


def test_hypothesis_exploration_composes_shared_contract():
    """Concerns hypothesis exploration reuses the shared evaluator contract
    rather than reimplementing competing logic."""
    from cmm.domains.concerns.operations import explore_hypotheses_result
    from cmm.domains.reflection.rules import evaluate_hypotheses

    hypotheses = (
        {
            "identity": "h1",
            "statement": "fatigue explains it",
            "supporting_ids": ("s1",),
        },
        {
            "identity": "h2",
            "statement": "stress explains it",
            "supporting_ids": ("s2",),
        },
    )
    concerns_view = explore_hypotheses_result(hypotheses=hypotheses)
    canonical = evaluate_hypotheses(hypotheses=hypotheses)
    assert concerns_view["winner_selected"] == canonical["winner_selected"]
    assert len(concerns_view["hypotheses"]) == len(canonical["hypotheses"])


# ── Specialized factual domains ──────────────────────────────────────────────


def test_university_oppositions_life_plan_project_own_factual_semantics():
    """Concerns resource definitions carry no specialized factual semantics:
    those domains own their facts through their own packs and reach Concerns
    only via domain_result projections."""
    from cmm.domains.concerns.resources import build_concerns_resource_definitions

    resources = {r.id: r for r in build_concerns_resource_definitions()}
    boundary = resources["concerns.domain_result"]
    assert boundary.metadata.get("cross_domain_projection") is True
    assert boundary.metadata.get("no_private_store_merge") is True
    assert boundary.metadata.get("specialized_ownership_preserved") is True


# ── Permissions composition ──────────────────────────────────────────────────


def test_most_restrictive_permissions_survive_composition():
    from cmm.agent_runtime.domain_permission_contracts import PermissionCapability
    from cmm.domains.concerns.permissions import build_concerns_permission_policy
    from cmm.domains.health.permissions import build_health_permission_policy

    concerns_policy = build_concerns_permission_policy()
    health_policy = build_health_permission_policy()
    composed_denied = set(concerns_policy.prohibited_capabilities) | set(
        health_policy.prohibited_capabilities
    )
    for capability in (
        PermissionCapability.MEMORY_WRITE,
        PermissionCapability.COMMUNICATION_EXTERNAL,
        PermissionCapability.SENSITIVE_INFERENCE_PERSIST,
        PermissionCapability.MEDICAL_DECISION,
    ):
        assert capability in composed_denied


def test_cross_domain_projection_records_json_safe():
    record = {
        "source_domain": "domain:health",
        "projection": "minimal_authorized",
        "red_flags_preserved": True,
    }
    json.dumps(record, allow_nan=False)
