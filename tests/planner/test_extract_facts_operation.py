from __future__ import annotations

from pathlib import Path

from kernel.documents.document import Document
from kernel.documents.pdf_reader import PDFReader
from kernel.knowledge.delta import KnowledgeDelta
from kernel.planner.extract_facts_operation import ExtractFactsOperation


def _fixture(name: str) -> Path:
    return Path(__file__).parent.parent / "fixtures" / "sample_pdf" / name


def test_extract_facts_operation_accepts_a_document() -> None:
    document = Document()
    operation = ExtractFactsOperation(document=document)

    assert operation.document is document


def test_extract_facts_operation_returns_knowledge_delta() -> None:
    document = Document()
    operation = ExtractFactsOperation(document=document)

    result = operation.execute()

    assert isinstance(result, KnowledgeDelta)
    assert result.is_empty is True


def test_extract_facts_operation_works_with_empty_document() -> None:
    operation = ExtractFactsOperation(document=Document())

    result = operation.execute()

    assert isinstance(result, KnowledgeDelta)
    assert result.is_empty is True


def test_extract_facts_operation_works_with_pdf_fixture() -> None:
    document = PDFReader().read(_fixture("hello.pdf"))
    operation = ExtractFactsOperation(document=document)
    before = tuple((page.number, page.text) for page in document.pages)

    result = operation.execute()

    after = tuple((page.number, page.text) for page in document.pages)

    assert isinstance(result, KnowledgeDelta)
    assert result.is_empty is True
    assert before == after


def test_extract_facts_operation_does_not_modify_input_document() -> None:
    document = PDFReader().read(_fixture("hello.pdf"))
    before = tuple((page.number, page.text) for page in document.pages)

    ExtractFactsOperation(document=document).execute()

    after = tuple((page.number, page.text) for page in document.pages)

    assert before == after
