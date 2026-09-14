"""Phase 10.24 — Reflection cross-domain boundary tests.

Reflection consumes ``relationship_event`` only through the shared
cross-domain mechanism as a minimal authorized projection; there is no direct
Relationships store/state import, and no dependency on the Concerns Domain
(10.25).  General remains the shared fallback (spec §30, §31, §32).
"""

from __future__ import annotations

from cmm.agent_runtime.operation_registry import InMemoryAgentOperationRegistry
from cmm.domains.operation_registry import InMemoryDomainOperationRegistry
from cmm.domains.reflection import (
    build_standard_reflection_domain_bootstrap,
    register_reflection_domain,
)
from cmm.domains.reflection.rules import (
    authorizes_confirmation,
    map_interests,
)
from cmm.domains.workflow_registry import InMemoryDomainWorkflowRegistry
from cmm.workflows.registry import InMemoryWorkflowRegistry


def test_general_fallback_reused():
    from cmm.domains.identifiers import DomainId

    bootstrap = build_standard_reflection_domain_bootstrap()
    assert bootstrap.domain_registry.get("domain:general") is not None
    assert bootstrap.resolver.fallback_domain == DomainId(slug="general")


def test_relationship_event_consumed_only_via_authorized_projection():
    """A relationship event projection is consumed only when literally
    authorized; malformed/nonliteral authorization fails closed."""
    projection = {
        "authorized": True,
        "event_type": "conflict",
        "source": "relationships:evt:1",
    }
    result = map_interests(
        records=(
            {
                "interest": "communication",
                "source": "relationships:evt:1",
                "source_kind": "relationship_event",
                "mention": True,
                "explicit": True,
                "context": "partnership",
                "observed_at": "2026-05-01",
                "contradictory": False,
            },
        )
    )
    assert result["interest_candidates"][0]["persistent_confirmed"] is False
    assert result["interest_candidates"][0]["grounded_evidence_count"] == 1

    # a malformed authorization must never widen persistence
    assert authorizes_confirmation(projection.get("authorized")) is True
    for raw in ("true", 1, [], {}, None, "yes"):
        assert authorizes_confirmation(raw) is False


def test_no_direct_relationships_store_import():
    """Reflection never imports Relationships store/state modules directly."""
    import sys

    import cmm.domains.reflection  # noqa: F401

    for module_name in tuple(sys.modules):
        if module_name.startswith("cmm.domains.reflection"):
            assert "cmm.domains.relationships" not in module_name
    # static check: no source imports from the relationships store/state
    import inspect

    source = inspect.getsource(__import__("cmm.domains.reflection", fromlist=["*"]))
    assert "relationships_store" not in source
    assert "relationships.state" not in source
    assert "relationships.timeline" not in source


def test_no_concerns_domain_dependency():
    """No static or import-time dependency of Reflection on cmm.domains.concerns.

    Phase 10.25 now implements ``cmm.domains.concerns`` as a sibling pack;
    the invariant under guard is that Reflection neither imports nor
    statically references it (composition goes only through shared
    cross-domain mechanisms).
    """
    import inspect
    import sys

    # Reflection modules never appear as concerns modules and vice versa
    for module_name in tuple(sys.modules):
        if module_name.startswith("cmm.domains.reflection"):
            assert not module_name.startswith("cmm.domains.concerns")

    source = inspect.getsource(__import__("cmm.domains.reflection", fromlist=["*"]))
    assert "cmm.domains.concerns" not in source

    # rules module must not reference concerns
    from cmm.domains.reflection import rules as reflection_rules

    rules_source = inspect.getsource(reflection_rules)
    assert "cmm.domains.concerns" not in rules_source


def test_relationship_interpretations_remain_interpretations():
    """Relationships-domain psychological interpretations remain
    interpretations when reflected; they are never promoted to facts."""
    from cmm.domains.reflection import classify_belief_evidence

    result = classify_belief_evidence(
        records=(
            {
                "identity": "r1",
                "statement": "they avoid intimacy (relationship analysis)",
                "kind": "interpretation",
                "fact": True,  # caller label must not promote it
                "source": "relationships:analysis:1",
            },
        )
    )
    assert result["facts"] == ()
    assert all(item["kind"] == "interpretation" for item in result["interpretations"])
    assert "r1" in result["promotions_blocked"]


def test_registration_does_not_merge_relationships_state():
    """register_reflection_domain never touches Relationships registries."""
    from cmm.cognitive.reasoning_rule_registry import InMemoryReasoningRuleRegistry
    from cmm.domains.permission_registry import DomainPermissionRegistry
    from cmm.domains.profile_registry import InMemoryDomainProfileRegistry
    from cmm.domains.registry import DomainRegistry
    from cmm.domains.resource_registry import InMemoryDomainResourceRegistry

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
    register_reflection_domain(**registries)
    # no relationships entries appear anywhere
    assert registries["domain_registry"].get("domain:relationships") is None
    assert registries["profile_registry"].get("relationships.profile") is None
    assert all(
        res.id.startswith("reflection.")
        for res in registries["resource_registry"].list_all()
    )
