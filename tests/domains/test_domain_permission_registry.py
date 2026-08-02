from datetime import datetime, timezone

import pytest

from cmm.domains.errors import DomainPermissionRegistryError
from cmm.domains.permission_contracts import DomainPermissionPolicy
from cmm.domains.permission_registry import DomainPermissionRegistry


def policy(version="1.0.0", enabled=True, domain="domain:health"):
    return DomainPermissionPolicy(f"permission:{domain}:{version}", domain, version, enabled=enabled)


def test_registry_rejects_duplicate_id_version_and_selects_highest_semver():
    registry = DomainPermissionRegistry()
    registry.register(policy("1.9.0"))
    registry.register(policy("1.10.0"))
    assert registry.active_for_domain("domain:health").version == "1.10.0"
    with pytest.raises(DomainPermissionRegistryError):
        registry.register(policy("1.10.0"))


def test_registry_does_not_evaluate_during_register_and_lists_deterministically():
    registry = DomainPermissionRegistry()
    registry.register(policy(domain="domain:z"))
    registry.register(policy(domain="domain:a"))
    assert [item.domain_id for item in registry.list_policies()] == ["domain:a", "domain:z"]


def test_disabled_policy_is_not_active_but_can_be_queried():
    registry = DomainPermissionRegistry()
    disabled = policy(enabled=False)
    registry.register(disabled)
    assert registry.get(disabled.policy_id, disabled.version) == disabled
    assert registry.active_for_domain("domain:health") is None


def test_expired_policy_is_never_active_when_clock_is_injected():
    registry = DomainPermissionRegistry()
    registry.register(DomainPermissionPolicy(
        "old", "domain:health", "1.0.0",
        expires_at=datetime(2026, 8, 1, tzinfo=timezone.utc),
    ))
    assert registry.active_for_domain(
        "domain:health", now=datetime(2026, 8, 2, tzinfo=timezone.utc)
    ) is None
    with pytest.raises(ValueError):
        registry.active_for_domain(
            "domain:health",
            now=datetime(2026, 8, 2, tzinfo=timezone.utc).replace(tzinfo=None),
        )
