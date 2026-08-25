"""Tests for Phase 10.29 Life Plan Domain Package Export Surface."""

from __future__ import annotations

import cmm.domains.life_plan as life_plan_pkg


def test_life_plan_package_exports() -> None:
    assert hasattr(life_plan_pkg, "build_life_plan_domain_definition")
    assert hasattr(life_plan_pkg, "build_life_plan_profile")
    assert hasattr(life_plan_pkg, "build_life_plan_permission_policy")
    assert hasattr(life_plan_pkg, "build_life_plan_resource_definitions")
    assert hasattr(life_plan_pkg, "build_life_plan_rules")
    assert hasattr(life_plan_pkg, "build_life_plan_operation_definitions")
    assert hasattr(life_plan_pkg, "build_life_plan_workflow_definitions")
    assert hasattr(life_plan_pkg, "build_standard_life_plan_domain_bootstrap")
    assert hasattr(life_plan_pkg, "register_life_plan_domain")
    assert hasattr(life_plan_pkg, "LIFE_PLAN_DOMAIN_ID")


def test_life_plan_package_all_parity() -> None:
    for name in life_plan_pkg.__all__:
        assert hasattr(life_plan_pkg, name), f"Missing export: {name}"
