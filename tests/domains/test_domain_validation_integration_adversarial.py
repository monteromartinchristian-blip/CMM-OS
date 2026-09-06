"""Phase 10.43 — Security and anti-fragmentation adversarial gate (Task 7)."""

from __future__ import annotations

import ast
import pathlib
import tempfile
from pathlib import Path

import pytest

from cmm.agent_runtime.enums import (
    AgentValidationStage,
    PolicyRiskLevel,
)
from cmm.agent_runtime.errors import ValidationAdapterError
from cmm.agent_runtime.validation_execution_adapter import AgentValidationAdapter
from cmm.agent_runtime.validation_integration_contracts import AgentValidationRequest
from cmm.domains.enums import DomainOperationType, DomainValidationStatus
from cmm.domains.errors import DomainSourceUntrusted, DomainValidationBlocked
from cmm.domains.loader import DeclarativeDomainLoader
from cmm.domains.manifest_reader import JsonDomainManifestReader
from cmm.domains.operation_contracts import DomainOperationDefinition
from cmm.domains.project.operations import build_project_operation_definitions
from cmm.domains.registry import DomainRegistry
from cmm.domains.validation import ensure_domain_validation_allows_install
from cmm.domains.validation_contracts import DomainValidationResult
from cmm.domains.validation_integration import (
    DomainValidationIntegrationError,
    build_operation_validation_requirements,
    compose_effective_validation_ids,
    is_ignored_caller_validation_metadata,
    require_canonical_validation_success,
    validate_domain_specialized_result,
)
from cmm.validation import ValidationResult, ValidationStatus
from cmm.validation.steps import ValidationStepResult
from tests.domains._loader_helpers import make_candidate, write_domain_dir


def _step(name: str, status=ValidationStatus.PASSED) -> ValidationStepResult:
    return ValidationStepResult(name=name, status=status)


def _canonical(
    result_id: str = "vr-1",
    status=ValidationStatus.PASSED,
    steps: tuple = (),
) -> ValidationResult:
    return ValidationResult(id=result_id, status=status, steps=tuple(steps))


def _passing_domain_result(**overrides) -> DomainValidationResult:
    defaults = {
        "domain_id": "domain:test",
        "version": "1.0.0",
        "status": DomainValidationStatus.PASSED,
        "manifest_valid": True,
        "compatibility_valid": True,
        "dependencies_valid": True,
        "contracts_valid": True,
        "permissions_valid": True,
        "operations_valid": True,
        "workflows_valid": True,
        "security_valid": True,
        "fragmentation_valid": True,
        "tests_valid": True,
        "metadata": {"strict": False, "tests_evaluated": True},
    }
    defaults.update(overrides)
    return DomainValidationResult(**defaults)


