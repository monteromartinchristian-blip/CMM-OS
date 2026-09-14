"""Phase 10.9 – Tests for DefaultCrossDomainEngine."""

from __future__ import annotations

import itertools
from datetime import datetime, timezone

import pytest

from cmm.domains.composition_contracts import (
    DomainComposition,
    DomainCompositionItem,
    PermissionComposition,
)
from cmm.domains.cross_domain_contracts import (
    CrossDomainContradiction,
    CrossDomainDependency,
    CrossDomainDomainResult,
    CrossDomainFinding,
    CrossDomainGap,
    CrossDomainKnowledgeResult,
    CrossDomainOperationResult,
    CrossDomainPlanResult,
    CrossDomainPolicy,
    CrossDomainQuestion,
    CrossDomainRequest,
    CrossDomainWorkflowResult,
)
from cmm.domains.cross_domain_engine import DefaultCrossDomainEngine
from cmm.domains.enums import (
    CrossDomainStatus,
    DomainCompositionStatus,
    DomainResolutionStatus,
)
from cmm.domains.errors import (
    CrossDomainConfigurationError,
    CrossDomainContractError,
    CrossDomainPortError,
)
from cmm.domains.resolver_contracts import DomainResolutionResult

NOW = datetime(2026, 7, 31, tzinfo=timezone.utc)


def _clock():
    return NOW


def _id_factory():
    counter = itertools.count(1)

    def _next() -> str:
        return f"id-{next(counter)}"

    return _next


def _finding(identifier: str, source_slug: str) -> CrossDomainFinding:
    return CrossDomainFinding(
        identifier=identifier,
        value=identifier,
        source_domains=(f"domain:{source_slug}",),
        provenance=(f"{source_slug}-provenance",),
    )


# ── Fake ports ───────────────────────────────────────────────────────────────


class FakeResolver:
    def __init__(self, result: DomainResolutionResult) -> None:
        self._result = result

    def resolve(self, request):
        return self._result


class FakeComposer:
    def __init__(self, result: DomainComposition) -> None:
        self._result = result

    def compose(self, resolution):
        return self._result


class FakeCognitive:
    def __init__(self, fn=None) -> None:
        self._fn = fn or (
            lambda *, domain_id, objective, context: CrossDomainDomainResult(
                domain_id=domain_id,
                status="completed",
                findings=(_finding(f"{domain_id.slug}-finding", domain_id.slug),),
                recommendations=(f"{domain_id.slug}-rec",),
                confidence=0.8,
            )
        )
        self.calls: list = []

    def reason(self, *, domain_id, objective, context):
        self.calls.append(domain_id)
        return self._fn(domain_id=domain_id, objective=objective, context=context)


class FakeAgent:
    def __init__(self, fn=None) -> None:
        self._fn = fn or (
            lambda *, domain_id, plan, context: CrossDomainDomainResult(
                domain_id=domain_id,
                status="completed",
                findings=(_finding(f"{domain_id.slug}-agent-finding", domain_id.slug),),
                recommendations=(f"{domain_id.slug}-agent-rec",),
                confidence=0.75,
            )
        )
        self.calls: list = []

    def coordinate(self, *, domain_id, plan, context):
        self.calls.append(domain_id)
        return self._fn(domain_id=domain_id, plan=plan, context=context)


class FakePlanner:
    def __init__(self, result_fn) -> None:
        self._result_fn = result_fn
        self.calls = 0

    def plan(self, *, composition, context):
        self.calls += 1
        return self._result_fn(composition, context)


class FakeWorkflowPort:
    def __init__(self, result: CrossDomainWorkflowResult) -> None:
        self._result = result
        self.calls: list = []

    def coordinate(self, *, workflow_ids, context):
        self.calls.append(workflow_ids)
        return self._result


class FakeOperationPort:
    def __init__(self, result: CrossDomainOperationResult) -> None:
        self._result = result
        self.calls: list = []

    def coordinate_operations(self, *, operation_ids, requesting_domains, context):
        self.calls.append((operation_ids, dict(requesting_domains)))
        return self._result


class FakeKnowledgePort:
    def __init__(self, result: CrossDomainKnowledgeResult) -> None:
        self._result = result
        self.calls = 0

    def retrieve(self, *, domains, entities, timelines, context):
        self.calls += 1
        return self._result


class ExplodingPort:
    def resolve(self, request):
        raise RuntimeError("boom")


# ── Builders ─────────────────────────────────────────────────────────────────


def _resolution(
    *,
    status=DomainResolutionStatus.RESOLVED,
    primary="domain:health",
    supporting=(),
    **kw,
) -> DomainResolutionResult:
    return DomainResolutionResult(
        id="res-1",
        context_id="ctx-1",
        status=status,
        primary_domain=primary,
        supporting_domains=supporting,
        resolved_at=NOW,
        **kw,
    )


def _composition(
    *,
    status=DomainCompositionStatus.COMPOSED,
    primary="domain:health",
    supporting=(),
    **kw,
) -> DomainComposition:
    return DomainComposition(
        id="comp-1",
        resolution_id="res-1",
        status=status,
        primary_domain=primary,
        supporting_domains=supporting,
        composed_at=NOW,
        **kw,
    )


def _engine(**kwargs) -> DefaultCrossDomainEngine:
    defaults = {
        "clock": _clock,
        "id_factory": _id_factory(),
        "trace_id_factory": _id_factory(),
    }
    defaults.update(kwargs)
    return DefaultCrossDomainEngine(**defaults)


def _request(**kw) -> CrossDomainRequest:
    base = {"id": "r1", "objective": "obj", "primary_domain": "domain:health"}
    base.update(kw)
    return CrossDomainRequest(**base)


# ── Tests ────────────────────────────────────────────────────────────────────


class TestValidFlows:
    def test_primary_only_completed(self) -> None:
        engine = _engine(
            resolver=FakeResolver(_resolution()),
            composer=FakeComposer(_composition()),
            cognitive=FakeCognitive(),
        )
        result = engine.execute(_request())
        assert result.status == CrossDomainStatus.COMPLETED
        assert len(result.domain_results) == 1

    def test_multiple_domains_completed(self) -> None:
        engine = _engine(
            resolver=FakeResolver(_resolution(supporting=("domain:general",))),
            composer=FakeComposer(_composition(supporting=("domain:general",))),
            cognitive=FakeCognitive(),
        )
        result = engine.execute(_request(supporting_domains=("domain:general",)))
        assert result.status == CrossDomainStatus.COMPLETED
        assert {r.domain_id.slug for r in result.domain_results} == {
            "health",
            "general",
        }

    def test_agent_flow(self) -> None:
        agent = FakeAgent()
        engine = _engine(
            resolver=FakeResolver(_resolution()),
            composer=FakeComposer(_composition()),
            agent=agent,
        )
        result = engine.execute(_request())
        assert result.status == CrossDomainStatus.COMPLETED
        assert len(agent.calls) == 1

    def test_deterministic_repeat(self) -> None:
        engine = _engine(
            resolver=FakeResolver(_resolution(supporting=("domain:general",))),
            composer=FakeComposer(_composition(supporting=("domain:general",))),
            cognitive=FakeCognitive(),
        )
        req = _request(supporting_domains=("domain:general",))
        r1 = engine.execute(req)
        r2 = engine.execute(req)
        # domain-independent fields are identical across runs (ids/trace ids
        # differ because the factories are stateful counters).
        assert r1.status == r2.status
        assert r1.domain_results == r2.domain_results
        assert r1.decisions == r2.decisions

    def test_request_not_mutated(self) -> None:
        req = _request(supporting_domains=("domain:general",))
        snapshot_before = req.to_dict()
        engine = _engine(
            resolver=FakeResolver(_resolution(supporting=("domain:general",))),
            composer=FakeComposer(_composition(supporting=("domain:general",))),
            cognitive=FakeCognitive(),
        )
        engine.execute(req)
        assert req.to_dict() == snapshot_before


