"""Phase 10.25 — Concerns Domain Rules and deterministic helpers.

A declarative domain + pure deterministic concern-support helpers.  The
helper functions are state-free: no IO, no model calls, no registry mutation,
no internal clock.  They receive context explicitly and return deterministic
structures.

Behavioral center (frozen design §1, §9, §10): understand the concern →
understand lived significance → resolve/infer the current support need → give
useful substantive support → calibrate reality / interpretation / fear /
hypothesis / scenario when useful → reassure when evidence supports
reassurance OR acknowledge a real concern OR preserve uncertainty → explore
action only when useful or wanted → allow continued conversation without
forced resolution.

Semantic invariants preserved here:

    emotion != fact; interpretation != fact; fear != prediction;
    possibility != probability; uncertainty != danger;
    reassurance != false certainty; validation != agreement;
    empathy != truth inflation; directness != harshness;
    repetition != pathology; concern != disorder; support != therapy.

Malformed evidence fails closed and never increases certainty, reassurance,
concern, risk or hypothesis support.  Duplicates never inflate evidence.
Equivalent evidence sets yield equivalent results independent of input order.
All public outputs are strict JSON-safe; caller inputs are never mutated.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
import math
from typing import Any
import unicodedata

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
from cmm.domains.concerns.catalog import CANONICAL_CONCERNS_RULE_IDS
from cmm.domains.rule_contracts import DomainReasoningRuleDefinition, DomainRuleResult

CONCERNS_RULE_IDS: tuple[str, ...] = CANONICAL_CONCERNS_RULE_IDS

# ── Closed support-need values (frozen design §11) ──────────────────────────

SUPPORT_UNDERSTANDING = "UNDERSTANDING"
SUPPORT_EXPLORATION = "EXPLORATION"
SUPPORT_PERSPECTIVE = "PERSPECTIVE"
SUPPORT_REALITY_CHECK = "REALITY_CHECK"
SUPPORT_REASSURANCE = "REASSURANCE"
SUPPORT_INFORMATION = "INFORMATION"
SUPPORT_PROBLEM_SOLVING = "PROBLEM_SOLVING"
SUPPORT_DECISION_SUPPORT = "DECISION_SUPPORT"
SUPPORT_EMOTIONAL_PROCESSING = "EMOTIONAL_PROCESSING"
SUPPORT_NEXT_STEP = "NEXT_STEP"
SUPPORT_MIXED = "MIXED"
SUPPORT_UNCLEAR = "UNCLEAR"

CANONICAL_SUPPORT_NEEDS: tuple[str, ...] = (
    SUPPORT_UNDERSTANDING,
    SUPPORT_EXPLORATION,
    SUPPORT_PERSPECTIVE,
    SUPPORT_REALITY_CHECK,
    SUPPORT_REASSURANCE,
    SUPPORT_INFORMATION,
    SUPPORT_PROBLEM_SOLVING,
    SUPPORT_DECISION_SUPPORT,
    SUPPORT_EMOTIONAL_PROCESSING,
    SUPPORT_NEXT_STEP,
    SUPPORT_MIXED,
    SUPPORT_UNCLEAR,
)

# Explicit request phrases → canonical support need (deterministic keyword
# mapping over normalized text).  This is a closed vocabulary, not a classifier.
_EXPLICIT_REQUEST_SIGNALS: tuple[tuple[frozenset[str], str], ...] = (
    (
        frozenset(
            {
                "just need to talk",
                "solo necesito hablar",
                "necesito desahogarme",
                "i don't want advice",
                "no quiero consejos",
                "no advice",
                "sin consejos",
                "just listening",
                "solo escuchar",
                "need to get this out",
                "necesito sacar esto",
                "listen to me",
                "escuchame",
                "escúchame",
            }
        ),
        SUPPORT_EMOTIONAL_PROCESSING,
    ),
    (
        frozenset(
            {"tell me what you think", "que opinas", "qué opinas", "what would you do", "tu opinion", "tu opinión"}
        ),
        SUPPORT_PERSPECTIVE,
    ),
    (
        frozenset(
            {
                "do you think this is likely",
                "is there actually reason to worry",
                "hay motivos reales para preocuparse",
                "am i overreacting",
                "estoy exagerando",
                "reality check",
            }
        ),
        SUPPORT_REALITY_CHECK,
    ),
    (
        frozenset(
            {"can you reassure me", "puedes tranquilizarme", "reassure me that", "tranquilizame"}
        ),
        SUPPORT_REASSURANCE,
    ),
    (
        frozenset(
            {
                "what can i do",
                "que puedo hacer",
                "qué puedo hacer",
                "help me solve",
                "ayudame a resolver",
                "ayúdame a resolver",
                "how do i fix",
            }
        ),
        SUPPORT_PROBLEM_SOLVING,
    ),
    (
        frozenset(
            {
                "help me decide",
                "ayudame a decidir",
                "ayúdame a decidir",
                "should i",
                "deberia",
                "debería",
                "what should i choose",
            }
        ),
        SUPPORT_DECISION_SUPPORT,
    ),
    (
        frozenset(
            {
                "why does this bother me",
                "por que me afecta",
                "por qué me afecta",
                "por que esto me afecta",
                "por qué esto me afecta",
                "why am i so affected",
            }
        ),
        SUPPORT_UNDERSTANDING,
    ),
    (
        frozenset(
            {
                "one next step",
                "un siguiente paso",
                "reasonable next step",
                "next step",
                "siguiente paso",
                "cual es el primer paso",
                "cuál es el primer paso",
            }
        ),
        SUPPORT_NEXT_STEP,
    ),
)

# Session-context keys carrying current-turn signals (recent session context).
_SESSION_CONTEXT_KEYS: tuple[str, ...] = (
    "current_turn_signal",
    "latest_request",
    "current_request",
)

# Historical preference is the weakest basis.
_HISTORICAL_KEYS: tuple[str, ...] = ("historical_preference",)

# ── Material question dimensions (frozen design §20) ────────────────────────

QUESTION_MATERIAL = "material"
QUESTION_NOT_MATERIAL = "not_material"

MATERIAL_CHANGE_DIMENSIONS: frozenset[str] = frozenset(
    {
        "meaning",
        "risk",
        "reassurance",
        "interpretation",
        "domain routing",
        "decision",
        "next step",
    }
)

# Normalized aliases for the material dimensions (accent/case-insensitive).
_DIMENSION_ALIASES: dict[str, str] = {
    "meaning": "meaning",
    "significado": "meaning",
    "risk": "risk",
    "riesgo": "risk",
    "reassurance": "reassurance",
    "tranquilidad": "reassurance",
    "interpretation": "interpretation",
    "interpretacion": "interpretation",
    "interpretación": "interpretation",
    "domain routing": "domain routing",
    "enrutamiento": "domain routing",
    "decision": "decision",
    "decisión": "decision",
    "next step": "next step",
    "siguiente paso": "next step",
}

# ── Epistemic levels (frozen design §18) ────────────────────────────────────

LEVEL_FACT = "fact"
LEVEL_EXPERIENCE = "experience"
LEVEL_INTERPRETATION = "interpretation"
LEVEL_FEAR = "fear"
LEVEL_HYPOTHESIS = "hypothesis"
LEVEL_SCENARIO = "scenario"
LEVEL_UNCERTAINTY = "uncertainty"
LEVEL_UNKNOWN = "unknown"

KNOWN_LEVELS: frozenset[str] = frozenset(
    {
        LEVEL_FACT,
        LEVEL_EXPERIENCE,
        LEVEL_INTERPRETATION,
        LEVEL_FEAR,
        LEVEL_HYPOTHESIS,
        LEVEL_SCENARIO,
        LEVEL_UNCERTAINTY,
        LEVEL_UNKNOWN,
    }
)

# ── Reassurance states (frozen design §22) ──────────────────────────────────

REASSURANCE_SUPPORTED = "REASSURANCE_SUPPORTED"
REASSURANCE_PARTIAL = "REASSURANCE_PARTIAL"
UNCERTAIN = "UNCERTAIN"
CONCERN_SUPPORTED = "CONCERN_SUPPORTED"
INSUFFICIENT_BASIS = "INSUFFICIENT_BASIS"

CANONICAL_REASSURANCE_STATES: tuple[str, ...] = (
    REASSURANCE_SUPPORTED,
    REASSURANCE_PARTIAL,
    UNCERTAIN,
    CONCERN_SUPPORTED,
    INSUFFICIENT_BASIS,
)

# ── Target-relative evidence stance (frozen design §13.12, §22) ─────────────
#
# Evidence direction is relative to the TARGET CLAIM being assessed (the
# feared interpretation / actual concern), never to the lexical key a record
# happens to use.  Each record must declare its stance explicitly; unknown or
# malformed stances fail closed and cannot strengthen either direction.

STANCE_SUPPORTS_TARGET = "supports_target"
STANCE_OPPOSES_TARGET = "opposes_target"
STANCE_NEUTRAL = "neutral"

_KNOWN_STANCES: frozenset[str] = frozenset(
    {STANCE_SUPPORTS_TARGET, STANCE_OPPOSES_TARGET, STANCE_NEUTRAL}
)
# Explicitly recognized strong source qualities (closed vocabulary).
# Full reassurance requires an explicit recognized strong quality.
_STRONG_SOURCE_QUALITIES: frozenset[str] = frozenset(
    {
        "grounded",
        "direct_observation",
        "verified_record",
        "reliable_source",
        "primary_source",
        "verified",
        "sensor",
        "system_record",
        "first_hand",
    }
)

# Explicitly weak source qualities: such records can never upgrade an
# assessment to full support (frozen design §22 "source quality").
_WEAK_SOURCE_QUALITIES: frozenset[str] = frozenset(
    {
        "unverified_hearsay",
        "speculation",
        "rumor",
        "guess",
        "unverified",
        "secondhand_anecdote",
        "weak",
    }
)

# Explicitly recognized current temporal relevance (closed vocabulary).
# Full reassurance requires an explicit recognized current value.
_CURRENT_TEMPORAL_RELEVANCE: frozenset[str] = frozenset(
    {
        "current",
        "recent",
        "active",
        "up_to_date",
        "present",
        "live",
        "real_time",
    }
)

# Explicitly stale temporal relevance: evidence about a past state cannot
# upgrade reassurance about the current situation (frozen design §22
# "temporal relevance").
_STALE_TEMPORAL_RELEVANCE: frozenset[str] = frozenset(
    {"stale", "outdated", "expired", "old", "historical_only"}
)

# ── Base plausibility contract (frozen design §22) ──────────────────────────

BASE_PLAUSIBILITY_LOW = "low"
BASE_PLAUSIBILITY_MODERATE = "moderate"
BASE_PLAUSIBILITY_HIGH = "high"
BASE_PLAUSIBILITY_UNKNOWN = "unknown"

_BASE_PLAUSIBILITY_ALLOWED: frozenset[str] = frozenset(
    {
        BASE_PLAUSIBILITY_LOW,
        BASE_PLAUSIBILITY_MODERATE,
        BASE_PLAUSIBILITY_HIGH,
        BASE_PLAUSIBILITY_UNKNOWN,
    }
)

_BASE_PLAUSIBILITY_ALIASES: dict[str, str] = {
    "low": BASE_PLAUSIBILITY_LOW,
    "implausible": BASE_PLAUSIBILITY_LOW,
    "unlikely": BASE_PLAUSIBILITY_LOW,
    "moderate": BASE_PLAUSIBILITY_MODERATE,
    "medium": BASE_PLAUSIBILITY_MODERATE,
    "plausible": BASE_PLAUSIBILITY_MODERATE,
    "high": BASE_PLAUSIBILITY_HIGH,
    "likely": BASE_PLAUSIBILITY_HIGH,
    "unknown": BASE_PLAUSIBILITY_UNKNOWN,
    "unspecified": BASE_PLAUSIBILITY_UNKNOWN,
}

# ── Action states (frozen design §27) ───────────────────────────────────────

ACTION_NO_ACTION_NEEDED = "NO_ACTION_NEEDED"
ACTION_OPTIONAL = "ACTION_OPTIONAL"
ACTION_USEFUL = "ACTION_USEFUL"
ACTION_RECOMMENDED = "ACTION_RECOMMENDED"
DOMAIN_ESCALATION_NEEDED = "DOMAIN_ESCALATION_NEEDED"
USER_DECISION_REQUIRED = "USER_DECISION_REQUIRED"


# ═════════════════════════════════════════════════════════════════════════════
# Strict literal gates + normalization primitives (shared Phase 10 pattern)
# ═════════════════════════════════════════════════════════════════════════════


def _boolean_true(value: Any) -> bool:
    """Strict runtime boolean: only the literal ``True`` counts (not truthiness)."""
    return isinstance(value, bool) and value is True


def _grants_authorization(value: Any) -> bool:
    """Only the literal ``True`` authorizes a boolean-gated field."""
    return value is True


def _authorization_malformed(value: Any) -> bool:
    """True when a boolean-gated field holds an unsupported non-boolean type."""
    return value is not None and not isinstance(value, bool)


def _usable_scalar_string(value: Any) -> str | None:
    """Return a usable scalar string identity, or ``None``.

    Never unwraps ``list``/``tuple``: a collection is malformed for a singular
    field and is not coerced into a scalar.
    """
    if isinstance(value, str):
        stripped = value.strip()
        return stripped if stripped else None
    return None


def _usable_reference(value: Any) -> str | None:
    """Return the first usable reference identifier, or ``None``."""
    if isinstance(value, str):
        stripped = value.strip()
        return stripped if stripped else None
    if isinstance(value, (list, tuple)):
        for item in value:
            usable = _usable_reference(item)
            if usable is not None:
                return usable
    return None


def _value_missing(value: Any) -> bool:
    """Only ``None`` and blank strings are missing; numeric zero/False are real values."""
    return value is None or (isinstance(value, str) and not value.strip())


def _normalize_collection(
    value: Any,
    *,
    require_mapping_elements: bool = False,
) -> tuple[list, bool]:
    """Normalize a raw collection value into ``(items, malformed)``.

    ``None`` yields an empty collection that is NOT malformed (absent is
    distinct from malformed).  A non-collection non-string value is malformed
    when a collection is required.
    """
    if value is None:
        return [], False
    if isinstance(value, str):
        # A plain string is not a collection of semantic records.
        return [], True
    if isinstance(value, (list, tuple)):
        items = list(value)
        if require_mapping_elements:
            malformed = any(not isinstance(item, Mapping) for item in items)
        else:
            malformed = False
        return items, malformed
    return [], True


def _finite_number(value: Any) -> float | None:
    """Parse a finite number (int/float, not bool) or return ``None``."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    number = float(value)
    if not math.isfinite(number):
        return None
    return number


