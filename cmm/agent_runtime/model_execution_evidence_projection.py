"""Project safe Model Gateway facts into the canonical Agent Runtime record.

Phase 11.21 emits its own safe evidence record
(:class:`~kernel.llm.model_gateway_contracts.ModelExecutionFacts`) through an
injected seam.  Where an agent-run-scoped record is genuinely required, this
module is the narrow projection into the existing canonical
:class:`~cmm.agent_runtime.model_execution_contracts.ModelExecutionRecord`
instead of broadening that contract's ownership.

Two honesty rules are explicit here:

* the older record's token/cost fields are non-optional integers, so an unknown
  provider metric is written as the record's own default **and** marked in
  ``reason_codes``/``metadata`` (``usage_unknown:<field>``).  The gateway facts
  remain the source of truth for "unknown" versus "reported zero";
* no prompt, attachment content, credential or hidden reasoning is ever copied:
  only identifiers, safe decisions and normalized counters.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from cmm.agent_runtime.model_execution_contracts import (
    ContentRetentionMode,
    ModelExecutionRecord,
    ModelExecutionStatus,
)
from kernel.llm.model_gateway_contracts import ModelExecutionFacts, ModelUsage

__all__ = ["ModelExecutionEvidenceProjector"]

#: Token fields the older record cannot express as unknown.
_INTEGER_USAGE_FIELDS = ("input_tokens", "output_tokens", "cached_tokens")


class ModelExecutionEvidenceProjector:
    """Project gateway evidence into one canonical Agent Runtime record."""

    __slots__ = ("_agent_run_id", "_capability")

    def __init__(self, *, agent_run_id: str, capability: str = "model.call") -> None:
        if not isinstance(agent_run_id, str) or not agent_run_id.strip():
            raise ValueError("agent_run_id must be a non-empty string")
        if not isinstance(capability, str) or not capability.strip():
            raise ValueError("capability must be a non-empty string")
        self._agent_run_id = agent_run_id.strip()
        self._capability = capability.strip()

    def project(
        self,
        facts: ModelExecutionFacts,
        *,
        metadata: Mapping[str, Any] | None = None,
        **overrides: Any,
    ) -> ModelExecutionRecord:
        """Return one canonical record for ``facts``."""

        if not isinstance(facts, ModelExecutionFacts):
            raise TypeError("facts must be a ModelExecutionFacts instance")

        usage = facts.usage
        unknown = tuple(
            field for field in _INTEGER_USAGE_FIELDS if getattr(usage, field) is None
        )
        reason_codes = [
            facts.error_code or "model_call_succeeded",
            *(f"usage_unknown:{field}" for field in unknown),
            *(f"fallback_skipped:{entry}" for entry in facts.fallback_skipped),
        ]

        now = datetime.now(timezone.utc)
        values: dict[str, Any] = {
            "id": f"{facts.request_id}:execution",
            "agent_run_id": self._agent_run_id,
            "provider_id": facts.provider_id,
            "model_id": facts.model_id,
            "capability": self._capability,
            "input_tokens": usage.input_tokens or 0,
            "output_tokens": usage.output_tokens or 0,
            "cached_tokens": usage.cached_tokens or 0,
            "estimated_cost": _estimated_cost(usage),
            "actual_cost": _actual_cost(usage),
            "latency_ms": facts.latency_ms or 0,
            "retry_number": facts.retry_count,
            "fallback_trigger": "model_gateway_fallback_used"
            if facts.fallback_used
            else None,
            "execution_status": (
                ModelExecutionStatus.COMPLETED
                if facts.success
                else ModelExecutionStatus.FAILED
            ),
            "content_retention": ContentRetentionMode.HASHES_ONLY,
            "reason_codes": tuple(reason_codes),
            "created_at": now,
            "completed_at": now,
            "metadata": {
                "request_id": facts.request_id,
                "selection_mode": facts.selection_mode.value,
                "capability_decision": facts.capability_decision,
                "privacy_decision": facts.privacy_decision,
                "requested_reasoning_effort": (facts.requested_reasoning_effort.value),
                "effective_reasoning_effort": (facts.effective_reasoning_effort.value),
                "reasoning_used": facts.reasoning_used,
                "input_modalities": list(facts.input_modalities),
                "tool_use": facts.tool_use,
                "structured_output_use": facts.structured_output_use,
                "streamed": facts.streamed,
                "cancelled": facts.cancelled,
                "timed_out": facts.timed_out,
                "fallback_index": facts.fallback_index,
                "fallback_used": facts.fallback_used,
                "finish_reason": facts.finish_reason,
                "usage_unknown_fields": list(unknown),
                **dict(facts.metadata),
                **dict(metadata or {}),
            },
        }
        values.update(overrides)
        return ModelExecutionRecord(**values)


def _estimated_cost(usage: ModelUsage) -> Decimal:
    if usage.cost is not None and usage.cost_source == "catalog_derived":
        return usage.cost
    return Decimal(0)


def _actual_cost(usage: ModelUsage) -> Decimal | None:
    if usage.cost is not None and usage.cost_source == "provider_reported":
        return usage.cost
    return None
