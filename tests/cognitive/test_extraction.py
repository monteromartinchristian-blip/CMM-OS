"""Tests for Phase 8.3 extraction layer."""

from __future__ import annotations

from datetime import datetime

import pytest

from cmm.cognitive import (
    CandidateKind,
    ExtractionStatus,
    InvalidExtractionError,
    InvalidExtractionEvidenceError,
    MappingKnowledgeExtractor,
    PlainTextKnowledgeExtractor,
    Resource,
    ResourceKind,
    ResourcePermission,
    ResourcePermissionOperation,
    ResourceSourceKind,
)
from cmm.cognitive.contracts import Confidence
from cmm.cognitive.extraction import (
    ExtractionCandidate,
    ExtractionContext,
    ExtractionEvidence,
    KnowledgeExtractionResult,
)
from cmm.cognitive.resources import ResourceProvenance, ResourceTemporalScope

# ── Helpers ───────────────────────────────────────────────────────────────────


def _infer_permission() -> ResourcePermission:
    return ResourcePermission(
        allowed_operations=(
            ResourcePermissionOperation.READ,
            ResourcePermissionOperation.INFER,
        )
    )


def _text_resource(
    content: str = "The patient visited the clinic on 2024-03-15. Is this correct?",
    kind: ResourceKind = ResourceKind.DOCUMENT,
    permissions: tuple = (),
) -> Resource:
    return Resource(
        domain="health",
        kind=kind,
        source=ResourceSourceKind.USER_INPUT,
        content=content,
        provenance=ResourceProvenance(
            source_type=ResourceSourceKind.USER_INPUT, source_id="src-1"
        ),
        reliability=Confidence(1.0),
        temporal_scope=ResourceTemporalScope(),
        permissions=permissions,
    )


def _mapping_resource(
    content: dict | list | None = None,
    kind: ResourceKind = ResourceKind.STRUCTURED_DATASET,
    permissions: tuple = (),
) -> Resource:
    if content is None:
        content = {"patient": {"name": "Alice", "age": 35}, "date": "2024-03-15"}
    return Resource(
        domain="health",
        kind=kind,
        source=ResourceSourceKind.STRUCTURED_DATA,
        content=content,
        provenance=ResourceProvenance(
            source_type=ResourceSourceKind.STRUCTURED_DATA, source_id="src-2"
        ),
        reliability=Confidence(1.0),
        temporal_scope=ResourceTemporalScope(),
        permissions=permissions,
    )


# ── ExtractionContext tests ───────────────────────────────────────────────────


class TestExtractionContext:
    def test_default_timestamp_is_aware(self) -> None:
        ctx = ExtractionContext()
        assert ctx.timestamp.tzinfo is not None

    def test_rejects_naive_timestamp(self) -> None:
        with pytest.raises(InvalidExtractionError, match="timezone-aware"):
            ExtractionContext(timestamp=datetime(2026, 1, 1))

    def test_rejects_non_positive_max_candidates(self) -> None:
        with pytest.raises(InvalidExtractionError, match="max_candidates"):
            ExtractionContext(max_candidates=0)

    def test_rejects_non_positive_max_content_length(self) -> None:
        with pytest.raises(InvalidExtractionError, match="max_content_length"):
            ExtractionContext(max_content_length=-5)

    def test_to_dict_serialises_all_fields(self) -> None:
        ctx = ExtractionContext(
            actor_id="user-1",
            domain="health",
            trace_id="tr-1",
            max_candidates=10,
        )
        d = ctx.to_dict()
        assert d["actor_id"] == "user-1"
        assert d["domain"] == "health"
        assert d["max_candidates"] == 10

    def test_allowed_kinds_is_tuple(self) -> None:
        ctx = ExtractionContext(
            allowed_candidate_kinds=(CandidateKind.STATEMENT, CandidateKind.KEYWORD)
        )
        assert isinstance(ctx.allowed_candidate_kinds, tuple)


# ── ExtractionEvidence tests ──────────────────────────────────────────────────


