"""Phase 10.24 — Reflection Domain Operations.

Nine declarative reflection operations built on the shared
``DomainOperationDefinition`` contract.  No implementation is embedded here; an
operation without a provided implementation is registered as **UNAVAILABLE**
(fail-closed).  Each operation exposes a pure, deterministic result builder that
produces its JSON-safe output payload: the semantic core used by workflow
implementations and tests.

Safety posture (spec §20, §23, §42):

- No operation performs an autonomous external action: ``prepare_notion_entry``
  prepares content only (``external_write_performed=False``); ``review_decision``
  analyzes without adopting (``decision_adopted=False``); ``build_personal_timeline``
  never invents dates or mutates shared timeline state.
- ``required_resources`` uses strict AND semantics; an operation only declares a
  resource it structurally consumes.  Missing required resources fail closed.
- Result builders never promote epistemic levels, never present psychological
  hypotheses as diagnoses, and never increase certainty.
"""

from __future__ import annotations

from collections.abc import Mapping

from cmm.agent_runtime.enums import PolicyRiskLevel
from cmm.domains.enums import DomainOperationType
from cmm.domains.operation_contracts import DomainOperationDefinition
from cmm.domains.reflection.catalog import CANONICAL_REFLECTION_OPERATION_IDS
from cmm.domains.reflection.rules import (
    CHRONOLOGY_EMPTY,
    CHRONOLOGY_EQUAL,
    CHRONOLOGY_MALFORMED,
    CHRONOLOGY_ORDERED,
    CHRONOLOGY_UNKNOWN,
    EVIDENCE_GROUNDED,
    EVIDENCE_MALFORMED,
    _normalize_chronology,
    _normalize_collection,
    classify_belief_evidence,
    compare_reflection_versions,
    evaluate_hypotheses,
    evaluate_open_questions,
)

REFLECTION_OPERATION_IDS: tuple[str, ...] = CANONICAL_REFLECTION_OPERATION_IDS

_OPERATION_TYPES = {
    "reflection.structure_reflection": DomainOperationType.ANALYSIS,
    "reflection.extract_beliefs": DomainOperationType.ANALYSIS,
    "reflection.compare_versions": DomainOperationType.ANALYSIS,
    "reflection.identify_open_questions": DomainOperationType.ANALYSIS,
    "reflection.generate_hypotheses": DomainOperationType.ANALYSIS,
    "reflection.build_personal_timeline": DomainOperationType.ANALYSIS,
    "reflection.prepare_notion_entry": DomainOperationType.PREPARATION,
    "reflection.generate_summary": DomainOperationType.ANALYSIS,
    "reflection.review_decision": DomainOperationType.ANALYSIS,
}

# Resources each operation structurally consumes (AND semantics).  Only
# operations that genuinely read a resource declare it here.
_REQUIRED_RESOURCES = {
    "reflection.structure_reflection": ("reflection.user_message",),
    "reflection.extract_beliefs": ("reflection.user_message",),
    "reflection.compare_versions": (
        "reflection.memory_entry",
        "reflection.journal_entry",
    ),
    "reflection.identify_open_questions": ("reflection.conversation",),
    "reflection.generate_hypotheses": ("reflection.user_message",),
    "reflection.build_personal_timeline": (
        "reflection.life_event",
        "reflection.journal_entry",
    ),
    "reflection.prepare_notion_entry": ("reflection.note",),
    "reflection.generate_summary": ("reflection.note",),
    "reflection.review_decision": ("reflection.decision", "reflection.goal"),
}


def _schema(required: tuple[str, ...], properties: dict) -> dict:
    """Build a deterministic JSON object schema with closed properties."""
    return {
        "type": "object",
        "required": list(required),
        "properties": properties,
        "additionalProperties": False,
    }


_ID_ARRAY = {"type": "array", "items": {"type": "string"}}


def _ids(min_items: int) -> dict:
    return {"type": "array", "items": {"type": "string"}, "minItems": min_items}


