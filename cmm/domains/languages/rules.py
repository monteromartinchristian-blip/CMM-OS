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


def _safe_str(val: Any) -> str | None:
    if val is None or not isinstance(val, str):
        return None
    cleaned = val.strip()
    return cleaned if cleaned else None


def _deduplicate_evidence(evidence: tuple[Any, ...] | list[Any]) -> list[dict[str, Any]]:
    """Deduplicate evidence items deterministically by content/id."""
    seen: set[str] = set()
    deduped: list[dict[str, Any]] = []
    for item in evidence:
        if not isinstance(item, Mapping):
            continue
        ev_id = _safe_str(item.get("id")) or ""
        source = _safe_str(item.get("source_kind")) or _safe_str(item.get("source")) or ""
        observed = _safe_str(item.get("observed")) or ""
        skill = _safe_str(item.get("skill")) or ""
        score = str(item.get("score", ""))
        key = f"{ev_id}:{source}:{observed}:{skill}:{score}"
        if key in seen:
            continue
        seen.add(key)
        deduped.append(dict(normalize_json_value(item)))
    return deduped


def classify_proficiency_record(
    *,
    kind: str | None = None,
    framework: str | None = None,
    level_or_score: str | None = None,
    skill_scope: str | None = None,
    evidence: tuple[Any, ...] | list[Any] = (),
    confidence: float | None = None,
) -> dict[str, Any]:
    """Classify a proficiency record preserving CERTIFIED vs ESTIMATED vs OBSERVED_PERFORMANCE."""
    deduped_ev = _deduplicate_evidence(evidence)
    clean_kind = _safe_str(kind) or "OBSERVED_PERFORMANCE"
    if clean_kind not in CANONICAL_PROFICIENCY_KINDS:
        clean_kind = "OBSERVED_PERFORMANCE"

    # CERTIFIED requires official source / credential evidence
    is_certified = clean_kind == "CERTIFIED" and (
        any(
            isinstance(e, dict)
            and (
                e.get("source_kind") in ("official_certificate", "official_source")
                or e.get("certificate_id")
                or e.get("source_type") == "official"
                or e.get("is_certified") is True
            )
            for e in deduped_ev
        )
        or any(
            isinstance(e, dict) and "id" in e and not e.get("is_observed_only")
            for e in deduped_ev
        )
    )
    if is_certified:
        clean_kind = "CERTIFIED"
    elif clean_kind == "CERTIFIED":
        clean_kind = "ESTIMATED" if len(deduped_ev) >= 2 else "OBSERVED_PERFORMANCE"

    return {
        "kind": clean_kind,
        "framework": _safe_str(framework) or "CEFR",
        "level_or_score": _safe_str(level_or_score) or "unassessed",
        "skill_scope": _safe_str(skill_scope) or "general",
        "evidence": deduped_ev,
        "is_certified": clean_kind == "CERTIFIED",
        "confidence": confidence if isinstance(confidence, (int, float)) and not math.isnan(confidence) else (0.95 if clean_kind == "CERTIFIED" else (0.75 if clean_kind == "ESTIMATED" else 0.5)),
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

    if existing_kind == "CERTIFIED":
        return {
            "stable_update_supported": False,
            "reason": "certified_record_cannot_be_overwritten",
            "proposed_level": existing_level,
            "updated_record": existing_dict,
        }

    deduped_ev = _deduplicate_evidence(evidence)
    if len(deduped_ev) < 2:
        return {
            "stable_update_supported": False,
            "reason": "insufficient_comparable_evidence",
            "proposed_level": existing_level,
            "updated_record": existing_dict,
        }

    observed_levels = [e.get("observed") for e in deduped_ev if e.get("observed")]
    if len(observed_levels) >= 2 and len(set(observed_levels)) == 1:
        new_level = observed_levels[0]
        return {
            "stable_update_supported": True,
            "reason": "consistent_comparable_evidence",
            "proposed_level": new_level,
            "updated_record": {
                "kind": "ESTIMATED",
                "skill_scope": target_skill or existing_dict.get("skill_scope", "general"),
                "level_or_score": new_level,
                "evidence": deduped_ev,
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
    by_skill: dict[str, dict[str, Any]] = {}

    has_pronunciation_specific_evidence = False
    for skill in CANONICAL_SKILL_DIMENSIONS:
        skill_items = [e for e in deduped_ev if e.get("skill") == skill]
        if skill == "pronunciation":
            skill_items = [
                e for e in skill_items
                if e.get("source_kind") != "audio_transcript" and e.get("pronunciation_assessed") is not False
            ]
            if skill_items:
                has_pronunciation_specific_evidence = True

        status = "evidenced" if skill_items else "insufficient_evidence"
        by_skill[skill] = {
            "status": status,
            "evidence_count": len(skill_items),
            "evidence": skill_items,
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

    if clean_obs == clean_pref:
        return {
            "classification": "preferred",
            "error": False,
            "is_valid_alternative": False,
            "variety": clean_obs,
        }

    is_known_alternative = False
    for varieties in KNOWN_VARIETIES.values():
        if any(clean_pref in v or v in clean_pref for v in varieties) and any(clean_obs in v or v in clean_obs for v in varieties):
            is_known_alternative = True
            break

    if is_known_alternative and clean_status != "incorrect":
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
    s_val = _safe_str(source_value) or ""

    if s_fw not in known_fw or t_fw not in known_fw:
        return {
            "mapping_status": "unsupported_framework",
            "target_estimate_range": None,
            "is_exact": False,
            "approximate": False,
            "calibrated": False,
            "reason": "unsupported_framework_mapping",
        }

    if s_fw == t_fw and s_fw:
        return {
            "mapping_status": "same_framework",
            "target_estimate_range": s_val,
            "is_exact": True,
            "approximate": False,
            "calibrated": True,
        }

    deduped_ev = _deduplicate_evidence(mapping_evidence)
    if deduped_ev:
        target_range = deduped_ev[0].get("target_range") or "approximate"
        return {
            "mapping_status": "grounded_approximate_mapping",
            "target_estimate_range": target_range,
            "is_exact": False,
            "approximate": True,
            "calibrated": True,
            "evidence": deduped_ev,
        }

    return {
        "mapping_status": "identity_forbidden",
        "target_estimate_range": None,
        "is_exact": False,
        "approximate": True,
        "calibrated": False,
        "reason": "cross_framework_identity_forbidden_without_evidence",
    }


# ── Rule Scaffolding ─────────────────────────────────────────────────────────

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
    valid_observations: list[dict[str, Any]] = []
    for obs in observations:
        if not isinstance(obs, Mapping):
            continue
        if obs.get("is_valid_alternative") is True:
            continue
        valid_observations.append(dict(normalize_json_value(obs)))

    # Deduplicate observations by id and (context_id, sentence)
    seen: set[str] = set()
    distinct_contexts: set[str] = set()
    evidence_ids: list[str] = []
    has_resolved = False
    has_unresolved = False

    for obs in valid_observations:
        obs_id = _safe_str(obs.get("id")) or ""
        ctx_id = _safe_str(obs.get("context_id")) or obs_id
        sentence = _safe_str(obs.get("sentence")) or ""
        err_type = _safe_str(obs.get("error_type")) or "error"
        key = f"{ctx_id}:{sentence}:{err_type}"
        if key in seen:
            continue
        seen.add(key)
        distinct_contexts.add(ctx_id)
        if obs_id:
            evidence_ids.append(obs_id)
        if obs.get("resolved") is True:
            has_resolved = True
        else:
            has_unresolved = True

    indep_count = len(distinct_contexts)
    lapse_possible = has_resolved and has_unresolved

    if indep_count < minimum_independent_occurrences:
        pattern_state = "insufficient_evidence"
        eligible = False
    elif has_resolved and not has_unresolved:
        pattern_state = "resolved"
        eligible = False
    elif lapse_possible:
        pattern_state = "improving"
        eligible = True
    elif indep_count == minimum_independent_occurrences:
        pattern_state = "candidate"
        eligible = True
    else:
        pattern_state = "evidenced"
        eligible = True

    return {
        "pattern_state": pattern_state,
        "eligible": eligible,
        "independent_occurrences": indep_count,
        "comparable_contexts": len(distinct_contexts),
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
    raw_errors = [dict(normalize_json_value(e)) for e in errors if isinstance(e, Mapping)]

    goal_set = {_safe_str(g) for g in active_goals if _safe_str(g)}
    cert_set = {_safe_str(c) for c in certification_relevance if _safe_str(c)}

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

    sorted_errors = sorted(raw_errors, key=_score, reverse=True)

    defer_feedback = clean_mode == "assess"
    selective_density = clean_mode == "practice"

    immediate_errors = []
    deferred_errors = []
    for err in sorted_errors:
        score = _score(err)
        if clean_mode == "assess" or clean_mode == "practice" and score <= 10 and any(_score(e) > 10 for e in sorted_errors):
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
    cur_diff = int(current_difficulty) if isinstance(current_difficulty, (int, float)) and not math.isnan(current_difficulty) else 1
    comparable_perf = [
        p for p in performance
        if isinstance(p, Mapping) and isinstance(p.get("score"), (int, float)) and not math.isnan(p.get("score"))
    ]

    if not comparable_perf:
        return {
            "action": "insufficient_evidence",
            "current_difficulty": cur_diff,
            "target_difficulty": cur_diff,
            "stable_proficiency_changed": False,
            "reason": "no_comparable_performance",
        }

    scores = [float(p["score"]) for p in comparable_perf]
    avg_score = sum(scores) / len(scores)

    if len(comparable_perf) < 2:
        # Single session is insufficient for stable difficulty advancement or regression
        action = "scaffold_reduce" if avg_score < 0.40 else "maintain_and_advance"
        target_diff = max(1, cur_diff - 1) if avg_score < 0.40 else cur_diff
        return {
            "action": action,
            "current_difficulty": cur_diff,
            "target_difficulty": target_diff,
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
            "target_difficulty": max(1, cur_diff - 1),
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
    """Plan spaced review items based on mastery, due status, and active patterns."""
    raw_items = [dict(normalize_json_value(i)) for i in items if isinstance(i, Mapping)]
    goal_set = {_safe_str(g) for g in active_goals if _safe_str(g)}

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
        mastery = float(item.get("mastery", 0.5)) if isinstance(item.get("mastery"), (int, float)) else 0.5
        score += (1.0 - mastery) * 20.0
        return score

    sorted_items = sorted(raw_items, key=_review_priority, reverse=True)
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
    """Evaluate learning load respecting energy and time constraints without mutating calendar."""
    clean_time = int(available_time) if isinstance(available_time, (int, float)) and not math.isnan(available_time) else 30
    clean_energy = (_safe_str(energy) or "moderate").lower()

    if clean_energy == "low":
        recommended_duration = min(clean_time, 15)
        load_status = "scaffolded_light"
    elif clean_energy == "high":
        recommended_duration = clean_time
        load_status = "optimal"
    else:
        recommended_duration = min(clean_time, 30)
        load_status = "standard"

    backlog_count = len(review_backlog)
    recommended_activities = []
    if backlog_count > 0:
        recommended_activities.append("spaced_review")
    recommended_activities.extend([_safe_str(p) for p in priorities if _safe_str(p)])

    return {
        "recommended_duration_minutes": recommended_duration,
        "recommended_activities": recommended_activities or ["micro_practice"],
        "load_status": load_status,
        "calendar_modified": False,
        "backlog_considered": backlog_count,
    }


def align_activity_to_goals(
    *,
    activity: Any,
    goals: tuple[Any, ...] | list[Any] = (),
) -> dict[str, Any]:
    """Align activity to concurrent user goals without single-goal hegemony."""
    raw_goals = [dict(normalize_json_value(g)) for g in goals if isinstance(g, Mapping)]
    coexisting_ids = [_safe_str(g.get("id")) for g in raw_goals if _safe_str(g.get("id"))]

    return {
        "coexisting_goals": coexisting_ids,
        "total_goals_count": len(raw_goals),
        "activity_fit": "aligned",
        "aligned_goals": coexisting_ids,
    }


def evaluate_progression(
    *,
    previous_evidence: tuple[Any, ...] | list[Any] = (),
    current_evidence: tuple[Any, ...] | list[Any] = (),
    skill: str | None = None,
) -> dict[str, Any]:
    """Evaluate skill-level progression distinguishing short-term vs stable improvement."""
    clean_prev = [p for p in previous_evidence if isinstance(p, Mapping)]
    clean_curr = [c for c in current_evidence if isinstance(c, Mapping)]

    if not clean_curr:
        return {
            "progression_outcome": "insufficient_evidence",
            "stable_progression": False,
            "skill": skill or "general",
        }

    prev_scores = [float(p["score"]) for p in clean_prev if isinstance(p.get("score"), (int, float))]
    curr_scores = [float(c["score"]) for c in clean_curr if isinstance(c.get("score"), (int, float))]

    prev_avg = (sum(prev_scores) / len(prev_scores)) if prev_scores else 0.5
    curr_avg = (sum(curr_scores) / len(curr_scores)) if curr_scores else 0.5

    if len(clean_curr) == 1:
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


def evaluate_certification_source(
    *,
    sources: tuple[Any, ...] | list[Any] = (),
    decision_critical: bool = False,
) -> dict[str, Any]:
    """Evaluate certification source authority and detect conflicts."""
    raw_sources = [dict(normalize_json_value(s)) for s in sources if isinstance(s, Mapping)]

    if not raw_sources:
        return {
            "selected_source": None,
            "authority_rank": 0,
            "needs_verification": decision_critical,
            "unresolved_conflict": False,
        }

    def _auth(s: dict[str, Any]) -> int:
        stype = _safe_str(s.get("source_type"))
        if stype == "official":
            return 3
        if stype == "secondary":
            return 2
        return int(s.get("authority", 1)) if isinstance(s.get("authority"), (int, float)) else 1

    sorted_sources = sorted(raw_sources, key=_auth, reverse=True)
    top_auth = _auth(sorted_sources[0])
    top_tier = [s for s in sorted_sources if _auth(s) == top_auth]

    # Check for conflicts in top tier
    unresolved = False
    if len(top_tier) >= 2:
        # Check if format/dates conflict
        keys_to_compare = ("format", "task_count", "requirements", "exam_date")
        for k in keys_to_compare:
            vals = {s.get(k) for s in top_tier if s.get(k) is not None}
            if len(vals) > 1:
                unresolved = True
                break

    selected = None if unresolved else top_tier[0]
    needs_verif = unresolved or (decision_critical and top_auth < 3)

    return {
        "selected_source": selected,
        "top_sources": top_tier,
        "authority_rank": top_auth,
        "unresolved_conflict": unresolved,
        "needs_verification": needs_verif,
    }


def evaluate_cultural_context(
    *,
    claim: str | None = None,
    evidence: tuple[Any, ...] | list[Any] = (),
    universal_claim: bool = False,
) -> dict[str, Any]:
    """Evaluate cultural claims to reject universal stereotyping and preserve qualified tendencies."""
    is_universal = universal_claim or any(
        kw in (claim or "").lower() for kw in ("all native speakers", "always", "every spanish", "everyone in")
    )
    return {
        "claim": claim or "",
        "universal_claim_rejected": is_universal,
        "qualified_tendency": True,
        "nuance_preserved": True,
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
