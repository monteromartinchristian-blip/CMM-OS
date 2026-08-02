"""Reference-only contracts for Phase 10.17 Domain Trace."""

from __future__ import annotations

import hashlib
import json
import math
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from types import MappingProxyType
from typing import Any

from cmm.domains.errors import (
    DomainSerializationError,
    DomainTraceContractError,
    DomainTraceSerializationError,
)
from cmm.domains.identifiers import DomainId

_ID_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_.:-]{0,191}$")
_MAX_METADATA_DEPTH = 4
_MAX_METADATA_ITEMS = 32
_MAX_METADATA_SEQUENCE_ITEMS = 64
_MAX_METADATA_STRING_LENGTH = 128
_PRIVATE_MARKERS = frozenset(
    {
        "prompt", "systemprompt", "developerprompt", "usermessage", "objectivetext",
        "content", "rawcontent", "payload", "secret", "token", "credential",
        "password", "apikey", "chainofthought", "reasoningtext", "rawreasoning",
        "rawresource", "toolarguments", "toolresponse", "providerrequest",
        "providerresponse", "pii",
    }
)
_PRIVATE_KEY_TOKENS = frozenset(
    {
        "prompt", "message", "content", "payload", "secret", "token",
        "credential", "password", "apikey", "pii",
    }
)
_SAFE_REFERENCE_KEYS = frozenset(
    {
        "reasoningtraceid",
        "knowledgepackageid",
        "providerauditid",
        "crossdomaintraceid",
    }
)
_PRIVATE_TOKEN_SEQUENCES = (
    ("prompt",),
    ("user", "message"),
    ("objective", "text"),
    ("content",),
    ("payload",),
    ("secret",),
    ("token",),
    ("credential",),
    ("password",),
    ("api", "key"),
    ("chain", "of", "thought"),
    ("reasoning", "text"),
    ("raw", "reasoning"),
    ("raw", "resource"),
    ("tool", "arguments"),
    ("tool", "response"),
    ("provider", "request"),
    ("provider", "response"),
)


