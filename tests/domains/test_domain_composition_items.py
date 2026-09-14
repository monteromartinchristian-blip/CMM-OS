"""Tests for Phase 10.8 – Composition Items (reference composition, profile, presentation)."""

from __future__ import annotations

from types import MappingProxyType

from cmm.domains.composition_contracts import (
    DomainCompositionPolicy,
)
from cmm.domains.composition_items import (
    compose_capability_items,
    compose_presentation,
    compose_reasoning_profile,
    compose_reference_items,
)
from cmm.domains.contracts import (
    DomainCapability,
    DomainDefinition,
    DomainManifestId,
)
from cmm.domains.enums import DomainConflictPolicy, DomainKind
from cmm.domains.identifiers import DomainId

# ── Helpers ────────────────────────────────────────────────────────────────────


def make_definition(slug, **kwargs):
    """Create a minimal DomainDefinition for testing."""
    defaults = {
        "id": DomainId.from_str(f"domain:{slug}"),
        "name": slug,
        "display_name": slug.title(),
        "version": "1.0.0",
        "kind": DomainKind.CORE,
        "description": f"Test domain {slug}",
        "manifest_id": DomainManifestId(slug=slug, version="1.0.0"),
        "enabled": True,
    }
    defaults.update(kwargs)
    return DomainDefinition(**defaults)


# ── Reference item composition ─────────────────────────────────────────────────


def test_reference_items_empty_definitions():
    items, decisions = compose_reference_items(
        category="rules", definitions=(), value_getter=lambda d: d.rules
    )
    assert items == ()
    assert decisions == ()


def test_reference_items_primary_precedence():
    d1 = make_definition("primary", rules=("rule-a", "rule-b"))
    d2 = make_definition("supporting", rules=("rule-b", "rule-c"))
    items, _decisions = compose_reference_items(
        category="rules",
        definitions=(d1, d2),
        value_getter=lambda d: d.rules,
    )
    ids = [i.identifier for i in items]
    assert ids == ["rule-a", "rule-b", "rule-c"]
    rule_b = next(i for i in items if i.identifier == "rule-b")
    contributing_slugs = {d.slug for d in rule_b.contributing_domains}
    assert contributing_slugs == {"primary", "supporting"}
    assert rule_b.primary_contributor.slug == "primary"


def test_reference_items_exact_duplicate_collapse():
    d1 = make_definition("a", rules=("shared",))
    d2 = make_definition("b", rules=("shared",))
    items, decisions = compose_reference_items(
        category="rules",
        definitions=(d1, d2),
        value_getter=lambda d: d.rules,
    )
    assert len(items) == 1
    assert items[0].identifier == "shared"
    assert len(items[0].contributing_domains) == 2
    assert any(d.code == "DOMAIN_COMPOSITION_DUPLICATE_COLLAPSED" for d in decisions)


def test_reference_items_stable_ordering():
    d1 = make_definition("alpha", rules=("rule-2", "rule-1"))
    d2 = make_definition("beta", rules=("rule-3",))
    items1, _ = compose_reference_items(
        category="rules",
        definitions=(d1, d2),
        value_getter=lambda d: d.rules,
    )
    items2, _ = compose_reference_items(
        category="rules",
        definitions=(d1, d2),
        value_getter=lambda d: d.rules,
    )
    assert [i.identifier for i in items1] == [i.identifier for i in items2]


def test_reference_items_no_semantic_lowercase():
    d1 = make_definition("a", rules=("Rule-A",))
    d2 = make_definition("b", rules=("rule-a",))
    items, _ = compose_reference_items(
        category="rules",
        definitions=(d1, d2),
        value_getter=lambda d: d.rules,
    )
    assert len(items) == 2


def test_capability_composition_unique_key():
    d1 = make_definition(
        "alpha",
        capabilities=(
            DomainCapability(
                name="analyze",
                kind="reasoning",
                provided_by=DomainId.from_str("domain:alpha"),
                version="1.0",
            ),
        ),
    )
    d2 = make_definition(
        "beta",
        capabilities=(
            DomainCapability(
                name="analyze",
                kind="reasoning",
                provided_by=DomainId.from_str("domain:beta"),
                version="1.0",
            ),
        ),
    )
    items, _decisions = compose_capability_items((d1, d2))
    assert len(items) == 1
    assert "capability:reasoning:analyze:1.0" == items[0].identifier


