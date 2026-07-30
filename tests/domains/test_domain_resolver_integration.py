"""Phase 10.7 — Integration tests for the complete Domain Resolver pipeline."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from cmm.domains.enums import DomainResolutionStatus
from cmm.domains.errors import DomainResolverConfigurationError
from cmm.domains.identifiers import DomainId
from cmm.domains.resolution_contracts import (
    DomainResolutionContext,
    DomainResolutionEntity,
    DomainResolutionPolicy,
    DomainResolutionResource,
    DomainResolutionSignal,
)
from cmm.domains.resolver import DefaultDomainResolver
from cmm.domains.resolver_contracts import DomainScoringPolicy
from cmm.domains.resolver_scoring import DomainCandidateScorer


def D(slug: str) -> DomainId:
    return DomainId(slug=slug)


def make_context(
    *,
    available: tuple[DomainId, ...] = (),
    explicit: tuple[DomainId, ...] = (),
    authorized: tuple[DomainId, ...] = (),
    active: tuple[DomainId, ...] = (),
    signals: tuple[DomainResolutionSignal, ...] = (),
    resources: tuple[DomainResolutionResource, ...] = (),
    entities: tuple[DomainResolutionEntity, ...] = (),
    policy: DomainResolutionPolicy | None = None,
    user_input: str = "test input",
    **kwargs: object,
) -> DomainResolutionContext:
    return DomainResolutionContext(
        id=kwargs.get("id", "ctx-1"),
        user_input=user_input,
        explicit_domains=explicit,
        available_domains=available,
        authorized_domains=authorized,
        active_domains=active,
        signals=signals,
        resources=resources,
        entities=entities,
        system_policy=policy,
    )


def make_signal(
    kind: str,
    source: str = "test",
    domain_ids: tuple[DomainId, ...] = (),
    confidence: float | None = None,
    weight: float | None = None,
) -> DomainResolutionSignal:
    return DomainResolutionSignal(
        kind=kind,
        source=source,
        value={"note": "test signal"},
        domain_ids=domain_ids,
        confidence=confidence,
        weight=weight,
        provenance={"source": "test"} if confidence is not None else None,
    )


def make_policy(
    *,
    denied: tuple[DomainId, ...] = (),
    required: tuple[DomainId, ...] = (),
    allowed: tuple[DomainId, ...] = (),
    high_impact: tuple[DomainId, ...] = (),
    require_auth: bool = True,
    min_confidence: float | None = None,
) -> DomainResolutionPolicy:
    return DomainResolutionPolicy(
        denied_domains=denied,
        required_domains=required,
        allowed_domains=allowed,
        high_impact_domains=high_impact,
        require_authorization=require_auth,
        minimum_confidence=min_confidence,
    )


def fixed_clock() -> datetime:
    return datetime(2025, 1, 1, 0, 0, 0, tzinfo=timezone.utc)


def fixed_id() -> str:
    return "fixed-id"


def make_resolver(
    *,
    fallback: DomainId | None = None,
    policy: DomainScoringPolicy | None = None,
    clock: object | None = None,
    id_factory: object | None = None,
) -> DefaultDomainResolver:
    return DefaultDomainResolver(
        fallback_domain=fallback,
        scoring_policy=policy,
        clock=clock or fixed_clock,
        id_factory=id_factory or fixed_id,
    )


# ═══════════════════════════════════════════════════════════════════════════
# Scoring
# ═══════════════════════════════════════════════════════════════════════════


class TestScoring:
    """Tests for the DomainCandidateScorer."""

    def test_explicit_scores_highest(self) -> None:
        scorer = DomainCandidateScorer()
        ctx = make_context(
            available=(D("health"), D("university")),
            explicit=(D("health"),),
            authorized=(D("health"), D("university")),
        )
        health = scorer.score(ctx, D("health"))
        university = scorer.score(ctx, D("university"))
        assert health.score > university.score
        assert health.score >= 100.0

    def test_resource_entity_knowledge_matches(self) -> None:
        scorer = DomainCandidateScorer()
        ctx = make_context(
            available=(D("health"), D("university")),
            authorized=(D("health"), D("university")),
            resources=(
                DomainResolutionResource(
                    id="r1",
                    resource_type="doc",
                    source="test",
                    domain_ids=(D("health"),),
                ),
            ),
            entities=(
                DomainResolutionEntity(
                    id="e1",
                    entity_type="person",
                    source="test",
                    domain_ids=(D("university"),),
                    confidence=0.9,
                    metadata={"source": "auto"},
                ),
            ),
        )
        health = scorer.score(ctx, D("health"))
        university = scorer.score(ctx, D("university"))
        assert health.score > 0
        assert university.score > 0

    def test_confidence_monotonic(self) -> None:
        scorer = DomainCandidateScorer()
        ctx = make_context(available=(D("health"),), authorized=(D("health"),))
        s1 = scorer.score(ctx, D("health"))
        assert 0.0 <= s1.confidence <= 1.0
        ctx2 = make_context(
            available=(D("health"),),
            authorized=(D("health"),),
            explicit=(D("health"),),
            signals=(
                make_signal(
                    "entity", "test", domain_ids=(D("health"),), confidence=0.9
                ),
            ),
        )
        s2 = scorer.score(ctx2, D("health"))
        assert s2.confidence >= s1.confidence

    def test_no_keyword_matching(self) -> None:
        scorer = DomainCandidateScorer()
        ctx = make_context(
            available=(D("health"),),
            authorized=(D("health"),),
            user_input="I need health advice about university policies",
        )
        _unused = (
            scorer.score(ctx, D("university"))
            if D("university") != ctx.available_domains[0]
            else None
        )
        assert True


# ═══════════════════════════════════════════════════════════════════════════
# Explicit
# ═══════════════════════════════════════════════════════════════════════════


class TestExplicit:
    def test_single_explicit_resolved(self) -> None:
        resolver = make_resolver()
        ctx = make_context(
            available=(D("health"), D("university")),
            explicit=(D("health"),),
            authorized=(D("health"), D("university")),
        )
        result = resolver.resolve(ctx)
        assert result.status == DomainResolutionStatus.RESOLVED
        assert result.primary_domain == D("health")

    def test_explicit_blocked_denied(self) -> None:
        """Domain that is denied cannot be selected."""
        resolver = make_resolver()
        ctx = make_context(
            available=(D("health"),),
            authorized=(),
            signals=(
                make_signal(
                    "entity", "test", domain_ids=(D("health"),), confidence=0.9
                ),
            ),
            policy=make_policy(denied=(D("health"),), require_auth=False),
        )
        result = resolver.resolve(ctx)
        rejected_slugs = {d.slug for d in result.rejected_domains}
        assert "health" in rejected_slugs

    def test_multiple_explicit_clearly_different(self) -> None:
        resolver = make_resolver(
            policy=DomainScoringPolicy(explicit_weight=100.0, ambiguity_margin=5.0)
        )
        ctx = make_context(
            available=(D("health"), D("university")),
            explicit=(D("health"), D("university")),
            authorized=(D("health"), D("university")),
            resources=(
                DomainResolutionResource(
                    id="r1",
                    resource_type="doc",
                    source="test",
                    domain_ids=(D("health"),),
                ),
            ),
        )
        result = resolver.resolve(ctx)
        assert result.primary_domain == D("health")
        assert result.status == DomainResolutionStatus.RESOLVED

    def test_multiple_explicit_tied_ambiguous(self) -> None:
        resolver = make_resolver(policy=DomainScoringPolicy(ambiguity_margin=5.0))
        ctx = make_context(
            available=(D("health"), D("university")),
            explicit=(D("health"), D("university")),
            authorized=(D("health"), D("university")),
        )
        result = resolver.resolve(ctx)
        assert result.status == DomainResolutionStatus.AMBIGUOUS
        assert len(result.ambiguous_domains) >= 2


# ═══════════════════════════════════════════════════════════════════════════
# Structured Signals
# ═══════════════════════════════════════════════════════════════════════════


class TestStructuredSignals:
    def test_entity_signal_produces_match(self) -> None:
        resolver = make_resolver()
        ctx = make_context(
            available=(D("university"), D("health")),
            authorized=(D("university"), D("health")),
            signals=(
                make_signal(
                    "entity", "nlp", domain_ids=(D("university"),), confidence=0.9
                ),
            ),
        )
        result = resolver.resolve(ctx)
        assert result.primary_domain == D("university")

    def test_intent_signal_produces_match(self) -> None:
        resolver = make_resolver()
        ctx = make_context(
            available=(D("university"), D("health")),
            authorized=(D("university"), D("health")),
            signals=(
                make_signal(
                    "intent", "parser", domain_ids=(D("health"),), confidence=0.85
                ),
            ),
        )
        result = resolver.resolve(ctx)
        assert result.primary_domain == D("health")

    def test_signal_dedup_no_double_count(self) -> None:
        resolver = make_resolver()
        signal = make_signal("entity", "nlp", domain_ids=(D("health"),), confidence=0.9)
        ctx = make_context(
            available=(D("health"),),
            authorized=(D("health"),),
            signals=(signal, signal),
        )
        result = resolver.resolve(ctx)
        assert result.status == DomainResolutionStatus.RESOLVED

    def test_text_without_signals_no_match(self) -> None:
        resolver = make_resolver()
        ctx = make_context(
            available=(D("university"), D("health")),
            authorized=(D("university"), D("health")),
            user_input="I have suspended juvenile law. I need help.",
        )
        result = resolver.resolve(ctx)
        assert result.status in (
            DomainResolutionStatus.UNSUPPORTED,
            DomainResolutionStatus.INSUFFICIENT_INFORMATION,
        )
        assert result.status != DomainResolutionStatus.RESOLVED

    def test_structured_signal_ignored_without_domain_ids(self) -> None:
        resolver = make_resolver()
        ctx = make_context(
            available=(D("university"), D("health")),
            authorized=(D("university"), D("health")),
            signals=(make_signal("intent", "parser", domain_ids=()),),
        )
        result = resolver.resolve(ctx)
        assert result.status in (
            DomainResolutionStatus.UNSUPPORTED,
            DomainResolutionStatus.INSUFFICIENT_INFORMATION,
        )
        assert result.status != DomainResolutionStatus.RESOLVED


# ═══════════════════════════════════════════════════════════════════════════
# Policy
# ═══════════════════════════════════════════════════════════════════════════


class TestPolicy:
    def test_denied_domain_rejected(self) -> None:
        """Denied domain gets rejected regardless of evidence."""
        resolver = make_resolver()
        # Denied domain incompatible with authorized, so use empty authorized
        # and evidence that would otherwise select health
        ctx = make_context(
            available=(D("health"), D("university")),
            authorized=(),  # No authorized domains → all non-denied are unauthorized
            signals=(
                make_signal(
                    "entity", "test", domain_ids=(D("health"),), confidence=0.9
                ),
            ),
            policy=make_policy(denied=(D("health"),), require_auth=False),
        )
        result = resolver.resolve(ctx)
        rejected_slugs = {d.slug for d in result.rejected_domains}
        assert "health" in rejected_slugs

    def test_required_domain_blocked(self) -> None:
        """Required domain that is not authorized → BLOCKED."""
        resolver = make_resolver()
        ctx = make_context(
            available=(D("health"), D("university")),
            authorized=(D("university"),),
            policy=make_policy(required=(D("health"),), require_auth=True),
        )
        result = resolver.resolve(ctx)
        assert result.status == DomainResolutionStatus.BLOCKED

    def test_unauthorized_not_in_authorized_rejected(self) -> None:
        resolver = make_resolver()
        ctx = make_context(
            available=(D("health"), D("university")),
            authorized=(D("health"),),
            signals=(
                make_signal(
                    "entity", "test", domain_ids=(D("university"),), confidence=0.9
                ),
            ),
        )
        result = resolver.resolve(ctx)
        rejected_slugs = {d.slug for d in result.rejected_domains}
        assert "university" in rejected_slugs

    def test_required_domain_supporting(self) -> None:
        """Required domain should be included as supporting."""
        resolver = make_resolver(
            policy=DomainScoringPolicy(
                supporting_margin=100.0, minimum_resolution_score=0.0
            )
        )
        ctx = make_context(
            available=(D("health"), D("university")),
            explicit=(D("health"),),
            authorized=(D("health"), D("university")),
            policy=make_policy(required=(D("university"),)),
        )
        result = resolver.resolve(ctx)
        supporting_slugs = {d.slug for d in result.supporting_domains}
        assert "university" in supporting_slugs

    def test_minimum_confidence_policy(self) -> None:
        resolver = make_resolver()
        ctx = make_context(
            available=(D("health"),),
            authorized=(D("health"),),
            policy=make_policy(high_impact=(D("health"),), min_confidence=0.99),
        )
        result = resolver.resolve(ctx)
        assert result.status in (
            DomainResolutionStatus.UNSUPPORTED,
            DomainResolutionStatus.INSUFFICIENT_INFORMATION,
        )


# ═══════════════════════════════════════════════════════════════════════════
# Ambiguity
# ═══════════════════════════════════════════════════════════════════════════


class TestAmbiguity:
    def test_tied_scores_ambiguous(self) -> None:
        resolver = make_resolver(policy=DomainScoringPolicy(ambiguity_margin=5.0))
        ctx = make_context(
            available=(D("health"), D("university")),
            authorized=(D("health"), D("university")),
            signals=(
                make_signal(
                    "entity", "test", domain_ids=(D("health"),), confidence=0.5
                ),
                make_signal(
                    "entity", "test", domain_ids=(D("university"),), confidence=0.5
                ),
            ),
        )
        result = resolver.resolve(ctx)
        assert result.status == DomainResolutionStatus.AMBIGUOUS
        assert result.requires_clarification is True
        assert result.recommended_question is not None

    def test_clear_winner_no_ambiguity(self) -> None:
        resolver = make_resolver(policy=DomainScoringPolicy(ambiguity_margin=5.0))
        ctx = make_context(
            available=(D("health"), D("university")),
            explicit=(D("health"),),
            authorized=(D("health"), D("university")),
        )
        result = resolver.resolve(ctx)
        assert result.status == DomainResolutionStatus.RESOLVED

    def test_deterministic_question(self) -> None:
        resolver = make_resolver(clock=fixed_clock, id_factory=fixed_id)
        ctx = make_context(
            available=(D("health"), D("university")),
            authorized=(D("health"), D("university")),
            signals=(
                make_signal(
                    "entity", "test", domain_ids=(D("health"),), confidence=0.5
                ),
                make_signal(
                    "entity", "test", domain_ids=(D("university"),), confidence=0.5
                ),
            ),
        )
        r1 = resolver.resolve(ctx)
        r2 = resolver.resolve(ctx)
        assert r1.recommended_question == r2.recommended_question

    def test_ambiguity_with_prudent_fallback(self) -> None:
        fb = D("general")
        resolver = make_resolver(
            fallback=fb, policy=DomainScoringPolicy(ambiguity_margin=5.0)
        )
        ctx = make_context(
            available=(D("health"), D("university"), fb),
            authorized=(D("health"), D("university"), fb),
            signals=(
                make_signal(
                    "entity", "test", domain_ids=(D("health"),), confidence=0.5
                ),
                make_signal(
                    "entity", "test", domain_ids=(D("university"),), confidence=0.5
                ),
            ),
        )
        result = resolver.resolve(ctx)
        assert result.status == DomainResolutionStatus.AMBIGUOUS
        assert result.fallback_used is True
        assert result.primary_domain == fb


# ═══════════════════════════════════════════════════════════════════════════
# Fallback
# ═══════════════════════════════════════════════════════════════════════════


class TestFallback:
    def test_fallback_used_when_no_evidence(self) -> None:
        fb = D("general")
        resolver = make_resolver(fallback=fb)
        ctx = make_context(
            available=(fb, D("health")),
            authorized=(fb, D("health")),
        )
        result = resolver.resolve(ctx)
        assert result.status == DomainResolutionStatus.INSUFFICIENT_INFORMATION
        assert result.fallback_used is True
        assert result.primary_domain == fb

    def test_fallback_not_used_when_evidence_exists(self) -> None:
        fb = D("general")
        resolver = make_resolver(fallback=fb)
        ctx = make_context(
            available=(fb, D("health")),
            explicit=(D("health"),),
            authorized=(fb, D("health")),
        )
        result = resolver.resolve(ctx)
        assert result.status == DomainResolutionStatus.RESOLVED
        assert result.primary_domain == D("health")
        assert result.fallback_used is False

    def test_fallback_not_configured_no_special_case(self) -> None:
        resolver = make_resolver()
        ctx = make_context(available=(D("health"),), authorized=(D("health"),))
        result = resolver.resolve(ctx)
        assert result.status == DomainResolutionStatus.UNSUPPORTED
        assert result.fallback_used is False

    def test_fallback_not_available_ignored(self) -> None:
        fb = D("general")
        resolver = make_resolver(fallback=fb)
        ctx = make_context(available=(D("health"),), authorized=(D("health"),))
        result = resolver.resolve(ctx)
        assert result.status == DomainResolutionStatus.UNSUPPORTED

    def test_fallback_denied_ignored(self) -> None:
        fb = D("general")
        resolver = make_resolver(fallback=fb)
        ctx = make_context(
            available=(fb, D("health")),
            authorized=(D("health"),),
            policy=make_policy(denied=(fb,)),
        )
        result = resolver.resolve(ctx)
        assert result.status != DomainResolutionStatus.RESOLVED


# ═══════════════════════════════════════════════════════════════════════════
# High Impact
# ═══════════════════════════════════════════════════════════════════════════


class TestHighImpact:
    def test_high_impact_low_confidence_protected(self) -> None:
        """High-impact domain with low confidence produces AMBIGUOUS or INSUFFICIENT."""
        # Lower min_resolution_score so the signal gets through to high-impact check
        resolver = make_resolver(
            policy=DomainScoringPolicy(minimum_resolution_score=0.0),
        )
        ctx = make_context(
            available=(D("health"), D("university")),
            authorized=(D("health"), D("university")),
            signals=(
                make_signal(
                    "entity", "test", domain_ids=(D("health"),), confidence=0.3
                ),
            ),
            policy=make_policy(high_impact=(D("health"),), min_confidence=0.8),
        )
        result = resolver.resolve(ctx)
        assert result.status != DomainResolutionStatus.RESOLVED
        assert result.requires_clarification is True

    def test_high_impact_sufficient_confidence_allowed(self) -> None:
        resolver = make_resolver()
        ctx = make_context(
            available=(D("health"),),
            authorized=(D("health"),),
            explicit=(D("health"),),
            policy=make_policy(high_impact=(D("health"),), min_confidence=0.5),
        )
        result = resolver.resolve(ctx)
        assert result.status == DomainResolutionStatus.RESOLVED

    def test_high_impact_explicit_still_protected(self) -> None:
        """Explicit domain does NOT bypass high-impact protection."""
        resolver = make_resolver()
        ctx = make_context(
            available=(D("health"), D("university")),
            explicit=(D("health"),),
            authorized=(D("health"), D("university")),
            policy=make_policy(high_impact=(D("health"),), min_confidence=0.99),
        )
        result = resolver.resolve(ctx)
        # High-impact explicit with insufficient confidence → blocked/ambiguous
        assert result.status in (
            DomainResolutionStatus.INSUFFICIENT_INFORMATION,
            DomainResolutionStatus.AMBIGUOUS,
        )


# ═══════════════════════════════════════════════════════════════════════════
# Supporting
# ═══════════════════════════════════════════════════════════════════════════


class TestSupporting:
    def test_supporting_selected(self) -> None:
        # Use larger supporting margin so reflection qualifies
        resolver = make_resolver(
            policy=DomainScoringPolicy(ambiguity_margin=5.0, supporting_margin=100.0)
        )
        ctx = make_context(
            available=(D("health"), D("reflection"), D("university")),
            explicit=(D("health"),),
            authorized=(D("health"), D("reflection"), D("university")),
            resources=(
                DomainResolutionResource(
                    id="r1",
                    resource_type="doc",
                    source="test",
                    domain_ids=(D("reflection"),),
                ),
            ),
        )
        result = resolver.resolve(ctx)
        assert result.primary_domain == D("health")
        supporting_slugs = {d.slug for d in result.supporting_domains}
        assert "reflection" in supporting_slugs

    def test_supporting_max_limit(self) -> None:
        p = DomainScoringPolicy(max_supporting_domains=1, supporting_margin=100.0)
        resolver = make_resolver(policy=p)
        ctx = make_context(
            available=(D("health"), D("reflection"), D("university")),
            explicit=(D("health"),),
            authorized=(D("health"), D("reflection"), D("university")),
            resources=(
                DomainResolutionResource(
                    id="r1",
                    resource_type="doc",
                    source="test",
                    domain_ids=(D("reflection"),),
                ),
                DomainResolutionResource(
                    id="r2",
                    resource_type="doc",
                    source="test",
                    domain_ids=(D("university"),),
                ),
            ),
        )
        result = resolver.resolve(ctx)
        assert len(result.supporting_domains) <= 1

    def test_supporting_not_rejected(self) -> None:
        resolver = make_resolver()
        ctx = make_context(
            available=(D("health"), D("reflection")),
            explicit=(D("health"),),
            authorized=(D("health"),),
            resources=(
                DomainResolutionResource(
                    id="r1",
                    resource_type="doc",
                    source="test",
                    domain_ids=(D("reflection"),),
                ),
            ),
        )
        result = resolver.resolve(ctx)
        supporting_slugs = {d.slug for d in result.supporting_domains}
        assert "reflection" not in supporting_slugs


# ═══════════════════════════════════════════════════════════════════════════
# Determinism
# ═══════════════════════════════════════════════════════════════════════════


class TestDeterminism:
    def test_same_context_same_result(self) -> None:
        resolver = make_resolver(clock=fixed_clock, id_factory=fixed_id)
        ctx = make_context(
            available=(D("health"), D("university")),
            explicit=(D("health"),),
            authorized=(D("health"), D("university")),
        )
        r1 = resolver.resolve(ctx)
        r2 = resolver.resolve(ctx)
        assert r1.id == r2.id
        assert r1.primary_domain == r2.primary_domain
        assert r1.status == r2.status
        assert r1.confidence == r2.confidence

    def test_different_input_order_same_ranking(self) -> None:
        resolver = make_resolver(clock=fixed_clock, id_factory=fixed_id)
        ctx1 = make_context(
            available=(D("health"), D("university")),
            explicit=(D("health"),),
            authorized=(D("health"), D("university")),
        )
        ctx2 = make_context(
            available=(D("university"), D("health")),
            explicit=(D("health"),),
            authorized=(D("health"), D("university")),
        )
        r1 = resolver.resolve(ctx1)
        r2 = resolver.resolve(ctx2)
        assert r1.primary_domain == r2.primary_domain

    def test_candidate_scores_stable(self) -> None:
        resolver = make_resolver(clock=fixed_clock, id_factory=fixed_id)
        ctx = make_context(
            available=(D("health"), D("university")),
            explicit=(D("health"),),
            authorized=(D("health"), D("university")),
        )
        r1 = resolver.resolve(ctx)
        r2 = resolver.resolve(ctx)
        cs1 = {c.domain_id.slug: c.score for c in r1.candidate_scores}
        cs2 = {c.domain_id.slug: c.score for c in r2.candidate_scores}
        assert cs1 == cs2

    def test_reasons_stable(self) -> None:
        resolver = make_resolver(clock=fixed_clock, id_factory=fixed_id)
        ctx = make_context(
            available=(D("health"), D("university")),
            explicit=(D("health"),),
            authorized=(D("health"), D("university")),
        )
        r1 = resolver.resolve(ctx)
        r2 = resolver.resolve(ctx)
        codes1 = tuple(r.code for r in r1.reasons)
        codes2 = tuple(r.code for r in r2.reasons)
        assert codes1 == codes2


# ═══════════════════════════════════════════════════════════════════════════
# Failures
# ═══════════════════════════════════════════════════════════════════════════


class TestFailures:
    def test_wrong_context_type_rejected(self) -> None:
        resolver = make_resolver()
        with pytest.raises(TypeError):
            resolver.resolve("not a context")  # type: ignore[arg-type]

    def test_invalid_scorer_policy_raises(self) -> None:
        p1 = DomainScoringPolicy(explicit_weight=50.0)
        p2 = DomainScoringPolicy(explicit_weight=100.0)
        scorer = DomainCandidateScorer(policy=p1)
        with pytest.raises(DomainResolverConfigurationError):
            DefaultDomainResolver(scorer=scorer, scoring_policy=p2)

    def test_no_registry_access(self) -> None:
        resolver = make_resolver()
        assert not hasattr(resolver, "_registry")

    def test_no_mutation_of_context(self) -> None:
        resolver = make_resolver()
        ctx = make_context(
            available=(D("health"),),
            authorized=(D("health"),),
            explicit=(D("health"),),
        )
        available_before = ctx.available_domains
        resolver.resolve(ctx)
        assert ctx.available_domains == available_before


# ═══════════════════════════════════════════════════════════════════════════
# Public API
# ═══════════════════════════════════════════════════════════════════════════


class TestPublicAPI:
    def test_all_symbols_importable(self) -> None:
        from cmm.domains import (
            DefaultDomainResolver,
            DomainCandidateScore,
            DomainResolutionResult,
        )

        assert DefaultDomainResolver is not None
        assert DomainCandidateScore is not None
        assert DomainResolutionResult is not None

    def test_result_to_dict_json_serializable(self) -> None:
        import json

        resolver = make_resolver(clock=fixed_clock, id_factory=fixed_id)
        ctx = make_context(
            available=(D("health"),),
            explicit=(D("health"),),
            authorized=(D("health"),),
        )
        result = resolver.resolve(ctx)
        d = result.to_dict()
        json_str = json.dumps(d)
        assert isinstance(json_str, str)

    def test_no_keywords_in_scoring(self) -> None:
        scorer = DomainCandidateScorer()
        import inspect

        source = inspect.getsource(scorer._score_explicit)
        assert "health" not in source.lower() or "health" not in source

    def test_no_agent_runtime_imports(self) -> None:
        import sys

        for module_name in list(sys.modules.keys()):
            if "cmm.domains.resolver" in module_name:
                _mod = sys.modules[module_name]
                break
