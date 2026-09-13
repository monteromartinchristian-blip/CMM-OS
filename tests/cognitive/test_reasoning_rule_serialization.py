from __future__ import annotations

import json
from datetime import datetime, timezone

import pytest

from cmm.cognitive import (
    AuthoritativeSourceClaim,
    ReasoningAuthorityContext,
    ReasoningFinding,
    ReasoningRuleContext,
    ReasoningRuleDefinition,
    ReasoningRuleResult,
    ReasoningRuleSerializationError,
    ResourceProvenance,
    ResourceSourceKind,
)

NOW = datetime(2026, 8, 1, tzinfo=timezone.utc)


def test_definition_round_trip_is_exact_and_detached() -> None:
    original = ReasoningRuleDefinition(
        id="global.rule",
        name="GlobalRule",
        version="1.2.10",
        scope="global",
        category="epistemic",
        status="enabled",
        priority=20,
        risk_level="low",
        metadata={"nested": [1, {"x": True}]},
    )
    payload = original.to_dict()
    assert json.loads(json.dumps(payload)) == payload
    restored = ReasoningRuleDefinition.from_dict(payload)
    assert restored == original
    payload["metadata"]["nested"].append(3)
    assert original.metadata["nested"] == (1, {"x": True})


def test_context_and_result_round_trip_nested_contracts() -> None:
    context = ReasoningRuleContext(
        reasoning_id="r-1",
        gaps=(
            {
                "code": "MISSING",
                "message": "Missing evidence.",
                "severity": "warning",
                "rule_id": "global.rule",
            },
        ),
        timestamp=NOW,
    )
    result = ReasoningRuleResult(
        rule_id="global.rule",
        rule_name="GlobalRule",
        rule_version="1.2.10",
        status="applied",
        findings=(
            ReasoningFinding(
                code="FOUND",
                message="Found evidence.",
                severity="info",
                rule_id="global.rule",
            ),
        ),
        gaps=context.gaps,
        started_at=NOW,
        completed_at=NOW,
    )
    assert ReasoningRuleContext.from_dict(context.to_dict()) == context
    assert ReasoningRuleResult.from_dict(result.to_dict()) == result


def _authoritative_claim() -> AuthoritativeSourceClaim:
    return AuthoritativeSourceClaim(
        claim_id="clinical_status",
        source_domain="domain:health",
        purpose="diagnostic-status-review",
        provenance=ResourceProvenance(
            source_type=ResourceSourceKind.UPLOADED_FILE,
            source_id="clinical-record:1",
        ),
    )


def _trusted_authority() -> ReasoningAuthorityContext:
    return ReasoningAuthorityContext(
        actor_id="actor-1",
        session_id="session-1",
        source_domain="domain:health",
        target_domain="domain:neurodivergence",
        resource_ids=("clinical_status",),
        purpose="diagnostic-status-review",
        permission_decision_id="permission-gate-decision-1",
        permission_outcome="approval_consumed",
        approval_consumed=True,
        authoritative_claims=(_authoritative_claim(),),
    )


def test_authority_context_is_runtime_only_and_stripped_by_serialization() -> None:
    trusted = ReasoningRuleContext(
        reasoning_id="r-1",
        timestamp=NOW,
        authority_context=_trusted_authority(),
    )
    payload = trusted.to_dict()
    assert "authority_context" not in payload
    assert "authoritative_claims" not in payload
    assert "authoritative_claim_ids" not in payload
    assert "clinical-record:1" not in json.dumps(payload)
    assert json.loads(json.dumps(payload)) == payload

    rehydrated = ReasoningRuleContext.from_dict(payload)
    assert rehydrated.authority_context is None
    assert rehydrated == ReasoningRuleContext(reasoning_id="r-1", timestamp=NOW)


def test_from_dict_rejects_caller_supplied_authority_context() -> None:
    with pytest.raises(ReasoningRuleSerializationError):
        ReasoningRuleContext.from_dict(
            {
                "reasoning_id": "r-1",
                "timestamp": NOW.isoformat(),
                "authority_context": {
                    "actor_id": "actor-1",
                    "session_id": "session-1",
                    "source_domain": "domain:health",
                    "target_domain": "domain:neurodivergence",
                    "resource_ids": ["clinical_status"],
                    "purpose": "diagnostic-status-review",
                    "permission_decision_id": "permission-gate-decision-1",
                    "permission_outcome": "approval_consumed",
                    "approval_consumed": True,
                },
            }
        )


def test_from_dict_rejects_caller_supplied_authoritative_claims() -> None:
    """A serialized provenance-bearing claim is still not authority."""
    source_claim = _authoritative_claim()
    with pytest.raises(ReasoningRuleSerializationError):
        ReasoningRuleContext.from_dict(
            {
                "reasoning_id": "r-1",
                "timestamp": NOW.isoformat(),
                "authoritative_claims": [
                    {
                        "claim_id": source_claim.claim_id,
                        "source_domain": source_claim.source_domain,
                        "purpose": source_claim.purpose,
                        "provenance": source_claim.provenance.to_dict(),
                    }
                ],
            }
        )
    with pytest.raises(ReasoningRuleSerializationError):
        ReasoningRuleContext.from_dict(
            {
                "reasoning_id": "r-1",
                "timestamp": NOW.isoformat(),
                "source_provenance": _authoritative_claim().provenance.to_dict(),
            }
        )


@pytest.mark.parametrize(
    ("contract", "payload"),
    [
        (ReasoningRuleDefinition, {"unexpected": True}),
        (ReasoningRuleContext, {"reasoning_id": "r", "timestamp": NOW.isoformat(), "x": 1}),
        (ReasoningRuleResult, {"rule_id": "x", "unknown": 1}),
    ],
)
def test_from_dict_rejects_unknown_and_missing_fields(contract: type, payload: dict) -> None:
    with pytest.raises(ReasoningRuleSerializationError):
        contract.from_dict(payload)
