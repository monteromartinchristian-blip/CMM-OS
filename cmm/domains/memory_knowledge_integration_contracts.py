"""Phase 10.44 — Domain Memory and Knowledge Graph Integration Contracts.

Immutable, reference-only projection contracts connecting Domain Intelligence
to the canonical Cognitive Layer and Agent Runtime without duplicating knowledge
or creating parallel knowledge owners.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import Enum
from types import MappingProxyType
from typing import Any, Protocol, runtime_checkable

from cmm.cognitive.enums import KnowledgeRelationKind
from cmm.cognitive.knowledge import Contradiction, KnowledgeRelation
from cmm.domains.errors import (
    DomainMemoryKnowledgeContractError,
    DomainMemoryKnowledgeSerializationError,
)
from cmm.domains.identifiers import DomainId
from cmm.domains.memory_contracts import (
    DomainMemoryProposalBinding,
    DomainMemoryReferenceInventory,
    DomainMemoryView,
    DomainMemoryViewRequest,
)

_HEX64_PATTERN = re.compile(r"^[0-9a-f]{64}$")
_PATH_PREFIX = "domain-memory-knowledge-path:"
_PROJECTION_PREFIX = "domain-memory-knowledge-projection:"

CANONICAL_RELATION_KINDS = frozenset(item.value for item in KnowledgeRelationKind)


def _require_canonical_relation_kind(value: Any, field_name: str) -> str:
    kind_str = _require_non_blank_str(value, field_name)
    try:
        canonical = KnowledgeRelationKind(kind_str)
    except ValueError:
        raise DomainMemoryKnowledgeContractError(
            f"{field_name} must be a canonical KnowledgeRelationKind value"
        ) from None
    return canonical.value


FORBIDDEN_PAYLOAD_FIELDS = frozenset(
    {
        "statement",
        "excerpt",
        "raw_content",
        "prompt",
        "reasoning_text",
        "chain_of_thought",
        "source_payload",
        "resource_content",
        "secret",
        "credential",
    }
)


def _thaw_json_value(obj: Any) -> Any:
    if isinstance(obj, MappingProxyType):
        return {k: _thaw_json_value(v) for k, v in sorted(obj.items())}
    if isinstance(obj, dict):
        return {k: _thaw_json_value(v) for k, v in sorted(obj.items())}
    if isinstance(obj, (tuple, list, set, frozenset)):
        return [_thaw_json_value(v) for v in obj]
    if hasattr(obj, "to_dict"):
        return _thaw_json_value(obj.to_dict())
    if hasattr(obj, "value") and isinstance(obj.value, (str, int, float, bool)):
        return obj.value
    return obj


def _canonical_json(data: Any) -> str:
    return json.dumps(
        _thaw_json_value(data), sort_keys=True, separators=(",", ":"), allow_nan=False
    )


def _sha256_digest(data: Any) -> str:
    return hashlib.sha256(_canonical_json(data).encode("utf-8")).hexdigest()


def _require_non_blank_str(value: Any, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise DomainMemoryKnowledgeContractError(
            f"{field_name} must be a non-empty string"
        )
    return value.strip()


def _require_hex64(value: Any, field_name: str) -> str:
    val = _require_non_blank_str(value, field_name)
    if not _HEX64_PATTERN.match(val):
        raise DomainMemoryKnowledgeContractError(
            f"{field_name} must be a 64-character lowercase hex digest"
        )
    return val


def _normalize_domain_id(val: Any) -> DomainId:
    if isinstance(val, DomainId):
        return val
    if isinstance(val, str):
        s = val.strip().removeprefix("domain:")
        try:
            return DomainId(s)
        except Exception as exc:
            raise DomainMemoryKnowledgeContractError(
                f"Invalid domain ID slug '{s}': {exc}"
            ) from exc
    raise DomainMemoryKnowledgeContractError(f"Invalid domain ID: {val}")


class DomainMemoryKnowledgeProjectionCapability(str, Enum):
    """Closed enum of requested memory-knowledge projection capabilities."""

    SHARED_IDENTITIES = "shared_identities"
    RELATIONS = "relations"
    TIMELINE = "timeline"
    CONTRADICTIONS = "contradictions"
    DEPENDENCIES = "dependencies"
    IMPACT_PATHS = "impact_paths"
    RELATION_PROPOSALS = "relation_proposals"


@dataclass(frozen=True, slots=True)
class DomainMemoryKnowledgeRelationRef:
    """Reference to a visible canonical knowledge relation."""

    relation_id: str
    source_reference_id: str
    target_reference_id: str
    kind: str
    provenance_reference: str | None = None

    def __post_init__(self) -> None:
        rel_id = _require_non_blank_str(self.relation_id, "relation_id")
        src_id = _require_non_blank_str(self.source_reference_id, "source_reference_id")
        tgt_id = _require_non_blank_str(self.target_reference_id, "target_reference_id")
        k = _require_canonical_relation_kind(self.kind, "kind")

        if src_id == tgt_id:
            raise DomainMemoryKnowledgeContractError(
                "Relation cannot reference its own source as target"
            )

        prov = None
        if self.provenance_reference is not None:
            prov = _require_non_blank_str(
                self.provenance_reference, "provenance_reference"
            )

        object.__setattr__(self, "relation_id", rel_id)
        object.__setattr__(self, "source_reference_id", src_id)
        object.__setattr__(self, "target_reference_id", tgt_id)
        object.__setattr__(self, "kind", k)
        object.__setattr__(self, "provenance_reference", prov)

    def to_dict(self) -> dict[str, Any]:
        return {
            "relation_id": self.relation_id,
            "source_reference_id": self.source_reference_id,
            "target_reference_id": self.target_reference_id,
            "kind": self.kind,
            "provenance_reference": self.provenance_reference,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> DomainMemoryKnowledgeRelationRef:
        if not isinstance(data, Mapping):
            raise DomainMemoryKnowledgeSerializationError("Payload must be a mapping")
        allowed = {
            "relation_id",
            "source_reference_id",
            "target_reference_id",
            "kind",
            "provenance_reference",
        }
        unknown = set(data.keys()) - allowed
        if unknown:
            raise DomainMemoryKnowledgeSerializationError(
                f"Unknown fields in relation ref payload: {sorted(unknown)}"
            )
        try:
            return cls(
                relation_id=data["relation_id"],
                source_reference_id=data["source_reference_id"],
                target_reference_id=data["target_reference_id"],
                kind=data["kind"],
                provenance_reference=data.get("provenance_reference"),
            )
        except KeyError as exc:
            raise DomainMemoryKnowledgeSerializationError(
                f"Missing required field in relation ref: {exc}"
            ) from exc
        except DomainMemoryKnowledgeContractError as exc:
            raise DomainMemoryKnowledgeSerializationError(str(exc)) from exc


@dataclass(frozen=True, slots=True)
class DomainMemoryKnowledgeContradictionRef:
    """Reference to a canonical contradiction between visible knowledge references."""

    contradiction_id: str
    reference_ids: tuple[str, ...]
    resolution_reference_id: str | None = None

    def __post_init__(self) -> None:
        c_id = _require_non_blank_str(self.contradiction_id, "contradiction_id")
        if not isinstance(self.reference_ids, (tuple, list)):
            raise DomainMemoryKnowledgeContractError(
                "reference_ids must be a collection of strings"
            )
        cleaned_refs = [
            _require_non_blank_str(r, "reference_id") for r in self.reference_ids
        ]
        if len(cleaned_refs) < 2:
            raise DomainMemoryKnowledgeContractError(
                "reference_ids must contain at least 2 distinct references"
            )
        if len(set(cleaned_refs)) != len(cleaned_refs):
            raise DomainMemoryKnowledgeContractError(
                "reference_ids must not contain duplicates"
            )
        sorted_refs = tuple(sorted(cleaned_refs))

        res_ref = None
        if self.resolution_reference_id is not None:
            res_ref = _require_non_blank_str(
                self.resolution_reference_id, "resolution_reference_id"
            )

        object.__setattr__(self, "contradiction_id", c_id)
        object.__setattr__(self, "reference_ids", sorted_refs)
        object.__setattr__(self, "resolution_reference_id", res_ref)

    def to_dict(self) -> dict[str, Any]:
        return {
            "contradiction_id": self.contradiction_id,
            "reference_ids": list(self.reference_ids),
            "resolution_reference_id": self.resolution_reference_id,
        }

    @classmethod
    def from_dict(
        cls, data: Mapping[str, Any]
    ) -> DomainMemoryKnowledgeContradictionRef:
        if not isinstance(data, Mapping):
            raise DomainMemoryKnowledgeSerializationError("Payload must be a mapping")
        allowed = {"contradiction_id", "reference_ids", "resolution_reference_id"}
        unknown = set(data.keys()) - allowed
        if unknown:
            raise DomainMemoryKnowledgeSerializationError(
                f"Unknown fields in contradiction ref payload: {sorted(unknown)}"
            )
        try:
            return cls(
                contradiction_id=data["contradiction_id"],
                reference_ids=tuple(data["reference_ids"]),
                resolution_reference_id=data.get("resolution_reference_id"),
            )
        except KeyError as exc:
            raise DomainMemoryKnowledgeSerializationError(
                f"Missing required field in contradiction ref: {exc}"
            ) from exc
        except DomainMemoryKnowledgeContractError as exc:
            raise DomainMemoryKnowledgeSerializationError(str(exc)) from exc


@dataclass(frozen=True, slots=True)
class DomainMemoryKnowledgePathHop:
    """One explicit hop in a knowledge dependency or impact path."""

    relation_id: str
    source_reference_id: str
    target_reference_id: str
    kind: str

    def __post_init__(self) -> None:
        rel_id = _require_non_blank_str(self.relation_id, "relation_id")
        src_id = _require_non_blank_str(self.source_reference_id, "source_reference_id")
        tgt_id = _require_non_blank_str(self.target_reference_id, "target_reference_id")
        k = _require_canonical_relation_kind(self.kind, "kind")

        if src_id == tgt_id:
            raise DomainMemoryKnowledgeContractError(
                "Hop cannot reference its own source as target"
            )

        object.__setattr__(self, "relation_id", rel_id)
        object.__setattr__(self, "source_reference_id", src_id)
        object.__setattr__(self, "target_reference_id", tgt_id)
        object.__setattr__(self, "kind", k)

    def to_dict(self) -> dict[str, Any]:
        return {
            "relation_id": self.relation_id,
            "source_reference_id": self.source_reference_id,
            "target_reference_id": self.target_reference_id,
            "kind": self.kind,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> DomainMemoryKnowledgePathHop:
        if not isinstance(data, Mapping):
            raise DomainMemoryKnowledgeSerializationError("Payload must be a mapping")
        allowed = {"relation_id", "source_reference_id", "target_reference_id", "kind"}
        unknown = set(data.keys()) - allowed
        if unknown:
            raise DomainMemoryKnowledgeSerializationError(
                f"Unknown fields in hop payload: {sorted(unknown)}"
            )
        try:
            return cls(
                relation_id=data["relation_id"],
                source_reference_id=data["source_reference_id"],
                target_reference_id=data["target_reference_id"],
                kind=data["kind"],
            )
        except KeyError as exc:
            raise DomainMemoryKnowledgeSerializationError(
                f"Missing required field in hop: {exc}"
            ) from exc
        except DomainMemoryKnowledgeContractError as exc:
            raise DomainMemoryKnowledgeSerializationError(str(exc)) from exc


@dataclass(frozen=True, slots=True)
class DomainMemoryKnowledgePath:
    """Content-bound, explicit sequence of canonical hops."""

    path_id: str
    hops: tuple[DomainMemoryKnowledgePathHop, ...]
    content_digest: str

    def __post_init__(self) -> None:
        if not self.hops:
            raise DomainMemoryKnowledgeContractError("Path cannot have empty hops")
        for hop in self.hops:
            if not isinstance(hop, DomainMemoryKnowledgePathHop):
                raise DomainMemoryKnowledgeContractError(
                    "hops elements must be DomainMemoryKnowledgePathHop"
                )

        for i in range(len(self.hops) - 1):
            if self.hops[i].target_reference_id != self.hops[i + 1].source_reference_id:
                raise DomainMemoryKnowledgeContractError(
                    f"Path hops are disconnected at index {i}: "
                    f"{self.hops[i].target_reference_id} != {self.hops[i + 1].source_reference_id}"
                )

        expected_digest = _sha256_digest([h.to_dict() for h in self.hops])
        expected_id = f"{_PATH_PREFIX}{expected_digest[:16]}"

        if self.content_digest != expected_digest:
            raise DomainMemoryKnowledgeContractError(
                f"Path content_digest mismatch: expected {expected_digest}, got {self.content_digest}"
            )
        if self.path_id != expected_id:
            raise DomainMemoryKnowledgeContractError(
                f"Path path_id mismatch: expected {expected_id}, got {self.path_id}"
            )

    @classmethod
    def create(
        cls, hops: Sequence[DomainMemoryKnowledgePathHop]
    ) -> DomainMemoryKnowledgePath:
        hops_tuple = tuple(hops)
        digest = _sha256_digest([h.to_dict() for h in hops_tuple])
        path_id = f"{_PATH_PREFIX}{digest[:16]}"
        return cls(path_id=path_id, hops=hops_tuple, content_digest=digest)

    def to_dict(self) -> dict[str, Any]:
        return {
            "path_id": self.path_id,
            "hops": [h.to_dict() for h in self.hops],
            "content_digest": self.content_digest,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> DomainMemoryKnowledgePath:
        if not isinstance(data, Mapping):
            raise DomainMemoryKnowledgeSerializationError("Payload must be a mapping")
        allowed = {"path_id", "hops", "content_digest"}
        unknown = set(data.keys()) - allowed
        if unknown:
            raise DomainMemoryKnowledgeSerializationError(
                f"Unknown fields in path payload: {sorted(unknown)}"
            )
        try:
            hops = tuple(
                DomainMemoryKnowledgePathHop.from_dict(h) for h in data["hops"]
            )
            return cls(
                path_id=data["path_id"],
                hops=hops,
                content_digest=data["content_digest"],
            )
        except KeyError as exc:
            raise DomainMemoryKnowledgeSerializationError(
                f"Missing required field in path: {exc}"
            ) from exc
        except DomainMemoryKnowledgeContractError as exc:
            raise DomainMemoryKnowledgeSerializationError(str(exc)) from exc


@dataclass(frozen=True, slots=True)
class DomainMemoryKnowledgeInventory:
    """Explicit read-only input inventory of canonical objects and Domain bindings."""

    relations: tuple[KnowledgeRelation, ...] = ()
    contradictions: tuple[Contradiction, ...] = ()
    proposal_bindings: tuple[DomainMemoryProposalBinding, ...] = ()

    def __post_init__(self) -> None:
        rel_map: dict[str, KnowledgeRelation] = {}
        for r in self.relations:
            if not isinstance(r, KnowledgeRelation):
                raise DomainMemoryKnowledgeContractError(
                    "relations element must be KnowledgeRelation"
                )
            if r.id in rel_map:
                raise DomainMemoryKnowledgeContractError(
                    f"Duplicate relation.id in inventory: {r.id}"
                )
            rel_map[r.id] = r
        sorted_rels = tuple(sorted(rel_map.values(), key=lambda r: r.id))

        contra_map: dict[str, Contradiction] = {}
        for c in self.contradictions:
            if not isinstance(c, Contradiction):
                raise DomainMemoryKnowledgeContractError(
                    "contradictions element must be Contradiction"
                )
            if c.id in contra_map:
                raise DomainMemoryKnowledgeContractError(
                    f"Duplicate contradiction.id in inventory: {c.id}"
                )
            contra_map[c.id] = c
        sorted_contras = tuple(sorted(contra_map.values(), key=lambda c: c.id))

        bind_map: dict[str, DomainMemoryProposalBinding] = {}
        for b in self.proposal_bindings:
            if not isinstance(b, DomainMemoryProposalBinding):
                raise DomainMemoryKnowledgeContractError(
                    "proposal_bindings element must be DomainMemoryProposalBinding"
                )
            if b.binding_id in bind_map:
                raise DomainMemoryKnowledgeContractError(
                    f"Duplicate proposal binding_id in inventory: {b.binding_id}"
                )
            bind_map[b.binding_id] = b
        sorted_bindings = tuple(sorted(bind_map.values(), key=lambda b: b.binding_id))

        object.__setattr__(self, "relations", sorted_rels)
        object.__setattr__(self, "contradictions", sorted_contras)
        object.__setattr__(self, "proposal_bindings", sorted_bindings)


@dataclass(frozen=True, slots=True)
class DomainMemoryKnowledgeProjectionRequest:
    """Authoritative input request binding memory/knowledge projection to Phase 10.18."""

    request_id: str
    primary_domain: DomainId
    supporting_domains: tuple[DomainId, ...]
    memory_view_id: str
    memory_view_digest: str
    resolution_reference_id: str
    composition_reference_id: str
    permission_decision_ids: tuple[str, ...]
    requested_capabilities: tuple[DomainMemoryKnowledgeProjectionCapability, ...]
    trace_id: str | None = None
    session_id: str | None = None
    temporal_reference: str | None = None

    @property
    def digest(self) -> str:
        return _sha256_digest(self.to_dict())

    def __post_init__(self) -> None:
        req_id = _require_non_blank_str(self.request_id, "request_id")
        mv_id = _require_non_blank_str(self.memory_view_id, "memory_view_id")
        mv_digest = _require_hex64(self.memory_view_digest, "memory_view_digest")
        res_ref = _require_non_blank_str(
            self.resolution_reference_id, "resolution_reference_id"
        )
        comp_ref = _require_non_blank_str(
            self.composition_reference_id, "composition_reference_id"
        )

        p_dom = _normalize_domain_id(self.primary_domain)
        s_doms = tuple(
            sorted(
                {_normalize_domain_id(d) for d in self.supporting_domains},
                key=lambda d: str(d),
            )
        )
        perm_ids = tuple(
            sorted(
                {
                    _require_non_blank_str(pid, "permission_decision_id")
                    for pid in self.permission_decision_ids
                }
            )
        )
        caps = tuple(
            sorted(
                set(self.requested_capabilities),
                key=lambda c: c.value,
            )
        )

        tr_id = (
            _require_non_blank_str(self.trace_id, "trace_id")
            if self.trace_id is not None
            else None
        )
        s_id = (
            _require_non_blank_str(self.session_id, "session_id")
            if self.session_id is not None
            else None
        )
        t_ref = (
            _require_non_blank_str(self.temporal_reference, "temporal_reference")
            if self.temporal_reference is not None
            else None
        )

        object.__setattr__(self, "request_id", req_id)
        object.__setattr__(self, "primary_domain", p_dom)
        object.__setattr__(self, "supporting_domains", s_doms)
        object.__setattr__(self, "memory_view_id", mv_id)
        object.__setattr__(self, "memory_view_digest", mv_digest)
        object.__setattr__(self, "resolution_reference_id", res_ref)
        object.__setattr__(self, "composition_reference_id", comp_ref)
        object.__setattr__(self, "permission_decision_ids", perm_ids)
        object.__setattr__(self, "requested_capabilities", caps)
        object.__setattr__(self, "trace_id", tr_id)
        object.__setattr__(self, "session_id", s_id)
        object.__setattr__(self, "temporal_reference", t_ref)

    def to_dict(self) -> dict[str, Any]:
        return {
            "request_id": self.request_id,
            "primary_domain": str(self.primary_domain),
            "supporting_domains": [str(d) for d in self.supporting_domains],
            "memory_view_id": self.memory_view_id,
            "memory_view_digest": self.memory_view_digest,
            "resolution_reference_id": self.resolution_reference_id,
            "composition_reference_id": self.composition_reference_id,
            "permission_decision_ids": list(self.permission_decision_ids),
            "requested_capabilities": [c.value for c in self.requested_capabilities],
            "trace_id": self.trace_id,
            "session_id": self.session_id,
            "temporal_reference": self.temporal_reference,
        }

    @classmethod
    def from_dict(
        cls, data: Mapping[str, Any]
    ) -> DomainMemoryKnowledgeProjectionRequest:
        if not isinstance(data, Mapping):
            raise DomainMemoryKnowledgeSerializationError("Payload must be a mapping")
        allowed = {
            "request_id",
            "primary_domain",
            "supporting_domains",
            "memory_view_id",
            "memory_view_digest",
            "resolution_reference_id",
            "composition_reference_id",
            "permission_decision_ids",
            "requested_capabilities",
            "trace_id",
            "session_id",
            "temporal_reference",
        }
        unknown = set(data.keys()) - allowed
        if unknown:
            raise DomainMemoryKnowledgeSerializationError(
                f"Unknown fields in projection request payload: {sorted(unknown)}"
            )
        try:
            return cls(
                request_id=data["request_id"],
                primary_domain=_normalize_domain_id(data["primary_domain"]),
                supporting_domains=tuple(
                    _normalize_domain_id(d) for d in data.get("supporting_domains", ())
                ),
                memory_view_id=data["memory_view_id"],
                memory_view_digest=data["memory_view_digest"],
                resolution_reference_id=data["resolution_reference_id"],
                composition_reference_id=data["composition_reference_id"],
                permission_decision_ids=tuple(data.get("permission_decision_ids", ())),
                requested_capabilities=tuple(
                    DomainMemoryKnowledgeProjectionCapability(c)
                    for c in data.get("requested_capabilities", ())
                ),
                trace_id=data.get("trace_id"),
                session_id=data.get("session_id"),
                temporal_reference=data.get("temporal_reference"),
            )
        except KeyError as exc:
            raise DomainMemoryKnowledgeSerializationError(
                f"Missing required field in request: {exc}"
            ) from exc
        except DomainMemoryKnowledgeContractError as exc:
            raise DomainMemoryKnowledgeSerializationError(str(exc)) from exc


@dataclass(frozen=True, slots=True)
class DomainMemoryKnowledgeProjection:
    """Strictly reference-only projection over canonical knowledge and Phase 10.18 memory."""

    projection_id: str
    request_id: str
    request_digest: str
    memory_view_id: str
    memory_view_digest: str
    selected_reference_ids: tuple[str, ...]
    shared_identity_reference_ids: tuple[str, ...]
    relation_refs: tuple[DomainMemoryKnowledgeRelationRef, ...]
    timeline_reference_ids: tuple[str, ...] = ()
    unknown_ordering_reference_ids: tuple[str, ...] = ()
    contradiction_refs: tuple[DomainMemoryKnowledgeContradictionRef, ...] = ()
    dependency_paths: tuple[DomainMemoryKnowledgePath, ...] = ()
    impact_paths: tuple[DomainMemoryKnowledgePath, ...] = ()
    proposal_binding_ids: tuple[str, ...] = ()
    excluded_reference_ids: tuple[str, ...] = ()
    content_digest: str = ""

    def __post_init__(self) -> None:
        p_id = _require_non_blank_str(self.projection_id, "projection_id")
        req_id = _require_non_blank_str(self.request_id, "request_id")
        req_digest = _require_hex64(self.request_digest, "request_digest")
        mv_id = _require_non_blank_str(self.memory_view_id, "memory_view_id")
        mv_digest = _require_hex64(self.memory_view_digest, "memory_view_digest")

        sel_ids = tuple(
            sorted(
                {
                    _require_non_blank_str(r, "selected_ref")
                    for r in self.selected_reference_ids
                }
            )
        )
        shared_ids = tuple(
            sorted(
                {
                    _require_non_blank_str(r, "shared_ref")
                    for r in self.shared_identity_reference_ids
                }
            )
        )
        excl_ids = tuple(
            sorted(
                {
                    _require_non_blank_str(r, "excluded_ref")
                    for r in self.excluded_reference_ids
                }
            )
        )
        tl_ids = tuple(
            _require_non_blank_str(r, "timeline_ref")
            for r in self.timeline_reference_ids
        )
        unk_ids = tuple(
            sorted(
                {
                    _require_non_blank_str(r, "unknown_ordering_ref")
                    for r in self.unknown_ordering_reference_ids
                }
            )
        )
        prop_ids = tuple(
            sorted(
                {
                    _require_non_blank_str(p, "proposal_binding_id")
                    for p in self.proposal_binding_ids
                }
            )
        )

        # Selected and excluded must be strictly disjoint
        overlap = set(sel_ids) & set(excl_ids)
        if overlap:
            raise DomainMemoryKnowledgeContractError(
                f"Selected and excluded references cannot overlap: {sorted(overlap)}"
            )

        # Shared identities must be subset of selected references
        missing_shared = set(shared_ids) - set(sel_ids)
        if missing_shared:
            raise DomainMemoryKnowledgeContractError(
                f"Shared identity references must be in selected references: {sorted(missing_shared)}"
            )

        sorted_relations = tuple(
            sorted(self.relation_refs, key=lambda r: r.relation_id)
        )
        sorted_contradictions = tuple(
            sorted(self.contradiction_refs, key=lambda c: c.contradiction_id)
        )
        sorted_dep_paths = tuple(sorted(self.dependency_paths, key=lambda p: p.path_id))
        sorted_imp_paths = tuple(sorted(self.impact_paths, key=lambda p: p.path_id))

        payload = {
            "request_id": req_id,
            "request_digest": req_digest,
            "memory_view_id": mv_id,
            "memory_view_digest": mv_digest,
            "selected_reference_ids": list(sel_ids),
            "shared_identity_reference_ids": list(shared_ids),
            "relation_refs": [r.to_dict() for r in sorted_relations],
            "timeline_reference_ids": list(tl_ids),
            "unknown_ordering_reference_ids": list(unk_ids),
            "contradiction_refs": [c.to_dict() for c in sorted_contradictions],
            "dependency_paths": [p.to_dict() for p in sorted_dep_paths],
            "impact_paths": [p.to_dict() for p in sorted_imp_paths],
            "proposal_binding_ids": list(prop_ids),
            "excluded_reference_ids": list(excl_ids),
        }

        expected_digest = _sha256_digest(payload)
        expected_id = f"{_PROJECTION_PREFIX}{expected_digest[:16]}"

        if self.content_digest != expected_digest:
            raise DomainMemoryKnowledgeContractError(
                f"content_digest mismatch: expected {expected_digest}, got {self.content_digest}"
            )
        if p_id != expected_id:
            raise DomainMemoryKnowledgeContractError(
                f"projection_id mismatch: expected {expected_id}, got {p_id}"
            )

        object.__setattr__(self, "projection_id", p_id)
        object.__setattr__(self, "request_id", req_id)
        object.__setattr__(self, "request_digest", req_digest)
        object.__setattr__(self, "memory_view_id", mv_id)
        object.__setattr__(self, "memory_view_digest", mv_digest)
        object.__setattr__(self, "selected_reference_ids", sel_ids)
        object.__setattr__(self, "shared_identity_reference_ids", shared_ids)
        object.__setattr__(self, "relation_refs", sorted_relations)
        object.__setattr__(self, "timeline_reference_ids", tl_ids)
        object.__setattr__(self, "unknown_ordering_reference_ids", unk_ids)
        object.__setattr__(self, "contradiction_refs", sorted_contradictions)
        object.__setattr__(self, "dependency_paths", sorted_dep_paths)
        object.__setattr__(self, "impact_paths", sorted_imp_paths)
        object.__setattr__(self, "proposal_binding_ids", prop_ids)
        object.__setattr__(self, "excluded_reference_ids", excl_ids)

    @classmethod
    def create(
        cls,
        *,
        request_id: str,
        request_digest: str,
        memory_view_id: str,
        memory_view_digest: str,
        selected_reference_ids: Sequence[str],
        shared_identity_reference_ids: Sequence[str],
        relation_refs: Sequence[DomainMemoryKnowledgeRelationRef],
        timeline_reference_ids: Sequence[str] = (),
        unknown_ordering_reference_ids: Sequence[str] = (),
        contradiction_refs: Sequence[DomainMemoryKnowledgeContradictionRef] = (),
        dependency_paths: Sequence[DomainMemoryKnowledgePath] = (),
        impact_paths: Sequence[DomainMemoryKnowledgePath] = (),
        proposal_binding_ids: Sequence[str] = (),
        excluded_reference_ids: Sequence[str] = (),
    ) -> DomainMemoryKnowledgeProjection:
        sel_ids = tuple(sorted(set(selected_reference_ids)))
        shared_ids = tuple(sorted(set(shared_identity_reference_ids)))
        excl_ids = tuple(sorted(set(excluded_reference_ids)))
        tl_ids = tuple(timeline_reference_ids)
        unk_ids = tuple(sorted(set(unknown_ordering_reference_ids)))
        prop_ids = tuple(sorted(set(proposal_binding_ids)))
        sorted_relations = tuple(sorted(relation_refs, key=lambda r: r.relation_id))
        sorted_contradictions = tuple(
            sorted(contradiction_refs, key=lambda c: c.contradiction_id)
        )
        sorted_dep_paths = tuple(sorted(dependency_paths, key=lambda p: p.path_id))
        sorted_imp_paths = tuple(sorted(impact_paths, key=lambda p: p.path_id))

        payload = {
            "request_id": request_id,
            "request_digest": request_digest,
            "memory_view_id": memory_view_id,
            "memory_view_digest": memory_view_digest,
            "selected_reference_ids": list(sel_ids),
            "shared_identity_reference_ids": list(shared_ids),
            "relation_refs": [r.to_dict() for r in sorted_relations],
            "timeline_reference_ids": list(tl_ids),
            "unknown_ordering_reference_ids": list(unk_ids),
            "contradiction_refs": [c.to_dict() for c in sorted_contradictions],
            "dependency_paths": [p.to_dict() for p in sorted_dep_paths],
            "impact_paths": [p.to_dict() for p in sorted_imp_paths],
            "proposal_binding_ids": list(prop_ids),
            "excluded_reference_ids": list(excl_ids),
        }
        digest = _sha256_digest(payload)
        proj_id = f"{_PROJECTION_PREFIX}{digest[:16]}"
        return cls(
            projection_id=proj_id,
            request_id=request_id,
            request_digest=request_digest,
            memory_view_id=memory_view_id,
            memory_view_digest=memory_view_digest,
            selected_reference_ids=sel_ids,
            shared_identity_reference_ids=shared_ids,
            relation_refs=sorted_relations,
            timeline_reference_ids=tl_ids,
            unknown_ordering_reference_ids=unk_ids,
            contradiction_refs=sorted_contradictions,
            dependency_paths=sorted_dep_paths,
            impact_paths=sorted_imp_paths,
            proposal_binding_ids=prop_ids,
            excluded_reference_ids=excl_ids,
            content_digest=digest,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "projection_id": self.projection_id,
            "request_id": self.request_id,
            "request_digest": self.request_digest,
            "memory_view_id": self.memory_view_id,
            "memory_view_digest": self.memory_view_digest,
            "selected_reference_ids": list(self.selected_reference_ids),
            "shared_identity_reference_ids": list(self.shared_identity_reference_ids),
            "relation_refs": [r.to_dict() for r in self.relation_refs],
            "timeline_reference_ids": list(self.timeline_reference_ids),
            "unknown_ordering_reference_ids": list(self.unknown_ordering_reference_ids),
            "contradiction_refs": [c.to_dict() for c in self.contradiction_refs],
            "dependency_paths": [p.to_dict() for p in self.dependency_paths],
            "impact_paths": [p.to_dict() for p in self.impact_paths],
            "proposal_binding_ids": list(self.proposal_binding_ids),
            "excluded_reference_ids": list(self.excluded_reference_ids),
            "content_digest": self.content_digest,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> DomainMemoryKnowledgeProjection:
        if not isinstance(data, Mapping):
            raise DomainMemoryKnowledgeSerializationError("Payload must be a mapping")
        allowed = {
            "projection_id",
            "request_id",
            "request_digest",
            "memory_view_id",
            "memory_view_digest",
            "selected_reference_ids",
            "shared_identity_reference_ids",
            "relation_refs",
            "timeline_reference_ids",
            "unknown_ordering_reference_ids",
            "contradiction_refs",
            "dependency_paths",
            "impact_paths",
            "proposal_binding_ids",
            "excluded_reference_ids",
            "content_digest",
        }
        unknown = set(data.keys()) - allowed
        if unknown:
            raise DomainMemoryKnowledgeSerializationError(
                f"Unknown fields in projection payload: {sorted(unknown)}"
            )
        try:
            rel_refs = tuple(
                DomainMemoryKnowledgeRelationRef.from_dict(r)
                for r in data.get("relation_refs", ())
            )
            contra_refs = tuple(
                DomainMemoryKnowledgeContradictionRef.from_dict(c)
                for c in data.get("contradiction_refs", ())
            )
            dep_paths = tuple(
                DomainMemoryKnowledgePath.from_dict(p)
                for p in data.get("dependency_paths", ())
            )
            imp_paths = tuple(
                DomainMemoryKnowledgePath.from_dict(p)
                for p in data.get("impact_paths", ())
            )
            return cls(
                projection_id=data["projection_id"],
                request_id=data["request_id"],
                request_digest=data["request_digest"],
                memory_view_id=data["memory_view_id"],
                memory_view_digest=data["memory_view_digest"],
                selected_reference_ids=tuple(data.get("selected_reference_ids", ())),
                shared_identity_reference_ids=tuple(
                    data.get("shared_identity_reference_ids", ())
                ),
                relation_refs=rel_refs,
                timeline_reference_ids=tuple(data.get("timeline_reference_ids", ())),
                unknown_ordering_reference_ids=tuple(
                    data.get("unknown_ordering_reference_ids", ())
                ),
                contradiction_refs=contra_refs,
                dependency_paths=dep_paths,
                impact_paths=imp_paths,
                proposal_binding_ids=tuple(data.get("proposal_binding_ids", ())),
                excluded_reference_ids=tuple(data.get("excluded_reference_ids", ())),
                content_digest=data["content_digest"],
            )
        except KeyError as exc:
            raise DomainMemoryKnowledgeSerializationError(
                f"Missing required field in projection: {exc}"
            ) from exc
        except DomainMemoryKnowledgeContractError as exc:
            raise DomainMemoryKnowledgeSerializationError(str(exc)) from exc


@runtime_checkable
class DomainMemoryKnowledgeIntegrator(Protocol):
    """Protocol for pure, reference-only Domain memory and knowledge graph integration."""

    def project(
        self,
        request: DomainMemoryKnowledgeProjectionRequest,
        *,
        memory_request: DomainMemoryViewRequest,
        view: DomainMemoryView,
        memory_inventory: DomainMemoryReferenceInventory,
        inventory: DomainMemoryKnowledgeInventory,
        resolution: Any | None = None,
        composition: Any | None = None,
    ) -> DomainMemoryKnowledgeProjection:
        """Project authorized canonical knowledge over a resolved Phase 10.18 memory view."""
        ...
