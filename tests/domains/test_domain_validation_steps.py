"""Phase 10.5 – Tests for domain validation step builder."""

from __future__ import annotations

import pytest

from cmm.domains.validation_contracts import DomainValidationRequest
from cmm.domains.validation_steps import (
    ALL_DOMAIN_STEPS,
    STEP_COMPATIBILITY,
    STEP_CONTRACTS,
    STEP_DEPENDENCIES,
    STEP_FRAGMENTATION,
    STEP_MANIFEST,
    STEP_PERMISSIONS,
    STEP_SECURITY,
    STEP_TESTS,
    build_domain_validation_steps,
)
from cmm.validation.steps import ValidationStepType


class DummyPack:
    def __init__(self, domain_id="domain:test", version="1.0.0"):
        self.id = domain_id
        self.version = version
        self.manifest = None
        self.definition = None


class TestBuildDomainValidationSteps:
    def test_all_eight_steps_in_order(self) -> None:
        pack = DummyPack()
        request = DomainValidationRequest(pack=pack, root_path="/tmp")
        steps = build_domain_validation_steps(request)

        assert len(steps) == 8
        assert steps[0].name == STEP_MANIFEST
        assert steps[1].name == STEP_CONTRACTS
        assert steps[2].name == STEP_PERMISSIONS
        assert steps[3].name == STEP_DEPENDENCIES
        assert steps[4].name == STEP_COMPATIBILITY
        assert steps[5].name == STEP_SECURITY
        assert steps[6].name == STEP_FRAGMENTATION
        assert steps[7].name == STEP_TESTS

    def test_all_steps_are_internal(self) -> None:
        pack = DummyPack()
        request = DomainValidationRequest(pack=pack, root_path="/tmp")
        steps = build_domain_validation_steps(request)

        for step in steps:
            assert step.step_type == ValidationStepType.INTERNAL

    def test_manifest_has_no_dependencies(self) -> None:
        pack = DummyPack()
        request = DomainValidationRequest(pack=pack, root_path="/tmp")
        steps = build_domain_validation_steps(request)

        manifest_step = next(s for s in steps if s.name == STEP_MANIFEST)
        assert manifest_step.dependencies == ()

    def test_contracts_depends_manifest(self) -> None:
        pack = DummyPack()
        request = DomainValidationRequest(pack=pack, root_path="/tmp")
        steps = build_domain_validation_steps(request)

        contracts = next(s for s in steps if s.name == STEP_CONTRACTS)
        assert STEP_MANIFEST in contracts.dependencies

    def test_security_depends_contracts_and_permissions(self) -> None:
        pack = DummyPack()
        request = DomainValidationRequest(pack=pack, root_path="/tmp")
        steps = build_domain_validation_steps(request)

        security = next(s for s in steps if s.name == STEP_SECURITY)
        assert STEP_CONTRACTS in security.dependencies
        assert STEP_PERMISSIONS in security.dependencies

    def test_fragmentation_depends_contracts(self) -> None:
        pack = DummyPack()
        request = DomainValidationRequest(pack=pack, root_path="/tmp")
        steps = build_domain_validation_steps(request)

        fragmentation = next(s for s in steps if s.name == STEP_FRAGMENTATION)
        assert STEP_CONTRACTS in fragmentation.dependencies

    def test_tests_depends_contracts_and_security(self) -> None:
        pack = DummyPack()
        request = DomainValidationRequest(pack=pack, root_path="/tmp")
        steps = build_domain_validation_steps(request)

        tests = next(s for s in steps if s.name == STEP_TESTS)
        assert STEP_CONTRACTS in tests.dependencies
        assert STEP_SECURITY in tests.dependencies

    def test_strict_mode_all_required(self) -> None:
        pack = DummyPack()
        request = DomainValidationRequest(pack=pack, root_path="/tmp", strict=True)
        steps = build_domain_validation_steps(request)

        for step in steps:
            assert step.required is True, (
                f"{step.name} should be required in strict mode"
            )

    def test_non_strict_tests_optional_when_run_tests_false(self) -> None:
        pack = DummyPack()
        request = DomainValidationRequest(
            pack=pack, root_path="/tmp", strict=False, run_tests=False
        )
        steps = build_domain_validation_steps(request)

        tests = next(s for s in steps if s.name == STEP_TESTS)
        assert tests.required is False

        # All other steps remain required
        for step in steps:
            if step.name != STEP_TESTS:
                assert step.required is True

    def test_requested_steps_subset(self) -> None:
        pack = DummyPack()
        request = DomainValidationRequest(
            pack=pack,
            root_path="/tmp",
            requested_steps=(STEP_MANIFEST, STEP_SECURITY),
        )
        steps = build_domain_validation_steps(request)

        manifest = next(s for s in steps if s.name == STEP_MANIFEST)
        security = next(s for s in steps if s.name == STEP_SECURITY)
        assert manifest.required is True
        assert security.required is True

        # Steps not in requested should not be required
        for step in steps:
            if step.name not in (STEP_MANIFEST, STEP_SECURITY):
                assert step.required is False

    def test_excluded_steps(self) -> None:
        pack = DummyPack()
        request = DomainValidationRequest(
            pack=pack,
            root_path="/tmp",
            excluded_steps=(STEP_TESTS,),
            run_tests=False,
        )
        steps = build_domain_validation_steps(request)

        # domain.tests is excluded (not present)
        assert not any(s.name == STEP_TESTS for s in steps)

        # All other steps remain
        assert len(steps) == 7

    def test_excluded_strict_mandatory_rejected(self) -> None:
        """Excluding mandatory step in strict mode raises."""
        from cmm.domains.errors import DomainValidationRequestInvalid

        pack = DummyPack()
        request = DomainValidationRequest(
            pack=pack,
            root_path="/tmp",
            excluded_steps=(STEP_MANIFEST,),
            strict=True,
        )
        with pytest.raises(DomainValidationRequestInvalid):
            build_domain_validation_steps(request)

    def test_excluded_tests_strict_run_tests_true_rejected(self) -> None:
        """Excluding domain.tests with strict=True and run_tests=True raises."""
        from cmm.domains.errors import DomainValidationRequestInvalid

        pack = DummyPack()
        request = DomainValidationRequest(
            pack=pack,
            root_path="/tmp",
            excluded_steps=(STEP_TESTS,),
            strict=True,
            run_tests=True,
        )
        with pytest.raises(DomainValidationRequestInvalid):
            build_domain_validation_steps(request)

    def test_all_domain_steps_constant(self) -> None:
        assert len(ALL_DOMAIN_STEPS) == 8
        assert STEP_MANIFEST in ALL_DOMAIN_STEPS
        assert STEP_TESTS in ALL_DOMAIN_STEPS