class TestResolutionOutcomes:
    def test_ambiguous_requires_review(self) -> None:
        resolution = _resolution(
            status=DomainResolutionStatus.AMBIGUOUS,
            primary=None,
            ambiguous_domains=("domain:health", "domain:general"),
            requires_clarification=True,
            recommended_question="which?",
        )
        engine = _engine(
            resolver=FakeResolver(resolution), composer=FakeComposer(_composition())
        )
        result = engine.execute(_request())
        assert result.status == CrossDomainStatus.REQUIRES_REVIEW

    def test_insufficient_information_without_primary_requires_review(self) -> None:
        resolution = _resolution(
            status=DomainResolutionStatus.INSUFFICIENT_INFORMATION,
            primary=None,
            requires_clarification=True,
        )
        engine = _engine(
            resolver=FakeResolver(resolution), composer=FakeComposer(_composition())
        )
        result = engine.execute(_request())
        assert result.status == CrossDomainStatus.REQUIRES_REVIEW

    def test_insufficient_information_with_clarification_requires_review(self) -> None:
        """requires_clarification=True must win even when a primary + fallback exist."""
        resolution = _resolution(
            status=DomainResolutionStatus.INSUFFICIENT_INFORMATION,
            primary="domain:health",
            fallback_used=True,
            requires_clarification=True,
        )
        engine = _engine(
            resolver=FakeResolver(resolution),
            composer=FakeComposer(_composition()),
            cognitive=FakeCognitive(),
        )
        result = engine.execute(_request())
        assert result.status == CrossDomainStatus.REQUIRES_REVIEW
        assert any(d.code == "HUMAN_REVIEW_REQUESTED" for d in result.decisions)
        # execution must not have proceeded to domain reasoning
        assert result.domain_results == ()

    def test_insufficient_information_without_declared_fallback_requires_review(
        self,
    ) -> None:
        """A primary domain alone (without an explicit fallback declaration) must
        not be treated as a safe, non-blocking continuation. The underlying
        DomainResolutionResult contract itself forces requires_clarification=True
        whenever a non-fallback primary is present under INSUFFICIENT_INFORMATION,
        so this exercises that combination end to end through the engine."""
        resolution = _resolution(
            status=DomainResolutionStatus.INSUFFICIENT_INFORMATION,
            primary="domain:health",
            fallback_used=False,
            requires_clarification=True,
        )
        engine = _engine(
            resolver=FakeResolver(resolution),
            composer=FakeComposer(_composition()),
            cognitive=FakeCognitive(),
        )
        result = engine.execute(_request())
        assert result.status == CrossDomainStatus.REQUIRES_REVIEW

    def test_insufficient_information_with_fallback_primary_continues(self) -> None:
        resolution = _resolution(
            status=DomainResolutionStatus.INSUFFICIENT_INFORMATION,
            primary="domain:health",
            fallback_used=True,
        )
        engine = _engine(
            resolver=FakeResolver(resolution),
            composer=FakeComposer(_composition()),
            cognitive=FakeCognitive(),
        )
        result = engine.execute(_request())
        assert result.status == CrossDomainStatus.COMPLETED

    def test_unsupported_is_blocked(self) -> None:
        resolution = _resolution(
            status=DomainResolutionStatus.UNSUPPORTED, primary=None, confidence=0.0
        )
        engine = _engine(
            resolver=FakeResolver(resolution), composer=FakeComposer(_composition())
        )
        result = engine.execute(_request())
        assert result.status == CrossDomainStatus.BLOCKED

    def test_resolution_blocked_is_blocked(self) -> None:
        from cmm.domains.resolver_contracts import DomainResolutionReason

        resolution = _resolution(
            status=DomainResolutionStatus.BLOCKED,
            primary=None,
            rejected_domains=("domain:health",),
            reasons=(
                DomainResolutionReason(code="X", message="blocked", blocking=True),
            ),
        )
        engine = _engine(
            resolver=FakeResolver(resolution), composer=FakeComposer(_composition())
        )
        result = engine.execute(_request())
        assert result.status == CrossDomainStatus.BLOCKED

    def test_resolution_failed_is_failed(self) -> None:
        resolution = _resolution(status=DomainResolutionStatus.FAILED, primary=None)
        engine = _engine(
            resolver=FakeResolver(resolution), composer=FakeComposer(_composition())
        )
        result = engine.execute(_request())
        assert result.status == CrossDomainStatus.FAILED


class TestCompositionOutcomes:
    def test_partial_composition_continues(self) -> None:
        composition = _composition(status=DomainCompositionStatus.PARTIAL)
        engine = _engine(
            resolver=FakeResolver(_resolution()),
            composer=FakeComposer(composition),
            cognitive=FakeCognitive(),
        )
        result = engine.execute(_request())
        assert result.status == CrossDomainStatus.COMPLETED

    def test_blocked_composition_is_blocked(self) -> None:
        from cmm.domains.composition_contracts import DomainCompositionConflict

        composition = _composition(
            status=DomainCompositionStatus.BLOCKED,
            conflicts=(
                DomainCompositionConflict(
                    code="X",
                    category="cat",
                    domains=("domain:health",),
                    severity="critical",
                    message="m",
                    blocking=True,
                ),
            ),
        )
        engine = _engine(
            resolver=FakeResolver(_resolution()), composer=FakeComposer(composition)
        )
        result = engine.execute(_request())
        assert result.status == CrossDomainStatus.BLOCKED

    def test_failed_composition_is_failed(self) -> None:
        composition = _composition(status=DomainCompositionStatus.FAILED)
        engine = _engine(
            resolver=FakeResolver(_resolution()), composer=FakeComposer(composition)
        )
        result = engine.execute(_request())
        assert result.status == CrossDomainStatus.FAILED


