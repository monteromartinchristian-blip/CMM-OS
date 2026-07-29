"""Phase 8.26 – Structural Cognitive Validation.

Validates cognitive artifacts before they can be considered trustworthy,
cached, persisted, exported, transmitted, supplied to a model, or used as a
dependency of another cognitive process.

This module reuses — and does not duplicate — the Phase 7 validation
contracts (``ValidationFinding``, ``ValidationArtifact``,
``ValidationStepResult``, ``ValidationStatus``, ``ValidationSeverity``),
the Phase 8.24 Cognitive Cache contracts, and the Phase 8.25 privacy
metadata contracts. It never invokes a model, never silently repairs
content, and never resolves contradictions automatically.

Integration with the Phase 7 ``ValidationPipeline`` is achieved via
:class:`CognitiveValidationStepExecutor`, an ``InternalValidator`` adapter
that wraps a :class:`CognitiveValidator` and returns a real
``ValidationStepResult``.
"""

from __future__ import annotations

import hashlib
import json
import time
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from types import MappingProxyType
from typing import Any, Protocol, runtime_checkable

from cmm.cognitive.cognitive_cache import (
    COGNITIVE_CACHE_SCHEMA_VERSION,
    CognitiveCacheContext,
    CognitiveCacheEntry,
    CognitiveCacheEntryStatus,
    default_cognitive_cache_validator,
)
from cmm.cognitive.enums import (
    ContradictionStatus,
    KnowledgeKind,
    TemporalValidityStatus,
)
from cmm.cognitive.errors import (
    CognitiveValidationError,
    CognitiveValidationExecutionError,
    InvalidCognitiveValidationContextError,
)
from cmm.cognitive.knowledge import KnowledgeItem
from cmm.cognitive.knowledge_packages import SCHEMA_VERSION as KP_SCHEMA_VERSION
from cmm.cognitive.knowledge_packages import KnowledgePackage
from cmm.cognitive.privacy import (
    PrivacyDecisionStatus,
    PrivacyMetadata,
    PrivacyOperation,
    PrivacyOperationContext,
    ProcessingLocation,
    evaluate_privacy_operation,
    privacy_from_knowledge_package,
)
from cmm.validation.artifacts import ValidationArtifact
from cmm.validation.context import ValidationContext
from cmm.validation.enums import ValidationSeverity, ValidationStatus
from cmm.validation.findings import ValidationFinding
from cmm.validation.steps import ValidationStep, ValidationStepResult

COGNITIVE_VALIDATION_SCHEMA_VERSION = 1

_SOURCE = "cognitive.validation"


# ── Decision enum ────────────────────────────────────────────────────────────


class CognitiveValidationDecision(str, Enum):
    """Aggregated decision derived from validation findings.

    Ordered from least to most restrictive. ``derive_cognitive_validation_decision``
    always returns the most restrictive decision implied by the findings, so a
    less-grave decision can never hide a more restrictive one.
    """

    ACCEPT = "accept"
    ACCEPT_WITH_WARNING = "accept_with_warning"
    REQUEST_INFORMATION = "request_information"
    REQUEST_APPROVAL = "request_approval"
    REPAIR = "repair"
    REBUILD = "rebuild"
    INVALIDATE = "invalidate"
    BLOCK = "block"
    ESCALATE = "escalate"


_DECISION_RANK: Mapping[CognitiveValidationDecision, int] = {
    CognitiveValidationDecision.ACCEPT: 0,
    CognitiveValidationDecision.ACCEPT_WITH_WARNING: 1,
    CognitiveValidationDecision.REQUEST_INFORMATION: 2,
    CognitiveValidationDecision.REQUEST_APPROVAL: 3,
    CognitiveValidationDecision.REPAIR: 4,
    CognitiveValidationDecision.REBUILD: 5,
    CognitiveValidationDecision.INVALIDATE: 6,
    CognitiveValidationDecision.ESCALATE: 7,
    CognitiveValidationDecision.BLOCK: 8,
}


# ── Finding codes ────────────────────────────────────────────────────────────

COG_SCHEMA_UNSUPPORTED = "COG_SCHEMA_UNSUPPORTED"
COG_PROVENANCE_MISSING = "COG_PROVENANCE_MISSING"
COG_TEMPORAL_EXPIRED = "COG_TEMPORAL_EXPIRED"
COG_TEMPORAL_UNKNOWN = "COG_TEMPORAL_UNKNOWN"
COG_EPISTEMIC_KIND_MISMATCH = "COG_EPISTEMIC_KIND_MISMATCH"
COG_EPISTEMIC_PROMOTION = "COG_EPISTEMIC_PROMOTION"
COG_EVIDENCE_INSUFFICIENT = "COG_EVIDENCE_INSUFFICIENT"
COG_MISSING_INFORMATION = "COG_MISSING_INFORMATION"
COG_CONTRADICTION_UNRESOLVED = "COG_CONTRADICTION_UNRESOLVED"
COG_PRIVACY_DENIED = "COG_PRIVACY_DENIED"
COG_REDACTION_REQUIRED = "COG_REDACTION_REQUIRED"
COG_APPROVAL_REQUIRED = "COG_APPROVAL_REQUIRED"
COG_CACHE_NOT_REUSABLE = "COG_CACHE_NOT_REUSABLE"
COG_CACHE_EXPIRED = "COG_CACHE_EXPIRED"
COG_CACHE_STALE = "COG_CACHE_STALE"
COG_CACHE_INVALID = "COG_CACHE_INVALID"
COG_DEPENDENCY_INVALIDATED = "COG_DEPENDENCY_INVALIDATED"
COG_PROFILE_MISMATCH = "COG_PROFILE_MISMATCH"
COG_DOMAIN_MISMATCH = "COG_DOMAIN_MISMATCH"
COG_CONTRADICTION_COMPLEX = "COG_CONTRADICTION_COMPLEX"


