"""Phase 10.24 — Reflection temporal evolution tests.

``compare_reflection_versions`` and ``ReflectionTemporalEvolutionRule`` compare
how an idea, belief, value, hypothesis, or identity narrative changes over time
using grounded chronology only.  Input order, equal timestamps, malformed
dates, and missing dates never manufacture directional evolution (spec §12,
§27, §41).
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

from cmm.cognitive.enums import ReasoningRuleResultStatus
from cmm.cognitive.reasoning_rule_contracts import ReasoningRuleContext
from cmm.domains.reflection.rules import (
    ReflectionTemporalEvolutionRule,
    compare_reflection_versions,
)

NOW = datetime(2026, 8, 1, tzinfo=timezone.utc)


def _version(version_id, identity, observed_at, content, *, source=None,
             grounded=None, contradiction=False, uncertain=False):
    return {
        "version_id": version_id,
        "identity": identity,
        "observed_at": observed_at,
        "content": content,
        "source": source,
        "grounded": grounded,
        "contradiction": contradiction,
        "uncertain": uncertain,
    }


def test_valid_ordered_dates_allow_directional_evolution():
    result = compare_reflection_versions(
        versions=(
            _version("v1", "belief:trust", "2026-01-01", "I trust them",
                     source="note:1", grounded=True),
            _version("v2", "belief:trust", "2026-08-01", "I no longer trust them",
                     source="note:2", grounded=True),
        )
    )
    assert result["chronology_state"] == "ordered"
    assert result["temporally_ordered"] is True
    assert len(result["changes"]) == 1
    change = result["changes"][0]
    assert change["from_version_id"] == "v1"
    assert change["to_version_id"] == "v2"
    assert change["changed"] is True


def test_same_exact_timestamp_z_and_offset_no_direction():
    result = compare_reflection_versions(
        versions=(
            _version("v1", "idea:x", "2026-08-01T10:00:00Z", "A"),
            _version("v2", "idea:x", "2026-08-01T10:00:00+00:00", "B"),
        )
    )
    assert result["chronology_state"] == "equal_timestamps"
    assert result["temporally_ordered"] is False
    assert result["equal_timestamps_no_evolution"] is True
    assert result["changes"] == ()


def test_same_date_only_value_no_direction():
    result = compare_reflection_versions(
        versions=(
            _version("v1", "idea:x", "2026-08-01", "A"),
            _version("v2", "idea:x", "2026-08-01", "B"),
        )
    )
    assert result["chronology_state"] == "equal_timestamps"
    assert result["temporally_ordered"] is False
    assert result["equal_timestamps_no_evolution"] is True


def test_malformed_date_no_direction():
    result = compare_reflection_versions(
        versions=(
            _version("v1", "idea:x", "not-a-date", "A"),
            _version("v2", "idea:x", "2026-08-01", "B"),
        )
    )
    assert result["chronology_state"] == "malformed"
    assert result["temporally_ordered"] is False
    assert result["changes"] == ()


def test_missing_date_chronology_unknown():
    result = compare_reflection_versions(
        versions=(
            _version("v1", "idea:x", None, "A"),
            _version("v2", "idea:x", "2026-08-01", "B"),
        )
    )
    assert result["chronology_state"] == "unknown"
    assert result["temporally_ordered"] is False
    assert result["changes"] == ()


def test_input_order_permutations_identical():
    versions = (
        _version("v1", "belief:x", "2026-01-01", "one", grounded=True),
        _version("v2", "belief:x", "2026-06-01", "two", grounded=True),
        _version("v3", "belief:x", "2026-12-01", "three", grounded=True),
    )
    import itertools

    results = [
        compare_reflection_versions(versions=tuple(order))
        for order in itertools.permutations(versions)
    ]
    canonical = {
        (
            result["chronology_state"],
            result["temporally_ordered"],
            tuple(
                (c["from_version_id"], c["to_version_id"], c["changed"])
                for c in result["changes"]
            ),
        )
        for result in results
    }
    assert len(canonical) == 1


def test_rephrased_wording_is_not_substantive_change():
    result = compare_reflection_versions(
        versions=(
            _version("v1", "belief:x", "2026-01-01", "I feel anxious about moving"),
            _version("v2", "belief:x", "2026-02-01", "moving makes me feel anxious"),
        )
    )
    assert result["chronology_state"] == "ordered"
    change = result["changes"][0]
    assert change["changed"] is False
    assert change["rephrased"] is True
    assert change["stable"] is True


def test_repetition_is_not_persistence():
    result = compare_reflection_versions(
        versions=(
            _version("v1", "belief:x", "2026-01-01", "repeated claim", grounded=True),
            _version("v2", "belief:x", "2026-06-01", "repeated claim", grounded=True),
        )
    )
    # identical content repeated over time is stable, not persistent evidence
    assert result["chronology_state"] == "ordered"
    assert result["changes"][0]["changed"] is False
    assert result["changes"][0]["persistence_established"] is False


def test_newer_ungrounded_record_is_not_current_truth():
    result = compare_reflection_versions(
        versions=(
            _version("v1", "belief:x", "2026-01-01", "grounded claim", grounded=True),
            _version("v2", "belief:x", "2026-06-01", "newer claim", grounded=False),
        )
    )
    assert result["chronology_state"] == "ordered"
    assert result["newest_is_current_truth"] is False


def test_temporal_rule_applied():
    context = ReasoningRuleContext(
        reasoning_id="rr-temp-1",
        timestamp=NOW,
        active_domains=("domain:reflection",),
        primary_domain="domain:reflection",
        metadata={
            "versions": (
                _version("v1", "belief:x", "2026-01-01", "one", grounded=True),
                _version("v2", "belief:x", "2026-08-01", "two", grounded=True),
            )
        },
    )
    rule = ReflectionTemporalEvolutionRule(definition=_definition())
    result = rule.evaluate(context)
    assert result.status is ReasoningRuleResultStatus.APPLIED
    finding = result.findings[0]
    assert finding.metadata["temporally_ordered"] is True
    assert finding.metadata["chronology_state"] == "ordered"
    json.dumps(finding.to_dict(), allow_nan=False)


def test_temporal_rule_not_applicable():
    context = ReasoningRuleContext(
        reasoning_id="rr-temp-2",
        timestamp=NOW,
        active_domains=("domain:reflection",),
        primary_domain="domain:reflection",
        metadata={},
    )
    rule = ReflectionTemporalEvolutionRule(definition=_definition())
    result = rule.evaluate(context)
    assert result.status is ReasoningRuleResultStatus.NOT_APPLICABLE


def _definition():
    from cmm.cognitive.enums import (
        ReasoningRiskLevel,
        ReasoningRuleCategory,
        ReasoningRuleScope,
        ReasoningRuleStatus,
    )
    from cmm.domains.rule_contracts import DomainReasoningRuleDefinition

    return DomainReasoningRuleDefinition(
        id="reflection.temporal_evolution",
        name="ReflectionTemporalEvolutionRule",
        version="1.0.0",
        scope=ReasoningRuleScope.DOMAIN,
        domain_id="domain:reflection",
        category=ReasoningRuleCategory.TEMPORALITY.value,
        status=ReasoningRuleStatus.ENABLED,
        priority=750,
        risk_level=ReasoningRiskLevel.LOW,
        deterministic=True,
        description="Reflection temporal evolution rule.",
        metadata={"phase": "10.24"},
    )