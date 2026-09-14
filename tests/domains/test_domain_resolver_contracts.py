"""Tests for Phase 10.7 resolver contracts — invariants, validation, and deep freeze."""

from __future__ import annotations

import json

import pytest

from cmm.domains.enums import DomainResolutionStatus
from cmm.domains.errors import (
    DomainContractValidationError,
    DomainResolutionSerializationError,
    DomainSerializationError,
)
from cmm.domains.identifiers import DomainId
from cmm.domains.resolver_contracts import (
    DomainCandidateScore,
    DomainResolutionReason,
    DomainResolutionResult,
    DomainScoringPolicy,
)

# ── Helpers ──────────────────────────────────────────────────────────────────


def make_domain(slug: str) -> DomainId:
    return DomainId(slug=slug)


def make_reason(
    code: str = "TEST_REASON",
    message: str = "test",
    **kwargs: object,
) -> DomainResolutionReason:
    return DomainResolutionReason(code=code, message=message, **kwargs)


# ═══════════════════════════════════════════════════════════════════════════
# DomainScoringPolicy
# ═══════════════════════════════════════════════════════════════════════════


class TestDomainScoringPolicy:
    def test_defaults_are_valid(self) -> None:
        policy = DomainScoringPolicy()
        assert policy.explicit_weight == 100.0
        assert policy.high_impact_minimum_confidence == 0.80

    def test_negative_weight_rejected(self) -> None:
        with pytest.raises(DomainContractValidationError, match="non-negative"):
            DomainScoringPolicy(explicit_weight=-1.0)

    def test_bool_weight_rejected(self) -> None:
        with pytest.raises(DomainContractValidationError, match="not a boolean"):
            DomainScoringPolicy(explicit_weight=True)  # type: ignore[arg-type]

    def test_nan_weight_rejected(self) -> None:
        with pytest.raises(DomainContractValidationError, match="finite"):
            DomainScoringPolicy(explicit_weight=float("nan"))

    def test_inf_weight_rejected(self) -> None:
        with pytest.raises(DomainContractValidationError, match="finite"):
            DomainScoringPolicy(explicit_weight=float("inf"))

    def test_confidence_out_of_range_rejected(self) -> None:
        with pytest.raises(DomainContractValidationError, match="between 0.0 and 1.0"):
            DomainScoringPolicy(default_minimum_confidence=1.5)

    def test_confidence_negative_rejected(self) -> None:
        with pytest.raises(DomainContractValidationError, match="between 0.0 and 1.0"):
            DomainScoringPolicy(default_minimum_confidence=-0.1)

    def test_confidence_bool_rejected(self) -> None:
        with pytest.raises(DomainContractValidationError, match="not a boolean"):
            DomainScoringPolicy(default_minimum_confidence=True)  # type: ignore[arg-type]

    def test_high_impact_below_default_rejected(self) -> None:
        with pytest.raises(DomainContractValidationError, match=">="):
            DomainScoringPolicy(
                default_minimum_confidence=0.8, high_impact_minimum_confidence=0.5
            )

    def test_confidence_scale_zero_rejected(self) -> None:
        with pytest.raises(DomainContractValidationError, match="positive"):
            DomainScoringPolicy(confidence_scale=0.0)

    def test_max_supporting_bool_rejected(self) -> None:
        with pytest.raises(DomainContractValidationError, match="integer"):
            DomainScoringPolicy(max_supporting_domains=True)  # type: ignore[arg-type]

    def test_max_supporting_negative_rejected(self) -> None:
        with pytest.raises(DomainContractValidationError, match="non-negative"):
            DomainScoringPolicy(max_supporting_domains=-1)

    def test_round_trip(self) -> None:
        policy = DomainScoringPolicy(explicit_weight=50.0)
        data = policy.to_dict()
        reloaded = DomainScoringPolicy.from_dict(data)
        assert reloaded.explicit_weight == 50.0
        assert reloaded.to_dict() == data

    def test_from_dict_unknown_fields_rejected(self) -> None:
        with pytest.raises(DomainSerializationError, match="unknown"):
            DomainScoringPolicy.from_dict({"explicit_weight": 50, "bogus": 1})

    def test_json_dumps(self) -> None:
        policy = DomainScoringPolicy()
        json.dumps(policy.to_dict())


