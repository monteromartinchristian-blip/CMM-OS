from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from ..enums import ValidationSeverity
from ..errors import ValidationContractError
from ..findings import ValidationFinding
from .enums import CommitGateReasonCode


@dataclass(frozen=True, slots=True)
class CommitGateReason:
    code: CommitGateReasonCode
    message: str
    step: str | None = None
    artifact: str | None = None
    finding: ValidationFinding | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if isinstance(self.code, str) and not isinstance(
            self.code, CommitGateReasonCode
        ):
            try:
                object.__setattr__(self, "code", CommitGateReasonCode(self.code))
            except ValueError as exc:
                raise ValidationContractError(
                    f"Invalid CommitGateReasonCode string '{self.code}'"
                ) from exc
        elif not isinstance(self.code, CommitGateReasonCode):
            raise ValidationContractError(
                "CommitGateReason.code must be a valid CommitGateReasonCode"
            )
        if not self.message:
            raise ValidationContractError("CommitGateReason.message must not be empty")
        object.__setattr__(self, "metadata", dict(self.metadata or {}))

    def serialize(self) -> dict[str, Any]:
        return {
            "code": self.code.value,
            "message": self.message,
            "step": self.step,
            "artifact": self.artifact,
            "finding": self.finding.serialize() if self.finding is not None else None,
            "metadata": dict(self.metadata or {}),
        }

    @classmethod
    def from_mapping(cls, payload: Mapping[str, Any]) -> CommitGateReason:
        finding_raw = payload.get("finding")
        finding_obj = None
        if isinstance(finding_raw, Mapping):
            finding_obj = ValidationFinding(
                code=str(finding_raw["code"]),
                message=str(finding_raw["message"]),
                severity=ValidationSeverity(finding_raw["severity"]),
                source=str(finding_raw["source"]),
                blocking=bool(finding_raw.get("blocking", False)),
                line=finding_raw.get("line"),
                column=finding_raw.get("column"),
                suggested_fix=finding_raw.get("suggested_fix"),
                documentation_url=finding_raw.get("documentation_url"),
                metadata=dict(finding_raw.get("metadata", {})),
            )
        return cls(
            code=CommitGateReasonCode(payload["code"]),
            message=str(payload["message"]),
            step=payload.get("step"),
            artifact=payload.get("artifact"),
            finding=finding_obj,
            metadata=dict(payload.get("metadata", {}))
            if isinstance(payload.get("metadata"), Mapping)
            else {},
        )


@dataclass(frozen=True, slots=True)
class CommitGateResult:
    allowed: bool
    validation_result_id: str
    reasons: tuple[CommitGateReason, ...] = ()
    blocking_findings: tuple[ValidationFinding, ...] = ()
    policy_name: str | None = None
    evaluated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    authorization_required: bool = True
    authorized: bool = False
    commit_requested: bool = False
    commit_created: bool = False
    commit_hash: str | None = None
    commit_message: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.validation_result_id:
            raise ValidationContractError(
                "CommitGateResult.validation_result_id must not be empty"
            )

        # Defensive copies of tuples and dict
        object.__setattr__(self, "reasons", tuple(self.reasons or ()))
        object.__setattr__(
            self, "blocking_findings", tuple(self.blocking_findings or ())
        )
        object.__setattr__(self, "metadata", dict(self.metadata or {}))

        # Guarantee datetime timezone awareness
        if self.evaluated_at is not None and self.evaluated_at.tzinfo is None:
            object.__setattr__(
                self, "evaluated_at", self.evaluated_at.replace(tzinfo=timezone.utc)
            )

        # Verification of invariants
        if self.commit_created:
            if not self.commit_hash:
                raise ValidationContractError(
                    "CommitGateResult.commit_created=True requires non-empty commit_hash"
                )
            if not self.commit_message:
                raise ValidationContractError(
                    "CommitGateResult.commit_created=True requires non-empty commit_message"
                )
            if not self.authorized:
                raise ValidationContractError(
                    "CommitGateResult.commit_created=True cannot coexist with authorized=False"
                )
            if not self.commit_requested:
                raise ValidationContractError(
                    "CommitGateResult.commit_created=True cannot coexist with commit_requested=False"
                )
            if not self.allowed:
                raise ValidationContractError(
                    "CommitGateResult.commit_created=True cannot coexist with allowed=False"
                )
        else:
            if self.commit_hash is not None:
                raise ValidationContractError(
                    "CommitGateResult.commit_hash must be None when commit_created=False"
                )

    def serialize(self) -> dict[str, Any]:
        return {
            "allowed": self.allowed,
            "validation_result_id": self.validation_result_id,
            "reasons": [r.serialize() for r in self.reasons],
            "blocking_findings": [f.serialize() for f in self.blocking_findings],
            "policy_name": self.policy_name,
            "evaluated_at": self.evaluated_at.isoformat(),
            "authorization_required": self.authorization_required,
            "authorized": self.authorized,
            "commit_requested": self.commit_requested,
            "commit_created": self.commit_created,
            "commit_hash": self.commit_hash,
            "commit_message": self.commit_message,
            "metadata": dict(self.metadata or {}),
        }

    @classmethod
    def from_mapping(cls, payload: Mapping[str, Any]) -> CommitGateResult:
        reasons_raw = payload.get("reasons", ())
        reasons_list = []
        if isinstance(reasons_raw, (list, tuple)):
            for r in reasons_raw:
                if isinstance(r, Mapping):
                    reasons_list.append(CommitGateReason.from_mapping(r))
                elif isinstance(r, CommitGateReason):
                    reasons_list.append(r)

        findings_raw = payload.get("blocking_findings", ())
        findings_list = []
        if isinstance(findings_raw, (list, tuple)):
            for f in findings_raw:
                if isinstance(f, Mapping):
                    findings_list.append(
                        ValidationFinding(
                            code=str(f["code"]),
                            message=str(f["message"]),
                            severity=ValidationSeverity(f["severity"]),
                            source=str(f["source"]),
                            blocking=bool(f.get("blocking", False)),
                            line=f.get("line"),
                            column=f.get("column"),
                            suggested_fix=f.get("suggested_fix"),
                            documentation_url=f.get("documentation_url"),
                            metadata=dict(f.get("metadata", {})),
                        )
                    )
                elif isinstance(f, ValidationFinding):
                    findings_list.append(f)

        evaluated_at_raw = payload.get("evaluated_at")
        evaluated_at_dt = None
        if isinstance(evaluated_at_raw, str):
            evaluated_at_dt = datetime.fromisoformat(evaluated_at_raw)
        elif isinstance(evaluated_at_raw, datetime):
            evaluated_at_dt = evaluated_at_raw

        return cls(
            allowed=bool(payload["allowed"]),
            validation_result_id=str(payload["validation_result_id"]),
            reasons=tuple(reasons_list),
            blocking_findings=tuple(findings_list),
            policy_name=payload.get("policy_name"),
            evaluated_at=evaluated_at_dt or datetime.now(timezone.utc),
            authorization_required=bool(payload.get("authorization_required", True)),
            authorized=bool(payload.get("authorized", False)),
            commit_requested=bool(payload.get("commit_requested", False)),
            commit_created=bool(payload.get("commit_created", False)),
            commit_hash=payload.get("commit_hash"),
            commit_message=payload.get("commit_message"),
            metadata=dict(payload.get("metadata", {}))
            if isinstance(payload.get("metadata"), Mapping)
            else {},
        )


__all__ = ["CommitGateReason", "CommitGateResult"]