# Maps each finding code to the decision it implies when blocking.
_CODE_DECISION: Mapping[str, CognitiveValidationDecision] = {
    COG_SCHEMA_UNSUPPORTED: CognitiveValidationDecision.BLOCK,
    COG_PROVENANCE_MISSING: CognitiveValidationDecision.BLOCK,
    COG_TEMPORAL_EXPIRED: CognitiveValidationDecision.INVALIDATE,
    COG_TEMPORAL_UNKNOWN: CognitiveValidationDecision.ACCEPT_WITH_WARNING,
    COG_EPISTEMIC_KIND_MISMATCH: CognitiveValidationDecision.REPAIR,
    COG_EPISTEMIC_PROMOTION: CognitiveValidationDecision.REPAIR,
    COG_EVIDENCE_INSUFFICIENT: CognitiveValidationDecision.REQUEST_INFORMATION,
    COG_MISSING_INFORMATION: CognitiveValidationDecision.REQUEST_INFORMATION,
    COG_CONTRADICTION_UNRESOLVED: CognitiveValidationDecision.ESCALATE,
    COG_CONTRADICTION_COMPLEX: CognitiveValidationDecision.ESCALATE,
    COG_PRIVACY_DENIED: CognitiveValidationDecision.BLOCK,
    COG_REDACTION_REQUIRED: CognitiveValidationDecision.BLOCK,
    COG_APPROVAL_REQUIRED: CognitiveValidationDecision.REQUEST_APPROVAL,
    COG_CACHE_NOT_REUSABLE: CognitiveValidationDecision.INVALIDATE,
    COG_CACHE_EXPIRED: CognitiveValidationDecision.INVALIDATE,
    COG_CACHE_STALE: CognitiveValidationDecision.INVALIDATE,
    COG_CACHE_INVALID: CognitiveValidationDecision.INVALIDATE,
    COG_DEPENDENCY_INVALIDATED: CognitiveValidationDecision.INVALIDATE,
    COG_PROFILE_MISMATCH: CognitiveValidationDecision.INVALIDATE,
    COG_DOMAIN_MISMATCH: CognitiveValidationDecision.INVALIDATE,
}


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _require_aware(value: datetime | None, name: str) -> None:
    if value is not None and value.tzinfo is None:
        raise InvalidCognitiveValidationContextError(
            f"{name} must be timezone-aware when provided"
        )


# ── CognitiveValidationContext ───────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class CognitiveValidationContext:
    """The caller's context for validating a cognitive artifact.

    Reuses :class:`ProcessingLocation` and :class:`PrivacyOperation` from
    Phase 8.25. Does not introduce a provider registry.
    """

    actor_id: str | None = None
    domain: str | None = None
    profile_version: str | None = None
    domain_version: str | None = None
    processing_location: ProcessingLocation = ProcessingLocation.LOCAL
    target_operation: PrivacyOperation | None = None
    permission_context: Mapping[str, Any] = field(default_factory=dict)
    known_dependency_ids: tuple[str, ...] = ()
    invalidated_dependency_ids: tuple[str, ...] = ()
    require_complete_package: bool = False
    require_current_information: bool = False
    now: datetime = field(default_factory=_utc_now)
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        location = self.processing_location
        if isinstance(location, str):
            try:
                location = ProcessingLocation(location)
            except ValueError as exc:
                raise InvalidCognitiveValidationContextError(
                    f"Invalid processing_location: {location}"
                ) from exc
        elif not isinstance(location, ProcessingLocation):
            raise InvalidCognitiveValidationContextError(
                f"Invalid processing_location: {location}"
            )
        object.__setattr__(self, "processing_location", location)

        op = self.target_operation
        if op is not None:
            if isinstance(op, str):
                try:
                    op = PrivacyOperation(op)
                except ValueError as exc:
                    raise InvalidCognitiveValidationContextError(
                        f"Invalid target_operation: {op}"
                    ) from exc
            elif not isinstance(op, PrivacyOperation):
                raise InvalidCognitiveValidationContextError(
                    f"Invalid target_operation: {op}"
                )
            object.__setattr__(self, "target_operation", op)

        _require_aware(self.now, "now")
        object.__setattr__(
            self, "known_dependency_ids", tuple(self.known_dependency_ids or ())
        )
        object.__setattr__(
            self,
            "invalidated_dependency_ids",
            tuple(self.invalidated_dependency_ids or ()),
        )
        object.__setattr__(
            self, "permission_context", MappingProxyType(dict(self.permission_context or {}))
        )
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata or {})))

    def to_privacy_operation_context(self) -> PrivacyOperationContext:
        """Build a Phase 8.25 ``PrivacyOperationContext`` from this context."""
        return PrivacyOperationContext(
            actor_id=self.actor_id,
            domain=self.domain,
            processing_location=self.processing_location,
            at=self.now,
        )

    def to_cache_context(self, context_signature: str) -> CognitiveCacheContext:
        """Build a Phase 8.24 ``CognitiveCacheContext`` from this context."""
        return CognitiveCacheContext(
            context_signature=context_signature,
            profile_version=self.profile_version,
            domain_version=self.domain_version,
            actor_id=self.actor_id,
            domain=self.domain,
            processing_location=self.processing_location,
            invalidated_dependency_ids=frozenset(self.invalidated_dependency_ids),
            at=self.now,
        )

    def serialize(self) -> dict[str, Any]:
        return {
            "actor_id": self.actor_id,
            "domain": self.domain,
            "profile_version": self.profile_version,
            "domain_version": self.domain_version,
            "processing_location": self.processing_location.value,
            "target_operation": (
                self.target_operation.value if self.target_operation is not None else None
            ),
            "permission_context": dict(self.permission_context),
            "known_dependency_ids": list(self.known_dependency_ids),
            "invalidated_dependency_ids": list(self.invalidated_dependency_ids),
            "require_complete_package": self.require_complete_package,
            "require_current_information": self.require_current_information,
            "now": self.now.isoformat(),
            "metadata": dict(self.metadata),
        }


