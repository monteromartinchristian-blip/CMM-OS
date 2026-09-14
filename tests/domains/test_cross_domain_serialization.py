"""Phase 10.9 – Round-trip serialization tests for Cross-Domain Engine contracts."""

from __future__ import annotations

import json
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
    CrossDomainOperationResult,
    CrossDomainPlanResult,
    CrossDomainPolicy,
    CrossDomainQuestion,
    CrossDomainRequest,
    CrossDomainResult,
    CrossDomainWorkflowResult,
)
from cmm.domains.errors import CrossDomainSerializationError

NOW = datetime(2026, 7, 31, tzinfo=timezone.utc)


def _roundtrip(cls, instance) -> None:
    data = instance.to_dict()
    json.dumps(data)  # must be JSON-safe
    rebuilt = cls.from_dict(data)
    assert rebuilt == instance
    assert rebuilt.to_dict() == data


def _finding(identifier: str = "f1") -> CrossDomainFinding:
    return CrossDomainFinding(
        identifier=identifier,
        value="v",
        source_domains=("domain:health",),
        provenance=("p",),
    )


class TestRoundTrips:
    def test_request(self) -> None:
        req = CrossDomainRequest(
            id="r1",
            objective="obj",
            primary_domain="domain:health",
            supporting_domains=("domain:general",),
            resources=("res1",),
            metadata={"k": "v"},
        )
        _roundtrip(CrossDomainRequest, req)

    def test_policy(self) -> None:
        _roundtrip(CrossDomainPolicy, CrossDomainPolicy(required_ports=("planner",)))

    def test_question(self) -> None:
        q = CrossDomainQuestion(
            id="q1",
            subject="s",
            requested_information="ri",
            target_entity="e1",
            time_scope="2026",
            requesting_domains=("domain:health",),
            answered=True,
            answer="a",
            provenance=("p1", "p2"),
        )
        _roundtrip(CrossDomainQuestion, q)

    def test_finding(self) -> None:
        f = CrossDomainFinding(
            identifier="f1",
            value={"a": [1, 2, "x"]},
            source_domains=("domain:health", "domain:general"),
            provenance=("p1", "p2"),
            private=True,
            transferable=False,
        )
        _roundtrip(CrossDomainFinding, f)

    def test_context_transfer(self) -> None:
        t = CrossDomainContextTransfer(
            source_domain="domain:health",
            target_domain="domain:general",
            kind="entity",
            identifier="e1",
            value={"a": [1, 2, "x"]},
            reason="r",
            iteration=2,
            provenance=("p1", "p2"),
        )
        _roundtrip(CrossDomainContextTransfer, t)

    def test_dependency(self) -> None:
        d = CrossDomainDependency(
            source_domain="domain:health",
            target_domain="domain:general",
            kind="requires",
            description="d",
            blocking=True,
            satisfied=False,
            provenance=("p1", "p2"),
        )
        _roundtrip(CrossDomainDependency, d)

    def test_contradiction(self) -> None:
        c = CrossDomainContradiction(
            id="c1",
            domains=("domain:health", "domain:general"),
            subject="s",
            statements=("a", "b"),
            severity="high",
            resolved=True,
            resolution="r",
            requires_review=True,
            provenance=("p1", "p2"),
        )
        _roundtrip(CrossDomainContradiction, c)

    def test_gap(self) -> None:
        g = CrossDomainGap(
            code="g1",
            domain_id="domain:health",
            description="d",
            required_information=("x",),
            blocking=True,
            recoverable=False,
            provenance=("p1",),
        )
        _roundtrip(CrossDomainGap, g)

    def test_decision(self) -> None:
        d = CrossDomainDecision(
            code="DOMAIN_SELECTED",
            stage="domain_execution",
            domain_id="domain:health",
            action="select",
            reason="why",
            blocking=True,
            iteration=3,
        )
        _roundtrip(CrossDomainDecision, d)

    def test_domain_result(self) -> None:
        q = CrossDomainQuestion(
            id="q1", subject="s", requested_information="ri", provenance=("p",)
        )
        r = CrossDomainDomainResult(
            domain_id="domain:health",
            status="completed",
            findings=(_finding(),),
            questions=(q,),
            recommendations=("rec",),
            operations=("op1",),
            workflow_requests=("wf1",),
            entities=("e1",),
            timelines=("t1",),
            confidence=0.7,
            external_calls_used=2,
            estimated_cost=1.25,
        )
        _roundtrip(CrossDomainDomainResult, r)

    def test_plan_result(self) -> None:
        p = CrossDomainPlanResult(
            status="completed",
            domain_order=("domain:health", "domain:general"),
            parallel_groups=(("domain:health",), ("domain:general",)),
            required_ports=("planner",),
            operation_requests=("op1",),
            workflow_requests=("wf1",),
            domain_modes={"domain:health": "agent", "domain:general": "cognitive"},
            external_calls_used=2,
            estimated_cost=1.25,
        )
        _roundtrip(CrossDomainPlanResult, p)

    def test_workflow_result(self) -> None:
        w = CrossDomainWorkflowResult(
            status="completed",
            workflow_ids=("wf1",),
            findings=(_finding(),),
            external_calls_used=2,
            estimated_cost=1.5,
        )
        _roundtrip(CrossDomainWorkflowResult, w)

    def test_operation_result(self) -> None:
        o = CrossDomainOperationResult(
            status="completed",
            operation_ids=("op1",),
            findings=(_finding(),),
            external_calls_used=1,
            estimated_cost=0.5,
        )
        _roundtrip(CrossDomainOperationResult, o)

    def test_knowledge_result(self) -> None:
        k = CrossDomainKnowledgeResult(
            status="completed",
            findings=(_finding(),),
            entities=("e1",),
            timelines=("t1",),
            external_calls_used=1,
        )
        _roundtrip(CrossDomainKnowledgeResult, k)

    def test_limits(self) -> None:
        limits = CrossDomainLimits(domains_used=2, reached_limits=("cost",))
        _roundtrip(CrossDomainLimits, limits)

    def test_context_snapshot(self) -> None:
        snap = CrossDomainContextSnapshot(
            request_id="r1",
            composition_id="c1",
            active_domains=("domain:health",),
            shared_findings=(_finding(),),
            started_at=NOW,
        )
        _roundtrip(CrossDomainContextSnapshot, snap)

    def test_result(self) -> None:
        res = CrossDomainResult(
            id="res1",
            status="completed",
            objective="obj",
            request_id="r1",
            composition_id="c1",
            shared_findings=(_finding(),),
            recommendations=("rec1",),
            trace_id="t1",
            started_at=NOW,
            completed_at=NOW,
        )
        _roundtrip(CrossDomainResult, res)


