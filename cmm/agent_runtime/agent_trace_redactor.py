"""Phase 9.19 – Agent Runtime Trace Redactor.

Redacts sensitive content from trace records before persistence.
Reuses existing sensitivity policy, permissions, and secret detection.
"""

from __future__ import annotations

import re
from typing import Any

from cmm.agent_runtime.agent_trace_contracts import (
    AgentTrace,
    AgentTraceRedactionReport,
)
from cmm.agent_runtime.enums import AgentTraceRedactionReason, AgentTraceStatus

# Patterns for detecting sensitive content
_SECRET_PATTERNS: list[tuple[str, AgentTraceRedactionReason, re.Pattern]] = [
    (
        "api_key",
        AgentTraceRedactionReason.SECRET,
        re.compile(
            r'(?i)(api[_-]?key|apikey|api_secret|api[_-]?token)\s*[:=]\s*["\']?[A-Za-z0-9_\-\.]{16,}["\']?'
        ),
    ),
    (
        "credential",
        AgentTraceRedactionReason.CREDENTIAL,
        re.compile(
            r'(?i)(password|passwd|pwd|secret|token|auth)\s*[:=]\s*["\']?[^\s"\'"]{8,}["\']?'
        ),
    ),
    (
        "private_key",
        AgentTraceRedactionReason.SECRET,
        re.compile(r"-----BEGIN (RSA |EC |DSA |OPENSSH )?PRIVATE KEY-----"),
    ),
    (
        "bearer_token",
        AgentTraceRedactionReason.CREDENTIAL,
        re.compile(r"(?i)bearer\s+[A-Za-z0-9_\-\.]{20,}"),
    ),
]

_PRIVATE_REASONING_FIELDS = frozenset(
    {
        "chain_of_thought",
        "internal_reasoning",
        "hidden_reasoning",
        "private_reasoning",
        "scratchpad",
        "reasoning_trace",
        "private_thoughts",
        "internal_notes",
    }
)

_PRIVATE_PROMPT_FIELDS = frozenset(
    {
        "prompt",
        "system_prompt",
        "user_prompt",
        "full_prompt",
        "private_prompt",
    }
)

_SENSITIVE_FIELD_PATTERNS = re.compile(
    r"(?i)(token|secret|password|credential|api_key|private_key|auth|session)"
)

_MAX_STRING_LENGTH = 10000


