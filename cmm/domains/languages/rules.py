"""Phase 10.26 — Languages Domain Rules and deterministic helpers.

A declarative domain + pure deterministic language pedagogy/proficiency helpers.
The helper functions are state-free: no IO, no model calls, no registry mutation,
no internal clock. They receive context explicitly and return deterministic
strict JSON-safe structures.

Semantic invariants preserved here:
    certified proficiency != estimated proficiency;
    estimated proficiency != observed performance;
    global proficiency != proficiency by skill;
    preferred variety != only valid variety;
    different valid variety != error;
    framework mapping != identity;
    one error != recurrent error pattern;
    practice result != stable proficiency;
    one better score != stable progression;
    one bad session != stable regression;
    transcript != pronunciation evidence;
    certification readiness != general proficiency;
    teaching != assessment;
    practice != constant correction;
    session observation != persistent memory;
    candidate update != confirmed persistence;
    review schedule proposal != calendar mutation;
    certification preparation != registration/payment/submission.

Malformed evidence fails closed and never increases certainty, level,
or pattern support. Duplicates never inflate evidence.
Equivalent evidence sets yield equivalent results independent of input order.
All public outputs are strict JSON-safe; caller inputs are never mutated.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from cmm.cognitive.enums import (
    ReasoningRiskLevel,
    ReasoningRuleCategory,
    ReasoningRuleResultStatus,
    ReasoningRuleScope,
    ReasoningRuleStatus,
    ReasoningSeverity,
)
from cmm.cognitive.reasoning_rule_contracts import (
    ReasoningEscalation,
    ReasoningFinding,
    ReasoningGap,
    ReasoningRuleContext,
    ReasoningRuleDefinition,
    ReasoningRuleResult,
    ReasoningRuleTraceEntry,
)
from cmm.domains.languages.catalog import (
    CANONICAL_LANGUAGES_RULE_IDS,
)
from cmm.domains.rule_contracts import DomainReasoningRuleDefinition, DomainRuleResult

LANGUAGES_RULE_IDS: tuple[str, ...] = CANONICAL_LANGUAGES_RULE_IDS

CANONICAL_SKILL_DIMENSIONS: tuple[str, ...] = (
    "listening",
    "speaking",
    "reading",
    "writing",
    "grammar",
    "vocabulary",
    "pronunciation",
    "interaction",
)

CANONICAL_PROFICIENCY_KINDS: tuple[str, ...] = (
    "CERTIFIED",
    "ESTIMATED",
    "OBSERVED_PERFORMANCE",
)

KNOWN_VARIETIES: dict[str, tuple[str, ...]] = {
    "english": ("american english", "british english", "australian english", "canadian english", "general english"),
    "spanish": ("castilian spanish", "peninsular spanish", "latin american spanish", "mexican spanish", "rioplatense spanish"),
    "french": ("standard french", "canadian french"),
    "catalan": ("central catalan", "valencian", "balearic catalan", "north-western catalan"),
}

_CERTIFIED_SOURCE_KINDS = frozenset(
    {
        "official_certificate",
        "official_exam_result",
        "official_credential",
    }
)
_PRONUNCIATION_ASSESSMENT_SOURCE_KINDS = frozenset(
    {
        "acoustic_assessment",
        "pronunciation_assessment",
    }
)
_PROVENANCE_FIELDS = (
    "provenance_id",
    "source_id",
    "assessment_id",
    "sample_id",
    "context_id",
    "session_id",
)
_CERTIFICATION_PROVENANCE_FIELDS = (
    "provenance_id",
    "source_id",
    "official_source_id",
)


def normalize_json_value(value: Any) -> Any:
    """Normalize arbitrarily nested values to strict JSON-safe types."""
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        if math.isnan(value) or math.isinf(value):
            return None
        return value
    if isinstance(value, Mapping):
        return {str(k): normalize_json_value(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set, frozenset)):
        return [normalize_json_value(v) for v in value]
    return str(value)


def _canonical_json_value(value: Any) -> str:
    """Return a deterministic hashable representation of normalized JSON without module imports."""
    norm = normalize_json_value(value)
    if norm is None:
        return "null"
    if norm is True:
        return "true"
    if norm is False:
        return "false"
    if isinstance(norm, int):
        return str(norm)
    if isinstance(norm, float):
        return f"{norm:.8f}".rstrip("0").rstrip(".") if "." in f"{norm:.8f}" else str(norm)
    if isinstance(norm, str):
        escaped = norm.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n").replace("\r", "\\r").replace("\t", "\\t")
        return f'"{escaped}"'
    if isinstance(norm, list):
        items_str = ",".join(_canonical_json_value(x) for x in norm)
        return f"[{items_str}]"
    if isinstance(norm, Mapping):
        sorted_keys = sorted(str(k) for k in norm)
        pairs_str = ",".join(f"{_canonical_json_value(k)}:{_canonical_json_value(norm[k])}" for k in sorted_keys)
        return f"{{{pairs_str}}}"
    return f'"{norm!s}"'


def _safe_str(val: Any) -> str | None:
    if val is None or not isinstance(val, str):
        return None
    cleaned = val.strip()
    return cleaned if cleaned else None


def _canonical_provenance(record: Mapping[str, Any]) -> str | None:
    """Return occurrence provenance that is independent of caller aliases."""
    for field in _PROVENANCE_FIELDS:
        value = _safe_str(record.get(field))
        if value is not None:
            return value
    return None


def _certification_provenance(record: Mapping[str, Any]) -> str | None:
    """Return provenance grounded in an official certification source."""
    for field in _CERTIFICATION_PROVENANCE_FIELDS:
        value = _safe_str(record.get(field))
        if value is not None:
            return value
    return None


def _framework_mapping_provenance(record: Mapping[str, Any]) -> str | None:
    """Return established provenance that can identify a framework concordance."""
    return _canonical_provenance(record) or _certification_provenance(record)


def _is_certifying_evidence(record: Any) -> bool:
    """Accept only grounded evidence from a recognized official credential source."""
    if not isinstance(record, Mapping):
        return False
    credential_ref = (
        _safe_str(record.get("certificate_id"))
        or _safe_str(record.get("credential_id"))
        or _safe_str(record.get("official_result_id"))
    )
    return (
        _safe_str(record.get("source_kind")) in _CERTIFIED_SOURCE_KINDS
        and credential_ref is not None
        and _certification_provenance(record) is not None
    )


def _finite_semantic_number(
    value: Any,
    *,
    minimum: float | None = None,
    maximum: float | None = None,
) -> float | None:
    """Validate and normalize decision-driving numeric inputs.

    Rejects bool, NaN, +Inf, -Inf, non-numeric scalars, and out-of-bounds values.
    """
    if value is None or isinstance(value, bool):
        return None
    if not isinstance(value, (int, float)):
        return None
    try:
        val_float = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(val_float):
        return None
    if minimum is not None and val_float < minimum:
        return None
    if maximum is not None and val_float > maximum:
        return None
    return val_float


def _is_grounded_proficiency_evidence(record: Mapping[str, Any]) -> bool:
    """Return whether a record can ground an observed proficiency level or score."""
    if _canonical_provenance(record) is None:
        return False
    if "skill" in record and _safe_str(record.get("skill")) is None:
        return False
    if _safe_str(record.get("observed")) or _safe_str(record.get("observed_performance")):
        return True
    score = _finite_semantic_number(record.get("score"))
    return score is not None


def _has_explicit_pronunciation_result(record: Mapping[str, Any]) -> bool:
    """Return whether an assessment record contains a usable pronunciation outcome."""
    if len([
        field for field in ("pronunciation_result", "pronunciation_feedback", "finding")
        if _safe_str(record.get(field)) is not None
    ]) > 0:
        return True
    score = _finite_semantic_number(record.get("score"))
    return score is not None


def _is_grounded_pronunciation_assessment(record: Mapping[str, Any]) -> bool:
    """Accept only provenance-grounded, explicit pronunciation assessment evidence."""
    if (
        _safe_str(record.get("skill")) != "pronunciation"
        or record.get("pronunciation_assessed") is False
        or _canonical_provenance(record) is None
    ):
        return False

    source_kind = _safe_str(record.get("source_kind"))
    if source_kind not in _PRONUNCIATION_ASSESSMENT_SOURCE_KINDS | {"audio_sample"}:
        return False
    return _has_explicit_pronunciation_result(record)


def _clean_proficiency_value(value: Any) -> str | float | None:
    """Normalize a direct claimed level or finite numeric score without mapping it."""
    text_value = _safe_str(value)
    if text_value is not None:
        return text_value
    num = _finite_semantic_number(value)
    if num is not None:
        return num
    return None


def _semantic_evidence_key(record: Mapping[str, Any]) -> tuple[Any, ...]:
    """Identify semantic evidence without treating caller-controlled IDs as provenance."""
    return (
        _canonical_provenance(record) or "unprovenanced",
        _safe_str(record.get("source_kind")) or _safe_str(record.get("source")),
        _safe_str(record.get("framework")),
        _safe_str(record.get("skill")),
        _safe_str(record.get("observed")) or _safe_str(record.get("observed_performance")),
        _canonical_json_value(record.get("score")),
        _safe_str(record.get("error_type")),
        _safe_str(record.get("sentence")),
        _safe_str(record.get("comparison_key")),
    )


def _deduplicate_evidence(evidence: Any) -> list[dict[str, Any]]:
    """Deduplicate evidence by grounded occurrence and semantic content."""
    if not isinstance(evidence, (list, tuple, set, frozenset)):
        return []
    seen: set[tuple[Any, ...]] = set()
    deduped: list[dict[str, Any]] = []
    for item in evidence:
        if not isinstance(item, Mapping):
            continue
        key = _semantic_evidence_key(item)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(dict(normalize_json_value(item)))
    return deduped


def _proficiency_evidence_supports_claim(
    record: Mapping[str, Any],
    *,
    requested_framework: str | None = None,
    requested_skill: str | None = None,
    requested_value: Any | None = None,
    require_comparable: bool = False,
) -> bool:
    """Consolidated epistemic predicate binding framework, skill, value, provenance, and comparability."""
    if not isinstance(record, Mapping):
        return False

    if _canonical_provenance(record) is None:
        return False

    if require_comparable:
        if record.get("comparable") is not True:
            return False
        if _safe_str(record.get("comparison_key")) is None:
            return False

    ev_fw = _safe_str(record.get("framework"))
    if requested_framework is not None:
        req_fw = requested_framework.strip().upper()
        if ev_fw is not None and ev_fw.upper() != req_fw:
            return False

    if requested_skill is not None:
        clean_req_skill = _safe_str(requested_skill)
        if clean_req_skill is not None:
            norm_skill = clean_req_skill.casefold()
            if norm_skill in CANONICAL_SKILL_DIMENSIONS:
                ev_skill = _safe_str(record.get("skill"))
                if ev_skill is None or ev_skill.casefold() != norm_skill:
                    return False
    elif "skill" in record and _safe_str(record.get("skill")) is None:
        return False

    if requested_value is not None:
        observed_value = _safe_str(record.get("observed")) or _safe_str(record.get("observed_performance"))
        if observed_value is not None:
            if isinstance(requested_value, str):
                return observed_value.casefold() == requested_value.casefold()
            return False

        score = _finite_semantic_number(record.get("score"))
        req_num = _finite_semantic_number(requested_value)
        if score is not None and req_num is not None:
            return score == req_num
        return False

    observed_value = _safe_str(record.get("observed")) or _safe_str(record.get("observed_performance"))
    if observed_value is not None:
        return True
    score = _finite_semantic_number(record.get("score"))
    return score is not None


def classify_proficiency_record(
    *,
    kind: str | None = None,
    framework: str | None = None,
    level_or_score: str | float | None = None,
    skill_scope: str | None = None,
    evidence: tuple[Any, ...] | list[Any] = (),
    confidence: float | None = None,
) -> dict[str, Any]:
    """Classify a proficiency record preserving CERTIFIED vs ESTIMATED vs OBSERVED_PERFORMANCE."""
    deduped_ev = _deduplicate_evidence(evidence)
    requested_kind = _safe_str(kind) or "OBSERVED_PERFORMANCE"
    if requested_kind not in CANONICAL_PROFICIENCY_KINDS:
        requested_kind = "OBSERVED_PERFORMANCE"
    clean_framework = _safe_str(framework)
    clean_skill_scope = _safe_str(skill_scope) or "general"
    clean_level_or_score = _clean_proficiency_value(level_or_score)

    # CERTIFIED requires recognized, grounded official credential evidence.
    certification_evidence_valid = len([e for e in deduped_ev if _is_certifying_evidence(e)]) > 0
    is_certified = requested_kind == "CERTIFIED" and certification_evidence_valid
    if is_certified:
        clean_kind = "CERTIFIED"
    else:
        grounded_ev = [
            item
            for item in deduped_ev
            if _proficiency_evidence_supports_claim(
                item,
                requested_framework=clean_framework,
                requested_skill=clean_skill_scope,
                requested_value=clean_level_or_score,
                require_comparable=False,
            )
        ]
        grounded_provenance = {_canonical_provenance(item) for item in grounded_ev}
        has_observed_evidence = bool(grounded_ev)
        has_independent_evidence = len(grounded_provenance) >= 2

        if requested_kind == "ESTIMATED" and has_independent_evidence:
            clean_kind = "ESTIMATED"
        else:
            # An invalid certificate does not invent an estimate; any separately
            # grounded task/session evidence remains only observed performance.
            clean_kind = "OBSERVED_PERFORMANCE"

    evidence_supports_level = (
        is_certified
        or (requested_kind == "ESTIMATED" and has_independent_evidence)
        or (requested_kind == "OBSERVED_PERFORMANCE" and has_observed_evidence)
    )

    default_confidence = (
        0.95
        if clean_kind == "CERTIFIED"
        else (0.75 if clean_kind == "ESTIMATED" else 0.5)
    )
    clean_confidence = 0.0
    if evidence_supports_level:
        clean_confidence = (
            float(confidence)
            if isinstance(confidence, (int, float))
            and not isinstance(confidence, bool)
            and math.isfinite(float(confidence))
            and 0.0 <= float(confidence) <= 1.0
            else default_confidence
        )

    return {
        "kind": clean_kind,
        "framework": _safe_str(framework) or "CEFR",
        "level_or_score": clean_level_or_score if evidence_supports_level and clean_level_or_score is not None else "unassessed",
        "skill_scope": clean_skill_scope,
        "evidence": deduped_ev,
        "is_certified": clean_kind == "CERTIFIED",
        "certification_evidence_valid": certification_evidence_valid,
        "confidence": clean_confidence,
    }


def evaluate_level_update(
    *,
    existing: Mapping[str, Any] | None = None,
    evidence: tuple[Any, ...] | list[Any] = (),
    target_skill: str | None = None,
) -> dict[str, Any]:
    """Evaluate a proposed level update from new evidence without overwriting certified records."""
    existing_dict = dict(existing) if isinstance(existing, Mapping) else {}
    existing_kind = existing_dict.get("kind")
    existing_level = existing_dict.get("level_or_score")
    existing_framework = _safe_str(existing_dict.get("framework")) or "CEFR"

    if existing_kind == "CERTIFIED":
        return {
            "stable_update_supported": False,
            "reason": "certified_record_cannot_be_overwritten",
            "proposed_level": existing_level,
            "updated_record": existing_dict,
        }

    deduped_ev = _deduplicate_evidence(evidence)
    comparable = [
        item
        for item in deduped_ev
        if _proficiency_evidence_supports_claim(
            item,
            requested_framework=existing_framework,
            requested_skill=target_skill or existing_dict.get("skill_scope"),
            requested_value=None,
            require_comparable=True,
        )
    ]
    comparison_keys = {_safe_str(item.get("comparison_key")) for item in comparable}
    provenance_units = {_canonical_provenance(item) for item in comparable}
    if len(comparable) < 2 or len(provenance_units) < 2 or len(comparison_keys) != 1:
        return {
            "stable_update_supported": False,
            "reason": "insufficient_comparable_evidence",
            "proposed_level": existing_level,
            "updated_record": existing_dict,
        }

    observed_levels = [
        _safe_str(e.get("observed")) or _safe_str(e.get("observed_performance"))
        for e in comparable
        if (_safe_str(e.get("observed")) or _safe_str(e.get("observed_performance"))) is not None
    ]
    if len(observed_levels) >= 2 and len(set(observed_levels)) == 1:
        new_level = observed_levels[0]
        return {
            "stable_update_supported": True,
            "reason": "consistent_comparable_evidence",
            "proposed_level": new_level,
            "updated_record": {
                "kind": "ESTIMATED",
                "framework": existing_framework,
                "skill_scope": target_skill or existing_dict.get("skill_scope", "general"),
                "level_or_score": new_level,
                "evidence": comparable,
            },
        }

    return {
        "stable_update_supported": False,
        "reason": "insufficient_comparable_evidence",
        "proposed_level": existing_level,
        "updated_record": existing_dict,
    }


def separate_skill_evidence(*, evidence: tuple[Any, ...] | list[Any] = ()) -> dict[str, Any]:
    """Strictly partition evidence across canonical skill dimensions."""
    deduped_ev = _deduplicate_evidence(evidence)

    pron_items = [
        e for e in deduped_ev
        if e.get("skill") == "pronunciation" and _is_grounded_pronunciation_assessment(e)
    ]
    has_pronunciation_specific_evidence = len(pron_items) > 0

    by_skill = {
        skill: {
            "status": "evidenced" if (pron_items if skill == "pronunciation" else [e for e in deduped_ev if e.get("skill") == skill]) else "insufficient_evidence",
            "evidence_count": len(pron_items if skill == "pronunciation" else [e for e in deduped_ev if e.get("skill") == skill]),
            "evidence": pron_items if skill == "pronunciation" else [e for e in deduped_ev if e.get("skill") == skill],
        }
        for skill in CANONICAL_SKILL_DIMENSIONS
    }

    return {
        "by_skill": by_skill,
        "pronunciation_assessed": has_pronunciation_specific_evidence,
        "total_evidence_count": len(deduped_ev),
    }


def classify_language_variety(
    *,
    preferred_variety: str | None = None,
    observed_variety: str | None = None,
    assessment_standard: str | None = None,
    form_status: str | None = None,
) -> dict[str, Any]:
    """Classify language variety and distinguish valid alternatives from errors."""
    clean_pref = (_safe_str(preferred_variety) or "").lower()
    clean_obs = (_safe_str(observed_variety) or "").lower()
    clean_status = (_safe_str(form_status) or "").lower()

    if clean_status == "incorrect":
        return {
            "classification": "incorrect",
            "error": True,
            "is_valid_alternative": False,
            "variety": clean_obs or "unknown",
        }

    if not clean_obs or not clean_pref:
        return {
            "classification": "uncertain",
            "error": False,
            "is_valid_alternative": False,
            "variety": clean_obs or "unknown",
        }

    preferred_family = next(
        (varieties for varieties in KNOWN_VARIETIES.values() if clean_pref in varieties),
        None,
    )
    observed_family = next(
        (varieties for varieties in KNOWN_VARIETIES.values() if clean_obs in varieties),
        None,
    )

    if clean_obs == clean_pref and preferred_family is not None:
        return {
            "classification": "preferred",
            "error": False,
            "is_valid_alternative": False,
            "variety": clean_obs,
        }

    if (
        preferred_family is not None
        and preferred_family == observed_family
        and clean_status != "incorrect"
    ):
        return {
            "classification": "valid_alternative",
            "error": False,
            "error_rejected": True,
            "variety_mismatch": True,
            "is_valid_alternative": True,
            "variety": clean_obs,
        }

    return {
        "classification": "uncertain",
        "error": False,
        "error_rejected": False,
        "variety_mismatch": clean_obs != clean_pref,
        "is_valid_alternative": False,
        "variety": clean_obs,
    }


def evaluate_framework_mapping(
    *,
    source_framework: str | None = None,
    source_value: str | None = None,
    target_framework: str | None = None,
    mapping_evidence: tuple[Any, ...] | list[Any] = (),
) -> dict[str, Any]:
    """Evaluate framework concordance mapping without assuming identity."""
    known_fw = {"CEFR", "ACTFL", "IELTS", "TOEFL", "CAMBRIDGE", "DELE", "DALF"}
    s_fw = (_safe_str(source_framework) or "").upper()
    t_fw = (_safe_str(target_framework) or "").upper()
    s_val = _safe_str(source_value)

    if s_fw not in known_fw or t_fw not in known_fw:
        return {
            "mapping_status": "unsupported_framework",
            "target_estimate_range": None,
            "is_exact": False,
            "approximate": False,
            "calibrated": False,
            "reason": "unsupported_framework_mapping",
        }

    if s_val is None:
        return {
            "mapping_status": "insufficient_evidence",
            "target_estimate_range": None,
            "is_exact": False,
            "approximate": False,
            "calibrated": False,
            "reason": "missing_or_malformed_source_value",
            "evidence": [],
        }

    if s_fw == t_fw and s_fw:
        return {
            "mapping_status": "same_framework",
            "target_estimate_range": s_val,
            "is_exact": True,
            "approximate": False,
            "calibrated": True,
        }

    mapping_list = list(mapping_evidence) if isinstance(mapping_evidence, (list, tuple, set, frozenset)) else []

    def _is_applicable_mapping(norm: dict[str, Any]) -> bool:
        if _framework_mapping_provenance(norm) is None:
            return False
        if _safe_str(norm.get("target_range")) is None:
            return False
        rec_src_fw = _safe_str(norm.get("source_framework"))
        if rec_src_fw is None or rec_src_fw.upper() != s_fw:
            return False
        rec_tgt_fw = _safe_str(norm.get("target_framework"))
        if rec_tgt_fw is None or rec_tgt_fw.upper() != t_fw:
            return False
        rec_src_val = _clean_proficiency_value(norm.get("source_value"))
        if rec_src_val is None:
            return False
        clean_s_val = _clean_proficiency_value(s_val)
        if clean_s_val is None:
            return False
        if isinstance(clean_s_val, float) and isinstance(rec_src_val, float):
            return clean_s_val == rec_src_val
        return str(clean_s_val).strip().casefold() == str(rec_src_val).strip().casefold()

    valid_recs = [
        norm
        for evidence in mapping_list
        if isinstance(evidence, Mapping)
        for norm in [dict(normalize_json_value(evidence))]
        if _is_applicable_mapping(norm)
    ]
    prov_to_ranges = {
        _framework_mapping_provenance(r): {_safe_str(x.get("target_range")) for x in valid_recs if _framework_mapping_provenance(x) == _framework_mapping_provenance(r)}
        for r in valid_recs
    }
    has_same_prov_conflict = len([ranges for ranges in prov_to_ranges.values() if len(ranges) > 1]) > 0
    all_ranges = {_safe_str(r.get("target_range")) for r in valid_recs}
    has_conflict = has_same_prov_conflict or len(all_ranges) > 1

    sorted_valid = sorted(valid_recs, key=_canonical_json_value, reverse=True)
    deduped_by_prov = {_framework_mapping_provenance(r): r for r in sorted_valid}
    qualified_evidence = sorted(
        deduped_by_prov.values(),
        key=_canonical_json_value,
    )
    if qualified_evidence and not has_conflict:
        target_range = _safe_str(qualified_evidence[0].get("target_range"))
        return {
            "mapping_status": "grounded_approximate_mapping",
            "target_estimate_range": target_range,
            "is_exact": False,
            "approximate": True,
            "calibrated": True,
            "evidence": qualified_evidence,
        }

    if has_conflict:
        return {
            "mapping_status": "insufficient_evidence",
            "target_estimate_range": None,
            "is_exact": False,
            "approximate": True,
            "calibrated": False,
            "reason": "conflicting_mapping_evidence",
            "evidence": qualified_evidence,
        }

    return {
        "mapping_status": "identity_forbidden",
        "target_estimate_range": None,
        "is_exact": False,
        "approximate": True,
        "calibrated": False,
        "reason": "cross_framework_identity_forbidden",
        "evidence": [],
    }


def _definition(
    rule_id: str,
    name: str,
    category: str,
    priority: int,
    risk_level: ReasoningRiskLevel = ReasoningRiskLevel.LOW,
) -> DomainReasoningRuleDefinition:
    return DomainReasoningRuleDefinition(
        id=rule_id,
        name=name,
        version="1.0.0",
        scope=ReasoningRuleScope.DOMAIN,
        domain_id="domain:languages",
        category=category,
        status=ReasoningRuleStatus.ENABLED,
        priority=priority,
        risk_level=risk_level,
        deterministic=True,
        description=f"Language pedagogy rule for {rule_id}.",
        metadata={"phase": "10.26"},
    )


def _mapping(metadata: Mapping[str, Any], key: str) -> Mapping[str, Any] | None:
    value = metadata.get(key)
    return value if isinstance(value, Mapping) else None


def _result(
    definition: ReasoningRuleDefinition,
    context: ReasoningRuleContext,
    status: ReasoningRuleResultStatus,
    *,
    findings: tuple[ReasoningFinding, ...] = (),
    gaps: tuple[ReasoningGap, ...] = (),
    escalation: ReasoningEscalation | None = None,
    code: str,
    message: str,
) -> ReasoningRuleResult:
    return DomainRuleResult(
        rule_id=definition.id,
        rule_name=definition.name,
        rule_version=definition.version,
        domain_id=definition.domain_id,
        status=status,
        findings=findings,
        gaps=gaps,
        escalation=escalation,
        trace_entries=(
            ReasoningRuleTraceEntry(
                code=code,
                message=message,
                rule_id=definition.id,
                domain_id=definition.domain_id,
                status=status,
                occurred_at=context.timestamp,
                output_count=len(findings) + len(gaps) + int(escalation is not None),
            ),
        ),
        started_at=context.timestamp,
        completed_at=context.timestamp,
    )


@dataclass(frozen=True, slots=True)
class LanguageLevelEvidenceRule:
    definition: DomainReasoningRuleDefinition

    def evaluate(self, context: ReasoningRuleContext) -> ReasoningRuleResult:
        mat = _mapping(context.metadata, "material") or {}
        rec = classify_proficiency_record(
            kind=mat.get("kind"),
            framework=mat.get("framework"),
            level_or_score=mat.get("level_or_score"),
            skill_scope=mat.get("skill_scope"),
            evidence=mat.get("evidence", ()),
        )
        finding = ReasoningFinding(
            code="LEVEL_EVIDENCE_EVALUATED",
            message=f"Proficiency classified as {rec['kind']}.",
            severity=ReasoningSeverity.INFO,
            rule_id=self.definition.id,
            domain_id=self.definition.domain_id,
            metadata=rec,
        )
        return _result(
            self.definition,
            context,
            ReasoningRuleResultStatus.APPLIED,
            findings=(finding,),
            code="LANGUAGE_LEVEL_EVIDENCE_APPLIED",
            message="Language level evidence evaluated.",
        )


@dataclass(frozen=True, slots=True)
class SkillSeparationRule:
    definition: DomainReasoningRuleDefinition

    def evaluate(self, context: ReasoningRuleContext) -> ReasoningRuleResult:
        mat = _mapping(context.metadata, "material") or {}
        sep = separate_skill_evidence(evidence=mat.get("evidence", ()))
        finding = ReasoningFinding(
            code="SKILL_SEPARATION_EVALUATED",
            message="Skill evidence separated across canonical dimensions.",
            severity=ReasoningSeverity.INFO,
            rule_id=self.definition.id,
            domain_id=self.definition.domain_id,
            metadata=sep,
        )
        return _result(
            self.definition,
            context,
            ReasoningRuleResultStatus.APPLIED,
            findings=(finding,),
            code="SKILL_SEPARATION_APPLIED",
            message="Skill separation evaluated.",
        )


@dataclass(frozen=True, slots=True)
class LanguageVarietyValidityRule:
    definition: DomainReasoningRuleDefinition

    def evaluate(self, context: ReasoningRuleContext) -> ReasoningRuleResult:
        mat = _mapping(context.metadata, "material") or {}
        var = classify_language_variety(
            preferred_variety=mat.get("preferred_variety"),
            observed_variety=mat.get("observed_variety"),
            assessment_standard=mat.get("assessment_standard"),
            form_status=mat.get("form_status"),
        )
        finding = ReasoningFinding(
            code="VARIETY_VALIDITY_EVALUATED",
            message=f"Variety classified as {var['classification']}.",
            severity=ReasoningSeverity.INFO,
            rule_id=self.definition.id,
            domain_id=self.definition.domain_id,
            metadata=var,
        )
        return _result(
            self.definition,
            context,
            ReasoningRuleResultStatus.APPLIED,
            findings=(finding,),
            code="VARIETY_VALIDITY_APPLIED",
            message="Variety validity evaluated.",
        )


@dataclass(frozen=True, slots=True)
class ProficiencyFrameworkRule:
    definition: DomainReasoningRuleDefinition

    def evaluate(self, context: ReasoningRuleContext) -> ReasoningRuleResult:
        mat = _mapping(context.metadata, "material") or {}
        map_res = evaluate_framework_mapping(
            source_framework=mat.get("source_framework"),
            source_value=mat.get("source_value"),
            target_framework=mat.get("target_framework"),
            mapping_evidence=mat.get("mapping_evidence", ()),
        )
        finding = ReasoningFinding(
            code="FRAMEWORK_MAPPING_EVALUATED",
            message=f"Framework mapping evaluated: {map_res['mapping_status']}.",
            severity=ReasoningSeverity.INFO,
            rule_id=self.definition.id,
            domain_id=self.definition.domain_id,
            metadata=map_res,
        )
        return _result(
            self.definition,
            context,
            ReasoningRuleResultStatus.APPLIED,
            findings=(finding,),
            code="FRAMEWORK_MAPPING_APPLIED",
            message="Framework mapping evaluated.",
        )


# ── Task 4 Helpers & Rule Classes ────────────────────────────────────────────

def evaluate_error_pattern(
    *,
    observations: tuple[Any, ...] | list[Any] = (),
    minimum_independent_occurrences: int = 2,
) -> dict[str, Any]:
    """Evaluate error pattern evidence across independent comparable observations."""
    if (
        isinstance(minimum_independent_occurrences, bool)
        or not isinstance(minimum_independent_occurrences, (int, float))
        or math.isnan(minimum_independent_occurrences)
        or math.isinf(minimum_independent_occurrences)
    ):
        min_occurrences = 2
    else:
        min_occurrences = int(minimum_independent_occurrences) if int(minimum_independent_occurrences) >= 2 else 2  # noqa: FURB136

    if not isinstance(observations, (list, tuple, set, frozenset)):
        observations = ()

    valid_observations: list[dict[str, Any]] = []
    for obs in observations:
        if not isinstance(obs, Mapping):
            continue
        if obs.get("is_valid_alternative") is True:
            continue
        valid_observations.append(dict(normalize_json_value(obs)))

    # Caller-controlled IDs are display references, never occurrence provenance.
    seen: set[tuple[Any, ...]] = set()
    distinct_occurrences: set[str] = set()
    comparable_occurrences: set[str] = set()
    comparison_keys: set[str] = set()
    error_types: set[str] = set()
    missing_error_type = False
    evidence_ids: list[str] = []
    has_resolved = False
    has_unresolved = False

    for obs in valid_observations:
        obs_id = _safe_str(obs.get("id")) or ""
        provenance = _canonical_provenance(obs)
        if provenance is None:
            continue
        sentence = _safe_str(obs.get("sentence")) or ""
        err_type = _safe_str(obs.get("error_type"))
        if err_type is None:
            missing_error_type = True
            err_type = "error"
        else:
            error_types.add(err_type)
        key = (provenance or "unprovenanced", sentence, err_type)
        if key in seen:
            continue
        seen.add(key)
        distinct_occurrences.add(provenance)
        comparison_key = _safe_str(obs.get("comparison_key"))
        if obs.get("comparable") is True and comparison_key is not None:
            comparable_occurrences.add(provenance)
            comparison_keys.add(comparison_key)
        if obs_id:
            evidence_ids.append(obs_id)
        if obs.get("resolved") is True:
            has_resolved = True
        else:
            has_unresolved = True

    indep_count = len(distinct_occurrences)
    comparable_count = (
        len(comparable_occurrences)
        if len(comparison_keys) == 1
        and len(error_types) == 1
        and not missing_error_type
        else 0
    )
    lapse_possible = has_resolved and has_unresolved

    if comparable_count < min_occurrences:
        pattern_state = "insufficient_evidence"
        eligible = False
    elif has_resolved and not has_unresolved:
        pattern_state = "resolved"
        eligible = False
    elif lapse_possible:
        pattern_state = "improving"
        eligible = True
    elif indep_count == min_occurrences:
        pattern_state = "candidate"
        eligible = True
    else:
        pattern_state = "evidenced"
        eligible = True

    return {
        "pattern_state": pattern_state,
        "eligible": eligible,
        "independent_occurrences": indep_count,
        "comparable_contexts": comparable_count,
        "lapse_possible": lapse_possible,
        "evidence_ids": sorted(evidence_ids),
    }


def prioritize_corrections(
    *,
    errors: tuple[Any, ...] | list[Any] = (),
    mode: str = "practice",
    active_goals: tuple[Any, ...] | list[Any] = (),
    certification_relevance: tuple[Any, ...] | list[Any] = (),
) -> dict[str, Any]:
    """Prioritize language corrections based on communicative usefulness and mode."""
    clean_mode = (_safe_str(mode) or "practice").lower()

    if not isinstance(errors, (list, tuple, set, frozenset)):
        raw_errors_list: list[Any] = []
    else:
        raw_errors_list = list(errors)

    if not isinstance(active_goals, (list, tuple, set, frozenset)):
        active_goals_list: list[Any] = []
    else:
        active_goals_list = list(active_goals)

    if not isinstance(certification_relevance, (list, tuple, set, frozenset)):
        certification_relevance_list: list[Any] = []
    else:
        certification_relevance_list = list(certification_relevance)

    raw_errors = [dict(normalize_json_value(e)) for e in raw_errors_list if isinstance(e, Mapping)]

    goal_set = {_safe_str(g) for g in active_goals_list if _safe_str(g)}
    cert_set = {_safe_str(c) for c in certification_relevance_list if _safe_str(c)}

    def _score(err: dict[str, Any]) -> int:
        cat = _safe_str(err.get("category")) or ""
        blocking = err.get("blocking") is True or cat == "comprehension_blocking"
        if blocking:
            return 100
        if cat == "recurrent":
            return 80
        err_id = _safe_str(err.get("id")) or ""
        err_type = _safe_str(err.get("error_type")) or ""
        if err_id in goal_set or err_type in goal_set:
            return 60
        if err_id in cert_set or err_type in cert_set:
            return 40
        if cat in ("naturalness", "register", "naturalness_register"):
            return 20
        return 10  # minor_style

    sorted_errors = sorted(raw_errors, key=lambda err: (-_score(err), _canonical_json_value(err)))

    defer_feedback = clean_mode == "assess"
    selective_density = clean_mode == "practice"

    immediate_errors = []
    deferred_errors = []
    for err in sorted_errors:
        score = _score(err)
        if clean_mode == "assess" or (clean_mode == "practice" and score <= 10 and len([e for e in sorted_errors if _score(e) > 10]) > 0):
            deferred_errors.append(err)
        else:
            immediate_errors.append(err)

    return {
        "prioritized_errors": sorted_errors,
        "immediate_errors": immediate_errors,
        "deferred_errors": deferred_errors,
        "mode": clean_mode,
        "defer_feedback": defer_feedback,
        "selective_density": selective_density,
        "immediate_correction_count": len(immediate_errors),
    }


def adapt_difficulty(
    *,
    current_difficulty: float,
    performance: tuple[Any, ...] | list[Any] = (),
    stable_proficiency: str | None = None,
) -> dict[str, Any]:
    """Adapt exercise difficulty based on accumulated comparable performance."""
    if (
        isinstance(current_difficulty, bool)
        or not isinstance(current_difficulty, (int, float))
        or math.isnan(current_difficulty)
        or math.isinf(current_difficulty)
        or current_difficulty < 1
    ):
        return {
            "action": "insufficient_evidence",
            "current_difficulty": 1,
            "target_difficulty": 1,
            "stable_proficiency_changed": False,
            "reason": "invalid_current_difficulty",
        }

    cur_diff = int(current_difficulty)

    if not isinstance(performance, (list, tuple, set, frozenset)):
        perf_list: list[Any] = []
    else:
        perf_list = list(performance)

    valid_perf = [
        (provenance, float(p.get("score")), comp_key, norm)
        for p in perf_list
        if isinstance(p, Mapping) and p.get("comparable") is True
        for comp_key in [_safe_str(p.get("comparison_key"))]
        if comp_key is not None
        for provenance in [_canonical_provenance(p)]
        if provenance is not None
        for score in [p.get("score")]
        if not isinstance(score, bool) and isinstance(score, (int, float)) and not math.isnan(score) and not math.isinf(score) and 0.0 <= float(score) <= 1.0
        for norm in [dict(normalize_json_value(p))]
    ]
    comparison_keys = {comp_key for _, _, comp_key, _ in valid_perf}
    if len(comparison_keys) != 1 or not valid_perf:
        return {
            "action": "insufficient_evidence",
            "current_difficulty": cur_diff,
            "target_difficulty": cur_diff,
            "stable_proficiency_changed": False,
            "reason": "no_comparable_performance",
        }

    sorted_perf = sorted(valid_perf, key=lambda item: _canonical_json_value(item[3]), reverse=True)
    deduped_by_prov = {prov: (score, norm) for prov, score, _, norm in sorted_perf}
    qualified_records = sorted(deduped_by_prov.values(), key=lambda item: _canonical_json_value(item[1]))
    scores = [score for score, _ in qualified_records]
    avg_score = sum(scores) / len(scores)

    if len(qualified_records) < 2:
        action = "scaffold_reduce" if avg_score < 0.40 else "maintain_and_advance"
        target_diff = (cur_diff - 1) if cur_diff > 1 else 1
        return {
            "action": action,
            "current_difficulty": cur_diff,
            "target_difficulty": target_diff if avg_score < 0.40 else cur_diff,
            "stable_proficiency_changed": False,
            "reason": "single_session_scaffold_only",
        }

    if avg_score >= 0.85:
        return {
            "action": "increase",
            "current_difficulty": cur_diff,
            "target_difficulty": cur_diff + 1,
            "stable_proficiency_changed": False,
            "reason": "consistent_high_mastery",
        }
    elif avg_score <= 0.50:
        return {
            "action": "scaffold_reduce",
            "current_difficulty": cur_diff,
            "target_difficulty": (cur_diff - 1) if cur_diff > 1 else 1,
            "stable_proficiency_changed": False,
            "reason": "consistent_high_difficulty",
        }
    else:
        return {
            "action": "maintain_and_advance",
            "current_difficulty": cur_diff,
            "target_difficulty": cur_diff,
            "stable_proficiency_changed": False,
            "reason": "adequate_consolidation",
        }


@dataclass(frozen=True, slots=True)
class ErrorPatternEvidenceRule:
    definition: DomainReasoningRuleDefinition

    def evaluate(self, context: ReasoningRuleContext) -> ReasoningRuleResult:
        mat = _mapping(context.metadata, "material") or {}
        res = evaluate_error_pattern(
            observations=mat.get("observations", ()),
            minimum_independent_occurrences=mat.get("minimum_independent_occurrences", 2),
        )
        finding = ReasoningFinding(
            code="ERROR_PATTERN_EVALUATED",
            message=f"Error pattern state: {res['pattern_state']}.",
            severity=ReasoningSeverity.INFO,
            rule_id=self.definition.id,
            domain_id=self.definition.domain_id,
            metadata=res,
        )
        return _result(
            self.definition,
            context,
            ReasoningRuleResultStatus.APPLIED,
            findings=(finding,),
            code="ERROR_PATTERN_EVIDENCE_APPLIED",
            message="Error pattern evidence evaluated.",
        )


@dataclass(frozen=True, slots=True)
class CorrectionPriorityRule:
    definition: DomainReasoningRuleDefinition

    def evaluate(self, context: ReasoningRuleContext) -> ReasoningRuleResult:
        mat = _mapping(context.metadata, "material") or {}
        res = prioritize_corrections(
            errors=mat.get("errors", ()),
            mode=mat.get("mode", "practice"),
            active_goals=mat.get("active_goals", ()),
            certification_relevance=mat.get("certification_relevance", ()),
        )
        finding = ReasoningFinding(
            code="CORRECTION_PRIORITY_EVALUATED",
            message=f"Prioritized {len(res['prioritized_errors'])} errors for mode {res['mode']}.",
            severity=ReasoningSeverity.INFO,
            rule_id=self.definition.id,
            domain_id=self.definition.domain_id,
            metadata=res,
        )
        return _result(
            self.definition,
            context,
            ReasoningRuleResultStatus.APPLIED,
            findings=(finding,),
            code="CORRECTION_PRIORITY_APPLIED",
            message="Correction priority evaluated.",
        )


@dataclass(frozen=True, slots=True)
class AdaptiveDifficultyRule:
    definition: DomainReasoningRuleDefinition

    def evaluate(self, context: ReasoningRuleContext) -> ReasoningRuleResult:
        mat = _mapping(context.metadata, "material") or {}
        res = adapt_difficulty(
            current_difficulty=mat.get("current_difficulty", 1),
            performance=mat.get("performance", ()),
            stable_proficiency=mat.get("stable_proficiency"),
        )
        finding = ReasoningFinding(
            code="ADAPTIVE_DIFFICULTY_EVALUATED",
            message=f"Difficulty action: {res['action']}.",
            severity=ReasoningSeverity.INFO,
            rule_id=self.definition.id,
            domain_id=self.definition.domain_id,
            metadata=res,
        )
        return _result(
            self.definition,
            context,
            ReasoningRuleResultStatus.APPLIED,
            findings=(finding,),
            code="ADAPTIVE_DIFFICULTY_APPLIED",
            message="Adaptive difficulty evaluated.",
        )


# ── Task 5 Helpers & Rule Classes ────────────────────────────────────────────

def plan_spaced_review(
    *,
    items: tuple[Any, ...] | list[Any] = (),
    active_goals: tuple[Any, ...] | list[Any] = (),
) -> dict[str, Any]:
    """Plan spaced review items based on mastery, due status, recall, importance, and active patterns."""
    if not isinstance(items, (list, tuple, set, frozenset)):
        items_list: list[Any] = []
    else:
        items_list = list(items)

    if not isinstance(active_goals, (list, tuple, set, frozenset)):
        active_goals_list: list[Any] = []
    else:
        active_goals_list = list(active_goals)

    goal_set = {_safe_str(g) for g in active_goals_list if _safe_str(g)}

    valid_items = [
        norm
        for raw in items_list
        if isinstance(raw, Mapping)
        for norm in [dict(normalize_json_value(raw))]
    ]
    sorted_raw = sorted(valid_items, key=_canonical_json_value, reverse=True)
    deduped_by_id = {
        item_id: item
        for item in sorted_raw
        for item_id in [_safe_str(item.get("id")) or _safe_str(item.get("term")) or _safe_str(item.get("item_id"))]
        if item_id is not None
    }
    anon_items = [
        item
        for item in sorted_raw
        if (_safe_str(item.get("id")) or _safe_str(item.get("term")) or _safe_str(item.get("item_id"))) is None
    ]
    unique_items = list(deduped_by_id.values()) + anon_items

    def _review_priority(item: dict[str, Any]) -> float:
        score = 0.0
        if item.get("due") is True:
            score += 50.0
        if item.get("active_pattern") is True:
            score += 30.0
        item_id = _safe_str(item.get("id")) or ""
        item_term = _safe_str(item.get("term")) or ""
        if item_id in goal_set or item_term in goal_set or item.get("goal_relevant") is True:
            score += 20.0

        # Mastery: lower mastery -> higher priority (bounded [0.0, 1.0], default 0.5)
        raw_mastery = item.get("mastery")
        if isinstance(raw_mastery, bool) or not isinstance(raw_mastery, (int, float)) or math.isnan(raw_mastery) or math.isinf(raw_mastery):
            mastery = 0.5
        else:
            m_val = float(raw_mastery)
            mastery = 1.0 if m_val > 1.0 else (0.0 if m_val < 0.0 else m_val)  # noqa: FURB136
        score += (1.0 - mastery) * 20.0

        # Recall: lower recall -> higher priority (bounded [0.0, 1.0], default 0.5)
        raw_recall = item.get("recall") if "recall" in item else item.get("retrieval_strength")
        if raw_recall is not None:
            if isinstance(raw_recall, bool) or not isinstance(raw_recall, (int, float)) or math.isnan(raw_recall) or math.isinf(raw_recall):
                recall = 0.5
            else:
                r_val = float(raw_recall)
                recall = 1.0 if r_val > 1.0 else (0.0 if r_val < 0.0 else r_val)  # noqa: FURB136
            score += (1.0 - recall) * 15.0

        # Importance: higher importance -> higher priority (bounded [0.0, 1.0], default 0.5)
        raw_importance = item.get("importance")
        if raw_importance is not None:
            if isinstance(raw_importance, bool) or not isinstance(raw_importance, (int, float)) or math.isnan(raw_importance) or math.isinf(raw_importance):
                importance = 0.5
            else:
                imp_val = float(raw_importance)
                importance = 1.0 if imp_val > 1.0 else (0.0 if imp_val < 0.0 else imp_val)  # noqa: FURB136
            score += importance * 15.0

        return score

    sorted_items = sorted(unique_items, key=lambda item: (-_review_priority(item), _canonical_json_value(item)))
    due_items = [i for i in sorted_items if i.get("due") is True or i.get("active_pattern") is True]

    return {
        "prioritized_items": sorted_items,
        "review_queue": sorted_items[:10],
        "due_items": due_items,
        "backlog_count": len(due_items),
    }


def evaluate_learning_load(
    *,
    available_time: float | None = None,
    energy: str | None = None,
    priorities: tuple[Any, ...] | list[Any] = (),
    deadlines: tuple[Any, ...] | list[Any] = (),
    recent_load: Any | None = None,
    review_backlog: tuple[Any, ...] | list[Any] = (),
) -> dict[str, Any]:
    """Evaluate learning load respecting energy, time, recent load, deadlines, and review backlog."""
    if not isinstance(priorities, (list, tuple, set, frozenset)):
        priorities_list: list[Any] = []
    else:
        priorities_list = list(priorities)

    if not isinstance(deadlines, (list, tuple, set, frozenset)):
        deadlines_list: list[Any] = []
    else:
        deadlines_list = list(deadlines)

    if not isinstance(review_backlog, (list, tuple, set, frozenset)):
        backlog_list: list[Any] = []
    else:
        backlog_list = list(review_backlog)

    if available_time is not None:
        if (
            isinstance(available_time, bool)
            or not isinstance(available_time, (int, float))
            or math.isnan(available_time)
            or math.isinf(available_time)
            or available_time < 0
        ):
            return {
                "recommended_duration_minutes": 0,
                "recommended_activities": ["micro_practice"],
                "load_status": "insufficient_constraints",
                "calendar_modified": False,
                "priorities_considered": len(priorities_list),
                "backlog_considered": len(backlog_list),
                "deadlines_considered": len(deadlines_list),
                "recent_load_considered": normalize_json_value(recent_load) if recent_load is not None else None,
            }
        clean_time = int(available_time)
    else:
        clean_time = 30

    clean_energy = (_safe_str(energy) or "moderate").lower()

    if clean_energy == "low":
        recommended_duration = min(clean_time, 15)
        load_status = "scaffolded_light"
        base_activities = ["micro_practice", "passive_input"]
    elif clean_energy == "high":
        recommended_duration = clean_time
        load_status = "optimal"
        base_activities = ["active_production", "concept_expansion"]
    else:
        recommended_duration = min(clean_time, 30)
        load_status = "standard"
        base_activities = ["guided_practice", "spaced_review"]

    # Recent load semantic adjustment: high recent load reduces burden/duration, never increases
    is_heavy_recent_load = False
    if isinstance(recent_load, Mapping):
        norm_load = dict(normalize_json_value(recent_load))
        hours = norm_load.get("hours")
        mins = norm_load.get("recent_minutes")
        status = _safe_str(norm_load.get("status"))
        is_heavy_recent_load = (
            (isinstance(hours, (int, float)) and not isinstance(hours, bool) and hours >= 4)
            or (isinstance(mins, (int, float)) and not isinstance(mins, bool) and mins >= 120)
            or (status in ("high", "heavy", "fatigued"))
            or norm_load.get("energy_depleted") is True
        )
    elif isinstance(recent_load, (int, float)) and not isinstance(recent_load, bool) and recent_load >= 4:
        is_heavy_recent_load = True

    if is_heavy_recent_load:
        recommended_duration = min(recommended_duration, 15)
        if load_status == "optimal":
            load_status = "standard"
        elif load_status == "standard":
            load_status = "scaffolded_light"

    # Assemble recommended activities based on deadlines, backlog, priorities, and base activities
    activities_order: list[str] = []

    # 1. Urgent deadlines prepend exam/prep activity
    has_urgent_deadline = len([
        d for d in deadlines_list
        if isinstance(d, Mapping)
        and (
            d.get("urgent") is True
            or _safe_str(d.get("priority")) == "urgent"
            or (isinstance(d.get("days_remaining"), (int, float)) and d.get("days_remaining") <= 3)
        )
    ]) > 0
    if has_urgent_deadline:
        activities_order.append("exam_practice")

    # 2. Review backlog prioritizes spaced review
    if len(backlog_list) > 0:
        activities_order.append("spaced_review")

    # 3. Explicit priorities
    for p in priorities_list:
        p_str = _safe_str(p)
        if p_str and p_str not in activities_order:
            activities_order.append(p_str)

    # 4. Base activities for current energy/load
    for act in base_activities:
        if act not in activities_order:
            activities_order.append(act)

    # Hard constraints: duration <= available_time and duration >= 0
    final_duration = min(recommended_duration, clean_time)
    final_duration = 0 if final_duration < 0 else final_duration  # noqa: FURB136

    return {
        "recommended_duration_minutes": final_duration,
        "recommended_activities": activities_order or ["micro_practice"],
        "load_status": load_status,
        "calendar_modified": False,
        "priorities_considered": len(priorities_list),
        "backlog_considered": len(backlog_list),
        "deadlines_considered": len(deadlines_list),
        "recent_load_considered": normalize_json_value(recent_load) if recent_load is not None else None,
    }


def align_activity_to_goals(
    *,
    activity: Any,
    goals: tuple[Any, ...] | list[Any] = (),
) -> dict[str, Any]:
    """Align activity to concurrent user goals without single-goal hegemony."""
    if not isinstance(goals, (list, tuple, set, frozenset)):
        goals_list: list[Any] = []
    else:
        goals_list = list(goals)

    raw_goals = [dict(normalize_json_value(g)) for g in goals_list if isinstance(g, Mapping)]
    coexisting_ids = sorted({gid for g in raw_goals if (gid := _safe_str(g.get("id"))) is not None})

    if not isinstance(activity, Mapping):
        if isinstance(activity, str) and activity.strip():
            activity_dict = {"type": activity.strip()}
        else:
            activity_dict = {}
    else:
        activity_dict = dict(normalize_json_value(activity))

    act_type = (_safe_str(activity_dict.get("type")) or _safe_str(activity_dict.get("activity_type")) or _safe_str(activity_dict.get("kind")) or "").lower()
    act_skill = (_safe_str(activity_dict.get("skill")) or _safe_str(activity_dict.get("target_skill")) or "").lower()
    act_purpose = (_safe_str(activity_dict.get("purpose")) or "").lower()
    act_topic = (_safe_str(activity_dict.get("topic")) or "").lower()
    act_target = (_safe_str(activity_dict.get("target")) or "").lower()

    raw_skills = activity_dict.get("skills") or ()
    if isinstance(raw_skills, (list, tuple, set, frozenset)):
        act_skills = {_safe_str(s).lower() for s in raw_skills if _safe_str(s)}
    elif isinstance(raw_skills, str):
        act_skills = {raw_skills.lower()}
    else:
        act_skills = set()
    if act_skill:
        act_skills.add(act_skill)

    raw_act_goals = activity_dict.get("goal_ids") or activity_dict.get("goal_id") or ()
    if isinstance(raw_act_goals, str):
        act_goal_ids = {raw_act_goals}
    elif isinstance(raw_act_goals, (list, tuple, set, frozenset)):
        act_goal_ids = {_safe_str(x) for x in raw_act_goals if _safe_str(x)}
    else:
        act_goal_ids = set()

    is_unrelated = (
        not act_type and not act_skills and not act_topic and not act_target and not act_goal_ids and not act_purpose
    ) or len([
        u for u in ("unrelated", "accounting", "tax_filing", "non_learning", "irrelevant")
        if u in act_type or u in act_purpose
    ]) > 0

    aligned_goal_ids: list[str] = []

    if not is_unrelated and raw_goals:
        for g in raw_goals:
            gid = _safe_str(g.get("id"))
            if gid is None:
                continue

            if gid in act_goal_ids:
                aligned_goal_ids.append(gid)
                continue

            g_kind = (_safe_str(g.get("kind")) or _safe_str(g.get("type")) or "").lower()
            g_skill = (_safe_str(g.get("skill")) or "").lower()
            g_target = (_safe_str(g.get("target")) or "").lower()

            matched = False

            if act_skills and len([s for s in act_skills if s == g_skill or s in g_kind or s in g_target]) > 0:
                matched = True

            if (act_type in ("roleplay", "conversation", "speaking_practice", "dialogue", "chat") or "conversation" in act_topic or "conversation" in act_purpose or "speaking" in act_purpose or "speaking" in act_skills or "conversation" in act_skills or "listening" in act_skills) and (g_kind in ("conversation", "speaking", "fluency") or g_skill in ("speaking", "listening") or "conversation" in g_target or "fluency" in g_target):
                matched = True

            if (act_type in ("formal_exam_essay", "exam_practice", "certification_prep", "mock_test", "standardized_test") or "exam" in act_purpose or "certification" in act_purpose or "assessment" in act_purpose) and (g_kind in ("certification", "exam", "assessment") or len([fw for fw in ("c1", "c2", "b2", "b1", "dele", "ielts", "toefl", "cambridge") if fw in g_target]) > 0):
                matched = True

            if (act_type in ("vocab_drill", "vocabulary", "flashcards", "spaced_review", "word_matching") or "vocab" in act_purpose or "vocabulary" in act_skills or "vocab" in act_skills) and (g_kind in ("vocabulary", "vocab", "lexicon") or g_skill == "vocabulary" or "vocab" in g_target):
                matched = True

            if (act_type in ("grammar_drill", "grammar", "syntax", "conjugation") or "grammar" in act_purpose or "grammar" in act_skills or "syntax" in act_skills) and (g_kind in ("grammar", "syntax", "accuracy") or g_skill == "grammar" or "grammar" in g_target):
                matched = True

            if (act_type in ("reading", "article_reading", "comprehension", "literature") or "reading" in act_purpose or "reading" in act_skills) and (g_kind in ("reading", "literature", "comprehension") or g_skill == "reading" or "reading" in g_target):
                matched = True

            if (act_type in ("writing", "essay", "composition", "free_writing") or "writing" in act_purpose or "writing" in act_skills) and (g_kind in ("writing", "academic_writing", "composition") or g_skill == "writing" or "writing" in g_target):
                matched = True

            if (act_type in ("practice", "review", "lesson", "exercise") or act_purpose in ("practice", "review", "lesson", "study")) and not is_unrelated:
                matched = True

            if matched:
                aligned_goal_ids.append(gid)

    unique_aligned_goals = sorted(set(aligned_goal_ids))
    activity_fit = "aligned" if unique_aligned_goals else "not_aligned"

    return {
        "coexisting_goals": coexisting_ids,
        "total_goals_count": len(raw_goals),
        "activity_fit": activity_fit,
        "aligned_goals": unique_aligned_goals,
    }


def evaluate_progression(
    *,
    previous_evidence: tuple[Any, ...] | list[Any] = (),
    current_evidence: tuple[Any, ...] | list[Any] = (),
    skill: str | None = None,
) -> dict[str, Any]:
    """Evaluate skill-level progression distinguishing short-term vs stable improvement."""
    clean_prev = _deduplicate_evidence(previous_evidence)
    clean_curr = _deduplicate_evidence(current_evidence)

    if not clean_prev or not clean_curr:
        return {
            "progression_outcome": "insufficient_evidence",
            "stable_progression": False,
            "skill": skill or "general",
        }

    def _comparable_score(record: Mapping[str, Any]) -> tuple[str, str, float] | None:
        provenance = _canonical_provenance(record)
        comparison_key = _safe_str(record.get("comparison_key"))
        score = record.get("score")
        if (
            provenance is None
            or comparison_key is None
            or record.get("comparable") is not True
            or isinstance(score, bool)
            or not isinstance(score, (int, float))
            or not math.isfinite(float(score))
            or (skill is not None and _safe_str(record.get("skill")) != skill)
        ):
            return None
        return comparison_key, provenance, float(score)

    previous_scores = [value for item in clean_prev if (value := _comparable_score(item)) is not None]
    current_scores = [value for item in clean_curr if (value := _comparable_score(item)) is not None]
    shared_keys = {key for key, _, _ in previous_scores} & {
        key for key, _, _ in current_scores
    }
    if len(shared_keys) != 1:
        return {
            "progression_outcome": "insufficient_evidence",
            "stable_progression": False,
            "skill": skill or "general",
        }

    comparison_key = next(iter(shared_keys))
    previous_for_key = [
        (provenance, score)
        for key, provenance, score in previous_scores
        if key == comparison_key
    ]
    prev_scores = [score for _, score in previous_for_key]
    baseline_provenance = {
        provenance for provenance, _ in previous_for_key
    }
    current_for_key = [
        (provenance, score)
        for key, provenance, score in current_scores
        if key == comparison_key and provenance not in baseline_provenance
    ]
    curr_scores = [score for _, score in current_for_key]
    if not prev_scores or not curr_scores:
        return {
            "progression_outcome": "insufficient_evidence",
            "stable_progression": False,
            "skill": skill or "general",
        }

    prev_avg = sum(prev_scores) / len(prev_scores)
    curr_avg = sum(curr_scores) / len(curr_scores)

    if len({provenance for provenance, _ in current_for_key}) < 2:
        if curr_avg > prev_avg + 0.15:
            outcome = "short_term_improvement"
        elif curr_avg < prev_avg - 0.20:
            outcome = "possible_regression"
        else:
            outcome = "stable"
        stable_prog = False
    else:
        if curr_avg > prev_avg + 0.10:
            outcome = "stable_improvement"
            stable_prog = True
        elif curr_avg < prev_avg - 0.25:
            outcome = "plateau"
            stable_prog = False
        else:
            outcome = "stable"
            stable_prog = False

    return {
        "progression_outcome": outcome,
        "stable_progression": stable_prog,
        "skill": skill or "general",
        "previous_average": prev_avg,
        "current_average": curr_avg,
    }


def _has_certification_source_authority_identity(source: Mapping[str, Any]) -> bool:
    """Accept only narrow source-identity predicates for certification authority."""
    if not isinstance(source, Mapping):
        return False
    return (
        _safe_str(source.get("official_source_id")) is not None
        or _safe_str(source.get("source_id")) is not None
        or _safe_str(source.get("provenance_id")) is not None
    )


def evaluate_certification_source(
    *,
    sources: tuple[Any, ...] | list[Any] = (),
    decision_critical: bool = False,
) -> dict[str, Any]:
    """Evaluate certification source authority and detect conflicts."""
    if not isinstance(sources, (list, tuple, set, frozenset)):
        sources_list: list[Any] = []
    else:
        sources_list = list(sources)

    raw_sources = [dict(normalize_json_value(s)) for s in sources_list if isinstance(s, Mapping)]

    if not raw_sources:
        return {
            "selected_source": None,
            "top_sources": [],
            "authority_rank": 0,
            "needs_verification": decision_critical,
            "unresolved_conflict": False,
        }

    def _temporal_state(source: Mapping[str, Any]) -> str:
        state = (_safe_str(source.get("temporal_state")) or "").lower()
        if source.get("date_valid") is True or state in {"current", "active", "verified_current"}:
            return "current"
        if source.get("date_valid") is False or state in {"stale", "historical", "expired", "outdated"}:
            return "stale"
        return "unknown"

    def _source_has_provenance(s: Mapping[str, Any]) -> bool:
        return _has_certification_source_authority_identity(s)

    def _auth(s: dict[str, Any]) -> int:
        stype = (_safe_str(s.get("source_type")) or "unknown").lower()
        temporal = _temporal_state(s)
        has_prov = _source_has_provenance(s)

        if stype == "official" and temporal == "current" and has_prov:
            return 6
        if stype in {"secondary", "authoritative_secondary"} and temporal == "current" and has_prov:
            return 5
        if stype == "official" and temporal == "stale" and has_prov:
            return 4
        if stype == "memory" and temporal == "stale":
            return 3
        if stype == "guide":
            return 2
        return 1

    sorted_sources = sorted(raw_sources, key=lambda s: (-_auth(s), _canonical_json_value(s)))
    top_auth = _auth(sorted_sources[0])
    top_tier = sorted(
        [s for s in sorted_sources if _auth(s) == top_auth],
        key=_canonical_json_value,
    )

    # Check for conflicts in top tier
    unresolved = False
    if len(top_tier) >= 2:
        # Check if format/dates conflict
        keys_to_compare = ("format", "task_count", "requirements", "exam_date")
        for k in keys_to_compare:
            vals = {
                _canonical_json_value(s.get(k))
                for s in top_tier
                if s.get(k) is not None
            }
            if len(vals) > 1:
                unresolved = True
                break

    selected = None if unresolved else top_tier[0]
    selected_temporal_state = _temporal_state(top_tier[0])
    needs_verif = unresolved or (
        decision_critical and (selected_temporal_state != "current" or top_auth < 5)
    )

    return {
        "selected_source": selected,
        "top_sources": top_tier,
        "authority_rank": top_auth,
        "unresolved_conflict": unresolved,
        "needs_verification": needs_verif,
    }


def _is_grounded_cultural_evidence(record: Mapping[str, Any]) -> bool:
    """Verify cultural evidence has recognized source/corpus/observation grounding."""
    return (
        _canonical_provenance(record) is not None
        or _safe_str(record.get("corpus_reference")) is not None
        or _safe_str(record.get("reference_id")) is not None
        or _safe_str(record.get("source_id")) is not None
        or _safe_str(record.get("observation_id")) is not None
        or _safe_str(record.get("lived_experience_id")) is not None
    )


def evaluate_cultural_context(
    *,
    claim: str | None = None,
    evidence: tuple[Any, ...] | list[Any] = (),
    universal_claim: bool = False,
) -> dict[str, Any]:
    """Evaluate cultural claims to reject universal stereotyping and preserve qualified tendencies."""
    if not isinstance(evidence, (list, tuple, set, frozenset)):
        ev_list: list[Any] = []
    else:
        ev_list = list(evidence)

    valid_evidence = [dict(normalize_json_value(e)) for e in ev_list if isinstance(e, Mapping)]
    claim_str = _safe_str(claim) or ""

    is_universal = universal_claim or len([
        kw for kw in (
            "all native speakers",
            "always",
            "every spanish",
            "everyone in",
            "never",
            "all french",
            "all germans",
            "universal rule",
        )
        if kw in claim_str.lower()
    ]) > 0

    has_grounded_evidence = len([e for e in valid_evidence if _is_grounded_cultural_evidence(e)]) > 0

    return {
        "claim": claim_str,
        "universal_claim_rejected": is_universal,
        "qualified_tendency": True,
        "nuance_preserved": True,
        "has_grounded_evidence": has_grounded_evidence,
        "evidence_status": "evidenced" if has_grounded_evidence else "weak_or_unprovenanced",
        "evidence": valid_evidence,
    }


def evaluate_language_memory_consent(
    *,
    content_kind: str | None = None,
    session_only: bool = True,
    consent: Any = None,
    permission_chain_valid: bool = False,
) -> dict[str, Any]:
    """Evaluate memory consent requirements enforcing literal boolean True and shared approval."""
    if session_only:
        return {
            "content_kind": content_kind or "session_data",
            "session_only_allowed": True,
            "persistence_required": False,
            "persistence_authorized": False,
            "proposal_required": False,
            "persistence_applied": False,
        }

    is_literal_true_consent = consent is True
    authorized = is_literal_true_consent and permission_chain_valid is True

    return {
        "content_kind": content_kind or "learning_state",
        "session_only_allowed": True,
        "persistence_required": True,
        "persistence_authorized": authorized,
        "proposal_required": is_literal_true_consent,
        "persistence_applied": False,  # Persistence is never directly applied by domain helper
    }


@dataclass(frozen=True, slots=True)
class SpacedReviewRule:
    definition: DomainReasoningRuleDefinition

    def evaluate(self, context: ReasoningRuleContext) -> ReasoningRuleResult:
        mat = _mapping(context.metadata, "material") or {}
        res = plan_spaced_review(
            items=mat.get("items", ()),
            active_goals=mat.get("active_goals", ()),
        )
        finding = ReasoningFinding(
            code="SPACED_REVIEW_EVALUATED",
            message=f"Spaced review queue formed with {len(res['review_queue'])} items.",
            severity=ReasoningSeverity.INFO,
            rule_id=self.definition.id,
            domain_id=self.definition.domain_id,
            metadata=res,
        )
        return _result(
            self.definition,
            context,
            ReasoningRuleResultStatus.APPLIED,
            findings=(finding,),
            code="SPACED_REVIEW_APPLIED",
            message="Spaced review evaluated.",
        )


@dataclass(frozen=True, slots=True)
class LearningLoadRule:
    definition: DomainReasoningRuleDefinition

    def evaluate(self, context: ReasoningRuleContext) -> ReasoningRuleResult:
        mat = _mapping(context.metadata, "material") or {}
        res = evaluate_learning_load(
            available_time=mat.get("available_time"),
            energy=mat.get("energy"),
            priorities=mat.get("priorities", ()),
            deadlines=mat.get("deadlines", ()),
            recent_load=mat.get("recent_load"),
            review_backlog=mat.get("review_backlog", ()),
        )
        finding = ReasoningFinding(
            code="LEARNING_LOAD_EVALUATED",
            message=f"Recommended {res['recommended_duration_minutes']} min load.",
            severity=ReasoningSeverity.INFO,
            rule_id=self.definition.id,
            domain_id=self.definition.domain_id,
            metadata=res,
        )
        return _result(
            self.definition,
            context,
            ReasoningRuleResultStatus.APPLIED,
            findings=(finding,),
            code="LEARNING_LOAD_APPLIED",
            message="Learning load evaluated.",
        )


@dataclass(frozen=True, slots=True)
class GoalAlignmentRule:
    definition: DomainReasoningRuleDefinition

    def evaluate(self, context: ReasoningRuleContext) -> ReasoningRuleResult:
        mat = _mapping(context.metadata, "material") or {}
        res = align_activity_to_goals(
            activity=mat.get("activity"),
            goals=mat.get("goals", ()),
        )
        finding = ReasoningFinding(
            code="GOAL_ALIGNMENT_EVALUATED",
            message=f"Aligned across {res['total_goals_count']} coexisting goals.",
            severity=ReasoningSeverity.INFO,
            rule_id=self.definition.id,
            domain_id=self.definition.domain_id,
            metadata=res,
        )
        return _result(
            self.definition,
            context,
            ReasoningRuleResultStatus.APPLIED,
            findings=(finding,),
            code="GOAL_ALIGNMENT_APPLIED",
            message="Goal alignment evaluated.",
        )


@dataclass(frozen=True, slots=True)
class ProgressionEvidenceRule:
    definition: DomainReasoningRuleDefinition

    def evaluate(self, context: ReasoningRuleContext) -> ReasoningRuleResult:
        mat = _mapping(context.metadata, "material") or {}
        res = evaluate_progression(
            previous_evidence=mat.get("previous_evidence", ()),
            current_evidence=mat.get("current_evidence", ()),
            skill=mat.get("skill"),
        )
        finding = ReasoningFinding(
            code="PROGRESSION_EVIDENCE_EVALUATED",
            message=f"Progression outcome: {res['progression_outcome']}.",
            severity=ReasoningSeverity.INFO,
            rule_id=self.definition.id,
            domain_id=self.definition.domain_id,
            metadata=res,
        )
        return _result(
            self.definition,
            context,
            ReasoningRuleResultStatus.APPLIED,
            findings=(finding,),
            code="PROGRESSION_EVIDENCE_APPLIED",
            message="Progression evidence evaluated.",
        )


@dataclass(frozen=True, slots=True)
class CertificationTemporalRule:
    definition: DomainReasoningRuleDefinition

    def evaluate(self, context: ReasoningRuleContext) -> ReasoningRuleResult:
        mat = _mapping(context.metadata, "material") or {}
        res = evaluate_certification_source(
            sources=mat.get("sources", ()),
            decision_critical=mat.get("decision_critical", False),
        )
        finding = ReasoningFinding(
            code="CERTIFICATION_TEMPORAL_EVALUATED",
            message=f"Certification source evaluated (needs_verification={res['needs_verification']}).",
            severity=ReasoningSeverity.INFO,
            rule_id=self.definition.id,
            domain_id=self.definition.domain_id,
            metadata=res,
        )
        return _result(
            self.definition,
            context,
            ReasoningRuleResultStatus.APPLIED,
            findings=(finding,),
            code="CERTIFICATION_TEMPORAL_APPLIED",
            message="Certification temporal source evaluated.",
        )


@dataclass(frozen=True, slots=True)
class CulturalContextEvidenceRule:
    definition: DomainReasoningRuleDefinition

    def evaluate(self, context: ReasoningRuleContext) -> ReasoningRuleResult:
        mat = _mapping(context.metadata, "material") or {}
        res = evaluate_cultural_context(
            claim=mat.get("claim"),
            evidence=mat.get("evidence", ()),
            universal_claim=mat.get("universal_claim", False),
        )
        finding = ReasoningFinding(
            code="CULTURAL_CONTEXT_EVALUATED",
            message="Cultural context evaluated with qualification.",
            severity=ReasoningSeverity.INFO,
            rule_id=self.definition.id,
            domain_id=self.definition.domain_id,
            metadata=res,
        )
        return _result(
            self.definition,
            context,
            ReasoningRuleResultStatus.APPLIED,
            findings=(finding,),
            code="CULTURAL_CONTEXT_APPLIED",
            message="Cultural context evaluated.",
        )


@dataclass(frozen=True, slots=True)
class LanguageMemoryConsentRule:
    definition: DomainReasoningRuleDefinition

    def evaluate(self, context: ReasoningRuleContext) -> ReasoningRuleResult:
        mat = _mapping(context.metadata, "material") or {}
        res = evaluate_language_memory_consent(
            content_kind=mat.get("content_kind"),
            session_only=mat.get("session_only", True),
            consent=mat.get("consent"),
            permission_chain_valid=mat.get("permission_chain_valid", False),
        )
        finding = ReasoningFinding(
            code="MEMORY_CONSENT_EVALUATED",
            message=f"Memory consent evaluated (persistence_authorized={res['persistence_authorized']}).",
            severity=ReasoningSeverity.INFO,
            rule_id=self.definition.id,
            domain_id=self.definition.domain_id,
            metadata=res,
        )
        return _result(
            self.definition,
            context,
            ReasoningRuleResultStatus.APPLIED,
            findings=(finding,),
            code="MEMORY_CONSENT_APPLIED",
            message="Memory consent evaluated.",
        )


def build_languages_rules() -> tuple[Any, ...]:
    """Build the fourteen Languages Domain rules deterministically in canonical catalog order."""
    by_id = {
        "languages.language_level_evidence": LanguageLevelEvidenceRule(
            definition=_definition("languages.language_level_evidence", "LanguageLevelEvidenceRule", ReasoningRuleCategory.EPISTEMIC.value, 700)
        ),
        "languages.skill_separation": SkillSeparationRule(
            definition=_definition("languages.skill_separation", "SkillSeparationRule", ReasoningRuleCategory.EPISTEMIC.value, 710)
        ),
        "languages.language_variety_validity": LanguageVarietyValidityRule(
            definition=_definition("languages.language_variety_validity", "LanguageVarietyValidityRule", ReasoningRuleCategory.EPISTEMIC.value, 720)
        ),
        "languages.proficiency_framework": ProficiencyFrameworkRule(
            definition=_definition("languages.proficiency_framework", "ProficiencyFrameworkRule", ReasoningRuleCategory.EPISTEMIC.value, 730)
        ),
        "languages.error_pattern_evidence": ErrorPatternEvidenceRule(
            definition=_definition("languages.error_pattern_evidence", "ErrorPatternEvidenceRule", ReasoningRuleCategory.EPISTEMIC.value, 740)
        ),
        "languages.correction_priority": CorrectionPriorityRule(
            definition=_definition("languages.correction_priority", "CorrectionPriorityRule", ReasoningRuleCategory.INFERENCE.value, 750)
        ),
        "languages.adaptive_difficulty": AdaptiveDifficultyRule(
            definition=_definition("languages.adaptive_difficulty", "AdaptiveDifficultyRule", ReasoningRuleCategory.INFERENCE.value, 760)
        ),
        "languages.spaced_review": SpacedReviewRule(
            definition=_definition("languages.spaced_review", "SpacedReviewRule", ReasoningRuleCategory.INFERENCE.value, 770)
        ),
        "languages.learning_load": LearningLoadRule(
            definition=_definition("languages.learning_load", "LearningLoadRule", ReasoningRuleCategory.INFERENCE.value, 780)
        ),
        "languages.goal_alignment": GoalAlignmentRule(
            definition=_definition("languages.goal_alignment", "GoalAlignmentRule", ReasoningRuleCategory.INFERENCE.value, 790)
        ),
        "languages.progression_evidence": ProgressionEvidenceRule(
            definition=_definition("languages.progression_evidence", "ProgressionEvidenceRule", ReasoningRuleCategory.EPISTEMIC.value, 800)
        ),
        "languages.certification_temporal": CertificationTemporalRule(
            definition=_definition("languages.certification_temporal", "CertificationTemporalRule", ReasoningRuleCategory.TEMPORALITY.value, 810)
        ),
        "languages.cultural_context_evidence": CulturalContextEvidenceRule(
            definition=_definition("languages.cultural_context_evidence", "CulturalContextEvidenceRule", ReasoningRuleCategory.EPISTEMIC.value, 820)
        ),
        "languages.language_memory_consent": LanguageMemoryConsentRule(
            definition=_definition("languages.language_memory_consent", "LanguageMemoryConsentRule", ReasoningRuleCategory.SAFETY.value, 830)
        ),
    }
    return tuple(
        by_id[rule_id]
        for rule_id in CANONICAL_LANGUAGES_RULE_IDS
    )
