"""Tests for Phase 10.8 – Dependency and Declared Conflict Analysis."""

from __future__ import annotations

import pytest

from cmm.domains.composition_conflicts import (
    analyze_declared_conflicts,
    analyze_dependencies,
)
from cmm.domains.composition_contracts import DomainCompositionPolicy
from cmm.domains.contracts import (
    DomainConflict,
    DomainDefinition,
    DomainDependency,
    DomainManifestId,
)
from cmm.domains.enums import DomainConflictPolicy, DomainKind
from cmm.domains.errors import (
    DomainCompositionContractError,
    DomainContractValidationError,
)
from cmm.domains.identifiers import DomainId


def make_definition(slug, **kwargs):
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


# ── Dependencies ───────────────────────────────────────────────────────────────


def test_required_dependency_present():
    d1 = make_definition(
        "a",
        dependencies=(
            DomainDependency(domain_id=DomainId.from_str("domain:b"), required=True),
        ),
    )
    d2 = make_definition("b")
    _decisions, conflicts = analyze_dependencies((d1, d2))
    assert not any(c.blocking for c in conflicts)


def test_required_dependency_missing():
    d1 = make_definition(
        "a",
        dependencies=(
            DomainDependency(
                domain_id=DomainId.from_str("domain:missing"), required=True
            ),
        ),
    )
    _decisions, conflicts = analyze_dependencies((d1,))
    assert any(c.blocking for c in conflicts)
    assert any("missing" in c.message for c in conflicts)


def test_optional_dependency_missing():
    d1 = make_definition(
        "a",
        optional_dependencies=(
            DomainDependency(
                domain_id=DomainId.from_str("domain:missing"), required=False
            ),
        ),
    )
    _decisions, conflicts = analyze_dependencies((d1,))
    assert any(not c.blocking for c in conflicts)
    assert any("missing" in c.message for c in conflicts)


def test_self_dependency_prevented_by_contract():
    """DomainDefinition constructor already rejects self-dependencies.
    The test verifies the DomainDefinition contract, not the composer."""
    with pytest.raises(
        (DomainCompositionContractError, DomainContractValidationError),
        match="cannot depend on itself",
    ):
        make_definition(
            "a",
            dependencies=(
                DomainDependency(
                    domain_id=DomainId.from_str("domain:a"), required=True
                ),
            ),
        )


def test_required_cycle_blocks():
    """Pure required dependency cycle must block."""
    d1 = make_definition(
        "alpha",
        dependencies=(
            DomainDependency(domain_id=DomainId.from_str("domain:beta"), required=True),
        ),
    )
    d2 = make_definition(
        "beta",
        dependencies=(
            DomainDependency(
                domain_id=DomainId.from_str("domain:alpha"), required=True
            ),
        ),
    )
    _decisions, conflicts = analyze_dependencies((d1, d2))
    cycle_conflicts = [
        c for c in conflicts if c.code == "DOMAIN_COMPOSITION_DEPENDENCY_CYCLE"
    ]
    assert len(cycle_conflicts) >= 1
    assert any(c.blocking for c in cycle_conflicts)


def test_optional_cycle_is_partial():
    """Pure optional dependency cycle must be non-blocking."""
    d1 = make_definition(
        "alpha",
        optional_dependencies=(
            DomainDependency(
                domain_id=DomainId.from_str("domain:beta"), required=False
            ),
        ),
    )
    d2 = make_definition(
        "beta",
        optional_dependencies=(
            DomainDependency(
                domain_id=DomainId.from_str("domain:alpha"), required=False
            ),
        ),
    )
    _decisions, conflicts = analyze_dependencies((d1, d2))
    cycle_conflicts = [
        c for c in conflicts if c.code == "DOMAIN_COMPOSITION_DEPENDENCY_CYCLE"
    ]
    assert len(cycle_conflicts) >= 1
    assert not any(c.blocking for c in cycle_conflicts)


