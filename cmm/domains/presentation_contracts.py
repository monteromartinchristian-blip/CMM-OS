"""Phase 10.16 – immutable, reference-only Domain Presentation contracts."""

from __future__ import annotations

import hashlib
import json
import math
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from enum import Enum
from types import MappingProxyType
from typing import Any

from cmm.domains.composition_contracts import PresentationComposition
from cmm.domains.errors import (
    DomainPresentationContractError,
    DomainPresentationSerializationError,
)
from cmm.domains.profile_contracts import DomainPresentationPolicy


class DomainOutputIntentType(str, Enum):
    """Closed logical output taxonomy; this phase never renders an output."""

    HUMAN_READABLE = "HUMAN_READABLE"
    STRUCTURED = "STRUCTURED"
    UI_COMPONENTS = "UI_COMPONENTS"
    ARTIFACT_REQUEST = "ARTIFACT_REQUEST"


class DomainPresentationItemType(str, Enum):
    FINDING = "FINDING"
    GAP = "GAP"
    WARNING = "WARNING"
    CONTRADICTION = "CONTRADICTION"
    QUESTION = "QUESTION"
    APPROVAL = "APPROVAL"
    ESCALATION = "ESCALATION"
    WORKFLOW = "WORKFLOW"
    MEMORY_PROPOSAL = "MEMORY_PROPOSAL"
    RECOMMENDATION = "RECOMMENDATION"
    DECISION = "DECISION"


class DomainPresentationEpistemicKind(str, Enum):
    FACT = "fact"
    INFERENCE = "inference"
    HYPOTHESIS = "hypothesis"
    DIAGNOSIS = "diagnosis"
    RECOMMENDATION = "recommendation"
    DECISION = "decision"
    UNKNOWN = "unknown"


class DomainPresentationValidationState(str, Enum):
    PLANNED = "PLANNED"
    VALID = "VALID"
    BLOCKED = "BLOCKED"


class DomainPresentationConflictCode(str, Enum):
    TERMINOLOGY_INCOMPATIBLE = "TERMINOLOGY_INCOMPATIBLE"
    COMPONENT_INCOMPATIBLE = "COMPONENT_INCOMPATIBLE"
    OUTPUT_INTENT_INCOMPATIBLE = "OUTPUT_INTENT_INCOMPATIBLE"
    REQUIRED_SECTION_SUPPRESSED = "REQUIRED_SECTION_SUPPRESSED"
    UNRESOLVED_MULTIDOMAIN = "UNRESOLVED_MULTIDOMAIN"


class DomainPresentationDecisionCode(str, Enum):
    SECTION_ORDER = "SECTION_ORDER"
    WARNING_ORDER = "WARNING_ORDER"
    COMPONENT_SELECTION = "COMPONENT_SELECTION"
    OUTPUT_INTENT = "OUTPUT_INTENT"
    VISIBILITY = "VISIBILITY"
    TERMINOLOGY = "TERMINOLOGY"