class AgentTraceRedactor:
    """Redacts sensitive content from trace records.

    Reuses existing sensitivity policy patterns.  Redaction is
    non-reversible: secrets are replaced with safe placeholders,
    not hashed.
    """

    def __init__(self, strict: bool = True) -> None:
        self._strict = strict

    def redact_trace(
        self, trace: AgentTrace
    ) -> tuple[AgentTrace, AgentTraceRedactionReport]:
        """Redact sensitive content from a trace.

        Returns a (redacted_trace, redaction_report) tuple.
        """
        redacted_fields: list[str] = []
        dropped_fields: list[str] = []
        reason_codes: list[str] = []
        retained_references: list[str] = []

        # Redact top-level metadata
        safe_metadata = self._redact_dict(
            trace.metadata, "metadata", redacted_fields, dropped_fields, reason_codes
        )

        # Build report
        report = AgentTraceRedactionReport(
            trace_id=trace.trace_id,
            redacted_fields=tuple(sorted(set(redacted_fields))),
            dropped_fields=tuple(sorted(set(dropped_fields))),
            reason_codes=tuple(sorted(set(reason_codes))),
            retained_references=tuple(sorted(set(retained_references))),
        )

        # If nothing was redacted, return original
        if not redacted_fields and not dropped_fields:
            return trace, report

        # Create redacted trace
        redacted = AgentTrace(
            trace_id=trace.trace_id,
            agent_run_id=trace.agent_run_id,
            goal_id=trace.goal_id,
            goal_created_by=trace.goal_created_by,
            agent_id=trace.agent_id,
            workflow_id=trace.workflow_id,
            autonomy_level=trace.autonomy_level,
            status=AgentTraceStatus.REDACTED.value
            if trace.status != AgentTraceStatus.REDACTED.value
            else trace.status,
            iterations=trace.iterations,
            observations=trace.observations,
            knowledge_loads=trace.knowledge_loads,
            cognitive_profiles=trace.cognitive_profiles,
            information_gaps=trace.information_gaps,
            questions=trace.questions,
            reasoning_result_ids=trace.reasoning_result_ids,
            runtime_decisions=trace.runtime_decisions,
            plans=trace.plans,
            policy_decisions=trace.policy_decisions,
            approval_requests=trace.approval_requests,
            approval_decisions=trace.approval_decisions,
            operations=trace.operations,
            resource_changes=trace.resource_changes,
            validations=trace.validations,
            recovery_decisions=trace.recovery_decisions,
            recovery_executions=trace.recovery_executions,
            checkpoints=trace.checkpoints,
            transactions=trace.transactions,
            outcome_evaluations=trace.outcome_evaluations,
            knowledge_updates=trace.knowledge_updates,
            memory_updates=trace.memory_updates,
            budget_events=trace.budget_events,
            warnings=trace.warnings,
            errors=trace.errors,
            stop_decision=trace.stop_decision,
            summary=trace.summary,
            started_at=trace.started_at,
            completed_at=trace.completed_at,
            duration_ms=trace.duration_ms,
            event_count=trace.event_count,
            source_event_ids=trace.source_event_ids,
            correlation_id=trace.correlation_id,
            metadata=safe_metadata,
            fingerprint=trace.fingerprint,
        )
        return redacted, report

    def redact_value(self, value: str, max_length: int = _MAX_STRING_LENGTH) -> str:
        """Redact a single string value if it contains sensitive content."""
        if len(value) > max_length:
            return value[:_MAX_STRING_LENGTH] + "... [truncated]"
        for _, reason, pattern in _SECRET_PATTERNS:
            if pattern.search(value):
                return "[REDACTED]"
        return value

    def _redact_dict(
        self,
        d: dict[str, Any],
        path: str,
        redacted_fields: list[str],
        dropped_fields: list[str],
        reason_codes: list[str],
    ) -> dict[str, Any]:
        """Recursively redact a dictionary."""
        result: dict[str, Any] = {}
        for key, value in d.items():
            field_path = f"{path}.{key}"

            # Check for private reasoning fields
            if key.lower() in _PRIVATE_REASONING_FIELDS:
                dropped_fields.append(field_path)
                reason_codes.append(AgentTraceRedactionReason.INTERNAL_REASONING.value)
                continue

            # Check for private prompt fields
            if key.lower() in _PRIVATE_PROMPT_FIELDS:
                dropped_fields.append(field_path)
                reason_codes.append(AgentTraceRedactionReason.PRIVATE_PROMPT.value)
                continue

            # Check for sensitive field names
            if _SENSITIVE_FIELD_PATTERNS.search(key):
                dropped_fields.append(field_path)
                reason_codes.append(AgentTraceRedactionReason.SECRET.value)
                continue

            # Recursively process dicts
            if isinstance(value, dict):
                result[key] = self._redact_dict(
                    value, field_path, redacted_fields, dropped_fields, reason_codes
                )
                continue

            # Redact strings
            if isinstance(value, str):
                if len(value) > _MAX_STRING_LENGTH:
                    result[key] = value[:_MAX_STRING_LENGTH] + "... [truncated]"
                    redacted_fields.append(field_path)
                    reason_codes.append(
                        AgentTraceRedactionReason.OVERSIZED_CONTENT.value
                    )
                    continue
                for _, reason, pattern in _SECRET_PATTERNS:
                    if pattern.search(value):
                        result[key] = "[REDACTED]"
                        redacted_fields.append(field_path)
                        reason_codes.append(reason.value)
                        break
                else:
                    result[key] = value
            else:
                result[key] = value

        return result

    def is_safe(self, value: Any) -> bool:
        """Check if a value is safe (no sensitive content detected)."""
        if isinstance(value, str):
            if len(value) > _MAX_STRING_LENGTH:
                return False
            for _, _, pattern in _SECRET_PATTERNS:
                if pattern.search(value):
                    return False
            return True
        if isinstance(value, dict):
            return all(self.is_safe(v) for v in value.values())
        if isinstance(value, (list, tuple)):
            return all(self.is_safe(v) for v in value)
        return True