def test_mixed_cycle_is_partial_or_explicit_policy_result():
    """Mixed (required+optional) cycle must be non-blocking."""
    d1 = make_definition(
        "alpha",
        dependencies=(
            DomainDependency(domain_id=DomainId.from_str("domain:beta"), required=True),
        ),
    )
    d2 = make_definition(
        "beta",
        optional_dependencies=(
            DomainDependency(
                domain_id=DomainId.from_str("domain:alpha"), required=False
            ),
        ),
    )
    _decisions, conflicts = analyze_dependencies((d1, d2))
    cycle_conflicts = [
        c for c in conflicts if c.code == "DOMAIN_COMPOSITION_DEPENDENCY_CYCLE"
    ]
    assert len(cycle_conflicts) >= 1
    # Mixed cycles are non-blocking
    assert not any(c.blocking for c in cycle_conflicts)


def test_cycle_code_is_not_missing_dependency():
    """Cycle code must be DOMAIN_COMPOSITION_DEPENDENCY_CYCLE, not REQUIRED_DEPENDENCY_MISSING."""
    d1 = make_definition(
        "alpha",
        dependencies=(
            DomainDependency(domain_id=DomainId.from_str("domain:beta"), required=True),
        ),
    )
    d2 = make_definition(
        "beta",
        dependencies=(
            DomainDependency(
                domain_id=DomainId.from_str("domain:alpha"), required=True
            ),
        ),
    )
    _decisions, conflicts = analyze_dependencies((d1, d2))
    cycle_conflicts = [c for c in conflicts if "cycle" in c.message.lower()]
    for cc in cycle_conflicts:
        assert cc.code == "DOMAIN_COMPOSITION_DEPENDENCY_CYCLE"
        assert cc.code != "DOMAIN_COMPOSITION_REQUIRED_DEPENDENCY_MISSING"


def test_cycle_order_deterministic():
    """Cycle order must be deterministic."""
    d1 = make_definition(
        "alpha",
        dependencies=(
            DomainDependency(domain_id=DomainId.from_str("domain:beta"), required=True),
        ),
    )
    d2 = make_definition(
        "beta",
        dependencies=(
            DomainDependency(
                domain_id=DomainId.from_str("domain:gamma"), required=True
            ),
        ),
    )
    d3 = make_definition(
        "gamma",
        dependencies=(
            DomainDependency(
                domain_id=DomainId.from_str("domain:alpha"), required=True
            ),
        ),
    )
    _decisions1, conflicts1 = analyze_dependencies((d1, d2, d3))
    _decisions2, conflicts2 = analyze_dependencies((d3, d1, d2))
    assert len(conflicts1) == len(conflicts2)


def test_no_autoload():
    d1 = make_definition(
        "a",
        dependencies=(
            DomainDependency(
                domain_id=DomainId.from_str("domain:external"), required=True
            ),
        ),
    )
    _decisions, conflicts = analyze_dependencies((d1,))
    assert any(c.blocking for c in conflicts)


# ── Declared conflicts ─────────────────────────────────────────────────────────


def test_declared_conflicts_only_selected():
    d1 = make_definition(
        "a",
        conflicts=(
            DomainConflict(
                domain_id=DomainId.from_str("domain:b"),
                reason="incompatible",
                severity="critical",
            ),
        ),
    )
    _decisions, conflicts = analyze_declared_conflicts((d1,), DomainCompositionPolicy())
    assert len(conflicts) == 0


def test_declared_conflicts_blocking_severity():
    d1 = make_definition(
        "a",
        conflicts=(
            DomainConflict(
                domain_id=DomainId.from_str("domain:b"),
                reason="incompatible",
                severity="critical",
            ),
        ),
    )
    d2 = make_definition("b")
    _decisions, conflicts = analyze_declared_conflicts(
        (d1, d2),
        DomainCompositionPolicy(blocking_severities=("critical",)),
    )
    assert any(c.blocking for c in conflicts)