class TestPlanner:
    def test_plan_cannot_require_knowledge_retroactively(self) -> None:
        planner = FakePlanner(
            lambda composition, context: CrossDomainPlanResult(
                status="completed",
                domain_order=(composition.primary_domain,),
                required_ports=("knowledge",),
            )
        )
        with pytest.raises(CrossDomainPortError):
            _engine(
                resolver=FakeResolver(_resolution()),
                composer=FakeComposer(_composition()),
                planner=planner,
                cognitive=FakeCognitive(),
            ).execute(_request())

    def test_plan_cannot_require_planner_retroactively(self) -> None:
        planner = FakePlanner(
            lambda composition, context: CrossDomainPlanResult(
                status="completed",
                domain_order=(composition.primary_domain,),
                required_ports=("planner",),
            )
        )
        with pytest.raises(CrossDomainPortError):
            _engine(
                resolver=FakeResolver(_resolution()),
                composer=FakeComposer(_composition()),
                planner=planner,
                cognitive=FakeCognitive(),
            ).execute(_request())

    def test_plan_required_ports_are_combined_with_policy(self) -> None:
        composition = _composition(
            workflows=(
                DomainCompositionItem(
                    category="workflows",
                    identifier="wf1",
                    contributing_domains=("domain:health",),
                    primary_contributor="domain:health",
                    precedence=1,
                ),
            ),
            operations=(
                DomainCompositionItem(
                    category="operations",
                    identifier="op1",
                    contributing_domains=("domain:health",),
                    primary_contributor="domain:health",
                    precedence=1,
                ),
            ),
        )
        planner = FakePlanner(
            lambda composition, context: CrossDomainPlanResult(
                status="completed",
                domain_order=(composition.primary_domain,),
                required_ports=("operation",),
            )
        )
        result = _engine(
            resolver=FakeResolver(_resolution()),
            composer=FakeComposer(composition),
            planner=planner,
            cognitive=FakeCognitive(),
            policy=CrossDomainPolicy(required_ports=("workflow",)),
        ).execute(_request())
        unavailable = {
            d.stage.value
            for d in result.decisions
            if d.code == "PORT_UNAVAILABLE" and d.blocking
        }
        assert "workflow_coordination" in unavailable
        assert "operation_coordination" in unavailable
        assert result.status == CrossDomainStatus.BLOCKED

    def test_planner_external_calls_are_recorded(self) -> None:
        planner = FakePlanner(
            lambda composition, context: CrossDomainPlanResult(
                status="completed", external_calls_used=1
            )
        )
        result = _engine(
            resolver=FakeResolver(_resolution()),
            composer=FakeComposer(_composition()),
            planner=planner,
            cognitive=FakeCognitive(),
        ).execute(_request(maximum_external_calls=2))
        assert planner.calls == 1
        assert result.limits.external_calls_used == 1

    def test_planner_cost_is_recorded(self) -> None:
        planner = FakePlanner(
            lambda composition, context: CrossDomainPlanResult(
                status="completed", estimated_cost=0.5
            )
        )
        result = _engine(
            resolver=FakeResolver(_resolution()),
            composer=FakeComposer(_composition()),
            planner=planner,
            cognitive=FakeCognitive(),
        ).execute(_request(maximum_cost=1.0))
        assert result.limits.estimated_cost == 0.5

    def test_planner_not_called_when_external_call_limit_reached(self) -> None:
        planner = FakePlanner(
            lambda composition, context: CrossDomainPlanResult(status="completed")
        )
        result = _engine(
            resolver=FakeResolver(_resolution()),
            composer=FakeComposer(_composition()),
            knowledge=FakeKnowledgePort(
                CrossDomainKnowledgeResult(status="completed", external_calls_used=1)
            ),
            planner=planner,
            cognitive=FakeCognitive(),
        ).execute(_request(maximum_external_calls=1))
        assert planner.calls == 0
        assert "external_calls" in result.limits.reached_limits

    def test_planner_result_exceeding_external_budget_is_rejected(self) -> None:
        planner = FakePlanner(
            lambda composition, context: CrossDomainPlanResult(
                status="completed", external_calls_used=2
            )
        )
        result = _engine(
            resolver=FakeResolver(_resolution()),
            composer=FakeComposer(_composition()),
            planner=planner,
            cognitive=FakeCognitive(),
        ).execute(_request(maximum_external_calls=1))
        assert result.limits.external_calls_used == 0
        assert result.domain_results == ()
        assert "external_calls" in result.limits.reached_limits

    def test_planner_result_exceeding_cost_budget_is_rejected(self) -> None:
        planner = FakePlanner(
            lambda composition, context: CrossDomainPlanResult(
                status="completed", estimated_cost=2.0
            )
        )
        result = _engine(
            resolver=FakeResolver(_resolution()),
            composer=FakeComposer(_composition()),
            planner=planner,
            cognitive=FakeCognitive(),
        ).execute(_request(maximum_cost=1.0))
        assert result.limits.estimated_cost == 0.0
        assert result.domain_results == ()
        assert "cost" in result.limits.reached_limits

    def test_absent_planner_falls_back_to_composition_order(self) -> None:
        engine = _engine(
            resolver=FakeResolver(_resolution(supporting=("domain:general",))),
            composer=FakeComposer(_composition(supporting=("domain:general",))),
            cognitive=FakeCognitive(),
        )
        result = engine.execute(_request(supporting_domains=("domain:general",)))
        assert any(d.code == "PORT_SKIPPED" for d in result.decisions)

    def test_planner_available_reorders_domains(self) -> None:
        def plan_fn(composition, context):
            return CrossDomainPlanResult(
                status="completed",
                domain_order=(
                    composition.primary_domain,
                    *composition.supporting_domains,
                ),
            )

        engine = _engine(
            resolver=FakeResolver(_resolution(supporting=("domain:general",))),
            composer=FakeComposer(_composition(supporting=("domain:general",))),
            planner=FakePlanner(plan_fn),
            cognitive=FakeCognitive(),
        )
        result = engine.execute(_request(supporting_domains=("domain:general",)))
        assert any(d.code == "PLAN_CREATED" for d in result.decisions)

    def test_invalid_plan_domain_raises_port_error(self) -> None:
        def plan_fn(composition, context):
            return CrossDomainPlanResult(
                status="completed", domain_order=("domain:health", "domain:unrelated")
            )

        engine = _engine(
            resolver=FakeResolver(_resolution()),
            composer=FakeComposer(_composition()),
            planner=FakePlanner(plan_fn),
            cognitive=FakeCognitive(),
        )
        with pytest.raises(CrossDomainPortError):
            engine.execute(_request())

    def test_plan_must_place_primary_first(self) -> None:
        def plan_fn(composition, context):
            return CrossDomainPlanResult(
                status="completed",
                domain_order=(
                    composition.supporting_domains[0],
                    composition.primary_domain,
                ),
            )

        engine = _engine(
            resolver=FakeResolver(_resolution(supporting=("domain:general",))),
            composer=FakeComposer(_composition(supporting=("domain:general",))),
            planner=FakePlanner(plan_fn),
            cognitive=FakeCognitive(),
        )
        with pytest.raises(CrossDomainPortError):
            engine.execute(_request(supporting_domains=("domain:general",)))

    def test_planner_domain_duplicates_rejected(self) -> None:
        # Contract itself rejects duplicate domain_order entries at
        # construction time — the engine never even gets to validate it.
        with pytest.raises(CrossDomainContractError):
            CrossDomainPlanResult(
                status="completed",
                domain_order=("domain:health", "domain:health"),
            )

    def test_planner_parallel_group_unknown_domain_rejected(self) -> None:
        with pytest.raises(CrossDomainContractError):
            CrossDomainPlanResult(
                status="completed",
                domain_order=("domain:health",),
                parallel_groups=(("domain:unrelated",),),
            )

    def test_planner_dependency_outside_composition_rejected(self) -> None:
        def plan_fn(composition, context):
            return CrossDomainPlanResult(
                status="completed",
                domain_order=(composition.primary_domain,),
                dependencies=(
                    CrossDomainDependency(
                        source_domain="domain:health",
                        target_domain="domain:unrelated",
                        kind="requires",
                        description="d",
                        provenance=("p",),
                    ),
                ),
            )

        engine = _engine(
            resolver=FakeResolver(_resolution()),
            composer=FakeComposer(_composition()),
            planner=FakePlanner(plan_fn),
            cognitive=FakeCognitive(),
        )
        with pytest.raises(CrossDomainPortError):
            engine.execute(_request())

    def test_omitted_supporting_domain_generates_explicit_decision(self) -> None:
        def plan_fn(composition, context):
            return CrossDomainPlanResult(
                status="completed", domain_order=(composition.primary_domain,)
            )

        engine = _engine(
            resolver=FakeResolver(_resolution(supporting=("domain:general",))),
            composer=FakeComposer(_composition(supporting=("domain:general",))),
            planner=FakePlanner(plan_fn),
            cognitive=FakeCognitive(),
        )
        result = engine.execute(_request(supporting_domains=("domain:general",)))
        omitted = [d for d in result.decisions if d.code == "DOMAIN_OMITTED_BY_PLAN"]
        assert len(omitted) == 1
        assert omitted[0].domain_id.slug == "general"
        assert omitted[0].blocking is False

    def test_required_planner_missing_is_blocked(self) -> None:
        engine = _engine(
            resolver=FakeResolver(_resolution()),
            composer=FakeComposer(_composition()),
            cognitive=FakeCognitive(),
            policy=CrossDomainPolicy(required_ports=("planner",)),
        )
        result = engine.execute(_request())
        assert result.status == CrossDomainStatus.BLOCKED

    def test_required_planner_missing_stops_dependent_execution(self) -> None:
        cognitive = FakeCognitive()
        engine = _engine(
            resolver=FakeResolver(_resolution()),
            composer=FakeComposer(_composition()),
            cognitive=cognitive,
            policy=CrossDomainPolicy(required_ports=("planner",)),
        )
        result = engine.execute(_request())
        assert result.status == CrossDomainStatus.BLOCKED
        # no domain work — and hence no reasoning — happened at all
        assert cognitive.calls == []
        assert result.domain_results == ()