# ═══════════════════════════════════════════════════════════════════════════
# DomainResolutionReason
# ═══════════════════════════════════════════════════════════════════════════


class TestDomainResolutionReason:
    def test_valid_reason(self) -> None:
        r = DomainResolutionReason(code="TEST", message="test")
        assert r.code == "TEST"
        assert r.blocking is False
        assert r.contribution is None

    def test_code_empty_rejected(self) -> None:
        with pytest.raises(DomainContractValidationError, match="non-empty"):
            DomainResolutionReason(code="", message="x")

    def test_message_empty_rejected(self) -> None:
        with pytest.raises(DomainContractValidationError, match="non-empty"):
            DomainResolutionReason(code="X", message="")

    def test_contribution_nan_rejected(self) -> None:
        with pytest.raises(DomainContractValidationError, match="finite"):
            DomainResolutionReason(code="X", message="x", contribution=float("nan"))

    def test_contribution_inf_rejected(self) -> None:
        with pytest.raises(DomainContractValidationError, match="finite"):
            DomainResolutionReason(code="X", message="x", contribution=float("inf"))

    def test_contribution_bool_rejected(self) -> None:
        with pytest.raises(DomainContractValidationError, match="not a boolean"):
            DomainResolutionReason(code="X", message="x", contribution=True)  # type: ignore[arg-type]

    def test_contribution_negative_allowed(self) -> None:
        r = DomainResolutionReason(code="X", message="x", contribution=-5.0)
        assert r.contribution == -5.0

    def test_contribution_zero_allowed(self) -> None:
        r = DomainResolutionReason(code="X", message="x", contribution=0.0)
        assert r.contribution == 0.0

    def test_blocking_strict_bool(self) -> None:
        r = DomainResolutionReason(code="X", message="x", blocking=True)
        assert r.blocking is True

    def test_with_domain_id(self) -> None:
        d = make_domain("health")
        r = DomainResolutionReason(code="X", message="x", domain_id=d)
        assert r.domain_id == d

    def test_domain_id_coerced_from_str(self) -> None:
        r = DomainResolutionReason(code="X", message="x", domain_id="domain:health")
        assert r.domain_id == make_domain("health")

    def test_credential_keys_rejected_in_metadata(self) -> None:
        with pytest.raises(DomainContractValidationError, match="password"):
            DomainResolutionReason(code="X", message="x", metadata={"password": "x"})

    def test_round_trip(self) -> None:
        r = DomainResolutionReason(
            code="TEST", message="hello", contribution=3.0, blocking=True
        )
        data = r.to_dict()
        reloaded = DomainResolutionReason.from_dict(data)
        assert reloaded.code == "TEST"
        assert reloaded.contribution == 3.0
        assert reloaded.blocking is True

    def test_json_dumps(self) -> None:
        r = DomainResolutionReason(code="TEST", message="hello")
        json.dumps(r.to_dict())

    def test_deep_freeze(self) -> None:
        r = DomainResolutionReason(code="X", message="x", metadata={"a": {"b": 1}})
        with pytest.raises(TypeError):
            r.metadata["c"] = 2  # type: ignore[index]


# ═══════════════════════════════════════════════════════════════════════════
# DomainCandidateScore
# ═══════════════════════════════════════════════════════════════════════════


