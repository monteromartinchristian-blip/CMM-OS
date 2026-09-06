"""Phase 10.43 — Pack installation/update policy integration (Task 2)."""

from __future__ import annotations

import inspect
import json

import pytest

from cmm.domains.enums import DomainValidationStatus
from cmm.domains.errors import (
    DomainValidationBlocked,
    DomainValidationExecutionError,
)
from cmm.domains.loader import DeclarativeDomainLoader
from cmm.domains.manifest_reader import JsonDomainManifestReader
from cmm.domains.registry import DomainRegistry
from cmm.domains.validation import (
    PipelineDomainValidator,
    ensure_domain_validation_allows_install,
    ensure_domain_validation_allows_update,
)
from cmm.domains.validation_contracts import (
    DomainValidationRequest,
    DomainValidationResult,
)
from cmm.domains.validation_policy_bindings import (
    DOMAIN_PACK_BASE_VALIDATION_IDS,
    build_domain_pack_installation_policy,
    build_domain_pack_update_policy,
)
from cmm.validation import ValidationPolicy
from tests.domains._loader_helpers import make_candidate, make_pack, write_domain_dir


def _pack_request(tmp_path, slug: str = "test-domain") -> DomainValidationRequest:
    domain_dir = tmp_path / slug
    domain_dir.mkdir(parents=True, exist_ok=True)
    manifest = {
        "id": slug,
        "version": "1.0.0",
        "author": "tester",
        "license": "MIT",
    }
    (domain_dir / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    (domain_dir / "probe.py").write_text("x = 1\n", encoding="utf-8")
    pack = make_pack(slug, "1.0.0", root_path=str(domain_dir))
    return DomainValidationRequest(
        pack=pack,
        root_path=str(domain_dir),
        strict=False,
        run_tests=False,
    )


def _failed_result() -> DomainValidationResult:
    return DomainValidationResult(
        domain_id="domain:test",
        version="1.0.0",
        status=DomainValidationStatus.FAILED,
        manifest_valid=False,
        compatibility_valid=False,
        dependencies_valid=False,
        contracts_valid=False,
        permissions_valid=False,
        operations_valid=False,
        workflows_valid=False,
        security_valid=False,
        fragmentation_valid=False,
        tests_valid=False,
        metadata={"strict": False, "tests_evaluated": True},
    )


def _error_result() -> DomainValidationResult:
    base = _failed_result()
    return DomainValidationResult(
        domain_id=base.domain_id,
        version=base.version,
        status=DomainValidationStatus.ERROR,
        manifest_valid=True,
        compatibility_valid=True,
        dependencies_valid=True,
        contracts_valid=True,
        permissions_valid=True,
        operations_valid=True,
        workflows_valid=True,
        security_valid=True,
        fragmentation_valid=True,
        tests_valid=True,
        metadata={"strict": False, "tests_evaluated": True},
    )


def _passing_result(**overrides) -> DomainValidationResult:
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


class TestInstallationPolicyBinding:
    def test_validate_accepts_canonical_policy_param(self) -> None:
        sig = inspect.signature(PipelineDomainValidator.validate)
        assert "policy" in sig.parameters

    def test_installation_policy_runs_through_pipeline_domain_validator(
        self, tmp_path
    ) -> None:
        request = _pack_request(tmp_path)
        policy = build_domain_pack_installation_policy()
        assert isinstance(policy, ValidationPolicy)
        validator = PipelineDomainValidator()
        result = validator.validate(request, policy=policy)
        # Real Phase 7 pipeline executed: step results cover the eight base checks.
        executed = {sr.name for sr in result.step_results}
        assert set(DOMAIN_PACK_BASE_VALIDATION_IDS) <= executed

    def test_update_policy_runs_through_pipeline_domain_validator(
        self, tmp_path
    ) -> None:
        request = _pack_request(tmp_path)
        policy = build_domain_pack_update_policy()
        validator = PipelineDomainValidator()
        result = validator.validate(request, policy=policy)
        executed = {sr.name for sr in result.step_results}
        assert set(DOMAIN_PACK_BASE_VALIDATION_IDS) <= executed

    def test_unknown_domain_policy_step_fails_closed(self, tmp_path) -> None:
        from cmm.domains.validation_policy_bindings import (
            DOMAIN_PACK_INSTALLATION_POLICY_NAME,
        )

        request = _pack_request(tmp_path)
        bad_policy = ValidationPolicy(
            name=DOMAIN_PACK_INSTALLATION_POLICY_NAME,
            required_steps=("domain.unknown_step",),
        )
        with pytest.raises(DomainValidationExecutionError):
            PipelineDomainValidator().validate(request, policy=bad_policy)

    def test_non_policy_object_rejected(self, tmp_path) -> None:
        request = _pack_request(tmp_path)
        with pytest.raises(DomainValidationExecutionError):
            PipelineDomainValidator().validate(request, policy="not-a-policy")  # type: ignore[arg-type]

    def test_canonical_pipeline_used_not_parallel(self, tmp_path) -> None:
        # The validator must delegate to the canonical Phase 7 pipeline:
        # injecting a real ValidationPipeline with its own registry works and
        # domain handlers are registered temporarily, not duplicated.
        from cmm.validation import (
            ValidationExecutor,
            ValidationPipeline,
            ValidationRegistry,
        )

        registry = ValidationRegistry()
        executor = ValidationExecutor()
        pipeline = ValidationPipeline(executor=executor, registry=registry)
        request = _pack_request(tmp_path)
        result = PipelineDomainValidator(pipeline=pipeline).validate(
            request, policy=build_domain_pack_installation_policy()
        )
        assert result.domain_id == "domain:test-domain"
        # Temporary handlers removed after run.
        for step_id in DOMAIN_PACK_BASE_VALIDATION_IDS:
            assert not registry.has(step_id)


class TestMonotonicSingleRead:
    def test_validate_reads_monotonic_clock_exactly_twice(self, tmp_path) -> None:
        # MINOR-01 regression: two consecutive t0 reads corrupt duration
        # accounting under deterministic clocks. Exactly one initial read
        # plus one final read must occur.
        values = iter((100.0, 100.25))
        calls: list[str] = []

        def _monotonic() -> float:
            calls.append("read")
            return next(values)

        request = _pack_request(tmp_path)
        result = PipelineDomainValidator(monotonic=_monotonic).validate(request)
        assert len(calls) == 2
        assert result.duration_ms == 250


class TestInstallGateFailClosed:
    def test_failed_blocks(self) -> None:
        with pytest.raises(DomainValidationBlocked):
            ensure_domain_validation_allows_install(_failed_result())

    def test_error_blocks(self) -> None:
        with pytest.raises(DomainValidationBlocked):
            ensure_domain_validation_allows_install(_error_result())

    def test_pending_blocks_fail_closed(self) -> None:
        result = _passing_result(status=DomainValidationStatus.PENDING)
        with pytest.raises(DomainValidationBlocked):
            ensure_domain_validation_allows_install(result)

    def test_running_blocks_fail_closed(self) -> None:
        result = _passing_result(status=DomainValidationStatus.RUNNING)
        with pytest.raises(DomainValidationBlocked):
            ensure_domain_validation_allows_install(result)

    def test_blocking_finding_blocks_even_when_flags_pass(self) -> None:
        from cmm.validation import ValidationFinding, ValidationSeverity

        finding = ValidationFinding(
            code="DOMAIN_TEST_BLOCKING",
            message="blocking",
            severity=ValidationSeverity.ERROR,
            source="domain.tests",
            blocking=True,
        )
        result = DomainValidationResult(
            domain_id="domain:test",
            version="1.0.0",
            status=DomainValidationStatus.FAILED,
            manifest_valid=True,
            compatibility_valid=True,
            dependencies_valid=True,
            contracts_valid=True,
            permissions_valid=True,
            operations_valid=True,
            workflows_valid=True,
            security_valid=True,
            fragmentation_valid=True,
            tests_valid=True,
            findings=(finding,),
            metadata={"strict": False, "tests_evaluated": True},
        )
        with pytest.raises(DomainValidationBlocked):
            ensure_domain_validation_allows_install(result)

    def test_warning_with_clean_flags_does_not_block(self) -> None:
        result = _passing_result(status=DomainValidationStatus.WARNING)
        ensure_domain_validation_allows_install(result)

    def test_update_gate_delegates_to_install_gate(self) -> None:
        # Passing result allowed.
        ensure_domain_validation_allows_update(
            _passing_result(status=DomainValidationStatus.PASSED)
        )
        # Failing result blocked.
        with pytest.raises(DomainValidationBlocked):
            ensure_domain_validation_allows_update(_failed_result())
        with pytest.raises(DomainValidationBlocked):
            ensure_domain_validation_allows_update(
                _passing_result(status=DomainValidationStatus.PENDING)
            )


class TestUpdateAtomicity:
    def test_failed_update_validation_preserves_previous_domain_atomically(
        self, tmp_path
    ) -> None:
        registry = DomainRegistry()
        loader = DeclarativeDomainLoader(
            manifest_reader=JsonDomainManifestReader(),
            registry=registry,
        )
        # Version A loads successfully.
        dir_a = write_domain_dir(tmp_path / "packs", "greeter", "1.0.0")
        cand_a = make_candidate(dir_a, "greeter", "1.0.0")
        loaded_a = loader.load(cand_a)
        from cmm.domains.enums import DomainLoadStatus

        assert loaded_a.status == DomainLoadStatus.LOADED

        # Candidate B fails canonical validation: gate blocks before any
        # registry mutation, so version A remains effective and no partial
        # version B registration remains.
        failing = _failed_result()
        with pytest.raises(DomainValidationBlocked):
            ensure_domain_validation_allows_update(failing)

        # No reload attempted: previous state intact.
        assert registry.get("greeter", "1.0.0") is not None
        assert loader.get_loaded("domain:greeter", "1.0.0") is not None
        # No partial B state.
        assert registry.get("greeter", "2.0.0") is None

    def test_loader_reload_preserves_previous_on_build_failure(self, tmp_path) -> None:
        # Existing atomic loader behavior reused: a broken candidate never
        # partially replaces the active domain.
        registry = DomainRegistry()
        loader = DeclarativeDomainLoader(
            manifest_reader=JsonDomainManifestReader(),
            registry=registry,
        )
        dir_a = write_domain_dir(tmp_path / "atomic", "keeper", "1.0.0")
        cand_a = make_candidate(dir_a, "keeper", "1.0.0")
        from cmm.domains.enums import DomainLoadStatus

        assert loader.load(cand_a).status == DomainLoadStatus.LOADED

        dir_b = write_domain_dir(tmp_path / "atomic2", "keeper", "2.0.0")
        cand_b = make_candidate(dir_b, "keeper", "2.0.0")
        # Tamper after checksum so build fails.
        (dir_b / "manifest.json").write_text(
            json.dumps(
                {
                    "id": "keeper",
                    "version": "9.9.9",
                    "author": "x",
                    "license": "MIT",
                }
            ),
            encoding="utf-8",
        )
        from cmm.domains.errors import DomainChecksumMismatch

        with pytest.raises(DomainChecksumMismatch):
            loader.reload(cand_b)
        # Previous version still effective.
        assert registry.get("keeper", "1.0.0") is not None