class TestKnowledge:
    def test_knowledge_absent_skipped(self) -> None:
        engine = _engine(
            resolver=FakeResolver(_resolution()),
            composer=FakeComposer(_composition()),
            cognitive=FakeCognitive(),
        )
        result = engine.execute(_request())
        assert any(d.code == "PORT_SKIPPED" for d in result.decisions)

    def test_knowledge_available_merges_entities(self) -> None:
        knowledge_port = FakeKnowledgePort(
            CrossDomainKnowledgeResult(status="completed", entities=("e1",))
        )
        engine = _engine(
            resolver=FakeResolver(_resolution()),
            composer=FakeComposer(_composition()),
            cognitive=FakeCognitive(),
            knowledge=knowledge_port,
        )
        result = engine.execute(_request())
        assert knowledge_port.calls == 1
        assert any(d.code == "KNOWLEDGE_RETRIEVED" for d in result.decisions)

    def test_required_knowledge_missing_stops_dependent_execution(self) -> None:
        cognitive = FakeCognitive()
        engine = _engine(
            resolver=FakeResolver(_resolution()),
            composer=FakeComposer(_composition()),
            cognitive=cognitive,
            policy=CrossDomainPolicy(required_ports=("knowledge",)),
        )
        result = engine.execute(_request())
        assert result.status == CrossDomainStatus.BLOCKED
        assert cognitive.calls == []
        assert result.domain_results == ()

    def test_required_knowledge_missing_skips_planner(self) -> None:
        planner = FakePlanner(
            lambda composition, context: CrossDomainPlanResult(status="completed")
        )
        cognitive = FakeCognitive()
        result = _engine(
            resolver=FakeResolver(_resolution()),
            composer=FakeComposer(_composition()),
            knowledge=None,
            planner=planner,
            cognitive=cognitive,
            policy=CrossDomainPolicy(required_ports=("knowledge",)),
        ).execute(_request())
        assert planner.calls == 0
        assert cognitive.calls == []
        assert result.domain_results == ()

    def test_required_knowledge_missing_skips_domain_execution(self) -> None:
        cognitive = FakeCognitive()
        result = _engine(
            resolver=FakeResolver(_resolution()),
            composer=FakeComposer(_composition()),
            cognitive=cognitive,
            policy=CrossDomainPolicy(required_ports=("knowledge",)),
        ).execute(_request())
        assert cognitive.calls == []
        assert result.domain_results == ()

    def test_knowledge_result_cannot_exceed_remaining_external_calls(self) -> None:
        knowledge = FakeKnowledgePort(
            CrossDomainKnowledgeResult(status="completed", external_calls_used=2)
        )
        result = _engine(
            resolver=FakeResolver(_resolution()),
            composer=FakeComposer(_composition()),
            knowledge=knowledge,
            cognitive=FakeCognitive(),
        ).execute(_request(maximum_external_calls=1))
        assert knowledge.calls == 1
        assert result.limits.external_calls_used == 0
        assert result.shared_findings == ()

    def test_knowledge_result_cannot_exceed_remaining_cost(self) -> None:
        knowledge = FakeKnowledgePort(
            CrossDomainKnowledgeResult(status="completed", estimated_cost=2.0)
        )
        result = _engine(
            resolver=FakeResolver(_resolution()),
            composer=FakeComposer(_composition()),
            knowledge=knowledge,
            cognitive=FakeCognitive(),
        ).execute(_request(maximum_cost=1.0))
        assert result.limits.estimated_cost == 0.0
        assert result.shared_findings == ()

    def test_cognitive_external_calls_are_recorded(self) -> None:
        cognitive = FakeCognitive(
            lambda **kw: CrossDomainDomainResult(
                domain_id=kw["domain_id"], status="completed", external_calls_used=1
            )
        )
        result = _engine(
            resolver=FakeResolver(_resolution()),
            composer=FakeComposer(_composition()),
            cognitive=cognitive,
        ).execute(_request(maximum_external_calls=2))
        assert result.limits.external_calls_used == 1
        assert result.domain_results[0].external_calls_used == 1

    def test_cognitive_cost_is_recorded(self) -> None:
        cognitive = FakeCognitive(
            lambda **kw: CrossDomainDomainResult(
                domain_id=kw["domain_id"], status="completed", estimated_cost=0.5
            )
        )
        result = _engine(
            resolver=FakeResolver(_resolution()),
            composer=FakeComposer(_composition()),
            cognitive=cognitive,
        ).execute(_request(maximum_cost=1.0))
        assert result.limits.estimated_cost == 0.5

    def test_cognitive_not_called_when_external_call_limit_reached(self) -> None:
        cognitive = FakeCognitive()
        result = _engine(
            resolver=FakeResolver(_resolution()),
            composer=FakeComposer(_composition()),
            knowledge=FakeKnowledgePort(
                CrossDomainKnowledgeResult(status="completed", external_calls_used=1)
            ),
            cognitive=cognitive,
        ).execute(_request(maximum_external_calls=1))
        assert cognitive.calls == []
        assert "external_calls" in result.limits.reached_limits

    def test_cognitive_result_exceeding_budget_is_rejected(self) -> None:
        cognitive = FakeCognitive(
            lambda **kw: CrossDomainDomainResult(
                domain_id=kw["domain_id"],
                status="completed",
                findings=(_finding("rejected", kw["domain_id"].slug),),
                external_calls_used=2,
            )
        )
        result = _engine(
            resolver=FakeResolver(_resolution()),
            composer=FakeComposer(_composition()),
            cognitive=cognitive,
        ).execute(_request(maximum_external_calls=1))
        assert result.domain_results == ()
        assert result.shared_findings == ()
        assert result.limits.external_calls_used == 0

    def test_agent_external_calls_are_recorded(self) -> None:
        agent = FakeAgent(
            lambda **kw: CrossDomainDomainResult(
                domain_id=kw["domain_id"], status="completed", external_calls_used=1
            )
        )
        result = _engine(
            resolver=FakeResolver(_resolution()),
            composer=FakeComposer(_composition()),
            agent=agent,
        ).execute(_request(maximum_external_calls=2))
        assert result.limits.external_calls_used == 1

    def test_agent_cost_is_recorded(self) -> None:
        agent = FakeAgent(
            lambda **kw: CrossDomainDomainResult(
                domain_id=kw["domain_id"], status="completed", estimated_cost=0.5
            )
        )
        result = _engine(
            resolver=FakeResolver(_resolution()),
            composer=FakeComposer(_composition()),
            agent=agent,
        ).execute(_request(maximum_cost=1.0))
        assert result.limits.estimated_cost == 0.5

    def test_agent_not_called_when_cost_limit_reached(self) -> None:
        agent = FakeAgent()
        planner = FakePlanner(
            lambda composition, context: CrossDomainPlanResult(
                status="completed", estimated_cost=1.0
            )
        )
        result = _engine(
            resolver=FakeResolver(_resolution()),
            composer=FakeComposer(_composition()),
            planner=planner,
            agent=agent,
        ).execute(_request(maximum_cost=1.0))
        assert agent.calls == []
        assert "cost" in result.limits.reached_limits

    def test_agent_result_exceeding_budget_is_rejected(self) -> None:
        agent = FakeAgent(
            lambda **kw: CrossDomainDomainResult(
                domain_id=kw["domain_id"],
                status="completed",
                findings=(_finding("rejected-agent", kw["domain_id"].slug),),
                estimated_cost=2.0,
            )
        )
        result = _engine(
            resolver=FakeResolver(_resolution()),
            composer=FakeComposer(_composition()),
            agent=agent,
        ).execute(_request(maximum_cost=1.0))
        assert result.domain_results == ()
        assert result.shared_findings == ()

    def test_workflow_result_cannot_exceed_remaining_external_calls(self) -> None:
        workflow = FakeWorkflowPort(
            CrossDomainWorkflowResult(
                status="completed",
                findings=(_finding("rejected-workflow", "health"),),
                external_calls_used=2,
            )
        )
        composition = _composition(
            workflows=(
                DomainCompositionItem(
                    category="workflows",
                    identifier="wf1",
                    contributing_domains=("domain:health",),
                    primary_contributor="domain:health",
                    precedence=1,
                ),
            )
        )
        result = _engine(
            resolver=FakeResolver(_resolution()),
            composer=FakeComposer(composition),
            cognitive=FakeCognitive(),
            workflow=workflow,
        ).execute(_request(maximum_external_calls=1))
        assert result.limits.external_calls_used == 0
        assert not any(
            f.identifier == "rejected-workflow" for f in result.shared_findings
        )

    def test_operation_result_cannot_exceed_remaining_external_calls(self) -> None:
        operation = FakeOperationPort(
            CrossDomainOperationResult(
                status="completed",
                findings=(_finding("rejected-operation", "health"),),
                external_calls_used=2,
            )
        )
        composition = _composition(
            operations=(
                DomainCompositionItem(
                    category="operations",
                    identifier="op1",
                    contributing_domains=("domain:health",),
                    primary_contributor="domain:health",
                    precedence=1,
                ),
            )
        )
        result = _engine(
            resolver=FakeResolver(_resolution()),
            composer=FakeComposer(composition),
            cognitive=FakeCognitive(),
            operation=operation,
        ).execute(_request(maximum_external_calls=1))
        assert result.limits.external_calls_used == 0
        assert not any(
            f.identifier == "rejected-operation" for f in result.shared_findings
        )

    def test_workflow_result_cannot_exceed_remaining_cost(self) -> None:
        workflow = FakeWorkflowPort(
            CrossDomainWorkflowResult(
                status="completed",
                findings=(_finding("rejected-workflow-cost", "health"),),
                estimated_cost=2.0,
            )
        )
        composition = _composition(
            workflows=(
                DomainCompositionItem(
                    category="workflows",
                    identifier="wf1",
                    contributing_domains=("domain:health",),
                    primary_contributor="domain:health",
                    precedence=1,
                ),
            )
        )
        result = _engine(
            resolver=FakeResolver(_resolution()),
            composer=FakeComposer(composition),
            cognitive=FakeCognitive(),
            workflow=workflow,
        ).execute(_request(maximum_cost=1.0))
        assert result.limits.estimated_cost == 0.0
        assert not any(
            f.identifier == "rejected-workflow-cost" for f in result.shared_findings
        )

    def test_operation_result_cannot_exceed_remaining_cost(self) -> None:
        operation = FakeOperationPort(
            CrossDomainOperationResult(
                status="completed",
                findings=(_finding("rejected-operation-cost", "health"),),
                estimated_cost=2.0,
            )
        )
        composition = _composition(
            operations=(
                DomainCompositionItem(
                    category="operations",
                    identifier="op1",
                    contributing_domains=("domain:health",),
                    primary_contributor="domain:health",
                    precedence=1,
                ),
            )
        )
        result = _engine(
            resolver=FakeResolver(_resolution()),
            composer=FakeComposer(composition),
            cognitive=FakeCognitive(),
            operation=operation,
        ).execute(_request(maximum_cost=1.0))
        assert result.limits.estimated_cost == 0.0
        assert not any(
            f.identifier == "rejected-operation-cost" for f in result.shared_findings
        )

    def test_precall_rejection_records_external_calls_limit(self) -> None:
        result = _engine(
            resolver=FakeResolver(_resolution()),
            composer=FakeComposer(_composition()),
            knowledge=FakeKnowledgePort(
                CrossDomainKnowledgeResult(status="completed", external_calls_used=1)
            ),
            cognitive=FakeCognitive(),
        ).execute(_request(maximum_external_calls=1))
        assert result.limits.reached_limits == ("external_calls",)

    def test_precall_rejection_records_cost_limit(self) -> None:
        result = _engine(
            resolver=FakeResolver(_resolution()),
            composer=FakeComposer(_composition()),
            cognitive=FakeCognitive(),
        ).execute(_request(maximum_cost=0.0))
        assert "cost" in result.limits.reached_limits

    def test_rejected_port_result_does_not_overincrement_counters(self) -> None:
        cognitive = FakeCognitive(
            lambda **kw: CrossDomainDomainResult(
                domain_id=kw["domain_id"], status="completed", external_calls_used=2
            )
        )
        result = _engine(
            resolver=FakeResolver(_resolution()),
            composer=FakeComposer(_composition()),
            cognitive=cognitive,
        ).execute(_request(maximum_external_calls=1))
        assert result.limits.external_calls_used == 0


