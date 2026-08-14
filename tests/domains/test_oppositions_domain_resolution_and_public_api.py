"""Phase 10.23 — Opposition Domain bootstrap + resolution + public API tests."""

from __future__ import annotations

from cmm.domains.oppositions import (
    OPPOSITIONS_DOMAIN_ID,
    build_standard_oppositions_domain_bootstrap,
)
from cmm.domains.oppositions.catalog import (
    CANONICAL_OPPOSITION_OPERATION_IDS,
    CANONICAL_OPPOSITION_RESOURCE_IDS,
    CANONICAL_OPPOSITION_RULE_IDS,
    CANONICAL_OPPOSITION_WORKFLOW_IDS,
)


def test_bootstrap_composes_general_plus_oppositions():
    bootstrap = build_standard_oppositions_domain_bootstrap()
    # General fallback present
    assert bootstrap.domain_registry.get("domain:general") is not None
    # Oppositions fully integrated
    registered_opps = {
        d.operation_id
        for d in bootstrap.operation_registry.list_definitions()
        if d.domain_id == OPPOSITIONS_DOMAIN_ID
    }
    assert registered_opps == set(CANONICAL_OPPOSITION_OPERATION_IDS)


def test_bootstrap_resolves_oppositions_domain():
    bootstrap = build_standard_oppositions_domain_bootstrap()
    resolved = bootstrap.domain_registry.get(OPPOSITIONS_DOMAIN_ID)
    assert resolved is not None
    assert str(resolved.id) == OPPOSITIONS_DOMAIN_ID


def test_bootstrap_exposes_resolver_with_general_fallback():
    bootstrap = build_standard_oppositions_domain_bootstrap()
    assert bootstrap.resolver is not None
    # general remains fallback
    assert str(bootstrap.resolver.fallback_domain) == "domain:general"


def test_bootstrap_registers_all_opposition_parts():
    bootstrap = build_standard_oppositions_domain_bootstrap()
    resources = {
        r.id for r in bootstrap.resource_registry.list_all()
        if r.domain_id == OPPOSITIONS_DOMAIN_ID
    }
    rules = {
        r.definition.id for r in bootstrap.rule_registry.list_all()
        if r.definition.domain_id == OPPOSITIONS_DOMAIN_ID
    }
    workflows = {w.workflow_id for w in bootstrap.workflow_registry.list_for_domain(OPPOSITIONS_DOMAIN_ID)}
    assert resources == set(CANONICAL_OPPOSITION_RESOURCE_IDS)
    assert rules == set(CANONICAL_OPPOSITION_RULE_IDS)
    assert workflows == set(CANONICAL_OPPOSITION_WORKFLOW_IDS)


def test_public_api_intentional():
    """Only intentional public API is exported from the package."""
    import cmm.domains.oppositions as _pkg

    public = set(_pkg.__all__)
    assert "build_oppositions_domain_definition" in public
    assert "register_oppositions_domain" in public
    assert "build_oppositions_rules" in public
    # internal helpers are not exported at package level
    assert "classify_opposition_source_authority" not in public


def test_import_no_side_effects():
    """Importing the package does not register anything or mutate globals."""
    import cmm.domains.oppositions as _pkg

    assert not hasattr(_pkg, "_GLOBAL_REGISTRIES")