class TestExtractionEvidence:
    def test_valid_construction(self) -> None:
        ev = ExtractionEvidence(
            resource_id="r1",
            fragment="hello",
            start=0,
            end=5,
        )
        assert ev.start == 0
        assert ev.end == 5

    def test_rejects_empty_resource_id(self) -> None:
        with pytest.raises(InvalidExtractionEvidenceError, match="resource_id"):
            ExtractionEvidence(resource_id="  ", fragment="x")

    def test_rejects_negative_start(self) -> None:
        with pytest.raises(InvalidExtractionEvidenceError, match="start"):
            ExtractionEvidence(resource_id="r1", fragment="x", start=-1)

    def test_rejects_end_before_start(self) -> None:
        with pytest.raises(InvalidExtractionEvidenceError, match="end"):
            ExtractionEvidence(resource_id="r1", fragment="x", start=5, end=3)

    def test_to_dict_structure(self) -> None:
        ev = ExtractionEvidence(
            resource_id="r1",
            fragment="the fragment",
            start=0,
            end=12,
            selector="$.a.b",
            page=1,
            section="Introduction",
        )
        d = ev.to_dict()
        assert d["resource_id"] == "r1"
        assert d["selector"] == "$.a.b"
        assert d["page"] == 1

    def test_metadata_is_defensive_copy(self) -> None:
        original = {"key": "val"}
        ev = ExtractionEvidence(resource_id="r1", fragment="x", metadata=original)
        original["extra"] = "y"
        assert "extra" not in ev.metadata


# ── ExtractionCandidate tests ─────────────────────────────────────────────────


class TestExtractionCandidate:
    def _make_candidate(self, **kwargs) -> ExtractionCandidate:
        ev = ExtractionEvidence(resource_id="r1", fragment="some text")
        defaults = dict(
            kind=CandidateKind.STATEMENT,
            value="some statement",
            confidence=Confidence(0.75),
            resource_id="r1",
            extractor_name="test",
            evidence=ev,
        )
        defaults.update(kwargs)
        return ExtractionCandidate(**defaults)

    def test_valid_construction(self) -> None:
        c = self._make_candidate()
        assert c.kind is CandidateKind.STATEMENT
        assert c.confidence.value == 0.75

    def test_rejects_empty_resource_id(self) -> None:
        ev = ExtractionEvidence(resource_id="r1", fragment="x")
        with pytest.raises(InvalidExtractionError, match="resource_id"):
            ExtractionCandidate(
                kind=CandidateKind.STATEMENT,
                value="x",
                confidence=Confidence(0.5),
                resource_id="  ",
                extractor_name="t",
                evidence=ev,
            )

    def test_rejects_empty_extractor_name(self) -> None:
        ev = ExtractionEvidence(resource_id="r1", fragment="x")
        with pytest.raises(InvalidExtractionError, match="extractor_name"):
            ExtractionCandidate(
                kind=CandidateKind.STATEMENT,
                value="x",
                confidence=Confidence(0.5),
                resource_id="r1",
                extractor_name="  ",
                evidence=ev,
            )

    def test_is_frozen(self) -> None:
        c = self._make_candidate()
        with pytest.raises(Exception):
            c.kind = CandidateKind.KEYWORD  # type: ignore[misc]

    def test_labels_are_tuple(self) -> None:
        c = self._make_candidate(labels=("tag1", "tag2"))
        assert isinstance(c.labels, tuple)

    def test_to_dict_structure(self) -> None:
        c = self._make_candidate()
        d = c.to_dict()
        for key in ("id", "kind", "value", "confidence", "resource_id", "evidence"):
            assert key in d
        assert d["kind"] == "statement"


# ── KnowledgeExtractionResult contract ───────────────────────────────────────


class TestKnowledgeExtractionResultContract:
    def _make_result(self, **kwargs) -> KnowledgeExtractionResult:
        defaults = dict(
            resource_id="r1",
            extractor_name="test",
            extractor_version="1.0.0",
            status=ExtractionStatus.COMPLETED,
        )
        defaults.update(kwargs)
        return KnowledgeExtractionResult(**defaults)

    def test_valid_construction(self) -> None:
        r = self._make_result()
        assert r.successful is True

    def test_rejects_naive_created_at(self) -> None:
        with pytest.raises(InvalidExtractionError, match="timezone-aware"):
            self._make_result(created_at=datetime(2026, 1, 1))

    def test_rejects_negative_duration(self) -> None:
        with pytest.raises(InvalidExtractionError, match="duration_ms"):
            self._make_result(duration_ms=-1.0)

    def test_candidate_count_property(self) -> None:
        ev = ExtractionEvidence(resource_id="r1", fragment="x")
        c = ExtractionCandidate(
            kind=CandidateKind.STATEMENT,
            value="x",
            confidence=Confidence(0.5),
            resource_id="r1",
            extractor_name="t",
            evidence=ev,
        )
        r = self._make_result(candidates=(c,))
        assert r.candidate_count == 1

    def test_has_warnings_and_has_errors(self) -> None:
        r = self._make_result(
            status=ExtractionStatus.PARTIAL,
            warnings=("watch",),
            errors=("broke",),
        )
        assert r.has_warnings is True
        assert r.has_errors is True

    def test_failed_is_not_successful(self) -> None:
        r = self._make_result(status=ExtractionStatus.FAILED)
        assert r.successful is False

    def test_empty_is_not_successful(self) -> None:
        r = self._make_result(status=ExtractionStatus.EMPTY)
        assert r.successful is False

    def test_partial_is_successful(self) -> None:
        r = self._make_result(status=ExtractionStatus.PARTIAL)
        assert r.successful is True

    def test_to_dict_keys(self) -> None:
        r = self._make_result()
        d = r.to_dict()
        for key in (
            "id",
            "resource_id",
            "extractor_name",
            "extractor_version",
            "status",
            "candidates",
            "warnings",
            "errors",
            "created_at",
            "successful",
            "candidate_count",
        ):
            assert key in d