class DomainPresentationValidationCode(str, Enum):
    """Closed, safe validation outcome codes for presentation preservation."""

    REQUEST_ID_CHANGED = "REQUEST_ID_CHANGED"
    COMPOSITION_ID_CHANGED = "COMPOSITION_ID_CHANGED"
    POLICY_ID_CHANGED = "POLICY_ID_CHANGED"
    OUTPUT_INTENT_CHANGED = "OUTPUT_INTENT_CHANGED"
    OUTPUT_INTENT_NOT_ALLOWED = "OUTPUT_INTENT_NOT_ALLOWED"
    PREFERRED_OUTPUT_TYPE_CHANGED = "PREFERRED_OUTPUT_TYPE_CHANGED"
    PROTECTED_TERMS_CHANGED = "PROTECTED_TERMS_CHANGED"
    TERM_GLOSSES_CHANGED = "TERM_GLOSSES_CHANGED"
    DETAIL_LEVEL_CHANGED = "DETAIL_LEVEL_CHANGED"
    WARNING_POSITION_CHANGED = "WARNING_POSITION_CHANGED"
    DISCLAIMERS_MISSING = "DISCLAIMERS_MISSING"
    HYPOTHESIS_UNQUALIFIED = "HYPOTHESIS_UNQUALIFIED"
    MISSING_REF = "MISSING_REF"
    UNKNOWN_REF = "UNKNOWN_REF"
    ITEM_TYPE_CHANGED = "ITEM_TYPE_CHANGED"
    EPISTEMIC_KIND_CHANGED = "EPISTEMIC_KIND_CHANGED"
    CONFIDENCE_CHANGED = "CONFIDENCE_CHANGED"
    PROVENANCE_REQUIREMENT_CHANGED = "PROVENANCE_REQUIREMENT_CHANGED"
    WARNING_PRIORITY_CHANGED = "WARNING_PRIORITY_CHANGED"
    SOURCE_ORDER_CHANGED = "SOURCE_ORDER_CHANGED"
    VISIBILITY_CHANGED = "VISIBILITY_CHANGED"
    DOMAIN_PARTICIPATION_CHANGED = "DOMAIN_PARTICIPATION_CHANGED"
    ITEM_VISIBILITY_STATE_CHANGED = "ITEM_VISIBILITY_STATE_CHANGED"
    REQUIRED_REFERENCE_HIDDEN = "REQUIRED_REFERENCE_HIDDEN"
    REQUIRED_REFERENCE_WITHOUT_SECTION = "REQUIRED_REFERENCE_WITHOUT_SECTION"
    REQUIRED_VISIBILITY_OBLIGATION_MISSING = "REQUIRED_VISIBILITY_OBLIGATION_MISSING"
    REQUIRED_SECTION_HIDDEN = "REQUIRED_SECTION_HIDDEN"
    DUPLICATE_REFERENCE = "DUPLICATE_REFERENCE"
    UNKNOWN_VISIBILITY_REFERENCE = "UNKNOWN_VISIBILITY_REFERENCE"
    EFFECTIVE_REQUIRED_SECTION_MISSING = "EFFECTIVE_REQUIRED_SECTION_MISSING"
    EFFECTIVE_REQUIRED_SECTION_NOT_REQUIRED = "EFFECTIVE_REQUIRED_SECTION_NOT_REQUIRED"
    EFFECTIVE_REQUIRED_SECTION_HIDDEN = "EFFECTIVE_REQUIRED_SECTION_HIDDEN"
    EFFECTIVE_REQUIRED_SECTION_SUPPRESSED = "EFFECTIVE_REQUIRED_SECTION_SUPPRESSED"
    MANDATORY_SECTION_SUPPRESSED = "MANDATORY_SECTION_SUPPRESSED"
    UNKNOWN_SECTION_REFERENCE = "UNKNOWN_SECTION_REFERENCE"
    MISSING_SECTION_REF = "MISSING_SECTION_REF"
    UNKNOWN_SECTION_REF = "UNKNOWN_SECTION_REF"
    ILLEGAL_DUPLICATE_REF = "ILLEGAL_DUPLICATE_REF"
    INVALID_WARNING_PRIORITY = "INVALID_WARNING_PRIORITY"
    WARNING_GROUP_TYPE_MISMATCH = "WARNING_GROUP_TYPE_MISMATCH"
    QUESTION_GROUP_TYPE_MISMATCH = "QUESTION_GROUP_TYPE_MISMATCH"
    APPROVAL_GROUP_TYPE_MISMATCH = "APPROVAL_GROUP_TYPE_MISMATCH"
    ESCALATION_GROUP_TYPE_MISMATCH = "ESCALATION_GROUP_TYPE_MISMATCH"
    WORKFLOW_GROUP_TYPE_MISMATCH = "WORKFLOW_GROUP_TYPE_MISMATCH"
    MEMORY_PROPOSAL_GROUP_TYPE_MISMATCH = "MEMORY_PROPOSAL_GROUP_TYPE_MISMATCH"
    WARNING_GROUP_MISSING_REF = "WARNING_GROUP_MISSING_REF"
    QUESTION_GROUP_MISSING_REF = "QUESTION_GROUP_MISSING_REF"
    APPROVAL_GROUP_MISSING_REF = "APPROVAL_GROUP_MISSING_REF"
    ESCALATION_GROUP_MISSING_REF = "ESCALATION_GROUP_MISSING_REF"
    WORKFLOW_GROUP_MISSING_REF = "WORKFLOW_GROUP_MISSING_REF"
    MEMORY_PROPOSAL_GROUP_MISSING_REF = "MEMORY_PROPOSAL_GROUP_MISSING_REF"
    COMPONENT_UNKNOWN_SECTION = "COMPONENT_UNKNOWN_SECTION"
    UNRESOLVED_MULTIDOMAIN_CONFLICT = "UNRESOLVED_MULTIDOMAIN_CONFLICT"


