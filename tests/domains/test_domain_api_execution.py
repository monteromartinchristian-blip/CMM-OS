"""Phase 10.36 — Domain API execution tests.

Covers canonical resolution delegation, authoritative operation orchestration,
and workflow registry/executor routing.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from cmm.domains.api import DefaultDomainAPI
from cmm.domains.identifiers import DomainId
from cmm.domains.resolution_contracts import DomainResolutionContext
from cmm.domains.resolver import DefaultDomainResolver
from tests.domains.test_domain_api_contracts import _make_collaborators


def _api_with_resolver(resolver: DefaultDomainResolver) -> DefaultDomainAPI:
    collaborators = _make_collaborators()
    collaborators["resolver"] = resolver
    return DefaultDomainAPI(**collaborators)


def _context() -> DomainResolutionContext:
    return DomainResolutionContext(
        id="ctx-1",
        objective="test objective",
        available_domains=(DomainId(slug="general"),),
        authorized_domains=(DomainId(slug="general"),),
        active_domains=(DomainId(slug="general"),),
        created_at=datetime(2026, 8, 31, 12, 0, tzinfo=timezone.utc),
    )


class TestResolveDomain:
    def test_delegates_to_canonical_resolver(self) -> None:
        resolver = DefaultDomainResolver(
            clock=lambda: datetime(2026, 8, 31, 12, 0, tzinfo=timezone.utc),
            id_factory=lambda: "res-fixed-1",
        )
        api = _api_with_resolver(resolver)
        context = _context()
        expected = resolver.resolve(context)
        actual = api.resolve_domain(context)
        assert actual == expected

    def test_preserves_canonical_blocked_status(self) -> None:
        # No available domains -> canonical fail-closed result must be
        # preserved unchanged through the facade.
        resolver = DefaultDomainResolver(
            clock=lambda: datetime(2026, 8, 31, 12, 0, tzinfo=timezone.utc),
            id_factory=lambda: "res-fixed-2",
        )
        api = _api_with_resolver(resolver)
        empty_context = DomainResolutionContext(
            id="ctx-empty",
            objective="nothing available",
            available_domains=(),
            created_at=datetime(2026, 8, 31, 12, 0, tzinfo=timezone.utc),
        )
        expected = resolver.resolve(empty_context)
        actual = api.resolve_domain(empty_context)
        assert actual == expected
        assert actual.status == expected.status
        assert actual.confidence == expected.confidence
        assert actual.reasons == expected.reasons
        assert actual.rejected_domains == expected.rejected_domains
        assert actual.ambiguous_domains == expected.ambiguous_domains


class TestStartWorkflow:
    def _workflow_registry_and_executor(self):
        from cmm.domains.workflow_contracts import DomainWorkflowDefinition
        from cmm.domains.workflow_execution import DomainWorkflowExecutor
        from cmm.domains.workflow_registry import InMemoryDomainWorkflowRegistry
        from cmm.workflows.contracts import WorkflowNode

        definition = DomainWorkflowDefinition(
            workflow_id="x.flow",
            domain_id="domain:x",
            version="1.0.0",
            name="X flow",
            nodes=(WorkflowNode("n", "complete", "N"),),
        )
        registry = InMemoryDomainWorkflowRegistry()
        registry.register(definition)
        executor = DomainWorkflowExecutor(id_factory=lambda: "run-1")
        return registry, executor, definition

    def _api_with_workflow_stack(self):
        collaborators = _make_collaborators()
        registry, executor, definition = self._workflow_registry_and_executor()
        collaborators["workflow_registry"] = registry
        collaborators["workflow_executor"] = executor
        return DefaultDomainAPI(**collaborators), registry, definition

    def test_resolves_through_registry_and_executes_canonically(self) -> None:
        from cmm.domains.workflow_contracts import (
            DomainWorkflowContext,
            DomainWorkflowResult,
        )

        api, _, _ = self._api_with_workflow_stack()
        context = DomainWorkflowContext("domain:x")
        result = api.start_workflow("x.flow", context, {})
        assert isinstance(result, DomainWorkflowResult)
        assert result.domain_id == "domain:x"
        assert result.run_id == "run-1"

    def test_uses_active_registry_definition_not_caller_supplied(self) -> None:
        from cmm.domains.workflow_contracts import DomainWorkflowContext

        api, registry, definition = self._api_with_workflow_stack()
        context = DomainWorkflowContext("domain:x")
        result = api.start_workflow("x.flow", context, {})
        # The executed definition came from resolve_active on the registry.
        assert registry.resolve_active("x.flow") is definition
        assert result.domain_id == definition.domain_id

    def test_unknown_workflow_raises_canonical_registry_error(self) -> None:
        from cmm.domains.workflow_contracts import DomainWorkflowContext
        from cmm.workflows.errors import WorkflowRegistryError

        api, _, _ = self._api_with_workflow_stack()
        context = DomainWorkflowContext("domain:x")
        with pytest.raises(WorkflowRegistryError):
            api.start_workflow("missing.flow", context, {})

    def test_permission_blocked_workflow_fails_closed(self) -> None:
        from cmm.domains.workflow_contracts import (
            DomainWorkflowContext,
            DomainWorkflowDefinition,
        )
        from cmm.domains.workflow_execution import DomainWorkflowExecutor
        from cmm.domains.workflow_registry import InMemoryDomainWorkflowRegistry
        from cmm.workflows.contracts import WorkflowNode

        definition = DomainWorkflowDefinition(
            workflow_id="secure.flow",
            domain_id="domain:secure",
            version="1.0.0",
            name="Secure flow",
            nodes=(WorkflowNode("n", "complete", "N"),),
            required_permissions=("domain:operation",),
        )
        registry = InMemoryDomainWorkflowRegistry()
        registry.register(definition)
        collaborators = _make_collaborators()
        collaborators["workflow_registry"] = registry
        collaborators["workflow_executor"] = DomainWorkflowExecutor(
            id_factory=lambda: "run-2"
        )
        api = DefaultDomainAPI(**collaborators)
        # Context grants no permissions -> canonical resolution blocks.
        context = DomainWorkflowContext("domain:secure")
        with pytest.raises(ValueError, match="unavailable"):
            api.start_workflow("secure.flow", context, {})
