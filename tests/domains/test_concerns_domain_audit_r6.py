"""Phase 10.25 — Audit-remediation regression tests for caveat stacking and
objective risk grounding.

Remediates I-005 (catastrophic caveat stacking not implemented) and I-006
(evaluate_proportional_risk ignores evidence).  Remote negative possibilities
must not be appended as safety caveats merely because they are technically
possible; objective risk must not be inferred from subjective severity
without grounded evidence or an authorized specialized domain result.
"""

from __future__ import annotations

import json

from cmm.domains.concerns.rules import (
    evaluate_caveat_policy,
    evaluate_proportional_risk,
)

# ═════════════════════════════════════════════════════════════════════════════
# I-005: caveat stacking
# ═════════════════════════════════════════════════════════════════════════════


def test_remote_negative_possibilities_are_not_stacked_as_safety_caveats():
    """Proposed remote negative scenarios without grounding/materiality must
    be dropped or flagged, never appended as safety padding (frozen §24.1,
    §88.4)."""
    proposed = (
        {
            "caveat": "the plane could crash",
            "grounding": None,
            "materiality": "remote_possibility",
            "relevance": "low",
            "source": "user hypothetical",
            "uncertainty": "high",
        },
        {
            "caveat": "they could be secretly offended",
            "grounding": None,
            "materiality": "remote_possibility",
            "relevance": "low",
            "source": "user hypothetical",
            "uncertainty": "high",
        },
        {
            "caveat": "the job offer could be rescinded for any reason",
            "grounding": None,
            "materiality": "remote_possibility",
            "relevance": "low",
            "source": "user hypothetical",
            "uncertainty": "high",
        },
    )
    record = evaluate_caveat_policy(caveats=proposed)
    assert record["retained"] == ()
    assert record["suppression_reason"] == "unsupported_remote_possibilities"
    # A long list of technical possibilities never grows the safe caveat set.
    assert len(record["retained"]) == 0


def test_one_material_warning_is_preserved_without_remote_caveat_expansion():
    """A real material warning survives; remote possibilities around it are
    not added."""
    proposed = (
        {
            "caveat": "documented missed safety checks",
            "grounding": "audit:1",
            "materiality": "material_warning",
            "relevance": "high",
            "source": "audit report",
            "uncertainty": "low",
        },
        {
            "caveat": "the machine could also catch fire",
            "grounding": None,
            "materiality": "remote_possibility",
            "relevance": "low",
            "source": "user hypothetical",
            "uncertainty": "high",
        },
        {
            "caveat": "a meteor could hit the building",
            "grounding": None,
            "materiality": "remote_possibility",
            "relevance": "low",
            "source": "user hypothetical",
            "uncertainty": "high",
        },
    )
    record = evaluate_caveat_policy(caveats=proposed)
    assert any("missed safety checks" in str(item) for item in record["retained"])
    # The two remote possibilities are not stacked onto the real warning.
    assert not any("catch fire" in str(item) for item in record["retained"])
    assert not any("meteor" in str(item) for item in record["retained"])


def test_caveat_count_does_not_grow_from_technical_possibility_alone():
    """Cumulative caveat counts must not increase merely because more
    technically-possible negatives are listed."""
    one = evaluate_caveat_policy(
        caveats=({"caveat": "x might fail", "materiality": "remote_possibility"},)
    )
    many = evaluate_caveat_policy(
        caveats=(
            {"caveat": "x might fail", "materiality": "remote_possibility"},
            {"caveat": "y might fail", "materiality": "remote_possibility"},
            {"caveat": "z might fail", "materiality": "remote_possibility"},
        )
    )
    assert len(one["retained"]) == len(many["retained"])
    assert many["suppressed_count"] >= 3


def test_material_warning_with_grounding_survives_stacking_guard():
    record = evaluate_caveat_policy(
        caveats=(
            {
                "caveat": "fever with neck stiffness",
                "grounding": "health:1",
                "materiality": "material_warning",
                "relevance": "high",
                "source": "clinical result",
                "uncertainty": "low",
            },
        )
    )
    assert len(record["retained"]) == 1
    json.dumps(record, allow_nan=False)


# ═════════════════════════════════════════════════════════════════════════════
# I-006: objective risk requires grounding
# ═════════════════════════════════════════════════════════════════════════════


def test_medium_subjective_severity_without_evidence_does_not_create_medium_objective_risk():
    """severity='medium' with no risk evidence and no specialized domain
    result must NOT create an objective medium risk state."""
    record = evaluate_proportional_risk(severity="medium", evidence=())
    assert record["risk_level"] not in ("medium", "high")
    assert record["risk_level"] in ("none", "unresolved")


def test_grounded_risk_evidence_changes_risk_state():
    """Grounded risk evidence changes the risk state from nothing to a
    calibrated level."""
    baseline = evaluate_proportional_risk(severity=None, evidence=())
    grounded = evaluate_proportional_risk(
        severity=None,
        evidence=(
            {
                "identity": "e1",
                "claim": "documented repeated safety incident",
                "stance": "supports_target",
                "grounding": "safety:1",
                "source_quality": "grounded",
                "temporal_relevance": "current",
            },
            {
                "identity": "e2",
                "claim": "recurring near-miss reports",
                "stance": "supports_target",
                "grounding": "safety:2",
                "source_quality": "grounded",
                "temporal_relevance": "current",
            },
        ),
    )
    assert baseline["risk_level"] in ("none", "unresolved")
    assert grounded["risk_level"] in ("low", "medium")
    assert grounded["risk_level"] != baseline["risk_level"]
    assert grounded["grounded_risk_evidence"] is True


def test_emotional_intensity_changes_lived_impact_not_objective_risk():
    """Emotional intensity alters lived impact, not objective risk.  Intensity
    wording (even recognized severity vocabulary) must never invent a higher
    objective risk without grounding."""
    evaluate_proportional_risk(severity="low", evidence=())  # noqa: intentionally unused
    intense = evaluate_proportional_risk(severity="overwhelming fear", evidence=())
    severe = evaluate_proportional_risk(severity="severe", evidence=())
    # Subjective intensity never produces objective high risk.
    assert intense["risk_level"] != "high"
    assert severe["risk_level"] != "high"
    # Grounded specialized red flags remain the only objective route to high.
    flagged = evaluate_proportional_risk(
        severity="calm",
        evidence=(),
        specialized_domain_result={
            "domain_id": "domain:health",
            "red_flags": ("red flag",),
            "authorized": True,
        },
    )
    assert flagged["risk_level"] == "high"
    assert flagged["specialized_ownership_preserved"] is True