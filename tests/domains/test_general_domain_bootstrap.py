"""Tests for the canonical General Domain bootstrap and discoverability."""

from __future__ import annotations

import pytest

from cmm.domains.errors import DomainOperationRegistryError
from cmm.domains.general import (
    GENERAL_DOMAIN_ID,
    GENERAL_OPERATION_IDS,
    GENERAL_RESOURCE_IDS,
    GENERAL_RULE_IDS,
    GENERAL_WORKFLOW_IDS,
    build_standard_general_domain_bootstrap,
)


def test_general_domain_discoverable():
    """domain:general is discoverable via the canonical bootstrap."""
    bootstrap = build_standard_general_domain_bootstrap()
    definition = bootstrap.domain_registry.get(GENERAL_DOMAIN_ID)
    assert definition is not None
    assert definition.id.slug == "general"


def test_nine_resources_resolvable():
    """All 9 General Domain resources are resolvable."""
    bootstrap = build_standard_general_domain_bootstrap()
    resource_ids = {r.id for r in bootstrap.resource_registry.list_all()}
    assert resource_ids == set(GENERAL_RESOURCE_IDS)
    assert len(resource_ids) == 9


def test_general_profile_resolvable():
    """GeneralProfile is resolvable."""
    bootstrap = build_standard_general_domain_bootstrap()
    profile = bootstrap.profile_registry.get("general.profile")
    assert profile is not None
    assert profile.profile_name == "GeneralProfile"


def test_six_rules_in_catalog():
    """All 6 General Domain rules appear in the real catalog."""
    bootstrap = build_standard_general_domain_bootstrap()
    rule_ids = {r.definition.id for r in bootstrap.rule_registry.list_all()}
    assert rule_ids == set(GENERAL_RULE_IDS)
    assert len(rule_ids) == 6


def test_eight_operations_in_catalog():
    """All 8 General Domain operations appear in the real catalog."""
    bootstrap = build_standard_general_domain_bootstrap()
    operation_ids = {
        d.operation_id for d in bootstrap.operation_registry.list_definitions()
    }
    assert operation_ids == set(GENERAL_OPERATION_IDS)
    assert len(operation_ids) == 8


def test_four_workflows_in_catalog():
    """All 4 General Domain workflows appear in the real catalog."""
    bootstrap = build_standard_general_domain_bootstrap()
    wf_ids = {
        w.workflow_id
        for w in bootstrap.workflow_registry.list_for_domain(GENERAL_DOMAIN_ID)
    }
    assert wf_ids == set(GENERAL_WORKFLOW_IDS)
    assert len(wf_ids) == 4


def test_permission_policy_accessible():
    """Permission policy is accessible via the canonical bootstrap."""
    bootstrap = build_standard_general_domain_bootstrap()
    policy = bootstrap.permission_registry.get("domain-permission:general:1.0.0")
    assert policy is not None
    assert policy.domain_id == "domain:general"


def test_presentation_policy_accessible():
    """Presentation policy is accessible via the profile."""
    bootstrap = build_standard_general_domain_bootstrap()
    profile = bootstrap.profile_registry.get("general.profile")
    assert profile is not None
    assert profile.presentation_policy is not None
    assert profile.presentation_policy.detail_level == "standard"


def test_no_registration_at_import():
    """Importing the module does not register anything."""
    import cmm.domains.general

    # No global registries exist at module level
    assert not hasattr(cmm.domains.general, "_GLOBAL_REGISTRIES")


def test_build_twice_produces_equivalent_snapshots():
    """Building twice produces equivalent snapshots."""
    a = build_standard_general_domain_bootstrap()
    b = build_standard_general_domain_bootstrap()

    a_resources = {r.id for r in a.resource_registry.list_all()}
    b_resources = {r.id for r in b.resource_registry.list_all()}
    assert a_resources == b_resources

    a_ops = {d.operation_id for d in a.operation_registry.list_definitions()}
    b_ops = {d.operation_id for d in b.operation_registry.list_definitions()}
    assert a_ops == b_ops

    a_rules = {r.definition.id for r in a.rule_registry.list_all()}
    b_rules = {r.definition.id for r in b.rule_registry.list_all()}
    assert a_rules == b_rules


