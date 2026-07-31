"""Phase 10.9 – Tests for cross-domain aggregation helpers."""

from __future__ import annotations

from cmm.domains.cross_domain_aggregation import (
    DOMAIN_STATUS_PRECEDENCE,
    derive_confidence,
    derive_cross_domain_status,
    merge_contradictions,
    merge_dependencies,
    merge_domain_results,
    merge_findings,
    merge_gaps,
    merge_questions,
    merge_recommendations,
    merge_two_findings,
)
from cmm.domains.cross_domain_contracts import (
    CrossDomainContradiction,
    CrossDomainDependency,
    CrossDomainDomainResult,
    CrossDomainFinding,
    CrossDomainGap,
    CrossDomainPolicy,
    CrossDomainQuestion,
)
from cmm.domains.enums import CrossDomainStatus


def _finding(
    identifier: str, source: str = "domain:health", **kw
) -> CrossDomainFinding:
    kwargs = {
        "identifier": identifier,
        "value": identifier,
        "source_domains": (source,),
        "provenance": ("p",),
    }
    kwargs.update(kw)
    return CrossDomainFinding(**kwargs)


class TestMergeFindings:
    def test_exact_dedupe_first_appearance(self) -> None:
        result = merge_findings(
            (_finding("a"), _finding("b")), (_finding("b"), _finding("c"))
        )
        assert [f.identifier for f in result] == ["a", "b", "c"]

    def test_merge_two_findings_unions_source_and_provenance(self) -> None:
        a = _finding("f1", source="domain:health", provenance=("p1",))
        b = _finding("f1", source="domain:general", provenance=("p2",))
        merged = merge_two_findings(a, b)
        assert {d.slug for d in merged.source_domains} == {"health", "general"}
        assert set(merged.provenance) == {"p1", "p2"}

    def test_merge_two_findings_most_restrictive_privacy(self) -> None:
        a = _finding("f1", private=False, transferable=True)
        b = _finding("f1", private=True, transferable=False)
        merged = merge_two_findings(a, b)
        assert merged.private is True
        assert merged.transferable is False

    def test_recommendations_same_semantics(self) -> None:
        result = merge_recommendations(("x",), ("x", "y"))
        assert result == ("x", "y")


class TestMergeDomainResults:
    def test_repeated_domain_results_are_merged_not_overwritten(self) -> None:
        r1 = CrossDomainDomainResult(
            domain_id="domain:health",
            status="completed",
            findings=(_finding("a"),),
            recommendations=("rec-a",),
        )
        r2 = CrossDomainDomainResult(
            domain_id="domain:health",
            status="blocked",
            findings=(_finding("b"),),
            recommendations=("rec-b",),
        )
        merged = merge_domain_results([r1, r2])
        assert len(merged) == 1
        # most restrictive status wins (BLOCKED), never "last write wins"
        assert merged[0].status == CrossDomainStatus.BLOCKED
        # findings/recommendations from BOTH attempts are preserved
        assert {f.identifier for f in merged[0].findings} == {"a", "b"}
        assert set(merged[0].recommendations) == {"rec-a", "rec-b"}

    def test_status_precedence_is_explicit_not_last_wins(self) -> None:
        # COMPLETED merged after FAILED must still yield FAILED (most
        # restrictive), even though FAILED came first in the precedence list
        # and COMPLETED was the *second* (i.e. "last") result.
        r1 = CrossDomainDomainResult(domain_id="domain:health", status="failed")
        r2 = CrossDomainDomainResult(domain_id="domain:health", status="completed")
        merged = merge_domain_results([r1, r2])
        assert merged[0].status == CrossDomainStatus.FAILED
        assert DOMAIN_STATUS_PRECEDENCE[0] == CrossDomainStatus.FAILED

    def test_preserves_execution_order(self) -> None:
        r1 = CrossDomainDomainResult(domain_id="domain:health", status="completed")
        r2 = CrossDomainDomainResult(domain_id="domain:general", status="completed")
        merged = merge_domain_results([r1, r2])
        assert [r.domain_id.slug for r in merged] == ["health", "general"]