# ── PlainTextKnowledgeExtractor ───────────────────────────────────────────────


class TestPlainTextKnowledgeExtractor:
    extractor = PlainTextKnowledgeExtractor()
    _perm = (_infer_permission(),)

    def _resource(self, text: str, kind=ResourceKind.DOCUMENT) -> Resource:
        return _text_resource(content=text, permissions=self._perm)

    def test_supports_text_document(self) -> None:
        r = self._resource("Hello world.")
        assert self.extractor.supports(r)

    def test_does_not_support_mapping_resource(self) -> None:
        r = _mapping_resource(permissions=self._perm)
        assert not self.extractor.supports(r)

    def test_extracts_statements(self) -> None:
        r = self._resource(
            "The patient has a fever. The doctor prescribed antibiotics."
        )
        result = self.extractor.extract(r)
        assert result.successful
        stmts = [c for c in result.candidates if c.kind is CandidateKind.STATEMENT]
        assert len(stmts) >= 1

    def test_extracts_questions(self) -> None:
        r = self._resource("Is the patient recovering? The treatment continues.")
        result = self.extractor.extract(r)
        questions = [c for c in result.candidates if c.kind is CandidateKind.QUESTION]
        assert len(questions) >= 1
        assert questions[0].value.endswith("?")

    def test_extracts_keywords(self) -> None:
        r = self._resource("Python programming language.")
        result = self.extractor.extract(r)
        keywords = [c for c in result.candidates if c.kind is CandidateKind.KEYWORD]
        assert len(keywords) >= 1

    def test_extracts_temporal_references(self) -> None:
        r = self._resource("The event happened on 2024-03-15.")
        result = self.extractor.extract(r)
        temporal = [
            c for c in result.candidates if c.kind is CandidateKind.TEMPORAL_REFERENCE
        ]
        assert len(temporal) >= 1
        assert "2024-03-15" in [c.value for c in temporal]

    def test_candidates_have_evidence(self) -> None:
        r = self._resource("The system is running.")
        result = self.extractor.extract(r)
        assert result.candidate_count > 0
        for candidate in result.candidates:
            assert candidate.evidence.resource_id == r.id
            assert candidate.evidence.fragment != ""

    def test_candidates_have_offsets(self) -> None:
        text = "The system works."
        r = self._resource(text)
        result = self.extractor.extract(r)
        stmts = [c for c in result.candidates if c.kind is CandidateKind.STATEMENT]
        assert stmts
        # At least one statement should have start/end
        assert stmts[0].evidence.start is not None
        assert stmts[0].evidence.end is not None

    def test_empty_content_returns_empty_status(self) -> None:
        r = Resource(
            domain="test",
            kind=ResourceKind.DOCUMENT,
            source=ResourceSourceKind.USER_INPUT,
            content="   ",
            provenance=ResourceProvenance(
                source_type=ResourceSourceKind.USER_INPUT, source_id="s1"
            ),
            reliability=Confidence(1.0),
            temporal_scope=ResourceTemporalScope(),
            permissions=self._perm,
        )
        result = self.extractor.extract(r)
        assert result.status is ExtractionStatus.EMPTY

    def test_no_infer_permission_fails(self) -> None:
        # No permissions means only READ is allowed by default
        r = _text_resource()
        result = self.extractor.extract(r)
        assert result.status is ExtractionStatus.FAILED
        assert result.has_errors

    def test_max_candidates_limit(self) -> None:
        long_text = " ".join(f"Sentence number {i} is here." for i in range(50))
        r = self._resource(long_text)
        ctx = ExtractionContext(max_candidates=3)
        result = self.extractor.extract(r, context=ctx)
        assert result.candidate_count <= 3

    def test_max_content_length_truncates(self) -> None:
        text = "A" * 1000 + " The end."
        r = self._resource(text)
        ctx = ExtractionContext(max_content_length=50)
        result = self.extractor.extract(r, context=ctx)
        assert result.truncated is True
        assert result.processed_length == 50

    def test_allowed_kinds_filter(self) -> None:
        r = self._resource("The system is running. Is it stable?")
        ctx = ExtractionContext(allowed_candidate_kinds=(CandidateKind.QUESTION,))
        result = self.extractor.extract(r, context=ctx)
        for c in result.candidates:
            assert c.kind is CandidateKind.QUESTION

    def test_unsupported_resource_kind(self) -> None:
        r = Resource(
            domain="test",
            kind=ResourceKind.STRUCTURED_DATASET,  # not text
            source=ResourceSourceKind.STRUCTURED_DATA,
            content={"k": "v"},
            provenance=ResourceProvenance(
                source_type=ResourceSourceKind.STRUCTURED_DATA, source_id="s1"
            ),
            reliability=Confidence(1.0),
            temporal_scope=ResourceTemporalScope(),
            permissions=self._perm,
        )
        result = self.extractor.extract(r)
        assert result.status is ExtractionStatus.UNSUPPORTED

    def test_duration_ms_is_non_negative(self) -> None:
        r = self._resource("short sentence.")
        result = self.extractor.extract(r)
        assert result.duration_ms is not None
        assert result.duration_ms >= 0