_INPUT_SCHEMAS = {
    "reflection.structure_reflection": _schema(
        ("material_ids",), {"material_ids": _ids(1)}
    ),
    "reflection.extract_beliefs": _schema(
        ("statements",), {"statements": _ids(1)}
    ),
    "reflection.compare_versions": _schema(
        ("versions",), {"versions": _ids(1)}
    ),
    "reflection.identify_open_questions": _schema(
        ("questions",), {"questions": _ids(1)}
    ),
    "reflection.generate_hypotheses": _schema(
        ("hypotheses",), {"hypotheses": _ids(1)}
    ),
    "reflection.build_personal_timeline": _schema(
        ("events",), {"events": _ids(1)}
    ),
    "reflection.generate_summary": _schema(
        ("source_ids",), {"source_ids": _ids(1)}
    ),
    "reflection.prepare_notion_entry": _schema(
        ("title",), {"title": {"type": "string"}, "note_id": {"type": "string"}}
    ),
    "reflection.review_decision": _schema(
        ("decision_id",), {"decision_id": {"type": "string"}}
    ),
}

_STRUCTURE_SECTION = {"type": "array", "items": {"type": "object"}}

_STRUCTURE_REFLECTION_OUTPUT = _schema(
    ("observations",),
    {
        "observations": _STRUCTURE_SECTION,
        "beliefs": _STRUCTURE_SECTION,
        "values": _STRUCTURE_SECTION,
        "emotions": _STRUCTURE_SECTION,
        "needs": _STRUCTURE_SECTION,
        "conflicts": _STRUCTURE_SECTION,
        "hypotheses": _STRUCTURE_SECTION,
        "uncertainties": _STRUCTURE_SECTION,
        "open_questions": _STRUCTURE_SECTION,
        "persisted": {"type": "boolean"},
    },
)

_EXTRACT_BELIEFS_OUTPUT = _schema(
    ("beliefs",),
    {
        "beliefs": _STRUCTURE_SECTION,
        "facts": _STRUCTURE_SECTION,
        "beliefs_as_facts": _STRUCTURE_SECTION,
    },
)

_COMPARE_VERSIONS_OUTPUT = _schema(
    ("chronology_state",),
    {
        "chronology_state": {"type": "string"},
        "changes": _STRUCTURE_SECTION,
        "input_order_not_chronology": {"type": "boolean"},
    },
)

_OPEN_QUESTIONS_OUTPUT = _schema(
    ("questions",),
    {
        "questions": _STRUCTURE_SECTION,
        "unresolved_count": {"type": "integer"},
        "invented_answers": {"type": "array", "items": {"type": "string"}},
    },
)

_HYPOTHESES_OUTPUT = _schema(
    ("hypotheses",),
    {
        "hypotheses": _STRUCTURE_SECTION,
        "winner_selected": {"type": "boolean"},
        "forced_conclusion": {"type": "boolean"},
        "no_diagnosis": {"type": "boolean"},
    },
)

_TIMELINE_OUTPUT = _schema(
    ("events",),
    {
        "events": _STRUCTURE_SECTION,
        "chronology_state": {"type": "string"},
        "invented_dates": {"type": "array", "items": {"type": "string"}},
        "timeline_mutated": {"type": "boolean"},
    },
)

_NOTION_OUTPUT = _schema(
    ("prepared_content",),
    {
        "prepared_content": {"type": "string"},
        "external_write_performed": {"type": "boolean"},
        "notion_connector_called": {"type": "boolean"},
        "saved_claim": {"type": "boolean"},
    },
)

_SUMMARY_OUTPUT = _schema(
    ("summary",),
    {
        "summary": {"type": "string"},
        "certainty_increased": {"type": "boolean"},
        "unresolved": {"type": "boolean"},
    },
)

_REVIEW_DECISION_OUTPUT = _schema(
    ("analysis",),
    {
        "analysis": {"type": "object"},
        "decision_adopted": {"type": "boolean"},
        "proposal_only": {"type": "boolean"},
        "recommendation": {"type": "string"},
        "adopted_decision": {"type": "boolean"},
    },
)

