"""Fail-closed external-inventory validation for Domain Traces."""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from datetime import datetime
from typing import Any, Protocol, runtime_checkable

from cmm.domains.errors import (
    DomainTraceContractError,
    DomainTraceSerializationError,
    DomainTraceValidationError,
)
from cmm.domains.trace_contracts import (
    DomainTrace,
    DomainTraceReference,
    DomainTraceReferenceInventory,
    DomainTraceReferenceKind,
    DomainTraceRole,
    DomainTraceStatus,
    DomainTraceValidationCode,
    DomainTraceValidationResult,
    _contains_private_marker,
    _freeze_metadata,
)

_VALIDATION_DATA_ERRORS = (
    AttributeError,
    DomainTraceContractError,
    DomainTraceSerializationError,
    IndexError,
    KeyError,
    OverflowError,
    TypeError,
    ValueError,
)


@runtime_checkable
class DomainTraceReferenceValidator(Protocol):
    def validate(self, trace: DomainTrace, inventory: DomainTraceReferenceInventory) -> DomainTraceValidationResult: ...


class DefaultDomainTraceReferenceValidator:
    """Compares only references to an authoritative, typed upstream inventory."""

    def validate(self, trace: DomainTrace, inventory: DomainTraceReferenceInventory) -> DomainTraceValidationResult:
        if not isinstance(trace, DomainTrace):
            raise DomainTraceValidationError("trace must be a DomainTrace", field="trace")
        if not isinstance(inventory, DomainTraceReferenceInventory):
            raise DomainTraceValidationError("inventory must be a DomainTraceReferenceInventory", field="inventory")
        codes: list[DomainTraceValidationCode] = []
        details: dict[str, list[str]] = {name: [] for name in (
            "missing", "unexpected", "duplicate", "kind", "domain", "invariant"
        )}
        self._run_check(
            lambda: self._validate_final_contract(trace, codes, details),
            codes,
            details,
            "final-contract",
        )
        self._run_check(
            lambda: self._validate_inventory_contract(inventory, codes, details),
            codes,
            details,
            "inventory-contract",
        )
        actual: tuple[DomainTraceReference, ...] = ()
        try:
            actual = self._validate_structure(trace, inventory, codes, details)
        except _VALIDATION_DATA_ERRORS:
            self._record_contract_failure(codes, details, "structure")
        for label, check in (
            ("temporal", lambda: self._validate_temporal_integrity(trace, inventory, codes, details)),
            ("metadata", lambda: self._validate_metadata(trace, codes, details)),
            ("references", lambda: self._validate_references(actual, inventory, codes, details)),
            ("domain-results", lambda: self._validate_domain_results(trace, inventory, codes, details)),
            ("cross-domain", lambda: self._validate_cross_domain(trace, inventory, codes, details)),
        ):
            self._run_check(check, codes, details, label)
        trace_digest = trace.digest if isinstance(getattr(trace, "digest", None), str) and re.fullmatch(r"[0-9a-f]{64}", trace.digest) else None
        try:
            inventory_digest = inventory.digest
        except _VALIDATION_DATA_ERRORS:
            codes.append(DomainTraceValidationCode.INVALID_TRACE_CONTRACT)
            details["invariant"].append("inventory-contract")
            inventory_digest = None
        return DomainTraceValidationResult(
            valid=not codes, codes=tuple(dict.fromkeys(codes)),
            missing_references=tuple(details["missing"]), unexpected_references=tuple(details["unexpected"]),
            duplicate_references=tuple(details["duplicate"]), reference_kind_mismatches=tuple(details["kind"]),
            reference_domain_mismatches=tuple(details["domain"]), invariant_failures=tuple(details["invariant"]),
            trace_digest=trace_digest, inventory_digest=inventory_digest,
        )

    @staticmethod
    def _record_contract_failure(
        codes: list[DomainTraceValidationCode],
        details: dict[str, list[str]],
        label: str,
    ) -> None:
        codes.append(DomainTraceValidationCode.INVALID_TRACE_CONTRACT)
        details["invariant"].append(label)

    @classmethod
    def _run_check(
        cls,
        check: Any,
        codes: list[DomainTraceValidationCode],
        details: dict[str, list[str]],
        label: str,
    ) -> None:
        try:
            check()
        except _VALIDATION_DATA_ERRORS:
            cls._record_contract_failure(codes, details, label)

    @staticmethod
    def _validate_final_contract(
        trace: DomainTrace,
        codes: list[DomainTraceValidationCode],
        details: dict[str, list[str]],
    ) -> None:
        extra_fields = set(vars(trace)) - set(DomainTrace.__dataclass_fields__) if hasattr(trace, "__dict__") else set()
        if extra_fields:
            codes.append(DomainTraceValidationCode.FORBIDDEN_FIELD)
            details["invariant"].append("forbidden-field")
            if _contains_inline_content(vars(trace)):
                codes.append(DomainTraceValidationCode.INLINE_CONTENT_DETECTED)
        payload = trace.to_dict()
        if _contains_inline_content(payload):
            codes.append(DomainTraceValidationCode.INLINE_CONTENT_DETECTED)
            details["invariant"].append("inline-content")
        restored = DomainTrace.from_dict(payload)
        if restored.to_dict() != payload:
            codes.append(DomainTraceValidationCode.INVALID_TRACE_CONTRACT)
            details["invariant"].append("non-canonical-trace")

    @staticmethod
    def _validate_inventory_contract(
        inventory: DomainTraceReferenceInventory,
        codes: list[DomainTraceValidationCode],
        details: dict[str, list[str]],
    ) -> None:
        payload = inventory.to_dict()
        restored = DomainTraceReferenceInventory.from_dict(payload)
        if restored.to_dict() != payload:
            codes.append(DomainTraceValidationCode.INVALID_TRACE_CONTRACT)
            details["invariant"].append("non-canonical-inventory")

    @staticmethod
    def _validate_structure(trace: DomainTrace, inventory: DomainTraceReferenceInventory, codes: list[DomainTraceValidationCode], details: dict[str, list[str]]) -> tuple[DomainTraceReference, ...]:
        if not isinstance(trace.primary_domain, type(inventory.expected_primary_domain)) or not isinstance(trace.supporting_domains, tuple) or not isinstance(trace.contributions, tuple):
            codes.append(DomainTraceValidationCode.INVALID_TRACE_CONTRACT)
            details["invariant"].append("participants")
            return ()
        expected_supporting = inventory.expected_supporting_domains
        if trace.primary_domain != inventory.expected_primary_domain or tuple(sorted(trace.supporting_domains, key=str)) != expected_supporting:
            codes.append(DomainTraceValidationCode.AUTHORITATIVE_DOMAIN_MISMATCH)
            details["invariant"].append("upstream-participants")
        for selection_name in ("resolution_result_domains", "composition_domains"):
            selection = getattr(inventory, selection_name)
            expected_source_id = (
                trace.references.resolution_result_id
                if selection_name == "resolution_result_domains"
                else trace.references.composition_id
            )
            if selection.primary_domain != inventory.expected_primary_domain or selection.supporting_domains != expected_supporting:
                codes.append(DomainTraceValidationCode.AUTHORITATIVE_DOMAIN_MISMATCH)
                details["invariant"].append(selection_name)
            if selection.source_id != expected_source_id:
                codes.append(DomainTraceValidationCode.AUTHORITATIVE_DOMAIN_MISMATCH)
                details["invariant"].append(f"{selection_name}-source")
        expected_domains = (inventory.expected_primary_domain, *expected_supporting)
        domain_ids: list[Any] = []
        references: list[DomainTraceReference] = []
        for index, contribution in enumerate(trace.contributions):
            if not hasattr(contribution, "domain_id") or not hasattr(contribution, "role") or not isinstance(contribution.references, tuple):
                codes.append(DomainTraceValidationCode.INVALID_TRACE_CONTRACT)
                details["invariant"].append(f"contribution:{index}")
                continue
            domain_ids.append(contribution.domain_id)
            expected_role = DomainTraceRole.PRIMARY if index == 0 else DomainTraceRole.SUPPORTING
            if not isinstance(contribution.role, DomainTraceRole):
                codes.append(DomainTraceValidationCode.INVALID_DOMAIN_ROLE)
                details["invariant"].append(f"role:{index}")
            elif contribution.role is not expected_role:
                codes.append(DomainTraceValidationCode.PRIMARY_SUPPORTING_MISMATCH)
            if contribution.domain_id not in expected_domains:
                codes.append(DomainTraceValidationCode.FOREIGN_CONTRIBUTION)
            for reference in contribution.references:
                if not isinstance(reference, DomainTraceReference):
                    codes.append(DomainTraceValidationCode.INVALID_TRACE_CONTRACT)
                    continue
                if not isinstance(reference.kind, DomainTraceReferenceKind):
                    codes.append(DomainTraceValidationCode.REFERENCE_KIND_MISMATCH)
                    details["kind"].append(str(getattr(reference, "ref_id", "invalid")))
                    continue
                if reference.domain_id != contribution.domain_id:
                    codes.append(DomainTraceValidationCode.REFERENCE_DOMAIN_MISMATCH)
                    details["domain"].append(reference.ref_id)
                references.append(reference)
        if len(domain_ids) != len(set(domain_ids)):
            codes.append(DomainTraceValidationCode.DUPLICATE_CONTRIBUTION)
        if tuple(domain_ids) != expected_domains:
            codes.append(DomainTraceValidationCode.AUTHORITATIVE_DOMAIN_MISMATCH)
        if not isinstance(trace.references, object) or not hasattr(trace.references, "all_references"):
            codes.append(DomainTraceValidationCode.INVALID_TRACE_CONTRACT)
        else:
            try:
                references.extend(trace.references.all_references())
            except (AttributeError, DomainTraceContractError, TypeError, ValueError):
                codes.append(DomainTraceValidationCode.INVALID_TRACE_CONTRACT)
        return tuple(references)

    @staticmethod
    def _validate_temporal_integrity(trace: DomainTrace, inventory: DomainTraceReferenceInventory, codes: list[DomainTraceValidationCode], details: dict[str, list[str]]) -> None:
        if not isinstance(trace.status, DomainTraceStatus):
            codes.append(DomainTraceValidationCode.UNKNOWN_STATUS)
        started, completed = trace.started_at, trace.completed_at
        if not _aware(started) or not _aware(completed):
            codes.append(DomainTraceValidationCode.INVALID_TIMESTAMP)
        elif completed < started:
            codes.append(DomainTraceValidationCode.INVALID_TIMESTAMP_ORDER)
        elif not isinstance(trace.duration_ms, int) or trace.duration_ms != int((completed - started).total_seconds() * 1000):
            codes.append(DomainTraceValidationCode.INVALID_DURATION)
        if not isinstance(trace.id, str) or not re.fullmatch(r"domain-trace:[0-9a-f]{24}", trace.id):
            codes.append(DomainTraceValidationCode.INVALID_TRACE_ID)
        if not isinstance(trace.digest, str) or not re.fullmatch(r"[0-9a-f]{64}", trace.digest):
            codes.append(DomainTraceValidationCode.INVALID_TRACE_DIGEST)
        else:
            try:
                if trace.digest != trace.calculate_digest() or trace.id != trace.canonical_id:
                    codes.append(DomainTraceValidationCode.ID_DIGEST_MISMATCH)
            except (AttributeError, DomainTraceContractError, TypeError, ValueError):
                codes.append(DomainTraceValidationCode.INVALID_TRACE_CONTRACT)

    @staticmethod
    def _validate_metadata(trace: DomainTrace, codes: list[DomainTraceValidationCode], details: dict[str, list[str]]) -> None:
        try:
            _freeze_metadata(trace.metadata)
        except (DomainTraceContractError, TypeError, ValueError):
            codes.append(DomainTraceValidationCode.UNSAFE_METADATA)
            details["invariant"].append("metadata")

    @staticmethod
    def _validate_references(actual: tuple[DomainTraceReference, ...], inventory: DomainTraceReferenceInventory, codes: list[DomainTraceValidationCode], details: dict[str, list[str]]) -> None:
        expected = inventory.references
        actual_by_id: dict[str, list[DomainTraceReference]] = {}
        for reference in actual:
            if not isinstance(reference, DomainTraceReference):
                codes.append(DomainTraceValidationCode.INVALID_TRACE_CONTRACT)
                continue
            actual_by_id.setdefault(reference.ref_id, []).append(reference)
        for ref_id, values in actual_by_id.items():
            identities = {(item.kind, item.domain_id) for item in values}
            if len(values) > 1 or len(identities) > 1:
                codes.append(DomainTraceValidationCode.REFERENCE_ID_COLLISION)
                details["duplicate"].append(ref_id)
        expected_by_id = {item.ref_id: item for item in expected}
        actual_ids = set(actual_by_id)
        for ref_id, values in actual_by_id.items():
            candidate = expected_by_id.get(ref_id)
            if candidate is None:
                codes.append(DomainTraceValidationCode.UNEXPECTED_REFERENCE)
                details["unexpected"].append(ref_id)
                continue
            value = values[0]
            if value.kind != candidate.kind:
                codes.append(DomainTraceValidationCode.KIND_MISMATCH)
                details["kind"].append(ref_id)
            elif value.domain_id != candidate.domain_id:
                codes.append(DomainTraceValidationCode.DOMAIN_MISMATCH)
                details["domain"].append(ref_id)
        for ref_id in set(expected_by_id) - actual_ids:
            codes.append(DomainTraceValidationCode.MISSING_REFERENCE)
            details["missing"].append(ref_id)

    @staticmethod
    def _validate_domain_results(trace: DomainTrace, inventory: DomainTraceReferenceInventory, codes: list[DomainTraceValidationCode], details: dict[str, list[str]]) -> None:
        if not isinstance(trace.domain_results, tuple):
            codes.append(DomainTraceValidationCode.INVALID_TRACE_CONTRACT)
            return
        contribution_result_items = [
            (reference.ref_id, contribution.domain_id)
            for contribution in trace.contributions if isinstance(contribution, object) and hasattr(contribution, "references")
            for reference in contribution.references if isinstance(reference, DomainTraceReference) and reference.kind is DomainTraceReferenceKind.DOMAIN_RESULT
        ]
        contribution_results = set(contribution_result_items)
        pairings = {(item.result_id, item.domain_id) for item in trace.domain_results if hasattr(item, "result_id") and hasattr(item, "domain_id")}
        if contribution_results != pairings or len(contribution_results) != len(contribution_result_items) or len(pairings) != len(trace.domain_results):
            codes.append(DomainTraceValidationCode.DOMAIN_RESULT_COVERAGE_MISMATCH)
            details["invariant"].append("domain-result-coverage")
        expected = {(item.result_id, item.domain_id, item.trace_id) for item in inventory.domain_results}
        actual = {(item.result_id, item.domain_id, item.trace_id) for item in trace.domain_results if hasattr(item, "trace_id")}
        if any(item.trace_id != trace.id for item in trace.domain_results if hasattr(item, "trace_id")) or actual != expected:
            codes.append(DomainTraceValidationCode.DOMAIN_RESULT_PAIRING_MISMATCH)

    @staticmethod
    def _validate_cross_domain(trace: DomainTrace, inventory: DomainTraceReferenceInventory, codes: list[DomainTraceValidationCode], details: dict[str, list[str]]) -> None:
        actual = {(item.result_id, item.trace_id) for item in trace.references.cross_domain_results}
        expected = {(item.result_id, item.trace_id) for item in inventory.cross_domain_results}
        if actual != expected or any(item.trace_id is None for item in trace.references.cross_domain_results):
            codes.append(DomainTraceValidationCode.CROSS_DOMAIN_PAIRING_MISMATCH)
        inventory_by_id = {item.ref_id: item.kind for item in inventory.references}
        if any(
            inventory_by_id.get(item.result_id) is not DomainTraceReferenceKind.CROSS_DOMAIN_RESULT
            or inventory_by_id.get(item.trace_id) is not DomainTraceReferenceKind.CROSS_DOMAIN_TRACE
            for item in trace.references.cross_domain_results
        ):
            codes.append(DomainTraceValidationCode.CROSS_DOMAIN_PAIRING_MISMATCH)


def _aware(value: Any) -> bool:
    return isinstance(value, datetime) and value.tzinfo is not None and value.utcoffset() is not None


def _contains_inline_content(value: Any) -> bool:
    if isinstance(value, str):
        return any(character.isspace() for character in value) or _contains_private_marker(value)
    if isinstance(value, Mapping):
        return any(
            (isinstance(key, str) and _contains_private_marker(key))
            or _contains_inline_content(item)
            for key, item in value.items()
        )
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        return any(_contains_inline_content(item) for item in value)
    return False