# ── Profile composition ────────────────────────────────────────────────────────


def test_profile_primary_base():
    d1 = make_definition("primary", reasoning_profile="default")
    d2 = make_definition("supporting", reasoning_profile="extra")
    profile, _ = compose_reasoning_profile((d1, d2))
    assert profile.base_profile == "default"
    assert "extra" in profile.contributing_profiles
    assert d1.id.slug in {d.slug for d in profile.contributing_domains}
    assert d2.id.slug in {d.slug for d in profile.contributing_domains}


def test_profile_primary_without_profile():
    d1 = make_definition("primary", reasoning_profile=None)
    d2 = make_definition("supporting", reasoning_profile="helper")
    profile, _ = compose_reasoning_profile((d1, d2))
    assert profile.base_profile is None
    assert "helper" in profile.contributing_profiles


def test_profile_metadata_ignored_when_no_reasoning_profile():
    """Profile metadata is only read from metadata['reasoning_profile'];
    if definition.metadata is None or missing the key, no values are extracted."""
    d1 = make_definition("primary", reasoning_profile="base")
    d2 = make_definition("supporting")
    profile, _ = compose_reasoning_profile((d1, d2))
    assert profile.base_profile == "base"


def test_profile_structure_preserved():
    d1 = make_definition("primary", reasoning_profile="p1")
    profile, _ = compose_reasoning_profile((d1,))
    assert profile.base_profile == "p1"
    assert isinstance(profile.contributing_domains, tuple)
    assert isinstance(profile.added_rules, tuple)


# ── Presentation composition ───────────────────────────────────────────────────


def test_presentation_primary_baseline():
    d1 = make_definition(
        "primary",
        presentation_policy=MappingProxyType({"theme": "dark", "lang": "en"}),
    )
    d2 = make_definition(
        "supporting",
        presentation_policy=MappingProxyType({"lang": "es", "font": "mono"}),
    )
    policy = DomainCompositionPolicy()
    pres, _decisions, _conflicts = compose_presentation((d1, d2), policy)
    vals = dict(pres.values)
    assert vals["theme"] == "dark"
    assert vals["lang"] == "en"
    assert vals["font"] == "mono"


def test_presentation_same_value_merges_provenance():
    d1 = make_definition(
        "primary", presentation_policy=MappingProxyType({"theme": "dark"})
    )
    d2 = make_definition(
        "supporting", presentation_policy=MappingProxyType({"theme": "dark"})
    )
    policy = DomainCompositionPolicy()
    pres, _decisions, _conflicts = compose_presentation((d1, d2), policy)
    assert "domain:primary" in str(pres.provenance)
    assert "domain:supporting" in str(pres.provenance)


def test_presentation_block_on_conflict():
    d1 = make_definition(
        "primary", presentation_policy=MappingProxyType({"theme": "dark"})
    )
    d2 = make_definition(
        "supporting", presentation_policy=MappingProxyType({"theme": "light"})
    )
    policy = DomainCompositionPolicy(
        conflict_policy=DomainConflictPolicy.BLOCK_ON_CONFLICT,
    )
    _pres, _decisions, conflicts = compose_presentation((d1, d2), policy)
    assert any(
        c.code == "DOMAIN_COMPOSITION_PRESENTATION_CONFLICT" and c.blocking
        for c in conflicts
    )


def test_presentation_primary_precedence():
    d1 = make_definition(
        "primary", presentation_policy=MappingProxyType({"theme": "dark"})
    )
    d2 = make_definition(
        "supporting", presentation_policy=MappingProxyType({"theme": "light"})
    )
    policy = DomainCompositionPolicy(
        conflict_policy=DomainConflictPolicy.PRIMARY_PRECEDENCE,
    )
    pres, _decisions, conflicts = compose_presentation((d1, d2), policy)
    vals = dict(pres.values)
    assert vals["theme"] == "dark"
    theme_conflict = next((c for c in conflicts if "theme" in c.message), None)
    assert theme_conflict is not None
    assert theme_conflict.resolved is True


def test_presentation_deterministic_key_order():
    d1 = make_definition(
        "primary",
        presentation_policy=MappingProxyType({"b": 1, "a": 2, "c": 3}),
    )
    policy = DomainCompositionPolicy()
    pres, _, _ = compose_presentation((d1,), policy)
    keys = list(pres.values.keys())
    assert keys == ["a", "b", "c"]