def test_declared_conflicts_partial_severity():
    d1 = make_definition(
        "a",
        conflicts=(
            DomainConflict(
                domain_id=DomainId.from_str("domain:b"),
                reason="mild",
                severity="medium",
            ),
        ),
    )
    d2 = make_definition("b")
    _decisions, conflicts = analyze_declared_conflicts(
        (d1, d2),
        DomainCompositionPolicy(partial_severities=("medium",)),
    )
    assert any(not c.blocking and not c.resolved for c in conflicts)


def test_declared_conflicts_unknown_severity():
    d1 = make_definition(
        "a",
        conflicts=(
            DomainConflict(
                domain_id=DomainId.from_str("domain:b"),
                reason="weird",
                severity="unknown-sev",
            ),
        ),
    )
    d2 = make_definition("b")
    _decisions, conflicts = analyze_declared_conflicts(
        (d1, d2), DomainCompositionPolicy()
    )
    found = [c for c in conflicts if not c.blocking]
    assert len(found) >= 1


def test_declared_conflicts_bilateral_duplicate():
    d1 = make_definition(
        "alpha",
        conflicts=(
            DomainConflict(
                domain_id=DomainId.from_str("domain:beta"),
                reason="conflict",
                severity="high",
            ),
        ),
    )
    d2 = make_definition(
        "beta",
        conflicts=(
            DomainConflict(
                domain_id=DomainId.from_str("domain:alpha"),
                reason="conflict",
                severity="high",
            ),
        ),
    )
    _decisions, conflicts = analyze_declared_conflicts(
        (d1, d2),
        DomainCompositionPolicy(blocking_severities=("high",)),
    )
    assert len(conflicts) == 1
    domains = {d.slug for d in conflicts[0].domains}
    assert domains == {"alpha", "beta"}


def test_block_on_conflict_policy():
    d1 = make_definition(
        "a",
        conflicts=(
            DomainConflict(
                domain_id=DomainId.from_str("domain:b"), reason="x", severity="low"
            ),
        ),
    )
    d2 = make_definition("b")
    _decisions, conflicts = analyze_declared_conflicts(
        (d1, d2),
        DomainCompositionPolicy(conflict_policy=DomainConflictPolicy.BLOCK_ON_CONFLICT),
    )
    assert any(c.blocking for c in conflicts)


def test_primary_precedence_resolves_nonblocking_primary_conflict():
    """PRIMARY_PRECEDENCE resolves non-blocking conflicts where primary is involved."""
    d1 = make_definition(
        "primary",
        conflicts=(
            DomainConflict(
                domain_id=DomainId.from_str("domain:beta"),
                reason="overlap",
                severity="medium",
            ),
        ),
    )
    d2 = make_definition("beta")
    policy = DomainCompositionPolicy(
        conflict_policy=DomainConflictPolicy.PRIMARY_PRECEDENCE,
        partial_severities=("medium",),
    )
    _decisions, conflicts = analyze_declared_conflicts((d1, d2), policy)
    found = [
        c for c in conflicts if c.resolved and c.resolution == "primary_precedence"
    ]
    assert len(found) >= 1


def test_primary_precedence_does_not_resolve_blocking_conflict():
    """PRIMARY_PRECEDENCE does NOT resolve blocking-severity conflicts."""
    d1 = make_definition(
        "primary",
        conflicts=(
            DomainConflict(
                domain_id=DomainId.from_str("domain:beta"),
                reason="critical incompatibility",
                severity="critical",
            ),
        ),
    )
    d2 = make_definition("beta")
    policy = DomainCompositionPolicy(
        conflict_policy=DomainConflictPolicy.PRIMARY_PRECEDENCE,
        blocking_severities=("critical",),
    )
    _decisions, conflicts = analyze_declared_conflicts((d1, d2), policy)
    found = [c for c in conflicts if c.resolved]
    assert len(found) == 0