class TestWorkflowAndOperations:
    def test_plan_required_workflow_missing_is_blocked(self) -> None:
        composition = _composition(
            workflows=(
                DomainCompositionItem(
                    category="workflows",
                    identifier="wf1",
                    contributing_domains=("domain:health",),
                    primary_contributor="domain:health",
                    precedence=1,
                ),
            )
        )
        planner = FakePlanner(
            lambda composition, context: CrossDomainPlanResult(
                status="completed",
                domain_order=(composition.primary_domain,),
                required_ports=("workflow",),
            )
        )
        result = _engine(
            resolver=FakeResolver(_resolution()),
            composer=FakeComposer(composition),
            planner=planner,
            cognitive=FakeCognitive(),
        ).execute(_request())
        assert result.status == CrossDomainStatus.BLOCKED
        assert any(
            d.code == "PORT_UNAVAILABLE"
            and d.stage.value == "workflow_coordination"
            and d.blocking
            for d in result.decisions
        )
        assert not any(
            d.code == "PORT_SKIPPED" and d.stage.value == "workflow_coordination"
            for d in result.decisions
        )

    def test_plan_required_operation_missing_is_blocked(self) -> None:
        composition = _composition(
            operations=(
                DomainCompositionItem(
                    category="operations",
                    identifier="op1",
                    contributing_domains=("domain:health",),
                    primary_contributor="domain:health",
                    precedence=1,
                ),
            )
        )
        planner = FakePlanner(
            lambda composition, context: CrossDomainPlanResult(
                status="completed",
                domain_order=(composition.primary_domain,),
                required_ports=("operation",),
            )
        )
        result = _engine(
            resolver=FakeResolver(_resolution()),
            composer=FakeComposer(composition),
            planner=planner,
            cognitive=FakeCognitive(),
        ).execute(_request())
        assert result.status == CrossDomainStatus.BLOCKED
        assert any(
            d.code == "PORT_UNAVAILABLE"
            and d.stage.value == "operation_coordination"
            and d.blocking
            for d in result.decisions
        )
        assert not any(
            d.code == "PORT_SKIPPED" and d.stage.value == "operation_coordination"
            for d in result.decisions
        )

    def test_workflow_flow(self) -> None:
        workflows = (
            DomainCompositionItem(
                category="workflows",
                identifier="wf1",
                contributing_domains=("domain:health",),
                primary_contributor="domain:health",
                precedence=1,
            ),
        )
        composition = _composition(workflows=workflows)
        workflow_port = FakeWorkflowPort(
            CrossDomainWorkflowResult(status="completed", workflow_ids=("wf1",))
        )
        engine = _engine(
            resolver=FakeResolver(_resolution()),
            composer=FakeComposer(composition),
            cognitive=FakeCognitive(),
            workflow=workflow_port,
        )
        result = engine.execute(_request())
        assert workflow_port.calls == [("wf1",)]
        assert any(d.code == "WORKFLOW_COORDINATED" for d in result.decisions)

    def test_workflow_external_call_limit_checked_before_call(self) -> None:
        workflows = (
            DomainCompositionItem(
                category="workflows",
                identifier="wf1",
                contributing_domains=("domain:health",),
                primary_contributor="domain:health",
                precedence=1,
            ),
        )
        composition = _composition(workflows=workflows)
        workflow_port = FakeWorkflowPort(
            CrossDomainWorkflowResult(status="completed", workflow_ids=("wf1",))
        )
        # A knowledge call exhausts the single external-call slot before the
        # workflow port would otherwise be invoked.
        knowledge_port = FakeKnowledgePort(
            CrossDomainKnowledgeResult(status="completed", external_calls_used=1)
        )
        engine = _engine(
            resolver=FakeResolver(_resolution()),
            composer=FakeComposer(composition),
            cognitive=FakeCognitive(),
            workflow=workflow_port,
            knowledge=knowledge_port,
        )
        result = engine.execute(_request(maximum_external_calls=1))
        # the port must never be invoked once the external-call budget is
        # already exhausted, and the skip must be recorded as a limit
        assert workflow_port.calls == []
        assert any(
            d.code == "LIMIT_REACHED" and d.action.startswith("skip workflow")
            for d in result.decisions
        )

    def test_operations_call_operation_port(self) -> None:
        operations = (
            DomainCompositionItem(
                category="operations",
                identifier="op1",
                contributing_domains=("domain:health",),
                primary_contributor="domain:health",
                precedence=1,
            ),
        )
        composition = _composition(operations=operations)
        operation_port = FakeOperationPort(
            CrossDomainOperationResult(status="completed", operation_ids=("op1",))
        )
        engine = _engine(
            resolver=FakeResolver(_resolution()),
            composer=FakeComposer(composition),
            cognitive=FakeCognitive(),
            operation=operation_port,
        )
        result = engine.execute(_request())
        assert len(operation_port.calls) == 1
        assert operation_port.calls[0][0] == ("op1",)
        assert any(d.code == "OPERATION_COORDINATED" for d in result.decisions)

    def test_operations_not_marked_coordinated_without_port(self) -> None:
        operations = (
            DomainCompositionItem(
                category="operations",
                identifier="op1",
                contributing_domains=("domain:health",),
                primary_contributor="domain:health",
                precedence=1,
            ),
        )
        composition = _composition(operations=operations)
        engine = _engine(
            resolver=FakeResolver(_resolution()),
            composer=FakeComposer(composition),
            cognitive=FakeCognitive(),
        )
        result = engine.execute(_request())
        assert not any(d.code == "OPERATION_COORDINATED" for d in result.decisions)
        assert any(d.code == "PORT_SKIPPED" for d in result.decisions)

    def test_operation_requesting_domains_preserved(self) -> None:
        operations = (
            DomainCompositionItem(
                category="operations",
                identifier="op1",
                contributing_domains=("domain:health",),
                primary_contributor="domain:health",
                precedence=1,
            ),
        )
        composition = _composition(
            operations=operations, supporting=("domain:general",)
        )
        operation_port = FakeOperationPort(
            CrossDomainOperationResult(status="completed", operation_ids=("op1",))
        )

        def cognitive_fn(*, domain_id, objective, context):
            ops = ("op1",) if domain_id.slug == "general" else ()
            return CrossDomainDomainResult(
                domain_id=domain_id, status="completed", operations=ops
            )

        engine = _engine(
            resolver=FakeResolver(_resolution(supporting=("domain:general",))),
            composer=FakeComposer(composition),
            cognitive=FakeCognitive(cognitive_fn),
            operation=operation_port,
        )
        engine.execute(_request(supporting_domains=("domain:general",)))
        _, requesting = operation_port.calls[0]
        assert {d.slug for d in requesting["op1"]} == {"health", "general"}

    def test_required_workflow_port_missing_is_blocked(self) -> None:
        workflows = (
            DomainCompositionItem(
                category="workflows",
                identifier="wf1",
                contributing_domains=("domain:health",),
                primary_contributor="domain:health",
                precedence=1,
            ),
        )
        composition = _composition(workflows=workflows)
        engine = _engine(
            resolver=FakeResolver(_resolution()),
            composer=FakeComposer(composition),
            cognitive=FakeCognitive(),
            policy=CrossDomainPolicy(required_ports=("workflow",)),
        )
        result = engine.execute(_request())
        assert result.status == CrossDomainStatus.BLOCKED