class TestUnknownFieldsRejected:
    def test_request_rejects_unknown(self) -> None:
        with pytest.raises(CrossDomainSerializationError):
            CrossDomainRequest.from_dict({"bogus": 1})

    def test_policy_rejects_unknown(self) -> None:
        with pytest.raises(CrossDomainSerializationError):
            CrossDomainPolicy.from_dict({"bogus": 1})

    def test_result_rejects_unknown(self) -> None:
        with pytest.raises(CrossDomainSerializationError):
            CrossDomainResult.from_dict({"bogus": 1})


class TestNestedFieldPaths:
    def test_invalid_nested_dependency_reports_path(self) -> None:
        with pytest.raises(CrossDomainSerializationError) as excinfo:
            CrossDomainDomainResult.from_dict(
                {
                    "domain_id": "domain:health",
                    "status": "completed",
                    "dependencies": [{"source_domain": "domain:health"}],
                }
            )
        assert "description" in str(excinfo.value) or "kind" in str(excinfo.value)


class TestStrictDeserializationAllContracts:
    """Each public contract must raise CrossDomainSerializationError on type
    mismatches instead of silently coercing (str(...)/bool(...)/int(...))."""

    def test_request_integer_supplied_as_string_field(self) -> None:
        with pytest.raises(CrossDomainSerializationError):
            CrossDomainRequest.from_dict(
                {"id": "r1", "objective": 123, "primary_domain": "domain:health"}
            )

    def test_request_bool_supplied_as_integer_field(self) -> None:
        with pytest.raises(CrossDomainSerializationError):
            CrossDomainRequest.from_dict(
                {
                    "id": "r1",
                    "objective": "obj",
                    "primary_domain": "domain:health",
                    "maximum_domains": True,
                }
            )

    def test_request_mapping_supplied_as_id(self) -> None:
        with pytest.raises(CrossDomainSerializationError):
            CrossDomainRequest.from_dict(
                {"id": {"a": 1}, "objective": "obj", "primary_domain": "domain:health"}
            )

    def test_request_list_supplied_as_objective(self) -> None:
        with pytest.raises(CrossDomainSerializationError):
            CrossDomainRequest.from_dict(
                {"id": "r1", "objective": ["a"], "primary_domain": "domain:health"}
            )

    def test_request_mapping_supplied_as_primary_domain(self) -> None:
        with pytest.raises(CrossDomainSerializationError):
            CrossDomainRequest.from_dict(
                {"id": "r1", "objective": "obj", "primary_domain": {"slug": "health"}}
            )

    def test_question_string_supplied_as_bool_field(self) -> None:
        with pytest.raises(CrossDomainSerializationError):
            CrossDomainQuestion.from_dict(
                {
                    "id": "q1",
                    "subject": "s",
                    "requested_information": "ri",
                    "provenance": ["p"],
                    "answered": "true",
                }
            )

    def test_contradiction_numeric_enum_rejected(self) -> None:
        with pytest.raises(CrossDomainSerializationError):
            CrossDomainContradiction.from_dict(
                {
                    "id": "c1",
                    "domains": ["domain:health", "domain:general"],
                    "subject": "s",
                    "statements": ["a"],
                    "severity": 5,
                    "provenance": ["p"],
                }
            )

    def test_decision_numeric_enum_rejected_for_stage(self) -> None:
        with pytest.raises(CrossDomainSerializationError):
            CrossDomainDecision.from_dict({"code": "X", "stage": 1, "action": "a"})

    def test_dependency_bool_supplied_as_integer_field(self) -> None:
        with pytest.raises(CrossDomainSerializationError):
            CrossDomainDependency.from_dict(
                {
                    "source_domain": "domain:health",
                    "target_domain": "domain:general",
                    "kind": "requires",
                    "description": "d",
                    "provenance": ["p"],
                    "blocking": "yes",
                }
            )

    def test_context_snapshot_invalid_datetime_rejected(self) -> None:
        with pytest.raises(CrossDomainSerializationError):
            CrossDomainContextSnapshot.from_dict(
                {"request_id": "r1", "started_at": "not-a-datetime"}
            )

    def test_result_invalid_datetime_rejected(self) -> None:
        with pytest.raises(CrossDomainSerializationError):
            CrossDomainResult.from_dict(
                {
                    "id": "res1",
                    "status": "failed",
                    "objective": "obj",
                    "request_id": "r1",
                    "trace_id": "t1",
                    "started_at": "not-a-datetime",
                    "completed_at": NOW.isoformat(),
                }
            )

    def test_result_bool_supplied_as_status(self) -> None:
        with pytest.raises(CrossDomainSerializationError):
            CrossDomainResult.from_dict(
                {
                    "id": "res1",
                    "status": True,
                    "objective": "obj",
                    "request_id": "r1",
                    "trace_id": "t1",
                    "started_at": NOW.isoformat(),
                    "completed_at": NOW.isoformat(),
                }
            )

    def test_gap_list_supplied_as_domain_id(self) -> None:
        with pytest.raises(CrossDomainSerializationError):
            CrossDomainGap.from_dict(
                {"code": "g1", "domain_id": ["domain:health"], "description": "d"}
            )

    def test_finding_integer_supplied_as_identifier(self) -> None:
        with pytest.raises(CrossDomainSerializationError):
            CrossDomainFinding.from_dict(
                {
                    "identifier": 1,
                    "value": "v",
                    "source_domains": ["domain:health"],
                    "provenance": ["p"],
                }
            )

    def test_plan_usage_fields_are_strict(self) -> None:
        with pytest.raises(CrossDomainSerializationError):
            CrossDomainPlanResult.from_dict(
                {"status": "completed", "external_calls_used": True}
            )
        with pytest.raises(CrossDomainSerializationError):
            CrossDomainPlanResult.from_dict(
                {"status": "completed", "estimated_cost": "1.0"}
            )

    def test_domain_result_usage_fields_are_strict(self) -> None:
        with pytest.raises(CrossDomainSerializationError):
            CrossDomainDomainResult.from_dict(
                {
                    "domain_id": "domain:health",
                    "status": "completed",
                    "external_calls_used": -1,
                }
            )
        with pytest.raises(CrossDomainSerializationError):
            CrossDomainDomainResult.from_dict(
                {
                    "domain_id": "domain:health",
                    "status": "completed",
                    "estimated_cost": float("inf"),
                }
            )

    def test_plan_and_domain_result_usage_unknown_fields_rejected(self) -> None:
        with pytest.raises(CrossDomainSerializationError):
            CrossDomainPlanResult.from_dict(
                {"status": "completed", "unexpected_usage": 1}
            )
        with pytest.raises(CrossDomainSerializationError):
            CrossDomainDomainResult.from_dict(
                {
                    "domain_id": "domain:health",
                    "status": "completed",
                    "unexpected_usage": 1,
                }
            )