class TestDomainCandidateScore:
    def test_valid_candidate(self) -> None:
        cs = DomainCandidateScore(
            domain_id=make_domain("health"),
            score=50.0,
            confidence=0.8,
            eligible=True,
            rejected=False,
        )
        assert cs.eligible is True
        assert cs.rejected is False

    def test_eligible_and_rejected_both_true_rejected(self) -> None:
        with pytest.raises(DomainContractValidationError, match="cannot both be True"):
            DomainCandidateScore(
                domain_id=make_domain("health"),
                score=50.0,
                confidence=0.8,
                eligible=True,
                rejected=True,
            )

    def test_rejected_without_codes_rejected(self) -> None:
        with pytest.raises(DomainContractValidationError, match="rejection code"):
            DomainCandidateScore(
                domain_id=make_domain("health"),
                score=0.0,
                confidence=0.0,
                eligible=False,
                rejected=True,
            )

    def test_rejected_with_codes_valid(self) -> None:
        cs = DomainCandidateScore(
            domain_id=make_domain("health"),
            score=0.0,
            confidence=0.0,
            eligible=False,
            rejected=True,
            rejection_codes=("DENIED",),
        )
        assert cs.rejection_codes == ("DENIED",)

    def test_score_finite_required(self) -> None:
        with pytest.raises(DomainContractValidationError, match="finite"):
            DomainCandidateScore(
                domain_id=make_domain("health"),
                score=float("nan"),
                confidence=0.5,
                eligible=True,
                rejected=False,
            )

    def test_confidence_bool_rejected(self) -> None:
        with pytest.raises(DomainContractValidationError, match="not a boolean"):
            DomainCandidateScore(
                domain_id=make_domain("health"),
                score=10.0,
                confidence=True,  # type: ignore[arg-type]
                eligible=True,
                rejected=False,
            )

    def test_confidence_range(self) -> None:
        with pytest.raises(DomainContractValidationError, match="between 0.0 and 1.0"):
            DomainCandidateScore(
                domain_id=make_domain("health"),
                score=10.0,
                confidence=2.0,
                eligible=True,
                rejected=False,
            )

    def test_not_eligible_not_rejected_ok(self) -> None:
        cs = DomainCandidateScore(
            domain_id=make_domain("health"),
            score=0.0,
            confidence=0.0,
            eligible=False,
            rejected=False,
        )
        assert cs.eligible is False
        assert cs.rejected is False

    def test_reasons_deduplicated(self) -> None:
        r = make_reason(code="DUP", message="dup")
        cs = DomainCandidateScore(
            domain_id=make_domain("health"),
            score=10.0,
            confidence=0.5,
            eligible=True,
            rejected=False,
            reasons=(r, r),  # duplicate
        )
        assert len(cs.reasons) == 1

    def test_round_trip(self) -> None:
        cs = DomainCandidateScore(
            domain_id=make_domain("health"),
            score=50.0,
            confidence=0.8,
            eligible=True,
            rejected=False,
            reasons=(make_reason("X", "y"),),
            matched_signal_kinds=("explicit",),
        )
        data = cs.to_dict()
        reloaded = DomainCandidateScore.from_dict(data)
        assert reloaded.score == 50.0
        assert len(reloaded.reasons) == 1
        assert reloaded.matched_signal_kinds == ("explicit",)

    def test_json_dumps(self) -> None:
        cs = DomainCandidateScore(
            domain_id=make_domain("health"),
            score=50.0,
            confidence=0.8,
            eligible=True,
            rejected=False,
        )
        json.dumps(cs.to_dict())


# ═══════════════════════════════════════════════════════════════════════════
# DomainResolutionResult — status invariants
# ═══════════════════════════════════════════════════════════════════════════