class TestPortAvailability:
    def test_optional_reasoning_port_unavailable_is_partial_or_failed(self) -> None:
        engine = _engine(
            resolver=FakeResolver(_resolution()),
            composer=FakeComposer(_composition()),
        )
        result = engine.execute(_request())
        assert result.status == CrossDomainStatus.FAILED
        assert any(
            d.code == "PORT_UNAVAILABLE" and not d.blocking for d in result.decisions
        )

    def test_required_reasoning_port_unavailable_is_blocked(self) -> None:
        engine = _engine(
            resolver=FakeResolver(_resolution()),
            composer=FakeComposer(_composition()),
            policy=CrossDomainPolicy(required_ports=("agent", "cognitive")),
        )
        result = engine.execute(_request())
        assert result.status == CrossDomainStatus.BLOCKED

    def test_unknown_required_port_rejected(self) -> None:
        with pytest.raises(CrossDomainContractError):
            CrossDomainPolicy(required_ports=("cognitiv",))  # typo


class TestDomainModes:
    def test_plan_required_agent_missing_blocks_agent_domain(self) -> None:
        planner = FakePlanner(
            lambda composition, context: CrossDomainPlanResult(
                status="completed",
                domain_order=(composition.primary_domain,),
                domain_modes={str(composition.primary_domain): "agent"},
                required_ports=("agent",),
            )
        )
        cognitive = FakeCognitive()
        result = _engine(
            resolver=FakeResolver(_resolution()),
            composer=FakeComposer(_composition()),
            planner=planner,
            cognitive=cognitive,
        ).execute(_request())
        assert cognitive.calls == []
        assert result.status == CrossDomainStatus.BLOCKED
        assert any(
            d.code == "PORT_UNAVAILABLE" and d.blocking for d in result.decisions
        )

    def test_plan_required_cognitive_missing_blocks_cognitive_domain(self) -> None:
        planner = FakePlanner(
            lambda composition, context: CrossDomainPlanResult(
                status="completed",
                domain_order=(composition.primary_domain,),
                domain_modes={str(composition.primary_domain): "cognitive"},
                required_ports=("cognitive",),
            )
        )
        agent = FakeAgent()
        result = _engine(
            resolver=FakeResolver(_resolution()),
            composer=FakeComposer(_composition()),
            planner=planner,
            agent=agent,
        ).execute(_request())
        assert agent.calls == []
        assert result.status == CrossDomainStatus.BLOCKED
        assert any(
            d.code == "PORT_UNAVAILABLE" and d.blocking for d in result.decisions
        )

    def test_required_domain_mode_has_no_silent_fallback(self) -> None:
        planner = FakePlanner(
            lambda composition, context: CrossDomainPlanResult(
                status="completed",
                domain_order=(composition.primary_domain,),
                domain_modes={str(composition.primary_domain): "agent"},
                required_ports=("agent",),
            )
        )
        cognitive = FakeCognitive()
        result = _engine(
            resolver=FakeResolver(_resolution()),
            composer=FakeComposer(_composition()),
            planner=planner,
            cognitive=cognitive,
        ).execute(_request())
        assert cognitive.calls == []
        assert not any(d.code == "DOMAIN_RESULT_MERGED" for d in result.decisions)
        assert result.status == CrossDomainStatus.BLOCKED

    def test_only_action_domain_uses_agent(self) -> None:
        cognitive = FakeCognitive()
        agent = FakeAgent()

        def plan_fn(composition, context):
            return CrossDomainPlanResult(
                status="completed",
                domain_order=(
                    composition.primary_domain,
                    *composition.supporting_domains,
                ),
                domain_modes={str(composition.supporting_domains[0]): "agent"},
            )

        engine = _engine(
            resolver=FakeResolver(_resolution(supporting=("domain:general",))),
            composer=FakeComposer(_composition(supporting=("domain:general",))),
            planner=FakePlanner(plan_fn),
            cognitive=cognitive,
            agent=agent,
        )
        engine.execute(_request(supporting_domains=("domain:general",)))
        assert [d.slug for d in cognitive.calls] == ["health"]
        assert [d.slug for d in agent.calls] == ["general"]

    def test_reasoning_domain_uses_cognitive(self) -> None:
        cognitive = FakeCognitive()
        agent = FakeAgent()

        def plan_fn(composition, context):
            return CrossDomainPlanResult(
                status="completed",
                domain_order=(
                    composition.primary_domain,
                    *composition.supporting_domains,
                ),
                domain_modes={str(composition.primary_domain): "cognitive"},
            )

        engine = _engine(
            resolver=FakeResolver(_resolution(supporting=("domain:general",))),
            composer=FakeComposer(_composition(supporting=("domain:general",))),
            planner=FakePlanner(plan_fn),
            cognitive=cognitive,
            agent=agent,
        )
        engine.execute(_request(supporting_domains=("domain:general",)))
        # "health" is explicitly declared cognitive; "general" has no
        # declared mode, so it defaults to Cognitive too (never Agent) —
        # no double-invocation of any domain.
        assert [d.slug for d in cognitive.calls] == ["health", "general"]
        assert agent.calls == []

    def test_declared_agent_mode_does_not_silently_fall_back_to_cognitive(self) -> None:
        cognitive = FakeCognitive()

        def plan_fn(composition, context):
            return CrossDomainPlanResult(
                status="completed",
                domain_order=(composition.primary_domain,),
                domain_modes={str(composition.primary_domain): "agent"},
            )

        engine = _engine(
            resolver=FakeResolver(_resolution()),
            composer=FakeComposer(_composition()),
            planner=FakePlanner(plan_fn),
            cognitive=cognitive,
            # no agent configured
        )
        result = engine.execute(_request())
        assert cognitive.calls == []
        assert any(d.code == "PORT_UNAVAILABLE" for d in result.decisions)


