"""Phase 8.5 – Knowledge Store interface and implementations.

Re-exports store contracts, in-memory implementation, and SQLite implementation.
"""

from __future__ import annotations

from cmm.cognitive.store_contracts import (
    KNOWLEDGE_STORE_SCHEMA_VERSION,
    KnowledgeStoreProtocol,
    validate_store_id,
)
from cmm.cognitive.store_memory import InMemoryKnowledgeStore
from cmm.cognitive.store_sqlite import SQLiteKnowledgeStore

# Public alias per requirements
LocalKnowledgeStore = SQLiteKnowledgeStore

__all__ = [
    "KNOWLEDGE_STORE_SCHEMA_VERSION",
    "InMemoryKnowledgeStore",
    "KnowledgeStoreProtocol",
    "LocalKnowledgeStore",
    "SQLiteKnowledgeStore",
    "validate_store_id",
]