_OUTPUT_SCHEMAS = {
    "reflection.structure_reflection": _schema(
        ("structure",), {"structure": _STRUCTURE_REFLECTION_OUTPUT}
    ),
    "reflection.extract_beliefs": _schema(
        ("result",), {"result": _EXTRACT_BELIEFS_OUTPUT}
    ),
    "reflection.compare_versions": _schema(
        ("comparison",), {"comparison": _COMPARE_VERSIONS_OUTPUT}
    ),
    "reflection.identify_open_questions": _schema(
        ("questions",), {"questions": _OPEN_QUESTIONS_OUTPUT}
    ),
    "reflection.generate_hypotheses": _schema(
        ("hypotheses",), {"hypotheses": _HYPOTHESES_OUTPUT}
    ),
    "reflection.build_personal_timeline": _schema(
        ("timeline",), {"timeline": _TIMELINE_OUTPUT}
    ),
    "reflection.prepare_notion_entry": _schema(
        ("entry",), {"entry": _NOTION_OUTPUT}
    ),
    "reflection.generate_summary": _schema(
        ("summary",), {"summary": _SUMMARY_OUTPUT}
    ),
    "reflection.review_decision": _schema(
        ("review",), {"review": _REVIEW_DECISION_OUTPUT}
    ),
}

_ALL_PROPOSAL_ONLY = frozenset(
    {
        "reflection.build_personal_timeline",
        "reflection.prepare_notion_entry",
        "reflection.review_decision",
    }
)

_ALL_PREPARATION_ONLY = frozenset({"reflection.prepare_notion_entry"})


def build_reflection_operation_definitions() -> tuple[DomainOperationDefinition, ...]:
    """Build the nine Reflection Domain operation definitions deterministically."""
    result = []
    for operation_id in REFLECTION_OPERATION_IDS:
        operation_type = _OPERATION_TYPES[operation_id]
        operation_name = operation_id.split(".", 1)[1]
        result.append(
            DomainOperationDefinition(
                operation_id=operation_id,
                domain_id="domain:reflection",
                version="1.0.0",
                name=operation_name.replace("_", " ").title(),
                description=f"Conservative structured operation for {operation_id}.",
                operation_type=operation_type,
                input_schema=_INPUT_SCHEMAS[operation_id],
                output_schema=_OUTPUT_SCHEMAS[operation_id],
                required_resources=_REQUIRED_RESOURCES[operation_id],
                required_permissions=(),
                risk_level=PolicyRiskLevel.LOW,
                reversible=False,
                requires_approval=False,
                validation_policy_id=None,
                rollback_policy_id=None,
                enabled=True,
                metadata={
                    "phase": "10.24",
                    "domain": "reflection",
                    "proposal_only": operation_id in _ALL_PROPOSAL_ONLY,
                    "preparation_only": operation_id in _ALL_PREPARATION_ONLY,
                },
            )
        )
    return tuple(result)


# ── Pure result builders (semantic cores, JSON-safe, deterministic) ──────────

def _normalize_flat_records(value):
    """Normalize a collection of mappings into a list of usable records.

    Returns ``(items, malformed)``; malformed members are tracked, never
    silently dropped.
    """
    raw, malformed = _normalize_collection(value, require_mapping_elements=True)
    items = []
    for entry in raw:
        if not isinstance(entry, Mapping):
            malformed = True
            continue
        normalized = {key: item for key, item in entry.items()}
        items.append(normalized)
    return items, malformed


def structure_reflection_result(*, material=()) -> dict:
    """Structure reflective material into canonical sections.

    Material records are partitioned by their epistemic level; nothing is
    silently promoted, nothing is persisted, and absent sections stay absent
    (never invented as empty truth).  Output is JSON-safe.
    """
    level_map = {
        "observation": "observations",
        "belief": "beliefs",
        "value": "values",
        "emotion": "emotions",
        "need": "needs",
        "conflict": "conflicts",
        "hypothesis": "hypotheses",
        "counter_hypothesis": "hypotheses",
        "uncertainty": "uncertainties",
        "open_question": "open_questions",
    }
    raw, malformed = _normalize_flat_records(material)
    sections = {name: [] for name in (
        "observations", "beliefs", "values", "emotions", "needs", "conflicts",
        "hypotheses", "uncertainties", "open_questions",
    )}
    for record in raw:
        level = record.get("level")
        section = level_map.get(level, "observations" if level == "observation" else None)
        if section is None:
            continue
        sections[section].append(
            {
                "identity": record.get("identity", "unknown"),
                "content": record.get("content", ""),
                "source": record.get("source"),
            }
        )
    return {
        "observations": tuple(sections["observations"]),
        "beliefs": tuple(sections["beliefs"]),
        "values": tuple(sections["values"]),
        "emotions": tuple(sections["emotions"]),
        "needs": tuple(sections["needs"]),
        "conflicts": tuple(sections["conflicts"]),
        "hypotheses": tuple(sections["hypotheses"]),
        "uncertainties": tuple(sections["uncertainties"]),
        "open_questions": tuple(sections["open_questions"]),
        "persisted": False,
        "evidence_state": EVIDENCE_MALFORMED if malformed else EVIDENCE_GROUNDED,
    }