# ── MappingKnowledgeExtractor ─────────────────────────────────────────────────


class TestMappingKnowledgeExtractor:
    extractor = MappingKnowledgeExtractor()
    _perm = (_infer_permission(),)

    def _resource(self, content: dict | list) -> Resource:
        return _mapping_resource(content=content, permissions=self._perm)

    def test_supports_mapping_resource(self) -> None:
        r = self._resource({"key": "value"})
        assert self.extractor.supports(r)

    def test_does_not_support_text_resource(self) -> None:
        r = _text_resource()
        assert not self.extractor.supports(r)

    def test_extracts_flat_mapping(self) -> None:
        r = self._resource({"name": "Alice", "role": "doctor"})
        result = self.extractor.extract(r)
        assert result.successful
        assert result.candidate_count >= 2

    def test_extracts_nested_mapping(self) -> None:
        r = self._resource({"patient": {"name": "Bob", "age": 30}})
        result = self.extractor.extract(r)
        values = [str(c.value) for c in result.candidates]
        assert any("Bob" in v for v in values)

    def test_extracts_list_items(self) -> None:
        r = self._resource({"tags": ["fever", "headache"]})
        result = self.extractor.extract(r)
        # tags is a list → flattened to $.tags[0], $.tags[1]
        assert result.candidate_count >= 2

    def test_candidates_have_selectors(self) -> None:
        r = self._resource({"patient": {"name": "Alice"}})
        result = self.extractor.extract(r)
        selectors = [c.evidence.selector for c in result.candidates]
        assert any(sel is not None and "patient" in sel for sel in selectors)

    def test_numeric_value_becomes_quantity(self) -> None:
        r = self._resource({"age": 42})
        result = self.extractor.extract(r)
        kinds = {c.kind for c in result.candidates}
        assert CandidateKind.QUANTITY in kinds

    def test_no_infer_permission_fails(self) -> None:
        r = _mapping_resource()  # no permissions → only READ
        result = self.extractor.extract(r)
        assert result.status is ExtractionStatus.FAILED

    def test_max_candidates_limit(self) -> None:
        big = {f"key_{i}": f"value_{i}" for i in range(100)}
        r = self._resource(big)
        ctx = ExtractionContext(max_candidates=5)
        result = self.extractor.extract(r, context=ctx)
        assert result.candidate_count <= 5

    def test_empty_mapping_returns_empty_status(self) -> None:
        r = self._resource({})
        result = self.extractor.extract(r)
        assert result.status is ExtractionStatus.EMPTY

    def test_skips_none_values(self) -> None:
        r = self._resource({"name": "Alice", "optional": None})
        result = self.extractor.extract(r)
        values = [c.value for c in result.candidates]
        assert None not in values

    def test_date_key_inferred_as_temporal(self) -> None:
        r = self._resource({"created_at": "2024-01-01", "name": "test"})
        result = self.extractor.extract(r)
        kinds = {c.kind for c in result.candidates}
        assert CandidateKind.TEMPORAL_REFERENCE in kinds

    def test_unsupported_resource_kind_returns_unsupported(self) -> None:
        r = _text_resource(permissions=self._perm)
        result = self.extractor.extract(r)
        assert result.status is ExtractionStatus.UNSUPPORTED
