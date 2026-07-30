"""Phase 10.6 — Tests for public API exports."""

from __future__ import annotations

import cmm.domains as pkg


class TestResolutionPublicAPI:
    def test_contracts_exported(self) -> None:
        assert hasattr(pkg, "DomainResolutionContext")
        assert hasattr(pkg, "DomainResolutionSignal")
        assert hasattr(pkg, "DomainResolutionResource")
        assert hasattr(pkg, "DomainResolutionEntity")
        assert hasattr(pkg, "DomainResolutionKnowledgeItem")
        assert hasattr(pkg, "DomainResolutionHistoryItem")
        assert hasattr(pkg, "DomainResolutionEvent")
        assert hasattr(pkg, "DomainResolutionPolicy")

    def test_builder_exported(self) -> None:
        assert hasattr(pkg, "DomainResolutionContextBuilder")

    def test_errors_exported(self) -> None:
        assert hasattr(pkg, "DomainResolutionError")
        assert hasattr(pkg, "DomainResolutionContractError")
        assert hasattr(pkg, "DomainResolutionSerializationError")
        assert hasattr(pkg, "DomainResolutionContextInvalid")
        assert hasattr(pkg, "DomainResolutionPolicyError")
        assert hasattr(pkg, "DomainResolutionSnapshotError")
        assert hasattr(pkg, "DomainResolutionLimitExceeded")

    def test_no_resolver_exported_yet(self) -> None:
        """Phase 10.6 must NOT export DomainResolver or DomainResolutionResult."""
        assert not hasattr(pkg, "DomainResolver")
        assert not hasattr(pkg, "DomainResolutionResult")
        assert not hasattr(pkg, "DomainResolutionStatus")

    def test_all_symbols_in_all(self) -> None:
        """All resolution symbols must be in __all__."""
        resolution_symbols = [
            "DomainResolutionContext",
            "DomainResolutionContextBuilder",
            "DomainResolutionContextInvalid",
            "DomainResolutionContractError",
            "DomainResolutionEntity",
            "DomainResolutionError",
            "DomainResolutionEvent",
            "DomainResolutionHistoryItem",
            "DomainResolutionKnowledgeItem",
            "DomainResolutionLimitExceeded",
            "DomainResolutionPolicy",
            "DomainResolutionPolicyError",
            "DomainResolutionResource",
            "DomainResolutionSerializationError",
            "DomainResolutionSignal",
            "DomainResolutionSnapshotError",
        ]
        for name in resolution_symbols:
            assert name in pkg.__all__, f"{name} missing from __all__"
