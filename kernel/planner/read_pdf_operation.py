"""Operation for reading a PDF into a reusable Document model."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, ClassVar, Mapping
from uuid import UUID, uuid4

from kernel.documents.document import Document
from kernel.documents.pdf_reader import PDFReader
from kernel.planner.exceptions import InvalidOperationError
from kernel.planner.operations import Operation


@dataclass(frozen=True, slots=True, kw_only=True)
class ReadPDFOperation(Operation):
    """Read a PDF file and produce a Document."""

    operation_type: ClassVar[str] = "read_pdf"
    metadata_name: ClassVar[str] = "read_pdf"
    description: ClassVar[str] = "Read a PDF file into a structured document model."
    category: ClassVar[str] = "documents"
    parameters: ClassVar[tuple[dict[str, Any], ...]] = (
        {
            "name": "path",
            "type": "str",
            "required": True,
            "description": "Path to the PDF file.",
        },
    )

    path: str = field()

    def execute(self) -> Document:
        """Read the configured PDF file and return a Document."""

        return PDFReader().read(self.path)

    def serialize(self) -> dict[str, Any]:
        payload = super().serialize()
        payload.update({"operation_type": self.operation_type_value, "path": self.path})
        return payload

    def validate(self) -> None:
        super().validate()
        if not isinstance(self.path, str) or not self.path.strip():
            raise InvalidOperationError("ReadPDFOperation requires a non-empty path.")

    @classmethod
    def _from_dict_payload(cls, payload: Mapping[str, Any]) -> "ReadPDFOperation":
        depends_on = tuple(UUID(item) for item in payload.get("depends_on", ()))
        metadata = payload.get("metadata", {}) or {}
        tags = tuple(payload.get("tags", ()))
        return cls(
            id=UUID(str(payload.get("id"))) if payload.get("id") is not None else uuid4(),
            depends_on=depends_on,
            metadata=dict(metadata),
            tags=tags,
            path=str(payload["path"]),
        )
