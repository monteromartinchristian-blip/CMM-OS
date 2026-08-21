"""Phase 10.25 — Concerns Domain definition tests.

The definition module builds the immutable ``domain:concerns``
``DomainDefinition`` deterministically; no global registration occurs at
import time (frozen design §4, §92).
"""

from __future__ import annotations

from cmm.domains.concerns.catalog import (
    CANONICAL_CONCERNS_OPERATION_IDS,
    CANONICAL_CONCERNS_RESOURCE_IDS,
    CANONICAL_CONCERNS_RULE_IDS,
    CANONICAL_CONCERNS_WORKFLOW_IDS,
)
from cmm.domains.concerns.definition import (
    CONCERNS_DOMAIN_ID,
    CONCERNS_DOMAIN_VERSION,
    CONCERNS_MANIFEST_ID,
    CONCERNS_PROFILE_NAME,
    build_concerns_domain_definition,
)
from cmm.domains.enums import DomainKind

CAPABILITIES = (
    "concern_understanding",
    "support_need_resolution",
    "reality_check",
    "evidence_calibrated_reassurance",
    "uncertainty_support",
    "risk_calibration",
    "problem_solving",
    "decision_support",
    "recurring_concern_review",
    "professional_discussion_preparation",
)


def test_canonical_domain_id():
    assert CONCERNS_DOMAIN_ID == "domain:concerns"


def test_profile_name_is_concern_support_profile():
    assert CONCERNS_PROFILE_NAME == "ConcernSupportProfile"


def test_definition_metadata():
    d = build_concerns_domain_definition()
    assert d.id == "domain:concerns"
    assert d.name == "concerns"
    assert str(d.kind) in ("personal", "DomainKind.PERSONAL") or d.kind == DomainKind.PERSONAL
    assert d.version == CONCERNS_DOMAIN_VERSION
    assert d.manifest_id == CONCERNS_MANIFEST_ID
    assert d.reasoning_profile == CONCERNS_PROFILE_NAME
    assert d.enabled is True


def test_definition_phase_metadata():
    d = build_concerns_domain_definition()
    metadata = d.metadata.metadata
    assert metadata.get("phase") == "10.25"
    assert d.capabilities
    capability_names = tuple(capability.name for capability in d.capabilities)
    assert capability_names == CAPABILITIES


def test_definition_reconciles_catalog_exactly():
    definition = build_concerns_domain_definition()
    assert tuple(definition.resources) == CANONICAL_CONCERNS_RESOURCE_IDS
    assert tuple(definition.rules) == CANONICAL_CONCERNS_RULE_IDS
    assert tuple(definition.operations) == CANONICAL_CONCERNS_OPERATION_IDS
    assert tuple(definition.workflows) == CANONICAL_CONCERNS_WORKFLOW_IDS


def test_definition_deterministic():
    d1 = build_concerns_domain_definition()
    d2 = build_concerns_domain_definition()
    assert d1.to_dict() == d2.to_dict()


def test_definition_no_import_time_registration():
    """Importing the definition module does not register the domain globally."""
    import cmm.domains.concerns.definition  # noqa: F401
    from cmm.domains.registry import DomainRegistry

    assert DomainRegistry().get(CONCERNS_DOMAIN_ID) is None