class TestMergeQuestions:
    def test_duplicate_question_merges_provenance(self) -> None:
        q1 = CrossDomainQuestion(
            id="q1",
            subject="s",
            requested_information="ri",
            requesting_domains=("domain:health",),
            provenance=("first", "shared"),
        )
        q2 = CrossDomainQuestion(
            id="q2",
            subject="s",
            requested_information="ri",
            requesting_domains=("domain:general",),
            provenance=("shared", "second"),
        )
        merged = merge_questions([q1], [q2])
        assert len(merged) == 1
        assert merged[0].provenance == ("first", "shared", "second")
        assert {d.slug for d in merged[0].requesting_domains} == {"health", "general"}

    def test_distinct_questions_not_collapsed(self) -> None:
        q1 = CrossDomainQuestion(
            id="q1", subject="s1", requested_information="ri", provenance=("p",)
        )
        q2 = CrossDomainQuestion(
            id="q2", subject="s2", requested_information="ri", provenance=("p",)
        )
        merged = merge_questions([q1, q2])
        assert len(merged) == 2


class TestMergeDependencies:
    def test_duplicate_dependency_merges_provenance(self) -> None:
        first = CrossDomainDependency(
            source_domain="domain:health",
            target_domain="domain:general",
            kind="requires",
            description="d",
            provenance=("first", "shared"),
        )
        second = CrossDomainDependency(
            source_domain="domain:health",
            target_domain="domain:general",
            kind="requires",
            description="d",
            provenance=("shared", "second"),
        )
        merged = merge_dependencies([first], [second])
        assert len(merged) == 1
        assert merged[0].provenance == ("first", "shared", "second")
        assert merged[0].source_domain.slug == "health"
        assert merged[0].target_domain.slug == "general"

    def test_sort_order_by_source_target_kind_description(self) -> None:
        d1 = CrossDomainDependency(
            source_domain="domain:general",
            target_domain="domain:health",
            kind="a",
            description="d",
            provenance=("p",),
        )
        d2 = CrossDomainDependency(
            source_domain="domain:general",
            target_domain="domain:health",
            kind="b",
            description="d",
            provenance=("p",),
        )
        merged = merge_dependencies([d2, d1])
        assert [d.kind for d in merged] == ["a", "b"]


class TestMergeContradictions:
    def test_duplicate_contradiction_merges_provenance(self) -> None:
        first = CrossDomainContradiction(
            id="c1",
            domains=("domain:health", "domain:general"),
            subject="s",
            statements=("a",),
            severity="high",
            provenance=("first", "shared"),
        )
        second = CrossDomainContradiction(
            id="c1",
            domains=("domain:health", "domain:general"),
            subject="s",
            statements=("a",),
            severity="high",
            provenance=("shared", "second"),
        )
        merged = merge_contradictions([first], [second])
        assert len(merged) == 1
        assert merged[0].provenance == ("first", "shared", "second")
        assert [d.slug for d in merged[0].domains] == ["health", "general"]

    def test_distinct_contradictions_never_collapsed(self) -> None:
        c1 = CrossDomainContradiction(
            id="c1",
            domains=("domain:health", "domain:general"),
            subject="s",
            statements=("a",),
            severity="high",
            provenance=("p",),
        )
        c2 = CrossDomainContradiction(
            id="c2",
            domains=("domain:health", "domain:general"),
            subject="s",
            statements=("b",),
            severity="high",
            provenance=("p",),
        )
        merged = merge_contradictions([c1, c2])
        assert len(merged) == 2


class TestMergeGaps:
    def test_structural_dedupe(self) -> None:
        g = CrossDomainGap(code="g1", domain_id="domain:health", description="d")
        merged = merge_gaps([g], [g])
        assert len(merged) == 1

    def test_sort_blocking_first(self) -> None:
        g1 = CrossDomainGap(
            code="a", domain_id="domain:health", description="d", blocking=False
        )
        g2 = CrossDomainGap(
            code="b", domain_id="domain:health", description="d", blocking=True
        )
        merged = merge_gaps([g1, g2])
        assert merged[0].code == "b"