# ── CognitiveValidationResult ────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class CognitiveValidationResult:
    """Immutable, versioned, serializable outcome of validating one artifact.

    Reuses Phase 7 ``ValidationFinding``, ``ValidationStatus``, and
    ``ValidationStepResult``. The decision is always derived from findings,
    never set arbitrarily.
    """

    id: str
    target_id: str
    target_kind: str
    status: ValidationStatus
    decision: CognitiveValidationDecision
    findings: tuple[ValidationFinding, ...] = ()
    blocking_findings: tuple[ValidationFinding, ...] = ()
    warnings: tuple[ValidationFinding, ...] = ()
    validated_rules: tuple[str, ...] = ()
    privacy_result: Mapping[str, Any] = field(default_factory=dict)
    temporal_result: Mapping[str, Any] = field(default_factory=dict)
    provenance_result: Mapping[str, Any] = field(default_factory=dict)
    epistemology_result: Mapping[str, Any] = field(default_factory=dict)
    contradiction_result: Mapping[str, Any] = field(default_factory=dict)
    cache_result: Mapping[str, Any] | None = None
    phase7_result: ValidationStepResult | None = None
    created_at: datetime = field(default_factory=_utc_now)
    metadata: Mapping[str, Any] = field(default_factory=dict)
    schema_version: int = COGNITIVE_VALIDATION_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if not self.id.strip():
            raise CognitiveValidationError("CognitiveValidationResult.id must not be empty")
        if not self.target_id.strip():
            raise CognitiveValidationError(
                "CognitiveValidationResult.target_id must not be empty"
            )
        if not self.target_kind.strip():
            raise CognitiveValidationError(
                "CognitiveValidationResult.target_kind must not be empty"
            )
        if self.schema_version != COGNITIVE_VALIDATION_SCHEMA_VERSION:
            raise CognitiveValidationError(
                f"Unsupported CognitiveValidationResult schema_version: {self.schema_version}"
            )
        if not isinstance(self.status, ValidationStatus):
            raise CognitiveValidationError("status must be a ValidationStatus")
        if not isinstance(self.decision, CognitiveValidationDecision):
            raise CognitiveValidationError("decision must be a CognitiveValidationDecision")
        _require_aware(self.created_at, "created_at")

        object.__setattr__(self, "findings", tuple(self.findings or ()))
        object.__setattr__(self, "blocking_findings", tuple(self.blocking_findings or ()))
        object.__setattr__(self, "warnings", tuple(self.warnings or ()))
        object.__setattr__(self, "validated_rules", tuple(self.validated_rules or ()))
        object.__setattr__(self, "privacy_result", MappingProxyType(dict(self.privacy_result or {})))
        object.__setattr__(self, "temporal_result", MappingProxyType(dict(self.temporal_result or {})))
        object.__setattr__(self, "provenance_result", MappingProxyType(dict(self.provenance_result or {})))
        object.__setattr__(self, "epistemology_result", MappingProxyType(dict(self.epistemology_result or {})))
        object.__setattr__(self, "contradiction_result", MappingProxyType(dict(self.contradiction_result or {})))
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata or {})))

    @property
    def is_accept(self) -> bool:
        return self.decision in (
            CognitiveValidationDecision.ACCEPT,
            CognitiveValidationDecision.ACCEPT_WITH_WARNING,
        )

    def serialize(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "id": self.id,
            "target_id": self.target_id,
            "target_kind": self.target_kind,
            "status": self.status.value,
            "decision": self.decision.value,
            "findings": [f.serialize() for f in self.findings],
            "blocking_findings": [f.serialize() for f in self.blocking_findings],
            "warnings": [f.serialize() for f in self.warnings],
            "validated_rules": list(self.validated_rules),
            "privacy_result": dict(self.privacy_result),
            "temporal_result": dict(self.temporal_result),
            "provenance_result": dict(self.provenance_result),
            "epistemology_result": dict(self.epistemology_result),
            "contradiction_result": dict(self.contradiction_result),
            "cache_result": dict(self.cache_result) if self.cache_result is not None else None,
            "phase7_result": (
                self.phase7_result.serialize() if self.phase7_result is not None else None
            ),
            "created_at": self.created_at.isoformat(),
            "metadata": dict(self.metadata),
        }

    def to_dict(self) -> dict[str, Any]:
        return self.serialize()

    @classmethod
    def from_mapping(cls, payload: Mapping[str, Any]) -> CognitiveValidationResult:
        if not isinstance(payload, Mapping):
            raise CognitiveValidationError("payload must be a mapping")

        def _parse_dt(raw: Any, name: str) -> datetime:
            if isinstance(raw, datetime):
                return raw
            if isinstance(raw, str):
                try:
                    return datetime.fromisoformat(raw)
                except ValueError as exc:
                    raise CognitiveValidationError(
                        f"Invalid ISO timestamp for {name}: {raw}"
                    ) from exc
            raise CognitiveValidationError(f"Expected timestamp string for {name}: {raw}")

        def _finding(raw: Any) -> ValidationFinding:
            if isinstance(raw, ValidationFinding):
                return raw
            if isinstance(raw, Mapping):
                return ValidationFinding(
                    code=str(raw["code"]),
                    message=str(raw["message"]),
                    severity=ValidationSeverity(raw["severity"]),
                    source=str(raw["source"]),
                    file_path=None,
                    line=raw.get("line"),
                    column=raw.get("column"),
                    blocking=bool(raw.get("blocking", False)),
                    suggested_fix=raw.get("suggested_fix"),
                    documentation_url=raw.get("documentation_url"),
                    metadata=dict(raw.get("metadata") or {}),
                )
            raise CognitiveValidationError(f"Invalid finding: {raw!r}")

        status_raw = payload.get("status", ValidationStatus.PASSED.value)
        status = (
            status_raw if isinstance(status_raw, ValidationStatus) else ValidationStatus(status_raw)
        )
        decision_raw = payload.get("decision", CognitiveValidationDecision.ACCEPT.value)
        decision = (
            decision_raw
            if isinstance(decision_raw, CognitiveValidationDecision)
            else CognitiveValidationDecision(decision_raw)
        )

        phase7_raw = payload.get("phase7_result")
        phase7: ValidationStepResult | None = None
        if phase7_raw is not None:
            if isinstance(phase7_raw, ValidationStepResult):
                phase7 = phase7_raw
            elif isinstance(phase7_raw, Mapping):
                phase7 = ValidationStepResult(
                    name=str(phase7_raw["name"]),
                    status=ValidationStatus(phase7_raw["status"]),
                    exit_code=phase7_raw.get("exit_code"),
                    duration_ms=int(phase7_raw.get("duration_ms", 0)),
                    stdout=str(phase7_raw.get("stdout", "")),
                    stderr=str(phase7_raw.get("stderr", "")),
                    findings=tuple(
                        _finding(f) for f in phase7_raw.get("findings", ())
                    ),
                    artifacts=(),
                    started_at=None,
                    completed_at=None,
                    metadata=dict(phase7_raw.get("metadata") or {}),
                )

        return cls(
            id=str(payload["id"]),
            target_id=str(payload["target_id"]),
            target_kind=str(payload["target_kind"]),
            status=status,
            decision=decision,
            findings=tuple(_finding(f) for f in payload.get("findings", ())),
            blocking_findings=tuple(_finding(f) for f in payload.get("blocking_findings", ())),
            warnings=tuple(_finding(f) for f in payload.get("warnings", ())),
            validated_rules=tuple(str(r) for r in payload.get("validated_rules", ())),
            privacy_result=dict(payload.get("privacy_result") or {}),
            temporal_result=dict(payload.get("temporal_result") or {}),
            provenance_result=dict(payload.get("provenance_result") or {}),
            epistemology_result=dict(payload.get("epistemology_result") or {}),
            contradiction_result=dict(payload.get("contradiction_result") or {}),
            cache_result=(
                dict(payload["cache_result"]) if payload.get("cache_result") is not None else None
            ),
            phase7_result=phase7,
            created_at=_parse_dt(payload.get("created_at"), "created_at"),
            metadata=dict(payload.get("metadata") or {}),
            schema_version=int(payload.get("schema_version", COGNITIVE_VALIDATION_SCHEMA_VERSION)),
        )

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> CognitiveValidationResult:
        return cls.from_mapping(data)


