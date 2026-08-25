"""Tests for Phase 10.28 Sport Domain Bootstrap."""

from __future__ import annotations

from cmm.domains.identifiers import DomainId
from cmm.domains.sport.bootstrap import (
    SPORT_BOOTSTRAP_NAME,
    SportDomainBootstrap,
    build_standard_sport_domain_bootstrap,
)
from cmm.domains.sport.definition import SPORT_DOMAIN_ID


def test_build_standard_sport_domain_bootstrap() -> None:
    bootstrap = build_standard_sport_domain_bootstrap()

    assert isinstance(bootstrap, SportDomainBootstrap)
    assert SPORT_BOOTSTRAP_NAME == "SportDomainBootstrap"
    assert bootstrap.domain_registry.get("domain:general") is not None
    assert bootstrap.domain_registry.get(SPORT_DOMAIN_ID) is not None
    assert bootstrap.profile_registry.get_by_domain(DomainId("general")) is not None
    assert bootstrap.profile_registry.get_by_domain(DomainId("sport")) is not None

    assert len(bootstrap.resource_registry.list_all()) >= 9
    assert len(bootstrap.rule_registry.list_all()) >= 6
    assert len(bootstrap.operation_registry.list_definitions()) >= 8
    assert len(bootstrap.workflow_registry.list_for_domain("domain:sport")) == 5