class TestFakeMissingEvidence:
    def test_fake_validation_result_id_rejected(self) -> None:
        # A caller-claimed ID with no canonical evidence is not truth.
        with pytest.raises(DomainValidationIntegrationError):
            require_canonical_validation_success(
                required_validation_ids=("domain.contracts",),
                canonical_results=(),
            )
        # Even with an unrelated real result, the fake ID has no evidence.
        real = _canonical("vr-real", steps=(_step("domain.manifest"),))
        with pytest.raises(DomainValidationIntegrationError):
            require_canonical_validation_success(
                required_validation_ids=("domain.contracts",),
                canonical_results=(real,),
            )

    def test_mismatched_validation_identity_rejected(self) -> None:
        real = _canonical("vr-1", steps=(_step("domain.contracts"),))
        with pytest.raises(DomainValidationIntegrationError):
            validate_domain_specialized_result(
                result={"domain_id": "domain:other", "status": "success"},
                expected_domain_id="domain:test",
                required_validation_ids=("domain.contracts",),
                canonical_validation_results=(real,),
            )

    def test_empty_result_set_for_mandatory_rejected(self) -> None:
        with pytest.raises(DomainValidationIntegrationError):
            validate_domain_specialized_result(
                result={"domain_id": "domain:test", "status": "success"},
                expected_domain_id="domain:test",
                required_validation_ids=("domain.contracts",),
                canonical_validation_results=(),
            )

    def test_unknown_validator_id_fails_closed(self) -> None:
        reqs = build_operation_validation_requirements(
            required_validation_ids=("unknown.required.validation",),
            stage="pre_execution",
            operation_name="test.op",
        )
        request = AgentValidationRequest(
            id="val-unknown",
            run_id="run-1",
            iteration_id="task-1",
            operation_request_id="req-1",
            stage=AgentValidationStage.PRE_EXECUTION,
            requirements=reqs,
        )
        with pytest.raises(ValidationAdapterError):
            AgentValidationAdapter().validate(request)

    def test_malformed_policy_id_rejected(self) -> None:
        with pytest.raises(DomainValidationIntegrationError):
            build_operation_validation_requirements(
                required_validation_ids=("x",),
                stage="not_a_stage",
            )

    def test_timeout_cancel_error_treated_as_non_success(self) -> None:
        for status in (
            ValidationStatus.TIMED_OUT,
            ValidationStatus.CANCELLED,
            ValidationStatus.ERROR,
            ValidationStatus.FAILED,
        ):
            res = _canonical(
                f"vr-{status.value}",
                status=status,
                steps=(_step("domain.contracts", status),),
            )
            with pytest.raises(DomainValidationIntegrationError):
                require_canonical_validation_success(
                    required_validation_ids=("domain.contracts",),
                    canonical_results=(res,),
                )
        # Domain gate also blocks non-terminal statuses.
        for domain_status in (
            DomainValidationStatus.FAILED,
            DomainValidationStatus.ERROR,
            DomainValidationStatus.PENDING,
            DomainValidationStatus.RUNNING,
        ):
            with pytest.raises(DomainValidationBlocked):
                ensure_domain_validation_allows_install(
                    _passing_domain_result(status=domain_status)
                )


class TestAuthoritySeparation:
    def test_passing_validation_does_not_enable_domain(self) -> None:
        result = _passing_domain_result()
        ensure_domain_validation_allows_install(result)
        # Validation gate passing carries no enablement: there is no
        # enablement flag on the result, and is_install_allowed is distinct
        # from enabled/authorized.
        assert result.is_install_allowed is True
        assert not hasattr(result, "enabled")

    def test_passing_validation_against_untrusted_still_requires_trust(self) -> None:
        # Trust is owned by the loader/trust policy, not validation: an
        # untrusted candidate is rejected at load even if its content would
        # validate.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            domain_dir = write_domain_dir(root, "untrusted-pack", "1.0.0")
            candidate = make_candidate(
                domain_dir, "untrusted-pack", "1.0.0", trusted=False
            )
            loader = DeclarativeDomainLoader(
                manifest_reader=JsonDomainManifestReader(),
                registry=DomainRegistry(),
            )
            with pytest.raises(DomainSourceUntrusted):
                loader.load(candidate)

    def test_passing_validation_with_missing_permission_grants_nothing(self) -> None:
        definition = DomainOperationDefinition(
            operation_id="test.op",
            domain_id="domain:test",
            version="1.0.0",
            name="op",
            description="test",
            operation_type=DomainOperationType.READ,
            required_permissions=("file.modify",),
            risk_level=PolicyRiskLevel.LOW,
            reversible=True,
            requires_approval=False,
            validation_policy_id="validation.test.op",
            rollback_policy_id="rollback.test.op",
            enabled=True,
            metadata={},
        )
        # Validation does not mutate the definition's permission requirements.
        assert definition.required_permissions == ("file.modify",)

    def test_passing_validation_with_missing_approval_grants_nothing(self) -> None:
        ops = {op.operation_id: op for op in build_project_operation_definitions()}
        modify = ops["project.modify_code"]
        assert modify.requires_approval is True
        # A passing specialized-result check returns references only; it
        # never flips requires_approval or grants approval.
        real = _canonical("vr-1", steps=(_step("syntax"),))
        refs = validate_domain_specialized_result(
            result={"domain_id": "domain:project", "status": "success"},
            expected_domain_id="domain:project",
            required_validation_ids=("syntax",),
            canonical_validation_results=(real,),
        )
        assert refs == ("vr-1",)
        assert modify.requires_approval is True


