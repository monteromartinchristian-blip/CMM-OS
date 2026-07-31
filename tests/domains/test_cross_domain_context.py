"""Phase 10.9 – Tests for CrossDomainContextBuilder."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from cmm.domains.cross_domain_context import CrossDomainContextBuilder
from cmm.domains.cross_domain_contracts import (
    CrossDomainContextTransfer,
    CrossDomainDecision,
    CrossDomainDependency,
    CrossDomainDomainResult,
    CrossDomainFinding,
    CrossDomainGap,
    CrossDomainQuestion,
)
from cmm.domains.enums import CrossDomainStage
from cmm.domains.errors import CrossDomainConfigurationError

NOW = datetime(2026, 7, 31, tzinfo=timezone.utc)


def _builder() -> CrossDomainContextBuilder:
    return CrossDomainContextBuilder(
        request_id="r1", composition_id="c1", clock=lambda: NOW
    )


def _finding(identifier: str, source: str = "domain:health") -> CrossDomainFinding:
    return CrossDomainFinding(
        identifier=identifier,
        value=identifier,
        source_domains=(source,),
        provenance=("p",),
    )


class TestConstruction:
    def test_requires_aware_clock(self) -> None:
        with pytest.raises(CrossDomainConfigurationError):
            CrossDomainContextBuilder(
                request_id="r1",
                composition_id=None,
                clock=lambda: datetime.fromisoformat("2026-01-01T00:00:00"),
            )

    def test_requires_nonempty_request_id(self) -> None:
        with pytest.raises(CrossDomainConfigurationError):
            CrossDomainContextBuilder(
                request_id="", composition_id=None, clock=lambda: NOW
            )


class TestSnapshotImmutability:
    def test_snapshot_reflects_no_state_by_default(self) -> None:
        b = _builder()
        snap = b.snapshot()
        assert snap.active_domains == ()
        assert snap.partial_results == ()

    def test_mutation_after_snapshot_does_not_leak(self) -> None:
        b = _builder()
        snap1 = b.snapshot()
        b.set_active_domains(("domain:health",))
        snap2 = b.snapshot()
        assert snap1.active_domains == ()
        assert snap2.active_domains == ("domain:health",)


class TestMergeDomainResult:
    def test_findings_entities_timelines_merge(self) -> None:
        b = _builder()
        r = CrossDomainDomainResult(
            domain_id="domain:health",
            status="completed",
            findings=(_finding("f1"), _finding("f2")),
            entities=("e1",),
            timelines=("t1",),
        )
        b.merge_domain_result(r)
        snap = b.snapshot()
        assert [f.identifier for f in snap.shared_findings] == ["f1", "f2"]
        assert snap.shared_entities == ("e1",)
        assert snap.shared_timelines == ("t1",)

    def test_exact_dedupe_across_domains(self) -> None:
        b = _builder()
        r1 = CrossDomainDomainResult(
            domain_id="domain:health",
            status="completed",
            findings=(_finding("shared", source="domain:health"),),
        )
        r2 = CrossDomainDomainResult(
            domain_id="domain:general",
            status="completed",
            findings=(
                _finding("shared", source="domain:general"),
                _finding("unique", source="domain:general"),
            ),
        )
        b.merge_domain_result(r1)
        b.merge_domain_result(r2)
        snap = b.snapshot()
        assert [f.identifier for f in snap.shared_findings] == ["shared", "unique"]
        merged_shared = snap.shared_findings[0]
        assert {d.slug for d in merged_shared.source_domains} == {"health", "general"}

    def test_partial_result_always_retained(self) -> None:
        b = _builder()
        r = CrossDomainDomainResult(domain_id="domain:health", status="blocked")
        b.merge_domain_result(r)
        assert b.snapshot().partial_results == (r,)

    def test_question_structural_dedupe_merges_requesting_domains(self) -> None:
        b = _builder()
        q1 = CrossDomainQuestion(
            id="q1",
            subject="s",
            requested_information="ri",
            requesting_domains=("domain:health",),
            provenance=("p",),
        )
        q2 = CrossDomainQuestion(
            id="q2",
            subject="s",
            requested_information="ri",
            requesting_domains=("domain:general",),
            provenance=("p2",),
        )
        b.merge_domain_result(
            CrossDomainDomainResult(
                domain_id="domain:health", status="completed", questions=(q1,)
            )
        )
        b.merge_domain_result(
            CrossDomainDomainResult(
                domain_id="domain:general", status="completed", questions=(q2,)
            )
        )
        snap = b.snapshot()
        assert len(snap.open_questions) == 1
        merged = snap.open_questions[0]
        assert {d.slug for d in merged.requesting_domains} == {"health", "general"}
        assert set(merged.provenance) == {
            "p",
            "p2",
        }  # provenance is unioned, not dropped

    def test_answered_question_moves_to_answered_list(self) -> None:
        b = _builder()
        q = CrossDomainQuestion(
            id="q1",
            subject="s",
            requested_information="ri",
            answered=True,
            answer="a",
            provenance=("p",),
        )
        b.merge_domain_result(
            CrossDomainDomainResult(
                domain_id="domain:health", status="completed", questions=(q,)
            )
        )
        snap = b.snapshot()
        assert snap.open_questions == ()
        assert len(snap.answered_questions) == 1

    def test_dependencies_contradictions_gaps_structurally_deduped(self) -> None:
        b = _builder()
        dep = CrossDomainDependency(
            source_domain="domain:health",
            target_domain="domain:general",
            kind="requires",
            description="d",
            provenance=("p",),
        )
        gap = CrossDomainGap(code="g1", domain_id="domain:health", description="d")
        r1 = CrossDomainDomainResult(
            domain_id="domain:health",
            status="completed",
            dependencies=(dep,),
            gaps=(gap,),
        )
        r2 = CrossDomainDomainResult(
            domain_id="domain:general",
            status="completed",
            dependencies=(dep,),
            gaps=(gap,),
        )
        b.merge_domain_result(r1)
        b.merge_domain_result(r2)
        snap = b.snapshot()
        assert len(snap.dependencies) == 1
        assert len(snap.gaps) == 1


class TestTransfers:
    def test_transfer_rejected_when_target_inactive(self) -> None:
        b = _builder()
        b.set_active_domains(("domain:health",))
        t = CrossDomainContextTransfer(
            source_domain="domain:health",
            target_domain="domain:general",
            kind="entity",
            identifier="e1",
            value=1,
            reason="r",
            provenance=("p",),
        )
        assert b.add_transfer(t) is False
        assert b.snapshot().transfers == ()

    def test_transfer_accepted_when_target_active(self) -> None:
        b = _builder()
        b.set_active_domains(("domain:health", "domain:general"))
        t = CrossDomainContextTransfer(
            source_domain="domain:health",
            target_domain="domain:general",
            kind="entity",
            identifier="e1",
            value=1,
            reason="r",
            provenance=("p",),
        )
        assert b.add_transfer(t) is True
        snap = b.snapshot()
        assert snap.transfers == (t,)
        assert snap.domain_hops == 1

    def test_private_transfer_blocked(self) -> None:
        b = _builder()
        b.set_active_domains(("domain:health", "domain:general"))
        t = CrossDomainContextTransfer(
            source_domain="domain:health",
            target_domain="domain:general",
            kind="entity",
            identifier="e1",
            value=1,
            reason="r",
            provenance=("p",),
            private=True,
        )
        assert b.add_transfer(t) is False

    def test_non_transferable_blocked(self) -> None:
        b = _builder()
        b.set_active_domains(("domain:health", "domain:general"))
        t = CrossDomainContextTransfer(
            source_domain="domain:health",
            target_domain="domain:general",
            kind="entity",
            identifier="e1",
            value=1,
            reason="r",
            provenance=("p",),
            transferable=False,
        )
        assert b.add_transfer(t) is False


class TestDecisionsAndVisits:
    def test_add_decision_recorded(self) -> None:
        b = _builder()
        d = CrossDomainDecision(
            code="DOMAIN_SELECTED",
            stage=CrossDomainStage.DOMAIN_EXECUTION,
            domain_id="domain:health",
            action="select",
        )
        b.add_decision(d)
        assert b.snapshot().decisions == (d,)

    def test_mark_visited_dedupes(self) -> None:
        from cmm.domains.identifiers import DomainId

        b = _builder()
        b.mark_visited(DomainId(slug="health"))
        b.mark_visited(DomainId(slug="health"))
        assert b.snapshot().visited_domains == (DomainId(slug="health"),)

    def test_advance_iteration(self) -> None:
        b = _builder()
        assert b.iteration == 0
        b.advance_iteration()
        assert b.iteration == 1
        assert b.snapshot().iteration == 1

    def test_consumption_tracking(self) -> None:
        b = _builder()
        b.consume_operations(2)
        b.consume_external_calls(3)
        b.add_cost(1.5)
        snap = b.snapshot()
        assert snap.consumed_operations == 2
        assert snap.consumed_external_calls == 3
        assert snap.estimated_cost == 1.5
