"""Phase 10.38 — Domain trust evaluation tests (RED target for Task 2).

Proves `evaluate_domain_trust` is a pure, deterministic, fail-closed
activation evaluator: it consumes already-canonical evidence and never
mutates, queries, or authorizes anything.
"""

from __future__ import annotations

from datetime import datetime, timezone

from cmm.agent_runtime.domain_permission_contracts import PermissionCapability
from cmm.domains.enums import (
    DomainSourceKind,
    DomainTrustLevel,
    DomainValidationStatus,
)
from cmm.domains.identifiers import DomainId, DomainManifestId
from cmm.domains.manifest import DomainManifest
from cmm.domains.trust_contracts import DomainTrustDecision, DomainTrustPolicy
from cmm.domains.trust_evaluator import evaluate_domain_trust
from cmm.domains.validation_contracts import DomainValidationResult

_NOW = datetime(2026, 9, 1, tzinfo=timezone.utc)


def _candidate(
    *,
    trusted: bool = True,
    source_id: str = "source:external-1",
    source_kind: DomainSourceKind = DomainSourceKind.DIRECTORY,
    domain_id: str = "domain:example",
    version: str = "1.0.0",
):
    from cmm.domains.discovery_contracts import DomainCandidate

    return DomainCandidate(
        candidate_id="candidate:example-1.0.0",
        source_id=source_id,
        source_kind=source_kind,
        location="/packs/example",
        manifest_path="manifest.json",
        domain_id=domain_id,
        detected_version=version,
        checksum="sha256:" + "a" * 64,
        trusted=trusted,
        discovered_at=_NOW,
    )


def _manifest(
    *,
    domain_id: str = "domain:example",
    version: str = "1.0.0",
    signature: str | None = None,
) -> DomainManifest:
    return DomainManifest(
        id=DomainManifestId(slug=domain_id.removeprefix("domain:"), version=version),
        domain_id=DomainId(slug=domain_id.removeprefix("domain:")),
        schema_version="1",
        package_version=version,
        pack_kind="external",
        signature=signature,
    )


def _validation(
    *,
    domain_id: str = "domain:example",
    version: str = "1.0.0",
    status: DomainValidationStatus = DomainValidationStatus.PASSED,
    security_valid: bool = True,
    blocking: bool = False,
    warning_only: bool = False,
) -> DomainValidationResult:
    class _F:
        def __init__(self, message: str, blocking: bool = False) -> None:
            self.message = message
            self.blocking = blocking
            self.code = "test"

    findings: tuple[object, ...] = ()
    warnings: tuple[object, ...] = ()
    if blocking:
        findings = (_F("blocking finding", blocking=True),)
    elif warning_only:
        warnings = (_F("warning finding"),)

    return DomainValidationResult(
        domain_id=domain_id,
        version=version,
        status=status,
        manifest_valid=True,
        compatibility_valid=True,
        dependencies_valid=True,
        contracts_valid=True,
        permissions_valid=True,
        operations_valid=True,
        workflows_valid=True,
        security_valid=security_valid,
        fragmentation_valid=True,
        tests_valid=True,
        findings=findings,
        warnings=warnings,
        validated_at=_NOW,
    )


def _policy(
    *,
    domain_id: str = "domain:example",
    trust_level: DomainTrustLevel = DomainTrustLevel.COMMUNITY,
    authorized_source_ids: tuple[str, ...] = ("source:external-1",),
    **kwargs: object,
) -> DomainTrustPolicy:
    return DomainTrustPolicy(
        domain_id=domain_id,
        trust_level=trust_level,
        authorized_source_ids=authorized_source_ids,
        **kwargs,  # type: ignore[arg-type]
    )


