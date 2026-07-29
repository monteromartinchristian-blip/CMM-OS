"""Phase 8.23 – provider-independent Knowledge Packages.

Packages are immutable snapshots assembled from the existing knowledge model and
retrieval layer.  They contain structured references, never provider prompts or
model-specific payloads.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from types import MappingProxyType
from typing import Any, Protocol

from cmm.cognitive.enums import KnowledgeKind, ResourcePermissionOperation
from cmm.cognitive.errors import InvalidKnowledgePackageError
from cmm.cognitive.knowledge import Contradiction, KnowledgeItem
from cmm.cognitive.query import KnowledgeQuery
from cmm.cognitive.resources import Resource
from cmm.cognitive.retrieval import KnowledgeRetriever
from cmm.cognitive.store_contracts import KnowledgeStoreProtocol

SCHEMA_VERSION = 1


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _aware(value: datetime | None, name: str) -> None:
    if value is not None and (not isinstance(value, datetime) or value.tzinfo is None):
        raise InvalidKnowledgePackageError(f"{name} must be timezone-aware")


def _jsonable(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, KnowledgeItem):
        payload = value.serialize()
        temporal_scope = payload.get("temporal_scope")
        if isinstance(temporal_scope, dict):
            temporal_scope.pop("validity_status", None)
        return _jsonable(payload)
    if isinstance(value, Resource):
        payload = value.to_dict()
        temporal_scope = payload.get("temporal_scope")
        if isinstance(temporal_scope, dict):
            temporal_scope.pop("expired", None)
        for permission in payload.get("permissions", ()):
            if isinstance(permission, dict):
                permission.pop("expired", None)
        return _jsonable(payload)
    if hasattr(value, "serialize") and callable(value.serialize):
        return _jsonable(value.serialize())
    if hasattr(value, "to_dict") and callable(value.to_dict):
        return _jsonable(value.to_dict())
    if isinstance(value, Mapping):
        return {str(key): _jsonable(value[key]) for key in sorted(value, key=str)}
    if isinstance(value, (tuple, list)):
        return [_jsonable(item) for item in value]
    if isinstance(value, set):
        return [_jsonable(item) for item in sorted(value, key=str)]
    return value


def _parse_datetime(value: Any, name: str, *, default: datetime | None = None) -> datetime | None:
    if value is None:
        return default
    if isinstance(value, datetime):
        result = value
    elif isinstance(value, str):
        try:
            result = datetime.fromisoformat(value)
        except ValueError as exc:
            raise InvalidKnowledgePackageError(f"Invalid ISO timestamp for {name}") from exc
    else:
        raise InvalidKnowledgePackageError(f"{name} must be a datetime or ISO string")
    _aware(result, name)
    return result


def _sequence(payload: Any, name: str) -> Sequence[Any]:
    if payload is None:
        return ()
    if isinstance(payload, (str, bytes, bytearray, Mapping)) or not isinstance(payload, Sequence):
        raise InvalidKnowledgePackageError(f"{name} must be a sequence")
    return payload


def _items(payload: Any, name: str = "package categories") -> tuple[KnowledgeItem, ...]:
    result: list[KnowledgeItem] = []
    for value in _sequence(payload, name):
        if isinstance(value, KnowledgeItem):
            result.append(value)
        elif isinstance(value, Mapping):
            result.append(KnowledgeItem.from_mapping(value))
        else:
            raise InvalidKnowledgePackageError("package categories must contain KnowledgeItem values")
    return tuple(result)


def _contradictions(payload: Any) -> tuple[Contradiction, ...]:
    result: list[Contradiction] = []
    for value in _sequence(payload, "contradictions"):
        if isinstance(value, Contradiction):
            result.append(value)
        elif isinstance(value, Mapping):
            result.append(Contradiction.from_mapping(value))
        else:
            raise InvalidKnowledgePackageError("contradictions must contain Contradiction values")
    return tuple(result)


@dataclass(frozen=True, slots=True)
class KnowledgePackage:
    """Immutable, versioned context snapshot for one objective."""

    id: str
    objective: str
    profile: str | None = None
    domain: str | None = None
    session_id: str | None = None
    current_state: tuple[Any, ...] = ()
    timeline: tuple[Any, ...] = ()
    active_goals: tuple[Any, ...] = ()
    facts: tuple[KnowledgeItem, ...] = ()
    observations: tuple[KnowledgeItem, ...] = ()
    inferences: tuple[KnowledgeItem, ...] = ()
    hypotheses: tuple[KnowledgeItem, ...] = ()
    other_knowledge: tuple[KnowledgeItem, ...] = ()
    contradictions: tuple[Contradiction, ...] = ()
    unknowns: tuple[Any, ...] = ()
    constraints: tuple[Any, ...] = ()
    preferences: tuple[Any, ...] = ()
    relevant_memory: tuple[Any, ...] = ()
    prior_reasoning: tuple[Any, ...] = ()
    resources: tuple[Resource, ...] = ()
    missing_information: tuple[Any, ...] = ()
    reasoning_profile: Mapping[str, Any] = field(default_factory=dict)
    domain_instructions: Mapping[str, Any] = field(default_factory=dict)
    privacy: Mapping[str, Any] = field(default_factory=dict)
    temporal_scope: Mapping[str, Any] = field(default_factory=dict)
    provenance: tuple[Any, ...] = ()
    created_at: datetime = field(default_factory=_utc_now)
    valid_until: datetime | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)
    schema_version: int = SCHEMA_VERSION

    def __post_init__(self) -> None:
        if not isinstance(self.id, str) or not self.id.strip():
            raise InvalidKnowledgePackageError("KnowledgePackage.id must not be empty")
        if not isinstance(self.objective, str) or not self.objective.strip():
            raise InvalidKnowledgePackageError("KnowledgePackage.objective must not be empty")
        if self.schema_version != SCHEMA_VERSION:
            raise InvalidKnowledgePackageError(f"Unsupported KnowledgePackage schema_version: {self.schema_version}")
        _aware(self.created_at, "created_at")
        _aware(self.valid_until, "valid_until")
        if self.valid_until is not None and self.valid_until < self.created_at:
            raise InvalidKnowledgePackageError("valid_until must be greater than or equal to created_at")

        categories = (
            self.facts,
            self.observations,
            self.inferences,
            self.hypotheses,
            self.other_knowledge,
        )
        if any(not isinstance(item, KnowledgeItem) for category in categories for item in category):
            raise InvalidKnowledgePackageError("epistemic categories must contain KnowledgeItem values")
        expected_kinds = (
            ("facts", self.facts, KnowledgeKind.FACT),
            ("observations", self.observations, KnowledgeKind.OBSERVATION),
            ("inferences", self.inferences, KnowledgeKind.INFERENCE),
            ("hypotheses", self.hypotheses, KnowledgeKind.HYPOTHESIS),
        )
        for field_name, values, expected in expected_kinds:
            if any(item.kind is not expected for item in values):
                raise InvalidKnowledgePackageError(
                    f"{field_name} may only contain {expected.value} KnowledgeItems"
                )
        reserved = {
            KnowledgeKind.FACT,
            KnowledgeKind.OBSERVATION,
            KnowledgeKind.INFERENCE,
            KnowledgeKind.HYPOTHESIS,
        }
        if any(item.kind in reserved for item in self.other_knowledge):
            raise InvalidKnowledgePackageError(
                "other_knowledge cannot contain reserved epistemic kinds"
            )
        ids = [item.id for category in categories for item in category]
        if len(ids) != len(set(ids)):
            raise InvalidKnowledgePackageError("epistemic categories must not contain duplicate item ids")
        contradiction_ids = [item.id for item in self.contradictions]
        if len(contradiction_ids) != len(set(contradiction_ids)):
            raise InvalidKnowledgePackageError("contradictions must not contain duplicate ids")
        if any(not isinstance(item, Contradiction) for item in self.contradictions):
            raise InvalidKnowledgePackageError("contradictions must contain Contradiction values")
        if any(not isinstance(item, Resource) for item in self.resources):
            raise InvalidKnowledgePackageError("resources must contain Resource values")

        for name in ("current_state", "timeline", "active_goals", "unknowns", "constraints", "preferences", "relevant_memory", "prior_reasoning", "missing_information", "provenance"):
            object.__setattr__(self, name, tuple(getattr(self, name) or ()))
        for name in ("facts", "observations", "inferences", "hypotheses", "other_knowledge", "contradictions", "resources"):
            object.__setattr__(self, name, tuple(getattr(self, name) or ()))
        for name in ("reasoning_profile", "domain_instructions", "privacy", "temporal_scope", "metadata"):
            object.__setattr__(self, name, MappingProxyType(dict(getattr(self, name) or {})))

    def serialize(self) -> dict[str, Any]:
        return _jsonable({
            "schema_version": self.schema_version,
            "id": self.id,
            "objective": self.objective,
            "profile": self.profile,
            "domain": self.domain,
            "session_id": self.session_id,
            "current_state": self.current_state,
            "timeline": self.timeline,
            "active_goals": self.active_goals,
            "facts": self.facts,
            "observations": self.observations,
            "inferences": self.inferences,
            "hypotheses": self.hypotheses,
            "other_knowledge": self.other_knowledge,
            "contradictions": self.contradictions,
            "unknowns": self.unknowns,
            "constraints": self.constraints,
            "preferences": self.preferences,
            "relevant_memory": self.relevant_memory,
            "prior_reasoning": self.prior_reasoning,
            "resources": self.resources,
            "missing_information": self.missing_information,
            "reasoning_profile": self.reasoning_profile,
            "domain_instructions": self.domain_instructions,
            "privacy": self.privacy,
            "temporal_scope": self.temporal_scope,
            "provenance": self.provenance,
            "created_at": self.created_at,
            "valid_until": self.valid_until,
            "metadata": self.metadata,
        })

    def to_dict(self) -> dict[str, Any]:
        return self.serialize()

    @classmethod
    def from_mapping(cls, payload: Mapping[str, Any]) -> KnowledgePackage:
        if not isinstance(payload, Mapping):
            raise InvalidKnowledgePackageError("payload must be a mapping")
        return cls(
            id=payload.get("id", ""),
            objective=payload.get("objective", ""),
            profile=payload.get("profile"),
            domain=payload.get("domain"),
            session_id=payload.get("session_id"),
            current_state=tuple(payload.get("current_state") or ()),
            timeline=tuple(payload.get("timeline") or ()),
            active_goals=tuple(payload.get("active_goals") or ()),
            facts=_items(payload.get("facts")),
            observations=_items(payload.get("observations")),
            inferences=_items(payload.get("inferences")),
            hypotheses=_items(payload.get("hypotheses")),
            other_knowledge=_items(payload.get("other_knowledge")),
            contradictions=_contradictions(payload.get("contradictions")),
            unknowns=tuple(payload.get("unknowns") or ()),
            constraints=tuple(payload.get("constraints") or ()),
            preferences=tuple(payload.get("preferences") or ()),
            relevant_memory=tuple(payload.get("relevant_memory") or ()),
            prior_reasoning=tuple(payload.get("prior_reasoning") or ()),
            resources=tuple(
                Resource.from_dict(value) if isinstance(value, Mapping) else value
                for value in _sequence(payload.get("resources"), "resources")
            ),
            missing_information=tuple(payload.get("missing_information") or ()),
            reasoning_profile=dict(payload.get("reasoning_profile") or {}),
            domain_instructions=dict(payload.get("domain_instructions") or {}),
            privacy=dict(payload.get("privacy") or {}),
            temporal_scope=dict(payload.get("temporal_scope") or {}),
            provenance=tuple(payload.get("provenance") or ()),
            created_at=_parse_datetime(payload.get("created_at"), "created_at", default=_utc_now()) or _utc_now(),
            valid_until=_parse_datetime(payload.get("valid_until"), "valid_until"),
            metadata=dict(payload.get("metadata") or {}),
            schema_version=payload.get("schema_version", 0),
        )

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> KnowledgePackage:
        return cls.from_mapping(data)


@dataclass(frozen=True, slots=True)
class KnowledgePackageRequest:
    objective: str
    profile: str | None = None
    domain: str | None = None
    session_id: str | None = None
    query: KnowledgeQuery | Mapping[str, Any] | None = None
    max_items: int | None = None
    max_resources: int | None = None
    max_contradictions: int | None = None
    max_memory: int | None = None
    max_prior_reasoning: int | None = None
    temporal_scope: Mapping[str, Any] = field(default_factory=dict)
    required_categories: tuple[KnowledgeKind, ...] = ()
    include_contradictions: bool = True
    include_resources: bool = True
    include_prior_reasoning: bool = True
    missing_information: tuple[Any, ...] = ()
    relevant_memory: tuple[Any, ...] = ()
    prior_reasoning: tuple[Any, ...] = ()
    permission_context: Mapping[str, Any] = field(default_factory=dict)
    privacy: Mapping[str, Any] = field(default_factory=dict)
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.objective, str) or not self.objective.strip():
            raise InvalidKnowledgePackageError("objective must not be empty")
        if self.query is not None and not isinstance(self.query, KnowledgeQuery):
            if isinstance(self.query, Mapping):
                object.__setattr__(self, "query", KnowledgeQuery.from_mapping(self.query))
            else:
                raise InvalidKnowledgePackageError("query must be a KnowledgeQuery or mapping")
        for name in ("max_items", "max_resources", "max_contradictions", "max_memory", "max_prior_reasoning"):
            value = getattr(self, name)
            if value is not None and (isinstance(value, bool) or not isinstance(value, int) or value < 0):
                raise InvalidKnowledgePackageError(f"{name} must be a non-negative integer")
        categories: list[KnowledgeKind] = []
        for value in self.required_categories or ():
            try:
                categories.append(value if isinstance(value, KnowledgeKind) else KnowledgeKind(value))
            except (TypeError, ValueError) as exc:
                raise InvalidKnowledgePackageError(f"Invalid required category: {value}") from exc
        object.__setattr__(self, "required_categories", tuple(dict.fromkeys(categories)))
        for name in ("missing_information", "relevant_memory", "prior_reasoning"):
            value = getattr(self, name)
            if isinstance(value, (str, bytes, bytearray, Mapping)):
                raise InvalidKnowledgePackageError(f"{name} must be a sequence")
            object.__setattr__(self, name, tuple(value or ()))
        object.__setattr__(self, "permission_context", MappingProxyType(dict(self.permission_context or {})))
        object.__setattr__(self, "privacy", MappingProxyType(dict(self.privacy or {})))
        object.__setattr__(self, "temporal_scope", MappingProxyType(dict(self.temporal_scope or {})))
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata or {})))


class InclusionPolicy(Protocol):
    def __call__(self, candidate: KnowledgeItem | Resource, context: Mapping[str, Any]) -> bool: ...


class KnowledgePackageBuilder:
    """Build relevant packages from an existing store and retriever."""

    def __init__(
        self,
        store: KnowledgeStoreProtocol,
        *,
        resources: Iterable[Resource] = (),
        inclusion_policy: InclusionPolicy | None = None,
    ) -> None:
        if not isinstance(store, KnowledgeStoreProtocol):
            raise InvalidKnowledgePackageError("store must implement KnowledgeStoreProtocol")
        self._retriever = KnowledgeRetriever(store)
        self._resources = tuple(resources)
        self._inclusion_policy = inclusion_policy

    def _allowed(self, candidate: KnowledgeItem | Resource, request: KnowledgePackageRequest) -> bool:
        if isinstance(candidate, Resource) and not candidate.permits(
            ResourcePermissionOperation.READ,
            actor_id=request.permission_context.get("actor_id"),
            domain=request.domain,
        ):
            return False
        if self._inclusion_policy is None:
            return True
        return bool(self._inclusion_policy(candidate, request.permission_context))

    @staticmethod
    def _package_id(request: KnowledgePackageRequest) -> str:
        payload = {
            "objective": " ".join(request.objective.casefold().split()),
            "profile": request.profile,
            "domain": request.domain,
            "session_id": request.session_id,
            "query": request.query.serialize() if isinstance(request.query, KnowledgeQuery) else None,
            "max_items": request.max_items,
            "max_resources": request.max_resources,
            "max_contradictions": request.max_contradictions,
            "max_memory": request.max_memory,
            "max_prior_reasoning": request.max_prior_reasoning,
            "temporal_scope": request.temporal_scope,
            "required_categories": request.required_categories,
            "include_contradictions": request.include_contradictions,
            "include_resources": request.include_resources,
            "include_prior_reasoning": request.include_prior_reasoning,
            "missing_information": request.missing_information,
            "relevant_memory": request.relevant_memory,
            "prior_reasoning": request.prior_reasoning,
            "privacy": request.privacy,
        }
        encoded = json.dumps(_jsonable(payload), sort_keys=True, separators=(",", ":"))
        return f"knowledge-package:{hashlib.sha256(encoded.encode()).hexdigest()[:24]}"

    @staticmethod
    def _terms(objective: str) -> tuple[str, ...]:
        return tuple(dict.fromkeys(re.findall(r"[\w-]{3,}", objective.casefold())))

    def build(self, request: KnowledgePackageRequest) -> KnowledgePackage:
        if not isinstance(request, KnowledgePackageRequest):
            raise InvalidKnowledgePackageError("request must be a KnowledgePackageRequest")
        query = request.query
        if query is not None:
            if not isinstance(query, KnowledgeQuery):
                raise InvalidKnowledgePackageError(
                    "request.query must be normalized to KnowledgeQuery"
                )
            result = self._retriever.query(query)
            candidates = list(result.items)
        else:
            matches: dict[str, KnowledgeItem] = {}
            for term in self._terms(request.objective):
                for candidate in self._retriever.query(KnowledgeQuery(text_contains=term)).items:
                    matches[candidate.id] = candidate
            candidates = sorted(matches.values(), key=lambda x: (-x.confidence.value, x.created_at, x.id))

        candidates = [candidate for candidate in candidates if self._allowed(candidate, request)]
        if request.required_categories:
            candidates = [candidate for candidate in candidates if candidate.kind in request.required_categories]
        if request.max_items is not None:
            candidates = candidates[: request.max_items]
        provenance: list[str] = []
        seen_provenance: set[str] = set()
        for candidate in candidates:
            if candidate.id not in seen_provenance:
                seen_provenance.add(candidate.id)
                provenance.append(candidate.id)

        contradictions: list[Contradiction] = []
        if request.include_contradictions:
            for candidate in candidates:
                for contradiction in self._retriever.contradictions_for_item(candidate.id):
                    if contradiction.id not in {item.id for item in contradictions}:
                        contradictions.append(contradiction)
            contradictions.sort(key=lambda x: (x.created_at, x.id))
            if request.max_contradictions is not None:
                contradictions = contradictions[: request.max_contradictions]

        selected_resources: list[Resource] = []
        if request.include_resources:
            resource_ids = {candidate.resource_id for candidate in candidates if candidate.resource_id}
            seen_resources: set[str] = set()
            for resource in self._resources:
                if (
                    resource.id in resource_ids
                    and resource.id not in seen_resources
                    and self._allowed(resource, request)
                ):
                    seen_resources.add(resource.id)
                    selected_resources.append(resource)
            selected_resources.sort(key=lambda x: (x.created_at, x.id))
            if request.max_resources is not None:
                selected_resources = selected_resources[: request.max_resources]

        grouped = {kind: tuple(candidate for candidate in candidates if candidate.kind is kind) for kind in KnowledgeKind}
        timestamps = [candidate.created_at for candidate in candidates]
        timestamps.extend(resource.created_at for resource in selected_resources)
        package_created_at = max(timestamps, default=datetime(1970, 1, 1, tzinfo=timezone.utc))
        for resource in selected_resources:
            if resource.id not in seen_provenance:
                seen_provenance.add(resource.id)
                provenance.append(resource.id)
        return KnowledgePackage(
            id=self._package_id(request),
            objective=request.objective.strip(),
            profile=request.profile,
            domain=request.domain,
            session_id=request.session_id,
            facts=grouped[KnowledgeKind.FACT],
            observations=grouped[KnowledgeKind.OBSERVATION],
            inferences=grouped[KnowledgeKind.INFERENCE],
            hypotheses=grouped[KnowledgeKind.HYPOTHESIS],
            other_knowledge=tuple(
                candidate
                for candidate in candidates
                if candidate.kind
                not in {
                    KnowledgeKind.FACT,
                    KnowledgeKind.OBSERVATION,
                    KnowledgeKind.INFERENCE,
                    KnowledgeKind.HYPOTHESIS,
                }
            ),
            contradictions=tuple(contradictions),
            resources=tuple(selected_resources),
            missing_information=request.missing_information,
            relevant_memory=request.relevant_memory[: request.max_memory] if request.max_memory is not None else request.relevant_memory,
            prior_reasoning=(request.prior_reasoning[: request.max_prior_reasoning] if request.include_prior_reasoning and request.max_prior_reasoning is not None else request.prior_reasoning if request.include_prior_reasoning else ()),
            privacy=request.privacy,
            temporal_scope=request.temporal_scope,
            created_at=package_created_at,
            provenance=tuple(provenance),
            metadata=request.metadata,
        )