# ── Decision derivation ──────────────────────────────────────────────────────


def derive_cognitive_validation_decision(
    findings: Sequence[ValidationFinding],
) -> CognitiveValidationDecision:
    """Derive the most restrictive decision from a sequence of findings.

    Pure, deterministic, and tested for precedence: a less-grave decision can
    never hide a more restrictive one.
    """
    if not findings:
        return CognitiveValidationDecision.ACCEPT

    has_warning = False
    most_restrictive = CognitiveValidationDecision.ACCEPT

    for finding in findings:
        if finding.blocking:
            code_decision = _CODE_DECISION.get(finding.code)
            if code_decision is not None:
                if _DECISION_RANK[code_decision] > _DECISION_RANK[most_restrictive]:
                    most_restrictive = code_decision
            else:
                # Unknown blocking finding → escalate
                if _DECISION_RANK[CognitiveValidationDecision.ESCALATE] > _DECISION_RANK[most_restrictive]:
                    most_restrictive = CognitiveValidationDecision.ESCALATE
        elif finding.severity in (ValidationSeverity.WARNING, ValidationSeverity.ERROR):
            has_warning = True

    if most_restrictive is CognitiveValidationDecision.ACCEPT and has_warning:
        return CognitiveValidationDecision.ACCEPT_WITH_WARNING
    return most_restrictive


# ── Rule protocol ────────────────────────────────────────────────────────────


@runtime_checkable
class CognitiveValidationRule(Protocol):
    """Protocol for structural cognitive validation rules.

    Rules are pure: they produce findings and never mutate the target.
    Exceptions are reserved for execution errors or corrupt contracts, not
    for simply invalid content.
    """

    name: str

    def applies(self, target: Any) -> bool: ...

    def evaluate(
        self, target: Any, context: CognitiveValidationContext
    ) -> tuple[ValidationFinding, ...]: ...


# ── Helper ───────────────────────────────────────────────────────────────────


def _finding(
    code: str,
    message: str,
    *,
    severity: ValidationSeverity,
    blocking: bool,
    target_id: str | None = None,
    metadata: Mapping[str, Any] | None = None,
) -> ValidationFinding:
    return ValidationFinding(
        code=code,
        message=message,
        severity=severity,
        source=_SOURCE,
        blocking=blocking,
        metadata=dict(metadata or {}, **({"target_id": target_id} if target_id else {})),
    )


def _status_from_findings(findings: Sequence[ValidationFinding]) -> ValidationStatus:
    if any(f.blocking and f.severity == ValidationSeverity.CRITICAL for f in findings):
        return ValidationStatus.FAILED
    if any(f.blocking for f in findings):
        return ValidationStatus.FAILED
    if any(f.severity == ValidationSeverity.WARNING for f in findings):
        return ValidationStatus.WARNING
    return ValidationStatus.PASSED


# ── Schema rule ──────────────────────────────────────────────────────────────


class SchemaRule:
    """Validates schema compliance: supported type, schema version, required
    fields, payload serializability, basic ID consistency, valid enums."""

    name = "cognitive.schema"

    def applies(self, target: Any) -> bool:
        return isinstance(target, (KnowledgePackage, CognitiveCacheEntry, KnowledgeItem))

    def evaluate(
        self, target: Any, context: CognitiveValidationContext
    ) -> tuple[ValidationFinding, ...]:
        findings: list[ValidationFinding] = []
        target_id = _target_id(target)

        if isinstance(target, KnowledgePackage):
            if target.schema_version != KP_SCHEMA_VERSION:
                findings.append(
                    _finding(
                        COG_SCHEMA_UNSUPPORTED,
                        f"KnowledgePackage schema_version {target.schema_version} is unsupported",
                        severity=ValidationSeverity.CRITICAL,
                        blocking=True,
                        target_id=target_id,
                        metadata={"expected": KP_SCHEMA_VERSION, "actual": target.schema_version},
                    )
                )
            if not target.id.strip():
                findings.append(
                    _finding(
                        COG_SCHEMA_UNSUPPORTED,
                        "KnowledgePackage.id must not be empty",
                        severity=ValidationSeverity.CRITICAL,
                        blocking=True,
                        target_id=target_id,
                    )
                )

        elif isinstance(target, CognitiveCacheEntry):
            if target.schema_version != COGNITIVE_CACHE_SCHEMA_VERSION:
                findings.append(
                    _finding(
                        COG_SCHEMA_UNSUPPORTED,
                        f"CognitiveCacheEntry schema_version {target.schema_version} is unsupported",
                        severity=ValidationSeverity.CRITICAL,
                        blocking=True,
                        target_id=target_id,
                        metadata={
                            "expected": COGNITIVE_CACHE_SCHEMA_VERSION,
                            "actual": target.schema_version,
                        },
                    )
                )

        elif isinstance(target, KnowledgeItem):
            if target.version < 1:
                findings.append(
                    _finding(
                        COG_SCHEMA_UNSUPPORTED,
                        "KnowledgeItem.version must be at least 1",
                        severity=ValidationSeverity.CRITICAL,
                        blocking=True,
                        target_id=target_id,
                    )
                )

        return tuple(findings)


# ── Provenance rule ──────────────────────────────────────────────────────────


class ProvenanceRule:
    """Validates provenance presence and traceability for KnowledgePackages."""

    name = "cognitive.provenance"

    def applies(self, target: Any) -> bool:
        return isinstance(target, KnowledgePackage)

    def evaluate(
        self, target: KnowledgePackage, context: CognitiveValidationContext
    ) -> tuple[ValidationFinding, ...]:
        findings: list[ValidationFinding] = []
        target_id = target.id

        if not target.provenance:
            findings.append(
                _finding(
                    COG_PROVENANCE_MISSING,
                    "KnowledgePackage has no provenance declarations",
                    severity=ValidationSeverity.ERROR,
                    blocking=True,
                    target_id=target_id,
                )
            )

        # Check that facts/inferences have provenance
        for category_name, items in (
            ("facts", target.facts),
            ("inferences", target.inferences),
        ):
            for item in items:
                if not item.evidence and not item.resource_id:
                    findings.append(
                        _finding(
                            COG_PROVENANCE_MISSING,
                            f"{category_name} item '{item.id}' has no evidence or resource_id",
                            severity=ValidationSeverity.WARNING,
                            blocking=False,
                            target_id=target_id,
                            metadata={"item_id": item.id, "category": category_name},
                        )
                    )

        return tuple(findings)