def normalize_json_value(value: Any) -> Any:
    """Recursively normalize a value to a strict-JSON-safe representation.

    Non-finite floats (NaN/infinity) collapse to ``None``; mappings, lists and
    tuples are recursed deterministically; strings, ints, finite floats and
    booleans pass through.  This is the shared normalization boundary for every
    public Concerns helper/operation result so that
    ``json.dumps(..., allow_nan=False)`` always succeeds without an accidental
    ``TypeError``.
    """
    if isinstance(value, float):
        if not math.isfinite(value):
            return None
        return value
    if isinstance(value, Mapping):
        return {
            (str(key) if not isinstance(key, str) else key): normalize_json_value(item)
            for key, item in value.items()
        }
    if isinstance(value, (list, tuple)):
        return tuple(normalize_json_value(item) for item in value)
    if isinstance(value, (str, int, bool)) or value is None:
        return value
    # Anything not JSON-safe at the helper boundary collapses fail-closed.
    return None


# ── Semantic normalization helpers ──────────────────────────────────────────


def _semantic_text(value: Any) -> str | None:
    """Normalize text into a lower-cased, unaccented string for matching."""
    import unicodedata

    text = _usable_scalar_string(value)
    if text is None:
        return None
    nfkd = unicodedata.normalize("NFKD", text)
    stripped = "".join(c for c in nfkd if not unicodedata.combining(c))
    return stripped.casefold().strip()


# ═════════════════════════════════════════════════════════════════════════════
# Task 3 helpers — understanding, lived experience, support need, questions
# ═════════════════════════════════════════════════════════════════════════════

# Closed catastrophic-promotion taxonomy (frozen design §24).
PROMOTION_POSSIBILITY_TO_PROBABILITY = "possibility_to_probability"
PROMOTION_AMBIGUITY_TO_WARNING_SIGN = "ambiguity_to_warning_sign"
PROMOTION_CHANGE_TO_DETERIORATION = "change_to_deterioration"
PROMOTION_SILENCE_TO_REJECTION = "silence_to_rejection"
PROMOTION_SYMPTOM_TO_SERIOUS_DISEASE = "symptom_to_serious_disease"
PROMOTION_SETBACK_TO_FAILURE = "setback_to_failure"
PROMOTION_UNCERTAINTY_TO_DANGER = "uncertainty_to_danger"

_CATASTROPHIC_PROMOTIONS: tuple[tuple[str, str, str], ...] = (
    ("possibility", "probability", PROMOTION_POSSIBILITY_TO_PROBABILITY),
    ("ambiguity", "warning_sign", PROMOTION_AMBIGUITY_TO_WARNING_SIGN),
    ("change", "deterioration", PROMOTION_CHANGE_TO_DETERIORATION),
    ("silence", "rejection", PROMOTION_SILENCE_TO_REJECTION),
    ("symptom", "serious_disease", PROMOTION_SYMPTOM_TO_SERIOUS_DISEASE),
    ("setback", "failure", PROMOTION_SETBACK_TO_FAILURE),
    ("uncertainty", "danger", PROMOTION_UNCERTAINTY_TO_DANGER),
)



# ═════════════════════════════════════════════════════════════════════════════
# Task 4 helpers — epistemics, uncertainty, reassurance, proportional risk
# ═════════════════════════════════════════════════════════════════════════════


def classify_concern_statement(value) -> dict:
    """Classify a statement into a canonical Concerns epistemic level.

    A caller-supplied ``level`` is honored only when it is one of the known
    levels.  A caller ``fact=True``/``confirmed=True`` label never promotes
    the level and never substitutes for grounding: a fact requires at least
    one usable evidence reference (frozen design §13.8, §67).  Experience
    stays valid lived experience without becoming an external fact; fear is
    never a prediction; scenario never claims probability.
    """
    if not isinstance(value, Mapping):
        return normalize_json_value(
            {
                "statement": None,
                "level": LEVEL_UNKNOWN,
                "grounded": False,
                "external_fact": False,
                "prediction": False,
                "probability_claim": False,
                "is_fear": False,
                "promotion_blocked": False,
                "malformed": True,
            }
        )
    statement = _usable_scalar_string(value.get("statement"))
    labeled_fact = _boolean_true(value.get("fact")) or _boolean_true(
        value.get("confirmed")
    )
    level = value.get("level")
    normalized_level = level if level in KNOWN_LEVELS else None

    raw_references = value.get("evidence_references")
    if isinstance(raw_references, (list, tuple)):
        collected = [
            usable
            for usable in (_usable_reference(item) for item in raw_references)
            if usable is not None
        ]
    else:
        single = _usable_reference(raw_references)
        collected = [single] if single is not None else []
    references = tuple(dict.fromkeys(collected))
    grounded = bool(references)

    promotion_blocked = False
    if normalized_level is None:
        # Positional fallback: explicit markers choose the closest safe level.
        if _boolean_true(value.get("experience")):
            normalized_level = LEVEL_EXPERIENCE
        elif _boolean_true(value.get("interpretation")):
            normalized_level = LEVEL_INTERPRETATION
        elif _boolean_true(value.get("fear")):
            normalized_level = LEVEL_FEAR
        elif _boolean_true(value.get("hypothesis")):
            normalized_level = LEVEL_HYPOTHESIS
        elif _boolean_true(value.get("scenario")):
            normalized_level = LEVEL_SCENARIO
        elif _boolean_true(value.get("uncertainty")):
            normalized_level = LEVEL_UNCERTAINTY
        else:
            normalized_level = LEVEL_UNKNOWN
        if labeled_fact and normalized_level != LEVEL_FACT:
            promotion_blocked = True
    elif normalized_level != LEVEL_FACT and labeled_fact:
        # A caller fact label on a non-fact level never promotes it.
        promotion_blocked = True

    if normalized_level == LEVEL_FACT and not grounded:
        # A bare fact label with no grounded reference stays ungrounded.
        promotion_blocked = True

    return normalize_json_value(
        {
            "statement": statement,
            "level": normalized_level,
            "grounded": grounded,
            "evidence_references": references,
            "external_fact": normalized_level == LEVEL_FACT and grounded,
            "prediction": False,
            "probability_claim": False,
            "is_fear": normalized_level == LEVEL_FEAR,
            "promotion_blocked": promotion_blocked,
            "labeled_fact": labeled_fact,
            "malformed": False,
        }
    )


def evaluate_uncertainty(*, records=()) -> dict:
    """Preserve what remains unknown without inventing resolution.

    Conflicting proposed resolutions stay conflict; malformed records fail
    closed and never resolve anything; empty input is valid-empty, not failure.
    """
    raw, malformed = _normalize_collection(records, require_mapping_elements=True)
    uncertainties: list[dict] = []
    resolutions: dict[str, set[str]] = {}
    malformed_records: list[str] = []
    valid_empty = records is not None and len(raw) == 0 and not malformed
    for entry in raw:
        if not isinstance(entry, Mapping):
            malformed_records.append(str(type(entry).__name__))
            continue
        identity = _usable_scalar_string(entry.get("identity"))
        unknown = _usable_scalar_string(entry.get("unknown")) or _usable_scalar_string(
            entry.get("ambiguous")
        )
        resolution = _usable_scalar_string(entry.get("resolution"))
        if identity is None and unknown is None:
            malformed_records.append("empty-record")
            continue
        record_identity = identity or unknown or "unidentified"
        uncertainties.append({"identity": record_identity, "unknown": unknown})
        if resolution is not None:
            # Conflict key is the unknown TOPIC (not the record identity):
            # two records proposing different answers for the same open
            # question remain conflicting.
            conflict_key = (unknown or record_identity).casefold()
            resolutions.setdefault(conflict_key, set()).add(resolution)

    conflict_present = any(len(options) > 1 for options in resolutions.values())
    return normalize_json_value(
        {
            "uncertainties": tuple(uncertainties),
            "uncertainty_preserved": True,
            "resolved_by_invention": False,
            "conflict_present": conflict_present,
            "conflicting_identities": tuple(
                sorted(key for key, options in resolutions.items() if len(options) > 1)
            ),
            "valid_empty": valid_empty and not malformed,
            "malformed_records": tuple(malformed_records),
            "malformed": malformed or bool(malformed_records),
            "persisted": False,
        }
    )


def _canonical_claim_key(claim: str) -> str:
    norm = unicodedata.normalize("NFKC", claim).strip().lower()
    return " ".join(norm.split())


def _normalize_evidence_entries(value: Any) -> tuple[tuple[dict, ...], int, int]:
    """Normalize evidence/counterevidence entries into target-relative records.

    Returns ``(usable, duplicate_count, malformed_count)``.

    Each usable record carries the frozen evidence dimensions explicitly:

        claim            — the substantive proposition the record asserts
        stance           — supports_target / opposes_target / neutral
        grounding        — provenance/source reference (required to count)
        source_quality   — grounded / weak quality marker (optional)
        temporal_relevance — current / stale marker (optional)

    Deduplication uses grounded provenance + substantive claim + stance —
    never the caller-controlled record ID alone — so one provenance repeated
    under different IDs cannot gain weight.  Records without an explicit
    known stance fail closed: they assert no target-relative direction and
    can never strengthen either reassurance or concern.
    """
    raw, malformed_structure = _normalize_collection(
        value, require_mapping_elements=True
    )
    malformed_count = 1 if malformed_structure else 0
    merged: dict[tuple[str, str, str], dict] = {}
    duplicates = 0
    for entry in raw:
        if not isinstance(entry, Mapping):
            malformed_count += 1
            continue
        identity = _usable_scalar_string(entry.get("identity"))
        grounding = _usable_reference(entry.get("grounding"))

        # Target-relative stance is explicit; legacy verb keys never decide
        # direction.  Unknown/missing stance fails closed.
        raw_stance = _usable_scalar_string(entry.get("stance"))
        stance = raw_stance if raw_stance in _KNOWN_STANCES else None

        # Substantive claim: explicit ``claim`` first; a bare string entry's
        # text may serve as its claim.
        claim = _usable_scalar_string(entry.get("claim"))
        if claim is None and isinstance(entry, str):
            claim = _usable_scalar_string(entry)

        if grounding is None or stance is None or claim is None:
            # A record that lacks provenance, an explicit stance, or a
            # substantive claim cannot count as target-relative evidence.
            malformed_count += 1
            continue

        source_quality = _usable_scalar_string(entry.get("source_quality"))
        temporal = _usable_scalar_string(entry.get("temporal_relevance"))

        # Deduplicate on provenance + normalized substantive claim + stance (NOT record ID).
        canonical_claim = _canonical_claim_key(claim)
        key = (grounding, canonical_claim, stance)
        if key in merged:
            duplicates += 1
            continue
        merged[key] = {
            "identity": identity,
            "claim": claim,
            "stance": stance,
            "grounding": grounding,
            "source_quality": source_quality,
            "temporal_relevance": temporal,
        }
    ordered = sorted(
        merged.values(),
        key=lambda item: (
            str(item["grounding"]),
            str(_canonical_claim_key(item["claim"])),
            str(item["stance"]),
        ),
    )
    return tuple(ordered), duplicates, malformed_count


