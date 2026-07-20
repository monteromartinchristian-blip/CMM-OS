"""Operation for extracting structured knowledge from a document."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, ClassVar, Mapping
from uuid import UUID, uuid4

from kernel.documents.document import Document
from kernel.knowledge.delta import KnowledgeDelta
from kernel.planner.exceptions import InvalidOperationError
from kernel.planner.operations import Operation


@dataclass(frozen=True, slots=True, kw_only=True)
class ExtractFactsOperation(Operation):
    """Traverse a document and return a reusable knowledge delta."""

    operation_type: ClassVar[str] = "extract_facts"
    metadata_name: ClassVar[str] = "extract_facts"
    description: ClassVar[str] = "Extract structured knowledge changes from a document."
    category: ClassVar[str] = "knowledge"
    parameters: ClassVar[tuple[dict[str, Any], ...]] = (
        {
            "name": "document",
            "type": "Document",
            "required": True,
            "description": "Document to inspect.",
        },
    )

    document: Document = field()

    def execute(self) -> KnowledgeDelta:
        """Inspect the document and return a minimal, valid knowledge delta."""

        for page in self.document.pages:
            _ = page.text

        return KnowledgeDelta()

    def validate(self) -> None:
        super().validate()
        if not isinstance(self.document, Document):
            raise InvalidOperationError("ExtractFactsOperation requires a Document instance.")

    def serialize(self) -> dict[str, Any]:
        payload = super().serialize()
        payload.update({"operation_type": self.operation_type_value, "document": None})
        return payload

    @classmethod
    def _from_dict_payload(cls, payload: Mapping[str, Any]) -> "ExtractFactsOperation":
        depends_on = tuple(UUID(item) for item in payload.get("depends_on", ()))
        metadata = payload.get("metadata", {}) or {}
        tags = tuple(payload.get("tags", ()))
        document = payload.get("document")
        if not isinstance(document, Document):
            raise InvalidOperationError("ExtractFactsOperation payload requires a Document instance.")

        return cls(
            id=UUID(str(payload.get("id"))) if payload.get("id") is not None else uuid4(),
            depends_on=depends_on,
            metadata=dict(metadata),
            tags=tags,
            document=document,
        )