_ARTIFACT_FORMATS = frozenset({"PDF", "DOCX", "HTML"})
_TOKEN_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_.:-]{0,127}$")
_DIGEST_RE = re.compile(r"^[0-9a-f]{64}$")


def _error(message: str, field: str) -> DomainPresentationContractError:
    return DomainPresentationContractError(message, field=field)


def _text(value: Any, field_name: str) -> str:
    if not isinstance(value, str) or not value:
        raise _error(f"{field_name} must be a non-empty string", field_name)
    return value


def _token(value: Any, field_name: str) -> str:
    value = _text(value, field_name)
    if not _TOKEN_RE.fullmatch(value):
        raise _error(f"{field_name} must be a safe identifier token", field_name)
    return value


def _non_negative_int(value: Any, field_name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise _error(f"{field_name} must be a non-negative integer", field_name)
    return value


def _float_opt(value: Any, field_name: str) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise _error(f"{field_name} must be a number or None", field_name)
    result = float(value)
    if not 0.0 <= result <= 1.0:
        raise _error(f"{field_name} must be between 0.0 and 1.0", field_name)
    return result


def _bool(value: Any, field_name: str) -> bool:
    if type(value) is not bool:
        raise _error(f"{field_name} must be a boolean", field_name)
    return value


def _tuple_of_tokens(value: Any, field_name: str) -> tuple[str, ...]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        raise _error(f"{field_name} must be a sequence", field_name)
    result = tuple(_token(item, field_name) for item in value)
    if len(result) != len(set(result)):
        raise _error(f"{field_name} must not contain duplicates", field_name)
    return result


def _enum(value: Any, enum_type: type[Enum], field_name: str) -> Any:
    if isinstance(value, enum_type):
        return value
    try:
        return enum_type(value)
    except (TypeError, ValueError) as exc:
        raise _error(f"{field_name} is not a valid {enum_type.__name__}", field_name) from exc


def _safe_metadata(value: Any) -> MappingProxyType[str, str | int | float | bool | None]:
    if not isinstance(value, Mapping):
        raise _error("safe_metadata must be a mapping", "safe_metadata")
    result: dict[str, str | int | float | bool | None] = {}
    for key, item in value.items():
        key = _token(key, "safe_metadata")
        if item is None:
            result[key] = item
            continue
        if type(item) is bool:
            result[key] = item
            continue
        if isinstance(item, int):
            result[key] = item
            continue
        if isinstance(item, float):
            if not math.isfinite(item):
                raise _error("safe_metadata floats must be finite", "safe_metadata")
            result[key] = item
            continue
        if isinstance(item, str):
            if not _TOKEN_RE.fullmatch(item):
                raise _error("safe_metadata strings must be safe identifier tokens", "safe_metadata")
            result[key] = item
            continue
        if item is not None:
            raise _error("safe_metadata values must be scalar", "safe_metadata")
    return MappingProxyType(result)


def _strict_mapping(data: Any, expected: frozenset[str], name: str) -> Mapping[str, Any]:
    if not isinstance(data, Mapping):
        raise DomainPresentationSerializationError(f"{name}.from_dict requires a mapping", field="data")
    unknown = set(data) - expected
    if unknown:
        raise DomainPresentationSerializationError(
            f"{name}.from_dict received unknown fields: {sorted(unknown)}", field="data"
        )
    return data


def _canonical_digest(value: Mapping[str, Any]) -> str:
    try:
        encoded = json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        )
    except (TypeError, ValueError) as exc:
        raise _error("canonical digest requires finite JSON values", "digest") from exc
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class DomainOutputIntent:
    output_type: DomainOutputIntentType
    artifact_format: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "output_type", _enum(self.output_type, DomainOutputIntentType, "output_type"))
        if self.artifact_format is not None:
            artifact_format = _enum(self.artifact_format, _ArtifactFormat, "artifact_format").value
            object.__setattr__(self, "artifact_format", artifact_format)
        if self.artifact_format is not None and self.output_type is not DomainOutputIntentType.ARTIFACT_REQUEST:
            raise _error("artifact_format requires ARTIFACT_REQUEST", "artifact_format")

    def to_dict(self) -> dict[str, Any]:
        return {"output_type": self.output_type.value, "artifact_format": self.artifact_format}

    @classmethod
    def from_dict(cls, data: Any) -> DomainOutputIntent:
        data = _strict_mapping(data, frozenset({"output_type", "artifact_format"}), cls.__name__)
        try:
            return cls(**data)
        except DomainPresentationContractError as exc:
            raise DomainPresentationSerializationError(exc.message, field=exc.field) from exc


