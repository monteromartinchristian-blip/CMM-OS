"""Technical Memory Integration for Continuous Validation (Subphase 7.13).

Provides structured memory persistence for validation outcomes adhering to
confidentiality constraints and configurable retention policies.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from ..results import ValidationResult
from .contracts import ValidationDecision, ValidationMemoryRecord


class ValidationMemoryAdapter:
    """Adapter for persisting structured validation summaries into TechnicalMemory."""

    def __init__(
        self,
        technical_memory: Any | None = None,
        retention_policy: str = "blocking_only",
    ) -> None:
        """Initialize adapter.

        Args:
            technical_memory: TechnicalMemory or compatible knowledge store instance.
            retention_policy: Memory retention policy ('always', 'blocking_only', 'failed_only', 'gate_rejected', 'recurring', 'never').
        """
        self._technical_memory = technical_memory
        self._retention_policy = retention_policy
        self._records: list[ValidationMemoryRecord] = []

    @property
    def retention_policy(self) -> str:
        return self._retention_policy

    @property
    def records(self) -> tuple[ValidationMemoryRecord, ...]:
        return tuple(self._records)

    def should_remember(
        self,
        result: ValidationResult,
        decision: ValidationDecision | None = None,
    ) -> bool:
        """Evaluate retention policy to decide if record should be remembered."""
        pol = self._retention_policy.lower()
        if pol == "never":
            return False
        if pol == "always":
            return True

        has_blocking = (
            len(result.blocking_findings) > 0 or result.status.value == "failed"
        )
        is_failed = result.status.value in ("failed", "error", "timed_out")
        gate_rejected = (
            decision.gate_result is not None and not decision.gate_result.approved
            if decision
            else False
        )
        has_recurring = any(
            "recurring" in f.code.lower() for f in result.blocking_findings
        )

        if pol == "blocking_only":
            return has_blocking or gate_rejected
        if pol == "failed_only":
            return is_failed
        if pol == "gate_rejected":
            return gate_rejected
        if pol == "recurring":
            return has_recurring

        return has_blocking

    def remember_validation(
        self,
        result: ValidationResult,
        decision: ValidationDecision | None = None,
        rollback_requested: bool = False,
        rollback_success: bool | None = None,
        commit_hash: str | None = None,
    ) -> ValidationMemoryRecord | None:
        """Store structured summary of validation execution if policy allows."""
        if not self.should_remember(result, decision):
            return None

        finding_codes = tuple({f.code for f in result.blocking_findings})
        affected_files = tuple(str(f) for f in result.changed_files)
        affected_modules = tuple(
            f.stem for f in result.changed_files if f.suffix == ".py"
        )

        gate_approved = (
            decision.gate_result.approved
            if (decision and decision.gate_result is not None)
            else None
        )

        decision_str = decision.recommended_action.value if decision else "unknown"

        metrics = {
            "duration_ms": result.duration_ms,
            "blocking_findings_count": len(result.blocking_findings),
            "warnings_count": len(result.warnings),
            "total_steps": len(result.steps),
        }

        rec = ValidationMemoryRecord(
            validation_id=result.id,
            timestamp=result.started_at.isoformat()
            if result.started_at
            else datetime.now(timezone.utc).isoformat(),
            policy=result.policy or "default",
            change_type="code_modification" if affected_files else "inspection",
            status=result.status.value,
            decision=decision_str,
            recurring_finding_codes=finding_codes,
            affected_files=affected_files,
            affected_modules=affected_modules,
            gate_approved=gate_approved,
            rollback_requested=rollback_requested,
            rollback_successful=rollback_success,
            metrics=metrics,
            commit_hash=commit_hash,
        )

        self._records.append(rec)

        # Store in TechnicalMemory if available
        if self._technical_memory is not None:
            try:
                # Integrate gracefully with TechnicalMemory facade
                if hasattr(self._technical_memory, "record_validation"):
                    self._technical_memory.record_validation(rec.serialize())
                elif hasattr(self._technical_memory, "_repository"):
                    repo = self._technical_memory._repository
                    if hasattr(repo, "store_metadata"):
                        repo.store_metadata(
                            f"validation_{rec.validation_id}", rec.serialize()
                        )
            except Exception:  # noqa: BLE001, S110
                pass

        return rec
