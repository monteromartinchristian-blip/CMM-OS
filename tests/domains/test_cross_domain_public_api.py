"""Phase 10.9 – Tests for Cross-Domain Engine public API exports."""

from __future__ import annotations

from cmm import domains


def test_expected_exports_present() -> None:
    expected = [
        "CrossDomainStatus",
        "CrossDomainRequest",
        "CrossDomainPolicy",
        "CrossDomainQuestion",
        "CrossDomainContextTransfer",
        "CrossDomainDependency",
        "CrossDomainContradiction",
        "CrossDomainGap",
        "CrossDomainDecision",
        "CrossDomainDomainResult",
        "CrossDomainPlanResult",
        "CrossDomainWorkflowResult",
        "CrossDomainKnowledgeResult",
        "CrossDomainLimits",
        "CrossDomainContextSnapshot",
        "CrossDomainResult",
        "DomainResolutionPort",
        "DomainCompositionPort",
        "CrossDomainCognitivePort",
        "CrossDomainPlannerPort",
        "CrossDomainAgentPort",
        "CrossDomainWorkflowPort",
        "CrossDomainKnowledgePort",
        "CrossDomainOperationPort",
        "CrossDomainOperationResult",
        "CrossDomainFinding",
        "KNOWN_CROSS_DOMAIN_PORTS",
        "DOMAIN_STATUS_PRECEDENCE",
        "CrossDomainEngine",
        "DefaultCrossDomainEngine",
        "CrossDomainContextBuilder",
        "CrossDomainLimitTracker",
        "CrossDomainError",
        "CrossDomainContractError",
        "CrossDomainSerializationError",
        "CrossDomainConfigurationError",
        "CrossDomainLimitError",
        "CrossDomainPortError",
        "CrossDomainExecutionError",
    ]
    for name in expected:
        assert hasattr(domains, name), f"Missing export: {name}"
        assert name in domains.__all__, f"Missing from __all__: {name}"


def test_forbidden_fake_implementations_absent() -> None:
    forbidden = [
        "FakeCrossDomainEngine",
        "InMemoryCrossDomainEngine",
        "StubCognitivePort",
        "StubAgentPort",
    ]
    for name in forbidden:
        assert not hasattr(domains, name), f"Forbidden export present: {name}"


def test_previous_phase_apis_remain() -> None:
    assert hasattr(domains, "DomainComposition")
    assert hasattr(domains, "DomainResolutionResult")
    assert hasattr(domains, "DomainResolver")
    assert hasattr(domains, "DomainComposer")


def test_error_hierarchy() -> None:
    assert issubclass(domains.CrossDomainContractError, domains.CrossDomainError)
    assert issubclass(domains.CrossDomainSerializationError, domains.CrossDomainError)
    assert issubclass(domains.CrossDomainConfigurationError, domains.CrossDomainError)
    assert issubclass(domains.CrossDomainLimitError, domains.CrossDomainError)
    assert issubclass(domains.CrossDomainPortError, domains.CrossDomainError)
    assert issubclass(domains.CrossDomainExecutionError, domains.CrossDomainError)
    assert issubclass(domains.CrossDomainError, domains.DomainError)


def test_error_codes_stable() -> None:
    assert domains.CrossDomainError.code == "CROSS_DOMAIN_ERROR"
    assert domains.CrossDomainContractError.code == "CROSS_DOMAIN_CONTRACT_ERROR"
    assert (
        domains.CrossDomainSerializationError.code == "CROSS_DOMAIN_SERIALIZATION_ERROR"
    )
    assert (
        domains.CrossDomainConfigurationError.code == "CROSS_DOMAIN_CONFIGURATION_ERROR"
    )
    assert domains.CrossDomainLimitError.code == "CROSS_DOMAIN_LIMIT_ERROR"
    assert domains.CrossDomainPortError.code == "CROSS_DOMAIN_PORT_ERROR"
    assert domains.CrossDomainExecutionError.code == "CROSS_DOMAIN_EXECUTION_ERROR"