class _ArtifactFormat(str, Enum):
    PDF = "PDF"
    DOCX = "DOCX"
    HTML = "HTML"


@dataclass(frozen=True, slots=True)
class DomainPresentationItemRef:
    ref_id: str
    item_type: DomainPresentationItemType
    source_order: int
    domain_ids: tuple[str, ...] = ()
    epistemic_kind: DomainPresentationEpistemicKind | None = None
    confidence: float | None = None
    requires_provenance: bool = False
    visible: bool = True
    warning_priority: int | None = None
    pending: bool = False
    requires_user_interaction: bool = False
    requires_approval: bool = False
    requires_confirmation: bool = False
    explicitly_visible: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "ref_id", _token(self.ref_id, "ref_id"))
        object.__setattr__(self, "item_type", _enum(self.item_type, DomainPresentationItemType, "item_type"))
        object.__setattr__(self, "source_order", _non_negative_int(self.source_order, "source_order"))
        object.__setattr__(self, "domain_ids", _tuple_of_tokens(self.domain_ids, "domain_ids"))
        if self.epistemic_kind is not None:
            object.__setattr__(self, "epistemic_kind", _enum(self.epistemic_kind, DomainPresentationEpistemicKind, "epistemic_kind"))
        object.__setattr__(self, "confidence", _float_opt(self.confidence, "confidence"))
        object.__setattr__(self, "requires_provenance", _bool(self.requires_provenance, "requires_provenance"))
        object.__setattr__(self, "visible", _bool(self.visible, "visible"))
        if self.warning_priority is not None:
            object.__setattr__(self, "warning_priority", _non_negative_int(self.warning_priority, "warning_priority"))
        if self.item_type is not DomainPresentationItemType.WARNING and self.warning_priority is not None:
            raise _error("warning_priority is only valid for WARNING", "warning_priority")
        for name in (
            "pending",
            "requires_user_interaction",
            "requires_approval",
            "requires_confirmation",
            "explicitly_visible",
        ):
            object.__setattr__(self, name, _bool(getattr(self, name), name))

    def to_dict(self) -> dict[str, Any]:
        return {
            "ref_id": self.ref_id, "item_type": self.item_type.value, "source_order": self.source_order,
            "domain_ids": list(self.domain_ids), "epistemic_kind": self.epistemic_kind.value if self.epistemic_kind else None,
            "confidence": self.confidence, "requires_provenance": self.requires_provenance,
            "visible": self.visible, "warning_priority": self.warning_priority,
            "pending": self.pending,
            "requires_user_interaction": self.requires_user_interaction,
            "requires_approval": self.requires_approval,
            "requires_confirmation": self.requires_confirmation,
            "explicitly_visible": self.explicitly_visible,
        }

    @classmethod
    def from_dict(cls, data: Any) -> DomainPresentationItemRef:
        data = _strict_mapping(data, frozenset(cls.__dataclass_fields__), cls.__name__)
        try:
            return cls(**data)
        except DomainPresentationContractError as exc:
            raise DomainPresentationSerializationError(exc.message, field=exc.field) from exc


