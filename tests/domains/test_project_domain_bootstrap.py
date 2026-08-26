"""Phase 10.30 — Project Domain Bootstrap Tests."""

from __future__ import annotations

from cmm.domains.identifiers import DomainId
from cmm.domains.project.bootstrap import (
    PROJECT_BOOTSTRAP_NAME,
    ProjectDomainBootstrap,
    build_standard_project_domain_bootstrap,
)
from cmm.domains.project.catalog import (
    CANONICAL_PROJECT_OPERATION_IDS,
    CANONICAL_PROJECT_RESOURCE_IDS,
    CANONICAL_PROJECT_RULE_IDS,
    CANONICAL_PROJECT_WORKFLOW_IDS,
    PROJECT_DOMAIN_ID,
)


def test_build_standard_project_domain_bootstrap_extends_life_plan_chain() -> None:
    bootstrap = build_standard_project_domain_bootstrap()
    assert isinstance(bootstrap, ProjectDomainBootstrap)
    assert PROJECT_BOOTSTRAP_NAME == "ProjectDomainBootstrap"

    # General, Life Plan, and Project are present in domain_registry
    assert bootstrap.domain_registry.get("domain:general") is not None
    assert bootstrap.domain_registry.get("domain:life-plan") is not None
    assert bootstrap.domain_registry.get(PROJECT_DOMAIN_ID) is not None

    # Future domains are absent
    assert bootstrap.domain_registry.get("domain:mental-health") is None
    assert bootstrap.domain_registry.get("domain:neurodivergence") is None

    # Profiles
    assert bootstrap.profile_registry.get_by_domain(DomainId("general")) is not None
    assert bootstrap.profile_registry.get_by_domain(DomainId("life-plan")) is not None
    assert bootstrap.profile_registry.get_by_domain(DomainId("project")) is not None

    # Resources include Project's 22
    all_res_ids = {r.id for r in bootstrap.resource_registry.list_all()}
    for res_id in CANONICAL_PROJECT_RESOURCE_IDS:
        assert res_id in all_res_ids

    # Rules include Project's 18
    all_rule_ids = {r.definition.id for r in bootstrap.rule_registry.list_all()}
    for rule_id in CANONICAL_PROJECT_RULE_IDS:
        assert rule_id in all_rule_ids

    # Operations include Project's 20
    all_op_ids = {
        op.operation_id for op in bootstrap.operation_registry.list_definitions()
    }
    for op_id in CANONICAL_PROJECT_OPERATION_IDS:
        assert op_id in all_op_ids

    # Workflows include Project's 12
    project_wfs = {
        w.workflow_id
        for w in bootstrap.workflow_registry.list_for_domain(PROJECT_DOMAIN_ID)
    }
    for wf_id in CANONICAL_PROJECT_WORKFLOW_IDS:
        assert wf_id in project_wfs

    # Permission policies
    assert (
        bootstrap.permission_registry.get("domain-permission:general:1.0.0") is not None
    )
    assert (
        bootstrap.permission_registry.get("domain-permission:life-plan:1.0.0")
        is not None
    )
    assert (
        bootstrap.permission_registry.get("domain-permission:project:1.0.0") is not None
    )

    # General fallback preserved in resolver
    from cmm.domains.resolution_builder import DomainResolutionContextBuilder

    ctx = DomainResolutionContextBuilder().build(
        registry_snapshot=bootstrap.domain_registry.snapshot(),
        user_input="General conversational input without domain signals",
        authorized_domains=("domain:general", "domain:life-plan", PROJECT_DOMAIN_ID),
        signals=(),
    )
    res = bootstrap.resolver.resolve(ctx)
    assert str(res.primary_domain) in ("domain:general", "general")