def evaluate_reassurance(
    *,
    target_claim=None,
    evidence=(),
    counterevidence=(),
    uncertainty=(),
    material_concerns=(),
    base_plausibility=None,
    specialized_domain_result=None,
) -> dict:
    """Evaluate whether the available basis supports reassurance.

    Canonical outcomes (frozen design §22):

        REASSURANCE_SUPPORTED / REASSURANCE_PARTIAL / UNCERTAIN /
        CONCERN_SUPPORTED / INSUFFICIENT_BASIS

    Direction is TARGET-RELATIVE: every record declares an explicit stance
    (``supports_target`` / ``opposes_target`` / ``neutral``) toward the
    ``target_claim`` being assessed.  The lexical key a record arrives under
    (``supports``/``against``) never decides direction.  Unknown/malformed
    stances fail closed and cannot strengthen either direction.

    Frozen dimensions represented structurally:

        target claim, stance relative to target, grounding/provenance,
        source quality, temporal relevance, material negative signal,
        remaining uncertainty, base plausibility.

    Reassurance may coexist with uncertainty.  Absolute certainty is never
    manufactured.  Duplicates (same provenance + claim + stance under any
    caller-controlled IDs) do not inflate.  Weak-quality or stale records can
    never upgrade an assessment to full support.  No numerical probability is
    assigned unless supplied by an authorized specialized source — and even
    then it is preserved with provenance rather than produced by Concerns.
    """
    supporting, duplicate_evidence, evidence_malformed = _normalize_evidence_entries(
        evidence
    )
    countering, duplicate_counter, counter_malformed = _normalize_evidence_entries(
        counterevidence
    )

    concerns_raw, concerns_malformed = _normalize_collection(material_concerns)
    acknowledged_concerns: list[str] = []
    for concern in concerns_raw:
        usable = _usable_scalar_string(concern)
        if usable is not None:
            acknowledged_concerns.append(usable)
    material_concern = bool(acknowledged_concerns)

    uncertainty_record = evaluate_uncertainty(records=uncertainty)
    remaining_uncertainty = tuple(
        item["identity"] for item in uncertainty_record["uncertainties"]
    )

    # Merge both buckets into one target-relative pool: bucket placement is
    # not direction; each record's explicit stance is.
    pool = (*supporting, *countering)

    def _is_current_and_grounded(record: dict) -> bool:
        sq = record.get("source_quality")
        tr = record.get("temporal_relevance")
        return (
            sq in _STRONG_SOURCE_QUALITIES
            and sq not in _WEAK_SOURCE_QUALITIES
            and tr in _CURRENT_TEMPORAL_RELEVANCE
            and tr not in _STALE_TEMPORAL_RELEVANCE
        )

    pro_concern_all = [
        item
        for item in pool
        if item["stance"] == STANCE_SUPPORTS_TARGET
    ]
    pro_reassurance_all = [
        item
        for item in pool
        if item["stance"] == STANCE_OPPOSES_TARGET
    ]
    pro_concern_valid = [
        item
        for item in pro_concern_all
        if item["source_quality"] not in _WEAK_SOURCE_QUALITIES
        and item["temporal_relevance"] not in _STALE_TEMPORAL_RELEVANCE
    ]
    pro_concern_strong = [
        item for item in pro_concern_all if _is_current_and_grounded(item)
    ]
    # Weak/stale opposing records stay visible in output supporting pool,
    # but only strong/current records can upgrade reassurance to full support.
    pro_reassurance_strong = [
        item for item in pro_reassurance_all if _is_current_and_grounded(item)
    ]

    malformed_total = evidence_malformed + counter_malformed + concerns_malformed

    specialized_probability = None
    specialized_authorized = False
    specialized_reassuring = False
    specialized_concern = False
    specialized_red_flags: tuple[str, ...] = ()
    specialized_domain_id = None

    if isinstance(specialized_domain_result, Mapping):
        specialized_domain_id = _usable_scalar_string(
            specialized_domain_result.get("domain_id")
        )
        specialized_authorized = _grants_authorization(
            specialized_domain_result.get("authorized")
        )
        if specialized_authorized:
            probability = specialized_domain_result.get("probability")
            numeric = _finite_number(probability)
            specialized_probability = (
                numeric if numeric is not None and 0.0 <= numeric <= 1.0 else None
            )
            flags, flags_malformed = _normalize_collection(
                specialized_domain_result.get("red_flags")
            )
            if not flags_malformed:
                specialized_red_flags = tuple(
                    flag
                    for flag in (_usable_scalar_string(f) for f in flags)
                    if flag is not None
                )
            spec_risk = _usable_scalar_string(
                specialized_domain_result.get("risk_level")
                or specialized_domain_result.get("risk")
            )
            spec_assessment = _usable_scalar_string(
                specialized_domain_result.get("assessment")
            )
            spec_concern_flag = _boolean_true(
                specialized_domain_result.get("material_concern")
                or specialized_domain_result.get("has_concern")
            )
            if (
                specialized_red_flags
                or spec_risk in (_RISK_HIGH, _RISK_MEDIUM)
                or spec_concern_flag
                or spec_assessment in (CONCERN_SUPPORTED, "material_concern", "risk")
            ):
                specialized_concern = True

            spec_reassuring_flag = _boolean_true(
                specialized_domain_result.get("reassuring")
                or specialized_domain_result.get("is_reassuring")
                or specialized_domain_result.get("reassurance_supported")
            )
            if spec_reassuring_flag or spec_assessment in (
                REASSURANCE_SUPPORTED,
                "reassuring",
            ):
                specialized_reassuring = True

    # Base plausibility evaluation
    raw_bp = _usable_scalar_string(base_plausibility)
    canonical_bp = (
        _BASE_PLAUSIBILITY_ALIASES.get(raw_bp.lower()) if raw_bp else None
    )
    base_plausibility_value = raw_bp if canonical_bp is not None else None
    evaluated_bp = canonical_bp or BASE_PLAUSIBILITY_UNKNOWN
    target = _usable_scalar_string(target_claim)

    both_sides = bool(pro_reassurance_all) and (
        bool(pro_concern_all) or specialized_concern
    )

    # Decision ladder (frozen design §22, §25):
    # - mixed signals with material concern → REASSURANCE_PARTIAL;
    # - mixed signals without material concern → UNCERTAIN;
    # - concern-only basis (material concern or >=2 valid grounded records without reassurance) → CONCERN_SUPPORTED;
    # - genuine target-supporting evidence caps reassurance below SUPPORTED (never minimized; §25);
    # - full reassurance requires >=2 strong, current, well-sourced records opposing the target with no genuine supporting record, a valid target claim, and low/moderate base plausibility;
    # - weak/stale opposing records stay visible in supporting but cap at partial;
    # - missing target claim fails closed: direction without a target cannot fully reassure.
    if both_sides and (material_concern or specialized_concern):
        assessment = REASSURANCE_PARTIAL
    elif both_sides:
        assessment = UNCERTAIN
    elif (
        (material_concern and not pro_reassurance_all)
        or (len(pro_concern_valid) >= 2 and not pro_reassurance_all)
        or (specialized_concern and not pro_reassurance_all)
    ):
        assessment = CONCERN_SUPPORTED
    elif (material_concern or specialized_concern) and (
        pro_reassurance_all or pro_concern_all or specialized_reassuring
    ):
        assessment = REASSURANCE_PARTIAL
    elif pro_concern_valid:
        # A single grounded target-supporting record is a real counter-signal
        # but not a confirmed concern basis.
        assessment = UNCERTAIN
    elif (
        len(pro_reassurance_strong) >= 2
        and not specialized_concern
        and not material_concern
    ):
        if target is None or evaluated_bp == BASE_PLAUSIBILITY_HIGH:
            assessment = REASSURANCE_PARTIAL
        else:
            assessment = REASSURANCE_SUPPORTED
    elif (
        pro_reassurance_all or specialized_reassuring
    ) and not specialized_concern and not material_concern:
        if evaluated_bp == BASE_PLAUSIBILITY_HIGH and not pro_reassurance_strong:
            assessment = UNCERTAIN
        elif (
            specialized_reassuring
            and not pro_reassurance_all
            and evaluated_bp != BASE_PLAUSIBILITY_HIGH
        ):
            assessment = REASSURANCE_PARTIAL
        else:
            assessment = REASSURANCE_PARTIAL
    else:
        assessment = INSUFFICIENT_BASIS

    if target is None and assessment == REASSURANCE_SUPPORTED:
        assessment = REASSURANCE_PARTIAL

    absolute_certainty = False
    return normalize_json_value(
        {
            "assessment": assessment,
            "target_claim": target,
            "base_plausibility": base_plausibility_value,
            "supporting": tuple(pro_reassurance_all),
            "counterevidence": tuple(pro_concern_all),
            "remaining_uncertainty": remaining_uncertainty,
            "acknowledged_concerns": tuple(acknowledged_concerns),
            "material_concern": material_concern,
            "concern_erased": material_concern
            and assessment in (REASSURANCE_SUPPORTED,),
            "absolute_certainty": absolute_certainty,
            "duplicate_count": duplicate_evidence + duplicate_counter,
            "malformed_count": malformed_total,
            "invented_assessment": False,
            "numeric_probability_assigned": False,
            "probability": None,
            "specialized_probability": specialized_probability,
            "specialized_authorized": specialized_authorized,
            "reassurance_coexists_with_uncertainty": assessment
            in (REASSURANCE_SUPPORTED, REASSURANCE_PARTIAL)
            and bool(remaining_uncertainty),
            "persisted": False,
        }
    )


_RISK_NONE = "none"
_RISK_LOW = "low"
_RISK_MEDIUM = "medium"
_RISK_HIGH = "high"
_RISK_UNRESOLVED = "unresolved"

_SEVERITY_ALIASES: dict[str, str] = {
    "none": _RISK_NONE,
    "minimal": _RISK_LOW,
    "minor": _RISK_LOW,
    "low": _RISK_LOW,
    "moderate": _RISK_MEDIUM,
    "medium": _RISK_MEDIUM,
    "high": _RISK_HIGH,
    "severe": _RISK_HIGH,
}

_IMMEDIATE_MARKERS: frozenset[str] = frozenset(
    {"now", "immediately", "today", "in progress", "happening now"}
)


def evaluate_proportional_risk(
    *,
    evidence=(),
    severity=None,
    immediacy=None,
    specialized_domain_result=None,
) -> dict:
    """Calibrate risk proportionally; emotional intensity alone never elevates it.

    Separates:
      - subjective severity / lived impact (never objective risk by itself);
      - grounded objective risk evidence (a real change to objective risk);
      - authorized specialized risk (preserved with provenance and never
        downgraded because wording is calm) (frozen design §23, §63).

    Without grounded risk evidence or an authorized specialized result,
    subjective severity cannot create an objective risk state: medium stays
    unresolved, high stays unresolved with ``emotion_drove_risk=True``.
    Malformed inputs fail closed to unresolved rather than triggering
    high-risk state.
    """
    severity_norm = _semantic_text(severity)
    severity_malformed = severity is not None and (
        severity_norm is None or severity_norm not in _SEVERITY_ALIASES
    ) and not isinstance(severity, str)
    if isinstance(severity, str) and severity_norm not in _SEVERITY_ALIASES:
        # Unknown free-text severity carries no weight.
        severity_malformed = True

    immediacy_norm = _semantic_text(immediacy)
    immediate_claim = immediacy_norm in _IMMEDIATE_MARKERS if immediacy_norm else False

    specialized_red_flags: tuple[str, ...] = ()
    specialized_authorized = False
    specialized_domain_id = None
    if isinstance(specialized_domain_result, Mapping):
        specialized_domain_id = _usable_scalar_string(
            specialized_domain_result.get("domain_id")
        )
        specialized_authorized = _grants_authorization(
            specialized_domain_result.get("authorized")
        )
        flags, flags_malformed = _normalize_collection(
            specialized_domain_result.get("red_flags")
        )
        if flags_malformed:
            specialized_authorized = False
        else:
            usable_flags = tuple(
                flag
                for flag in (_usable_scalar_string(flag) for flag in flags)
                if flag is not None
            )
            if usable_flags:
                specialized_red_flags = usable_flags

    # ── Grounded objective risk evidence (I-006) ──────────────────────────
    # Evidence records may explicitly support a material risk (stance
    # supports_risk / supports / material).  Only grounded, current, material
    # records count toward objective risk.
    risk_evidence, _risk_dup, risk_malformed = _normalize_evidence_entries(evidence)
    grounded_risk_records = [
        item
        for item in risk_evidence
        if item["grounding"]
        and item["stance"] in (STANCE_SUPPORTS_TARGET, "supports_risk", "material")
        and item["source_quality"] in _STRONG_SOURCE_QUALITIES
        and item["source_quality"] not in _WEAK_SOURCE_QUALITIES
        and item["temporal_relevance"] in _CURRENT_TEMPORAL_RELEVANCE
        and item["temporal_relevance"] not in _STALE_TEMPORAL_RELEVANCE
    ]
    risk_evidence_material = len(grounded_risk_records) >= 1

    emotion_drove_risk = False
    if severity_malformed:
        base_risk = _RISK_UNRESOLVED
    else:
        mapped_severity = _SEVERITY_ALIASES.get(severity_norm)
        if mapped_severity in (_RISK_HIGH, _RISK_MEDIUM):
            # Subjective severity alone does NOT produce objective risk:
            # emotional certainty != evidential certainty (frozen §23, §29).
            emotion_drove_risk = True
        base_risk = _RISK_NONE

    # Objective risk ladder (grounding first):
    # - authorized specialized red flags → high (never downgraded by calm wording);
    # - grounded material risk evidence → calibrated non-none risk;
    # - immediacy alone without grounding stays unresolved;
    # - subjective severity never creates objective risk at ANY level (frozen §23).
    if specialized_authorized and specialized_red_flags:
        risk_level = _RISK_HIGH
        emotion_drove_risk = False
    elif risk_evidence_material and immediate_claim:
        risk_level = _RISK_HIGH
    elif risk_evidence_material:
        risk_level = _RISK_MEDIUM if len(grounded_risk_records) >= 2 else _RISK_LOW
    elif immediate_claim and risk_malformed == 0 and not risk_evidence_material:
        # Immediacy without grounded basis still cannot manufacture risk.
        risk_level = _RISK_UNRESOLVED
    elif severity_malformed:
        risk_level = _RISK_UNRESOLVED
    else:
        risk_level = _RISK_NONE

    invented_risk = (
        risk_level == _RISK_HIGH and not specialized_authorized and not risk_evidence_material
    )
    return normalize_json_value(
        {
            "risk_level": risk_level,
            "emotion_drove_risk": emotion_drove_risk,
            "downgraded": False,
            "specialized_ownership_preserved": specialized_authorized,
            "specialized_domain_id": specialized_domain_id,
            "specialized_red_flags": specialized_red_flags,
            "grounded_risk_evidence": bool(grounded_risk_records),
            "immediate": immediate_claim and risk_level == _RISK_HIGH,
            "escalation_recommended": risk_level == _RISK_HIGH
            and specialized_authorized,
            "invented_risk": invented_risk,
            "malformed_input_ignored": severity_malformed,
            "persisted": False,
        }
    )