@dataclass(frozen=True, slots=True)
class DomainPresentationRequest:
    request_id: str
    upstream_result_id: str
    composition_id: str
    policy_id: str
    presentation: PresentationComposition
    policy: DomainPresentationPolicy
    items: tuple[DomainPresentationItemRef, ...]
    primary_domain_id: str
    output_intent: DomainOutputIntent | None = None
    supporting_domain_ids: tuple[str, ...] = ()
    safe_metadata: MappingProxyType[str, str | int | float | bool | None] = field(default_factory=lambda: MappingProxyType({}))

    def __post_init__(self) -> None:
        for name in ("request_id", "upstream_result_id", "composition_id", "policy_id", "primary_domain_id"):
            object.__setattr__(self, name, _token(getattr(self, name), name))
        if not isinstance(self.presentation, PresentationComposition):
            raise _error("presentation must be a PresentationComposition", "presentation")
        if not isinstance(self.policy, DomainPresentationPolicy):
            raise _error("policy must be a DomainPresentationPolicy", "policy")
        if self.output_intent is not None and not isinstance(self.output_intent, DomainOutputIntent):
            object.__setattr__(self, "output_intent", DomainOutputIntent.from_dict(self.output_intent))
        object.__setattr__(self, "supporting_domain_ids", _tuple_of_tokens(self.supporting_domain_ids, "supporting_domain_ids"))
        if self.primary_domain_id in self.supporting_domain_ids:
            raise _error("primary_domain_id must not appear in supporting_domain_ids", "supporting_domain_ids")
        if isinstance(self.items, (str, bytes)) or not isinstance(self.items, Sequence):
            raise _error("items must be a sequence", "items")
        items = tuple(
            item if isinstance(item, DomainPresentationItemRef) else DomainPresentationItemRef.from_dict(item)
            for item in self.items
        )
        if len({item.ref_id for item in items}) != len(items):
            raise _error("items must not contain duplicate ref_id values", "items")
        object.__setattr__(self, "items", items)
        object.__setattr__(self, "safe_metadata", _safe_metadata(self.safe_metadata))

    def to_dict(self) -> dict[str, Any]:
        return {
            "request_id": self.request_id, "upstream_result_id": self.upstream_result_id,
            "composition_id": self.composition_id, "policy_id": self.policy_id,
            "presentation": self.presentation.to_dict(), "policy": self.policy.to_dict(),
            "output_intent": self.output_intent.to_dict() if self.output_intent else None, "items": [item.to_dict() for item in self.items],
            "primary_domain_id": self.primary_domain_id, "supporting_domain_ids": list(self.supporting_domain_ids),
            "safe_metadata": dict(self.safe_metadata),
        }

    def calculate_digest(self) -> str:
        return _canonical_digest(self.to_dict())

    @classmethod
    def from_dict(cls, data: Any) -> DomainPresentationRequest:
        data = dict(_strict_mapping(data, frozenset(cls.__dataclass_fields__), cls.__name__))
        try:
            data["presentation"] = PresentationComposition.from_dict(data["presentation"])
            data["policy"] = DomainPresentationPolicy.from_dict(data["policy"])
            if data["output_intent"] is not None:
                data["output_intent"] = DomainOutputIntent.from_dict(data["output_intent"])
            data["items"] = tuple(DomainPresentationItemRef.from_dict(item) for item in data["items"])
            return cls(**data)
        except (DomainPresentationContractError, KeyError) as exc:
            message = exc.message if isinstance(exc, DomainPresentationContractError) else f"missing field: {exc.args[0]}"
            raise DomainPresentationSerializationError(message, field="data") from exc


