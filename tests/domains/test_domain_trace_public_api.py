"""Phase 10.17 public API stays reference-only."""

from __future__ import annotations

from cmm import domains


def test_expected_domain_trace_exports_present() -> None:
    expected = (
        "DomainTrace",
        "DomainTraceAssembler",
        "DomainTraceAssemblyRequest",
        "DomainTraceContribution",
        "DomainTraceDomainSelection",
        "DomainResultTraceReference",
        "DomainTraceReference",
        "DomainTraceReferenceInventory",
        "DomainTraceReferenceKind",
        "DomainTraceReferences",
        "DomainTraceRole",
        "CrossDomainTraceReference",
        "DomainTraceReferenceValidator",
        "DefaultDomainTraceReferenceValidator",
        "DomainTraceStatus",
        "DomainTraceValidationCode",
        "DomainTraceValidationResult",
        "DomainTraceValidationState",
        "DomainTraceError",
        "DomainTraceContractError",
        "DomainTraceSerializationError",
        "DomainTraceValidationError",
    )
    for name in expected:
        assert hasattr(domains, name), f"missing export: {name}"
        assert name in domains.__all__
