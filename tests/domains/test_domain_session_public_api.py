"""Phase 10.34 — Domain Session Public API & Import Boundary Tests."""

from __future__ import annotations


def test_public_api_exports():
    from cmm import domains

    expected_exports = [
        "DOMAIN_SESSION_EXTENSION_KEY",
        "DOMAIN_SESSION_SCHEMA_VERSION",
        "DomainSessionCheck",
        "DomainSessionCheckStatus",
        "DomainSessionCodec",
        "DomainSessionContext",
        "DomainSessionContractError",
        "DomainSessionError",
        "DomainSessionResumeError",
        "DomainSessionResumeRequest",
        "DomainSessionResumeResult",
        "DomainSessionResumeStatus",
        "DomainSessionRevalidationError",
        "DomainSessionResumer",
        "DomainSessionSecurityError",
        "DomainSessionSerializationError",
        "DomainSessionTransition",
        "DomainWorkflowClassification",
        "revalidate_domains",
        "revalidate_resource_and_knowledge_drift",
        "revalidate_session_state",
        "revalidate_temporal",
        "revalidate_workflows",
    ]

    for export in expected_exports:
        assert hasattr(domains, export), (
            f"cmm.domains is missing expected export '{export}'"
        )
        assert export in domains.__all__, (
            f"'{export}' is missing from cmm.domains.__all__"
        )


def test_no_forbidden_abstractions_exported():
    from cmm import domains

    forbidden_symbols = [
        "DomainSessionRepository",
        "AgentRuntimeEventBus",
        "DomainEventStore",
        "DomainEventQueue",
        "DomainEventDLQ",
    ]

    for sym in forbidden_symbols:
        assert not hasattr(domains, sym), (
            f"Forbidden symbol '{sym}' must not be exported in cmm.domains"
        )


def test_cognitive_core_does_not_import_domain_sessions():
    import cmm.agent_runtime
    import cmm.cognitive

    # Agent runtime and cognitive core modules must not import domain session contracts
    for mod in [cmm.agent_runtime, cmm.cognitive]:
        assert not hasattr(mod, "DomainSessionContext")
        assert not hasattr(mod, "DomainSessionResumer")
        assert not hasattr(mod, "DomainSessionCodec")
