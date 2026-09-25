"""Phase 11.21 — canonical execution-record projection tests.

The projection is intentionally lossy in one documented way: the older record's
integer token fields cannot express "unknown", so an unknown metric is written
as the record's default AND explicitly marked, never presented as a measured
zero.  Nothing unsafe may cross the projection.
"""

from __future__ import annotations

import json
from decimal import Decimal

import pytest

from cmm.agent_runtime.model_execution_contracts import (
    ModelExecutionRecord,
    ModelExecutionStatus,
)
from cmm.agent_runtime.model_execution_evidence_projection import (
    ModelExecutionEvidenceProjector,
)
from kernel.llm.model_gateway_contracts import (
    ModelExecutionFacts,
    ModelSelectionMode,
    ModelUsage,
    ReasoningEffort,
)


def _facts(**overrides: object) -> ModelExecutionFacts:
    values: dict[str, object] = {
        "request_id": "model-request-1",
        "provider_id": "local",
        "model_id": "model-1",
        "selection_mode": ModelSelectionMode.EXPLICIT,
        "success": True,
        "privacy_decision": "not_required",
    }
    values.update(overrides)
    return ModelExecutionFacts(**values)  # type: ignore[arg-type]


def _projector(**overrides: object) -> ModelExecutionEvidenceProjector:
    values: dict[str, object] = {"agent_run_id": "agent-run-1"}
    values.update(overrides)
    return ModelExecutionEvidenceProjector(**values)  # type: ignore[arg-type]


def test_projects_safe_facts_into_a_canonical_record() -> None:
    record = _projector().project(
        _facts(
            usage=ModelUsage(input_tokens=10, output_tokens=4, cached_tokens=2),
            latency_ms=42,
            retry_count=1,
            input_modalities=("text",),
            tool_use=True,
            finish_reason="stop",
        )
    )

    assert isinstance(record, ModelExecutionRecord)
    assert record.agent_run_id == "agent-run-1"
    assert record.provider_id == "local"
    assert record.model_id == "model-1"
    assert record.capability == "model.call"
    assert record.input_tokens == 10
    assert record.output_tokens == 4
    assert record.cached_tokens == 2
    assert record.latency_ms == 42
    assert record.retry_number == 1
    assert record.execution_status is ModelExecutionStatus.COMPLETED
    assert "model_call_succeeded" in record.reason_codes


def test_unknown_usage_is_marked_and_never_presented_as_measured() -> None:
    record = _projector().project(_facts())

    assert record.input_tokens == 0
    assert record.output_tokens == 0
    assert record.cached_tokens == 0
    assert "usage_unknown:input_tokens" in record.reason_codes
    assert "usage_unknown:output_tokens" in record.reason_codes
    assert "usage_unknown:cached_tokens" in record.reason_codes
    assert tuple(record.metadata["usage_unknown_fields"]) == (
        "input_tokens",
        "output_tokens",
        "cached_tokens",
    )


def test_known_zero_usage_is_not_marked_unknown() -> None:
    record = _projector().project(
        _facts(usage=ModelUsage(input_tokens=0, output_tokens=0, cached_tokens=0))
    )

    assert tuple(record.metadata["usage_unknown_fields"]) == ()
    assert not any(
        str(code).startswith("usage_unknown:") for code in record.reason_codes
    )


def test_provider_reported_cost_becomes_the_actual_cost() -> None:
    record = _projector().project(
        _facts(
            usage=ModelUsage(
                input_tokens=1,
                output_tokens=1,
                cost=Decimal("0.00100000"),
                cost_source="provider_reported",
            )
        )
    )

    assert record.actual_cost == Decimal("0.00100000")
    assert record.estimated_cost == Decimal(0)


def test_catalog_derived_cost_becomes_the_estimated_cost() -> None:
    record = _projector().project(
        _facts(
            usage=ModelUsage(
                input_tokens=1,
                output_tokens=1,
                cost=Decimal("0.00200000"),
                cost_source="catalog_derived",
            )
        )
    )

    assert record.estimated_cost == Decimal("0.00200000")
    assert record.actual_cost is None


def test_a_failed_call_is_projected_with_its_safe_error_code() -> None:
    record = _projector().project(
        _facts(success=False, error_code="PROVIDER_TIMEOUT", timed_out=True)
    )

    assert record.execution_status is ModelExecutionStatus.FAILED
    assert "PROVIDER_TIMEOUT" in record.reason_codes
    assert record.metadata["timed_out"] is True


def test_fallback_state_is_projected_safely() -> None:
    record = _projector().project(
        _facts(
            fallback_used=True,
            fallback_index=1,
            fallback_skipped=("fallback-a:secondary:CAPABILITY_UNSUPPORTED",),
        )
    )

    assert record.fallback_trigger == "model_gateway_fallback_used"
    assert record.metadata["fallback_index"] == 1
    assert any(
        str(code).startswith("fallback_skipped:") for code in record.reason_codes
    )


def test_reasoning_effort_is_projected_safely() -> None:
    record = _projector().project(
        _facts(
            requested_reasoning_effort=ReasoningEffort.HIGH,
            effective_reasoning_effort=ReasoningEffort.HIGH,
            reasoning_used=True,
        )
    )

    assert record.metadata["requested_reasoning_effort"] == "high"
    assert record.metadata["effective_reasoning_effort"] == "high"
    assert record.metadata["reasoning_used"] is True


def test_projection_carries_no_prompt_bytes_or_secret() -> None:
    record = _projector().project(
        _facts(metadata={"trace": "abc"}, input_modalities=("text", "image"))
    )

    serialized = json.dumps(record.to_dict()).lower()
    for forbidden in (
        "prompt",
        "api_key",
        "credential",
        "reasoning_trace",
        "chain_of_thought",
        "scratchpad",
        "provider_exception",
    ):
        assert f'"{forbidden}"' not in serialized


def test_projection_requires_agent_run_context() -> None:
    with pytest.raises(ValueError):
        ModelExecutionEvidenceProjector(agent_run_id="  ")

    with pytest.raises(TypeError):
        _projector().project("not-facts")  # type: ignore[arg-type]


def test_projection_defaults_stay_agent_runtime_owned() -> None:
    record = _projector().project(_facts())

    assert record.content_retention.value == "hashes_only"
    assert record.acceptance_status.value == "pending"
    assert record.validation_result_ids == ()