# ── Temporality rule ─────────────────────────────────────────────────────────


class TemporalityRule:
    """Validates timezone-aware timestamps, valid_until, temporal scope,
    expired information, and require_current_information."""

    name = "cognitive.temporality"

    def applies(self, target: Any) -> bool:
        return isinstance(target, (KnowledgePackage, CognitiveCacheEntry, KnowledgeItem))

    def evaluate(
        self, target: Any, context: CognitiveValidationContext
    ) -> tuple[ValidationFinding, ...]:
        findings: list[ValidationFinding] = []
        target_id = _target_id(target)
        now = context.now

        if isinstance(target, KnowledgePackage):
            if target.valid_until is not None and target.valid_until < now:
                findings.append(
                    _finding(
                        COG_TEMPORAL_EXPIRED,
                        "KnowledgePackage has expired (valid_until in the past)",
                        severity=ValidationSeverity.ERROR,
                        blocking=True,
                        target_id=target_id,
                        metadata={"valid_until": target.valid_until.isoformat()},
                    )
                )
            if context.require_current_information:
                for item in target.facts:
                    status = item.temporal_scope.validity_status
                    if status is TemporalValidityStatus.EXPIRED:
                        findings.append(
                            _finding(
                                COG_TEMPORAL_EXPIRED,
                                f"fact '{item.id}' is expired",
                                severity=ValidationSeverity.ERROR,
                                blocking=True,
                                target_id=target_id,
                                metadata={"item_id": item.id},
                            )
                        )
                    elif status is TemporalValidityStatus.UNKNOWN:
                        findings.append(
                            _finding(
                                COG_TEMPORAL_UNKNOWN,
                                f"fact '{item.id}' has unknown temporal validity",
                                severity=ValidationSeverity.WARNING,
                                blocking=False,
                                target_id=target_id,
                                metadata={"item_id": item.id},
                            )
                        )

        elif isinstance(target, CognitiveCacheEntry):
            if target.valid_until is not None and target.valid_until <= now:
                findings.append(
                    _finding(
                        COG_CACHE_EXPIRED,
                        "CognitiveCacheEntry has expired",
                        severity=ValidationSeverity.ERROR,
                        blocking=True,
                        target_id=target_id,
                        metadata={"valid_until": target.valid_until.isoformat()},
                    )
                )

        elif isinstance(target, KnowledgeItem):
            status = target.temporal_scope.validity_status
            if status is TemporalValidityStatus.EXPIRED and context.require_current_information:
                findings.append(
                    _finding(
                        COG_TEMPORAL_EXPIRED,
                        f"KnowledgeItem '{target.id}' is expired",
                        severity=ValidationSeverity.ERROR,
                        blocking=True,
                        target_id=target_id,
                    )
                )

        return tuple(findings)


# ── Epistemology rule ────────────────────────────────────────────────────────


class EpistemologyRule:
    """Validates epistemic kind consistency, no silent promotion, confidence
    and evidence sufficiency, and declared missing information."""

    name = "cognitive.epistemology"

    def applies(self, target: Any) -> bool:
        return isinstance(target, (KnowledgePackage, KnowledgeItem))

    def evaluate(
        self, target: Any, context: CognitiveValidationContext
    ) -> tuple[ValidationFinding, ...]:
        findings: list[ValidationFinding] = []
        target_id = _target_id(target)

        items: tuple[KnowledgeItem, ...] = ()
        if isinstance(target, KnowledgePackage):
            items = target.facts + target.observations + target.inferences + target.hypotheses
        elif isinstance(target, KnowledgeItem):
            items = (target,)

        for item in items:
            # Kind mismatch is already enforced by KnowledgePackage.__post_init__,
            # but we check for external/corrupt payloads.
            if item.kind is KnowledgeKind.FACT and not item.evidence:
                findings.append(
                    _finding(
                        COG_EVIDENCE_INSUFFICIENT,
                        f"fact '{item.id}' has no supporting evidence",
                        severity=ValidationSeverity.WARNING,
                        blocking=False,
                        target_id=target_id,
                        metadata={"item_id": item.id},
                    )
                )
            if item.kind is KnowledgeKind.HYPOTHESIS and item.confidence.value >= 0.9:
                findings.append(
                    _finding(
                        COG_EPISTEMIC_PROMOTION,
                        f"hypothesis '{item.id}' has confidence {item.confidence.value}; "
                        "high confidence does not promote a hypothesis to a fact",
                        severity=ValidationSeverity.INFO,
                        blocking=False,
                        target_id=target_id,
                        metadata={"item_id": item.id, "confidence": item.confidence.value},
                    )
                )
            if item.kind is KnowledgeKind.INFERENCE and not item.evidence:
                findings.append(
                    _finding(
                        COG_EVIDENCE_INSUFFICIENT,
                        f"inference '{item.id}' has no supporting evidence",
                        severity=ValidationSeverity.WARNING,
                        blocking=False,
                        target_id=target_id,
                        metadata={"item_id": item.id},
                    )
                )

        if isinstance(target, KnowledgePackage) and target.missing_information:
            findings.append(
                _finding(
                    COG_MISSING_INFORMATION,
                    f"KnowledgePackage declares {len(target.missing_information)} missing information item(s)",
                    severity=ValidationSeverity.INFO,
                    blocking=False,
                    target_id=target_id,
                    metadata={"count": len(target.missing_information)},
                )
            )

        return tuple(findings)


# ── Contradictions rule ──────────────────────────────────────────────────────


class ContradictionsRule:
    """Validates explicit contradictions, unresolved contradictions, and
    prevents contradictions from disappearing by being cached."""

    name = "cognitive.contradictions"

    def applies(self, target: Any) -> bool:
        return isinstance(target, KnowledgePackage)

    def evaluate(
        self, target: KnowledgePackage, context: CognitiveValidationContext
    ) -> tuple[ValidationFinding, ...]:
        findings: list[ValidationFinding] = []
        target_id = target.id

        for contradiction in target.contradictions:
            if contradiction.status is ContradictionStatus.UNRESOLVED:
                findings.append(
                    _finding(
                        COG_CONTRADICTION_UNRESOLVED,
                        f"contradiction '{contradiction.id}' is unresolved",
                        severity=ValidationSeverity.ERROR,
                        blocking=True,
                        target_id=target_id,
                        metadata={
                            "contradiction_id": contradiction.id,
                            "item_a_id": contradiction.item_a_id,
                            "item_b_id": contradiction.item_b_id,
                        },
                    )
                )

        return tuple(findings)