class TestDomainResolutionResultResolved:
    def test_resolved_requires_primary(self) -> None:
        with pytest.raises(DomainContractValidationError, match="primary_domain"):
            DomainResolutionResult(
                id="r1",
                context_id="c1",
                status=DomainResolutionStatus.RESOLVED,
            )

    def test_resolved_primary_not_in_rejected(self) -> None:
        d = make_domain("health")
        with pytest.raises(DomainContractValidationError, match="rejected_domains"):
            DomainResolutionResult(
                id="r1",
                context_id="c1",
                status=DomainResolutionStatus.RESOLVED,
                primary_domain=d,
                rejected_domains=(d,),
            )

    def test_resolved_primary_not_in_ambiguous(self) -> None:
        d = make_domain("health")
        with pytest.raises(DomainContractValidationError, match="ambiguous_domains"):
            DomainResolutionResult(
                id="r1",
                context_id="c1",
                status=DomainResolutionStatus.RESOLVED,
                primary_domain=d,
                ambiguous_domains=(d,),
            )

    def test_resolved_no_clarification(self) -> None:
        with pytest.raises(
            DomainContractValidationError, match="requires_clarification"
        ):
            DomainResolutionResult(
                id="r1",
                context_id="c1",
                status=DomainResolutionStatus.RESOLVED,
                primary_domain=make_domain("health"),
                requires_clarification=True,
            )

    def test_resolved_no_question(self) -> None:
        with pytest.raises(DomainContractValidationError, match="recommended_question"):
            DomainResolutionResult(
                id="r1",
                context_id="c1",
                status=DomainResolutionStatus.RESOLVED,
                primary_domain=make_domain("health"),
                recommended_question="q?",
            )

    def test_resolved_valid(self) -> None:
        r = DomainResolutionResult(
            id="r1",
            context_id="c1",
            status=DomainResolutionStatus.RESOLVED,
            primary_domain=make_domain("health"),
        )
        assert r.status == DomainResolutionStatus.RESOLVED


class TestDomainResolutionResultAmbiguous:
    def test_ambiguous_requires_two(self) -> None:
        with pytest.raises(DomainContractValidationError, match="at least 2"):
            DomainResolutionResult(
                id="r1",
                context_id="c1",
                status=DomainResolutionStatus.AMBIGUOUS,
                ambiguous_domains=(make_domain("health"),),
                recommended_question="?",
                requires_clarification=True,
            )

    def test_ambiguous_requires_clarification(self) -> None:
        with pytest.raises(
            DomainContractValidationError, match="requires_clarification"
        ):
            DomainResolutionResult(
                id="r1",
                context_id="c1",
                status=DomainResolutionStatus.AMBIGUOUS,
                ambiguous_domains=(make_domain("health"), make_domain("university")),
                recommended_question="?",
            )

    def test_ambiguous_requires_question(self) -> None:
        with pytest.raises(DomainContractValidationError, match="recommended_question"):
            DomainResolutionResult(
                id="r1",
                context_id="c1",
                status=DomainResolutionStatus.AMBIGUOUS,
                ambiguous_domains=(make_domain("health"), make_domain("university")),
                requires_clarification=True,
            )

    def test_ambiguous_valid(self) -> None:
        r = DomainResolutionResult(
            id="r1",
            context_id="c1",
            status=DomainResolutionStatus.AMBIGUOUS,
            ambiguous_domains=(make_domain("health"), make_domain("university")),
            requires_clarification=True,
            recommended_question="Which one?",
        )
        assert r.status == DomainResolutionStatus.AMBIGUOUS


class TestDomainResolutionResultUnsupported:
    def test_unsupported_no_primary(self) -> None:
        with pytest.raises(DomainContractValidationError, match="primary_domain"):
            DomainResolutionResult(
                id="r1",
                context_id="c1",
                status=DomainResolutionStatus.UNSUPPORTED,
                primary_domain=make_domain("health"),
            )

    def test_unsupported_zero_confidence(self) -> None:
        with pytest.raises(DomainContractValidationError, match="confidence"):
            DomainResolutionResult(
                id="r1",
                context_id="c1",
                status=DomainResolutionStatus.UNSUPPORTED,
                confidence=0.5,
            )

    def test_unsupported_valid(self) -> None:
        r = DomainResolutionResult(
            id="r1",
            context_id="c1",
            status=DomainResolutionStatus.UNSUPPORTED,
        )
        assert r.confidence == 0.0
        assert r.primary_domain is None


