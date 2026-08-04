"""Tests for Phase 10.18 Domain Memory public API exports."""

import cmm.domains


def test_domain_memory_public_exports() -> None:
    expected_symbols = [
        "DomainMemoryReferenceKind",
        "DomainMemorySelectionDecisionCode",
        "DomainMemoryValidationCode",
        "DomainMemoryReference",
        "DomainMemoryViewRequest",
        "DomainMemorySelectionDecision",
        "DomainMemoryView",
        "DomainMemoryProposalBinding",
        "DomainMemoryReferenceInventory",
        "DomainMemoryValidationResult",
        "DomainMemoryViewResolver",
        "DefaultDomainMemoryViewResolver",
        "DomainMemoryIntegrationValidator",
        "DefaultDomainMemoryIntegrationValidator",
        "DomainMemoryError",
        "DomainMemoryContractError",
        "DomainMemorySerializationError",
        "DomainMemoryResolutionError",
        "DomainMemoryValidationError",
        "DomainMemoryPermissionError",
        "DomainMemoryProposalBindingError",
        "DomainMemoryPrivacyError",
    ]

    for symbol in expected_symbols:
        assert hasattr(cmm.domains, symbol), (
            f"Missing public symbol in cmm.domains: {symbol}"
        )
        assert symbol in cmm.domains.__all__, (
            f"Symbol {symbol} not listed in cmm.domains.__all__"
        )