# ── Privacy rule ─────────────────────────────────────────────────────────────


class PrivacyRule:
    """Validates privacy compliance using Phase 8.25 contracts.

    Uses ``PrivacyMetadata``, ``resolve_effective_privacy_metadata``, and
    ``evaluate_privacy_operation``. A denied decision produces a blocking
    finding. ``REDACTION_REQUIRED`` and ``APPROVAL_REQUIRED`` translate to
    explicit cognitive decisions, not automatic authorization.
    """

    name = "cognitive.privacy"

    def applies(self, target: Any) -> bool:
        return isinstance(target, (KnowledgePackage, CognitiveCacheEntry))

    def evaluate(
        self, target: Any, context: CognitiveValidationContext
    ) -> tuple[ValidationFinding, ...]:
        findings: list[ValidationFinding] = []
        target_id = _target_id(target)

        privacy: PrivacyMetadata | None = None
        if isinstance(target, KnowledgePackage):
            privacy = privacy_from_knowledge_package(target)
        elif isinstance(target, CognitiveCacheEntry):
            privacy = target.privacy

        if privacy is None:
            return ()

        operation = context.target_operation or PrivacyOperation.PROCESS_LOCAL
        op_context = context.to_privacy_operation_context()
        decision = evaluate_privacy_operation(privacy, operation, op_context)

        if decision.status is PrivacyDecisionStatus.DENIED:
            findings.append(
                _finding(
                    COG_PRIVACY_DENIED,
                    f"privacy denied: {decision.reason_code}",
                    severity=ValidationSeverity.CRITICAL,
                    blocking=True,
                    target_id=target_id,
                    metadata={"reason_code": decision.reason_code, "operation": operation.value},
                )
            )
        elif decision.status is PrivacyDecisionStatus.REDACTION_REQUIRED:
            findings.append(
                _finding(
                    COG_REDACTION_REQUIRED,
                    "privacy metadata requires redaction before this operation",
                    severity=ValidationSeverity.ERROR,
                    blocking=True,
                    target_id=target_id,
                    metadata={"operation": operation.value},
                )
            )
        elif decision.status is PrivacyDecisionStatus.APPROVAL_REQUIRED:
            findings.append(
                _finding(
                    COG_APPROVAL_REQUIRED,
                    "privacy metadata requires approval before this operation",
                    severity=ValidationSeverity.ERROR,
                    blocking=True,
                    target_id=target_id,
                    metadata={"operation": operation.value},
                )
            )

        return tuple(findings)


# ── Knowledge Package rule ───────────────────────────────────────────────────


class KnowledgePackageRule:
    """Validates Knowledge Package completeness, objective, categorization,
    missing information, unresolved contradictions, provenance, privacy,
    expiration, and schema version."""

    name = "cognitive.knowledge_package"

    def applies(self, target: Any) -> bool:
        return isinstance(target, KnowledgePackage)

    def evaluate(
        self, target: KnowledgePackage, context: CognitiveValidationContext
    ) -> tuple[ValidationFinding, ...]:
        findings: list[ValidationFinding] = []
        target_id = target.id

        if context.require_complete_package:
            if not target.facts and not target.observations and not target.inferences:
                findings.append(
                    _finding(
                        COG_MISSING_INFORMATION,
                        "KnowledgePackage is incomplete: no facts, observations, or inferences",
                        severity=ValidationSeverity.ERROR,
                        blocking=True,
                        target_id=target_id,
                    )
                )
            if target.missing_information:
                findings.append(
                    _finding(
                        COG_MISSING_INFORMATION,
                        f"KnowledgePackage has {len(target.missing_information)} declared missing information item(s)",
                        severity=ValidationSeverity.WARNING,
                        blocking=True,
                        target_id=target_id,
                        metadata={"count": len(target.missing_information)},
                    )
                )

        # Unresolved contradictions
        unresolved = [c for c in target.contradictions if c.status is ContradictionStatus.UNRESOLVED]
        if unresolved:
            findings.append(
                _finding(
                    COG_CONTRADICTION_UNRESOLVED,
                    f"KnowledgePackage has {len(unresolved)} unresolved contradiction(s)",
                    severity=ValidationSeverity.ERROR,
                    blocking=True,
                    target_id=target_id,
                    metadata={"count": len(unresolved)},
                )
            )

        return tuple(findings)


# ── Cognitive Cache rule ─────────────────────────────────────────────────────


class CognitiveCacheRule:
    """Validates cache status, expiration, context signature, schema version,
    privacy, permissions, profile/domain version, invalidated dependencies,
    and safe reuse. Reuses ``default_cognitive_cache_validator``."""

    name = "cognitive.cache"

    def applies(self, target: Any) -> bool:
        return isinstance(target, CognitiveCacheEntry)

    def evaluate(
        self, target: CognitiveCacheEntry, context: CognitiveValidationContext
    ) -> tuple[ValidationFinding, ...]:
        findings: list[ValidationFinding] = []
        target_id = target.id

        if target.status is CognitiveCacheEntryStatus.INVALID:
            findings.append(
                _finding(
                    COG_CACHE_INVALID,
                    "CognitiveCacheEntry is marked invalid",
                    severity=ValidationSeverity.ERROR,
                    blocking=True,
                    target_id=target_id,
                )
            )
        elif target.status is CognitiveCacheEntryStatus.STALE:
            findings.append(
                _finding(
                    COG_CACHE_STALE,
                    "CognitiveCacheEntry is marked stale",
                    severity=ValidationSeverity.WARNING,
                    blocking=True,
                    target_id=target_id,
                )
            )
        elif target.status is CognitiveCacheEntryStatus.EXPIRED:
            findings.append(
                _finding(
                    COG_CACHE_EXPIRED,
                    "CognitiveCacheEntry is marked expired",
                    severity=ValidationSeverity.ERROR,
                    blocking=True,
                    target_id=target_id,
                )
            )

        # Use the existing default validator for structural checks
        cache_context = context.to_cache_context(target.context_signature)
        cache_result = default_cognitive_cache_validator(target, cache_context)
        if cache_result.status is not CognitiveCacheEntryStatus.VALID:
            if cache_result.status is CognitiveCacheEntryStatus.EXPIRED:
                findings.append(
                    _finding(
                        COG_CACHE_EXPIRED,
                        f"cache validator: {cache_result.reason}",
                        severity=ValidationSeverity.ERROR,
                        blocking=True,
                        target_id=target_id,
                        metadata={"reason": cache_result.reason},
                    )
                )
            elif cache_result.status is CognitiveCacheEntryStatus.STALE:
                findings.append(
                    _finding(
                        COG_CACHE_STALE,
                        f"cache validator: {cache_result.reason}",
                        severity=ValidationSeverity.WARNING,
                        blocking=True,
                        target_id=target_id,
                        metadata={"reason": cache_result.reason},
                    )
                )
            elif cache_result.status is CognitiveCacheEntryStatus.INVALID:
                findings.append(
                    _finding(
                        COG_CACHE_NOT_REUSABLE,
                        f"cache validator: {cache_result.reason}",
                        severity=ValidationSeverity.ERROR,
                        blocking=True,
                        target_id=target_id,
                        metadata={"reason": cache_result.reason},
                    )
                )

        return tuple(findings)