@dataclass(frozen=True, slots=True)
class DomainPresentationSectionPlan:
    section_id: str
    item_refs: tuple[str, ...]
    required: bool = False
    visible: bool = True

    def __post_init__(self) -> None:
        object.__setattr__(self, "section_id", _token(self.section_id, "section_id"))
        object.__setattr__(self, "item_refs", _tuple_of_tokens(self.item_refs, "item_refs"))
        object.__setattr__(self, "required", _bool(self.required, "required"))
        object.__setattr__(self, "visible", _bool(self.visible, "visible"))

    def to_dict(self) -> dict[str, Any]:
        return {"section_id": self.section_id, "item_refs": list(self.item_refs), "required": self.required, "visible": self.visible}

    @classmethod
    def from_dict(cls, data: Any) -> DomainPresentationSectionPlan:
        data = _strict_mapping(data, frozenset(cls.__dataclass_fields__), cls.__name__)
        return cls(**data)


@dataclass(frozen=True, slots=True)
class DomainPresentationComponentDescriptor:
    component_id: str
    view_id: str
    section_id: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "component_id", _token(self.component_id, "component_id"))
        object.__setattr__(self, "view_id", _token(self.view_id, "view_id"))
        if self.section_id is not None:
            object.__setattr__(self, "section_id", _token(self.section_id, "section_id"))

    def to_dict(self) -> dict[str, Any]:
        return {"component_id": self.component_id, "view_id": self.view_id, "section_id": self.section_id}

    @classmethod
    def from_dict(cls, data: Any) -> DomainPresentationComponentDescriptor:
        return cls(**_strict_mapping(data, frozenset(cls.__dataclass_fields__), cls.__name__))


@dataclass(frozen=True, slots=True)
class DomainPresentationConflict:
    code: DomainPresentationConflictCode
    related_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "code", _enum(self.code, DomainPresentationConflictCode, "code"))
        object.__setattr__(self, "related_ids", _tuple_of_tokens(self.related_ids, "related_ids"))

    def to_dict(self) -> dict[str, Any]:
        return {"code": self.code.value, "related_ids": list(self.related_ids)}

    @classmethod
    def from_dict(cls, data: Any) -> DomainPresentationConflict:
        return cls(**_strict_mapping(data, frozenset(cls.__dataclass_fields__), cls.__name__))


@dataclass(frozen=True, slots=True)
class DomainPresentationDecision:
    code: DomainPresentationDecisionCode
    related_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "code", _enum(self.code, DomainPresentationDecisionCode, "code"))
        object.__setattr__(self, "related_ids", _tuple_of_tokens(self.related_ids, "related_ids"))

    def to_dict(self) -> dict[str, Any]:
        return {"code": self.code.value, "related_ids": list(self.related_ids)}

    @classmethod
    def from_dict(cls, data: Any) -> DomainPresentationDecision:
        return cls(**_strict_mapping(data, frozenset(cls.__dataclass_fields__), cls.__name__))