def test_no_duplicate_ids():
    """No duplicate IDs across any registry."""
    bootstrap = build_standard_general_domain_bootstrap()

    resource_ids = [r.id for r in bootstrap.resource_registry.list_all()]
    assert len(resource_ids) == len(set(resource_ids))

    rule_ids = [r.definition.id for r in bootstrap.rule_registry.list_all()]
    assert len(rule_ids) == len(set(rule_ids))

    op_ids = [d.operation_id for d in bootstrap.operation_registry.list_definitions()]
    assert len(op_ids) == len(set(op_ids))

    wf_ids = [
        w.workflow_id
        for w in bootstrap.workflow_registry.list_for_domain(GENERAL_DOMAIN_ID)
    ]
    assert len(wf_ids) == len(set(wf_ids))


def _make_request(operation_id: str):
    """Build a valid AgentOperationRequest for testing."""
    from cmm.agent_runtime.operation_execution_contracts import AgentOperationRequest

    return AgentOperationRequest(
        id=f"req-{operation_id}",
        agent_run_id="run-1",
        workflow_id="wf-1",
        task_id="task-1",
        operation_name=operation_id,
        idempotency_key=f"key-{operation_id}",
        operation_version="1.0.0",
        parameters={},
    )


def test_operations_unavailable_without_implementations():
    """Operations are UNAVAILABLE (fail-closed) without injected implementations."""
    from cmm.domains.enums import DomainOperationStatus
    from cmm.domains.operation_availability import (
        DomainOperationAvailabilityContext,
        DomainOperationAvailabilityResolver,
    )

    bootstrap = build_standard_general_domain_bootstrap()
    resolver = DomainOperationAvailabilityResolver()
    context = DomainOperationAvailabilityContext(
        primary_domain_id="domain:general",
        granted_permissions=("resource.read", "memory.read"),
        available_resources=("general.user_message",),
    )
    for op in bootstrap.operation_registry.list_definitions():
        availability = resolver.resolve(op, context)
        assert availability.status is DomainOperationStatus.UNAVAILABLE
        assert "availability.disabled" in availability.reason_codes


def test_operations_accept_injected_implementations():
    """Injected implementations make operations available."""
    from cmm.domains.general import build_general_operation_definitions

    class _RealDelegate:
        def __init__(self, definition):
            self.definition = definition

        def execute(self, request):
            return {
                "success": True,
                "output": {"status": "completed", "operation_id": self.definition.operation_id},
                "effects": (),
            }

    operations = build_general_operation_definitions()
    implementations = {
        op.operation_id: _RealDelegate(op) for op in operations
    }
    bootstrap = build_standard_general_domain_bootstrap(
        operation_implementations=implementations
    )
    for op in bootstrap.operation_registry.list_definitions():
        impl = bootstrap.operation_registry.get_implementation(
            op.operation_id, op.version
        )
        assert impl is not None
        assert callable(getattr(impl, "execute", None))
        result = impl.execute(_make_request(op.operation_id))
        assert result["success"] is True
        assert "output" in result
        assert "effects" in result
def test_bootstrap_exposes_configured_general_resolver():
    """The canonical bootstrap exposes a DefaultDomainResolver with General fallback."""
    from cmm.domains.identifiers import DomainId
    from cmm.domains.resolver import DefaultDomainResolver

    bootstrap = build_standard_general_domain_bootstrap()
    assert isinstance(bootstrap.resolver, DefaultDomainResolver)
    assert bootstrap.resolver.fallback_domain == DomainId(slug="general")
    bootstrap = build_standard_general_domain_bootstrap()
    assert isinstance(bootstrap.resolver, DefaultDomainResolver)
    assert bootstrap.resolver.fallback_domain == DomainId(slug="general")


def test_standard_general_unimplemented_operation_cannot_be_enabled():
    """Audit v2 P1: a canonical General operation cannot be enabled without an impl."""
    bootstrap = build_standard_general_domain_bootstrap()
    operation_registry = bootstrap.operation_registry

    with pytest.raises(DomainOperationRegistryError):
        operation_registry.set_enabled("general.create_task", "1.0.0", True)

    # Remains disabled / unavailable and unexecutable.
    definition = operation_registry.get("general.create_task", "1.0.0")
    assert definition.enabled is False
    assert operation_registry.resolve_active("general.create_task", required=False) is None
    with pytest.raises(DomainOperationRegistryError):
        operation_registry.get_implementation("general.create_task", "1.0.0")