def detect_catastrophic_escalation(*, source_state, proposed_state) -> dict:
    """Detect an unsupported catastrophic promotion between semantic kinds.

    Blocked promotions (frozen design §24): possibility→probability,
    ambiguity→warning sign, change→deterioration, silence→rejection,
    symptom→serious disease, setback→failure, uncertainty→danger.  Malformed
    states are evaluated=False and authorize no transition either way.
    """
    source_kind = (
        _semantic_text(source_state.get("kind"))
        if isinstance(source_state, Mapping)
        else None
    )
    proposed_kind = (
        _semantic_text(proposed_state.get("kind"))
        if isinstance(proposed_state, Mapping)
        else None
    )
    evaluated = source_kind is not None and proposed_kind is not None
    blocked = False
    promotion = None
    if evaluated:
        for source, proposed, marker in _CATASTROPHIC_PROMOTIONS:
            if source_kind == source and proposed_kind == proposed:
                blocked = True
                promotion = marker
                break
    return normalize_json_value(
        {
            "evaluated": evaluated,
            "blocked": blocked,
            "promotion": promotion,
            "source_kind": source_kind,
            "proposed_kind": proposed_kind,
            "adequate_evidence": False,
        }
    )


# ── Caveat stacking guard (frozen design §24.1, §88.4; I-005) ───────────────
#
# Remote negative possibilities must not be appended as safety caveats merely
# because they are technically possible.  A caveat survives only when it is
# material AND grounded AND current-relevant.  Unsupported remote negatives
# are suppressed and counted, so "probably fine, BUT..." lists never grow from
# technical possibility alone.

_MATERIAL_WARNING_KINDS: frozenset[str] = frozenset(
    {"material_warning", "material", "warning", "grounded_warning"}
)
_REMOTE_POSSIBILITY_KINDS: frozenset[str] = frozenset(
    {
        "remote_possibility",
        "remote",
        "technical_possibility",
        "speculative",
        "unlikely",
    }
)


def evaluate_caveat_policy(*, caveats=()) -> dict:
    """Apply the proportional-caveat guard to a proposed caveat/scenario set.

    Each proposed item may carry:

        caveat          — the text
        grounding       — provenance/source reference
        materiality     — material_warning | remote_possibility | ...
        relevance       — low/medium/high
        source          — source label
        uncertainty     — low/medium/high

    A caveat is RETAINED only when it is a material, grounded, relevant
    warning.  Remote negative possibilities are suppressed (never stacked)
    even when technically possible.  The result is JSON-safe and order
    invariant.
    """
    raw, malformed = _normalize_collection(caveats, require_mapping_elements=True)
    retained: list[dict] = []
    suppressed = 0
    for entry in raw:
        if not isinstance(entry, Mapping):
            suppressed += 1
            continue
        caveat = _usable_scalar_string(
            entry.get("caveat") or entry.get("warning") or entry.get("text")
        )
        if caveat is None:
            suppressed += 1
            continue
        materiality = _semantic_text(entry.get("materiality")) or "remote_possibility"
        grounding = _usable_reference(entry.get("grounding"))
        relevance = _semantic_text(entry.get("relevance")) or "low"
        uncertainty = _semantic_text(entry.get("uncertainty")) or "high"

        is_material = materiality in _MATERIAL_WARNING_KINDS or (
            materiality not in _REMOTE_POSSIBILITY_KINDS and grounding is not None
        )
        relevant = relevance in ("high", "medium")
        grounded = grounding is not None
        if is_material and grounded and relevant and uncertainty not in ("high", "unknown"):
            retained.append(
                {
                    "caveat": caveat,
                    "grounding": grounding,
                    "materiality": materiality,
                    "relevance": relevance,
                    "source": _usable_scalar_string(entry.get("source")),
                    "uncertainty": uncertainty,
                }
            )
        else:
            suppressed += 1

    retained = sorted(retained, key=lambda item: str(item["caveat"]))
    return normalize_json_value(
        {
            "retained": tuple(retained),
            "suppressed_count": suppressed + (1 if malformed else 0),
            "suppression_reason": (
                "unsupported_remote_possibilities" if retained and suppressed
                else "unsupported_remote_possibilities"
                if suppressed and not retained
                else None
            ),
            "remote_possibilities_not_stacked": True,
            "malformed_input": malformed,
        }
    )


def detect_false_reassurance(*, reassurance_state, material_concerns=()) -> dict:
    """Detect reassurance that minimizes real evidence merely to comfort.

    Forbidden when material warning signals exist and are minimized/erased,
    or when the reassuring statement claims absolute certainty (frozen design §25).
    """
    state = reassurance_state if isinstance(reassurance_state, Mapping) else {}
    assessment = _usable_scalar_string(state.get("assessment"))
    concerns_raw, concerns_malformed = _normalize_collection(material_concerns)
    concerns = tuple(
        usable
        for usable in (_usable_scalar_string(item) for item in concerns_raw)
        if usable is not None
    )
    has_material_concern = bool(concerns) or concerns_malformed
    absolute_certainty = _boolean_true(state.get("absolute_certainty"))
    concern_erased = _boolean_true(state.get("concern_erased"))

    false_reassurance = False
    reason = None
    corrected = assessment
    if absolute_certainty:
        false_reassurance = True
        reason = "absolute_certainty"
        corrected = CONCERN_SUPPORTED if has_material_concern else UNCERTAIN
    elif has_material_concern and assessment == REASSURANCE_SUPPORTED:
        false_reassurance = True
        reason = "material_concern_minimized"
        corrected = CONCERN_SUPPORTED
    elif has_material_concern and assessment == REASSURANCE_PARTIAL and concern_erased:
        false_reassurance = True
        reason = "material_concern_minimized"
        corrected = CONCERN_SUPPORTED

    presented_as_supported = (
        assessment == REASSURANCE_SUPPORTED and not false_reassurance
    )
    return normalize_json_value(
        {
            "false_reassurance": false_reassurance,
            "reason": reason,
            "corrected_assessment": corrected,
            "presented_as_supported": presented_as_supported,
            "material_concerns": concerns,
            "absolute_certainty": absolute_certainty,
        }
    )


# ═════════════════════════════════════════════════════════════════════════════
# Task 5 helpers — recurrence, agency, directness, immediate escalation
# ═════════════════════════════════════════════════════════════════════════════

RECURRENCE_FIRST_TIME = "first_time"
RECURRENCE_NEW_TOPIC = "same_topic_new_question"
RECURRENCE_SAME_QUESTION_NEW_EVIDENCE = "same_question_new_evidence"
RECURRENCE_SAME_QUESTION_SAME_EVIDENCE = "same_question_same_evidence"
RECURRENCE_IMPACT_CHANGED = "impact_changed"

# Grounded dimensions required before a repetitive impossible-certainty
# pattern may be structurally recognized (frozen design §26).  ALL of them
# must be present across turns; missing evidence is never invented.
_PATTERN_DIMENSIONS: frozenset[str] = frozenset(
    {
        "same_question",
        "evidence_state_unchanged",
        "impossible_certainty_pursuit",
        "relief_followed_by_checking",
        "multiple_turns",
    }
)

_MIN_TURNS_FOR_PATTERN = 3

# Closed immediate-risk signal vocabulary.  This is a routing boundary, not a
# clinical classifier (frozen design §29): Concerns never creates its own
# clinical or emergency protocol.
_IMMEDIATE_RISK_SIGNALS: tuple[str, ...] = (
    "immediate physical danger",
    "physical danger now",
    "active abuse",
    "active violence",
    "violence happening now",
    "imminent self-harm",
    "self-harm risk now",
    "imminent harm",
    "severe acute medical warning sign",
    "crushing chest pain at rest right now",
    "immediately destructive external action",
)


def review_recurring_concern_state(*, current=None, previous=()) -> dict:
    """Compare the current concern with previous grounded iterations.

    Recurrence comparison uses actual state — question, grounded evidence set
    and impact — never merely topic labels (frozen design §70).  Returning to
    the same concern is not pathology; ``pathology_inferred`` is always False.
    """
    current_ok = isinstance(current, Mapping)
    previous_raw = previous if isinstance(previous, (list, tuple)) else ()
    malformed = (current is not None and not current_ok) or not isinstance(
        previous, (list, tuple)
    )
    if not current_ok:
        return normalize_json_value(
            {
                "recurrence": RECURRENCE_FIRST_TIME,
                "same_topic": False,
                "same_question": False,
                "meaningfully_different": False,
                "evidence_changed": False,
                "interpretation_changed": False,
                "impact_changed": False,
                "reassurance_allowed": True,
                "new_risk_invented_from_repetition": False,
                "pathology_inferred": False,
                "diagnosis": None,
                "psychiatric_label": False,
                "malformed_input": True,
            }
        )

    topic = _semantic_text(
        current.get("topic") or current.get("situation") or current.get("concern")
    )
    question = _semantic_text(current.get("question"))
    current_evidence = {
        ref
        for ref in (
            _usable_reference(item)
            for item in (
                current.get("evidence_references")
                if isinstance(current.get("evidence_references"), (list, tuple))
                else ()
            )
        )
        if ref is not None
    }

    comparable_previous = []
    prior_topics: set[str] = set()
    prior_questions: dict[str, set[str]] = {}
    prior_evidence: dict[str, set[str]] = {}
    prior_impacts: dict[str, str | None] = {}
    for entry in previous_raw:
        if not isinstance(entry, Mapping):
            malformed = True
            continue
        entry_topic = _semantic_text(
            entry.get("topic") or entry.get("situation") or entry.get("concern")
        )
        entry_question = _semantic_text(entry.get("question"))
        entry_refs = {
            ref
            for ref in (
                _usable_reference(item)
                for item in (
                    entry.get("evidence_references")
                    if isinstance(entry.get("evidence_references"), (list, tuple))
                    else ()
                )
            )
            if ref is not None
        }
        impact = _semantic_text(entry.get("impact_level"))
        comparable_previous.append(entry)
        if entry_topic:
            prior_topics.add(entry_topic)
            if entry_question:
                prior_questions.setdefault(entry_topic, set()).add(entry_question)
            prior_evidence.setdefault(entry_topic, set()).update(entry_refs)
            if impact:
                prior_impacts[entry_topic] = impact

    same_topic = topic is not None and topic in prior_topics
    same_question = (
        same_topic
        and question is not None
        and question in prior_questions.get(topic, set())
    )
    prior_refs_for_topic = prior_evidence.get(topic or "", set()) if topic else set()

    if not previous_raw or not same_topic:
        recurrence = RECURRENCE_FIRST_TIME
    elif not same_question:
        recurrence = RECURRENCE_NEW_TOPIC
    elif current_evidence != prior_refs_for_topic:
        recurrence = RECURRENCE_SAME_QUESTION_NEW_EVIDENCE
    else:
        recurrence = RECURRENCE_SAME_QUESTION_SAME_EVIDENCE

    current_impact = _semantic_text(current.get("impact_level"))
    impact_changed = bool(
        same_topic
        and current_impact
        and prior_impacts.get(topic) is not None
        and current_impact != prior_impacts[topic]
    )

    meaningfully_different = recurrence in (
        RECURRENCE_NEW_TOPIC,
        RECURRENCE_SAME_QUESTION_NEW_EVIDENCE,
    ) or impact_changed

    return normalize_json_value(
        {
            "recurrence": recurrence,
            "same_topic": same_topic,
            "same_question": same_question,
            "meaningfully_different": meaningfully_different,
            "evidence_changed": recurrence
            == RECURRENCE_SAME_QUESTION_NEW_EVIDENCE,
            "interpretation_changed": _boolean_true(
                current.get("interpretation_changed")
            ),
            "impact_changed": impact_changed,
            # Reassurance remains allowed unless independent grounded evidence
            # changes the assessment; repetition alone never blocks it.
            "reassurance_allowed": True,
            "new_risk_invented_from_repetition": False,
            "pathology_inferred": False,
            "diagnosis": None,
            "psychiatric_label": False,
            "malformed_input": malformed,
        }
    )


