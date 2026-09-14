"""Phase 10.36 — Domain API conflict resolution and trace coordination tests.

Proves pure conflict delegation, trace assembly equivalence, canonical trace
validation, and that no hidden persistence is created.
"""

from __future__ import annotations

from datetime import datetime, timezone

from cmm.domains.api import DefaultDomainAPI
from cmm.domains.conflict_resolution import DomainConflictResolver
from cmm.domains.conflict_resolution_contracts import (
    DomainConflictAuthority,
    DomainConflictCase,
    DomainConflictKind,
    DomainConflictReference,
    DomainConflictSeverity,
    DomainConflictSourceKind,
    DomainConflictStatus,
)
from cmm.domains.identifiers import DomainId
from cmm.domains.trace_assembler import DomainTraceAssembler
from cmm.domains.trace_contracts import (
    DomainResultTraceReference,
    DomainTraceAssemblyRequest,
    DomainTraceContribution,
    DomainTraceDomainSelection,
    DomainTraceReference,
    DomainTraceReferenceInventory,
    DomainTraceReferenceKind,
    DomainTraceReferences,
    DomainTraceRole,
)
from cmm.domains.trace_validation import DefaultDomainTraceReferenceValidator
from tests.domains.test_domain_api_contracts import _make_collaborators


def _api() -> DefaultDomainAPI:
    return DefaultDomainAPI(**_make_collaborators())


def _conflict_case() -> DomainConflictCase:
    return DomainConflictCase(
        id="case-api-1",
        domains=(DomainId(slug="general"), DomainId(slug="health")),
        kind=DomainConflictKind.EVIDENCE,
        severity=DomainConflictSeverity.MATERIAL,
        status=DomainConflictStatus.OPEN,
        references=(
            DomainConflictReference(
                source_kind=DomainConflictSourceKind.DOMAIN_SPECIFIC_CONFLICT,
                source_id="ref-1",
                domain_id=DomainId(slug="general"),
                blocking=False,
                severity=DomainConflictSeverity.MATERIAL,
                authority_kind=DomainConflictAuthority.PRIMARY_DOMAIN,
            ),
        ),
    )


NOW = datetime(2026, 8, 31, 12, 0, tzinfo=timezone.utc)


def _trace_request() -> DomainTraceAssemblyRequest:
    primary = DomainTraceContribution(
        domain_id="domain:life-plan",
        role=DomainTraceRole.PRIMARY,
        references=(
            DomainTraceReference(
                ref_id="result:1",
                kind=DomainTraceReferenceKind.DOMAIN_RESULT,
                domain_id="domain:life-plan",
            ),
        ),
    )
    supporting = DomainTraceContribution(
        domain_id="domain:health",
        role=DomainTraceRole.SUPPORTING,
        references=(
            DomainTraceReference(
                ref_id="warning:1",
                kind=DomainTraceReferenceKind.WARNING,
                domain_id="domain:health",
            ),
        ),
    )
    return DomainTraceAssemblyRequest(
        request_id="request:1",
        goal_id="goal:1",
        primary_domain="domain:life-plan",
        supporting_domains=("domain:health",),
        contributions=(primary, supporting),
        references=DomainTraceReferences(
            resolution_context_id="resolution-context:1",
            resolution_result_id="resolution-result:1",
            composition_id="composition:1",
        ),
        domain_results=(DomainResultTraceReference("result:1", "domain:life-plan"),),
        started_at=NOW,
        completed_at=datetime(2026, 8, 31, 12, 0, 1, tzinfo=timezone.utc),
        metadata={"category": "api-test"},
    )


class TestResolveConflict:
    def test_delegates_to_pure_resolver(self) -> None:
        api = _api()
        case = _conflict_case()
        expected = DomainConflictResolver().resolve(case)
        actual = api.resolve_conflict(case)
        assert actual == expected

    def test_conflict_input_is_not_mutated(self) -> None:
        api = _api()
        case = _conflict_case()
        before = case.to_dict()
        api.resolve_conflict(case)
        assert case.to_dict() == before

    def test_authority_parameters_are_forwarded(self) -> None:
        api = _api()
        case = _conflict_case()
        expected = DomainConflictResolver().resolve(
            case, primary_domain=DomainId(slug="general")
        )
        actual = api.resolve_conflict(case, primary_domain=DomainId(slug="general"))
        assert actual == expected


class TestAssembleTrace:
    def test_assembly_equals_direct_assembler(self) -> None:
        api = _api()
        request = _trace_request()
        expected = DomainTraceAssembler().assemble(request)
        actual = api.assemble_trace(request)
        assert actual == expected

    def test_no_hidden_persistence_created(self) -> None:
        api = _api()
        api.assemble_trace(_trace_request())
        for forbidden in (
            "_traces",
            "_trace_store",
            "_trace_cache",
            "_trace_repository",
        ):
            assert not hasattr(api, forbidden)
        assert not hasattr(api, "get_trace")
        assert not hasattr(api, "list_traces")
        assert not hasattr(type(api), "get_trace")
        assert not hasattr(type(api), "list_traces")


class TestValidateTrace:
    def _trace_and_inventory(self):
        trace = DomainTraceAssembler().assemble(_trace_request())
        inventory = DomainTraceReferenceInventory(
            references=trace.all_references(),
            domain_results=trace.domain_results,
            expected_primary_domain="domain:life-plan",
            expected_supporting_domains=("domain:health",),
            resolution_result_domains=DomainTraceDomainSelection(
                "resolution-result:1", "domain:life-plan", ("domain:health",)
            ),
            composition_domains=DomainTraceDomainSelection(
                "composition:1", "domain:life-plan", ("domain:health",)
            ),
        )
        return trace, inventory

    def test_validation_equals_direct_validator(self) -> None:
        api = _api()
        trace, inventory = self._trace_and_inventory()
        expected = DefaultDomainTraceReferenceValidator().validate(trace, inventory)
        actual = api.validate_trace(trace, inventory)
        assert actual == expected
        assert actual.valid is True

    def test_validation_remains_reference_only(self) -> None:
        api = _api()
        trace, inventory = self._trace_and_inventory()
        result = api.validate_trace(trace, inventory)
        assert result.valid is True
        # No persistence side effects on the facade.
        assert not hasattr(api, "_trace_store")
        assert not hasattr(api, "_traces")