class TestBlockedAndSource:
    def test_blocked_denies_even_when_candidate_trusted(self) -> None:
        candidate = _candidate(trusted=True)
        policy = _policy(trust_level=DomainTrustLevel.BLOCKED)
        decision = evaluate_domain_trust(
            candidate=candidate,
            manifest=_manifest(),
            validation=_validation(),
            policy=policy,
            manual_enable_requested=True,
        )
        assert decision.activation_allowed is False
        assert "trust.blocked" in decision.reason_codes

    def test_wrong_source_denied_with_trusted_candidate(self) -> None:
        candidate = _candidate(trusted=True, source_id="source:other")
        policy = _policy(authorized_source_ids=("source:external-1",))
        decision = evaluate_domain_trust(
            candidate=candidate,
            manifest=_manifest(),
            validation=_validation(),
            policy=policy,
            manual_enable_requested=True,
        )
        assert decision.activation_allowed is False
        assert "trust.source_not_authorized" in decision.reason_codes

    def test_empty_authorized_sources_authorizes_nothing(self) -> None:
        candidate = _candidate(trusted=True)
        policy = _policy(authorized_source_ids=())
        decision = evaluate_domain_trust(
            candidate=candidate,
            manifest=_manifest(),
            validation=_validation(),
            policy=policy,
            manual_enable_requested=True,
        )
        assert decision.activation_allowed is False
        assert "trust.source_not_authorized" in decision.reason_codes

    def test_explicit_policy_matching_source_is_usable(self) -> None:
        candidate = _candidate(source_id="source:external-1")
        policy = _policy(authorized_source_ids=("source:external-1",))
        decision = evaluate_domain_trust(
            candidate=candidate,
            manifest=_manifest(),
            validation=_validation(),
            policy=policy,
            manual_enable_requested=True,
        )
        assert decision.activation_allowed is True
        assert "trust.source_not_authorized" not in decision.reason_codes


class TestValidationIdentity:
    def test_wrong_validation_domain_fails_closed(self) -> None:
        policy = _policy()
        decision = evaluate_domain_trust(
            candidate=_candidate(),
            manifest=_manifest(),
            validation=_validation(domain_id="domain:other"),
            policy=policy,
            manual_enable_requested=True,
        )
        assert decision.activation_allowed is False
        assert "trust.validation_failed" in decision.reason_codes

    def test_stale_validation_version_fails_closed(self) -> None:
        policy = _policy()
        decision = evaluate_domain_trust(
            candidate=_candidate(version="2.0.0"),
            manifest=_manifest(version="2.0.0"),
            validation=_validation(version="1.0.0"),
            policy=policy,
            manual_enable_requested=True,
        )
        assert decision.activation_allowed is False
        assert "trust.validation_failed" in decision.reason_codes

    def test_failed_validation_status_fails_closed(self) -> None:
        decision = evaluate_domain_trust(
            candidate=_candidate(),
            manifest=_manifest(),
            validation=_validation(status=DomainValidationStatus.FAILED),
            policy=_policy(),
            manual_enable_requested=True,
        )
        assert decision.activation_allowed is False
        assert "trust.validation_failed" in decision.reason_codes

    def test_pending_validation_status_fails_closed(self) -> None:
        # V1 MAJOR-01: non-terminal PENDING must never be activation evidence.
        decision = evaluate_domain_trust(
            candidate=_candidate(),
            manifest=_manifest(),
            validation=_validation(status=DomainValidationStatus.PENDING),
            policy=_policy(),
            manual_enable_requested=True,
        )
        assert decision.activation_allowed is False
        assert "trust.validation_failed" in decision.reason_codes

    def test_running_validation_status_fails_closed(self) -> None:
        # V1 MAJOR-01: non-terminal RUNNING must never be activation evidence.
        decision = evaluate_domain_trust(
            candidate=_candidate(),
            manifest=_manifest(),
            validation=_validation(status=DomainValidationStatus.RUNNING),
            policy=_policy(),
            manual_enable_requested=True,
        )
        assert decision.activation_allowed is False
        assert "trust.validation_failed" in decision.reason_codes

    def test_blocking_finding_fails_closed(self) -> None:
        decision = evaluate_domain_trust(
            candidate=_candidate(),
            manifest=_manifest(),
            validation=_validation(
                status=DomainValidationStatus.WARNING, blocking=True
            ),
            policy=_policy(),
            manual_enable_requested=True,
        )
        assert decision.activation_allowed is False
        assert "trust.validation_failed" in decision.reason_codes

    def test_security_invalid_fails_closed(self) -> None:
        decision = evaluate_domain_trust(
            candidate=_candidate(),
            manifest=_manifest(),
            validation=_validation(security_valid=False),
            policy=_policy(),
            manual_enable_requested=True,
        )
        assert decision.activation_allowed is False
        assert "trust.validation_failed" in decision.reason_codes

    def test_manifest_identity_mismatch_fails_closed(self) -> None:
        policy = _policy()
        decision = evaluate_domain_trust(
            candidate=_candidate(),
            manifest=_manifest(domain_id="domain:other"),
            validation=_validation(),
            policy=policy,
            manual_enable_requested=True,
        )
        assert decision.activation_allowed is False
        assert "trust.validation_failed" in decision.reason_codes

    def test_manifest_version_mismatch_fails_closed(self) -> None:
        policy = _policy()
        decision = evaluate_domain_trust(
            candidate=_candidate(),
            manifest=_manifest(version="9.9.9"),
            validation=_validation(),
            policy=policy,
            manual_enable_requested=True,
        )
        assert decision.activation_allowed is False
        assert "trust.validation_failed" in decision.reason_codes


