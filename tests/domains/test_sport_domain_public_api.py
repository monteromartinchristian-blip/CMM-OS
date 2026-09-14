"""Tests for Phase 10.28 Sport Domain Public API."""

from __future__ import annotations

import cmm.domains.sport


def test_sport_public_api_exports() -> None:
    assert hasattr(cmm.domains.sport, "SPORT_DOMAIN_ID")
    assert hasattr(cmm.domains.sport, "build_sport_domain_definition")
    assert hasattr(cmm.domains.sport, "register_sport_domain")
    assert hasattr(cmm.domains.sport, "build_standard_sport_domain_bootstrap")
    assert hasattr(cmm.domains.sport, "build_sport_profile")
    assert hasattr(cmm.domains.sport, "build_sport_rules")
    assert hasattr(cmm.domains.sport, "build_sport_operation_definitions")
    assert hasattr(cmm.domains.sport, "build_sport_workflow_definitions")
    assert hasattr(cmm.domains.sport, "build_sport_permission_policy")

    assert "SPORT_DOMAIN_ID" in cmm.domains.sport.__all__
    assert "build_standard_sport_domain_bootstrap" in cmm.domains.sport.__all__


def test_fresh_import_has_no_side_effects() -> None:
    import cmm.domains.sport

    assert cmm.domains.sport.SPORT_DOMAIN_ID == "domain:sport"