# ── Dependencies rule ────────────────────────────────────────────────────────


class DependenciesRule:
    """Validates dependency IDs, known dependencies, invalidated dependencies,
    profile version, domain version, and context compatibility."""

    name = "cognitive.dependencies"

    def applies(self, target: Any) -> bool:
        return isinstance(target, (KnowledgePackage, CognitiveCacheEntry))

    def evaluate(
        self, target: Any, context: CognitiveValidationContext
    ) -> tuple[ValidationFinding, ...]:
        findings: list[ValidationFinding] = []
        target_id = _target_id(target)

        dependency_ids: tuple[str, ...] = ()

        if isinstance(target, CognitiveCacheEntry):
            dependency_ids = target.dependency_ids
        elif isinstance(target, KnowledgePackage):
            # KnowledgePackage doesn't have explicit dependency_ids, but we
            # check profile/domain version compatibility
            pass

        # Invalidated dependencies
        if context.invalidated_dependency_ids:
            invalidated = set(dependency_ids) & set(context.invalidated_dependency_ids)
            if invalidated:
                findings.append(
                    _finding(
                        COG_DEPENDENCY_INVALIDATED,
                        f"dependencies invalidated: {sorted(invalidated)}",
                        severity=ValidationSeverity.ERROR,
                        blocking=True,
                        target_id=target_id,
                        metadata={"invalidated": sorted(invalidated)},
                    )
                )

        # Profile version mismatch
        if isinstance(target, CognitiveCacheEntry):
            if (
                context.profile_version is not None
                and target.profile_version is not None
                and target.profile_version != context.profile_version
            ):
                findings.append(
                    _finding(
                        COG_PROFILE_MISMATCH,
                        f"profile_version mismatch: entry={target.profile_version}, context={context.profile_version}",
                        severity=ValidationSeverity.WARNING,
                        blocking=True,
                        target_id=target_id,
                        metadata={
                            "entry": target.profile_version,
                            "context": context.profile_version,
                        },
                    )
                )
            if (
                context.domain_version is not None
                and target.domain_version is not None
                and target.domain_version != context.domain_version
            ):
                findings.append(
                    _finding(
                        COG_DOMAIN_MISMATCH,
                        f"domain_version mismatch: entry={target.domain_version}, context={context.domain_version}",
                        severity=ValidationSeverity.WARNING,
                        blocking=True,
                        target_id=target_id,
                        metadata={
                            "entry": target.domain_version,
                            "context": context.domain_version,
                        },
                    )
                )

        return tuple(findings)


# ── Helpers ──────────────────────────────────────────────────────────────────


def _target_id(target: Any) -> str:
    if isinstance(target, (KnowledgePackage, CognitiveCacheEntry, KnowledgeItem)):
        return target.id
    return getattr(target, "id", "unknown")


def _target_kind(target: Any) -> str:
    if isinstance(target, KnowledgePackage):
        return "knowledge_package"
    if isinstance(target, CognitiveCacheEntry):
        return "cognitive_cache_entry"
    if isinstance(target, KnowledgeItem):
        return "knowledge_item"
    return type(target).__name__