class TestSignaturePresence:
    def test_require_signature_with_none_denied(self) -> None:
        policy = _policy(require_signature=True)
        decision = evaluate_domain_trust(
            candidate=_candidate(),
            manifest=_manifest(signature=None),
            validation=_validation(),
            policy=policy,
            manual_enable_requested=True,
        )
        assert decision.activation_allowed is False
        assert "trust.signature_required" in decision.reason_codes

    def test_require_signature_with_present_signature_passes_presence(self) -> None:
        policy = _policy(require_signature=True)
        decision = evaluate_domain_trust(
            candidate=_candidate(),
            manifest=_manifest(signature="base64-not-verified"),
            validation=_validation(),
            policy=policy,
            manual_enable_requested=True,
        )
        assert decision.activation_allowed is True
        assert "trust.signature_required" not in decision.reason_codes

    def test_no_signature_required_and_no_signature_is_fine(self) -> None:
        policy = _policy(require_signature=False)
        decision = evaluate_domain_trust(
            candidate=_candidate(),
            manifest=_manifest(signature=None),
            validation=_validation(),
            policy=policy,
            manual_enable_requested=True,
        )
        assert decision.activation_allowed is True
        assert "trust.signature_required" not in decision.reason_codes

    def test_no_decision_claims_cryptographic_verification(self) -> None:
        policy = _policy(require_signature=True)
        decision = evaluate_domain_trust(
            candidate=_candidate(),
            manifest=_manifest(signature="base64-not-verified"),
            validation=_validation(),
            policy=policy,
            manual_enable_requested=True,
        )
        assert decision.activation_allowed is True
        serialized = decision.to_dict()
        joined = f"{serialized}".lower()
        assert "cryptographically verified" not in joined
        assert "verified publisher" not in joined
        assert "authenticated package" not in joined
        assert "trusted by certificate" not in joined


class TestManualEnable:
    def test_manual_enable_required_and_not_requested_denied(self) -> None:
        policy = _policy(require_manual_enable=True)
        decision = evaluate_domain_trust(
            candidate=_candidate(),
            manifest=_manifest(),
            validation=_validation(),
            policy=policy,
            manual_enable_requested=False,
        )
        assert decision.activation_allowed is False
        assert "trust.manual_enable_required" in decision.reason_codes

    def test_manual_enable_required_and_requested_is_ok(self) -> None:
        policy = _policy(require_manual_enable=True)
        decision = evaluate_domain_trust(
            candidate=_candidate(),
            manifest=_manifest(),
            validation=_validation(),
            policy=policy,
            manual_enable_requested=True,
        )
        assert decision.activation_allowed is True
        assert "trust.manual_enable_required" not in decision.reason_codes

    def test_manual_enable_not_required_and_not_requested_is_ok(self) -> None:
        policy = _policy(require_manual_enable=False)
        decision = evaluate_domain_trust(
            candidate=_candidate(),
            manifest=_manifest(),
            validation=_validation(),
            policy=policy,
            manual_enable_requested=False,
        )
        assert decision.activation_allowed is True
        assert "trust.manual_enable_required" not in decision.reason_codes