def evaluate_repetitive_certainty_pattern(*, turns=()) -> dict:
    """Structurally recognize a repetitive impossible-certainty pattern only
    when ALL grounded dimensions coexist across multiple turns.

    Even when recognized: no psychiatric label, reassurance remains allowed,
    unchanged evidence and unresolved uncertainty stay visible (frozen §26).
    """
    raw, malformed_structure = _normalize_collection(
        turns, require_mapping_elements=True
    )
    present: set[str] = set()
    turn_count = len(raw)
    for turn in raw:
        if not isinstance(turn, Mapping):
            continue
        if _boolean_true(turn.get("same_question")):
            present.add("same_question")
        if _usable_scalar_string(turn.get("evidence_state")) == "unchanged":
            present.add("evidence_state_unchanged")
        # Impossible-certainty pursuit is an INDEPENDENT grounded dimension
        # (frozen design §26).  ``same_question`` alone never implies it — a
        # repeated identical question about an unresolvable matter is not
        # certainty pursuit unless an explicit marker exists (I-002).
        if _boolean_true(turn.get("pursuing_certainty")) or _boolean_true(
            turn.get("impossible_certainty")
        ):
            present.add("impossible_certainty_pursuit")
        if _boolean_true(turn.get("relief_followed_by_checking")):
            present.add("relief_followed_by_checking")
    if turn_count >= _MIN_TURNS_FOR_PATTERN:
        present.add("multiple_turns")

    required_present = _PATTERN_DIMENSIONS <= present
    pattern_detected = (
        required_present
        and not malformed_structure
        and turn_count >= _MIN_TURNS_FOR_PATTERN
    )
    missing = tuple(sorted(_PATTERN_DIMENSIONS - present))
    return normalize_json_value(
        {
            "pattern_detected": pattern_detected,
            "dimensions_present": tuple(sorted(present)),
            "missing_dimensions": missing,
            "turn_count": turn_count,
            "required_dimensions_met": required_present,
            # Non-negotiable outcomes even under a detected pattern.
            "reassurance_allowed": True,
            "unchanged_evidence_visible": True,
            "unresolved_uncertainty_visible": True,
            "pathology_inferred": False,
            "diagnosis": None,
            "psychiatric_label": False,
            "punitive_or_withholding": False,
            "malformed_input": malformed_structure,
        }
    )


def evaluate_action_state(
    *,
    options=(),
    urgency=None,
    user_request=None,
    grounded_options=False,
    specialized_recommendation=False,
    specialized_domain_result=None,
) -> dict:
    """Resolve the canonical action state without pressure or adoption.

    No action is a valid outcome.  option != recommendation != adopted action
    != authorized execution; the system never adopts a personal decision and
    never executes an external action from a Concerns operation.
    """
    options_raw, options_malformed = _normalize_collection(options)
    usable_options = tuple(
        usable
        for usable in (_usable_scalar_string(item) for item in options_raw)
        if usable is not None
    )
    request_norm = _semantic_text(user_request)
    urgency_norm = _semantic_text(urgency)

    wants_no_advice = any(
        marker in (request_norm or "")
        for marker in ("just need to talk", "no advice", "solo necesito hablar", "wait")
        if marker
    )
    wants_decision_made = bool(
        request_norm
        and ("decide for me" in request_norm or "decide por mi" in request_norm)
    )
    asks_action = bool(
        request_norm
        and any(
            marker in request_norm
            for marker in ("what can i do", "que puedo hacer", "next step", "siguiente paso")
            if marker
        )
    )
    urgent = urgency_norm in {"now", "today", "urgent", "soon", "immediately"}

    specialized_domain_id = None
    specialized_flags: tuple[str, ...] = ()
    specialized_authorized = False
    if isinstance(specialized_domain_result, Mapping):
        specialized_domain_id = _usable_scalar_string(
            specialized_domain_result.get("domain_id")
        )
        specialized_authorized = _grants_authorization(
            specialized_domain_result.get("authorized")
        )
        flags, flags_malformed = _normalize_collection(
            specialized_domain_result.get("red_flags")
        )
        if not flags_malformed:
            specialized_flags = tuple(
                flag
                for flag in (_usable_scalar_string(flag) for flag in flags)
                if flag is not None
            )

    # Explicit wait / no-advice / just-talk intent is respected (I-003):
    # before any candidate-option logic, an explicit no-action intent with no
    # grounded immediate specialized escalation yields NO_ACTION_NEEDED.
    # Options may exist internally but the action result must not invite
    # action against the user's current explicit intent.
    grounded_immediate_escalation = (
        specialized_authorized and bool(specialized_flags) and urgent
    )
    if wants_no_advice and not grounded_immediate_escalation:
        return normalize_json_value(
            {
                "state": ACTION_NO_ACTION_NEEDED,
                "options": usable_options,
                "options_are_candidates": True,
                "recommendation_made": False,
                "specialized_recommendation": specialized_recommendation,
                "decision_adopted": False,
                "external_action_executed": False,
                "user_decision_required_for_adoption": True,
                "action_forced": False,
                "specialized_domain_id": specialized_domain_id,
                "grounded_options": _grants_authorization(grounded_options),
                "malformed_input": options_malformed,
            }
        )

    if wants_decision_made:
        state = USER_DECISION_REQUIRED
    elif grounded_immediate_escalation:
        # Only grounded immediate/domain escalation can override explicit
        # no-advice/wait, and only to DOMAIN_ESCALATION_NEEDED (never to a
        # personal adopted decision).
        state = DOMAIN_ESCALATION_NEEDED
    elif specialized_authorized and specialized_flags and urgent:
        state = DOMAIN_ESCALATION_NEEDED
    elif urgent and specialized_recommendation and usable_options:
        state = ACTION_RECOMMENDED
    elif asks_action and usable_options:
        state = ACTION_USEFUL
    elif usable_options:
        state = ACTION_OPTIONAL
    elif asks_action and not options_malformed:
        # A request for action with no usable options stays proportional.
        state = ACTION_OPTIONAL
    else:
        state = ACTION_NO_ACTION_NEEDED

    recommendation_made = state in (ACTION_RECOMMENDED,)
    return normalize_json_value(
        {
            "state": state,
            "options": usable_options,
            "options_are_candidates": True,
            "recommendation_made": recommendation_made,
            "specialized_recommendation": specialized_recommendation,
            "decision_adopted": False,
            "external_action_executed": False,
            "user_decision_required_for_adoption": True,
            "action_forced": state == ACTION_NO_ACTION_NEEDED and False,
            "specialized_domain_id": specialized_domain_id,
            "grounded_options": _grants_authorization(grounded_options),
            "malformed_input": options_malformed,
        }
    )


def evaluate_grounded_directness(
    *,
    assessment=None,
    evidence=(),
    uncertainty=(),
) -> dict:
    """Decide whether a grounded opinion may be stated, and how directly.

    The system may disagree when evidence is weak for the user's reading,
    acknowledge real concern when evidence is strong, and must preserve
    uncertainty when balanced.  Empathy never requires agreement, but
    directness is never harshness.
    """
    assessment_norm = _semantic_text(assessment)
    records, malformed = _normalize_collection(evidence, require_mapping_elements=True)
    supporting_refs = {
        item["grounding"]
        for item in records
        if isinstance(item, Mapping) and item.get("supports") and _usable_reference(item.get("identity")) is not None
    }
    countering_refs = {
        item["grounding"]
        for item in records
        if isinstance(item, Mapping) and item.get("against") and _usable_reference(item.get("identity")) is not None
    }
    del supporting_refs, countering_refs

    grounded_support = [
        item
        for item in records
        if isinstance(item, Mapping)
        and _usable_reference(item.get("grounding")) is not None
        and _usable_scalar_string(item.get("supports")) is not None
    ]
    grounded_counter = [
        item
        for item in records
        if isinstance(item, Mapping)
        and _usable_reference(item.get("grounding")) is not None
        and _usable_scalar_string(item.get("against")) is not None
    ]
    has_basis = bool(grounded_support or grounded_counter)
    balanced = bool(grounded_support) and bool(grounded_counter)

    uncertainty_record = evaluate_uncertainty(records=uncertainty)

    grounded_opinion_stated = has_basis
    disagreement_explicit = (
        has_basis
        and assessment_norm == "user_interpretation_unlikely"
        and len(grounded_counter) >= len(grounded_support)
    )
    real_concern_acknowledged = (
        has_basis
        and assessment_norm == "concern_material"
        and len(grounded_support) >= len(grounded_counter)
    )
    uncertainty_preserved = balanced or bool(
        uncertainty_record["uncertainties"]
    ) or assessment_norm == "balanced"

    basis = "insufficient" if not has_basis else ("balanced" if balanced else "grounded")

    return normalize_json_value(
        {
            "grounded_opinion_stated": grounded_opinion_stated,
            "basis": basis,
            "disagreement_explicit": disagreement_explicit,
            "real_concern_acknowledged": real_concern_acknowledged,
            "uncertainty_preserved": uncertainty_preserved,
            "forced_conclusion": False,
            "forced_neutrality": False,
            "harsh": False,
            "experience_dismissed": False,
            "unsupported_certainty_added": False,
            "malformed_input": malformed,
        }
    )


def evaluate_immediate_risk_escalation(
    *,
    risk_state=None,
    specialized_domain_result=None,
) -> dict:
    """Route credible immediate risk through existing shared/specialized
    contracts; ordinary distress is never silently escalated (frozen §29).

    Concerns creates no own emergency protocol; escalation provenance is the
    authorized specialized result, never emotional intensity.
    """
    state = risk_state if isinstance(risk_state, Mapping) else {}
    described = _semantic_text(state.get("described_signal"))

    credible_signal = bool(
        described
        and any(marker in described for marker in _IMMEDIATE_RISK_SIGNALS if marker)
    )

    specialized_domain_id = None
    specialized_flags: tuple[str, ...] = ()
    specialized_authorized = False
    if isinstance(specialized_domain_result, Mapping):
        specialized_domain_id = _usable_scalar_string(
            specialized_domain_result.get("domain_id")
        )
        specialized_authorized = _grants_authorization(
            specialized_domain_result.get("authorized")
        )
        flags, flags_malformed = _normalize_collection(
            specialized_domain_result.get("red_flags")
        )
        if not flags_malformed:
            specialized_flags = tuple(
                flag
                for flag in (_usable_scalar_string(flag) for flag in flags)
                if flag is not None
            )

    escalate_via_specialized = (
        credible_signal and specialized_authorized and bool(specialized_flags)
    )
    escalate = escalate_via_specialized
    return normalize_json_value(
        {
            "escalate": escalate,
            "credible_signal": credible_signal,
            "routed_to_domain": specialized_domain_id if escalate else None,
            "escalation_source": (
                "specialized_domain_result" if escalate else None
            ),
            "own_protocol_created": False,
            "emotion_triggered_escalation": False,
            "ordinary_distress_not_escalated": not escalate,
            "malformed_input": risk_state is not None
            and not isinstance(risk_state, Mapping),
        }
    )


def _match_support_need(text: str | None) -> str | None:
    """Match a free-text request/signal against the closed request vocabulary.

    Deterministic first-match over a fixed phrase table; no classifier and no
    probabilistic scoring.  Returns a canonical support-need value or ``None``.
    """
    norm = _semantic_text(text)
    if not norm:
        return None
    for phrases, support in _EXPLICIT_REQUEST_SIGNALS:
        for phrase in phrases:
            if _semantic_text(phrase) and _semantic_text(phrase) in norm:
                return support
    return None


def _match_support_needs(text: Any) -> tuple[str, ...]:
    """Return every canonical support need expressed inside ``text``.

    Splits on clause separators so one message can legitimately express more
    than one need ("tell me what you think, then help me pick a step").
    Deterministic; order follows the fixed phrase table.
    """
    raw = _semantic_text(text)
    if not raw:
        return ()
    import re

    clauses = [
        clause
        for clause in re.split(r"[,.;!?]+|\band then\b|\by tambien\b|\bluego\b", raw)
        if clause.strip()
    ]
    clauses = clauses or [raw]
    matched: list[str] = []
    seen: set[str] = set()
    # Deterministic scan: for every clause, first matching phrase group wins.
    for clause in clauses:
        for phrases, support in _EXPLICIT_REQUEST_SIGNALS:
            hit = False
            for phrase in phrases:
                normalized = _semantic_text(phrase)
                if normalized and normalized in clause:
                    hit = True
                    break
            if hit and support not in seen:
                seen.add(support)
                matched.append(support)
            if hit:
                break
    return tuple(matched)


