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
    "spanish": ("castilian spanish", "latin american spanish", "mexican spanish", "rioplatense spanish"),
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
        key = f"{ev_id}:{source}:{observed}"
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
    is_certified = clean_kind == "CERTIFIED" and any(
        isinstance(e, dict) and e.get("source_kind") in ("official_certificate", "official_source")
        for e in deduped_ev
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
            "is_valid_alternative": True,
            "variety": clean_obs,
        }

    return {
        "classification": "uncertain",
        "error": False,
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
    s_fw = (_safe_str(source_framework) or "").upper()
    t_fw = (_safe_str(target_framework) or "").upper()
    s_val = _safe_str(source_value) or ""

    if s_fw == t_fw and s_fw:
        return {
            "mapping_status": "same_framework",
            "target_estimate_range": s_val,
            "is_exact": True,
            "approximate": False,
        }

    deduped_ev = _deduplicate_evidence(mapping_evidence)
    if deduped_ev:
        target_range = deduped_ev[0].get("target_range") or "approximate"
        return {
            "mapping_status": "grounded_approximate_mapping",
            "target_estimate_range": target_range,
            "is_exact": False,
            "approximate": True,
            "evidence": deduped_ev,
        }

    return {
        "mapping_status": "identity_forbidden",
        "target_estimate_range": None,
        "is_exact": False,
        "approximate": True,
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