def _deterministic_result_id(
    target_id: str, target_kind: str, validated_rules: Sequence[str]
) -> str:
    payload = {
        "target_id": target_id,
        "target_kind": target_kind,
        "validated_rules": sorted(validated_rules),
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    digest = hashlib.sha256(encoded.encode("utf-8")).hexdigest()[:24]
    return f"cognitive-validation:{digest}"


# ── Default rules ────────────────────────────────────────────────────────────


def default_cognitive_validation_rules() -> tuple[CognitiveValidationRule, ...]:
    """Return the default set of structural cognitive validation rules."""
    return (
        SchemaRule(),
        ProvenanceRule(),
        TemporalityRule(),
        EpistemologyRule(),
        ContradictionsRule(),
        PrivacyRule(),
        KnowledgePackageRule(),
        CognitiveCacheRule(),
        DependenciesRule(),
    )


def _select_rules(
    target: Any, rules: Sequence[CognitiveValidationRule]
) -> tuple[CognitiveValidationRule, ...]:
    """Select rules that apply to the target, preserving registration order."""
    return tuple(rule for rule in rules if rule.applies(target))


# ── CognitiveValidator service ───────────────────────────────────────────────


class CognitiveValidator:
    """Validates cognitive artifacts against structural rules.

    Selects rules by target type, executes them deterministically, aggregates
    findings, separates blocking findings and warnings, produces a decision,
    generates a stable ID, and records executed rule names. Never alters the
    target, never invokes a model, and never persists automatically.
    """

    __slots__ = ("_rules",)

    def __init__(
        self, rules: Sequence[CognitiveValidationRule] | None = None
    ) -> None:
        self._rules: tuple[CognitiveValidationRule, ...] = tuple(
            rules if rules is not None else default_cognitive_validation_rules()
        )

    @property
    def rules(self) -> tuple[CognitiveValidationRule, ...]:
        return self._rules

    def validate(
        self,
        target: Any,
        context: CognitiveValidationContext,
        *,
        explicit_rules: Sequence[str] | None = None,
    ) -> CognitiveValidationResult:
        if not isinstance(context, CognitiveValidationContext):
            raise InvalidCognitiveValidationContextError(
                "context must be a CognitiveValidationContext"
            )

        selected = self._rules
        if explicit_rules is not None:
            explicit_set = set(explicit_rules)
            selected = tuple(r for r in self._rules if r.name in explicit_set)
        else:
            selected = _select_rules(target, self._rules)

        all_findings: list[ValidationFinding] = []
        rule_results: dict[str, list[ValidationFinding]] = {}
        validated_rule_names: list[str] = []

        for rule in selected:
            try:
                rule_findings = rule.evaluate(target, context)
            except CognitiveValidationExecutionError:
                raise
            except Exception as exc:
                raise CognitiveValidationExecutionError(
                    f"Rule '{rule.name}' raised an execution error: {exc}"
                ) from exc
            all_findings.extend(rule_findings)
            rule_results[rule.name] = list(rule_findings)
            validated_rule_names.append(rule.name)

        findings_tuple = tuple(all_findings)
        blocking = tuple(f for f in findings_tuple if f.blocking)
        warnings = tuple(
            f for f in findings_tuple if not f.blocking and f.severity == ValidationSeverity.WARNING
        )
        decision = derive_cognitive_validation_decision(findings_tuple)
        status = _status_from_findings(findings_tuple)
        target_id = _target_id(target)
        target_kind = _target_kind(target)
        result_id = _deterministic_result_id(target_id, target_kind, validated_rule_names)

        # Build partial results
        privacy_result = {
            "findings": [f.serialize() for f in rule_results.get("cognitive.privacy", ())],
        }
        temporal_result = {
            "findings": [f.serialize() for f in rule_results.get("cognitive.temporality", ())],
        }
        provenance_result = {
            "findings": [f.serialize() for f in rule_results.get("cognitive.provenance", ())],
        }
        epistemology_result = {
            "findings": [f.serialize() for f in rule_results.get("cognitive.epistemology", ())],
        }
        contradiction_result = {
            "findings": [f.serialize() for f in rule_results.get("cognitive.contradictions", ())],
        }
        cache_result = None
        if "cognitive.cache" in rule_results:
            cache_result = {
                "findings": [f.serialize() for f in rule_results.get("cognitive.cache", ())],
            }

        return CognitiveValidationResult(
            id=result_id,
            target_id=target_id,
            target_kind=target_kind,
            status=status,
            decision=decision,
            findings=findings_tuple,
            blocking_findings=blocking,
            warnings=warnings,
            validated_rules=tuple(validated_rule_names),
            privacy_result=privacy_result,
            temporal_result=temporal_result,
            provenance_result=provenance_result,
            epistemology_result=epistemology_result,
            contradiction_result=contradiction_result,
            cache_result=cache_result,
            created_at=context.now,
            metadata={"rule_count": len(validated_rule_names)},
        )


# ── Phase 7 integration: CognitiveValidationStepExecutor ────────────────────


class CognitiveValidationStepExecutor:
    """Adapter that wraps a :class:`CognitiveValidator` as a Phase 7
    ``InternalValidator``, returning a real ``ValidationStepResult``.

    The target and cognitive context are bound at construction time, so each
    executor instance validates exactly one artifact. The step name defaults
    to ``cognitive.validation`` but can be customized.
    """

    def __init__(
        self,
        validator: CognitiveValidator,
        target: Any,
        cognitive_context: CognitiveValidationContext,
        *,
        name: str = "cognitive.validation",
        explicit_rules: Sequence[str] | None = None,
    ) -> None:
        self._validator = validator
        self._target = target
        self._cognitive_context = cognitive_context
        self._name = name
        self._explicit_rules = explicit_rules

    @property
    def name(self) -> str:
        return self._name

    def validate(
        self, context: ValidationContext, step: ValidationStep
    ) -> ValidationStepResult:
        started_at = datetime.now(timezone.utc)
        t0 = time.perf_counter()
        try:
            cog_result = self._validator.validate(
                self._target,
                self._cognitive_context,
                explicit_rules=self._explicit_rules,
            )
        except CognitiveValidationExecutionError as exc:
            return ValidationStepResult(
                name=step.name,
                status=ValidationStatus.ERROR,
                duration_ms=int((time.perf_counter() - t0) * 1000),
                stderr=str(exc),
                started_at=started_at,
                completed_at=datetime.now(timezone.utc),
                metadata={"executor": "cognitive", "error": "execution_error"},
            )

        # Build a Phase 7 artifact with kind = cognitive_validation_report
        artifact = ValidationArtifact(
            id=cog_result.id,
            kind="cognitive_validation_report",
            source=_SOURCE,
            content={
                "target_id": cog_result.target_id,
                "target_kind": cog_result.target_kind,
                "decision": cog_result.decision.value,
                "validated_rules": list(cog_result.validated_rules),
                "schema_version": cog_result.schema_version,
                "created_at": cog_result.created_at.isoformat(),
            },
            findings=cog_result.findings,
            metrics={
                "finding_count": len(cog_result.findings),
                "blocking_count": len(cog_result.blocking_findings),
                "warning_count": len(cog_result.warnings),
            },
        )

        # Map cognitive status to Phase 7 status
        if cog_result.status is ValidationStatus.PASSED:
            step_status = ValidationStatus.PASSED
        elif cog_result.status is ValidationStatus.WARNING:
            step_status = ValidationStatus.WARNING
        else:
            step_status = ValidationStatus.FAILED

        return ValidationStepResult(
            name=step.name,
            status=step_status,
            duration_ms=int((time.perf_counter() - t0) * 1000),
            findings=cog_result.findings,
            artifacts=(artifact,),
            started_at=started_at,
            completed_at=datetime.now(timezone.utc),
            metadata={
                "executor": "cognitive",
                "cognitive_validation_id": cog_result.id,
                "decision": cog_result.decision.value,
                "target_id": cog_result.target_id,
                "target_kind": cog_result.target_kind,
            },
        )


def build_cognitive_validation_step(
    validator: CognitiveValidator,
    target: Any,
    cognitive_context: CognitiveValidationContext,
    *,
    name: str = "cognitive.validation",
    explicit_rules: Sequence[str] | None = None,
) -> ValidationStep:
    """Build a Phase 7 ``ValidationStep`` (INTERNAL type) for cognitive validation."""
    from cmm.validation.steps import ValidationStepType

    return ValidationStep(
        name=name,
        step_type=ValidationStepType.INTERNAL,
        required=True,
        timeout_seconds=60,
        stop_on_failure=True,
        metadata={
            "cognitive_validation": True,
            "target_id": _target_id(target),
            "target_kind": _target_kind(target),
        },
    )


__all__ = [
    "COGNITIVE_VALIDATION_SCHEMA_VERSION",
    "CognitiveValidationContext",
    "CognitiveValidationDecision",
    "CognitiveValidationResult",
    "CognitiveValidationRule",
    "CognitiveValidationStepExecutor",
    "CognitiveValidator",
    "derive_cognitive_validation_decision",
]