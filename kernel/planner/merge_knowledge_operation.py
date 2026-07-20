"""Operation for applying a knowledge delta to a knowledge base."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, ClassVar, Mapping
from uuid import UUID, uuid4

from kernel.knowledge.base import KnowledgeBase
from kernel.knowledge.delta import KnowledgeDelta
from kernel.planner.exceptions import InvalidOperationError
from kernel.planner.operations import Operation


@dataclass(frozen=True, slots=True, kw_only=True)
class MergeKnowledgeOperation(Operation):
    """Apply a knowledge delta to a knowledge base and return a new base."""

    operation_type: ClassVar[str] = "merge_knowledge"
    metadata_name: ClassVar[str] = "merge_knowledge"
    description: ClassVar[str] = "Apply a knowledge delta to a knowledge base."
    category: ClassVar[str] = "knowledge"
    parameters: ClassVar[tuple[dict[str, Any], ...]] = (
        {
            "name": "knowledge_base",
            "type": "KnowledgeBase",
            "required": True,
            "description": "Knowledge base to update.",
        },
        {
            "name": "delta",
            "type": "KnowledgeDelta",
            "required": True,
            "description": "Knowledge changes to apply.",
        },
    )

    knowledge_base: KnowledgeBase = field()
    delta: KnowledgeDelta = field()

    def execute(self) -> KnowledgeBase:
        """Return a new knowledge base with the delta applied."""

        items = {item.key: item for item in self.knowledge_base.list()}

        for item in self.delta.additions:
            items[item.key] = item

        for item in self.delta.modifications:
            items[item.key] = item

        for item in self.delta.removals:
            items.pop(item.key, None)

        return KnowledgeBase(items.values())

    def validate(self) -> None:
        """Validate the merge payload."""

        super().validate()
        if not isinstance(self.knowledge_base, KnowledgeBase):
            raise InvalidOperationError("MergeKnowledgeOperation requires a KnowledgeBase instance.")
        if not isinstance(self.delta, KnowledgeDelta):
            raise InvalidOperationError("MergeKnowledgeOperation requires a KnowledgeDelta instance.")

    def serialize(self) -> dict[str, Any]:
        payload = super().serialize()
        payload.update({"operation_type": self.operation_type_value, "knowledge_base": None, "delta": None})
        return payload

    @classmethod
    def _from_dict_payload(cls, payload: Mapping[str, Any]) -> "MergeKnowledgeOperation":
        depends_on = tuple(UUID(item) for item in payload.get("depends_on", ()))
        metadata = payload.get("metadata", {}) or {}
        tags = tuple(payload.get("tags", ()))
        knowledge_base = payload.get("knowledge_base")
        delta = payload.get("delta")
        if not isinstance(knowledge_base, KnowledgeBase):
            raise InvalidOperationError("MergeKnowledgeOperation payload requires a KnowledgeBase instance.")
        if not isinstance(delta, KnowledgeDelta):
            raise InvalidOperationError("MergeKnowledgeOperation payload requires a KnowledgeDelta instance.")

        return cls(
            id=UUID(str(payload.get("id"))) if payload.get("id") is not None else uuid4(),
            depends_on=depends_on,
            metadata=dict(metadata),
            tags=tags,
            knowledge_base=knowledge_base,
            delta=delta,
        )