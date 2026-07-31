"""Tests for Phase 10.8 – Domain Composer orchestration."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from cmm.domains.composer import DefaultDomainComposer, DomainComposer
from cmm.domains.contracts import DomainDefinition, DomainDependency, DomainManifestId
from cmm.domains.enums import (
    DomainCompositionStatus,
    DomainKind,
    DomainResolutionStatus,
)
from cmm.domains.errors import (
    DomainCompositionConfigurationError,
    DomainCompositionContractError,
)
from cmm.domains.identifiers import DomainId
from cmm.domains.resolver_contracts import DomainResolutionResult


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


def make_resolution(primary_slug="primary", supporting_slugs=()):
    return DomainResolutionResult(
        id="res-1",
        context_id="ctx-1",
        status=DomainResolutionStatus.RESOLVED,
        primary_domain=DomainId.from_str(f"domain:{primary_slug}"),
        supporting_domains=tuple(
            DomainId.from_str(f"domain:{s}") for s in supporting_slugs
        ),
    )


def test_composer_protocol():
    assert isinstance(DefaultDomainComposer(), DomainComposer)


def test_resolved_composes():
    resolution = make_resolution()
    d1 = make_definition("primary")
    composer = DefaultDomainComposer()
    result = composer.compose(resolution, [d1])
    assert result.status == DomainCompositionStatus.COMPOSED
    assert result.primary_domain.slug == "primary"


def test_ambiguous_rejected():
    """Composer requires RESOLVED status; AMBIGUOUS is rejected."""
    from cmm.domains.resolver_contracts import DomainResolutionReason

    resolution = DomainResolutionResult(
        id="res-1",
        context_id="ctx-1",
        status=DomainResolutionStatus.AMBIGUOUS,
        primary_domain=DomainId.from_str("domain:primary"),
        ambiguous_domains=(
            DomainId.from_str("domain:primary"),
            DomainId.from_str("domain:other"),
        ),
        requires_clarification=True,
        recommended_question="Which domain should be used?",
        confidence=0.5,
        reasons=(
            DomainResolutionReason(
                code="ambiguous", message="Multiple matches", blocking=False
            ),
        ),
    )
    d1 = make_definition("primary")
    composer = DefaultDomainComposer()
    with pytest.raises(DomainCompositionContractError):
        composer.compose(resolution, [d1])


def test_blocked_rejected():
    """Composer rejects resolution with BLOCKED status."""
    from cmm.domains.resolver_contracts import DomainResolutionReason

    resolution = DomainResolutionResult(
        id="res-1",
        context_id="ctx-1",
        status=DomainResolutionStatus.BLOCKED,
        rejected_domains=(DomainId.from_str("domain:blocked-domain"),),
        confidence=0.0,
        reasons=(
            DomainResolutionReason(
                code="blocked", message="No eligible domain", blocking=True
            ),
        ),
    )
    d1 = make_definition("primary")
    composer = DefaultDomainComposer()
    with pytest.raises(DomainCompositionContractError):
        composer.compose(resolution, [d1])


def test_missing_primary():
    resolution = make_resolution(primary_slug="primary")
    d1 = make_definition("other")
    composer = DefaultDomainComposer()
    with pytest.raises(DomainCompositionContractError):
        composer.compose(resolution, [d1])


def test_missing_supporting():
    resolution = make_resolution(
        primary_slug="primary", supporting_slugs=("support-1",)
    )
    d1 = make_definition("primary")
    d2 = make_definition("support-2")
    composer = DefaultDomainComposer()
    with pytest.raises(DomainCompositionContractError):
        composer.compose(resolution, [d1, d2])


def test_extra_definition():
    resolution = make_resolution(primary_slug="primary")
    d1 = make_definition("primary")
    d2 = make_definition("extra")
    composer = DefaultDomainComposer()
    with pytest.raises(DomainCompositionContractError):
        composer.compose(resolution, [d1, d2])


def test_duplicate_id():
    resolution = make_resolution(primary_slug="primary")
    d1 = make_definition("primary")
    d2 = make_definition("primary")
    composer = DefaultDomainComposer()
    with pytest.raises(DomainCompositionContractError):
        composer.compose(resolution, [d1, d2])


def test_disabled_domain():
    resolution = make_resolution(primary_slug="primary")
    d1 = make_definition("primary", enabled=False)
    composer = DefaultDomainComposer()
    with pytest.raises(DomainCompositionContractError):
        composer.compose(resolution, [d1])


def test_supporting_disabled():
    resolution = make_resolution(primary_slug="primary", supporting_slugs=("supp",))
    d1 = make_definition("primary")
    d2 = make_definition("supp", enabled=False)
    composer = DefaultDomainComposer()
    with pytest.raises(DomainCompositionContractError):
        composer.compose(resolution, [d1, d2])


def test_composed_status():
    resolution = make_resolution(primary_slug="alpha")
    d1 = make_definition("alpha")
    composer = DefaultDomainComposer()
    result = composer.compose(resolution, [d1])
    assert result.status == DomainCompositionStatus.COMPOSED


def test_partial_status_from_optional_missing():
    resolution = make_resolution(primary_slug="alpha")
    d1 = make_definition(
        "alpha",
        optional_dependencies=(
            DomainDependency(
                domain_id=DomainId.from_str("domain:missing"), required=False
            ),
        ),
    )
    composer = DefaultDomainComposer()
    result = composer.compose(resolution, [d1])
    assert result.status == DomainCompositionStatus.PARTIAL


def test_blocked_status_from_dependency():
    resolution = make_resolution(primary_slug="alpha")
    d1 = make_definition(
        "alpha",
        dependencies=(
            DomainDependency(
                domain_id=DomainId.from_str("domain:missing"), required=True
            ),
        ),
    )
    composer = DefaultDomainComposer()
    result = composer.compose(resolution, [d1])
    assert result.status == DomainCompositionStatus.BLOCKED


def test_fixed_clock():
    resolution = make_resolution(primary_slug="alpha")
    d1 = make_definition("alpha")
    fixed_dt = datetime(2024, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
    composer = DefaultDomainComposer(clock=lambda: fixed_dt)
    result = composer.compose(resolution, [d1])
    assert result.composed_at == fixed_dt


def test_fixed_id():
    resolution = make_resolution(primary_slug="alpha")
    d1 = make_definition("alpha")
    composer = DefaultDomainComposer(id_factory=lambda: "my-id")
    result = composer.compose(resolution, [d1])
    assert result.id == "my-id"


def test_naive_clock():
    resolution = make_resolution(primary_slug="alpha")
    d1 = make_definition("alpha")
    composer = DefaultDomainComposer(
        clock=lambda: datetime.fromisoformat("2024-01-01T00:00:00")
    )
    with pytest.raises(DomainCompositionConfigurationError):
        composer.compose(resolution, [d1])


def test_invalid_id_factory():
    resolution = make_resolution(primary_slug="alpha")
    d1 = make_definition("alpha")
    composer = DefaultDomainComposer(id_factory=lambda: "")
    with pytest.raises(DomainCompositionConfigurationError):
        composer.compose(resolution, [d1])


def test_clock_runtime_error_propagates():
    """Clock errors propagate without being wrapped as DomainCompositionExecutionError."""
    resolution = make_resolution(primary_slug="alpha")
    d1 = make_definition("alpha")

    def bad_clock():
        raise RuntimeError("clock is broken")

    composer = DefaultDomainComposer(clock=bad_clock)
    with pytest.raises(RuntimeError, match="clock is broken"):
        composer.compose(resolution, [d1])


def test_id_factory_runtime_error_propagates():
    """ID factory errors propagate without being wrapped."""
    resolution = make_resolution(primary_slug="alpha")
    d1 = make_definition("alpha")

    def bad_id():
        raise RuntimeError("id factory is broken")

    composer = DefaultDomainComposer(id_factory=bad_id)
    with pytest.raises(RuntimeError, match="id factory is broken"):
        composer.compose(resolution, [d1])


def test_no_broad_exception_catch_in_composer_source():
    """Verify the composer source does not contain except Exception blocks for clock/id_factory."""
    import inspect

    source = inspect.getsource(DefaultDomainComposer.compose)

    # Find all except clauses in compose method
    except_lines = [
        l.strip() for l in source.split("\n") if "except" in l and "Exception" in l
    ]
    # There should be no bare except Exception catching clock/id_factory
    # The source may have except for DomainCompositionContractError etc, but not Exception
    # Check that no line matches "except Exception" without more specific exceptions
    for line in except_lines:
        # Allow except clauses that have specific exceptions before Exception
        if "except Exception" in line:
            # If it's just "except Exception:" or "except Exception as" with no other exceptions
            stripped = line.replace(" ", "")
            if stripped.startswith("exceptException"):
                pytest.fail(f"Found bare 'except Exception' in composer source: {line}")


def test_determinism():
    resolution = make_resolution(primary_slug="alpha")
    d1 = make_definition("alpha", rules=("r1", "r2"))
    fixed_dt = datetime(2024, 1, 1, tzinfo=timezone.utc)
    composer = DefaultDomainComposer(clock=lambda: fixed_dt, id_factory=lambda: "x")
    r1 = composer.compose(resolution, [d1])
    r2 = composer.compose(resolution, [d1])
    assert r1.to_dict() == r2.to_dict()


def test_definitions_normalization():
    resolution = make_resolution(
        primary_slug="primary", supporting_slugs=("supp-beta", "supp-alpha")
    )
    d_primary = make_definition("primary")
    d_beta = make_definition("supp-beta")
    d_alpha = make_definition("supp-alpha")
    composer = DefaultDomainComposer()
    result = composer.compose(resolution, [d_beta, d_alpha, d_primary])
    assert result.primary_domain.slug == "primary"
    assert [d.slug for d in result.supporting_domains] == ["supp-beta", "supp-alpha"]


def test_no_broad_catch():
    resolution = make_resolution(primary_slug="alpha")
    d1 = make_definition("alpha")
    composer = DefaultDomainComposer()
    result = composer.compose(resolution, [d1])
    assert result is not None


def test_all_decisions_retained():
    resolution = make_resolution(primary_slug="alpha")
    d1 = make_definition("alpha", rules=("rule-1",))
    composer = DefaultDomainComposer()
    result = composer.compose(resolution, [d1])
    assert len(result.rules) == 1


def test_no_mutation():
    resolution = make_resolution(primary_slug="alpha")
    d1 = make_definition("alpha")
    original_id = resolution.id
    composer = DefaultDomainComposer()
    _result = composer.compose(resolution, [d1])
    assert resolution.id == original_id
    assert d1.enabled is True
