"""Architecture primitives for the CMM OS technical knowledge graph."""

from __future__ import annotations

from cmm.memory.graph import KnowledgeGraph
from cmm.memory.indexer import ProjectIndexer
from cmm.memory.models import KnowledgeEdge, KnowledgeNode, RelationType
from cmm.memory.query import KnowledgeQuery
from cmm.memory.repository import KnowledgeRepository
from cmm.memory.persistence import (
    CorruptRepositoryError,
    FileFingerprint,
    IncompatibleRepositoryError,
    PersistentKnowledgeRepository,
    ProjectMismatchError,
    ProjectSnapshot,
    RepositoryError,
    RepositoryNotFoundError,
)
from cmm.memory.results import MemoryLoadResult, MemoryRefreshResult, ProjectChangeSet, RepositoryResult
from cmm.memory.technical_memory import TechnicalMemory
from cmm.memory.technical_reasoner import TechnicalReasoner

__all__ = [
    "KnowledgeEdge",
    "KnowledgeGraph",
    "KnowledgeNode",
    "KnowledgeQuery",
    "KnowledgeRepository",
    "PersistentKnowledgeRepository",
    "RepositoryError",
    "RepositoryNotFoundError",
    "CorruptRepositoryError",
    "IncompatibleRepositoryError",
    "ProjectMismatchError",
    "FileFingerprint",
    "ProjectSnapshot",
    "ProjectChangeSet",
    "MemoryLoadResult",
    "MemoryRefreshResult",
    "RepositoryResult",
    "ProjectIndexer",
    "RelationType",
    "TechnicalMemory",
    "TechnicalReasoner",
]