def extract_beliefs_result(*, statements=()) -> dict:
    """Extract candidate beliefs preserving explicit/inferred/uncertain/

contradicted state.  No inferred belief becomes a user fact.  Output is
JSON-safe.
    """
    normalized_statements = []
    for entry in statements:
        if isinstance(entry, Mapping):
            record = dict(entry)
            record.setdefault("kind", "belief")
            normalized_statements.append(record)
    classified = classify_belief_evidence(records=normalized_statements)
    return {
        "beliefs": tuple(classified["beliefs"]),
        "facts": (),
        "beliefs_as_facts": (),
        "promotions_blocked": classified["promotions_blocked"],
        "type_promotion": classified["type_promotion"],
        "unresolved": classified["unresolved"],
    }
    """Extract candidate beliefs preserving explicit/inferred/uncertain/

contradicted state.  No inferred belief becomes a user fact.  Output is
JSON-safe.
    """
    classified = classify_belief_evidence(records=statements)
    return {
        "beliefs": tuple(classified["beliefs"]),
        "facts": (),
        "beliefs_as_facts": (),
        "promotions_blocked": classified["promotions_blocked"],
        "type_promotion": classified["type_promotion"],
        "unresolved": classified["unresolved"],
    }


def compare_versions_result(*, versions=()) -> dict:
    """Compare versioned records with grounded chronology only; input order is

never chronology.  Output is JSON-safe.
    """
    record = compare_reflection_versions(versions=versions)
    return {
        "chronology_state": record["chronology_state"],
        "changes": record["changes"],
        "input_order_not_chronology": record["input_order_not_chronology"],
        "temporally_ordered": record["temporally_ordered"],
        "equal_timestamps_no_evolution": record["equal_timestamps_no_evolution"],
    }


def identify_open_questions_result(*, questions=()) -> dict:
    """Return unresolved questions and why each remains unresolved with no

invented answer.  Output is JSON-safe.
    """
    return evaluate_open_questions(questions=questions)


def generate_hypotheses_result(*, hypotheses=()) -> dict:
    """Produce multiple prudent hypotheses; no winner, no diagnosis, no forced

conclusion.  Output is JSON-safe.
    """
    record = evaluate_hypotheses(hypotheses=hypotheses)
    return {
        "hypotheses": record["hypotheses"],
        "winner_selected": record["winner_selected"],
        "forced_conclusion": record["forced_conclusion"],
        "no_diagnosis": True,
        "unresolved": record["unresolved"],
        "insufficient_basis_to_rank": record["insufficient_basis_to_rank"],
    }


def build_personal_timeline_result(*, events=()) -> dict:
    """Build a timeline proposal from grounded events; no invented dates, no

shared timeline mutation.  Events with unusable dates are reported in
``unusable_dates`` and never silently ordered.  Output is JSON-safe.
    """
    raw, malformed = _normalize_flat_records(events)
    timeline = []
    unusable_dates = []
    scalars = []
    for event in raw:
        observed = event.get("observed_at")
        scalar = _normalize_chronology(observed)
        if observed is not None and scalar is None:
            unusable_dates.append(event.get("event_id") or "unknown")
            continue
        scalars.append(scalar)
        timeline.append(
            {
                "event_id": event.get("event_id") or "unknown",
                "observed_at": observed,
                "content": event.get("content", ""),
            }
        )
    if malformed or unusable_dates:
        chronology_state = CHRONOLOGY_MALFORMED
        temporally_ordered = False
    elif not timeline or any(scalar is None for scalar in scalars):
        chronology_state = (
            CHRONOLOGY_UNKNOWN
            if any(scalar is None for scalar in scalars)
            else CHRONOLOGY_EMPTY
        )
        temporally_ordered = False
    elif len(set(scalars)) == 1:
        chronology_state = CHRONOLOGY_EQUAL
        temporally_ordered = False
    else:
        timeline.sort(key=lambda item: item.get("observed_at") or "")
        chronology_state = CHRONOLOGY_ORDERED
        temporally_ordered = True
    return {
        "events": tuple(timeline),
        "chronology_state": chronology_state,
        "temporally_ordered": temporally_ordered,
        "unusable_dates": tuple(unusable_dates),
        "invented_dates": (),
        "timeline_mutated": False,
        "input_order_not_chronology": True,
    }