class TestCapabilityCeilings:
    def test_default_policy_denies_all_privileged_capabilities(self) -> None:
        policy = _policy()
        decision = evaluate_domain_trust(
            candidate=_candidate(),
            manifest=_manifest(),
            validation=_validation(),
            policy=policy,
            manual_enable_requested=True,
        )
        denied = set(decision.denied_capabilities)
        assert PermissionCapability.OPERATION_EXECUTE.value in denied
        assert PermissionCapability.WORKFLOW_EXECUTE.value in denied
        assert PermissionCapability.MEMORY_WRITE.value in denied
        assert PermissionCapability.SEARCH_EXTERNAL.value in denied
        assert PermissionCapability.MODEL_EXTERNAL.value in denied
        assert PermissionCapability.COMMUNICATION_EXTERNAL.value in denied
        assert PermissionCapability.EXPORT.value in denied
        assert PermissionCapability.DOMAIN_CROSS_ACCESS.value in denied
        assert PermissionCapability.SENSITIVE_INFERENCE.value in denied
        assert PermissionCapability.SENSITIVE_INFERENCE_PERSIST.value in denied
        assert PermissionCapability.FILE_MODIFY.value in denied
        assert PermissionCapability.TASK_CREATE.value in denied
        assert PermissionCapability.SCHEDULE_MODIFY.value in denied
        assert PermissionCapability.GOAL_UPDATE.value in denied
        assert PermissionCapability.PUBLICATION.value in denied
        assert PermissionCapability.KNOWLEDGE_DELETE.value in denied
        assert PermissionCapability.PERMISSION_MODIFY.value in denied
        assert PermissionCapability.IRREVERSIBLE_CHANGE.value in denied
        assert PermissionCapability.MEDICAL_ACTION.value in denied
        assert PermissionCapability.LEGAL_ACTION.value in denied
        assert PermissionCapability.FINANCIAL_ACTION.value in denied
        assert PermissionCapability.FINANCIAL_SPEND.value in denied

    def test_enabling_code_execution_removes_only_operation_workflow_denial(
        self,
    ) -> None:
        policy = _policy(allow_code_execution=True)
        decision = evaluate_domain_trust(
            candidate=_candidate(),
            manifest=_manifest(),
            validation=_validation(),
            policy=policy,
            manual_enable_requested=True,
        )
        denied = set(decision.denied_capabilities)
        assert PermissionCapability.OPERATION_EXECUTE.value not in denied
        assert PermissionCapability.WORKFLOW_EXECUTE.value not in denied
        # Other dimensions remain denied.
        assert PermissionCapability.MEMORY_WRITE.value in denied
        assert PermissionCapability.SEARCH_EXTERNAL.value in denied

    def test_enabling_memory_write_removes_only_memory_write(self) -> None:
        policy = _policy(allow_memory_write=True)
        decision = evaluate_domain_trust(
            candidate=_candidate(),
            manifest=_manifest(),
            validation=_validation(),
            policy=policy,
            manual_enable_requested=True,
        )
        denied = set(decision.denied_capabilities)
        assert PermissionCapability.MEMORY_WRITE.value not in denied
        assert PermissionCapability.OPERATION_EXECUTE.value in denied

    def test_enabling_external_access_removes_external_capabilities(self) -> None:
        policy = _policy(allow_external_access=True)
        decision = evaluate_domain_trust(
            candidate=_candidate(),
            manifest=_manifest(),
            validation=_validation(),
            policy=policy,
            manual_enable_requested=True,
        )
        denied = set(decision.denied_capabilities)
        for cap in (
            PermissionCapability.SEARCH_EXTERNAL,
            PermissionCapability.MODEL_EXTERNAL,
            PermissionCapability.COMMUNICATION_EXTERNAL,
            PermissionCapability.EXPORT,
            PermissionCapability.DOMAIN_CROSS_ACCESS,
        ):
            assert cap.value not in denied
        assert PermissionCapability.MEMORY_WRITE.value in denied

    def test_enabling_sensitive_resources_removes_sensitive_capabilities(
        self,
    ) -> None:
        policy = _policy(allow_sensitive_resources=True)
        decision = evaluate_domain_trust(
            candidate=_candidate(),
            manifest=_manifest(),
            validation=_validation(),
            policy=policy,
            manual_enable_requested=True,
        )
        denied = set(decision.denied_capabilities)
        assert PermissionCapability.SENSITIVE_INFERENCE.value not in denied
        assert PermissionCapability.SENSITIVE_INFERENCE_PERSIST.value not in denied

    def test_enabling_destructive_operations_removes_destructive_capabilities(
        self,
    ) -> None:
        policy = _policy(allow_destructive_operations=True)
        decision = evaluate_domain_trust(
            candidate=_candidate(),
            manifest=_manifest(),
            validation=_validation(),
            policy=policy,
            manual_enable_requested=True,
        )
        denied = set(decision.denied_capabilities)
        for cap in (
            PermissionCapability.FILE_MODIFY,
            PermissionCapability.TASK_CREATE,
            PermissionCapability.SCHEDULE_MODIFY,
            PermissionCapability.GOAL_UPDATE,
            PermissionCapability.PUBLICATION,
            PermissionCapability.KNOWLEDGE_DELETE,
            PermissionCapability.PERMISSION_MODIFY,
            PermissionCapability.IRREVERSIBLE_CHANGE,
            PermissionCapability.MEDICAL_ACTION,
            PermissionCapability.LEGAL_ACTION,
            PermissionCapability.FINANCIAL_ACTION,
            PermissionCapability.FINANCIAL_SPEND,
        ):
            assert cap.value not in denied

    def test_capability_denial_does_not_fail_activation(self) -> None:
        """A denied capability constrains authority but never blocks activation."""
        policy = _policy()
        decision = evaluate_domain_trust(
            candidate=_candidate(),
            manifest=_manifest(),
            validation=_validation(),
            policy=policy,
            manual_enable_requested=True,
        )
        assert decision.activation_allowed is True
        assert decision.denied_capabilities


