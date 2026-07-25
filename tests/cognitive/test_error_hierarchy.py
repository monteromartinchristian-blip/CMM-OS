"""Tests for the Cognitive Layer error hierarchy.

Verifies that all public error classes form a coherent hierarchy rooted at
CognitiveError and that no errors leak generic Python exceptions.
"""

from __future__ import annotations

import inspect

import cmm.cognitive.errors as errors_module
from cmm.cognitive.errors import CognitiveError


def _all_error_classes() -> list[type]:
    """Collect every public Exception subclass in the errors module."""
    return [
        obj
        for name, obj in inspect.getmembers(errors_module, inspect.isclass)
        if issubclass(obj, Exception) and not name.startswith("_")
    ]


class TestErrorHierarchy:
    """All public errors must descend from CognitiveError."""

    def test_all_errors_subclass_cognitive_error(self) -> None:
        for cls in _all_error_classes():
            assert issubclass(cls, CognitiveError), (
                f"{cls.__name__} does not inherit from CognitiveError"
            )

    def test_no_duplicate_error_names(self) -> None:
        # Filter out aliases (InvalidKnowledgeModelError = InvalidKnowledgeItemError)
        unique_classes = set(_all_error_classes())
        names = [cls.__name__ for cls in unique_classes]
        duplicates = [n for n in names if names.count(n) > 1]
        assert duplicates == [], f"Duplicate error names: {set(duplicates)}"

    def test_all_errors_have_docstrings(self) -> None:
        for cls in _all_error_classes():
            assert cls.__doc__, f"{cls.__name__} is missing a docstring"

    def test_phase_base_errors_exist(self) -> None:
        """Each phase should have a distinct base error."""
        expected_bases = [
            "CognitiveError",
            "KnowledgeStoreError",
            "KnowledgeRetrievalError",
            "KnowledgeConsolidationError",
            "KnowledgeContradictionDetectionError",
            "KnowledgeContradictionResolutionError",
            "KnowledgeResolutionPolicyError",
            "KnowledgeResolutionExecutionError",
            "KnowledgeResolutionMemoryError",
            "KnowledgeReflectionError",
            "KnowledgeCognitiveCycleError",
        ]
        for name in expected_bases:
            assert hasattr(errors_module, name), f"Missing base error: {name}"
            cls = getattr(errors_module, name)
            assert issubclass(cls, CognitiveError)

    def test_store_errors_hierarchy(self) -> None:
        from cmm.cognitive.errors import (
            KnowledgeStoreConflictError,
            KnowledgeStoreCorruptionError,
            KnowledgeStoreError,
            KnowledgeStoreNotFoundError,
            KnowledgeStoreSchemaError,
            KnowledgeStoreSerializationError,
        )

        for cls in [
            KnowledgeStoreNotFoundError,
            KnowledgeStoreConflictError,
            KnowledgeStoreCorruptionError,
            KnowledgeStoreSchemaError,
            KnowledgeStoreSerializationError,
        ]:
            assert issubclass(cls, KnowledgeStoreError)
            assert issubclass(cls, CognitiveError)

    def test_consolidation_errors_hierarchy(self) -> None:
        from cmm.cognitive.errors import (
            InvalidConsolidationCandidateError,
            InvalidConsolidationPlanError,
            KnowledgeConsolidationApplicationError,
            KnowledgeConsolidationConflictError,
            KnowledgeConsolidationError,
            ManualReviewRequiredError,
        )

        for cls in [
            InvalidConsolidationCandidateError,
            InvalidConsolidationPlanError,
            KnowledgeConsolidationConflictError,
            KnowledgeConsolidationApplicationError,
            ManualReviewRequiredError,
        ]:
            assert issubclass(cls, KnowledgeConsolidationError)

    def test_detection_errors_hierarchy(self) -> None:
        from cmm.cognitive.errors import (
            ContradictionRegistrationError,
            InvalidContradictionDetectionError,
            InvalidContradictionSignalError,
            KnowledgeContradictionConflictError,
            KnowledgeContradictionDetectionError,
        )

        for cls in [
            InvalidContradictionSignalError,
            InvalidContradictionDetectionError,
            KnowledgeContradictionConflictError,
            ContradictionRegistrationError,
        ]:
            assert issubclass(cls, KnowledgeContradictionDetectionError)

    def test_resolution_errors_hierarchy(self) -> None:
        from cmm.cognitive.errors import (
            InvalidResolutionProposalError,
            KnowledgeContradictionResolutionError,
            ResolutionConflictError,
        )

        for cls in [InvalidResolutionProposalError, ResolutionConflictError]:
            assert issubclass(cls, KnowledgeContradictionResolutionError)

    def test_executor_errors_hierarchy(self) -> None:
        from cmm.cognitive.errors import (
            InvalidResolutionExecutionError,
            KnowledgeResolutionExecutionError,
            ResolutionExecutionConflictError,
            ResolutionExecutionRollbackError,
        )

        for cls in [
            InvalidResolutionExecutionError,
            ResolutionExecutionConflictError,
            ResolutionExecutionRollbackError,
        ]:
            assert issubclass(cls, KnowledgeResolutionExecutionError)

    def test_memory_errors_hierarchy(self) -> None:
        from cmm.cognitive.errors import (
            InvalidResolutionMemoryEntryError,
            KnowledgeResolutionMemoryError,
            ResolutionMemoryConflictError,
        )

        for cls in [InvalidResolutionMemoryEntryError, ResolutionMemoryConflictError]:
            assert issubclass(cls, KnowledgeResolutionMemoryError)

    def test_reflection_errors_hierarchy(self) -> None:
        from cmm.cognitive.errors import (
            InvalidReflectionReportError,
            KnowledgeReflectionError,
            ReflectionAnalysisConflictError,
        )

        for cls in [InvalidReflectionReportError, ReflectionAnalysisConflictError]:
            assert issubclass(cls, KnowledgeReflectionError)

    def test_cycle_errors_hierarchy(self) -> None:
        from cmm.cognitive.errors import (
            CognitiveCycleExecutionError,
            InvalidCognitiveCycleError,
            KnowledgeCognitiveCycleError,
        )

        for cls in [InvalidCognitiveCycleError, CognitiveCycleExecutionError]:
            assert issubclass(cls, KnowledgeCognitiveCycleError)

    def test_errors_importable_from_public_api(self) -> None:
        """All error classes should be in cmm.cognitive.__all__."""
        from cmm import cognitive

        for cls in _all_error_classes():
            name = cls.__name__
            # Skip the backward-compat alias
            if name == "InvalidKnowledgeModelError":
                continue
            assert name in cognitive.__all__, (
                f"{name} is not exported in cmm.cognitive.__all__"
            )

    def test_cognitive_error_is_catchable(self) -> None:
        """All cognitive errors should be catchable as CognitiveError."""
        for cls in _all_error_classes():
            if cls is CognitiveError:
                continue
            try:
                raise cls("test")
            except CognitiveError:
                pass  # Expected
            except Exception:  # noqa: BLE001
                raise AssertionError(f"{cls.__name__} not caught by CognitiveError")