@dataclass(frozen=True, slots=True)
class DomainPresentationPlan:
    plan_id: str
    request_id: str
    composition_id: str
    policy_id: str
    output_intent: DomainOutputIntent
    sections: tuple[DomainPresentationSectionPlan, ...]
    preferred_output_type: DomainOutputIntentType | None = None
    detail_level: str | None = None
    warning_position: str | None = None
    qualified_hypothesis_refs: tuple[str, ...] = ()
    item_refs: tuple[DomainPresentationItemRef, ...] = ()
    components: tuple[DomainPresentationComponentDescriptor, ...] = ()
    protected_terms: tuple[str, ...] = ()
    term_glosses: MappingProxyType[str, str] = field(default_factory=lambda: MappingProxyType({}))
    warning_refs: tuple[str, ...] = ()
    conflicts: tuple[DomainPresentationConflict, ...] = ()
    decisions: tuple[DomainPresentationDecision, ...] = ()
    visibility_obligations: tuple[str, ...] = ()
    question_refs: tuple[str, ...] = ()
    approval_refs: tuple[str, ...] = ()
    escalation_refs: tuple[str, ...] = ()
    workflow_refs: tuple[str, ...] = ()
    memory_proposal_refs: tuple[str, ...] = ()
    validation_state: DomainPresentationValidationState = DomainPresentationValidationState.PLANNED
    safe_metadata: MappingProxyType[str, str | int | float | bool | None] = field(default_factory=lambda: MappingProxyType({}))

    def __post_init__(self) -> None:
        for name in ("plan_id", "request_id", "composition_id", "policy_id"):
            object.__setattr__(self, name, _token(getattr(self, name), name))
        if not isinstance(self.output_intent, DomainOutputIntent):
            object.__setattr__(self, "output_intent", DomainOutputIntent.from_dict(self.output_intent))
        if self.preferred_output_type is not None:
            object.__setattr__(
                self,
                "preferred_output_type",
                _enum(
                    self.preferred_output_type,
                    DomainOutputIntentType,
                    "preferred_output_type",
                ),
            )
        if self.detail_level is not None:
            object.__setattr__(self, "detail_level", _token(self.detail_level, "detail_level"))
        if self.warning_position is not None:
            object.__setattr__(
                self, "warning_position", _token(self.warning_position, "warning_position")
            )
        for name, cls in (("sections", DomainPresentationSectionPlan), ("item_refs", DomainPresentationItemRef), ("components", DomainPresentationComponentDescriptor), ("conflicts", DomainPresentationConflict), ("decisions", DomainPresentationDecision)):
            value = getattr(self, name)
            if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
                raise _error(f"{name} must be a sequence", name)
            object.__setattr__(self, name, tuple(item if isinstance(item, cls) else cls.from_dict(item) for item in value))
        if len({section.section_id for section in self.sections}) != len(self.sections):
            raise _error("sections must not contain duplicate section_id values", "sections")
        if len({item.ref_id for item in self.item_refs}) != len(self.item_refs):
            raise _error("item_refs must not contain duplicate ref_id values", "item_refs")
        for name in ("protected_terms", "warning_refs", "visibility_obligations", "question_refs", "approval_refs", "escalation_refs", "workflow_refs", "memory_proposal_refs", "qualified_hypothesis_refs"):
            object.__setattr__(self, name, _tuple_of_tokens(getattr(self, name), name))
        glosses = _validate_glosses(self.term_glosses)
        if not set(glosses).issubset(self.protected_terms):
            raise _error("term_glosses keys must be protected_terms", "term_glosses")
        object.__setattr__(self, "term_glosses", glosses)
        object.__setattr__(self, "validation_state", _enum(self.validation_state, DomainPresentationValidationState, "validation_state"))
        object.__setattr__(self, "safe_metadata", _safe_metadata(self.safe_metadata))

    def to_dict(self) -> dict[str, Any]:
        return {
            "plan_id": self.plan_id, "request_id": self.request_id, "composition_id": self.composition_id, "policy_id": self.policy_id,
            "output_intent": self.output_intent.to_dict(), "sections": [v.to_dict() for v in self.sections], "preferred_output_type": self.preferred_output_type.value if self.preferred_output_type else None, "detail_level": self.detail_level, "warning_position": self.warning_position, "qualified_hypothesis_refs": list(self.qualified_hypothesis_refs), "item_refs": [v.to_dict() for v in self.item_refs],
            "components": [v.to_dict() for v in self.components], "protected_terms": list(self.protected_terms), "term_glosses": dict(self.term_glosses),
            "warning_refs": list(self.warning_refs), "conflicts": [v.to_dict() for v in self.conflicts], "decisions": [v.to_dict() for v in self.decisions],
            "visibility_obligations": list(self.visibility_obligations), "question_refs": list(self.question_refs), "approval_refs": list(self.approval_refs),
            "escalation_refs": list(self.escalation_refs), "workflow_refs": list(self.workflow_refs), "memory_proposal_refs": list(self.memory_proposal_refs),
            "validation_state": self.validation_state.value, "safe_metadata": dict(self.safe_metadata),
        }

    def calculate_digest(self) -> str:
        return _canonical_digest(self.to_dict())

    @classmethod
    def from_dict(cls, data: Any) -> DomainPresentationPlan:
        data = dict(_strict_mapping(data, frozenset(cls.__dataclass_fields__), cls.__name__))
        data["output_intent"] = DomainOutputIntent.from_dict(data["output_intent"])
        if data["preferred_output_type"] is not None:
            data["preferred_output_type"] = DomainOutputIntentType(data["preferred_output_type"])
        for name, item_cls in (("sections", DomainPresentationSectionPlan), ("item_refs", DomainPresentationItemRef), ("components", DomainPresentationComponentDescriptor), ("conflicts", DomainPresentationConflict), ("decisions", DomainPresentationDecision)):
            data[name] = tuple(item_cls.from_dict(item) for item in data[name])
        return cls(**data)