def _normalized(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", value.lower())


def _word_tokens(value: str) -> tuple[str, ...]:
    separated = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1 \2", value)
    separated = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", separated)
    return tuple(item for item in re.split(r"[^A-Za-z0-9]+", separated.lower()) if item)


def _contains_private_marker(value: str) -> bool:
    normalized = _normalized(value)
    if normalized in _SAFE_REFERENCE_KEYS:
        return False
    tokens = _word_tokens(value)
    if normalized in _PRIVATE_MARKERS or any(item in _PRIVATE_KEY_TOKENS for item in tokens):
        return True
    return any(
        tokens[index:index + len(sequence)] == sequence
        for sequence in _PRIVATE_TOKEN_SEQUENCES
        for index in range(len(tokens) - len(sequence) + 1)
    )


def _identifier(value: Any, field_name: str) -> str:
    if not isinstance(value, str) or not _ID_RE.fullmatch(value):
        raise DomainTraceContractError(f"{field_name} must be a safe reference ID", field=field_name)
    return value


def _domain_id(value: Any, field_name: str) -> DomainId:
    if isinstance(value, DomainId):
        return value
    if isinstance(value, str):
        try:
            return DomainId.from_str(value)
        except ValueError as exc:
            raise DomainTraceContractError(f"{field_name} must be a DomainId", field=field_name) from exc
    raise DomainTraceContractError(f"{field_name} must be a DomainId", field=field_name)


def _aware(value: Any, field_name: str) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise DomainTraceContractError(f"{field_name} must be timezone-aware", field=field_name)
    return value


def _freeze_metadata(value: Any, field_name: str = "metadata", depth: int = 0) -> Any:
    if depth > _MAX_METADATA_DEPTH:
        raise DomainTraceContractError(f"{field_name} exceeds maximum depth", field=field_name)
    if value is None or isinstance(value, bool):
        return value
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise DomainTraceContractError(f"{field_name} floats must be finite", field=field_name)
        return value
    if isinstance(value, str):
        if len(value) > _MAX_METADATA_STRING_LENGTH or not _ID_RE.fullmatch(value):
            raise DomainTraceContractError(f"{field_name} strings must be bounded safe tokens", field=field_name)
        if _contains_private_marker(value):
            raise DomainTraceContractError(f"{field_name} contains private data", field=field_name)
        return value
    if isinstance(value, Mapping):
        if len(value) > _MAX_METADATA_ITEMS:
            raise DomainTraceContractError(f"{field_name} has too many entries", field=field_name)
        result: dict[str, Any] = {}
        for key, item in value.items():
            if not isinstance(key, str) or not _ID_RE.fullmatch(key):
                raise DomainTraceContractError(f"{field_name} keys must be safe tokens", field=field_name)
            if _contains_private_marker(key):
                raise DomainTraceContractError(f"{field_name} contains private data", field=field_name)
            result[key] = _freeze_metadata(item, field_name, depth + 1)
        return MappingProxyType(result)
    if isinstance(value, (list, tuple)):
        if len(value) > _MAX_METADATA_SEQUENCE_ITEMS:
            raise DomainTraceContractError(f"{field_name} has too many values", field=field_name)
        return tuple(_freeze_metadata(item, field_name, depth + 1) for item in value)
    raise DomainTraceContractError(f"{field_name} must be JSON-safe", field=field_name)


def _thaw(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {key: _thaw(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_thaw(item) for item in value]
    return value


def _canonical_json(value: Mapping[str, Any]) -> str:
    try:
        return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)
    except (TypeError, ValueError) as exc:
        raise DomainTraceContractError("trace must be JSON serializable", field="trace") from exc


def _strict_keys(data: Mapping[str, Any], allowed: set[str], name: str) -> None:
    if not isinstance(data, Mapping):
        raise DomainTraceSerializationError(f"{name} requires a mapping", field="data")
    if any(not isinstance(key, str) for key in data):
        raise DomainTraceSerializationError(f"{name} keys must be strings", field="data")
    unknown = set(data) - allowed
    if unknown:
        raise DomainTraceSerializationError(f"unknown {name} fields", field="data")


def _sorted_ids(values: Any, field_name: str) -> tuple[str, ...]:
    if values is None:
        return ()
    if isinstance(values, (str, bytes)) or not isinstance(values, Sequence):
        raise DomainTraceContractError(f"{field_name} must be a sequence", field=field_name)
    result = tuple(_identifier(value, field_name) for value in values)
    if len(result) != len(set(result)):
        raise DomainTraceContractError(f"{field_name} must not contain duplicates", field=field_name)
    return tuple(sorted(result))


def _sorted_diagnostics(values: Any, field_name: str) -> tuple[str, ...]:
    if values is None:
        return ()
    if isinstance(values, (str, bytes)) or not isinstance(values, Sequence):
        raise DomainTraceContractError(f"{field_name} must be a sequence", field=field_name)
    labels: list[str] = []
    for value in values:
        if isinstance(value, str) and _ID_RE.fullmatch(value):
            labels.append(value)
            continue
        if isinstance(value, str):
            material = f"str:{value}".encode()
        elif isinstance(value, bytes):
            material = b"bytes:" + value
        else:
            value_type = type(value)
            material = f"type:{value_type.__module__}.{value_type.__qualname__}".encode()
        labels.append(f"invalid-reference:{hashlib.sha256(material).hexdigest()[:16]}")
    return tuple(sorted(set(labels)))


def _validate_domain_result_coverage(
    contributions: Sequence[DomainTraceContribution],
    domain_results: Sequence[DomainResultTraceReference],
) -> None:
    """Ensure DOMAIN_RESULT references in contributions exactly match domain_results pairings."""
    contribution_pairs: list[tuple[str, object]] = []
    for contribution in contributions:
        for ref in contribution.references:
            if ref.kind is DomainTraceReferenceKind.DOMAIN_RESULT:
                contribution_pairs.append((ref.ref_id, contribution.domain_id))
    pairing_pairs = [(item.result_id, item.domain_id) for item in domain_results]
    if len(contribution_pairs) != len(set(contribution_pairs)):
        raise DomainTraceContractError(
            "duplicate DOMAIN_RESULT references in contributions",
            field="contributions",
        )
    if len(pairing_pairs) != len(set(pairing_pairs)):
        raise DomainTraceContractError(
            "duplicate domain_results pairings",
            field="domain_results",
        )
    if set(contribution_pairs) != set(pairing_pairs):
        raise DomainTraceContractError(
            "DOMAIN_RESULT references must exactly match domain_results pairings",
            field="domain_results",
        )


def _validate_global_id_uniqueness(
    contributions: Sequence[DomainTraceContribution],
    references: DomainTraceReferences,
) -> None:
    """Ensure each ref_id resolves to a single (kind, domain_id) identity."""
    identity_by_id: dict[str, tuple[DomainTraceReferenceKind, object]] = {}
    all_refs: list[DomainTraceReference] = []
    for contribution in contributions:
        all_refs.extend(contribution.references)
    all_refs.extend(references.all_references())
    for ref in all_refs:
        identity = (ref.kind, ref.domain_id)
        if ref.ref_id in identity_by_id:
            raise DomainTraceContractError(
                "reference IDs must resolve to a single identity",
                field="references",
            )
        identity_by_id[ref.ref_id] = identity


class DomainTraceStatus(str, Enum):
    COMPLETED = "completed"
    PARTIAL = "partial"
    BLOCKED = "blocked"
    FAILED = "failed"
    CANCELLED = "cancelled"


class DomainTraceRole(str, Enum):
    PRIMARY = "primary"
    SUPPORTING = "supporting"


@dataclass(frozen=True, slots=True)
class DomainTraceDomainSelection:
    """Authoritative primary/supporting domains from one upstream result."""

    source_id: str
    primary_domain: DomainId
    supporting_domains: tuple[DomainId, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "source_id", _identifier(self.source_id, "source_id"))
        object.__setattr__(self, "primary_domain", _domain_id(self.primary_domain, "primary_domain"))
        supporting = tuple(_domain_id(item, "supporting_domains") for item in self.supporting_domains)
        if self.primary_domain in supporting or len(set(supporting)) != len(supporting):
            raise DomainTraceContractError("supporting_domains must be unique and exclude primary_domain", field="supporting_domains")
        object.__setattr__(self, "supporting_domains", tuple(sorted(supporting, key=str)))

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_id": self.source_id,
            "primary_domain": str(self.primary_domain),
            "supporting_domains": [str(item) for item in self.supporting_domains],
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> DomainTraceDomainSelection:
        _strict_keys(data, {"source_id", "primary_domain", "supporting_domains"}, cls.__name__)
        try:
            return cls(data["source_id"], data["primary_domain"], tuple(data.get("supporting_domains", ())))
        except (KeyError, TypeError, ValueError, DomainSerializationError, DomainTraceContractError) as exc:
            raise DomainTraceSerializationError(
                "invalid DomainTraceDomainSelection payload",
                field="data",
            ) from exc


class DomainTraceReferenceKind(str, Enum):
    RESOURCE_RESOLUTION = "resource_resolution"
    PROFILE = "profile"
    PROFILE_TRACE = "profile_trace"
    RULE_PLAN = "rule_plan"
    RULE_RESULT = "rule_result"
    APPLIED_RULE_TRACE = "applied_rule_trace"
    OPERATION_RESULT = "operation_result"
    WORKFLOW_RUN = "workflow_run"
    WORKFLOW_RESULT = "workflow_result"
    PERMISSION_DECISION = "permission_decision"
    APPROVAL_REQUEST = "approval_request"
    APPROVAL_DECISION = "approval_decision"
    FINDING = "finding"
    GAP = "gap"
    CONTRADICTION = "contradiction"
    WARNING = "warning"
    DOMAIN_RESULT = "domain_result"
    RESOLUTION_CONTEXT = "resolution_context"
    RESOLUTION_RESULT = "resolution_result"
    COMPOSITION = "composition"
    AGENT_TRACE = "agent_trace"
    COGNITIVE_RESULT = "cognitive_result"
    REASONING_TRACE = "reasoning_trace"
    KNOWLEDGE_PACKAGE = "knowledge_package"
    CROSS_DOMAIN_RESULT = "cross_domain_result"
    CROSS_DOMAIN_TRACE = "cross_domain_trace"
    PRESENTATION_PLAN = "presentation_plan"
    PRESENTATION_VALIDATION_RESULT = "presentation_validation_result"


_GLOBAL_KINDS = frozenset(
    {
        DomainTraceReferenceKind.RESOLUTION_CONTEXT,
        DomainTraceReferenceKind.RESOLUTION_RESULT,
        DomainTraceReferenceKind.COMPOSITION,
        DomainTraceReferenceKind.AGENT_TRACE,
        DomainTraceReferenceKind.COGNITIVE_RESULT,
        DomainTraceReferenceKind.REASONING_TRACE,
        DomainTraceReferenceKind.KNOWLEDGE_PACKAGE,
        DomainTraceReferenceKind.CROSS_DOMAIN_RESULT,
        DomainTraceReferenceKind.CROSS_DOMAIN_TRACE,
        DomainTraceReferenceKind.PRESENTATION_PLAN,
        DomainTraceReferenceKind.PRESENTATION_VALIDATION_RESULT,
    }
)


@dataclass(frozen=True, slots=True)
class DomainTraceReference:
    """One reference and its strict category and ownership."""

    ref_id: str
    kind: DomainTraceReferenceKind
    domain_id: DomainId | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "ref_id", _identifier(self.ref_id, "ref_id"))
        if not isinstance(self.kind, DomainTraceReferenceKind):
            object.__setattr__(self, "kind", DomainTraceReferenceKind(self.kind))
        if self.domain_id is not None:
            object.__setattr__(self, "domain_id", _domain_id(self.domain_id, "domain_id"))
        if (self.kind in _GLOBAL_KINDS) != (self.domain_id is None):
            raise DomainTraceContractError(
                "global references must omit domain_id and domain references must include it",
                field="domain_id",
            )

    def to_dict(self) -> dict[str, str | None]:
        return {"ref_id": self.ref_id, "kind": self.kind.value, "domain_id": str(self.domain_id) if self.domain_id else None}

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> DomainTraceReference:
        _strict_keys(data, {"ref_id", "kind", "domain_id"}, cls.__name__)
        try:
            return cls(ref_id=data["ref_id"], kind=data["kind"], domain_id=data.get("domain_id"))
        except (KeyError, TypeError, ValueError, DomainSerializationError, DomainTraceContractError) as exc:
            raise DomainTraceSerializationError(
                "invalid DomainTraceReference payload",
                field="data",
            ) from exc


@dataclass(frozen=True, slots=True)
class DomainTraceContribution:
    """References contributed by exactly one participating domain."""

    domain_id: DomainId
    role: DomainTraceRole
    references: tuple[DomainTraceReference, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "domain_id", _domain_id(self.domain_id, "domain_id"))
        if not isinstance(self.role, DomainTraceRole):
            object.__setattr__(self, "role", DomainTraceRole(self.role))
        refs = tuple(
            reference if isinstance(reference, DomainTraceReference) else DomainTraceReference.from_dict(reference)
            for reference in self.references
        )
        if any(reference.domain_id != self.domain_id or reference.kind in _GLOBAL_KINDS for reference in refs):
            raise DomainTraceContractError("contribution references must belong to its domain", field="references")
        if len({(reference.ref_id, reference.kind, reference.domain_id) for reference in refs}) != len(refs):
            raise DomainTraceContractError("contribution references must not duplicate", field="references")
        object.__setattr__(self, "references", refs)

    def canonicalized(self) -> DomainTraceContribution:
        return DomainTraceContribution(self.domain_id, self.role, tuple(sorted(self.references, key=_reference_sort_key)))

    def to_dict(self) -> dict[str, Any]:
        return {"domain_id": str(self.domain_id), "role": self.role.value, "references": [item.to_dict() for item in self.references]}

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> DomainTraceContribution:
        _strict_keys(data, {"domain_id", "role", "references"}, cls.__name__)
        try:
            return cls(data["domain_id"], data["role"], tuple(DomainTraceReference.from_dict(item) for item in data.get("references", ())))
        except (KeyError, TypeError, ValueError, DomainSerializationError, DomainTraceContractError, DomainTraceSerializationError) as exc:
            raise DomainTraceSerializationError(
                "invalid DomainTraceContribution payload",
                field="data",
            ) from exc


def _canonical_participants(
    primary_domain: DomainId,
    supporting_domains: Sequence[DomainId | str],
    contributions: Sequence[DomainTraceContribution | Mapping[str, Any]],
) -> tuple[tuple[DomainId, ...], tuple[DomainTraceContribution, ...]]:
    supporting = tuple(_domain_id(value, "supporting_domains") for value in supporting_domains)
    if primary_domain in supporting or len(set(supporting)) != len(supporting):
        raise DomainTraceContractError(
            "supporting_domains must be unique and exclude primary_domain",
            field="supporting_domains",
        )
    canonical_supporting = tuple(sorted(supporting, key=str))
    normalized = tuple(
        DomainTraceContribution.from_dict(item.to_dict())
        if isinstance(item, DomainTraceContribution)
        else DomainTraceContribution.from_dict(item)
        for item in contributions
    )
    domain_ids = tuple(item.domain_id for item in normalized)
    expected = {primary_domain, *canonical_supporting}
    if len(domain_ids) != len(set(domain_ids)) or set(domain_ids) != expected:
        raise DomainTraceContractError(
            "contributions must contain each participating domain once",
            field="contributions",
        )
    by_domain = {item.domain_id: item for item in normalized}
    primary = by_domain[primary_domain]
    if primary.role is not DomainTraceRole.PRIMARY or any(
        by_domain[domain_id].role is not DomainTraceRole.SUPPORTING
        for domain_id in canonical_supporting
    ):
        raise DomainTraceContractError(
            "contribution roles must match participating domains",
            field="contributions",
        )
    ordered = (
        primary.canonicalized(),
        *(by_domain[domain_id].canonicalized() for domain_id in canonical_supporting),
    )
    return canonical_supporting, ordered


def _reference_sort_key(reference: DomainTraceReference) -> tuple[str, str, str]:
    return (reference.kind.value, str(reference.domain_id or ""), reference.ref_id)


def _domain_result_sort_key(reference: DomainResultTraceReference) -> tuple[str, str, str]:
    return (str(reference.domain_id), reference.result_id, reference.trace_id or "")


@dataclass(frozen=True, slots=True)
class DomainResultTraceReference:
    result_id: str
    domain_id: DomainId
    trace_id: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "result_id", _identifier(self.result_id, "result_id"))
        object.__setattr__(self, "domain_id", _domain_id(self.domain_id, "domain_id"))
        if self.trace_id is not None:
            object.__setattr__(self, "trace_id", _identifier(self.trace_id, "trace_id"))

    def to_dict(self) -> dict[str, str | None]:
        return {"result_id": self.result_id, "domain_id": str(self.domain_id), "trace_id": self.trace_id}

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> DomainResultTraceReference:
        _strict_keys(data, {"result_id", "domain_id", "trace_id"}, cls.__name__)
        try:
            return cls(data["result_id"], data["domain_id"], data.get("trace_id"))
        except (KeyError, TypeError, ValueError, DomainSerializationError, DomainTraceContractError) as exc:
            raise DomainTraceSerializationError(
                "invalid DomainResultTraceReference payload",
                field="data",
            ) from exc


