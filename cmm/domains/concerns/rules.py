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
                "sin consejos",
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


import math


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

    Historical preference never overrides an explicit current request.  The
    result is a revisable conversational hypothesis, never a diagnosis,
    personality trait, or durable identity.
    """
    components: list[str] = []

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

    explicit_components = _classify_all(explicit_request)
    explicit = explicit_components[0] if explicit_components else None
    components.extend(explicit_components)

    signal_components = _classify_all(current_signal)
    signal = signal_components[0] if signal_components else None
    components.extend(signal_components)

    context_need: str | None = None
    if isinstance(session_context, Mapping):
        for key in _SESSION_CONTEXT_KEYS:
            context_need = _classify(session_context.get(key))
            if context_need is not None and context_need != SUPPORT_MIXED:
                components.append(context_need)
                break

    historical: str | None = None
    if isinstance(historical_preference, Mapping):
        for key in _HISTORICAL_KEYS:
            historical = _usable_scalar_string(historical_preference.get(key))
    else:
        historical = _usable_scalar_string(historical_preference)

    unique_components: list[str] = []
    for component in components:
        if component not in unique_components:
            unique_components.append(component)

    if len(unique_components) > 1:
        support_need = SUPPORT_MIXED
        basis = "explicit_current_request"
        if signal is not None and explicit is None:
            basis = "clear_current_signal"
    elif len(unique_components) == 1:
        support_need = unique_components[0]
        if explicit is not None:
            basis = "explicit_current_request"
        elif signal is not None:
            basis = "clear_current_signal"
        elif context_need is not None:
            basis = "recent_session_context"
        else:  # pragma: no cover - defensive
            basis = "default_heuristic"
    elif historical in CANONICAL_SUPPORT_NEEDS and historical != SUPPORT_MIXED:
        support_need = historical
        basis = "historical_preference"
    else:
        support_need = SUPPORT_UNCLEAR
        basis = "no_usable_signal"

    problem_solving_allowed = support_need in (
        SUPPORT_PROBLEM_SOLVING,
        SUPPORT_NEXT_STEP,
        SUPPORT_DECISION_SUPPORT,
        SUPPORT_MIXED,
    )
    return normalize_json_value(
        {
            "support_need": support_need,
            "basis": basis,
            "components": tuple(unique_components),
            "explicit": explicit is not None,
            "inferred": explicit is None and support_need != SUPPORT_UNCLEAR,
            "invented_classification": False,
            "problem_solving_allowed": problem_solving_allowed,
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

    def evaluate(self, context: ReasoningRuleContext) -> ReasoningRuleResult:  # pragma: no cover - implemented in Task 4
        return _result(
            self.definition,
            context,
            ReasoningRuleResultStatus.NOT_APPLICABLE,
            code="RULE_DEFERRED_TO_TASK4",
            message="Implemented with the epistemics helpers (Task 4).",
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

    def evaluate(self, context: ReasoningRuleContext) -> ReasoningRuleResult:  # pragma: no cover - implemented in Task 4
        return _result(
            self.definition,
            context,
            ReasoningRuleResultStatus.NOT_APPLICABLE,
            code="RULE_DEFERRED_TO_TASK4",
            message="Implemented with the uncertainty helper (Task 4).",
        )


@dataclass(frozen=True, slots=True)
class EvidenceCalibratedReassuranceRule:
    definition: DomainReasoningRuleDefinition

    def evaluate(self, context: ReasoningRuleContext) -> ReasoningRuleResult:  # pragma: no cover - implemented in Task 4
        return _result(
            self.definition,
            context,
            ReasoningRuleResultStatus.NOT_APPLICABLE,
            code="RULE_DEFERRED_TO_TASK4",
            message="Implemented with the reassurance helper (Task 4).",
        )


@dataclass(frozen=True, slots=True)
class ProportionalRiskRule:
    definition: DomainReasoningRuleDefinition

    def evaluate(self, context: ReasoningRuleContext) -> ReasoningRuleResult:  # pragma: no cover - implemented in Task 4
        return _result(
            self.definition,
            context,
            ReasoningRuleResultStatus.NOT_APPLICABLE,
            code="RULE_DEFERRED_TO_TASK4",
            message="Implemented with the proportional-risk helper (Task 4).",
        )


@dataclass(frozen=True, slots=True)
class NoCatastrophicEscalationRule:
    definition: DomainReasoningRuleDefinition

    def evaluate(self, context: ReasoningRuleContext) -> ReasoningRuleResult:  # pragma: no cover - implemented in Task 4
        return _result(
            self.definition,
            context,
            ReasoningRuleResultStatus.NOT_APPLICABLE,
            code="RULE_DEFERRED_TO_TASK4",
            message="Implemented with the escalation detector (Task 4).",
        )


@dataclass(frozen=True, slots=True)
class NoFalseReassuranceRule:
    definition: DomainReasoningRuleDefinition

    def evaluate(self, context: ReasoningRuleContext) -> ReasoningRuleResult:  # pragma: no cover - implemented in Task 4
        return _result(
            self.definition,
            context,
            ReasoningRuleResultStatus.NOT_APPLICABLE,
            code="RULE_DEFERRED_TO_TASK4",
            message="Implemented with the false-reassurance detector (Task 4).",
        )


@dataclass(frozen=True, slots=True)
class RepetitionWithoutPathologizingRule:
    definition: DomainReasoningRuleDefinition

    def evaluate(self, context: ReasoningRuleContext) -> ReasoningRuleResult:  # pragma: no cover - implemented in Task 5
        return _result(
            self.definition,
            context,
            ReasoningRuleResultStatus.NOT_APPLICABLE,
            code="RULE_DEFERRED_TO_TASK5",
            message="Implemented with the recurrence helpers (Task 5).",
        )


@dataclass(frozen=True, slots=True)
class AgencyWithoutPressureRule:
    definition: DomainReasoningRuleDefinition

    def evaluate(self, context: ReasoningRuleContext) -> ReasoningRuleResult:  # pragma: no cover - implemented in Task 5
        return _result(
            self.definition,
            context,
            ReasoningRuleResultStatus.NOT_APPLICABLE,
            code="RULE_DEFERRED_TO_TASK5",
            message="Implemented with the action-state helper (Task 5).",
        )


@dataclass(frozen=True, slots=True)
class DirectnessWithoutHarshnessRule:
    definition: DomainReasoningRuleDefinition

    def evaluate(self, context: ReasoningRuleContext) -> ReasoningRuleResult:  # pragma: no cover - implemented in Task 5
        return _result(
            self.definition,
            context,
            ReasoningRuleResultStatus.NOT_APPLICABLE,
            code="RULE_DEFERRED_TO_TASK5",
            message="Implemented with the directness helper (Task 5).",
        )


@dataclass(frozen=True, slots=True)
class ImmediateRiskEscalationRule:
    definition: DomainReasoningRuleDefinition

    def evaluate(self, context: ReasoningRuleContext) -> ReasoningRuleResult:  # pragma: no cover - implemented in Task 5
        return _result(
            self.definition,
            context,
            ReasoningRuleResultStatus.NOT_APPLICABLE,
            code="RULE_DEFERRED_TO_TASK5",
            message="Implemented with the escalation helper (Task 5).",
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
