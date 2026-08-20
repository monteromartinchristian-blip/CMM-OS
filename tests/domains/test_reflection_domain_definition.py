"""Phase 10.24 — Reflection Domain definition tests.

The definition module builds the immutable ``domain:reflection``
``DomainDefinition`` deterministically; no global registration occurs at
import time (spec §4, §39).
"""

from __future__ import annotations

from cmm.domains.reflection import (
    REFLECTION_DOMAIN_ID,
    REFLECTION_DOMAIN_VERSION,
    REFLECTION_MANIFEST_ID,
    REFLECTION_PROFILE_NAME,
    build_reflection_domain_definition,
)
from cmm.domains.reflection.catalog import (
    CANONICAL_REFLECTION_OPERATION_IDS,
    CANONICAL_REFLECTION_RESOURCE_IDS,
    CANONICAL_REFLECTION_RULE_IDS,
    CANONICAL_REFLECTION_WORKFLOW_IDS,
)


def test_canonical_domain_id():
    assert REFLECTION_DOMAIN_ID == "domain:reflection"


def test_definition_metadata():
    d = build_reflection_domain_definition()
    assert d.id == "domain:reflection"
    assert d.name == "reflection"
    assert d.version == REFLECTION_DOMAIN_VERSION
    assert d.manifest_id == REFLECTION_MANIFEST_ID
    assert d.reasoning_profile == REFLECTION_PROFILE_NAME
    assert d.enabled is True


def test_definition_reconciles_catalog_exactly():
    d = build_reflection_domain_definition()
    assert set(d.resources) == set(CANONICAL_REFLECTION_RESOURCE_IDS)
    assert set(d.rules) == set(CANONICAL_REFLECTION_RULE_IDS)
    assert set(d.operations) == set(CANONICAL_REFLECTION_OPERATION_IDS)
    assert set(d.workflows) == set(CANONICAL_REFLECTION_WORKFLOW_IDS)


def test_definition_deterministic():
    d1 = build_reflection_domain_definition()
    d2 = build_reflection_domain_definition()
    assert d1.to_dict() == d2.to_dict()


def test_definition_high_sensitivity_presentation():
    d = build_reflection_domain_definition()
    presentation = d.presentation_policy
    assert presentation.get("include_uncertainty") is True
    assert presentation.get("include_provenance") is True
    assert presentation.get("include_alternatives") is True
    assert presentation.get("allow_speculation") is False
    assert presentation.get("require_disclaimers") is True


def test_definition_no_import_time_registration():
    """Importing the definition module does not register the domain globally."""
    import cmm.domains.reflection.definition  # noqa: F401
    from cmm.domains.registry import DomainRegistry

    assert DomainRegistry().get(REFLECTION_DOMAIN_ID) is None