@dataclass(frozen=True, slots=True)
class CrossDomainTraceReference:
    result_id: str
    trace_id: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "result_id", _identifier(self.result_id, "result_id"))
        object.__setattr__(self, "trace_id", _identifier(self.trace_id, "trace_id"))

    def to_dict(self) -> dict[str, str]:
        return {"result_id": self.result_id, "trace_id": self.trace_id}

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> CrossDomainTraceReference:
        _strict_keys(data, {"result_id", "trace_id"}, cls.__name__)
        try:
            return cls(data["result_id"], data["trace_id"])
        except (KeyError, TypeError, ValueError, DomainTraceContractError) as exc:
            raise DomainTraceSerializationError(
                "invalid CrossDomainTraceReference payload",
                field="data",
            ) from exc


@dataclass(frozen=True, slots=True)
class DomainTraceReferences:
    """Closed, typed global reference categories."""

    resolution_context_id: str
    resolution_result_id: str
    composition_id: str
    agent_trace_id: str | None = None
    cognitive_result_ids: tuple[str, ...] = ()
    reasoning_trace_ids: tuple[str, ...] = ()
    knowledge_package_ids: tuple[str, ...] = ()
    cross_domain_results: tuple[CrossDomainTraceReference, ...] = ()
    presentation_plan_ids: tuple[str, ...] = ()
    presentation_validation_result_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        for name in ("resolution_context_id", "resolution_result_id", "composition_id"):
            object.__setattr__(self, name, _identifier(getattr(self, name), name))
        if self.agent_trace_id is not None:
            object.__setattr__(self, "agent_trace_id", _identifier(self.agent_trace_id, "agent_trace_id"))
        for name in ("cognitive_result_ids", "reasoning_trace_ids", "knowledge_package_ids", "presentation_plan_ids", "presentation_validation_result_ids"):
            object.__setattr__(self, name, _sorted_ids(getattr(self, name), name))
        pairings = tuple(
            pairing if isinstance(pairing, CrossDomainTraceReference) else CrossDomainTraceReference.from_dict(pairing)
            for pairing in self.cross_domain_results
        )
        if len({pairing.result_id for pairing in pairings}) != len(pairings):
            raise DomainTraceContractError("cross_domain_results must not duplicate", field="cross_domain_results")
        object.__setattr__(self, "cross_domain_results", tuple(sorted(pairings, key=lambda item: item.result_id)))

    def all_references(self) -> tuple[DomainTraceReference, ...]:
        items = [
            DomainTraceReference(self.resolution_context_id, DomainTraceReferenceKind.RESOLUTION_CONTEXT),
            DomainTraceReference(self.resolution_result_id, DomainTraceReferenceKind.RESOLUTION_RESULT),
            DomainTraceReference(self.composition_id, DomainTraceReferenceKind.COMPOSITION),
        ]
        if self.agent_trace_id:
            items.append(DomainTraceReference(self.agent_trace_id, DomainTraceReferenceKind.AGENT_TRACE))
        items.extend(DomainTraceReference(item, DomainTraceReferenceKind.COGNITIVE_RESULT) for item in self.cognitive_result_ids)
        items.extend(DomainTraceReference(item, DomainTraceReferenceKind.REASONING_TRACE) for item in self.reasoning_trace_ids)
        items.extend(DomainTraceReference(item, DomainTraceReferenceKind.KNOWLEDGE_PACKAGE) for item in self.knowledge_package_ids)
        items.extend(DomainTraceReference(item.result_id, DomainTraceReferenceKind.CROSS_DOMAIN_RESULT) for item in self.cross_domain_results)
        items.extend(
            DomainTraceReference(item.trace_id, DomainTraceReferenceKind.CROSS_DOMAIN_TRACE)
            for item in self.cross_domain_results
        )
        items.extend(DomainTraceReference(item, DomainTraceReferenceKind.PRESENTATION_PLAN) for item in self.presentation_plan_ids)
        items.extend(DomainTraceReference(item, DomainTraceReferenceKind.PRESENTATION_VALIDATION_RESULT) for item in self.presentation_validation_result_ids)
        return tuple(sorted(items, key=_reference_sort_key))

    def to_dict(self) -> dict[str, Any]:
        return {
            "resolution_context_id": self.resolution_context_id, "resolution_result_id": self.resolution_result_id,
            "composition_id": self.composition_id, "agent_trace_id": self.agent_trace_id,
            "cognitive_result_ids": list(self.cognitive_result_ids), "reasoning_trace_ids": list(self.reasoning_trace_ids),
            "knowledge_package_ids": list(self.knowledge_package_ids),
            "cross_domain_results": [item.to_dict() for item in self.cross_domain_results],
            "presentation_plan_ids": list(self.presentation_plan_ids),
            "presentation_validation_result_ids": list(self.presentation_validation_result_ids),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> DomainTraceReferences:
        _strict_keys(data, {field_name for field_name in cls.__dataclass_fields__}, cls.__name__)
        try:
            return cls(**{**data, "cross_domain_results": tuple(CrossDomainTraceReference.from_dict(item) for item in data.get("cross_domain_results", ()))})
        except (KeyError, TypeError, ValueError, DomainSerializationError, DomainTraceContractError, DomainTraceSerializationError) as exc:
            raise DomainTraceSerializationError(
                "invalid DomainTraceReferences payload",
                field="data",
            ) from exc


@dataclass(frozen=True, slots=True)
class DomainTraceAssemblyRequest:
    request_id: str
    primary_domain: DomainId
    contributions: tuple[DomainTraceContribution, ...]
    references: DomainTraceReferences
    started_at: datetime
    completed_at: datetime
    supporting_domains: tuple[DomainId, ...] = ()
    goal_id: str | None = None
    domain_results: tuple[DomainResultTraceReference, ...] = ()
    status: DomainTraceStatus = DomainTraceStatus.COMPLETED
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "request_id", _identifier(self.request_id, "request_id"))
        object.__setattr__(self, "primary_domain", _domain_id(self.primary_domain, "primary_domain"))
        if self.goal_id is not None:
            object.__setattr__(self, "goal_id", _identifier(self.goal_id, "goal_id"))
        supporting, contributions = _canonical_participants(
            self.primary_domain, self.supporting_domains, self.contributions
        )
        object.__setattr__(self, "supporting_domains", supporting)
        object.__setattr__(self, "contributions", contributions)
        references = (
            DomainTraceReferences.from_dict(self.references.to_dict())
            if isinstance(self.references, DomainTraceReferences)
            else DomainTraceReferences.from_dict(self.references)
        )
        object.__setattr__(self, "references", references)
        results = tuple(
            DomainResultTraceReference.from_dict(item.to_dict())
            if isinstance(item, DomainResultTraceReference)
            else DomainResultTraceReference.from_dict(item)
            for item in self.domain_results
        )
        if len({item.result_id for item in results}) != len(results):
            raise DomainTraceContractError("domain_results must not duplicate", field="domain_results")
        object.__setattr__(self, "domain_results", tuple(sorted(results, key=_domain_result_sort_key)))
        _validate_domain_result_coverage(contributions, self.domain_results)
        _validate_global_id_uniqueness(contributions, references)
        if not isinstance(self.status, DomainTraceStatus):
            object.__setattr__(self, "status", DomainTraceStatus(self.status))
        object.__setattr__(self, "started_at", _aware(self.started_at, "started_at"))
        object.__setattr__(self, "completed_at", _aware(self.completed_at, "completed_at"))
        if self.completed_at < self.started_at:
            raise DomainTraceContractError("completed_at must not precede started_at", field="completed_at")
        object.__setattr__(self, "metadata", _freeze_metadata(self.metadata))

    def to_dict(self) -> dict[str, Any]:
        return {
            "request_id": self.request_id, "goal_id": self.goal_id,
            "primary_domain": str(self.primary_domain), "supporting_domains": [str(item) for item in self.supporting_domains],
            "contributions": [item.to_dict() for item in self.contributions], "references": self.references.to_dict(),
            "domain_results": [item.to_dict() for item in self.domain_results], "status": self.status.value,
            "started_at": self.started_at.isoformat(), "completed_at": self.completed_at.isoformat(), "metadata": _thaw(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> DomainTraceAssemblyRequest:
        allowed = {field_name for field_name in cls.__dataclass_fields__}
        _strict_keys(data, allowed, cls.__name__)
        try:
            return cls(
                request_id=data["request_id"], goal_id=data.get("goal_id"), primary_domain=data["primary_domain"],
                supporting_domains=tuple(data.get("supporting_domains", ())),
                contributions=tuple(DomainTraceContribution.from_dict(item) for item in data["contributions"]),
                references=DomainTraceReferences.from_dict(data["references"]),
                domain_results=tuple(DomainResultTraceReference.from_dict(item) for item in data.get("domain_results", ())),
                status=data.get("status", DomainTraceStatus.COMPLETED.value), started_at=datetime.fromisoformat(data["started_at"]),
                completed_at=datetime.fromisoformat(data["completed_at"]), metadata=data.get("metadata", {}),
            )
        except (
            KeyError,
            TypeError,
            ValueError,
            DomainSerializationError,
            DomainTraceContractError,
        ) as exc:
            raise DomainTraceSerializationError(
                "invalid DomainTraceAssemblyRequest payload",
                field="data",
            ) from exc


@dataclass(frozen=True, slots=True)
class DomainTrace:
    """Final, immutable, persistence-independent reference-only trace."""

    id: str
    digest: str
    request_id: str
    primary_domain: DomainId
    supporting_domains: tuple[DomainId, ...]
    contributions: tuple[DomainTraceContribution, ...]
    references: DomainTraceReferences
    domain_results: tuple[DomainResultTraceReference, ...]
    status: DomainTraceStatus
    started_at: datetime
    completed_at: datetime
    duration_ms: int
    goal_id: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "id", _identifier(self.id, "id"))
        if not isinstance(self.digest, str) or not re.fullmatch(r"[0-9a-f]{64}", self.digest):
            raise DomainTraceContractError("digest must be a SHA-256 hex digest", field="digest")
        object.__setattr__(self, "request_id", _identifier(self.request_id, "request_id"))
        object.__setattr__(self, "primary_domain", _domain_id(self.primary_domain, "primary_domain"))
        supporting, contributions = _canonical_participants(
            self.primary_domain, self.supporting_domains, self.contributions
        )
        object.__setattr__(self, "supporting_domains", supporting)
        object.__setattr__(self, "contributions", contributions)
        references = (
            DomainTraceReferences.from_dict(self.references.to_dict())
            if isinstance(self.references, DomainTraceReferences)
            else DomainTraceReferences.from_dict(self.references)
        )
        object.__setattr__(self, "references", references)
        results = tuple(
            DomainResultTraceReference.from_dict(item.to_dict())
            if isinstance(item, DomainResultTraceReference)
            else DomainResultTraceReference.from_dict(item)
            for item in self.domain_results
        )
        if any(item.trace_id != self.id for item in results):
            raise DomainTraceContractError("DomainResult trace IDs must equal DomainTrace.id", field="domain_results")
        object.__setattr__(self, "domain_results", tuple(sorted(results, key=_domain_result_sort_key)))
        _validate_domain_result_coverage(contributions, self.domain_results)
        _validate_global_id_uniqueness(contributions, references)
        if not isinstance(self.status, DomainTraceStatus):
            object.__setattr__(self, "status", DomainTraceStatus(self.status))
        object.__setattr__(self, "started_at", _aware(self.started_at, "started_at"))
        object.__setattr__(self, "completed_at", _aware(self.completed_at, "completed_at"))
        expected_duration = int((self.completed_at - self.started_at).total_seconds() * 1000)
        if self.completed_at < self.started_at or self.duration_ms != expected_duration:
            raise DomainTraceContractError("duration_ms must equal timestamps", field="duration_ms")
        if self.goal_id is not None:
            object.__setattr__(self, "goal_id", _identifier(self.goal_id, "goal_id"))
        object.__setattr__(self, "metadata", _freeze_metadata(self.metadata))

    def _digest_payload(self) -> dict[str, Any]:
        payload = self.to_dict()
        payload.pop("id")
        payload.pop("digest")
        for item in payload["domain_results"]:
            item["trace_id"] = None
        return payload

    def calculate_digest(self) -> str:
        return hashlib.sha256(_canonical_json(self._digest_payload()).encode("utf-8")).hexdigest()

    @property
    def canonical_id(self) -> str:
        return f"domain-trace:{self.calculate_digest()[:24]}"

    def all_references(self) -> tuple[DomainTraceReference, ...]:
        items = [reference for contribution in self.contributions for reference in contribution.references]
        return tuple(sorted((*items, *self.references.all_references()), key=_reference_sort_key))

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id, "digest": self.digest, "request_id": self.request_id, "goal_id": self.goal_id,
            "primary_domain": str(self.primary_domain), "supporting_domains": [str(item) for item in self.supporting_domains],
            "contributions": [item.to_dict() for item in self.contributions], "references": self.references.to_dict(),
            "domain_results": [item.to_dict() for item in self.domain_results], "status": self.status.value,
            "started_at": self.started_at.isoformat(), "completed_at": self.completed_at.isoformat(),
            "duration_ms": self.duration_ms, "metadata": _thaw(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> DomainTrace:
        known = {field_name for field_name in cls.__dataclass_fields__}
        _strict_keys(data, known, cls.__name__)
        try:
            return cls(
                id=data["id"], digest=data["digest"], request_id=data["request_id"], goal_id=data.get("goal_id"),
                primary_domain=data["primary_domain"], supporting_domains=tuple(data.get("supporting_domains", ())),
                contributions=tuple(DomainTraceContribution.from_dict(item) for item in data["contributions"]),
                references=DomainTraceReferences.from_dict(data["references"]),
                domain_results=tuple(DomainResultTraceReference.from_dict(item) for item in data.get("domain_results", ())),
                status=data["status"], started_at=datetime.fromisoformat(data["started_at"]),
                completed_at=datetime.fromisoformat(data["completed_at"]), duration_ms=data["duration_ms"], metadata=data.get("metadata", {}),
            )
        except (
            KeyError,
            TypeError,
            ValueError,
            DomainSerializationError,
            DomainTraceContractError,
        ) as exc:
            raise DomainTraceSerializationError(
                "invalid DomainTrace payload",
                field="data",
            ) from exc


@dataclass(frozen=True, slots=True)
class DomainTraceReferenceInventory:
    """External typed inventory used to validate a DomainTrace."""

    references: tuple[DomainTraceReference, ...]
    expected_primary_domain: DomainId
    resolution_result_domains: DomainTraceDomainSelection
    composition_domains: DomainTraceDomainSelection
    expected_supporting_domains: tuple[DomainId, ...] = ()
    domain_results: tuple[DomainResultTraceReference, ...] = ()
    cross_domain_results: tuple[CrossDomainTraceReference, ...] = ()

    def __post_init__(self) -> None:
        refs = tuple(item if isinstance(item, DomainTraceReference) else DomainTraceReference.from_dict(item) for item in self.references)
        identity_by_id: dict[str, tuple[DomainTraceReferenceKind, DomainId | None]] = {}
        for item in refs:
            identity = (item.kind, item.domain_id)
            if item.ref_id in identity_by_id:
                raise DomainTraceContractError("reference IDs must resolve uniquely", field="references")
            identity_by_id[item.ref_id] = identity
        object.__setattr__(self, "references", tuple(sorted(refs, key=_reference_sort_key)))
        object.__setattr__(self, "expected_primary_domain", _domain_id(self.expected_primary_domain, "expected_primary_domain"))
        supporting = tuple(_domain_id(item, "expected_supporting_domains") for item in self.expected_supporting_domains)
        if self.expected_primary_domain in supporting or len(set(supporting)) != len(supporting):
            raise DomainTraceContractError("expected_supporting_domains must be unique and exclude primary", field="expected_supporting_domains")
        object.__setattr__(self, "expected_supporting_domains", tuple(sorted(supporting, key=str)))
        if not isinstance(self.resolution_result_domains, DomainTraceDomainSelection):
            object.__setattr__(self, "resolution_result_domains", DomainTraceDomainSelection.from_dict(self.resolution_result_domains))
        if not isinstance(self.composition_domains, DomainTraceDomainSelection):
            object.__setattr__(self, "composition_domains", DomainTraceDomainSelection.from_dict(self.composition_domains))
        results = tuple(item if isinstance(item, DomainResultTraceReference) else DomainResultTraceReference.from_dict(item) for item in self.domain_results)
        cross = tuple(item if isinstance(item, CrossDomainTraceReference) else CrossDomainTraceReference.from_dict(item) for item in self.cross_domain_results)
        if len({item.result_id for item in results}) != len(results):
            raise DomainTraceContractError("inventory domain result pairings must not duplicate", field="domain_results")
        if len({item.result_id for item in cross}) != len(cross):
            raise DomainTraceContractError("inventory cross-domain result pairings must not duplicate", field="cross_domain_results")
        object.__setattr__(self, "domain_results", tuple(sorted(results, key=lambda item: item.result_id)))
        object.__setattr__(self, "cross_domain_results", tuple(sorted(cross, key=lambda item: item.result_id)))

    def to_dict(self) -> dict[str, Any]:
        return {
            "references": [item.to_dict() for item in self.references],
            "expected_primary_domain": str(self.expected_primary_domain),
            "expected_supporting_domains": [str(item) for item in self.expected_supporting_domains],
            "resolution_result_domains": self.resolution_result_domains.to_dict(),
            "composition_domains": self.composition_domains.to_dict(),
            "domain_results": [item.to_dict() for item in self.domain_results],
            "cross_domain_results": [item.to_dict() for item in self.cross_domain_results],
        }

    @property
    def digest(self) -> str:
        return hashlib.sha256(_canonical_json(self.to_dict()).encode("utf-8")).hexdigest()

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> DomainTraceReferenceInventory:
        allowed = {field_name for field_name in cls.__dataclass_fields__}
        _strict_keys(data, allowed, cls.__name__)
        try:
            return cls(
                references=tuple(DomainTraceReference.from_dict(item) for item in data["references"]),
                expected_primary_domain=data["expected_primary_domain"],
                expected_supporting_domains=tuple(data.get("expected_supporting_domains", ())),
                resolution_result_domains=DomainTraceDomainSelection.from_dict(data["resolution_result_domains"]),
                composition_domains=DomainTraceDomainSelection.from_dict(data["composition_domains"]),
                domain_results=tuple(DomainResultTraceReference.from_dict(item) for item in data.get("domain_results", ())),
                cross_domain_results=tuple(CrossDomainTraceReference.from_dict(item) for item in data.get("cross_domain_results", ())),
            )
        except (
            KeyError,
            TypeError,
            ValueError,
            DomainSerializationError,
            DomainTraceContractError,
        ) as exc:
            raise DomainTraceSerializationError(
                "invalid DomainTraceReferenceInventory payload",
                field="data",
            ) from exc


class DomainTraceValidationCode(str, Enum):
    MISSING_REFERENCE = "missing_reference"
    UNEXPECTED_REFERENCE = "unexpected_reference"
    DUPLICATE_REFERENCE = "duplicate_reference"
    KIND_MISMATCH = "kind_mismatch"
    DOMAIN_MISMATCH = "domain_mismatch"
    PRIMARY_SUPPORTING_MISMATCH = "primary_supporting_mismatch"
    DUPLICATE_CONTRIBUTION = "duplicate_contribution"
    FOREIGN_CONTRIBUTION = "foreign_contribution"
    CROSS_DOMAIN_PAIRING_MISMATCH = "cross_domain_pairing_mismatch"
    DOMAIN_RESULT_PAIRING_MISMATCH = "domain_result_pairing_mismatch"
    INVALID_TIMESTAMP = "invalid_timestamp"
    INVALID_DURATION = "invalid_duration"
    UNKNOWN_STATUS = "unknown_status"
    ID_DIGEST_MISMATCH = "id_digest_mismatch"
    UNSAFE_METADATA = "unsafe_metadata"
    INLINE_CONTENT = "inline_content"
    INLINE_CONTENT_DETECTED = "inline_content_detected"
    FORBIDDEN_FIELD = "forbidden_field"
    AUTHORITATIVE_DOMAIN_MISMATCH = "authoritative_domain_mismatch"
    REFERENCE_ID_COLLISION = "reference_id_collision"
    DOMAIN_RESULT_COVERAGE_MISMATCH = "domain_result_coverage_mismatch"
    INVALID_DOMAIN_ROLE = "invalid_domain_role"
    REFERENCE_KIND_MISMATCH = "reference_kind_mismatch"
    REFERENCE_DOMAIN_MISMATCH = "reference_domain_mismatch"
    INVALID_TIMESTAMP_ORDER = "invalid_timestamp_order"
    INVALID_TRACE_ID = "invalid_trace_id"
    INVALID_TRACE_DIGEST = "invalid_trace_digest"
    INVALID_TRACE_CONTRACT = "invalid_trace_contract"


class DomainTraceValidationState(str, Enum):
    VALID = "valid"
    BLOCKED = "blocked"


@dataclass(frozen=True, slots=True)
class DomainTraceValidationResult:
    valid: bool
    codes: tuple[DomainTraceValidationCode, ...] = ()
    missing_references: tuple[str, ...] = ()
    unexpected_references: tuple[str, ...] = ()
    duplicate_references: tuple[str, ...] = ()
    reference_kind_mismatches: tuple[str, ...] = ()
    reference_domain_mismatches: tuple[str, ...] = ()
    invariant_failures: tuple[str, ...] = ()
    trace_digest: str | None = None
    inventory_digest: str | None = None

    def __post_init__(self) -> None:
        codes = tuple(item if isinstance(item, DomainTraceValidationCode) else DomainTraceValidationCode(item) for item in self.codes)
        object.__setattr__(self, "codes", tuple(dict.fromkeys(codes)))
        for name in ("missing_references", "unexpected_references", "duplicate_references", "reference_kind_mismatches", "reference_domain_mismatches", "invariant_failures"):
            object.__setattr__(self, name, _sorted_diagnostics(getattr(self, name), name))
        for name in ("trace_digest", "inventory_digest"):
            value = getattr(self, name)
            if value is not None and (not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{64}", value)):
                raise DomainTraceContractError(f"{name} must be a SHA-256 hex digest", field=name)
        has_diagnostics = any(
            getattr(self, name)
            for name in (
                "missing_references", "unexpected_references", "duplicate_references",
                "reference_kind_mismatches", "reference_domain_mismatches", "invariant_failures",
            )
        )
        if not isinstance(self.valid, bool):
            raise DomainTraceContractError("valid must be a boolean", field="valid")
        if self.valid and (self.codes or has_diagnostics):
            raise DomainTraceContractError("valid results cannot contain failures", field="valid")
        if not self.valid and not (self.codes or has_diagnostics):
            raise DomainTraceContractError("invalid results require a failure", field="valid")

    @property
    def missing_refs(self) -> tuple[str, ...]:
        return self.missing_references

    @property
    def unexpected_refs(self) -> tuple[str, ...]:
        return self.unexpected_references

    @property
    def state(self) -> DomainTraceValidationState:
        return DomainTraceValidationState.VALID if self.valid else DomainTraceValidationState.BLOCKED

    def to_dict(self) -> dict[str, Any]:
        return {
            "valid": self.valid, "codes": [item.value for item in self.codes],
            "missing_references": list(self.missing_references), "unexpected_references": list(self.unexpected_references),
            "duplicate_references": list(self.duplicate_references), "reference_kind_mismatches": list(self.reference_kind_mismatches),
            "reference_domain_mismatches": list(self.reference_domain_mismatches), "invariant_failures": list(self.invariant_failures),
            "trace_digest": self.trace_digest, "inventory_digest": self.inventory_digest,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> DomainTraceValidationResult:
        allowed = {field_name for field_name in cls.__dataclass_fields__}
        _strict_keys(data, allowed, cls.__name__)
        try:
            return cls(
                valid=data["valid"], codes=tuple(data.get("codes", ())),
                missing_references=tuple(data.get("missing_references", ())),
                unexpected_references=tuple(data.get("unexpected_references", ())),
                duplicate_references=tuple(data.get("duplicate_references", ())),
                reference_kind_mismatches=tuple(data.get("reference_kind_mismatches", ())),
                reference_domain_mismatches=tuple(data.get("reference_domain_mismatches", ())),
                invariant_failures=tuple(data.get("invariant_failures", ())),
                trace_digest=data.get("trace_digest"), inventory_digest=data.get("inventory_digest"),
            )
        except (KeyError, TypeError, ValueError, DomainTraceContractError) as exc:
            raise DomainTraceSerializationError("invalid DomainTraceValidationResult payload", field="data") from exc