class TestIndependentContinuationAndBlocking:
    def test_independent_domain_continues_after_sibling_blocks(self) -> None:
        def cognitive_fn(*, domain_id, objective, context):
            if domain_id.slug == "health":
                return CrossDomainDomainResult(
                    domain_id=domain_id,
                    status="blocked",
                    gaps=(
                        CrossDomainGap(
                            code="g1",
                            domain_id=domain_id,
                            description="d",
                            blocking=True,
                        ),
                    ),
                )
            return CrossDomainDomainResult(
                domain_id=domain_id,
                status="completed",
                findings=(_finding("general-finding", "general"),),
                recommendations=("general rec",),
                confidence=0.9,
            )

        engine = _engine(
            resolver=FakeResolver(_resolution(supporting=("domain:general",))),
            composer=FakeComposer(_composition(supporting=("domain:general",))),
            cognitive=FakeCognitive(cognitive_fn),
            policy=CrossDomainPolicy(continue_independent_domains=True),
        )
        result = engine.execute(_request(supporting_domains=("domain:general",)))
        assert result.status == CrossDomainStatus.PARTIAL
        assert any(d.code == "PARTIAL_RESULT_RETAINED" for d in result.decisions)
        assert {r.domain_id.slug for r in result.domain_results} == {
            "health",
            "general",
        }

    def test_blocker_propagates_to_dependent_domain(self) -> None:
        def plan_fn(composition, context):
            return CrossDomainPlanResult(
                status="completed",
                domain_order=(
                    composition.primary_domain,
                    *composition.supporting_domains,
                ),
                dependencies=(
                    CrossDomainDependency(
                        source_domain="domain:health",
                        target_domain="domain:general",
                        kind="requires",
                        description="d",
                        provenance=("p",),
                    ),
                ),
            )

        def cognitive_fn(*, domain_id, objective, context):
            if domain_id.slug == "health":
                return CrossDomainDomainResult(domain_id=domain_id, status="failed")
            return CrossDomainDomainResult(domain_id=domain_id, status="completed")

        engine = _engine(
            resolver=FakeResolver(_resolution(supporting=("domain:general",))),
            composer=FakeComposer(_composition(supporting=("domain:general",))),
            planner=FakePlanner(plan_fn),
            cognitive=FakeCognitive(cognitive_fn),
        )
        result = engine.execute(_request(supporting_domains=("domain:general",)))
        skipped = [d for d in result.decisions if d.code == "DOMAIN_SKIPPED"]
        assert len(skipped) == 1
        assert skipped[0].domain_id.slug == "general"


class TestFindingTransfer:
    def test_finding_transfer_preserves_source_provenance(self) -> None:
        def plan_fn(composition, context):
            return CrossDomainPlanResult(
                status="completed",
                domain_order=(
                    composition.primary_domain,
                    *composition.supporting_domains,
                ),
                dependencies=(
                    CrossDomainDependency(
                        source_domain="domain:health",
                        target_domain="domain:general",
                        kind="requires",
                        description="health informs general",
                        provenance=("dependency-provenance",),
                    ),
                ),
            )

        def cognitive_fn(*, domain_id, objective, context):
            if domain_id.slug == "health":
                return CrossDomainDomainResult(
                    domain_id=domain_id,
                    status="completed",
                    findings=(
                        CrossDomainFinding(
                            identifier="symptom-1",
                            value="fatigue",
                            source_domains=("domain:health",),
                            provenance=("finding-own-provenance",),
                        ),
                    ),
                )
            # by the time "general" runs, the transfer should already have
            # happened and be visible on the snapshot
            transferred = [t for t in context.transfers if t.identifier == "symptom-1"]
            assert len(transferred) == 1
            assert transferred[0].provenance == ("finding-own-provenance",)
            assert transferred[0].provenance != ("dependency-provenance",)
            return CrossDomainDomainResult(domain_id=domain_id, status="completed")

        engine = _engine(
            resolver=FakeResolver(_resolution(supporting=("domain:general",))),
            composer=FakeComposer(_composition(supporting=("domain:general",))),
            planner=FakePlanner(plan_fn),
            cognitive=FakeCognitive(cognitive_fn),
        )
        result = engine.execute(_request(supporting_domains=("domain:general",)))
        transferred_decisions = [
            d for d in result.decisions if d.code == "CONTEXT_TRANSFERRED"
        ]
        assert len(transferred_decisions) == 1

    def test_dependency_provenance_cannot_replace_finding_provenance(self) -> None:
        captured = {}

        def plan_fn(composition, context):
            return CrossDomainPlanResult(
                status="completed",
                domain_order=(
                    composition.primary_domain,
                    *composition.supporting_domains,
                ),
                dependencies=(
                    CrossDomainDependency(
                        source_domain="domain:health",
                        target_domain="domain:general",
                        kind="requires",
                        description="d",
                        provenance=("dependency-provenance-should-not-appear",),
                    ),
                ),
            )

        def cognitive_fn(*, domain_id, objective, context):
            if domain_id.slug == "health":
                return CrossDomainDomainResult(
                    domain_id=domain_id,
                    status="completed",
                    findings=(
                        CrossDomainFinding(
                            identifier="f1",
                            value="v",
                            source_domains=("domain:health",),
                            provenance=("real-finding-provenance",),
                        ),
                    ),
                )
            captured["transfers"] = context.transfers
            return CrossDomainDomainResult(domain_id=domain_id, status="completed")

        engine = _engine(
            resolver=FakeResolver(_resolution(supporting=("domain:general",))),
            composer=FakeComposer(_composition(supporting=("domain:general",))),
            planner=FakePlanner(plan_fn),
            cognitive=FakeCognitive(cognitive_fn),
        )
        engine.execute(_request(supporting_domains=("domain:general",)))
        transfer = captured["transfers"][0]
        assert transfer.provenance == ("real-finding-provenance",)
        assert "dependency-provenance-should-not-appear" not in transfer.provenance

    def test_private_finding_not_transferred(self) -> None:
        def plan_fn(composition, context):
            return CrossDomainPlanResult(
                status="completed",
                domain_order=(
                    composition.primary_domain,
                    *composition.supporting_domains,
                ),
                dependencies=(
                    CrossDomainDependency(
                        source_domain="domain:health",
                        target_domain="domain:general",
                        kind="requires",
                        description="d",
                        provenance=("p",),
                    ),
                ),
            )

        def cognitive_fn(*, domain_id, objective, context):
            if domain_id.slug == "health":
                return CrossDomainDomainResult(
                    domain_id=domain_id,
                    status="completed",
                    findings=(
                        CrossDomainFinding(
                            identifier="private-f",
                            value="v",
                            source_domains=("domain:health",),
                            provenance=("p",),
                            private=True,
                        ),
                    ),
                )
            return CrossDomainDomainResult(domain_id=domain_id, status="completed")

        engine = _engine(
            resolver=FakeResolver(_resolution(supporting=("domain:general",))),
            composer=FakeComposer(_composition(supporting=("domain:general",))),
            planner=FakePlanner(plan_fn),
            cognitive=FakeCognitive(cognitive_fn),
        )
        result = engine.execute(_request(supporting_domains=("domain:general",)))
        assert not any(d.code == "CONTEXT_TRANSFERRED" for d in result.decisions)
        assert any(d.code == "CONTEXT_TRANSFER_BLOCKED" for d in result.decisions)

    def test_composition_permission_denies_transfer(self) -> None:
        def plan_fn(composition, context):
            return CrossDomainPlanResult(
                status="completed",
                domain_order=(
                    composition.primary_domain,
                    *composition.supporting_domains,
                ),
                dependencies=(
                    CrossDomainDependency(
                        source_domain="domain:health",
                        target_domain="domain:general",
                        kind="requires",
                        description="d",
                        provenance=("p",),
                    ),
                ),
            )

        def cognitive_fn(*, domain_id, objective, context):
            if domain_id.slug == "health":
                return CrossDomainDomainResult(
                    domain_id=domain_id,
                    status="completed",
                    findings=(
                        CrossDomainFinding(
                            identifier="f1",
                            value="v",
                            source_domains=("domain:health",),
                            provenance=("p",),
                        ),
                    ),
                )
            return CrossDomainDomainResult(domain_id=domain_id, status="completed")

        composition = _composition(
            supporting=("domain:general",),
            permissions=PermissionComposition(denied_permissions=("deny:health",)),
        )
        engine = _engine(
            resolver=FakeResolver(_resolution(supporting=("domain:general",))),
            composer=FakeComposer(composition),
            planner=FakePlanner(plan_fn),
            cognitive=FakeCognitive(cognitive_fn),
        )
        result = engine.execute(_request(supporting_domains=("domain:general",)))
        assert not any(d.code == "CONTEXT_TRANSFERRED" for d in result.decisions)
        assert any(d.code == "CONTEXT_TRANSFER_BLOCKED" for d in result.decisions)


