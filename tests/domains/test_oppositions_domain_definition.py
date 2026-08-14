"""Phase 10.23 — Opposition Domain Definition tests."""

from __future__ import annotations

from cmm.domains.oppositions import (
    OPPOSITIONS_DOMAIN_ID,
    OPPOSITIONS_DOMAIN_VERSION,
    OPPOSITIONS_MANIFEST_ID,
    OPPOSITIONS_PROFILE_NAME,
    build_oppositions_domain_definition,
)
from cmm.domains.oppositions.catalog import (
    CANONICAL_OPPOSITION_OPERATION_IDS,
    CANONICAL_OPPOSITION_RESOURCE_IDS,
    CANONICAL_OPPOSITION_RULE_IDS,
    CANONICAL_OPPOSITION_WORKFLOW_IDS,
)


def test_canonical_domain_id():
    """Canonical domain ID is ``domain:oppositions``."""
    assert OPPOSITIONS_DOMAIN_ID == "domain:oppositions"


def test_definition_metadata():
    d = build_oppositions_domain_definition()
    assert d.id == "domain:oppositions"
    assert d.version == OPPOSITIONS_DOMAIN_VERSION
    assert d.manifest_id == OPPOSITIONS_MANIFEST_ID
    assert d.reasoning_profile == OPPOSITIONS_PROFILE_NAME
    assert d.enabled is True


def test_definition_reconciles_catalogue_exactly():
    d = build_oppositions_domain_definition()
    assert set(d.resources) == set(CANONICAL_OPPOSITION_RESOURCE_IDS)
    assert set(d.rules) == set(CANONICAL_OPPOSITION_RULE_IDS)
    assert set(d.operations) == set(CANONICAL_OPPOSITION_OPERATION_IDS)
    assert set(d.workflows) == set(CANONICAL_OPPOSITION_WORKFLOW_IDS)


def test_definition_deterministic():
    d1 = build_oppositions_domain_definition()
    d2 = build_oppositions_domain_definition()
    assert d1.to_dict() == d2.to_dict()


def test_definition_no_import_time_registration():
    """Importing definition does not register globally."""
    import cmm.domains.oppositions

    assert not hasattr(cmm.domains.oppositions, "_GLOBAL_REGISTRIES")


def test_capabilities_declared():
    d = build_oppositions_domain_definition()
    capability_names = {c.name for c in d.capabilities}
    assert {"opposition_planning", "opposition_source_authority"} <= capability_names