class TestDomainResolutionResultBlocked:
    def test_blocked_no_primary(self) -> None:
        with pytest.raises(DomainContractValidationError, match="primary_domain"):
            DomainResolutionResult(
                id="r1",
                context_id="c1",
                status=DomainResolutionStatus.BLOCKED,
                primary_domain=make_domain("health"),
                rejected_domains=(make_domain("health"),),
                reasons=(make_reason(code="X", message="x", blocking=True),),
            )

    def test_blocked_requires_rejected(self) -> None:
        with pytest.raises(DomainContractValidationError, match="rejected domain"):
            DomainResolutionResult(
                id="r1",
                context_id="c1",
                status=DomainResolutionStatus.BLOCKED,
            )

    def test_blocked_requires_blocking_reason(self) -> None:
        with pytest.raises(DomainContractValidationError, match="blocking reason"):
            DomainResolutionResult(
                id="r1",
                context_id="c1",
                status=DomainResolutionStatus.BLOCKED,
                rejected_domains=(make_domain("health"),),
            )

    def test_blocked_valid(self) -> None:
        r = DomainResolutionResult(
            id="r1",
            context_id="c1",
            status=DomainResolutionStatus.BLOCKED,
            rejected_domains=(make_domain("health"),),
            reasons=(make_reason(code="X", message="blocked", blocking=True),),
        )
        assert r.status == DomainResolutionStatus.BLOCKED


class TestDomainResolutionResultFailed:
    def test_failed_valid(self) -> None:
        r = DomainResolutionResult(
            id="r1",
            context_id="c1",
            status=DomainResolutionStatus.FAILED,
        )
        assert r.status == DomainResolutionStatus.FAILED


class TestDomainResolutionResultSerialization:
    def test_round_trip_resolved(self) -> None:
        r = DomainResolutionResult(
            id="r1",
            context_id="c1",
            status=DomainResolutionStatus.RESOLVED,
            primary_domain=make_domain("health"),
            supporting_domains=(make_domain("reflection"),),
            confidence=0.9,
            reasons=(make_reason("X", "y", contribution=5.0),),
        )
        data = r.to_dict()
        reloaded = DomainResolutionResult.from_dict(data)
        assert reloaded.id == "r1"
        assert reloaded.context_id == "c1"
        assert reloaded.primary_domain == make_domain("health")
        assert reloaded.supporting_domains == (make_domain("reflection"),)

    def test_unknown_fields_rejected(self) -> None:
        data = {
            "id": "r1",
            "context_id": "c1",
            "status": "resolved",
            "primary_domain": "domain:health",
            "resolved_at": "2025-01-01T00:00:00+00:00",
            "bogus": True,
        }
        with pytest.raises(DomainSerializationError, match="unknown"):
            DomainResolutionResult.from_dict(data)

    def test_datetime_timezone_aware(self) -> None:
        r = DomainResolutionResult(
            id="r1",
            context_id="c1",
            status=DomainResolutionStatus.RESOLVED,
            primary_domain=make_domain("health"),
        )
        assert r.resolved_at.tzinfo is not None

    def test_json_dumps(self) -> None:
        r = DomainResolutionResult(
            id="r1",
            context_id="c1",
            status=DomainResolutionStatus.RESOLVED,
            primary_domain=make_domain("health"),
        )
        json.dumps(r.to_dict())

    def test_round_trip_ambiguous(self) -> None:
        r = DomainResolutionResult(
            id="r1",
            context_id="c1",
            status=DomainResolutionStatus.AMBIGUOUS,
            ambiguous_domains=(make_domain("health"), make_domain("university")),
            requires_clarification=True,
            recommended_question="Which domain?",
        )
        data = r.to_dict()
        reloaded = DomainResolutionResult.from_dict(data)
        assert reloaded.status == DomainResolutionStatus.AMBIGUOUS

    def test_naive_datetime_from_string_rejected(self) -> None:
        data = {
            "id": "r1",
            "context_id": "c1",
            "status": "resolved",
            "primary_domain": "domain:health",
            "resolved_at": "2025-01-01T00:00:00",
        }
        with pytest.raises(DomainResolutionSerializationError, match="timezone-aware"):
            DomainResolutionResult.from_dict(data)