class TestContradictionsAndGaps:
    def test_high_severity_contradiction_requires_review(self) -> None:
        def cognitive_fn(*, domain_id, objective, context):
            return CrossDomainDomainResult(
                domain_id=domain_id,
                status="completed",
                contradictions=(
                    CrossDomainContradiction(
                        id="c1",
                        domains=("domain:health", "domain:general"),
                        subject="s",
                        statements=("a", "b"),
                        severity="critical",
                        provenance=("p",),
                    ),
                ),
            )

        engine = _engine(
            resolver=FakeResolver(_resolution(supporting=("domain:general",))),
            composer=FakeComposer(_composition(supporting=("domain:general",))),
            cognitive=FakeCognitive(cognitive_fn),
        )
        result = engine.execute(_request(supporting_domains=("domain:general",)))
        assert result.status == CrossDomainStatus.REQUIRES_REVIEW

    def test_recoverable_gap_generates_question(self) -> None:
        def cognitive_fn(*, domain_id, objective, context):
            return CrossDomainDomainResult(
                domain_id=domain_id,
                status="completed",
                gaps=(
                    CrossDomainGap(
                        code="g1",
                        domain_id=domain_id,
                        description="missing info",
                        recoverable=True,
                    ),
                ),
                questions=(
                    CrossDomainQuestion(
                        id="q1",
                        subject="s",
                        requested_information="ri",
                        requesting_domains=(domain_id,),
                        provenance=("p",),
                    ),
                ),
                findings=(_finding("f", domain_id.slug),),
                recommendations=("r",),
                confidence=0.7,
            )

        engine = _engine(
            resolver=FakeResolver(_resolution()),
            composer=FakeComposer(_composition()),
            cognitive=FakeCognitive(cognitive_fn),
        )
        result = engine.execute(_request())
        assert len(result.open_questions) == 1
        assert len(result.cross_domain_gaps) == 1


class TestLimits:
    def test_limit_reached_when_iterations_too_small(self) -> None:
        engine = _engine(
            resolver=FakeResolver(_resolution(supporting=("domain:general",))),
            composer=FakeComposer(_composition(supporting=("domain:general",))),
            cognitive=FakeCognitive(),
        )
        result = engine.execute(
            _request(supporting_domains=("domain:general",), maximum_iterations=1)
        )
        assert result.status == CrossDomainStatus.LIMIT_REACHED
        assert "iterations" in result.limits.reached_limits
        assert len(result.domain_results) == 1

    def test_limit_reached_never_becomes_failed(self) -> None:
        engine = _engine(
            resolver=FakeResolver(_resolution(supporting=("domain:general",))),
            composer=FakeComposer(_composition(supporting=("domain:general",))),
            cognitive=FakeCognitive(),
        )
        result = engine.execute(
            _request(supporting_domains=("domain:general",), maximum_iterations=1)
        )
        assert result.status != CrossDomainStatus.FAILED

    def test_question_limit_prevents_overconsumption(self) -> None:
        def cognitive_fn(*, domain_id, objective, context):
            questions = tuple(
                CrossDomainQuestion(
                    id=f"q{i}",
                    subject=f"s{i}",
                    requested_information="ri",
                    provenance=("p",),
                )
                for i in range(3)
            )
            return CrossDomainDomainResult(
                domain_id=domain_id, status="completed", questions=questions
            )

        engine = _engine(
            resolver=FakeResolver(_resolution()),
            composer=FakeComposer(_composition()),
            cognitive=FakeCognitive(cognitive_fn),
        )
        result = engine.execute(_request(maximum_questions=2))
        assert len(result.open_questions) == 2
        assert "questions" in result.limits.reached_limits
        overflow_gaps = [
            g for g in result.cross_domain_gaps if g.code == "QUESTION_LIMIT_EXCEEDED"
        ]
        assert len(overflow_gaps) == 1

    def test_resolver_and_composer_never_consume_external_call_budget(self) -> None:
        # Resolver/composer are treated as internal calls: even with a tight
        # external-call budget and no knowledge/workflow/operation ports
        # configured (so nothing else could consume it either), the budget
        # must remain untouched after a normal run.
        engine = _engine(
            resolver=FakeResolver(_resolution()),
            composer=FakeComposer(_composition()),
            cognitive=FakeCognitive(),
        )
        result = engine.execute(_request(maximum_external_calls=1))
        assert result.composition_id == "comp-1"
        assert result.status == CrossDomainStatus.COMPLETED
        assert result.limits.external_calls_used == 0
        assert "external_calls" not in result.limits.reached_limits

    def test_parallel_group_size_exceeded_recorded_in_reached_limits(self) -> None:
        def plan_fn(composition, context):
            return CrossDomainPlanResult(
                status="completed",
                domain_order=(
                    composition.primary_domain,
                    *composition.supporting_domains,
                ),
                parallel_groups=(
                    (composition.primary_domain, *composition.supporting_domains),
                ),
            )

        engine = _engine(
            resolver=FakeResolver(_resolution(supporting=("domain:general",))),
            composer=FakeComposer(_composition(supporting=("domain:general",))),
            planner=FakePlanner(plan_fn),
            cognitive=FakeCognitive(),
            policy=CrossDomainPolicy(maximum_parallel_group_size=1),
        )
        result = engine.execute(_request(supporting_domains=("domain:general",)))
        assert "parallel_group_size" in result.limits.reached_limits


class TestFactoriesAndPortErrors:
    def test_invalid_request_type_rejected(self) -> None:
        engine = _engine(
            resolver=FakeResolver(_resolution()), composer=FakeComposer(_composition())
        )
        with pytest.raises(CrossDomainContractError):
            engine.execute(object())  # type: ignore[arg-type]

    def test_id_factory_returning_empty_string_rejected(self) -> None:
        engine = _engine(
            resolver=FakeResolver(_resolution()),
            composer=FakeComposer(_composition()),
            cognitive=FakeCognitive(),
            id_factory=lambda: "",
        )
        with pytest.raises(CrossDomainConfigurationError):
            engine.execute(_request())

    def test_clock_naive_datetime_rejected(self) -> None:
        engine = _engine(
            resolver=FakeResolver(_resolution()),
            composer=FakeComposer(_composition()),
            cognitive=FakeCognitive(),
            clock=lambda: datetime.fromisoformat("2026-01-01T00:00:00"),
        )
        with pytest.raises(CrossDomainConfigurationError):
            engine.execute(_request())

    def test_factory_exception_propagates(self) -> None:
        def _boom() -> str:
            raise RuntimeError("factory exploded")

        engine = _engine(
            resolver=FakeResolver(_resolution()),
            composer=FakeComposer(_composition()),
            cognitive=FakeCognitive(),
            id_factory=_boom,
        )
        with pytest.raises(RuntimeError):
            engine.execute(_request())

    def test_port_exception_propagates(self) -> None:
        engine = _engine(
            resolver=ExplodingPort(), composer=FakeComposer(_composition())
        )
        with pytest.raises(RuntimeError):
            engine.execute(_request())

    def test_resolver_wrong_return_type_raises_port_error(self) -> None:
        class BadResolver:
            def resolve(self, request):
                return "not-a-result"

        engine = _engine(resolver=BadResolver(), composer=FakeComposer(_composition()))
        with pytest.raises(CrossDomainPortError):
            engine.execute(_request())

    def test_constructor_rejects_incompatible_required_port(self) -> None:
        with pytest.raises(CrossDomainConfigurationError):
            DefaultCrossDomainEngine(
                resolver=object(), composer=FakeComposer(_composition())
            )