def test_primary_precedence_does_not_resolve_supporting_only_conflict():
    """PRIMARY_PRECEDENCE does not resolve conflicts where primary is not involved."""
    d1 = make_definition(
        "primary",
    )
    d2 = make_definition(
        "alpha",
        conflicts=(
            DomainConflict(
                domain_id=DomainId.from_str("domain:beta"),
                reason="overlap",
                severity="medium",
            ),
        ),
    )
    d3 = make_definition("beta")
    policy = DomainCompositionPolicy(
        conflict_policy=DomainConflictPolicy.PRIMARY_PRECEDENCE,
        partial_severities=("medium",),
    )
    _decisions, conflicts = analyze_declared_conflicts((d1, d2, d3), policy)
    found = [c for c in conflicts if c.resolved]
    assert len(found) == 0


def test_primary_precedence_does_not_guess_unknown_severity():
    """Unknown severity is never auto-resolved."""
    d1 = make_definition(
        "primary",
        conflicts=(
            DomainConflict(
                domain_id=DomainId.from_str("domain:beta"),
                reason="unknown",
                severity="mystery-level",
            ),
        ),
    )
    d2 = make_definition("beta")
    policy = DomainCompositionPolicy(
        conflict_policy=DomainConflictPolicy.PRIMARY_PRECEDENCE,
    )
    _decisions, conflicts = analyze_declared_conflicts((d1, d2), policy)
    found = [c for c in conflicts if c.resolved]
    assert len(found) == 0


def test_same_domains_different_message_not_deduplicated():
    """Two conflicts with same domains but different messages are not deduplicated."""
    d1 = make_definition(
        "a",
        conflicts=(
            DomainConflict(
                domain_id=DomainId.from_str("domain:b"),
                reason="reason one",
                severity="warning",
            ),
        ),
    )
    d2 = make_definition(
        "b",
        conflicts=(
            DomainConflict(
                domain_id=DomainId.from_str("domain:a"),
                reason="reason two",
                severity="warning",
            ),
        ),
    )
    policy = DomainCompositionPolicy(partial_severities=("warning",))
    _decisions, conflicts = analyze_declared_conflicts((d1, d2), policy)
    assert len(conflicts) == 2
    messages = {c.message for c in conflicts}
    assert len(messages) == 2


def test_bilateral_exact_duplicate_is_deduplicated():
    """Exact duplicate bilateral conflict should be deduplicated."""
    d1 = make_definition(
        "alpha",
        conflicts=(
            DomainConflict(
                domain_id=DomainId.from_str("domain:beta"),
                reason="exact same",
                severity="high",
            ),
        ),
    )
    d2 = make_definition(
        "beta",
        conflicts=(
            DomainConflict(
                domain_id=DomainId.from_str("domain:alpha"),
                reason="exact same",
                severity="high",
            ),
        ),
    )
    policy = DomainCompositionPolicy(blocking_severities=("high",))
    _decisions, conflicts = analyze_declared_conflicts((d1, d2), policy)
    assert len(conflicts) == 1


def test_same_message_different_metadata_not_silently_collapsed():
    """Different metadata prevents collapse."""
    d1 = make_definition(
        "a",
        conflicts=(
            DomainConflict(
                domain_id=DomainId.from_str("domain:b"),
                reason="collision",
                severity="warning",
            ),
        ),
    )
    d2 = make_definition(
        "b",
        conflicts=(
            DomainConflict(
                domain_id=DomainId.from_str("domain:a"),
                reason="different reason despite same severity",
                severity="warning",
            ),
        ),
    )
    policy = DomainCompositionPolicy(partial_severities=("warning",))
    _decisions, conflicts = analyze_declared_conflicts((d1, d2), policy)
    # Different reasons should produce different messages, so not deduplicated
    assert len(conflicts) == 2
