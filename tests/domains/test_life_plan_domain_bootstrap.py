"""Tests for Phase 10.29 Life Plan Domain Bootstrap."""

from __future__ import annotations

from cmm.domains.identifiers import DomainId
from cmm.domains.life_plan.bootstrap import (
    LIFE_PLAN_BOOTSTRAP_NAME,
    LifePlanDomainBootstrap,
    build_standard_life_plan_domain_bootstrap,
)
from cmm.domains.life_plan.catalog import (
    LIFE_PLAN_DOMAIN_ID,
    LIFE_PLAN_OPERATION_IDS,
    LIFE_PLAN_RESOURCE_IDS,
    LIFE_PLAN_RULE_IDS,
    LIFE_PLAN_WORKFLOW_IDS,
)


def test_build_standard_life_plan_domain_bootstrap() -> None:
    bootstrap = build_standard_life_plan_domain_bootstrap()

    assert isinstance(bootstrap, LifePlanDomainBootstrap)
    assert LIFE_PLAN_BOOTSTRAP_NAME == "LifePlanDomainBootstrap"

    # Verify both general and life plan are in domain registry
    assert bootstrap.domain_registry.get("domain:general") is not None
    assert bootstrap.domain_registry.get(LIFE_PLAN_DOMAIN_ID) is not None

    # Verify profile registry
    assert bootstrap.profile_registry.get_by_domain(DomainId("general")) is not None
    assert bootstrap.profile_registry.get_by_domain(DomainId("life-plan")) is not None

    # Verify counts
    assert len(bootstrap.resource_registry.list_all()) >= len(LIFE_PLAN_RESOURCE_IDS)
    assert len(bootstrap.rule_registry.list_all()) >= len(LIFE_PLAN_RULE_IDS)
    assert len(bootstrap.operation_registry.list_definitions()) >= len(
        LIFE_PLAN_OPERATION_IDS
    )
    assert len(bootstrap.workflow_registry.list_for_domain(LIFE_PLAN_DOMAIN_ID)) == len(
        LIFE_PLAN_WORKFLOW_IDS
    )