class TestDecisionEvidence:
    def test_decision_carries_reference_evidence_only(self) -> None:
        decision = evaluate_domain_trust(
            candidate=_candidate(source_id="source:external-1"),
            manifest=_manifest(),
            validation=_validation(),
            policy=_policy(),
            manual_enable_requested=True,
        )
        assert isinstance(decision, DomainTrustDecision)
        assert decision.domain_id == "domain:example"
        assert decision.candidate_id == "candidate:example-1.0.0"
        assert decision.source_id == "source:external-1"
        assert decision.trust_level is DomainTrustLevel.COMMUNITY
        fields = set(decision.__dataclass_fields__)
        assert "prompt" not in fields
        assert "content" not in fields
        assert "manifest" not in fields
        assert "signature" not in fields
        assert "secret" not in fields

    def test_low_trust_levels_remain_restrictive_through_defaults(self) -> None:
        for level in (
            DomainTrustLevel.COMMUNITY,
            DomainTrustLevel.UNTRUSTED,
            DomainTrustLevel.BLOCKED,
        ):
            policy = _policy(trust_level=level)
            decision = evaluate_domain_trust(
                candidate=_candidate(),
                manifest=_manifest(),
                validation=_validation(),
                policy=policy,
                manual_enable_requested=True,
            )
            # Policy declaration is explicit: enum order must not secretly
            # widen capacity. All allow_* are False, so checks stay closed.
            assert decision.activation_allowed is (
                level is not DomainTrustLevel.BLOCKED
            )
            assert decision.denied_capabilities

    def test_pure_function_does_not_mutate_inputs(self) -> None:
        candidate = _candidate()
        manifest = _manifest()
        validation = _validation()
        policy = _policy()
        before = (
            candidate.to_dict(),
            manifest.to_dict(),
            validation.to_dict(),
            policy.to_dict(),
        )
        evaluate_domain_trust(
            candidate=candidate,
            manifest=manifest,
            validation=validation,
            policy=policy,
            manual_enable_requested=True,
        )
        after = (
            candidate.to_dict(),
            manifest.to_dict(),
            validation.to_dict(),
            policy.to_dict(),
        )
        assert after == before
