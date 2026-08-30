"""Phase 10.36 — Domain API lifecycle tests.

Proves discover/validate/install/enable/disable delegate to canonical
components and that install != enable, install != authorization, discovery
does not register, and validation does not register.
"""

from __future__ import annotations

from pathlib import Path

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


def _make_api(
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


def _source(root: Path) -> DomainSource:
    return DomainSource(
        source_id="api-test-source",
        kind=DomainSourceKind.DIRECTORY,
        location=str(root),
        trusted=True,
        recursive=False,
    )


class TestDiscovery:
    def test_discover_returns_canonical_result(self, tmp_path: Path) -> None:
        api, _ = _make_api()
        write_domain_dir(tmp_path, "greeter", "1.0.0")
        result = api.discover_domains((_source(tmp_path),))
        assert [c.domain_id for c in result.candidates] == ["domain:greeter"]

    def test_discovery_does_not_register(self, tmp_path: Path) -> None:
        api, registry = _make_api()
        write_domain_dir(tmp_path, "greeter", "1.0.0")
        before = registry.snapshot_state()
        api.discover_domains((_source(tmp_path),))
        assert registry.snapshot_state() == before
        assert registry.contains("greeter") is False


class TestValidation:
    def _pack_and_request(self, tmp_path: Path):
        from cmm.domains.pack import DomainPack, ParsedDomainPack

        domain_dir = write_domain_dir(tmp_path, "greeter", "1.0.0")
        candidate = make_candidate(domain_dir, "greeter", "1.0.0")
        manifest_doc = JsonDomainManifestReader().read_document(
            domain_dir / "manifest.json"
        )
        parsed = ParsedDomainPack.from_declarative_dict(manifest_doc.data)
        pack = DomainPack(
            definition=parsed.definition,
            manifest=parsed.manifest,
            root_path=str(domain_dir),
        )
        request = DomainValidationRequest(
            pack=pack,
            root_path=str(domain_dir),
            candidate=candidate,
            strict=False,
            run_tests=False,
        )
        return request

    def test_validate_returns_canonical_result(self, tmp_path: Path) -> None:
        api, _ = _make_api()
        request = self._pack_and_request(tmp_path)
        result = api.validate_domain(request)
        assert result.domain_id == "domain:greeter"
        assert result.version == "1.0.0"
        assert result.manifest_valid is True

    def test_validation_does_not_register(self, tmp_path: Path) -> None:
        api, registry = _make_api()
        request = self._pack_and_request(tmp_path)
        before = registry.snapshot_state()
        api.validate_domain(request)
        assert registry.snapshot_state() == before
        assert registry.contains("greeter") is False


class TestInstall:
    def test_install_uses_canonical_loader_path(self, tmp_path: Path) -> None:
        api, registry = _make_api()
        domain_dir = write_domain_dir(tmp_path, "greeter", "1.0.0")
        candidate = make_candidate(domain_dir, "greeter", "1.0.0")
        result = api.install_domain(candidate)
        assert result.status == DomainLoadStatus.LOADED
        assert registry.get("greeter", "1.0.0") is not None

    def test_install_does_not_implicitly_enable(self, tmp_path: Path) -> None:
        api, registry = _make_api()
        domain_dir = write_domain_dir(tmp_path, "greeter", "1.0.0")
        candidate = make_candidate(domain_dir, "greeter", "1.0.0")
        api.install_domain(candidate)
        record = registry.get_record("greeter", "1.0.0")
        assert record is not None
        assert record.status == DomainStatus.REGISTERED
        assert record.definition.enabled is False

    def test_untrusted_install_remains_fail_closed(self, tmp_path: Path) -> None:
        api, registry = _make_api()
        domain_dir = write_domain_dir(tmp_path, "greeter", "1.0.0")
        candidate = make_candidate(domain_dir, "greeter", "1.0.0", trusted=False)
        with pytest.raises(DomainSourceUntrusted):
            api.install_domain(candidate)
        assert registry.contains("greeter") is False

    def test_untrusted_install_with_explicit_opt_in_loads(self, tmp_path: Path) -> None:
        api, _ = _make_api()
        domain_dir = write_domain_dir(tmp_path, "greeter", "1.0.0")
        candidate = make_candidate(domain_dir, "greeter", "1.0.0", trusted=False)
        result = api.install_domain(candidate, allow_untrusted=True)
        assert result.status == DomainLoadStatus.LOADED


class TestEnableDisable:
    def _installed_api(self, tmp_path: Path):
        api, registry = _make_api()
        domain_dir = write_domain_dir(tmp_path, "greeter", "1.0.0")
        candidate = make_candidate(domain_dir, "greeter", "1.0.0")
        api.install_domain(candidate)
        return api, registry

    def test_enable_is_separate_explicit_call(self, tmp_path: Path) -> None:
        api, registry = self._installed_api(tmp_path)
        assert registry.get_record("greeter").status == DomainStatus.REGISTERED
        definition = api.enable_domain("greeter")
        assert definition.enabled is True
        assert registry.get_record("greeter").status == DomainStatus.ACTIVE

    def test_disable_is_separate_explicit_call(self, tmp_path: Path) -> None:
        api, registry = self._installed_api(tmp_path)
        api.enable_domain("greeter")
        definition = api.disable_domain("greeter")
        assert definition.enabled is False
        assert registry.get_record("greeter").status == DomainStatus.DISABLED

    def test_enable_missing_domain_raises_canonical_error(self, tmp_path: Path) -> None:
        api, _ = self._installed_api(tmp_path)
        from cmm.domains.errors import DomainRegistryNotFound

        with pytest.raises(DomainRegistryNotFound):
            api.enable_domain("missing")