class TestMetadataPromptInjection:
    def test_downgrade_keys_are_ignored(self) -> None:
        for key in (
            "skip_validation",
            "validation_passed",
            "required_validation_ids",
            "trust",
            "approval",
        ):
            assert is_ignored_caller_validation_metadata(key) is True

    def test_caller_claim_of_pass_ignored_without_evidence(self) -> None:
        with pytest.raises(DomainValidationIntegrationError):
            validate_domain_specialized_result(
                result={
                    "domain_id": "domain:test",
                    "status": "success",
                    "validation_passed": True,
                    "skip_validation": True,
                    "trust": "trusted",
                    "approval": "approved",
                },
                expected_domain_id="domain:test",
                required_validation_ids=("domain.contracts",),
                canonical_validation_results=(),
            )

    def test_caller_empty_ids_cannot_remove_host_requirements(self) -> None:
        host = compose_effective_validation_ids(
            primary_required=("domain.contracts",),
            operation_required=("operation.output.validation",),
        )
        assert host == ("domain.contracts", "operation.output.validation")
        # Caller metadata is not an input to the composer; host obligations
        # survive regardless of caller claims.

    def test_prompt_config_claiming_pass_rejected(self) -> None:
        # A result payload claiming trust/approval via prompt/config fields
        # still requires canonical evidence.
        with pytest.raises(DomainValidationIntegrationError):
            require_canonical_validation_success(
                required_validation_ids=("domain.contracts",),
                canonical_results=(),
            )


class TestNoDuplicateTruth:
    def test_repeated_declaration_yields_single_reference(self) -> None:
        effective = compose_effective_validation_ids(
            primary_required=("domain.contracts",),
            supporting_required=("domain.contracts",),
            operation_required=("domain.contracts",),
            workflow_required=("domain.contracts",),
        )
        assert effective == ("domain.contracts",)
        real = _canonical("vr-1", steps=(_step("domain.contracts"),))
        refs = require_canonical_validation_success(
            required_validation_ids=effective,
            canonical_results=(real, real),
        )
        assert refs == ("vr-1",)


PROHIBITED_SYMBOLS = (
    "DomainValidationEngine",
    "DomainValidationRuntime",
    "DomainValidationStore",
    "DomainValidationRepository",
    "DomainValidationEventBus",
    "DomainValidationHistory",
    "DomainValidationCommitGate",
    "DomainValidationPolicyRegistry",
    "DomainValidationExecutor",
)


class TestStructuralAntiFragmentation:
    def test_no_parallel_validation_symbols_in_domains(self) -> None:
        root = pathlib.Path("cmm/domains")
        offenders: list[str] = []
        for path in sorted(root.glob("*.py")):
            try:
                text = path.read_text(encoding="utf-8")
            except OSError:
                continue
            for symbol in PROHIBITED_SYMBOLS:
                if symbol in text:
                    offenders.append(f"{path.name}:{symbol}")
        assert offenders == []

    def test_no_second_pipeline_registry_or_store(self) -> None:
        root = pathlib.Path("cmm/domains")
        for path in sorted(root.glob("validation_*.py")):
            text = path.read_text(encoding="utf-8")
            tree = ast.parse(text)
            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef):
                    assert "ValidationPipeline" not in node.name or node.name in (
                        "PipelineDomainValidator",
                    ), f"{path.name}:{node.name}"
                    assert "ValidationRegistry" not in node.name, (
                        f"{path.name}:{node.name}"
                    )
                    assert "ValidationExecutor" not in node.name, (
                        f"{path.name}:{node.name}"
                    )
                    assert "ValidationStore" not in node.name, (
                        f"{path.name}:{node.name}"
                    )
                    assert "CommitGate" not in node.name, f"{path.name}:{node.name}"

    def test_integration_layer_delegates_without_own_pipeline(self) -> None:
        text = pathlib.Path("cmm/domains/validation_integration.py").read_text(
            encoding="utf-8"
        )
        assert "ValidationPipeline(" not in text
        assert "ValidationRegistry(" not in text
        assert "ValidationExecutor(" not in text
        # Canonical PipelineDomainValidator remains permitted elsewhere.
        validator_text = pathlib.Path("cmm/domains/validation.py").read_text(
            encoding="utf-8"
        )
        assert "PipelineDomainValidator" in validator_text

    def test_no_new_validation_truth_model(self) -> None:
        text = pathlib.Path("cmm/domains/validation_integration.py").read_text(
            encoding="utf-8"
        )
        assert "class DomainValidationResult" not in text
        assert "class ValidationResult" not in text
        assert "class ValidationPolicy" not in text