def infer_support_need(
    *,
    explicit_request=None,
    current_signal=None,
    session_context=None,
    historical_preference=None,
) -> dict:
    """Resolve the current conversational support need with strict precedence.

    Priority (frozen design §12):

        explicit current request > clear current signal >
        recent session context > historical preference > UNCLEAR

    Resolution is tiered: once a usable higher-precedence tier is found,
    lower tiers may NOT add components.  ``MIXED`` is allowed only when the
    HIGHEST-precedence source itself clearly expresses multiple concurrent
    needs.  Historical preference never overrides an explicit current request.
    The result is a revisable conversational hypothesis, never a diagnosis,
    personality trait, or durable identity.
    """

    def _classify(value: Any) -> str | None:
        if isinstance(value, Mapping):
            # A mapping may carry either a canonical marker or free text.
            for key in ("support_need", "requested_support"):
                marker = _usable_scalar_string(value.get(key))
                if marker in CANONICAL_SUPPORT_NEEDS:
                    return marker
            for key in ("text", "request", "signal", "statement"):
                matched = _match_support_need(value.get(key))
                if matched is not None:
                    return matched
            return None
        matched = _match_support_need(value)
        if matched is not None:
            return matched
        marker = _usable_scalar_string(value)
        if marker in CANONICAL_SUPPORT_NEEDS:
            return marker
        return None

    def _classify_all(value: Any) -> tuple[str, ...]:
        if isinstance(value, Mapping):
            for key in ("support_need", "requested_support"):
                marker = _usable_scalar_string(value.get(key))
                if marker in CANONICAL_SUPPORT_NEEDS:
                    return (marker,)
            for key in ("text", "request", "signal", "statement"):
                matched = _match_support_needs(value.get(key))
                if matched:
                    return matched
            return ()
        matched = _match_support_needs(value)
        if matched:
            return matched
        marker = _usable_scalar_string(value)
        if marker in CANONICAL_SUPPORT_NEEDS:
            return (marker,)
        return ()

    def _without_mixed(needs: tuple[str, ...]) -> tuple[str, ...]:
        return tuple(need for need in needs if need != SUPPORT_MIXED)

    # ── Tier 1: explicit current request ──────────────────────────────────
    explicit_components = _without_mixed(_classify_all(explicit_request))
    if explicit_components:
        unique: list[str] = []
        for component in explicit_components:
            if component not in unique:
                unique.append(component)
        support_need = (
            SUPPORT_MIXED if len(unique) > 1 else unique[0]
        )
        basis = "explicit_current_request"
        return normalize_json_value(
            {
                "support_need": support_need,
                "basis": basis,
                "components": tuple(unique),
                "explicit": True,
                "inferred": False,
                "invented_classification": False,
                "problem_solving_allowed": support_need in (
                    SUPPORT_PROBLEM_SOLVING,
                    SUPPORT_NEXT_STEP,
                    SUPPORT_DECISION_SUPPORT,
                    SUPPORT_MIXED,
                ),
                "diagnosis": False,
                "personality_trait": False,
                "durable_identity": False,
                "revisable": True,
            }
        )

    # ── Tier 2: clear current conversational signal ───────────────────────
    signal_components = _without_mixed(_classify_all(current_signal))
    if signal_components:
        unique: list[str] = []
        for component in signal_components:
            if component not in unique:
                unique.append(component)
        support_need = (
            SUPPORT_MIXED if len(unique) > 1 else unique[0]
        )
        return normalize_json_value(
            {
                "support_need": support_need,
                "basis": "clear_current_signal",
                "components": tuple(unique),
                "explicit": False,
                "inferred": True,
                "invented_classification": False,
                "problem_solving_allowed": support_need in (
                    SUPPORT_PROBLEM_SOLVING,
                    SUPPORT_NEXT_STEP,
                    SUPPORT_DECISION_SUPPORT,
                    SUPPORT_MIXED,
                ),
                "diagnosis": False,
                "personality_trait": False,
                "durable_identity": False,
                "revisable": True,
            }
        )

    # ── Tier 3: recent session context ────────────────────────────────────
    context_need: str | None = None
    if isinstance(session_context, Mapping):
        for key in _SESSION_CONTEXT_KEYS:
            context_need = _classify(session_context.get(key))
            if context_need is not None and context_need != SUPPORT_MIXED:
                break
    if context_need is not None:
        return normalize_json_value(
            {
                "support_need": context_need,
                "basis": "recent_session_context",
                "components": (context_need,),
                "explicit": False,
                "inferred": True,
                "invented_classification": False,
                "problem_solving_allowed": context_need in (
                    SUPPORT_PROBLEM_SOLVING,
                    SUPPORT_NEXT_STEP,
                    SUPPORT_DECISION_SUPPORT,
                ),
                "diagnosis": False,
                "personality_trait": False,
                "durable_identity": False,
                "revisable": True,
            }
        )

    # ── Tier 4: historical preference ─────────────────────────────────────
    historical: str | None = None
    if isinstance(historical_preference, Mapping):
        for key in _HISTORICAL_KEYS:
            historical = _usable_scalar_string(historical_preference.get(key))
    else:
        historical = _usable_scalar_string(historical_preference)

    if historical in CANONICAL_SUPPORT_NEEDS and historical != SUPPORT_MIXED:
        return normalize_json_value(
            {
                "support_need": historical,
                "basis": "historical_preference",
                "components": (historical,),
                "explicit": False,
                "inferred": True,
                "invented_classification": False,
                "problem_solving_allowed": historical in (
                    SUPPORT_PROBLEM_SOLVING,
                    SUPPORT_NEXT_STEP,
                    SUPPORT_DECISION_SUPPORT,
                ),
                "diagnosis": False,
                "personality_trait": False,
                "durable_identity": False,
                "revisable": True,
            }
        )

    # ── Tier 5: UNCLEAR / default ─────────────────────────────────────────
    return normalize_json_value(
        {
            "support_need": SUPPORT_UNCLEAR,
            "basis": "no_usable_signal",
            "components": (),
            "explicit": False,
            "inferred": False,
            "invented_classification": False,
            "problem_solving_allowed": False,
            "diagnosis": False,
            "personality_trait": False,
            "durable_identity": False,
            "revisable": True,
        }
    )


_UNDERSTANDING_REQUIRED_FIELDS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("situation", ("situation", "statement", "situation_summary")),
    ("trigger", ("trigger", "activating_event")),
)


def _first_usable(material: Mapping, *keys: str) -> Any:
    for key in keys:
        value = material.get(key)
        usable = _usable_scalar_string(value)
        if usable is not None:
            return value
    return None


def understand_concern(material) -> dict:
    """Construct the minimal coherent representation of what troubles the user.

    Canonical behavior (frozen design §16):

        enough context for useful response -> respond
        material missing context           -> ask targeted question
        minor missing context              -> respond with qualification

    Never automatically produces advice, a coping plan or an action plan.
    """
    raw_material = material if isinstance(material, Mapping) else {}
    malformed_material = not isinstance(material, Mapping)

    situation = _first_usable(raw_material, *_UNDERSTANDING_REQUIRED_FIELDS[0][1])
    trigger = _first_usable(raw_material, *_UNDERSTANDING_REQUIRED_FIELDS[1][1])
    matters = _first_usable(raw_material, "what_matters", "feared_meaning", "core_issue")
    statement = _first_usable(raw_material, "statement")
    session_context = raw_material.get("session_context")
    explicit_request = raw_material.get("explicit_request")

    has_core = situation is not None or statement is not None
    understood = has_core and (
        matters is not None or _usable_scalar_string(trigger) is not None
    )

    resolved_from_session = False
    core_issue: str | None = _usable_scalar_string(matters)
    if core_issue is None and isinstance(session_context, Mapping):
        active_topic = _usable_scalar_string(session_context.get("active_topic"))
        if active_topic is not None:
            core_issue = active_topic
            resolved_from_session = True
            understood = understood or has_core

    support = infer_support_need(
        explicit_request=explicit_request,
        session_context=session_context if isinstance(session_context, Mapping) else None,
    )

    questions: list[dict] = []
    ask_question = False
    respond_with_qualification = False
    if not understood and has_core:
        ask_question = True
        questions.append(
            {
                "question": "What specifically about this is worrying you?",
                "materiality": QUESTION_MATERIAL,
                "reason": "changes_interpretation",
            }
        )
    elif understood and not resolved_from_session:
        # A minor gap (e.g. a missing trigger detail): qualify rather than
        # interrogate.
        respond_with_qualification = True

    ready_for_substantive_response = understood and support["support_need"] != SUPPORT_UNCLEAR
    return normalize_json_value(
        {
            "understood": understood,
            "core_issue": core_issue,
            "situation": _usable_scalar_string(situation),
            "trigger": _usable_scalar_string(trigger),
            "resolved_from_session_context": resolved_from_session,
            "missing_material_context": ()
            if understood
            else (("feared_meaning_or_trigger",),)[0],
            "ask_question": ask_question,
            "questions": tuple(questions),
            "respond_with_qualification": respond_with_qualification,
            "ready_for_substantive_response": ready_for_substantive_response,
            "support_need": support["support_need"],
            "mandatory_action_plan": False,
            "advice_generated": False,
            "malformed_input": malformed_material,
        }
    )


def map_lived_experience(material) -> dict:
    """Represent how the concern is affecting the user (frozen design §36).

    Emotion stays valid lived experience without becoming external fact;
    interpretation stays interpretation; fear stays fear and never becomes a
    prediction.  No diagnosis and no stable-identity inference.  Partial
    population is valid: missing fields are not failures.
    """
    raw = material if isinstance(material, Mapping) else {}
    malformed = not isinstance(material, Mapping)

    emotions: list[dict] = []
    fears: list[dict] = []
    interpretations: list[dict] = []
    needs: list[dict] = []

    for bucket, target in (
        ("emotion_statements", emotions),
        ("emotions", emotions),
        ("fear_statements", fears),
        ("fears", fears),
        ("interpretation_statements", interpretations),
        ("interpretations", interpretations),
        ("need_statements", needs),
        ("needs", needs),
    ):
        items, item_malformed = _normalize_collection(raw.get(bucket))
        if item_malformed:
            malformed = True
            continue
        for item in items:
            content = _usable_scalar_string(item) if not isinstance(item, Mapping) else _usable_scalar_string(item.get("content")) or _usable_scalar_string(item.get("statement"))
            if content is None:
                continue
            record = {
                "content": content,
                "source": (
                    _usable_scalar_string(item.get("source"))
                    if isinstance(item, Mapping)
                    else None
                ),
            }
            target.append(record)

    desired_outcome = _usable_scalar_string(raw.get("desired_outcome"))
    perceived_meaning = _usable_scalar_string(raw.get("perceived_meaning"))

    return normalize_json_value(
        {
            "emotions": tuple(
                {**emotion, "experience_valid": True, "external_fact": False}
                for emotion in emotions
            ),
            "fears": tuple(
                {**fear, "prediction": False, "fact": False} for fear in fears
            ),
            "interpretations": tuple(
                {**item, "promoted_to_fact": False} for item in interpretations
            ),
            "needs": tuple(needs),
            "desired_outcome": desired_outcome,
            "perceived_meaning": perceived_meaning,
            "complete": bool(emotions or fears or interpretations or needs),
            "failure": False,
            "diagnosis": False,
            "stable_identity_inference": False,
            "persisted": False,
            "malformed_input": malformed,
        }
    )


def evaluate_question_materiality(*, question=None, changes=()) -> dict:
    """Decide whether asking ``question`` is justified (frozen design §20).

    A question is materially required only if its answer can change meaning,
    risk, reassurance, interpretation, domain routing, decision, or next step.
    Malformed truthy primitives never mean 'material question'.
    """
    question_text = _usable_scalar_string(question)

    recognized: set[str] = set()
    changes_malformed = False
    if isinstance(changes, str):
        normalized = _semantic_text(changes)
        alias = _DIMENSION_ALIASES.get(normalized or "")
        if alias is not None:
            recognized.add(alias)
        elif normalized:
            changes_malformed = True
    elif isinstance(changes, (list, tuple)):
        for change in changes:
            normalized = _semantic_text(change)
            if normalized is None:
                # Non-string members (bool/int/float/mapping/objects) are
                # malformed and never widen into a material question.
                changes_malformed = True
                continue
            alias = _DIMENSION_ALIASES.get(normalized)
            if alias is not None:
                recognized.add(alias)
            else:
                # Unknown free-text labels carry no semantic weight; they do
                # not count toward materiality but do not poison the input.
                continue
    elif changes is not None:
        # Non-collection non-string values (bool, int, float, mapping, objects)
        # are malformed input and never widen into a material question.
        changes_malformed = True

    material = (
        question_text is not None
        and len(recognized) > 0
        and not changes_malformed
    )
    return normalize_json_value(
        {
            "question": question_text,
            "materiality": QUESTION_MATERIAL if material else QUESTION_NOT_MATERIAL,
            "recognized_changes": tuple(sorted(recognized)),
            "changes_malformed": changes_malformed,
            "ritual_question": not material,
        }
    )


# ═════════════════════════════════════════════════════════════════════════════
# Shared rule scaffolding (Phase 10 pattern)
# ═════════════════════════════════════════════════════════════════════════════


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
        domain_id="domain:concerns",
        category=category,
        status=ReasoningRuleStatus.ENABLED,
        priority=priority,
        risk_level=risk_level,
        deterministic=True,
        description=f"Conservative concern-support rule for {rule_id}.",
        metadata={"phase": "10.25"},
    )


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


def _mapping(metadata: Mapping, key: str) -> Mapping | None:
    value = metadata.get(key)
    return value if isinstance(value, Mapping) else None


def _seq(metadata: Mapping, key: str) -> tuple | None:
    value = metadata.get(key)
    return value if isinstance(value, (list, tuple)) else None


# ═════════════════════════════════════════════════════════════════════════════
# Task 3 rule classes
# ═════════════════════════════════════════════════════════════════════════════


@dataclass(frozen=True, slots=True)
class UnderstandBeforeInterveneRule:
    definition: DomainReasoningRuleDefinition

    def evaluate(self, context: ReasoningRuleContext) -> ReasoningRuleResult:
        material = _mapping(context.metadata, "material")
        if material is None:
            return _result(
                self.definition,
                context,
                ReasoningRuleResultStatus.NOT_APPLICABLE,
                code="RULE_NOT_APPLICABLE",
                message="No concern material supplied.",
            )
        record = understand_concern(material)
        intervention_allowed = record["understood"] and not record["ask_question"]
        finding = ReasoningFinding(
            code=(
                "UNDERSTANDING_SUFFICIENT"
                if intervention_allowed
                else "UNDERSTANDING_INCOMPLETE"
            ),
            message=(
                "Understanding precedes intervention; response readiness "
                "assessed without forcing advice or an action plan."
                if intervention_allowed
                else "Material context is missing; a targeted question precedes "
                "any intervention."
            ),
            severity=ReasoningSeverity.INFO,
            rule_id=self.definition.id,
            domain_id=self.definition.domain_id,
            metadata={
                "intervention_allowed": intervention_allowed,
                "understood": record["understood"],
                "ask_question": record["ask_question"],
                "mandatory_action_plan": record["mandatory_action_plan"],
                "advice_generated": record["advice_generated"],
                "support_need": record["support_need"],
            },
        )
        return _result(
            self.definition,
            context,
            ReasoningRuleResultStatus.APPLIED,
            findings=(finding,),
            code="UNDERSTAND_BEFORE_INTERVENE_EVALUATED",
            message="Understanding-first gate evaluated.",
        )


