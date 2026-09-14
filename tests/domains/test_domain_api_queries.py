"""Phase 10.36 — Domain API read-only query tests.

Proves list/get/capabilities/resources/rules/operations/workflows delegate to
the canonical registry and that read-only calls never mutate registry state.
"""

from __future__ import annotations

import pytest

from cmm.domains.api import DefaultDomainAPI
from cmm.domains.contracts import DomainDefinition
from cmm.domains.enums import DomainKind
from cmm.domains.identifiers import DomainId, DomainManifestId
from cmm.domains.registry import DomainRegistry
from cmm.domains.registry_contracts import DomainQuery
from tests.domains.test_domain_api_contracts import _make_collaborators


def _definition(slug: str, version: str = "1.0.0") -> DomainDefinition:
    return DomainDefinition(
        id=DomainId(slug=slug),
        name=slug,
        display_name=f"Domain {slug}",
        version=version,
        kind=DomainKind.PERSONAL,
        description=f"Description for {slug}",
        manifest_id=DomainManifestId(slug=slug, version=version),
        capabilities=(
            {
                "name": f"{slug}.capability",
                "kind": "core",
                "provided_by": f"domain:{slug}",
                "version": version,
            },
        ),
        resources=(f"{slug}:resource-1", f"{slug}:resource-2"),
        rules=(f"{slug}:rule-1",),
        operations=(f"{slug}.op-1",),
        workflows=(f"{slug}.flow-1",),
    )


def _registry_with(*definitions: DomainDefinition) -> DomainRegistry:
    registry = DomainRegistry()
    for definition in definitions:
        registry.register(definition)
    return registry


def _api_with_registry(registry: DomainRegistry) -> DefaultDomainAPI:
    collaborators = _make_collaborators()
    collaborators["domain_registry"] = registry
    return DefaultDomainAPI(**collaborators)


class TestListDomains:
    def test_delegates_to_registry_list(self) -> None:
        registry = _registry_with(_definition("alpha"), _definition("beta"))
        api = _api_with_registry(registry)
        assert api.list_domains() == registry.list()

    def test_delegates_query_filtering(self) -> None:
        registry = _registry_with(_definition("alpha"), _definition("beta"))
        api = _api_with_registry(registry)
        query = DomainQuery(capabilities=("alpha.capability",))
        assert api.list_domains(query) == registry.list(query)
        assert [d.id.slug for d in api.list_domains(query)] == ["alpha"]


class TestGetDomain:
    def test_returns_canonical_object_identity(self) -> None:
        definition = _definition("alpha")
        registry = _registry_with(definition)
        api = _api_with_registry(registry)
        # The API must return the registry's canonical stored object.
        assert api.get_domain("alpha") is registry.get("alpha")
        assert api.get_domain("alpha") == registry.get("alpha")

    def test_versioned_lookup(self) -> None:
        registry = _registry_with(_definition("alpha", "1.0.0"))
        api = _api_with_registry(registry)
        assert api.get_domain("alpha", "1.0.0") is not None
        assert api.get_domain("alpha", "9.9.9") is None

    def test_missing_returns_none(self) -> None:
        api = _api_with_registry(DomainRegistry())
        assert api.get_domain("missing") is None


class TestGetCapabilities:
    def test_returns_definition_declared_capabilities(self) -> None:
        definition = _definition("alpha")
        registry = _registry_with(definition)
        api = _api_with_registry(registry)
        capabilities = api.get_capabilities("alpha")
        assert [c.name for c in capabilities] == ["alpha.capability"]
        assert capabilities == definition.capabilities


class TestIdentifierSurfaces:
    def test_resources_equal_registry_tuple(self) -> None:
        registry = _registry_with(_definition("alpha"))
        api = _api_with_registry(registry)
        assert api.get_resources("alpha") == registry.list_resources("alpha")
        assert api.get_resources("alpha") == ("alpha:resource-1", "alpha:resource-2")

    def test_rules_equal_registry_tuple(self) -> None:
        registry = _registry_with(_definition("alpha"))
        api = _api_with_registry(registry)
        assert api.get_rules("alpha") == registry.list_rules("alpha")

    def test_operations_equal_registry_tuple(self) -> None:
        registry = _registry_with(_definition("alpha"))
        api = _api_with_registry(registry)
        assert api.get_operations("alpha") == registry.list_operations("alpha")

    def test_workflows_equal_registry_tuple(self) -> None:
        registry = _registry_with(_definition("alpha"))
        api = _api_with_registry(registry)
        assert api.get_workflows("alpha") == registry.list_workflows("alpha")


class TestReadOnlyMutationInvariants:
    @pytest.mark.parametrize(
        "call",
        [
            lambda api: api.list_domains(),
            lambda api: api.get_domain("alpha"),
            lambda api: api.get_capabilities("alpha"),
            lambda api: api.get_resources("alpha"),
            lambda api: api.get_rules("alpha"),
            lambda api: api.get_operations("alpha"),
            lambda api: api.get_workflows("alpha"),
        ],
    )
    def test_read_only_calls_do_not_mutate_registry(self, call) -> None:
        registry = _registry_with(_definition("alpha"))
        api = _api_with_registry(registry)
        before = registry.snapshot_state()
        call(api)
        assert registry.snapshot_state() == before
