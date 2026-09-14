"""Phase 10.9 – Tests for Cross-Domain Engine contracts (validation, invariants)."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from cmm.domains.cross_domain_contracts import (
    CrossDomainContextSnapshot,
    CrossDomainContextTransfer,
    CrossDomainContradiction,
    CrossDomainDecision,
    CrossDomainDependency,
    CrossDomainDomainResult,
    CrossDomainFinding,
    CrossDomainGap,
    CrossDomainKnowledgeResult,
    CrossDomainLimits,
    CrossDomainPlanResult,
    CrossDomainPolicy,
    CrossDomainQuestion,
    CrossDomainRequest,
    CrossDomainResult,
    CrossDomainWorkflowResult,
)
from cmm.domains.enums import CrossDomainSeverity, CrossDomainStage, CrossDomainStatus
from cmm.domains.errors import CrossDomainContractError

NOW = datetime(2026, 7, 31, tzinfo=timezone.utc)
LATER = datetime(2026, 7, 31, 0, 5, tzinfo=timezone.utc)


class TestCrossDomainRequest:
    def test_minimal_valid(self) -> None:
        req = CrossDomainRequest(
            id="r1", objective="obj", primary_domain="domain:health"
        )
        assert req.primary_domain.slug == "health"
        assert req.supporting_domains == ()

    def test_empty_id_rejected(self) -> None:
        with pytest.raises(CrossDomainContractError):
            CrossDomainRequest(id="", objective="obj", primary_domain="domain:health")

    def test_empty_objective_rejected(self) -> None:
        with pytest.raises(CrossDomainContractError):
            CrossDomainRequest(id="r1", objective="", primary_domain="domain:health")

    def test_primary_in_supporting_rejected(self) -> None:
        with pytest.raises(CrossDomainContractError):
            CrossDomainRequest(
                id="r1",
                objective="obj",
                primary_domain="domain:health",
                supporting_domains=("domain:health",),
            )

    def test_duplicate_supporting_rejected(self) -> None:
        with pytest.raises(CrossDomainContractError):
            CrossDomainRequest(
                id="r1",
                objective="obj",
                primary_domain="domain:health",
                supporting_domains=("domain:general", "domain:general"),
            )

    def test_total_domains_exceeds_maximum(self) -> None:
        with pytest.raises(CrossDomainContractError):
            CrossDomainRequest(
                id="r1",
                objective="obj",
                primary_domain="domain:health",
                supporting_domains=("domain:general",),
                maximum_domains=1,
            )

    @pytest.mark.parametrize(
        "field_name",
        [
            "maximum_domains",
            "maximum_domain_hops",
            "maximum_iterations",
            "maximum_questions",
            "maximum_operations",
            "maximum_external_calls",
            "maximum_duration_ms",
        ],
    )
    def test_limits_strictly_positive(self, field_name: str) -> None:
        with pytest.raises(CrossDomainContractError):
            CrossDomainRequest(
                id="r1",
                objective="obj",
                primary_domain="domain:health",
                **{field_name: 0},
            )

    def test_limit_bool_rejected_as_int(self) -> None:
        with pytest.raises(CrossDomainContractError):
            CrossDomainRequest(
                id="r1",
                objective="obj",
                primary_domain="domain:health",
                maximum_domains=True,
            )

    def test_maximum_cost_none_allowed(self) -> None:
        req = CrossDomainRequest(
            id="r1", objective="obj", primary_domain="domain:health"
        )
        assert req.maximum_cost is None

    def test_maximum_cost_negative_rejected(self) -> None:
        with pytest.raises(CrossDomainContractError):
            CrossDomainRequest(
                id="r1",
                objective="obj",
                primary_domain="domain:health",
                maximum_cost=-1.0,
            )

    def test_maximum_cost_nan_rejected(self) -> None:
        with pytest.raises(CrossDomainContractError):
            CrossDomainRequest(
                id="r1",
                objective="obj",
                primary_domain="domain:health",
                maximum_cost=float("nan"),
            )

    def test_resources_must_be_unique(self) -> None:
        with pytest.raises(CrossDomainContractError):
            CrossDomainRequest(
                id="r1",
                objective="obj",
                primary_domain="domain:health",
                resources=("r", "r"),
            )

    def test_metadata_credential_key_rejected(self) -> None:
        with pytest.raises(CrossDomainContractError):
            CrossDomainRequest(
                id="r1",
                objective="obj",
                primary_domain="domain:health",
                metadata={"api_key": "secret"},
            )

    def test_unknown_field_rejected_from_dict(self) -> None:
        req = CrossDomainRequest(
            id="r1", objective="obj", primary_domain="domain:health"
        )
        data = req.to_dict()
        data["bogus"] = True
        from cmm.domains.errors import CrossDomainSerializationError

        with pytest.raises(CrossDomainSerializationError):
            CrossDomainRequest.from_dict(data)


class TestCrossDomainPolicy:
    def test_defaults_valid(self) -> None:
        pol = CrossDomainPolicy()
        assert pol.maximum_parallel_group_size == 4

    def test_penalty_out_of_range_rejected(self) -> None:
        with pytest.raises(CrossDomainContractError):
            CrossDomainPolicy(contradiction_penalty=1.5)

    def test_bool_rejected_for_stop_flags(self) -> None:
        with pytest.raises(CrossDomainContractError):
            CrossDomainPolicy(stop_on_blocking_contradiction=1)

    def test_group_size_must_be_positive(self) -> None:
        with pytest.raises(CrossDomainContractError):
            CrossDomainPolicy(maximum_parallel_group_size=0)


class TestCrossDomainQuestion:
    def test_structural_identity_key(self) -> None:
        q = CrossDomainQuestion(
            id="q1", subject="s", requested_information="ri", provenance=("p",)
        )
        assert q.identity_key() == ("s", "ri", None, None)

    def test_answered_requires_answer(self) -> None:
        with pytest.raises(CrossDomainContractError):
            CrossDomainQuestion(
                id="q1",
                subject="s",
                requested_information="ri",
                answered=True,
                provenance=("p",),
            )

    def test_answer_forbidden_when_not_answered(self) -> None:
        with pytest.raises(CrossDomainContractError):
            CrossDomainQuestion(
                id="q1",
                subject="s",
                requested_information="ri",
                answered=False,
                answer="a",
                provenance=("p",),
            )

    def test_provenance_required(self) -> None:
        with pytest.raises(CrossDomainContractError):
            CrossDomainQuestion(
                id="q1", subject="s", requested_information="ri", provenance=()
            )


class TestCrossDomainContextTransfer:
    def test_source_target_must_differ(self) -> None:
        with pytest.raises(CrossDomainContractError):
            CrossDomainContextTransfer(
                source_domain="domain:health",
                target_domain="domain:health",
                kind="entity",
                identifier="e1",
                value=1,
                reason="r",
                provenance=("p",),
            )

    def test_negative_iteration_rejected(self) -> None:
        with pytest.raises(CrossDomainContractError):
            CrossDomainContextTransfer(
                source_domain="domain:health",
                target_domain="domain:general",
                kind="entity",
                identifier="e1",
                value=1,
                reason="r",
                provenance=("p",),
                iteration=-1,
            )

    def test_provenance_required(self) -> None:
        with pytest.raises(CrossDomainContractError):
            CrossDomainContextTransfer(
                source_domain="domain:health",
                target_domain="domain:general",
                kind="entity",
                identifier="e1",
                value=1,
                reason="r",
                provenance=(),
            )

    def test_value_must_be_json_safe(self) -> None:
        with pytest.raises(CrossDomainContractError):
            CrossDomainContextTransfer(
                source_domain="domain:health",
                target_domain="domain:general",
                kind="entity",
                identifier="e1",
                value=object(),
                reason="r",
                provenance=("p",),
            )


class TestCrossDomainDependency:
    def test_source_target_must_differ(self) -> None:
        with pytest.raises(CrossDomainContractError):
            CrossDomainDependency(
                source_domain="domain:health",
                target_domain="domain:health",
                kind="requires",
                description="d",
                provenance=("p",),
            )

    def test_identity_key_structural(self) -> None:
        dep = CrossDomainDependency(
            source_domain="domain:health",
            target_domain="domain:general",
            kind="requires",
            description="d",
            blocking=True,
            provenance=("p",),
        )
        assert dep.identity_key() == ("health", "general", "requires", "d", True)


class TestCrossDomainContradiction:
    def test_requires_two_domains(self) -> None:
        with pytest.raises(CrossDomainContractError):
            CrossDomainContradiction(
                id="c1",
                domains=("domain:health",),
                subject="s",
                statements=("a",),
                severity="high",
                provenance=("p",),
            )

    def test_statements_non_empty(self) -> None:
        with pytest.raises(CrossDomainContractError):
            CrossDomainContradiction(
                id="c1",
                domains=("domain:health", "domain:general"),
                subject="s",
                statements=(),
                severity="high",
                provenance=("p",),
            )

    def test_unresolved_cannot_have_resolution(self) -> None:
        with pytest.raises(CrossDomainContractError):
            CrossDomainContradiction(
                id="c1",
                domains=("domain:health", "domain:general"),
                subject="s",
                statements=("a", "b"),
                severity="high",
                resolved=False,
                resolution="fixed",
                provenance=("p",),
            )

    def test_resolved_with_resolution_ok(self) -> None:
        c = CrossDomainContradiction(
            id="c1",
            domains=("domain:health", "domain:general"),
            subject="s",
            statements=("a", "b"),
            severity=CrossDomainSeverity.HIGH,
            resolved=True,
            resolution="fixed",
            provenance=("p",),
        )
        assert c.resolution == "fixed"

    def test_invalid_severity_rejected(self) -> None:
        with pytest.raises(CrossDomainContractError):
            CrossDomainContradiction(
                id="c1",
                domains=("domain:health", "domain:general"),
                subject="s",
                statements=("a",),
                severity="extreme",
                provenance=("p",),
            )


class TestCrossDomainGap:
    def test_minimal_valid(self) -> None:
        gap = CrossDomainGap(code="g1", domain_id="domain:health", description="d")
        assert gap.recoverable is True
        assert gap.blocking is False


class TestCrossDomainDecision:
    def test_minimal_valid(self) -> None:
        d = CrossDomainDecision(
            code="DOMAIN_SELECTED",
            stage=CrossDomainStage.DOMAIN_EXECUTION,
            domain_id="domain:health",
            action="select",
        )
        assert d.iteration == 0

    def test_invalid_stage_rejected(self) -> None:
        with pytest.raises(CrossDomainContractError):
            CrossDomainDecision(
                code="X", stage="not-a-stage", domain_id=None, action="a"
            )


class TestCrossDomainDomainResult:
    def test_rejects_non_terminal_status(self) -> None:
        with pytest.raises(CrossDomainContractError):
            CrossDomainDomainResult(domain_id="domain:health", status="pending")

    def test_confidence_out_of_range_rejected(self) -> None:
        with pytest.raises(CrossDomainContractError):
            CrossDomainDomainResult(
                domain_id="domain:health", status="completed", confidence=1.5
            )

    def test_partial_findings_valid_when_blocked(self) -> None:
        finding = CrossDomainFinding(
            identifier="f1",
            value="partial finding",
            source_domains=("domain:health",),
            provenance=("p",),
        )
        r = CrossDomainDomainResult(
            domain_id="domain:health",
            status="blocked",
            findings=(finding,),
        )
        assert r.status == CrossDomainStatus.BLOCKED
        assert r.findings == (finding,)


class TestCrossDomainPlanResult:
    def test_parallel_group_must_reference_known_domain(self) -> None:
        with pytest.raises(CrossDomainContractError):
            CrossDomainPlanResult(
                status="completed",
                domain_order=("domain:health",),
                parallel_groups=(("domain:general",),),
            )

    def test_parallel_group_duplicate_rejected(self) -> None:
        with pytest.raises(CrossDomainContractError):
            CrossDomainPlanResult(
                status="completed",
                domain_order=("domain:health",),
                parallel_groups=(("domain:health", "domain:health"),),
            )

    def test_rejects_non_terminal_status(self) -> None:
        with pytest.raises(CrossDomainContractError):
            CrossDomainPlanResult(status="running")


class TestCrossDomainWorkflowResult:
    def test_negative_external_calls_rejected(self) -> None:
        with pytest.raises(CrossDomainContractError):
            CrossDomainWorkflowResult(status="completed", external_calls_used=-1)


class TestCrossDomainKnowledgeResult:
    def test_estimated_cost_must_be_finite(self) -> None:
        with pytest.raises(CrossDomainContractError):
            CrossDomainKnowledgeResult(status="completed", estimated_cost=float("inf"))


class TestCrossDomainLimits:
    def test_negative_counter_rejected(self) -> None:
        with pytest.raises(CrossDomainContractError):
            CrossDomainLimits(domains_used=-1)

    def test_reached_limits_deterministic_order(self) -> None:
        limits = CrossDomainLimits(reached_limits=("duration", "domains", "cost"))
        assert limits.reached_limits == ("domains", "cost", "duration")

    def test_reached_limits_duplicates_rejected(self) -> None:
        with pytest.raises(CrossDomainContractError):
            CrossDomainLimits(reached_limits=("domains", "domains"))

    def test_bool_rejected_for_counter(self) -> None:
        with pytest.raises(CrossDomainContractError):
            CrossDomainLimits(domains_used=True)


class TestCrossDomainContextSnapshot:
    def test_naive_datetime_rejected(self) -> None:
        with pytest.raises(CrossDomainContractError):
            CrossDomainContextSnapshot(
                request_id="r1",
                composition_id=None,
                started_at=datetime.fromisoformat("2026-01-01T00:00:00"),
            )

    def test_active_domains_must_be_unique(self) -> None:
        with pytest.raises(CrossDomainContractError):
            CrossDomainContextSnapshot(
                request_id="r1",
                composition_id=None,
                active_domains=("domain:health", "domain:health"),
                started_at=NOW,
            )

    def test_immutable_defaults(self) -> None:
        snap = CrossDomainContextSnapshot(
            request_id="r1", composition_id=None, started_at=NOW
        )
        assert snap.active_domains == ()
        assert snap.decisions == ()


class TestCrossDomainResultInvariants:
    def _base_kwargs(self) -> dict:
        return {
            "id": "res1",
            "objective": "obj",
            "request_id": "r1",
            "composition_id": "comp1",
            "trace_id": "t1",
            "started_at": NOW,
            "completed_at": LATER,
        }

    def test_rejects_pending_status(self) -> None:
        with pytest.raises(CrossDomainContractError):
            CrossDomainResult(status="pending", **self._base_kwargs())

    def test_rejects_running_status(self) -> None:
        with pytest.raises(CrossDomainContractError):
            CrossDomainResult(status="running", **self._base_kwargs())

    def test_completed_at_before_started_at_rejected(self) -> None:
        kwargs = self._base_kwargs()
        kwargs["started_at"], kwargs["completed_at"] = LATER, NOW
        with pytest.raises(CrossDomainContractError):
            CrossDomainResult(status="failed", **kwargs)

    def test_failed_allows_empty_result(self) -> None:
        r = CrossDomainResult(status="failed", **self._base_kwargs())
        assert r.status == CrossDomainStatus.FAILED

    def test_completed_requires_useful_output(self) -> None:
        with pytest.raises(CrossDomainContractError):
            CrossDomainResult(status="completed", **self._base_kwargs())

    def test_completed_with_findings_ok(self) -> None:
        finding = CrossDomainFinding(
            identifier="f1",
            value="v",
            source_domains=("domain:health",),
            provenance=("p",),
        )
        r = CrossDomainResult(
            status="completed", shared_findings=(finding,), **self._base_kwargs()
        )
        assert r.shared_findings == (finding,)

    def test_blocked_requires_blocking_condition(self) -> None:
        with pytest.raises(CrossDomainContractError):
            CrossDomainResult(status="blocked", **self._base_kwargs())

    def test_blocked_with_blocking_gap_ok(self) -> None:
        gap = CrossDomainGap(
            code="g1", domain_id="domain:health", description="d", blocking=True
        )
        r = CrossDomainResult(
            status="blocked", cross_domain_gaps=(gap,), **self._base_kwargs()
        )
        assert r.status == CrossDomainStatus.BLOCKED

    def test_limit_reached_requires_reached_limit(self) -> None:
        with pytest.raises(CrossDomainContractError):
            CrossDomainResult(status="limit_reached", **self._base_kwargs())

    def test_limit_reached_with_reached_limits_ok(self) -> None:
        r = CrossDomainResult(
            status="limit_reached",
            limits=CrossDomainLimits(reached_limits=("questions",)),
            **self._base_kwargs(),
        )
        assert "questions" in r.limits.reached_limits

    def test_requires_review_requires_condition(self) -> None:
        with pytest.raises(CrossDomainContractError):
            CrossDomainResult(status="requires_review", **self._base_kwargs())

    def test_requires_review_with_unresolved_contradiction_ok(self) -> None:
        c = CrossDomainContradiction(
            id="c1",
            domains=("domain:health", "domain:general"),
            subject="s",
            statements=("a", "b"),
            severity="high",
            requires_review=True,
            provenance=("p",),
        )
        r = CrossDomainResult(
            status="requires_review", contradictions=(c,), **self._base_kwargs()
        )
        assert r.status == CrossDomainStatus.REQUIRES_REVIEW

    def test_partial_requires_useful_output(self) -> None:
        with pytest.raises(CrossDomainContractError):
            CrossDomainResult(status="partial", **self._base_kwargs())

    def test_confidence_out_of_range_rejected(self) -> None:
        with pytest.raises(CrossDomainContractError):
            CrossDomainResult(status="failed", confidence=2.0, **self._base_kwargs())