class TestDeriveConfidence:
    def test_none_when_no_evidence(self) -> None:
        assert (
            derive_confidence(
                [],
                CrossDomainPolicy(),
                unresolved_contradiction=False,
                unresolved_gap=False,
                skipped_required_domain=False,
                unavailable_required_port=False,
                limit_reached=False,
            )
            is None
        )

    def test_uses_minimum_of_contributing_confidences(self) -> None:
        results = [
            CrossDomainDomainResult(
                domain_id="domain:health",
                status="completed",
                recommendations=("r1",),
                confidence=0.9,
            ),
            CrossDomainDomainResult(
                domain_id="domain:general",
                status="completed",
                recommendations=("r2",),
                confidence=0.6,
            ),
        ]
        conf = derive_confidence(
            results,
            CrossDomainPolicy(),
            unresolved_contradiction=False,
            unresolved_gap=False,
            skipped_required_domain=False,
            unavailable_required_port=False,
            limit_reached=False,
        )
        assert conf == 0.6

    def test_ignores_results_without_recommendations(self) -> None:
        results = [
            CrossDomainDomainResult(
                domain_id="domain:health", status="completed", confidence=0.1
            ),
            CrossDomainDomainResult(
                domain_id="domain:general",
                status="completed",
                recommendations=("r",),
                confidence=0.8,
            ),
        ]
        conf = derive_confidence(
            results,
            CrossDomainPolicy(),
            unresolved_contradiction=False,
            unresolved_gap=False,
            skipped_required_domain=False,
            unavailable_required_port=False,
            limit_reached=False,
        )
        assert conf == 0.8

    def test_each_penalty_applied(self) -> None:
        results = [
            CrossDomainDomainResult(
                domain_id="domain:health",
                status="completed",
                recommendations=("r",),
                confidence=1.0,
            )
        ]
        policy = CrossDomainPolicy(
            contradiction_penalty=0.1,
            gap_penalty=0.1,
            skipped_required_domain_penalty=0.1,
            unavailable_required_port_penalty=0.1,
            limit_reached_penalty=0.1,
        )
        conf = derive_confidence(
            results,
            policy,
            unresolved_contradiction=True,
            unresolved_gap=True,
            skipped_required_domain=True,
            unavailable_required_port=True,
            limit_reached=True,
        )
        assert conf == 0.5

    def test_clamped_at_zero(self) -> None:
        results = [
            CrossDomainDomainResult(
                domain_id="domain:health",
                status="completed",
                recommendations=("r",),
                confidence=0.1,
            )
        ]
        policy = CrossDomainPolicy(contradiction_penalty=1.0)
        conf = derive_confidence(
            results,
            policy,
            unresolved_contradiction=True,
            unresolved_gap=False,
            skipped_required_domain=False,
            unavailable_required_port=False,
            limit_reached=False,
        )
        assert conf == 0.0

    def test_no_bonuses_applied(self) -> None:
        results = [
            CrossDomainDomainResult(
                domain_id="domain:health",
                status="completed",
                recommendations=("r",),
                confidence=0.5,
            )
        ]
        conf = derive_confidence(
            results,
            CrossDomainPolicy(),
            unresolved_contradiction=False,
            unresolved_gap=False,
            skipped_required_domain=False,
            unavailable_required_port=False,
            limit_reached=False,
        )
        assert conf == 0.5  # never exceeds the minimum contributing confidence


class TestDeriveStatus:
    def test_blocked_takes_priority(self) -> None:
        status = derive_cross_domain_status(
            is_blocked=True,
            limit_reached=True,
            requires_review=True,
            has_useful_output=True,
            all_domains_completed=True,
        )
        assert status == CrossDomainStatus.BLOCKED

    def test_limit_reached_next(self) -> None:
        status = derive_cross_domain_status(
            is_blocked=False,
            limit_reached=True,
            requires_review=True,
            has_useful_output=True,
            all_domains_completed=True,
        )
        assert status == CrossDomainStatus.LIMIT_REACHED

    def test_requires_review_next(self) -> None:
        status = derive_cross_domain_status(
            is_blocked=False,
            limit_reached=False,
            requires_review=True,
            has_useful_output=True,
            all_domains_completed=True,
        )
        assert status == CrossDomainStatus.REQUIRES_REVIEW

    def test_completed_when_all_done(self) -> None:
        status = derive_cross_domain_status(
            is_blocked=False,
            limit_reached=False,
            requires_review=False,
            has_useful_output=True,
            all_domains_completed=True,
        )
        assert status == CrossDomainStatus.COMPLETED

    def test_partial_when_incomplete(self) -> None:
        status = derive_cross_domain_status(
            is_blocked=False,
            limit_reached=False,
            requires_review=False,
            has_useful_output=True,
            all_domains_completed=False,
        )
        assert status == CrossDomainStatus.PARTIAL

    def test_failed_when_nothing_useful(self) -> None:
        status = derive_cross_domain_status(
            is_blocked=False,
            limit_reached=False,
            requires_review=False,
            has_useful_output=False,
            all_domains_completed=False,
        )
        assert status == CrossDomainStatus.FAILED
