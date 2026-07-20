from __future__ import annotations

import json

from kernel.documents.document import Document
from kernel.knowledge.base import KnowledgeBase
from kernel.knowledge.delta import KnowledgeDelta
from kernel.planner.operation_catalog import OperationCatalog
from kernel.planner.operation_metadata import OperationMetadata
from kernel.planner.operations import CreateClassOperation, EnsureImportOperation, ExtractFactsOperation, InsertMethodOperation, MergeKnowledgeOperation, ReadPDFOperation, ReplaceMethodOperation


def test_catalog_discovers_all_registered_operations() -> None:
    catalog = OperationCatalog()

    operation_names = {metadata.name for metadata in catalog.operations()}

    assert {"create_class", "insert_method", "replace_method", "ensure_import", "read_pdf", "extract_facts", "merge_knowledge"}.issubset(operation_names)


def test_catalog_get_returns_metadata() -> None:
    catalog = OperationCatalog()

    metadata = catalog.get("replace_method")

    assert isinstance(metadata, OperationMetadata)
    assert metadata.name == "replace_method"
    assert metadata.category == "python"


def test_catalog_to_dict_is_json_serializable() -> None:
    catalog = OperationCatalog()

    payload = catalog.to_dict()

    assert isinstance(payload, dict)
    json_text = json.dumps(payload)
    assert json.loads(json_text)["operations"]


def test_operations_expose_metadata_objects() -> None:
    operations = [
        CreateClassOperation(class_name="User"),
        InsertMethodOperation(target_class="User", method_name="run", source_code="def run(self):\n    pass"),
        ReplaceMethodOperation(target_class="User", method_name="run", source_code="def run(self):\n    return True"),
        EnsureImportOperation(module="typing", name="Optional"),
        ExtractFactsOperation(document=Document()),
        ReadPDFOperation(path="/tmp/example.pdf"),
        MergeKnowledgeOperation(
            knowledge_base=KnowledgeBase.empty(),
            delta=KnowledgeDelta(),
        ),
    ]

    for operation in operations:
        metadata = operation.operation_metadata()
        schema = operation.schema()

        assert metadata.name
        assert metadata.description
        assert metadata.category
        assert metadata.parameters
        assert schema["name"] == metadata.name
        assert schema["description"] == metadata.description
        assert schema["category"] == metadata.category