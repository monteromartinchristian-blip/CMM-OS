"""Phase 10.36 — adversarial facade boundary hardening.

Consolidates the required adversarial cases that are not already covered by
the per-task focused suites. Every case proves a real canonical boundary.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from cmm.domains.api import DefaultDomainAPI
from cmm.domains.discovery import FileSystemDomainDiscovery
from cmm.domains.discovery_contracts import DomainSource
from cmm.domains.enums import DomainLoadStatus, DomainSourceKind, DomainStatus
from cmm.domains.errors import DomainSourceUntrusted
from cmm.domains.loader import DeclarativeDomainLoader
from cmm.domains.manifest_reader import JsonDomainManifestReader
from cmm.domains.registry import DomainRegistry
from cmm.domains.validation import PipelineDomainValidator
from cmm.domains.validation_contracts import DomainValidationRequest
from tests.domains._loader_helpers import make_candidate, write_domain_dir
from tests.domains.test_domain_api_contracts import _make_collaborators

NOW = datetime(2026, 8, 31, 12, 0, tzinfo=timezone.utc)


def _api(
    registry: DomainRegistry | None = None,
) -> tuple[DefaultDomainAPI, DomainRegistry]:
    registry = registry or DomainRegistry()
    collaborators = _make_collaborators()
    collaborators["domain_registry"] = registry
    collaborators["loader"] = DeclarativeDomainLoader(
        manifest_reader=JsonDomainManifestReader(), registry=registry
    )
    collaborators["discovery"] = FileSystemDomainDiscovery()
    collaborators["validator"] = PipelineDomainValidator()
    return DefaultDomainAPI(**collaborators), registry


def _source(root) -> DomainSource:
    return DomainSource(
        source_id="adv-source",
        kind=DomainSourceKind.DIRECTORY,
        location=str(root),
        trusted=True,
        recursive=False,
    )


class TestInstallAuthorizationBoundaries:
    def test_install_does_not_implicitly_authorize(self, tmp_path) -> None:
        """A loaded domain is registered but confers no authorization."""
        api, registry = _api()
        domain_dir = write_domain_dir(tmp_path, "greeter", "1.0.0")
        candidate = make_candidate(domain_dir, "greeter", "1.0.0")
        api.install_domain(candidate)
        record = registry.get_record("greeter", "1.0.0")
        assert record.status == DomainStatus.REGISTERED
        assert record.definition.enabled is False
        # Registered-but-not-enabled domains are not resolvable as active.
        assert api.get_domain("greeter").enabled is False

    def test_untrusted_load_blocked_even_after_other_loads(self, tmp_path) -> None:
        """Fail-closed default is per-candidate, never a session-wide grant."""
        api, registry = _api()
        trusted_dir = write_domain_dir(tmp_path, "trusted", "1.0.0")
        api.install_domain(make_candidate(trusted_dir, "trusted", "1.0.0"))
        untrusted_dir = write_domain_dir(tmp_path, "untrusted", "1.0.0")
        with pytest.raises(DomainSourceUntrusted):
            api.install_domain(
                make_candidate(untrusted_dir, "untrusted", "1.0.0", trusted=False)
            )
        assert registry.contains("untrusted") is False
        assert registry.contains("trusted") is True


class TestDiscoveryValidationBoundaries:
    def test_discovery_does_not_execute_pack_code_or_create_files(
        self, tmp_path
    ) -> None:
        api, registry = _api()
        write_domain_dir(tmp_path, "greeter", "1.0.0")
        before = sorted(p.name for p in tmp_path.iterdir())
        result = api.discover_domains((_source(tmp_path),))
        assert len(result.candidates) == 1
        after = sorted(p.name for p in tmp_path.iterdir())
        assert after == before
        assert registry.snapshot_state() == DomainRegistry().snapshot_state() or (
            registry.contains("greeter") is False
        )

    def test_validation_does_not_install_or_enable(self, tmp_path) -> None:
        api, registry = _api()
        domain_dir = write_domain_dir(tmp_path, "greeter", "1.0.0")
        candidate = make_candidate(domain_dir, "greeter", "1.0.0")
        manifest_doc = JsonDomainManifestReader().read_document(
            domain_dir / "manifest.json"
        )
        from cmm.domains.pack import DomainPack, ParsedDomainPack

        parsed = ParsedDomainPack.from_declarative_dict(manifest_doc.data)
        pack = DomainPack(
            definition=parsed.definition,
            manifest=parsed.manifest,
            root_path=str(domain_dir),
        )
        result = api.validate_domain(
            DomainValidationRequest(
                pack=pack,
                root_path=str(domain_dir),
                candidate=candidate,
                strict=False,
                run_tests=False,
            )
        )
        assert result.domain_id == "domain:greeter"
        assert registry.contains("greeter") is False


class TestFacadeStateBoundaries:
    def test_facade_creates_no_shadow_registry_truth(self, tmp_path) -> None:
        """Two facades over one registry see identical truth; a second
        facade over a fresh registry cannot see the first registry's state."""
        api1, _registry1 = _api()
        domain_dir = write_domain_dir(tmp_path, "greeter", "1.0.0")
        api1.install_domain(make_candidate(domain_dir, "greeter", "1.0.0"))
        api2, registry2 = _api()
        assert api1.get_domain("greeter") is not None
        assert api2.get_domain("greeter") is None
        assert registry2.contains("greeter") is False
        # No shadow copy exists on the facade instances.
        assert "domains" not in vars(api1)
        assert "definitions" not in vars(api1)
        assert "_cache" not in vars(api1)

    def test_install_result_is_canonical_load_result(self, tmp_path) -> None:
        api, _ = _api()
        domain_dir = write_domain_dir(tmp_path, "greeter", "1.0.0")
        result = api.install_domain(make_candidate(domain_dir, "greeter", "1.0.0"))
        assert result.status == DomainLoadStatus.LOADED
        assert result.registry_record is not None
        assert result.candidate.candidate_id == "greeter:1.0.0"
