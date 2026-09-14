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

    def test_phase_10_7_symbols_exported(self) -> None:
        """Phase 10.7 must export resolver symbols."""
        assert hasattr(pkg, "DomainResolver")
        assert hasattr(pkg, "DomainResolutionResult")
        assert hasattr(pkg, "DomainResolutionStatus")
        assert hasattr(pkg, "DomainResolutionReason")
        assert hasattr(pkg, "DomainCandidateScore")
        assert hasattr(pkg, "DomainCandidateScorer")
        assert hasattr(pkg, "DomainScoringPolicy")
        assert hasattr(pkg, "DefaultDomainResolver")
        assert hasattr(pkg, "DomainResolverError")
        assert hasattr(pkg, "DomainResolverConfigurationError")
        assert hasattr(pkg, "DomainResolverExecutionError")
        assert hasattr(pkg, "DomainResolutionAmbiguityError")
        assert hasattr(pkg, "DomainResolutionUnsupportedError")
        assert hasattr(pkg, "DomainResolutionBlockedError")

    def test_all_symbols_in_all(self) -> None:
        """All resolution symbols must be in __all__."""
        resolution_symbols = [
            "DefaultDomainResolver",
            "DomainCandidateScore",
            "DomainCandidateScorer",
            "DomainResolutionAmbiguityError",
            "DomainResolutionBlockedError",
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
            "DomainResolutionReason",
            "DomainResolutionResource",
            "DomainResolutionResult",
            "DomainResolutionSerializationError",
            "DomainResolutionSignal",
            "DomainResolutionSnapshotError",
            "DomainResolutionStatus",
            "DomainResolutionUnsupportedError",
            "DomainResolver",
            "DomainResolverConfigurationError",
            "DomainResolverError",
            "DomainResolverExecutionError",
            "DomainScoringPolicy",
        ]
        for name in resolution_symbols:
            assert name in pkg.__all__, f"{name} missing from __all__"