def _validate_glosses(value: Any) -> MappingProxyType[str, str]:
    if not isinstance(value, Mapping):
        raise _error("term_glosses must be a mapping", "term_glosses")
    result: dict[str, str] = {}
    for key, item in value.items():
        if not isinstance(item, str) or not item or len(item) > 512:
            raise _error("term_glosses values must be non-empty bounded strings", "term_glosses")
        result[_token(key, "term_glosses")] = item
    return MappingProxyType(result)


@dataclass(frozen=True, slots=True)
class DomainPresentationValidationResult:
    valid: bool
    state: DomainPresentationValidationState
    codes: tuple[DomainPresentationValidationCode, ...] = ()
    conflicts: tuple[DomainPresentationConflict, ...] = ()
    missing_refs: tuple[str, ...] = ()
    unexpected_refs: tuple[str, ...] = ()
    invariants: tuple[str, ...] = ()
    upstream_digest: str = ""
    plan_digest: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "valid", _bool(self.valid, "valid"))
        object.__setattr__(self, "state", _enum(self.state, DomainPresentationValidationState, "state"))
        if isinstance(self.codes, (str, bytes)) or not isinstance(self.codes, Sequence):
            raise _error("codes must be a sequence", "codes")
        object.__setattr__(
            self,
            "codes",
            tuple(
                _enum(code, DomainPresentationValidationCode, "codes")
                for code in self.codes
            ),
        )
        for name in ("missing_refs", "unexpected_refs", "invariants"):
            object.__setattr__(self, name, _tuple_of_tokens(getattr(self, name), name))
        object.__setattr__(self, "conflicts", tuple(item if isinstance(item, DomainPresentationConflict) else DomainPresentationConflict.from_dict(item) for item in self.conflicts))
        for name in ("upstream_digest", "plan_digest"):
            digest = getattr(self, name)
            if not isinstance(digest, str) or not _DIGEST_RE.fullmatch(digest):
                raise _error(f"{name} must be a SHA-256 hex digest", name)
            object.__setattr__(self, name, digest)
        expected_state = DomainPresentationValidationState.VALID if self.valid else DomainPresentationValidationState.BLOCKED
        if self.state is not expected_state:
            raise _error("state must match valid", "state")

    def to_dict(self) -> dict[str, Any]:
        return {"valid": self.valid, "state": self.state.value, "codes": [code.value for code in self.codes], "conflicts": [v.to_dict() for v in self.conflicts], "missing_refs": list(self.missing_refs), "unexpected_refs": list(self.unexpected_refs), "invariants": list(self.invariants), "upstream_digest": self.upstream_digest, "plan_digest": self.plan_digest}

    @classmethod
    def from_dict(cls, data: Any) -> DomainPresentationValidationResult:
        data = dict(_strict_mapping(data, frozenset(cls.__dataclass_fields__), cls.__name__))
        data["conflicts"] = tuple(DomainPresentationConflict.from_dict(item) for item in data["conflicts"])
        return cls(**data)


__all__ = [
    "DomainOutputIntent", "DomainOutputIntentType", "DomainPresentationComponentDescriptor",
    "DomainPresentationConflict", "DomainPresentationConflictCode", "DomainPresentationDecision",
    "DomainPresentationDecisionCode", "DomainPresentationEpistemicKind", "DomainPresentationItemRef",
    "DomainPresentationItemType", "DomainPresentationPlan", "DomainPresentationRequest",
    "DomainPresentationSectionPlan", "DomainPresentationValidationCode", "DomainPresentationValidationResult", "DomainPresentationValidationState",
]