@dataclass(frozen=True, slots=True)
class EmotionalValidationRule:
    definition: DomainReasoningRuleDefinition

    def evaluate(self, context: ReasoningRuleContext) -> ReasoningRuleResult:
        experience = _mapping(context.metadata, "lived_experience")
        if experience is None:
            return _result(
                self.definition,
                context,
                ReasoningRuleResultStatus.NOT_APPLICABLE,
                code="RULE_NOT_APPLICABLE",
                message="No lived-experience material supplied.",
            )
        record = map_lived_experience(experience)
        validated = bool(record["emotions"] or record["fears"] or record["needs"])
        finding = ReasoningFinding(
            code="EMOTIONAL_VALIDATION_PRESERVED",
            message=(
                "Emotional experience is treated as valid without promoting "
                "an external interpretation to fact."
            ),
            severity=ReasoningSeverity.INFO,
            rule_id=self.definition.id,
            domain_id=self.definition.domain_id,
            metadata={
                "experience_validated": validated,
                "interpretation_promoted_to_fact": any(
                    item["promoted_to_fact"] for item in record["interpretations"]
                ),
                "fear_promoted_to_prediction": any(
                    fear["prediction"] for fear in record["fears"]
                ),
                "emotion_count": len(record["emotions"]),
                "diagnosis": record["diagnosis"],
            },
        )
        return _result(
            self.definition,
            context,
            ReasoningRuleResultStatus.APPLIED,
            findings=(finding,),
            code="EXPERIENCE_VALIDATION_RECORDED",
            message="Experience validated; epistemic boundary held.",
        )


@dataclass(frozen=True, slots=True)
class ExperienceRealitySeparationRule:
    definition: DomainReasoningRuleDefinition

    def evaluate(self, context: ReasoningRuleContext) -> ReasoningRuleResult:
        statements = _seq(context.metadata, "statements")
        if not statements:
            return _result(
                self.definition,
                context,
                ReasoningRuleResultStatus.NOT_APPLICABLE,
                code="RULE_NOT_APPLICABLE",
                message="No concern statements supplied.",
            )
        classified = tuple(
            classify_concern_statement(statement) for statement in statements
        )
        promotions = sum(1 for record in classified if record["promotion_blocked"])
        finding = ReasoningFinding(
            code="EXPERIENCE_REALITY_SEPARATED",
            message=(
                "Facts, experiences, interpretations, fears, hypotheses, "
                "scenarios and uncertainty are kept distinct; caller labels "
                "never bypass grounding."
            ),
            severity=ReasoningSeverity.INFO,
            rule_id=self.definition.id,
            domain_id=self.definition.domain_id,
            metadata={
                "levels": tuple(record["level"] for record in classified),
                "promotions_blocked": promotions,
                "records": classified,
            },
        )
        return _result(
            self.definition,
            context,
            ReasoningRuleResultStatus.APPLIED,
            findings=(finding,),
            code="EPISTEMIC_LEVELS_ASSIGNED",
            message="Epistemic separation applied without promotion.",
        )


@dataclass(frozen=True, slots=True)
class SupportNeedCalibrationRule:
    definition: DomainReasoningRuleDefinition

    def evaluate(self, context: ReasoningRuleContext) -> ReasoningRuleResult:
        record_input = _mapping(context.metadata, "support_need")
        if record_input is None:
            return _result(
                self.definition,
                context,
                ReasoningRuleResultStatus.NOT_APPLICABLE,
                code="RULE_NOT_APPLICABLE",
                message="No support-need inputs supplied.",
            )
        record = infer_support_need(
            explicit_request=record_input.get("explicit_request"),
            current_signal=record_input.get("current_signal"),
            session_context=record_input.get("session_context"),
            historical_preference=record_input.get("historical_preference"),
        )
        finding = ReasoningFinding(
            code="SUPPORT_NEED_CALIBRATED",
            message=(
                f"Support need resolved as {record['support_need']} from "
                f"{record['basis']}; it remains revisable."
            ),
            severity=ReasoningSeverity.INFO,
            rule_id=self.definition.id,
            domain_id=self.definition.domain_id,
            metadata={"record": record},
        )
        return _result(
            self.definition,
            context,
            ReasoningRuleResultStatus.APPLIED,
            findings=(finding,),
            code="SUPPORT_NEED_RESOLVED",
            message="Support need calibrated with strict precedence.",
        )


@dataclass(frozen=True, slots=True)
class ContextualQuestionRule:
    definition: DomainReasoningRuleDefinition

    def evaluate(self, context: ReasoningRuleContext) -> ReasoningRuleResult:
        questions = _seq(context.metadata, "questions")
        if questions is None:
            return _result(
                self.definition,
                context,
                ReasoningRuleResultStatus.NOT_APPLICABLE,
                code="RULE_NOT_APPLICABLE",
                message="No candidate questions supplied.",
            )
        evaluations = [
            evaluate_question_materiality(
                question=question.get("question") if isinstance(question, Mapping) else question,
                changes=question.get("changes", ()) if isinstance(question, Mapping) else (),
            )
            for question in questions
            if isinstance(question, (Mapping, str))
        ]
        material_questions = tuple(
            evaluation
            for evaluation in evaluations
            if evaluation["materiality"] == QUESTION_MATERIAL
        )
        finding = ReasoningFinding(
            code="QUESTIONS_FILTERED_BY_MATERIALITY",
            message=(
                f"{len(material_questions)} of {len(evaluations)} candidate "
                "questions are materially useful; ritual questioning suppressed."
            ),
            severity=ReasoningSeverity.INFO,
            rule_id=self.definition.id,
            domain_id=self.definition.domain_id,
            metadata={
                "candidate_count": len(evaluations),
                "material_count": len(material_questions),
                "evaluations": evaluations,
                "maximum_questions": 3,
            },
        )
        return _result(
            self.definition,
            context,
            ReasoningRuleResultStatus.APPLIED,
            findings=(finding,),
            code="CONTEXTUAL_QUESTIONS_EVALUATED",
            message="Question materiality evaluated.",
        )


@dataclass(frozen=True, slots=True)
class UncertaintyPreservationRule:
    definition: DomainReasoningRuleDefinition

    def evaluate(self, context: ReasoningRuleContext) -> ReasoningRuleResult:
        records = _seq(context.metadata, "uncertainty_records")
        if records is None:
            return _result(
                self.definition,
                context,
                ReasoningRuleResultStatus.NOT_APPLICABLE,
                code="RULE_NOT_APPLICABLE",
                message="No uncertainty records supplied.",
            )
        record = evaluate_uncertainty(records=records)
        finding = ReasoningFinding(
            code="UNCERTAINTY_PRESERVED",
            message=(
                "Unresolved uncertainty is preserved; no invented certainty "
                "for comfort and no invented risk for caution."
            ),
            severity=ReasoningSeverity.INFO,
            rule_id=self.definition.id,
            domain_id=self.definition.domain_id,
            metadata={
                "conflict_present": record["conflict_present"],
                "resolved_by_invention": record["resolved_by_invention"],
                "uncertainties": record["uncertainties"],
                "malformed": record["malformed"],
            },
        )
        return _result(
            self.definition,
            context,
            ReasoningRuleResultStatus.APPLIED,
            findings=(finding,),
            code="UNCERTAINTY_RECORDED",
            message="Uncertainty preserved without forced resolution.",
        )


@dataclass(frozen=True, slots=True)
class EvidenceCalibratedReassuranceRule:
    definition: DomainReasoningRuleDefinition

    def evaluate(self, context: ReasoningRuleContext) -> ReasoningRuleResult:
        inputs = _mapping(context.metadata, "reassurance_inputs")
        if inputs is None:
            return _result(
                self.definition,
                context,
                ReasoningRuleResultStatus.NOT_APPLICABLE,
                code="RULE_NOT_APPLICABLE",
                message="No reassurance inputs supplied.",
            )
        record = evaluate_reassurance(
            evidence=inputs.get("evidence", ()),
            counterevidence=inputs.get("counterevidence", ()),
            uncertainty=inputs.get("uncertainty", ()),
            material_concerns=inputs.get("material_concerns", ()),
            specialized_domain_result=inputs.get("specialized_domain_result"),
        )
        false_check = detect_false_reassurance(
            reassurance_state={"assessment": record["assessment"]},
            material_concerns=(
                record["acknowledged_concerns"] if record["concern_erased"] else ()
            ),
        )
        finding = ReasoningFinding(
            code="REASSURANCE_CALIBRATED",
            message=(
                f"Reassurance assessment {record['assessment']} is "
                "evidence-calibrated; absolute certainty was not manufactured."
            ),
            severity=ReasoningSeverity.INFO,
            rule_id=self.definition.id,
            domain_id=self.definition.domain_id,
            metadata={
                "assessment": record["assessment"],
                "absolute_certainty": record["absolute_certainty"],
                "coexists_with_uncertainty": record[
                    "reassurance_coexists_with_uncertainty"
                ],
                "false_reassurance": false_check["false_reassurance"],
                "duplicate_count": record["duplicate_count"],
                "malformed_count": record["malformed_count"],
            },
        )
        return _result(
            self.definition,
            context,
            ReasoningRuleResultStatus.APPLIED,
            findings=(finding,),
            code="REASSURANCE_EVALUATED",
            message="Reassurance calibrated against evidence.",
        )



@dataclass(frozen=True, slots=True)
class ProportionalRiskRule:
    definition: DomainReasoningRuleDefinition

    def evaluate(self, context: ReasoningRuleContext) -> ReasoningRuleResult:
        inputs = _mapping(context.metadata, "risk_inputs")
        if inputs is None:
            return _result(
                self.definition,
                context,
                ReasoningRuleResultStatus.NOT_APPLICABLE,
                code="RULE_NOT_APPLICABLE",
                message="No risk inputs supplied.",
            )
        record = evaluate_proportional_risk(
            evidence=inputs.get("evidence", ()),
            severity=inputs.get("severity"),
            immediacy=inputs.get("immediacy"),
            specialized_domain_result=inputs.get("specialized_domain_result"),
        )
        finding = ReasoningFinding(
            code="RISK_PROPORTIONAL",
            message=(
                "Risk is proportional to grounded evidence; emotional "
                "intensity alone did not elevate it and specialized red flags "
                "were preserved."
            ),
            severity=(
                ReasoningSeverity.WARNING
                if record["risk_level"] == _RISK_HIGH
                else ReasoningSeverity.INFO
            ),
            rule_id=self.definition.id,
            domain_id=self.definition.domain_id,
            metadata={
                "risk_level": record["risk_level"],
                "emotion_drove_risk": record["emotion_drove_risk"],
                "downgraded": record["downgraded"],
                "specialized_ownership_preserved": record[
                    "specialized_ownership_preserved"
                ],
            },
        )
        return _result(
            self.definition,
            context,
            ReasoningRuleResultStatus.APPLIED,
            findings=(finding,),
            code="RISK_CALIBRATED",
            message="Proportional risk evaluated.",
        )


@dataclass(frozen=True, slots=True)
class NoCatastrophicEscalationRule:
    definition: DomainReasoningRuleDefinition

    def evaluate(self, context: ReasoningRuleContext) -> ReasoningRuleResult:
        transitions = _seq(context.metadata, "transitions")
        caveats = _seq(context.metadata, "caveats")
        if not transitions and not caveats:
            return _result(
                self.definition,
                context,
                ReasoningRuleResultStatus.NOT_APPLICABLE,
                code="RULE_NOT_APPLICABLE",
                message="No semantic transitions or caveats supplied.",
            )
        results = ()
        blocked = ()
        if transitions:
            results = tuple(
                detect_catastrophic_escalation(
                    source_state=(
                        transition.get("source_state")
                        if isinstance(transition, Mapping)
                        else {"kind": transition.get("source_kind") or transition.get("source")}
                        if isinstance(transition, Mapping)
                        else None
                    ),
                    proposed_state=(
                        transition.get("proposed_state")
                        if isinstance(transition, Mapping)
                        else {"kind": transition.get("proposed_kind") or transition.get("proposed")}
                        if isinstance(transition, Mapping)
                        else None
                    ),
                )
                for transition in transitions
            )
            blocked = tuple(result["promotion"] for result in results if result["blocked"])

        caveat_record = None
        if caveats:
            caveat_record = evaluate_caveat_policy(caveats=caveats)

        any_blocked = bool(blocked)
        finding_metadata: dict[str, Any] = {
            "blocked_promotions": blocked,
            "results": results,
        }
        if caveat_record is not None:
            finding_metadata["retained_caveats"] = caveat_record["retained"]
            finding_metadata["suppressed_caveats_count"] = caveat_record["suppressed_count"]
            finding_metadata["remote_possibilities_not_stacked"] = caveat_record["remote_possibilities_not_stacked"]

        finding = ReasoningFinding(
            code=(
                "CATASTROPHIC_ESCALATION_BLOCKED"
                if any_blocked
                else "NO_CATASTROPHIC_PROMOTION"
            ),
            message=(
                "Unsupported catastrophic promotion detected and blocked."
                if any_blocked
                else "No unsupported catastrophic promotion found; caveat policy enforced."
            ),
            severity=ReasoningSeverity.WARNING if any_blocked else ReasoningSeverity.INFO,
            rule_id=self.definition.id,
            domain_id=self.definition.domain_id,
            metadata=finding_metadata,
        )
        return _result(
            self.definition,
            context,
            (
                ReasoningRuleResultStatus.BLOCKED
                if any_blocked
                else ReasoningRuleResultStatus.APPLIED
            ),
            findings=(finding,),
            code="CATASTROPHIC_ESCALATION_EVALUATED",
            message="Catastrophic escalation and caveat policy evaluated.",
        )