def prepare_notion_entry_result(*, title, sections=(), raw_notes="") -> dict:
    """Prepare Notion entry *content* only; never performs an external write.

    PREPARATION != EXTERNAL COMMUNICATION: no connector is called, no page is
    created/updated, and no write is claimed.  Output is JSON-safe.
    """
    lines = [f"# {title}"]
    for section in sections:
        lines.append(f"## {section}")
    lines.append("")
    lines.append(raw_notes)
    return {
        "prepared_content": "\n".join(lines),
        "external_write_performed": False,
        "notion_connector_called": False,
        "saved_claim": False,
        "note_id": None,
        "title": title,
    }


def generate_summary_result(*, source, certainty_override=None) -> dict:
    """Summarize a structured reflection without increasing certainty.

    Uncertainty, ambivalence, open questions, hypothesis status and decision
    status are preserved.  Output is JSON-safe.
    """
    if isinstance(source, Mapping):
        unresolved = bool(source.get("unresolved", False)) or bool(source.get("open_questions"))
        ambivalence_present = bool(source.get("ambivalence_present", False))
        hypotheses = source.get("hypotheses", ()) or ()
        open_questions = source.get("open_questions", ()) or ()
        hypothesis_count = len(hypotheses)
    else:
        unresolved = True
        ambivalence_present = False
        hypotheses = ()
        open_questions = ()
        hypothesis_count = 0
    certainty_increased = False
    if certainty_override is not None:
        certainty_increased = True  # explicit override may raise wording level
    text = []
    if unresolved:
        text.append("This reflection remains unresolved.")
    if ambivalence_present:
        text.append("Conflicting feelings are preserved without forcing a single answer.")
    if hypothesis_count > 0:
        text.append(f"{hypothesis_count} hypothesis/hypotheses remain candidates.")
    return {
        "summary": " ".join(text) if text else "No summary content provided.",
        "certainty_increased": certainty_increased,
        "unresolved": unresolved,
        "ambivalence_present": ambivalence_present,
        "hypothesis_count": hypothesis_count,
        "open_questions": tuple(open_questions) if isinstance(open_questions, (list, tuple)) else (open_questions,),
        "decision_status": "not adopted" if unresolved else "reviewed",
    }


def review_decision_result(*, decision_candidate=None, values=(), tensions=(),
                           options=()) -> dict:
    """Review a decision candidate without adopting it.

    Decision discussed != decision made; a recommendation is analysis, never an
    adoption.  Output is JSON-safe.
    """
    review = {
        "decision_candidate": decision_candidate,
        "values": tuple(values) if isinstance(values, (list, tuple)) else (values,),
        "tensions": tuple(tensions) if isinstance(tensions, (list, tuple)) else (tensions,),
        "options": tuple(options) if isinstance(options, (list, tuple)) else (options,),
        "uncertainties": (),
        "adopted_decision": False,
    }
    return {
        "analysis": review,
        "decision_adopted": False,
        "proposal_only": True,
        "recommendation": "review complete; no decision adopted without explicit user confirmation.",
        "adopted_decision": False,
        "decision_candidate_reviewed": True,
    }


__all__ = [
    "REFLECTION_OPERATION_IDS",
    "build_personal_timeline_result",
    "build_reflection_operation_definitions",
    "compare_versions_result",
    "extract_beliefs_result",
    "generate_hypotheses_result",
    "generate_summary_result",
    "identify_open_questions_result",
    "prepare_notion_entry_result",
    "review_decision_result",
    "structure_reflection_result",
]