"""Phase 10.1 – Tests for public API exports from cmm.domains."""

from __future__ import annotations

import cmm.domains


class TestPublicAPI:
    """Verify that all public symbols are exported from cmm.domains."""

    def test_errors_exported(self) -> None:
        assert hasattr(cmm.domains, "DomainError")
        assert hasattr(cmm.domains, "DomainContractError")
        assert hasattr(cmm.domains, "DomainContractValidationError")
        assert hasattr(cmm.domains, "DomainSerializationError")

    def test_enums_exported(self) -> None:
        assert hasattr(cmm.domains, "DomainStatus")
        assert hasattr(cmm.domains, "DomainKind")
        assert hasattr(cmm.domains, "DomainPackKind")
        assert hasattr(cmm.domains, "DomainPackStatus")

    def test_identifiers_exported(self) -> None:
        assert hasattr(cmm.domains, "DomainId")
        assert hasattr(cmm.domains, "DomainManifestId")
        assert hasattr(cmm.domains, "DomainResultId")

    def test_contracts_exported(self) -> None:
        assert hasattr(cmm.domains, "DomainMetadata")
        assert hasattr(cmm.domains, "DomainCapability")
        assert hasattr(cmm.domains, "DomainDependency")
        assert hasattr(cmm.domains, "DomainConflict")
        assert hasattr(cmm.domains, "DomainDefinition")
        assert hasattr(cmm.domains, "DomainResult")
        assert hasattr(cmm.domains, "DomainManifest")
        assert hasattr(cmm.domains, "DomainComponentReference")
        assert hasattr(cmm.domains, "DomainPermissionReference")
        assert hasattr(cmm.domains, "DomainCompatibility")
        assert hasattr(cmm.domains, "DomainPack")
        assert hasattr(cmm.domains, "ParsedDomainPack")

    def test_all_symbols_in_all(self) -> None:
        """Check that all expected symbols are in __all__."""
        expected = {
            "DeclarativeDomainLoader",
            "DomainCandidate",
            "DomainCandidateInvalid",
            "DomainCapability",
            "DomainCapabilityConflict",
            "DomainChecksumMismatch",
            "DomainCompatibility",
            "DomainComponentReference",
            "DomainConflict",
            "DomainContractError",
            "DomainContractValidationError",
            "DomainDefinition",
            "DomainDefinitionRegistryValidator",
            "DomainDependency",
            "DomainDependencyMissing",
            "DomainDiscovery",
            "DomainDiscoveryError",
            "DomainDiscoveryIssue",
            "DomainDiscoveryResult",
            "DomainDiscoverySourceError",
            "DomainError",
            "DomainId",
            "DomainKind",
            "DomainLoadFailed",
            "DomainLoadRejected",
            "DomainLoadResult",
            "DomainLoadRollbackFailed",
            "DomainLoadStatus",
            "DomainLoader",
            "DomainLoaderError",
            "DomainLoaderSnapshot",
            "DomainManifest",
            "DomainManifestId",
            "DomainManifestDocument",
            "DomainManifestReader",
            "DomainMetadata",
            "DomainPack",
            "DomainPackKind",
            "DomainPackStatus",
            "DomainPathEscape",
            "DomainPermissionReference",
            "DomainQuery",
            "DomainRegistry",
            "DomainRegistryConflict",
            "DomainRegistryError",
            "DomainRegistryNotFound",
            "DomainRegistryRecord",
            "DomainRegistrySnapshot",
            "DomainRegistryStoreSnapshot",
            "DomainRegistryStateError",
            "DomainRegistryStore",
            "DomainRegistryValidationError",
            "DomainRegistryVersionError",
            "DomainReloadFailed",
            "DomainReloadRollbackFailed",
            "DomainResult",
            "DomainResultId",
            "DomainRollbackFailed",
            "DomainSerializationError",
            "DomainSource",
            "DomainSourceKind",
            "DomainSourceUntrusted",
            "DomainStatus",
            "DomainUnloadFailed",
            "DomainUnloadRollbackFailed",
            "DomainValidationResult",
            "FileSystemDomainDiscovery",
            "InMemoryDomainRegistryStore",
            "JsonDomainManifestReader",
            "ParsedDomainPack",
        }
        assert set(cmm.domains.__all__) == expected

    def test_all_symbols_accessible_from_package(self) -> None:
        """All __all__ symbols should be accessible as attributes."""
        for name in cmm.domains.__all__:
            assert hasattr(cmm.domains, name), f"Missing symbol: {name}"

    def test_no_unexpected_symbols_in_package(self) -> None:
        """Ensure we have exactly the right number of public symbols."""
        assert len(cmm.domains.__all__) == 70

    def test_domain_status_all_values(self) -> None:
        """Verify DomainStatus enum values via package access."""
        from cmm.domains import DomainStatus

        statuses = {v.value for v in DomainStatus}
        assert "active" in statuses
        assert "failed" in statuses
        assert "unloaded" in statuses

    def test_domain_kind_all_values(self) -> None:
        """Verify DomainKind enum values via package access."""
        from cmm.domains import DomainKind

        kinds = {v.value for v in DomainKind}
        assert "core" in kinds
        assert "experimental" in kinds

    def test_no_duplicate_exports(self) -> None:
        """Ensure __all__ has no duplicates."""
        assert len(cmm.domains.__all__) == len(set(cmm.domains.__all__))

    def test_discovery_and_loader_symbols_exported(self) -> None:
        assert hasattr(cmm.domains, "DomainSource")
        assert hasattr(cmm.domains, "DomainCandidate")
        assert hasattr(cmm.domains, "DomainDiscoveryIssue")
        assert hasattr(cmm.domains, "DomainDiscoveryResult")
        assert hasattr(cmm.domains, "DomainDiscovery")
        assert hasattr(cmm.domains, "FileSystemDomainDiscovery")
        assert hasattr(cmm.domains, "DomainManifestReader")
        assert hasattr(cmm.domains, "JsonDomainManifestReader")
        assert hasattr(cmm.domains, "DomainLoader")
        assert hasattr(cmm.domains, "DeclarativeDomainLoader")
        assert hasattr(cmm.domains, "DomainLoadResult")
        assert hasattr(cmm.domains, "DomainLoaderSnapshot")
        assert hasattr(cmm.domains, "DomainSourceKind")
        assert hasattr(cmm.domains, "DomainLoadStatus")

    def test_no_internal_helpers_exported(self) -> None:
        """Path, checksum, and parsing internals must never be public."""
        forbidden = {
            "_validate_safe_relative_path",
            "_walk_directories",
            "_extract_identity",
            "_compare_sources",
            "_compare_candidates",
            "_strip_internal_metadata",
        }
        assert forbidden.isdisjoint(set(cmm.domains.__all__))