@dataclass(frozen=True, slots=True)
class NoFalseReassuranceRule:
    definition: DomainReasoningRuleDefinition

    def evaluate(self, context: ReasoningRuleContext) -> ReasoningRuleResult:
        state = _mapping(context.metadata, "reassurance_state")
        concerns = _seq(context.metadata, "material_concerns") or ()
        if state is None and not concerns:
            return _result(
                self.definition,
                context,
                ReasoningRuleResultStatus.NOT_APPLICABLE,
                code="RULE_NOT_APPLICABLE",
                message="No reassurance-state or material concerns supplied.",
            )
        record = detect_false_reassurance(
            reassurance_state=state or {},
            material_concerns=concerns,
        )
        finding = ReasoningFinding(
            code=(
                "FALSE_REASSURANCE_BLOCKED"
                if record["false_reassurance"]
                else "REASSURANCE_HONEST"
            ),
            message=(
                "Reassurance minimized a material concern or claimed absolute "
                "certainty; corrected."
                if record["false_reassurance"]
                else "Reassurance is honest; real warning signals were not erased."
            ),
            severity=(
                ReasoningSeverity.WARNING
                if record["false_reassurance"]
                else ReasoningSeverity.INFO
            ),
            rule_id=self.definition.id,
            domain_id=self.definition.domain_id,
            metadata={
                "false_reassurance": record["false_reassurance"],
                "corrected_assessment": record["corrected_assessment"],
                "reason": record["reason"],
            },
        )
        return _result(
            self.definition,
            context,
            (
                ReasoningRuleResultStatus.BLOCKED
                if record["false_reassurance"]
                else ReasoningRuleResultStatus.APPLIED
            ),
            findings=(finding,),
            code="FALSE_REASSURANCE_EVALUATED",
            message="False-reassurance gate evaluated.",
        )


@dataclass(frozen=True, slots=True)
class RepetitionWithoutPathologizingRule:
    definition: DomainReasoningRuleDefinition

    def evaluate(self, context: ReasoningRuleContext) -> ReasoningRuleResult:
        recurrence = _mapping(context.metadata, "recurrence")
        if recurrence is None:
            return _result(
                self.definition,
                context,
                ReasoningRuleResultStatus.NOT_APPLICABLE,
                code="RULE_NOT_APPLICABLE",
                message="No recurrence inputs supplied.",
            )
        record = review_recurring_concern_state(
            current=recurrence.get("current"),
            previous=recurrence.get("previous", ()),
        )
        pattern = evaluate_repetitive_certainty_pattern(
            turns=recurrence.get("turns", ())
        )
        finding = ReasoningFinding(
            code="RECURRENCE_REVIEWED_WITHOUT_PATHOLOGY",
            message=(
                "Returning to the same concern is not pathology; reassurance "
                "remains allowed and unchanged evidence/uncertainty stay visible."
            ),
            severity=ReasoningSeverity.INFO,
            rule_id=self.definition.id,
            domain_id=self.definition.domain_id,
            metadata={
                "recurrence": record["recurrence"],
                "evidence_changed": record["evidence_changed"],
                "meaningfully_different": record["meaningfully_different"],
                "reassurance_allowed": record["reassurance_allowed"],
                "pathology_inferred": (
                    record["pathology_inferred"] or pattern["pathology_inferred"]
                ),
                "pattern_detected": pattern["pattern_detected"],
                "psychiatric_label": pattern["psychiatric_label"],
            },
        )
        return _result(
            self.definition,
            context,
            ReasoningRuleResultStatus.APPLIED,
            findings=(finding,),
            code="RECURRENCE_EVALUATED",
            message="Recurrence reviewed without pathologizing.",
        )


@dataclass(frozen=True, slots=True)
class AgencyWithoutPressureRule:
    definition: DomainReasoningRuleDefinition

    def evaluate(self, context: ReasoningRuleContext) -> ReasoningRuleResult:
        action = _mapping(context.metadata, "action")
        if action is None:
            return _result(
                self.definition,
                context,
                ReasoningRuleResultStatus.NOT_APPLICABLE,
                code="RULE_NOT_APPLICABLE",
                message="No action-state inputs supplied.",
            )
        record = evaluate_action_state(
            options=action.get("options", ()),
            urgency=action.get("urgency"),
            user_request=action.get("user_request"),
            grounded_options=bool(action.get("grounded_options")),
            specialized_recommendation=bool(action.get("specialized_recommendation")),
            specialized_domain_result=action.get("specialized_domain_result"),
        )
        finding = ReasoningFinding(
            code="ACTION_STATE_RESOLVED_WITHOUT_PRESSURE",
            message=(
                "Action state resolved; option != recommendation != adopted "
                "decision != authorized execution."
            ),
            severity=ReasoningSeverity.INFO,
            rule_id=self.definition.id,
            domain_id=self.definition.domain_id,
            metadata={
                "state": record["state"],
                "record": record,
                "action_forced": False,
                "external_action_executed": False,
            },
        )
        return _result(
            self.definition,
            context,
            ReasoningRuleResultStatus.APPLIED,
            findings=(finding,),
            code="AGENCY_PRESERVED",
            message="Agency preserved without forced action.",
        )


@dataclass(frozen=True, slots=True)
class DirectnessWithoutHarshnessRule:
    definition: DomainReasoningRuleDefinition

    def evaluate(self, context: ReasoningRuleContext) -> ReasoningRuleResult:
        directness = _mapping(context.metadata, "directness")
        if directness is None:
            return _result(
                self.definition,
                context,
                ReasoningRuleResultStatus.NOT_APPLICABLE,
                code="RULE_NOT_APPLICABLE",
                message="No directness inputs supplied.",
            )
        record = evaluate_grounded_directness(
            assessment=directness.get("assessment"),
            evidence=directness.get("evidence", ()),
            uncertainty=directness.get("uncertainty", ()),
        )
        finding = ReasoningFinding(
            code="GROUNDED_DIRECTNESS_ASSESSED",
            message=(
                "A grounded opinion may be stated with an explicit basis; "
                "empathy does not require agreement and directness is never "
                "harshness."
            ),
            severity=ReasoningSeverity.INFO,
            rule_id=self.definition.id,
            domain_id=self.definition.domain_id,
            metadata={
                "record": record,
                "harsh": record["harsh"],
                "disagreement_explicit": record["disagreement_explicit"],
                "grounded_opinion_stated": record["grounded_opinion_stated"],
                "uncertainty_preserved": record["uncertainty_preserved"],
            },
        )
        return _result(
            self.definition,
            context,
            ReasoningRuleResultStatus.APPLIED,
            findings=(finding,),
            code="DIRECTNESS_EVALUATED",
            message="Grounded directness evaluated.",
        )


@dataclass(frozen=True, slots=True)
class ImmediateRiskEscalationRule:
    definition: DomainReasoningRuleDefinition

    def evaluate(self, context: ReasoningRuleContext) -> ReasoningRuleResult:
        escalation = _mapping(context.metadata, "escalation")
        if escalation is None:
            return _result(
                self.definition,
                context,
                ReasoningRuleResultStatus.NOT_APPLICABLE,
                code="RULE_NOT_APPLICABLE",
                message="No escalation inputs supplied.",
            )
        record = evaluate_immediate_risk_escalation(
            risk_state=escalation.get("risk_state"),
            specialized_domain_result=escalation.get("specialized_domain_result"),
        )
        finding = ReasoningFinding(
            code=(
                "IMMEDIATE_RISK_ESCALATED"
                if record["escalate"]
                else "NO_IMMEDIATE_ESCALATION"
            ),
            message=(
                "Credible immediate risk routed through the authorized "
                "specialized contract; no own protocol was created."
                if record["escalate"]
                else "Ordinary distress or unverified claims are not escalated."
            ),
            severity=(
                ReasoningSeverity.WARNING
                if record["escalate"]
                else ReasoningSeverity.INFO
            ),
            rule_id=self.definition.id,
            domain_id=self.definition.domain_id,
            metadata={
                "escalate": record["escalate"],
                "routed_to_domain": record["routed_to_domain"],
                "own_protocol_created": record["own_protocol_created"],
                "emotion_triggered_escalation": record[
                    "emotion_triggered_escalation"
                ],
            },
        )
        return _result(
            self.definition,
            context,
            ReasoningRuleResultStatus.APPLIED,
            findings=(finding,),
            code="IMMEDIATE_RISK_EVALUATED",
            message="Immediate-risk boundary evaluated.",
        )


def build_concerns_rules() -> tuple[Any, ...]:
    """Build the fourteen Concerns Domain rules deterministically in catalog order."""
    by_id = {
        "concerns.agency_without_pressure": AgencyWithoutPressureRule(
            definition=_definition(
                "concerns.agency_without_pressure",
                "AgencyWithoutPressureRule",
                ReasoningRuleCategory.INFERENCE.value,
                750,
            )
        ),
        "concerns.contextual_question": ContextualQuestionRule(
            definition=_definition(
                "concerns.contextual_question",
                "ContextualQuestionRule",
                ReasoningRuleCategory.INFERENCE.value,
                740,
            )
        ),
        "concerns.directness_without_harshness": DirectnessWithoutHarshnessRule(
            definition=_definition(
                "concerns.directness_without_harshness",
                "DirectnessWithoutHarshnessRule",
                ReasoningRuleCategory.INFERENCE.value,
                745,
            )
        ),
        "concerns.emotional_validation": EmotionalValidationRule(
            definition=_definition(
                "concerns.emotional_validation",
                "EmotionalValidationRule",
                ReasoningRuleCategory.EPISTEMIC.value,
                720,
            )
        ),
        "concerns.evidence_calibrated_reassurance": EvidenceCalibratedReassuranceRule(
            definition=_definition(
                "concerns.evidence_calibrated_reassurance",
                "EvidenceCalibratedReassuranceRule",
                ReasoningRuleCategory.EPISTEMIC.value,
                700,
            )
        ),
        "concerns.experience_reality_separation": ExperienceRealitySeparationRule(
            definition=_definition(
                "concerns.experience_reality_separation",
                "ExperienceRealitySeparationRule",
                ReasoningRuleCategory.EPISTEMIC.value,
                710,
            )
        ),
        "concerns.immediate_risk_escalation": ImmediateRiskEscalationRule(
            definition=_definition(
                "concerns.immediate_risk_escalation",
                "ImmediateRiskEscalationRule",
                ReasoningRuleCategory.SAFETY.value,
                820,
                risk_level=ReasoningRiskLevel.HIGH,
            )
        ),
        "concerns.no_catastrophic_escalation": NoCatastrophicEscalationRule(
            definition=_definition(
                "concerns.no_catastrophic_escalation",
                "NoCatastrophicEscalationRule",
                ReasoningRuleCategory.SAFETY.value,
                800,
                risk_level=ReasoningRiskLevel.MEDIUM,
            )
        ),
        "concerns.no_false_reassurance": NoFalseReassuranceRule(
            definition=_definition(
                "concerns.no_false_reassurance",
                "NoFalseReassuranceRule",
                ReasoningRuleCategory.SAFETY.value,
                790,
                risk_level=ReasoningRiskLevel.MEDIUM,
            )
        ),
        "concerns.proportional_risk": ProportionalRiskRule(
            definition=_definition(
                "concerns.proportional_risk",
                "ProportionalRiskRule",
                ReasoningRuleCategory.SAFETY.value,
                780,
                risk_level=ReasoningRiskLevel.MEDIUM,
            )
        ),
        "concerns.repetition_without_pathologizing": RepetitionWithoutPathologizingRule(
            definition=_definition(
                "concerns.repetition_without_pathologizing",
                "RepetitionWithoutPathologizingRule",
                ReasoningRuleCategory.SAFETY.value,
                810,
                risk_level=ReasoningRiskLevel.MEDIUM,
            )
        ),
        "concerns.support_need_calibration": SupportNeedCalibrationRule(
            definition=_definition(
                "concerns.support_need_calibration",
                "SupportNeedCalibrationRule",
                ReasoningRuleCategory.INFERENCE.value,
                730,
            )
        ),
        "concerns.understand_before_intervene": UnderstandBeforeInterveneRule(
            definition=_definition(
                "concerns.understand_before_intervene",
                "UnderstandBeforeInterveneRule",
                ReasoningRuleCategory.EPISTEMIC.value,
                690,
            )
        ),
        "concerns.uncertainty_preservation": UncertaintyPreservationRule(
            definition=_definition(
                "concerns.uncertainty_preservation",
                "UncertaintyPreservationRule",
                ReasoningRuleCategory.EPISTEMIC.value,
                705,
            )
        ),
    }
    return tuple(by_id[rule_id] for rule_id in CONCERNS_RULE_IDS)
