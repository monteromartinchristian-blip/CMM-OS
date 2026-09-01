"""Phase 10.38 — Domain trust lifecycle tests (RED target for Task 4).

Proves that explicit activation through ``DefaultDomainAPI.enable_domain``
is guarded by the trust boundary:

- external/non-internal candidates without an explicit trust policy fail closed;
- ``candidate.trusted=True`` is not authority for non-internal sources;
- ``BLOCKED``/signature-required/stale-validation reject before registry mutation;
- trusted INTERNAL candidates with no policy preserve Phase 10.36 behavior;
- rejection leaves no partial enabled/authorization state.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from cmm.domains.api import DefaultDomainAPI
from cmm.domains.discovery import FileSystemDomainDiscovery
from cmm.domains.discovery_contracts import DomainSource
from cmm.domains.enums import (
    DomainLoadStatus,
    DomainSourceKind,
    DomainTrustLevel,
)
from cmm.domains.errors import DomainError
from cmm.domains.loader import DeclarativeDomainLoader
from cmm.domains.manifest_reader import JsonDomainManifestReader
from cmm.domains.registry import DomainRegistry
from cmm.domains.trust_contracts import DomainTrustPolicy
from cmm.domains.validation import PipelineDomainValidator
from cmm.domains.validation_contracts import DomainValidationRequest
from tests.domains._loader_helpers import make_candidate, write_domain_dir
from tests.domains.test_domain_api_contracts import _make_collaborators


def _make_api(
    registry: DomainRegistry | None = None,
    *,
    trust_policy_lookup=None,
) -> tuple[DefaultDomainAPI, DomainRegistry]:
    registry = registry or DomainRegistry()
    collaborators = _make_collaborators()
    collaborators["domain_registry"] = registry
    collaborators["loader"] = DeclarativeDomainLoader(
        manifest_reader=JsonDomainManifestReader(), registry=registry
    )
    collaborators["discovery"] = FileSystemDomainDiscovery()
    collaborators["validator"] = PipelineDomainValidator()
    if trust_policy_lookup is not None:
        collaborators["trust_policy_lookup"] = trust_policy_lookup
    return DefaultDomainAPI(**collaborators), registry


def _source(root: Path, *, trusted: bool = True) -> DomainSource:
    return DomainSource(
        source_id="lifecycle-source",
        kind=DomainSourceKind.DIRECTORY,
        location=str(root),
        trusted=trusted,
        recursive=False,
    )


def _write_pack(
    root: Path,
    slug: str,
    version: str,
    *,
    signature: bool = False,
) -> Path:
    """Write a minimal pack that passes strict canonical validation."""
    import json

    domain_dir = write_domain_dir(root, slug, version)
    if signature:
        manifest_file = domain_dir / "manifest.json"
        data = json.loads(manifest_file.read_text(encoding="utf-8"))
        data["signature"] = "base64-presence-not-verified"
        manifest_file.write_text(json.dumps(data), encoding="utf-8")
    test_dir = domain_dir / "tests"
    test_dir.mkdir(parents=True, exist_ok=True)
    (test_dir / "test_domain.py").write_text(
        "def test_placeholder():\n    assert True\n", encoding="utf-8"
    )
    return domain_dir


class TestExternalActivationRequiresPolicy:
    def test_external_candidate_without_policy_fails_closed(
        self, tmp_path: Path
    ) -> None:
        api, registry = _make_api()
        domain_dir = _write_pack(tmp_path, "ext", "1.0.0")
        candidate = make_candidate(
            domain_dir,
            "ext",
            "1.0.0",
            trusted=True,
            source_id="lifecycle-source",
        )
        result = api.install_domain(candidate)
        assert result.status == DomainLoadStatus.LOADED
        before = registry.snapshot_state()
        with pytest.raises(DomainError):
            api.enable_domain("ext", "1.0.0")
        assert registry.snapshot_state() == before
        assert registry.get("ext", "1.0.0").enabled is False

    def test_trusted_bool_is_not_authority_for_directory_source(
        self, tmp_path: Path
    ) -> None:
        api, registry = _make_api()
        domain_dir = _write_pack(tmp_path, "ext", "1.0.0")
        candidate = make_candidate(
            domain_dir,
            "ext",
            "1.0.0",
            trusted=True,
            source_id="lifecycle-source",
        )
        api.install_domain(candidate)
        before = registry.snapshot_state()
        with pytest.raises(DomainError):
            api.enable_domain("ext", "1.0.0")
        assert registry.snapshot_state() == before
        assert registry.get("ext", "1.0.0").enabled is False


class TestExplicitPolicySafePath:
    def _policy(self, *, trust_level=DomainTrustLevel.COMMUNITY) -> DomainTrustPolicy:
        return DomainTrustPolicy(
            domain_id="domain:ext",
            trust_level=trust_level,
            authorized_source_ids=("lifecycle-source",),
            allow_code_execution=True,
        )

    def test_explicit_policy_safe_activation(self, tmp_path: Path) -> None:
        api, registry = _make_api(trust_policy_lookup=lambda _: self._policy())
        domain_dir = write_domain_dir(tmp_path, "ext", "1.0.0")
        candidate = make_candidate(
            domain_dir,
            "ext",
            "1.0.0",
            trusted=True,
            source_id="lifecycle-source",
        )
        result = api.install_domain(candidate)
        assert result.status == DomainLoadStatus.LOADED
        definition = api.enable_domain("ext", "1.0.0")
        assert definition.enabled is True
        assert registry.get("ext", "1.0.0").enabled is True

    def test_activation_only_happens_on_explicit_enable(self, tmp_path: Path) -> None:
        api, registry = _make_api(trust_policy_lookup=lambda _: self._policy())
        domain_dir = write_domain_dir(tmp_path, "ext", "1.0.0")
        candidate = make_candidate(
            domain_dir,
            "ext",
            "1.0.0",
            trusted=False,
            source_id="lifecycle-source",
        )
        result = api.install_domain(candidate, allow_untrusted=True)
        assert result.status == DomainLoadStatus.LOADED
        # Discovery/load never enable: registry still not enabled.
        assert registry.get("ext", "1.0.0").enabled is False


class TestBlockedPolicy:
    def test_blocked_denies_even_with_trusted_candidate_and_matching_source(
        self, tmp_path: Path
    ) -> None:
        api, registry = _make_api(
            trust_policy_lookup=lambda _: DomainTrustPolicy(
                domain_id="domain:ext",
                trust_level=DomainTrustLevel.BLOCKED,
                authorized_source_ids=("lifecycle-source",),
            )
        )
        domain_dir = _write_pack(tmp_path, "ext", "1.0.0")
        candidate = make_candidate(
            domain_dir,
            "ext",
            "1.0.0",
            trusted=True,
            source_id="lifecycle-source",
        )
        result = api.install_domain(candidate)
        assert result.status == DomainLoadStatus.LOADED
        before = registry.snapshot_state()
        with pytest.raises(DomainError) as excinfo:
            api.enable_domain("ext", "1.0.0")
        assert "trust.blocked" in excinfo.value.details["reason_codes"]
        assert registry.snapshot_state() == before
        assert registry.get("ext", "1.0.0").enabled is False


class TestSignatureRequired:
    def _policy(self) -> DomainTrustPolicy:
        return DomainTrustPolicy(
            domain_id="domain:ext",
            trust_level=DomainTrustLevel.COMMUNITY,
            authorized_source_ids=("lifecycle-source",),
            require_signature=True,
        )

    def test_signature_required_missing_fails_closed(self, tmp_path: Path) -> None:
        api, registry = _make_api(trust_policy_lookup=lambda _: self._policy())
        domain_dir = _write_pack(tmp_path, "ext", "1.0.0")
        candidate = make_candidate(
            domain_dir,
            "ext",
            "1.0.0",
            trusted=True,
            source_id="lifecycle-source",
        )
        api.install_domain(candidate)
        before = registry.snapshot_state()
        with pytest.raises(DomainError) as excinfo:
            api.enable_domain("ext", "1.0.0")
        assert "trust.signature_required" in excinfo.value.details["reason_codes"]
        assert registry.snapshot_state() == before
        assert registry.get("ext", "1.0.0").enabled is False

    def test_signature_present_satisfies_presence_only(self, tmp_path: Path) -> None:
        api, _ = _make_api(trust_policy_lookup=lambda _: self._policy())
        domain_dir = _write_pack(tmp_path, "ext", "1.0.0", signature=True)
        candidate = make_candidate(
            domain_dir,
            "ext",
            "1.0.0",
            trusted=True,
            source_id="lifecycle-source",
        )
        api.install_domain(candidate)
        definition = api.enable_domain("ext", "1.0.0")
        assert definition.enabled is True


class TestStaleValidation:
    def test_stale_validation_fails_closed(self, tmp_path: Path) -> None:
        # A validator that returns a stale (wrong-version) canonical result
        # must fail activation; trust never accepts stale validation.
        class _StaleValidator:
            def validate(self, request: DomainValidationRequest):
                from cmm.domains.enums import DomainValidationStatus
                from cmm.domains.validation_contracts import DomainValidationResult

                return DomainValidationResult(
                    domain_id=request.candidate.domain_id,
                    version="9.9.9",  # stale version mismatch
                    status=DomainValidationStatus.PASSED,
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
                )

        api, registry = _make_api(
            trust_policy_lookup=lambda _: DomainTrustPolicy(
                domain_id="domain:ext",
                trust_level=DomainTrustLevel.COMMUNITY,
                authorized_source_ids=("lifecycle-source",),
            )
        )
        # Rebind the validator to the stale one after construction.
        api._validator = _StaleValidator()  # type: ignore[assignment]
        domain_dir = _write_pack(tmp_path, "ext", "1.0.0")
        candidate = make_candidate(
            domain_dir,
            "ext",
            "1.0.0",
            trusted=True,
            source_id="lifecycle-source",
        )
        api.install_domain(candidate)
        before = registry.snapshot_state()
        with pytest.raises(DomainError) as excinfo:
            api.enable_domain("ext", "1.0.0")
        assert "trust.validation_failed" in excinfo.value.details["reason_codes"]
        assert registry.snapshot_state() == before
        assert registry.get("ext", "1.0.0").enabled is False


class TestInternalCompatibility:
    def test_trusted_internal_candidate_without_policy_preserves_phase1036(
        self, tmp_path: Path
    ) -> None:
        api, _ = _make_api()
        domain_dir = _write_pack(tmp_path, "internal", "1.0.0")
        candidate = make_candidate(
            domain_dir,
            "internal",
            "1.0.0",
            trusted=True,
            source_id="s1",
        )
        # Force the source kind to INTERNAL.
        from dataclasses import replace

        candidate = replace(candidate, source_kind=DomainSourceKind.INTERNAL)
        result = api.install_domain(candidate)
        assert result.status == DomainLoadStatus.LOADED
        definition = api.enable_domain("internal", "1.0.0")
        assert definition.enabled is True

    def test_internal_source_with_explicit_policy_applies_policy(
        self, tmp_path: Path
    ) -> None:
        from dataclasses import replace

        api, registry = _make_api(
            trust_policy_lookup=lambda _: DomainTrustPolicy(
                domain_id="domain:internal",
                trust_level=DomainTrustLevel.BLOCKED,
                authorized_source_ids=("s1",),
            )
        )
        domain_dir = _write_pack(tmp_path, "internal", "1.0.0")
        candidate = make_candidate(
            domain_dir,
            "internal",
            "1.0.0",
            trusted=True,
            source_id="s1",
        )
        candidate = replace(candidate, source_kind=DomainSourceKind.INTERNAL)
        api.install_domain(candidate)
        before = registry.snapshot_state()
        with pytest.raises(DomainError) as excinfo:
            api.enable_domain("internal", "1.0.0")
        assert "trust.blocked" in excinfo.value.details["reason_codes"]
        assert registry.snapshot_state() == before


class TestNoPartialState:
    def test_rejection_leaves_loaded_state_coherent(self, tmp_path: Path) -> None:
        api, _ = _make_api()  # no trust lookup: external load+enable must fail
        domain_dir = _write_pack(tmp_path, "ext", "1.0.0")
        candidate = make_candidate(domain_dir, "ext", "1.0.0", trusted=True)
        result = api.install_domain(candidate)
        assert result.status == DomainLoadStatus.LOADED
        with pytest.raises(DomainError):
            api.enable_domain("ext", "1.0.0")
        # Loaded state remains coherent and the pack is still queryable.
        assert api.get_domain("ext", "1.0.0") is not None
        assert api.get_domain("ext", "1.0.0").enabled is False
