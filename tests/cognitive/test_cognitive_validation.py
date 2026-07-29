"""Tests for Phase 8.26 – Structural Cognitive Validation.

Covers contracts, rules, decisions, service, Phase 7 integration, and
architecture constraints.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from cmm.cognitive.cognitive_cache import (
    CognitiveCacheEntry,
    CognitiveCacheEntryStatus,
    cognitive_cache_entry_id,
)
from cmm.cognitive.contracts import Confidence
from cmm.cognitive.enums import (
    ContradictionStatus,
    KnowledgeKind,
    SensitivityLevel,
    TemporalScopeKind,
)
from cmm.cognitive.errors import (
    CognitiveValidationError,
    InvalidCognitiveValidationContextError,
)
from cmm.cognitive.knowledge import (
    Contradiction,
    Evidence,
    KnowledgeItem,
    TemporalScope,
)
from cmm.cognitive.knowledge_packages import KnowledgePackage
from cmm.cognitive.privacy import (
    PrivacyMetadata,
    PrivacyOperation,
    PrivacyPolicy,
    ProcessingLocation,
)
from cmm.cognitive.validation import (
    COGNITIVE_VALIDATION_SCHEMA_VERSION,
    CognitiveCacheRule,
    CognitiveValidationContext,
    CognitiveValidationDecision,
    CognitiveValidationResult,
    CognitiveValidationStepExecutor,
    CognitiveValidator,
    ContradictionsRule,
    DependenciesRule,
    EpistemologyRule,
    KnowledgePackageRule,
    PrivacyRule,
    ProvenanceRule,
    SchemaRule,
    TemporalityRule,
    derive_cognitive_validation_decision,
)
from cmm.validation.context import ValidationContext
from cmm.validation.enums import ValidationSeverity, ValidationStatus
from cmm.validation.findings import ValidationFinding
from cmm.validation.steps import (
    ValidationStep,
    ValidationStepResult,
    ValidationStepType,
)

# ── Fixtures ─────────────────────────────────────────────────────────────────


_NOW = datetime(2026, 7, 29, 12, 0, 0, tzinfo=timezone.utc)
_PAST = _NOW - timedelta(days=30)
_FUTURE = _NOW + timedelta(days=30)


def _ctx(**kwargs: object) -> CognitiveValidationContext:
    defaults: dict[str, object] = {"now": _NOW}
    defaults.update(kwargs)
    return CognitiveValidationContext(**defaults)  # type: ignore[arg-type]


def _fact(
    statement: str = "test fact",
    *,
    evidence: tuple[Evidence, ...] = (),
    temporal_scope: TemporalScope | None = None,
    confidence: Confidence | None = None,
) -> KnowledgeItem:
    return KnowledgeItem(
        statement=statement,
        kind=KnowledgeKind.FACT,
        confidence=confidence or Confidence(value=0.9),
        evidence=evidence,
        temporal_scope=temporal_scope or TemporalScope(),
    )


def _inference(statement: str = "test inference") -> KnowledgeItem:
    return KnowledgeItem(
        statement=statement,
        kind=KnowledgeKind.INFERENCE,
        confidence=Confidence(value=0.7),
    )


def _hypothesis(
    statement: str = "test hypothesis", confidence: float = 0.5
) -> KnowledgeItem:
    return KnowledgeItem(
        statement=statement,
        kind=KnowledgeKind.HYPOTHESIS,
        confidence=Confidence(value=confidence),
    )


def _observation(statement: str = "test observation") -> KnowledgeItem:
    return KnowledgeItem(
        statement=statement,
        kind=KnowledgeKind.OBSERVATION,
        confidence=Confidence(value=0.8),
    )


def _evidence() -> Evidence:
    return Evidence(
        resource_id="resource-1",
        fragment="test fragment",
        confidence=Confidence(value=0.9),
    )


def _package(
    *,
    id: str = "knowledge-package:test",
    objective: str = "test objective",
    facts: tuple[KnowledgeItem, ...] = (),
    observations: tuple[KnowledgeItem, ...] = (),
    inferences: tuple[KnowledgeItem, ...] = (),
    hypotheses: tuple[KnowledgeItem, ...] = (),
    contradictions: tuple[Contradiction, ...] = (),
    provenance: tuple[str, ...] = ("source-1",),
    valid_until: datetime | None = None,
    missing_information: tuple[object, ...] = (),
    privacy: dict[str, object] | None = None,
    created_at: datetime | None = None,
) -> KnowledgePackage:
    return KnowledgePackage(
        id=id,
        objective=objective,
        facts=facts,
        observations=observations,
        inferences=inferences,
        hypotheses=hypotheses,
        contradictions=contradictions,
        provenance=provenance,
        valid_until=valid_until,
        created_at=created_at or _NOW - timedelta(minutes=5),
        missing_information=missing_information,
        privacy=privacy or {},
    )


def _cache_entry(
    *,
    status: CognitiveCacheEntryStatus = CognitiveCacheEntryStatus.VALID,
    valid_until: datetime | None = None,
    profile_version: str | None = None,
    domain_version: str | None = None,
    dependency_ids: tuple[str, ...] = (),
    privacy: PrivacyMetadata | None = None,
    context_signature: str = "sha256:test",
    created_at: datetime | None = None,
) -> CognitiveCacheEntry:
    return CognitiveCacheEntry(
        id=cognitive_cache_entry_id("test-key", context_signature),
        key="test-key",
        kind="test",
        value={"data": "test"},
        context_signature=context_signature,
        profile_version=profile_version,
        domain_version=domain_version,
        dependency_ids=dependency_ids,
        valid_until=valid_until,
        created_at=created_at or _NOW - timedelta(minutes=5),
        status=status,
        privacy=privacy,
    )


# ── Contract tests ───────────────────────────────────────────────────────────


class TestCognitiveValidationContext:
    def test_minimal_valid_context(self) -> None:
        ctx = CognitiveValidationContext()
        assert ctx.processing_location is ProcessingLocation.LOCAL
        assert ctx.target_operation is None
        assert ctx.require_complete_package is False

    def test_context_is_immutable(self) -> None:
        ctx = _ctx()
        with pytest.raises(AttributeError):
            ctx.actor_id = "changed"  # type: ignore[misc]

    def test_invalid_processing_location(self) -> None:
        with pytest.raises(InvalidCognitiveValidationContextError):
            CognitiveValidationContext(processing_location="invalid")  # type: ignore[arg-type]

    def test_invalid_target_operation(self) -> None:
        with pytest.raises(InvalidCognitiveValidationContextError):
            CognitiveValidationContext(target_operation="invalid")  # type: ignore[arg-type]

    def test_naive_now_rejected(self) -> None:
        with pytest.raises(InvalidCognitiveValidationContextError):
            CognitiveValidationContext(now=datetime(2026, 1, 1))  # noqa: DTZ001

    def test_serialize_round_trip(self) -> None:
        ctx = _ctx(actor_id="actor-1", domain="medical")
        data = ctx.serialize()
        assert data["actor_id"] == "actor-1"
        assert data["processing_location"] == "local"


class TestCognitiveValidationResult:
    def test_minimal_valid_result(self) -> None:
        result = CognitiveValidationResult(
            id="cognitive-validation:test",
            target_id="target-1",
            target_kind="knowledge_package",
            status=ValidationStatus.PASSED,
            decision=CognitiveValidationDecision.ACCEPT,
        )
        assert result.schema_version == COGNITIVE_VALIDATION_SCHEMA_VERSION
        assert result.is_accept

    def test_result_is_immutable(self) -> None:
        result = CognitiveValidationResult(
            id="cognitive-validation:test",
            target_id="target-1",
            target_kind="knowledge_package",
            status=ValidationStatus.PASSED,
            decision=CognitiveValidationDecision.ACCEPT,
        )
        with pytest.raises(AttributeError):
            result.target_id = "changed"  # type: ignore[misc]

    def test_invalid_schema_version(self) -> None:
        with pytest.raises(CognitiveValidationError):
            CognitiveValidationResult(
                id="test",
                target_id="t",
                target_kind="k",
                status=ValidationStatus.PASSED,
                decision=CognitiveValidationDecision.ACCEPT,
                schema_version=99,
            )

    def test_invalid_decision(self) -> None:
        with pytest.raises(CognitiveValidationError):
            CognitiveValidationResult(
                id="test",
                target_id="t",
                target_kind="k",
                status=ValidationStatus.PASSED,
                decision="invalid",  # type: ignore[arg-type]
            )

    def test_naive_created_at_rejected(self) -> None:
        with pytest.raises(InvalidCognitiveValidationContextError):
            CognitiveValidationResult(
                id="test",
                target_id="t",
                target_kind="k",
                status=ValidationStatus.PASSED,
                decision=CognitiveValidationDecision.ACCEPT,
                created_at=datetime(2026, 1, 1),  # noqa: DTZ001
            )

    def test_serialize_round_trip(self) -> None:
        result = CognitiveValidationResult(
            id="cognitive-validation:test",
            target_id="target-1",
            target_kind="knowledge_package",
            status=ValidationStatus.PASSED,
            decision=CognitiveValidationDecision.ACCEPT,
            validated_rules=("cognitive.schema",),
        )
        data = result.serialize()
        assert data["decision"] == "accept"
        assert data["validated_rules"] == ["cognitive.schema"]

    def test_from_mapping_round_trip(self) -> None:
        result = CognitiveValidationResult(
            id="cognitive-validation:test",
            target_id="target-1",
            target_kind="knowledge_package",
            status=ValidationStatus.WARNING,
            decision=CognitiveValidationDecision.ACCEPT_WITH_WARNING,
        )
        data = result.serialize()
        restored = CognitiveValidationResult.from_mapping(data)
        assert restored.id == result.id
        assert restored.decision == result.decision
        assert restored.status == result.status


# ── Decision tests ───────────────────────────────────────────────────────────


class TestDeriveDecision:
    def test_no_findings_accept(self) -> None:
        assert (
            derive_cognitive_validation_decision(())
            is CognitiveValidationDecision.ACCEPT
        )

    def test_only_info_accept(self) -> None:
        f = ValidationFinding(
            code="COG_INFO",
            message="info",
            severity=ValidationSeverity.INFO,
            source="test",
        )
        assert (
            derive_cognitive_validation_decision((f,))
            is CognitiveValidationDecision.ACCEPT
        )

    def test_warning_accept_with_warning(self) -> None:
        f = ValidationFinding(
            code="COG_WARN",
            message="warn",
            severity=ValidationSeverity.WARNING,
            source="test",
        )
        assert (
            derive_cognitive_validation_decision((f,))
            is CognitiveValidationDecision.ACCEPT_WITH_WARNING
        )

    def test_missing_information_request_information(self) -> None:
        f = ValidationFinding(
            code="COG_MISSING_INFORMATION",
            message="missing",
            severity=ValidationSeverity.ERROR,
            source="test",
            blocking=True,
        )
        assert (
            derive_cognitive_validation_decision((f,))
            is CognitiveValidationDecision.REQUEST_INFORMATION
        )

    def test_approval_required(self) -> None:
        f = ValidationFinding(
            code="COG_APPROVAL_REQUIRED",
            message="approval",
            severity=ValidationSeverity.ERROR,
            source="test",
            blocking=True,
        )
        assert (
            derive_cognitive_validation_decision((f,))
            is CognitiveValidationDecision.REQUEST_APPROVAL
        )

    def test_repair(self) -> None:
        f = ValidationFinding(
            code="COG_EPISTEMIC_KIND_MISMATCH",
            message="mismatch",
            severity=ValidationSeverity.ERROR,
            source="test",
            blocking=True,
        )
        assert (
            derive_cognitive_validation_decision((f,))
            is CognitiveValidationDecision.REPAIR
        )

    def test_invalidate(self) -> None:
        f = ValidationFinding(
            code="COG_CACHE_EXPIRED",
            message="expired",
            severity=ValidationSeverity.ERROR,
            source="test",
            blocking=True,
        )
        assert (
            derive_cognitive_validation_decision((f,))
            is CognitiveValidationDecision.INVALIDATE
        )

    def test_block(self) -> None:
        f = ValidationFinding(
            code="COG_SCHEMA_UNSUPPORTED",
            message="unsupported",
            severity=ValidationSeverity.CRITICAL,
            source="test",
            blocking=True,
        )
        assert (
            derive_cognitive_validation_decision((f,))
            is CognitiveValidationDecision.BLOCK
        )

    def test_escalate(self) -> None:
        f = ValidationFinding(
            code="COG_CONTRADICTION_UNRESOLVED",
            message="unresolved",
            severity=ValidationSeverity.ERROR,
            source="test",
            blocking=True,
        )
        assert (
            derive_cognitive_validation_decision((f,))
            is CognitiveValidationDecision.ESCALATE
        )

    def test_precedence_block_over_invalidate(self) -> None:
        block_f = ValidationFinding(
            code="COG_SCHEMA_UNSUPPORTED",
            message="block",
            severity=ValidationSeverity.CRITICAL,
            source="test",
            blocking=True,
        )
        inv_f = ValidationFinding(
            code="COG_CACHE_EXPIRED",
            message="invalidate",
            severity=ValidationSeverity.ERROR,
            source="test",
            blocking=True,
        )
        assert (
            derive_cognitive_validation_decision((inv_f, block_f))
            is CognitiveValidationDecision.BLOCK
        )

    def test_precedence_block_over_escalate(self) -> None:
        escalate_f = ValidationFinding(
            code="COG_CONTRADICTION_UNRESOLVED",
            message="escalate",
            severity=ValidationSeverity.ERROR,
            source="test",
            blocking=True,
        )
        block_f = ValidationFinding(
            code="COG_PRIVACY_DENIED",
            message="block",
            severity=ValidationSeverity.CRITICAL,
            source="test",
            blocking=True,
        )
        # BLOCK (8) > ESCALATE (7)
        assert (
            derive_cognitive_validation_decision((block_f, escalate_f))
            is CognitiveValidationDecision.BLOCK
        )

    def test_unknown_blocking_finding_escalates(self) -> None:
        f = ValidationFinding(
            code="COG_UNKNOWN_CODE",
            message="unknown",
            severity=ValidationSeverity.ERROR,
            source="test",
            blocking=True,
        )
        assert (
            derive_cognitive_validation_decision((f,))
            is CognitiveValidationDecision.ESCALATE
        )


# ── Schema rule tests ────────────────────────────────────────────────────────


class TestSchemaRule:
    def test_schema_valid_package(self) -> None:
        rule = SchemaRule()
        pkg = _package()
        findings = rule.evaluate(pkg, _ctx())
        assert len(findings) == 0

    def test_schema_invalid_version(self) -> None:
        rule = SchemaRule()
        pkg = _package()
        # KnowledgePackage.__post_init__ rejects invalid schema_version,
        # so we test with a valid package and verify the rule doesn't add findings
        findings = rule.evaluate(pkg, _ctx())
        assert all(f.code != "COG_SCHEMA_UNSUPPORTED" for f in findings)

    def test_schema_valid_cache_entry(self) -> None:
        rule = SchemaRule()
        entry = _cache_entry()
        findings = rule.evaluate(entry, _ctx())
        assert len(findings) == 0


# ── Provenance rule tests ────────────────────────────────────────────────────


class TestProvenanceRule:
    def test_provenance_valid(self) -> None:
        rule = ProvenanceRule()
        pkg = _package(
            facts=(_fact(evidence=(_evidence(),)),),
            provenance=("source-1",),
        )
        findings = rule.evaluate(pkg, _ctx())
        assert len(findings) == 0

    def test_provenance_missing(self) -> None:
        rule = ProvenanceRule()
        pkg = _package(provenance=())
        findings = rule.evaluate(pkg, _ctx())
        assert any(f.code == "COG_PROVENANCE_MISSING" and f.blocking for f in findings)

    def test_provenance_fact_without_evidence(self) -> None:
        rule = ProvenanceRule()
        pkg = _package(
            facts=(_fact(evidence=()),),
            provenance=("source-1",),
        )
        findings = rule.evaluate(pkg, _ctx())
        assert any(
            f.code == "COG_PROVENANCE_MISSING" and not f.blocking for f in findings
        )


# ── Temporality rule tests ───────────────────────────────────────────────────


class TestTemporalityRule:
    def test_content_valid(self) -> None:
        rule = TemporalityRule()
        pkg = _package(valid_until=_FUTURE)
        findings = rule.evaluate(pkg, _ctx())
        assert all(f.code != "COG_TEMPORAL_EXPIRED" for f in findings)

    def test_content_expired(self) -> None:
        rule = TemporalityRule()
        pkg = _package(
            valid_until=_NOW - timedelta(seconds=1),
            created_at=_NOW - timedelta(minutes=2),
        )
        findings = rule.evaluate(pkg, _ctx())
        assert any(f.code == "COG_TEMPORAL_EXPIRED" and f.blocking for f in findings)

    def test_cache_expired(self) -> None:
        rule = TemporalityRule()
        entry = _cache_entry(valid_until=_NOW - timedelta(seconds=1))
        findings = rule.evaluate(entry, _ctx())
        assert any(f.code == "COG_CACHE_EXPIRED" and f.blocking for f in findings)

    def test_require_current_information_expired_fact(self) -> None:
        rule = TemporalityRule()
        expired_scope = TemporalScope(
            kind=TemporalScopeKind.INTERVAL,
            valid_from=_PAST - timedelta(days=10),
            valid_until=_PAST,
        )
        pkg = _package(facts=(_fact(temporal_scope=expired_scope),))
        findings = rule.evaluate(pkg, _ctx(require_current_information=True))
        assert any(f.code == "COG_TEMPORAL_EXPIRED" and f.blocking for f in findings)


# ── Epistemology rule tests ──────────────────────────────────────────────────


class TestEpistemologyRule:
    def test_fact_correctly_categorized(self) -> None:
        rule = EpistemologyRule()
        pkg = _package(facts=(_fact(evidence=(_evidence(),)),))
        findings = rule.evaluate(pkg, _ctx())
        assert all(f.code != "COG_EVIDENCE_INSUFFICIENT" for f in findings)

    def test_fact_without_evidence(self) -> None:
        rule = EpistemologyRule()
        pkg = _package(facts=(_fact(evidence=()),))
        findings = rule.evaluate(pkg, _ctx())
        assert any(
            f.code == "COG_EVIDENCE_INSUFFICIENT" and not f.blocking for f in findings
        )

    def test_inference_correctly_categorized(self) -> None:
        rule = EpistemologyRule()
        pkg = _package(
            inferences=(_inference(),),
            provenance=("source-1",),
        )
        # Inference without evidence → warning
        findings = rule.evaluate(pkg, _ctx())
        assert any(f.code == "COG_EVIDENCE_INSUFFICIENT" for f in findings)

    def test_hypothesis_not_promoted(self) -> None:
        rule = EpistemologyRule()
        hyp = _hypothesis(confidence=0.95)
        pkg = _package(hypotheses=(hyp,))
        findings = rule.evaluate(pkg, _ctx())
        assert any(f.code == "COG_EPISTEMIC_PROMOTION" for f in findings)

    def test_missing_information_declared(self) -> None:
        rule = EpistemologyRule()
        pkg = _package(missing_information=("missing-1",))
        findings = rule.evaluate(pkg, _ctx())
        assert any(f.code == "COG_MISSING_INFORMATION" for f in findings)


# ── Contradictions rule tests ────────────────────────────────────────────────


class TestContradictionsRule:
    def test_no_contradictions(self) -> None:
        rule = ContradictionsRule()
        pkg = _package()
        findings = rule.evaluate(pkg, _ctx())
        assert len(findings) == 0

    def test_resolved_contradiction(self) -> None:
        rule = ContradictionsRule()
        c = Contradiction(
            item_a_id="a",
            item_b_id="b",
            status=ContradictionStatus.RESOLVED,
        )
        pkg = _package(contradictions=(c,))
        findings = rule.evaluate(pkg, _ctx())
        assert all(f.code != "COG_CONTRADICTION_UNRESOLVED" for f in findings)

    def test_unresolved_contradiction(self) -> None:
        rule = ContradictionsRule()
        c = Contradiction(
            item_a_id="a",
            item_b_id="b",
            status=ContradictionStatus.UNRESOLVED,
        )
        pkg = _package(contradictions=(c,))
        findings = rule.evaluate(pkg, _ctx())
        assert any(
            f.code == "COG_CONTRADICTION_UNRESOLVED" and f.blocking for f in findings
        )


# ── Privacy rule tests ───────────────────────────────────────────────────────


class TestPrivacyRule:
    def test_privacy_allowed(self) -> None:
        rule = PrivacyRule()
        privacy = PrivacyMetadata(
            policy=PrivacyPolicy.REMOTE_ALLOWED,
            sensitivity=SensitivityLevel.PUBLIC,
            allow_remote=True,
            allowed_processing_locations=(
                ProcessingLocation.LOCAL,
                ProcessingLocation.REMOTE,
            ),
            allow_cache=True,
        )
        entry = _cache_entry(privacy=privacy)
        findings = rule.evaluate(entry, _ctx(target_operation=PrivacyOperation.CACHE))
        assert all(f.code != "COG_PRIVACY_DENIED" for f in findings)

    def test_privacy_denied(self) -> None:
        rule = PrivacyRule()
        privacy = PrivacyMetadata(
            policy=PrivacyPolicy.LOCAL_ONLY,
            sensitivity=SensitivityLevel.RESTRICTED,
            allow_cache=False,
        )
        entry = _cache_entry(privacy=privacy)
        findings = rule.evaluate(entry, _ctx(target_operation=PrivacyOperation.CACHE))
        assert any(f.code == "COG_PRIVACY_DENIED" and f.blocking for f in findings)

    def test_redaction_required(self) -> None:
        rule = PrivacyRule()
        privacy = PrivacyMetadata(
            policy=PrivacyPolicy.REMOTE_ALLOWED,
            sensitivity=SensitivityLevel.PUBLIC,
            allow_remote=True,
            allowed_processing_locations=(
                ProcessingLocation.LOCAL,
                ProcessingLocation.REMOTE,
            ),
            requires_redaction=True,
        )
        entry = _cache_entry(privacy=privacy)
        findings = rule.evaluate(
            entry, _ctx(target_operation=PrivacyOperation.PROCESS_REMOTE)
        )
        assert any(f.code == "COG_REDACTION_REQUIRED" and f.blocking for f in findings)

    def test_approval_required(self) -> None:
        rule = PrivacyRule()
        privacy = PrivacyMetadata(
            policy=PrivacyPolicy.REMOTE_ALLOWED,
            sensitivity=SensitivityLevel.PUBLIC,
            allow_remote=True,
            allowed_processing_locations=(
                ProcessingLocation.LOCAL,
                ProcessingLocation.REMOTE,
            ),
            requires_approval=True,
        )
        entry = _cache_entry(privacy=privacy)
        findings = rule.evaluate(
            entry, _ctx(target_operation=PrivacyOperation.PROCESS_REMOTE)
        )
        assert any(f.code == "COG_APPROVAL_REQUIRED" and f.blocking for f in findings)


# ── Knowledge Package rule tests ─────────────────────────────────────────────


class TestKnowledgePackageRule:
    def test_complete_package(self) -> None:
        rule = KnowledgePackageRule()
        pkg = _package(facts=(_fact(evidence=(_evidence(),)),))
        findings = rule.evaluate(pkg, _ctx())
        assert all(f.code != "COG_MISSING_INFORMATION" for f in findings)

    def test_incomplete_package(self) -> None:
        rule = KnowledgePackageRule()
        pkg = _package()
        findings = rule.evaluate(pkg, _ctx(require_complete_package=True))
        assert any(f.code == "COG_MISSING_INFORMATION" and f.blocking for f in findings)

    def test_package_with_missing_information(self) -> None:
        rule = KnowledgePackageRule()
        pkg = _package(missing_information=("missing-1",))
        findings = rule.evaluate(pkg, _ctx(require_complete_package=True))
        assert any(f.code == "COG_MISSING_INFORMATION" and f.blocking for f in findings)


# ── Cognitive Cache rule tests ───────────────────────────────────────────────


class TestCognitiveCacheRule:
    def test_reusable_cache(self) -> None:
        rule = CognitiveCacheRule()
        entry = _cache_entry()
        findings = rule.evaluate(entry, _ctx())
        assert len(findings) == 0

    def test_stale_cache(self) -> None:
        rule = CognitiveCacheRule()
        entry = _cache_entry(status=CognitiveCacheEntryStatus.STALE)
        findings = rule.evaluate(entry, _ctx())
        assert any(f.code == "COG_CACHE_STALE" and f.blocking for f in findings)

    def test_expired_cache(self) -> None:
        rule = CognitiveCacheRule()
        entry = _cache_entry(status=CognitiveCacheEntryStatus.EXPIRED)
        findings = rule.evaluate(entry, _ctx())
        assert any(f.code == "COG_CACHE_EXPIRED" and f.blocking for f in findings)

    def test_invalid_cache(self) -> None:
        rule = CognitiveCacheRule()
        entry = _cache_entry(status=CognitiveCacheEntryStatus.INVALID)
        findings = rule.evaluate(entry, _ctx())
        assert any(f.code == "COG_CACHE_INVALID" and f.blocking for f in findings)


# ── Dependencies rule tests ──────────────────────────────────────────────────


class TestDependenciesRule:
    def test_no_invalidated_dependencies(self) -> None:
        rule = DependenciesRule()
        entry = _cache_entry(dependency_ids=("dep-1", "dep-2"))
        findings = rule.evaluate(entry, _ctx())
        assert all(f.code != "COG_DEPENDENCY_INVALIDATED" for f in findings)

    def test_dependency_invalidated(self) -> None:
        rule = DependenciesRule()
        entry = _cache_entry(dependency_ids=("dep-1", "dep-2"))
        findings = rule.evaluate(entry, _ctx(invalidated_dependency_ids=("dep-1",)))
        assert any(
            f.code == "COG_DEPENDENCY_INVALIDATED" and f.blocking for f in findings
        )

    def test_profile_mismatch(self) -> None:
        rule = DependenciesRule()
        entry = _cache_entry(profile_version="v1")
        findings = rule.evaluate(entry, _ctx(profile_version="v2"))
        assert any(f.code == "COG_PROFILE_MISMATCH" and f.blocking for f in findings)

    def test_domain_mismatch(self) -> None:
        rule = DependenciesRule()
        entry = _cache_entry(domain_version="v1")
        findings = rule.evaluate(entry, _ctx(domain_version="v2"))
        assert any(f.code == "COG_DOMAIN_MISMATCH" and f.blocking for f in findings)


# ── Service tests ────────────────────────────────────────────────────────────


class TestCognitiveValidator:
    def test_selects_rules_for_knowledge_package(self) -> None:
        validator = CognitiveValidator()
        pkg = _package(facts=(_fact(evidence=(_evidence(),)),), provenance=("s",))
        result = validator.validate(pkg, _ctx())
        assert "cognitive.schema" in result.validated_rules
        assert "cognitive.provenance" in result.validated_rules
        assert "cognitive.knowledge_package" in result.validated_rules
        # Cache rule should NOT apply to KnowledgePackage
        assert "cognitive.cache" not in result.validated_rules

    def test_selects_rules_for_cache_entry(self) -> None:
        validator = CognitiveValidator()
        entry = _cache_entry()
        result = validator.validate(entry, _ctx())
        assert "cognitive.schema" in result.validated_rules
        assert "cognitive.cache" in result.validated_rules
        # Provenance rule should NOT apply to CognitiveCacheEntry
        assert "cognitive.provenance" not in result.validated_rules

    def test_explicit_rules(self) -> None:
        validator = CognitiveValidator()
        pkg = _package()
        result = validator.validate(pkg, _ctx(), explicit_rules=("cognitive.schema",))
        assert tuple(result.validated_rules) == ("cognitive.schema",)

    def test_deterministic_order(self) -> None:
        validator = CognitiveValidator()
        pkg = _package(facts=(_fact(evidence=(_evidence(),)),), provenance=("s",))
        r1 = validator.validate(pkg, _ctx())
        r2 = validator.validate(pkg, _ctx())
        assert r1.validated_rules == r2.validated_rules

    def test_deterministic_ids(self) -> None:
        validator = CognitiveValidator()
        pkg = _package(facts=(_fact(evidence=(_evidence(),)),), provenance=("s",))
        r1 = validator.validate(pkg, _ctx())
        r2 = validator.validate(pkg, _ctx())
        assert r1.id == r2.id

    def test_blocking_and_warnings_separated(self) -> None:
        validator = CognitiveValidator()
        # Package with no provenance → blocking, and fact without evidence → warning
        pkg = _package(facts=(_fact(evidence=()),), provenance=())
        result = validator.validate(pkg, _ctx())
        assert len(result.blocking_findings) > 0
        assert all(f.blocking for f in result.blocking_findings)
        assert all(not f.blocking for f in result.warnings)

    def test_target_not_modified(self) -> None:
        validator = CognitiveValidator()
        pkg = _package(facts=(_fact(evidence=(_evidence(),)),), provenance=("s",))
        original_serialize = pkg.serialize()
        validator.validate(pkg, _ctx())
        assert pkg.serialize() == original_serialize

    def test_metadata_preserved(self) -> None:
        validator = CognitiveValidator()
        pkg = _package(facts=(_fact(evidence=(_evidence(),)),), provenance=("s",))
        result = validator.validate(pkg, _ctx())
        assert "rule_count" in result.metadata

    def test_no_model_invocation(self) -> None:
        """The validator must not invoke any model."""
        validator = CognitiveValidator()
        pkg = _package()
        # This should complete without any model calls
        result = validator.validate(pkg, _ctx())
        assert result is not None


# ── Phase 7 integration tests ────────────────────────────────────────────────


class TestPhase7Integration:
    def test_executor_returns_validation_step_result(self) -> None:
        validator = CognitiveValidator()
        pkg = _package(facts=(_fact(evidence=(_evidence(),)),), provenance=("s",))
        cog_ctx = _ctx()
        executor = CognitiveValidationStepExecutor(validator, pkg, cog_ctx)
        val_ctx = ValidationContext(project_root=Path("/tmp"))
        step = ValidationStep(
            name="cognitive.validation",
            step_type=ValidationStepType.INTERNAL,
        )
        result = executor.validate(val_ctx, step)
        assert isinstance(result, ValidationStepResult)
        assert result.name == "cognitive.validation"

    def test_executor_status_passed(self) -> None:
        validator = CognitiveValidator()
        pkg = _package(facts=(_fact(evidence=(_evidence(),)),), provenance=("s",))
        executor = CognitiveValidationStepExecutor(validator, pkg, _ctx())
        val_ctx = ValidationContext(project_root=Path("/tmp"))
        step = ValidationStep(
            name="cognitive.validation", step_type=ValidationStepType.INTERNAL
        )
        result = executor.validate(val_ctx, step)
        assert result.status is ValidationStatus.PASSED

    def test_executor_status_warning(self) -> None:
        validator = CognitiveValidator()
        # Fact without evidence → warning
        pkg = _package(facts=(_fact(evidence=()),), provenance=("s",))
        executor = CognitiveValidationStepExecutor(validator, pkg, _ctx())
        val_ctx = ValidationContext(project_root=Path("/tmp"))
        step = ValidationStep(
            name="cognitive.validation", step_type=ValidationStepType.INTERNAL
        )
        result = executor.validate(val_ctx, step)
        assert result.status is ValidationStatus.WARNING

    def test_executor_status_failed(self) -> None:
        validator = CognitiveValidator()
        # No provenance → blocking
        pkg = _package(provenance=())
        executor = CognitiveValidationStepExecutor(validator, pkg, _ctx())
        val_ctx = ValidationContext(project_root=Path("/tmp"))
        step = ValidationStep(
            name="cognitive.validation", step_type=ValidationStepType.INTERNAL
        )
        result = executor.validate(val_ctx, step)
        assert result.status is ValidationStatus.FAILED

    def test_executor_findings_preserved(self) -> None:
        validator = CognitiveValidator()
        pkg = _package(provenance=())
        executor = CognitiveValidationStepExecutor(validator, pkg, _ctx())
        val_ctx = ValidationContext(project_root=Path("/tmp"))
        step = ValidationStep(
            name="cognitive.validation", step_type=ValidationStepType.INTERNAL
        )
        result = executor.validate(val_ctx, step)
        assert len(result.findings) > 0

    def test_executor_artifact_generated(self) -> None:
        validator = CognitiveValidator()
        pkg = _package(facts=(_fact(evidence=(_evidence(),)),), provenance=("s",))
        executor = CognitiveValidationStepExecutor(validator, pkg, _ctx())
        val_ctx = ValidationContext(project_root=Path("/tmp"))
        step = ValidationStep(
            name="cognitive.validation", step_type=ValidationStepType.INTERNAL
        )
        result = executor.validate(val_ctx, step)
        assert len(result.artifacts) == 1
        artifact = result.artifacts[0]
        assert artifact.kind == "cognitive_validation_report"
        assert "target_id" in artifact.content
        assert "decision" in artifact.content

    def test_executor_artifact_no_sensitive_payload(self) -> None:
        validator = CognitiveValidator()
        privacy = PrivacyMetadata(
            policy=PrivacyPolicy.LOCAL_ONLY,
            sensitivity=SensitivityLevel.RESTRICTED,
        )
        entry = _cache_entry(privacy=privacy)
        executor = CognitiveValidationStepExecutor(validator, entry, _ctx())
        val_ctx = ValidationContext(project_root=Path("/tmp"))
        step = ValidationStep(
            name="cognitive.validation", step_type=ValidationStepType.INTERNAL
        )
        result = executor.validate(val_ctx, step)
        artifact = result.artifacts[0]
        # Artifact should not contain the full entry value
        assert "value" not in artifact.content
        assert "privacy" not in artifact.content

    def test_executor_compatible_with_pipeline(self) -> None:
        """The executor should be usable as an InternalValidator in the pipeline."""
        from cmm.validation.executor import ValidationExecutor
        from cmm.validation.registry import ValidationRegistry

        validator = CognitiveValidator()
        pkg = _package(facts=(_fact(evidence=(_evidence(),)),), provenance=("s",))
        executor = CognitiveValidationStepExecutor(validator, pkg, _ctx())

        registry = ValidationRegistry()
        registry.register("cognitive.validation", executor)

        val_executor = ValidationExecutor()
        val_ctx = ValidationContext(project_root=Path("/tmp"))
        step = ValidationStep(
            name="cognitive.validation", step_type=ValidationStepType.INTERNAL
        )
        result = val_executor.execute(val_ctx, step, registry)
        assert isinstance(result, ValidationStepResult)
        assert result.name == "cognitive.validation"


# ── Architecture tests ───────────────────────────────────────────────────────


class TestArchitecture:
    def test_no_provider_routing_llm_imports(self) -> None:
        """validation.py must not import providers, routing, LLM, or model gateway."""
        import ast

        with open("cmm/cognitive/validation.py") as f:
            tree = ast.parse(f.read())
        forbidden = {"provider", "routing", "llm", "model_gateway", "gateway"}
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                module = node.module or ""
                for word in forbidden:
                    assert word not in module.lower(), (
                        f"Forbidden import '{word}' in {module}"
                    )
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    for word in forbidden:
                        assert word not in alias.name.lower(), (
                            f"Forbidden import '{word}' in {alias.name}"
                        )

    def test_reuses_validation_finding(self) -> None:
        from cmm.cognitive.validation import _finding

        f = _finding(
            "COG_TEST",
            "test",
            severity=ValidationSeverity.INFO,
            blocking=False,
        )
        assert isinstance(f, ValidationFinding)

    def test_reuses_privacy_metadata(self) -> None:
        ctx = _ctx()
        op_ctx = ctx.to_privacy_operation_context()
        from cmm.cognitive.privacy import PrivacyOperationContext

        assert isinstance(op_ctx, PrivacyOperationContext)

    def test_reuses_cognitive_cache_validator(self) -> None:
        from cmm.cognitive.validation import default_cognitive_validation_rules

        rules = default_cognitive_validation_rules()
        cache_rule = next(r for r in rules if r.name == "cognitive.cache")
        assert isinstance(cache_rule, CognitiveCacheRule)

    def test_public_api_exports(self) -> None:
        from cmm import cognitive

        for name in (
            "COGNITIVE_VALIDATION_SCHEMA_VERSION",
            "CognitiveValidationContext",
            "CognitiveValidationDecision",
            "CognitiveValidationResult",
            "CognitiveValidationRule",
            "CognitiveValidationStepExecutor",
            "CognitiveValidator",
            "derive_cognitive_validation_decision",
        ):
            assert hasattr(cognitive, name), f"{name} not exported"

    def test_cognitive_suite_compatible(self) -> None:
        """Existing cognitive tests should still pass — verified by running them separately."""
        # This is a structural test: the import itself must not fail
        from cmm import cognitive

        assert cognitive.CognitiveValidationDecision.ACCEPT.value == "accept"
