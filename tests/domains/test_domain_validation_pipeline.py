"""Phase 10.5 – Tests for pipeline integration and step ordering."""

from __future__ import annotations

import pytest

from cmm.domains.errors import DomainValidationStepMissing
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
    _resolve_transitive_deps,
    build_domain_validation_steps,
)


class DummyPack:
    def __init__(self, domain_id="domain:test", version="1.0.0"):
        self.id = domain_id
        self.version = version
        self.manifest = None
        self.definition = None


class TestTransitiveDeps:
    """DFS transitive dependency resolution."""

    def test_security_includes_all_deps(self) -> None:
        resolved = _resolve_transitive_deps((STEP_SECURITY,), ())
        assert STEP_MANIFEST in resolved
        assert STEP_CONTRACTS in resolved
        assert STEP_PERMISSIONS in resolved
        assert STEP_SECURITY in resolved
        # Should not include steps that are NOT transitive deps
        assert STEP_TESTS not in resolved
        assert STEP_FRAGMENTATION not in resolved

    def test_tests_includes_all_deps(self) -> None:
        resolved = _resolve_transitive_deps((STEP_TESTS,), ())
        assert STEP_MANIFEST in resolved
        assert STEP_CONTRACTS in resolved
        assert STEP_PERMISSIONS in resolved
        assert STEP_SECURITY in resolved
        assert STEP_TESTS in resolved
        # fragmentation is NOT a transitive dep of tests
        assert STEP_FRAGMENTATION not in resolved

    def test_fragmentation_subset(self) -> None:
        resolved = _resolve_transitive_deps((STEP_FRAGMENTATION,), ())
        assert STEP_MANIFEST in resolved
        assert STEP_CONTRACTS in resolved
        assert STEP_FRAGMENTATION in resolved
        assert STEP_SECURITY not in resolved
        assert STEP_TESTS not in resolved

    def test_transitive_excluded_rejected(self) -> None:
        with pytest.raises(DomainValidationStepMissing):
            _resolve_transitive_deps((STEP_SECURITY,), (STEP_CONTRACTS,))

    def test_deterministic_order(self) -> None:
        pack = DummyPack()
        request = DomainValidationRequest(
            pack=pack,
            root_path="/tmp",
            requested_steps=(STEP_TESTS, STEP_MANIFEST),
        )
        steps = build_domain_validation_steps(request)
        names = [s.name for s in steps]
        # All steps present
        for n in (
            STEP_MANIFEST,
            STEP_CONTRACTS,
            STEP_PERMISSIONS,
            STEP_SECURITY,
            STEP_TESTS,
        ):
            assert n in names
        # No extra steps
        assert STEP_FRAGMENTATION not in names
        assert STEP_COMPATIBILITY not in names
        assert STEP_DEPENDENCIES not in names
        # Ordered
        assert names == sorted(names, key=lambda n: ALL_DOMAIN_STEPS.index(n))

    def test_no_extra_steps_in_requested_subset(self) -> None:
        pack = DummyPack()
        request = DomainValidationRequest(
            pack=pack,
            root_path="/tmp",
            requested_steps=(STEP_MANIFEST, STEP_SECURITY),
        )
        steps = build_domain_validation_steps(request)
        names = {s.name for s in steps}
        # Contains manifest, contracts, permissions, security (transitive)
        assert names == {STEP_MANIFEST, STEP_CONTRACTS, STEP_PERMISSIONS, STEP_SECURITY}
        # Not present: tests, fragmentation, compatibility, dependencies
        assert STEP_TESTS not in names
        assert STEP_FRAGMENTATION not in names
        assert STEP_COMPATIBILITY not in names
        assert STEP_DEPENDENCIES not in names


class TestRequiredPolicy:
    """required policy correctly set."""

    def test_requested_steps_are_required(self) -> None:
        pack = DummyPack()
        request = DomainValidationRequest(
            pack=pack,
            root_path="/tmp",
            requested_steps=(STEP_SECURITY,),
        )
        steps = build_domain_validation_steps(request)
        for s in steps:
            if s.name == STEP_SECURITY:
                assert s.required is True
            else:
                assert s.required is False

    def test_all_steps_in_full_mode_are_required(self) -> None:
        pack = DummyPack()
        request = DomainValidationRequest(pack=pack, root_path="/tmp")
        steps = build_domain_validation_steps(request)
        for s in steps:
            assert s.required is True
