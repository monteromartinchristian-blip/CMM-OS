"""Reusable knowledge-delta domain model."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Any


@dataclass(frozen=True, slots=True)
class Evidence:
    """A traceable piece of evidence supporting a knowledge item."""

    source: str
    excerpt: str
    location: str | None = None
    confidence: float = 1.0
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class KnowledgeItem:
    """A single change proposal against a knowledge base entry."""

    key: str
    value: Any
    previous_value: Any | None = None
    evidence: tuple[Evidence, ...] = field(default_factory=tuple)
    metadata: dict[str, Any] = field(default_factory=dict)

    def with_evidence(self, *items: Evidence) -> "KnowledgeItem":
        """Return a new item with additional evidence attached."""

        return replace(self, evidence=self.evidence + tuple(items))


@dataclass(frozen=True, slots=True)
class KnowledgeDelta:
    """A proposed set of changes to a knowledge base."""

    additions: tuple[KnowledgeItem, ...] = field(default_factory=tuple)
    modifications: tuple[KnowledgeItem, ...] = field(default_factory=tuple)
    removals: tuple[KnowledgeItem, ...] = field(default_factory=tuple)
    contradictions: tuple[KnowledgeItem, ...] = field(default_factory=tuple)
    unresolved_questions: tuple[str, ...] = field(default_factory=tuple)

    @property
    def is_empty(self) -> bool:
        """Return whether the delta contains no changes."""

        return (
            len(self.additions) == 0
            and len(self.modifications) == 0
            and len(self.removals) == 0
            and len(self.contradictions) == 0
            and len(self.unresolved_questions) == 0
        )

    def add_addition(self, item: KnowledgeItem) -> "KnowledgeDelta":
        return replace(self, additions=self.additions + (item,))

    def add_modification(self, item: KnowledgeItem) -> "KnowledgeDelta":
        return replace(self, modifications=self.modifications + (item,))

    def add_removal(self, item: KnowledgeItem) -> "KnowledgeDelta":
        return replace(self, removals=self.removals + (item,))

    def add_contradiction(self, item: KnowledgeItem) -> "KnowledgeDelta":
        return replace(self, contradictions=self.contradictions + (item,))

    def add_unresolved_question(self, question: str) -> "KnowledgeDelta":
        return replace(self, unresolved_questions=self.unresolved_questions + (question,))
