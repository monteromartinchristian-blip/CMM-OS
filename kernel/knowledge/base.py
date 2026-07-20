"""Persistent knowledge base container."""

from __future__ import annotations

from collections.abc import Iterable

from kernel.knowledge.delta import KnowledgeItem


class KnowledgeBase:
    """In-memory knowledge base indexed by item key."""

    __slots__ = ("_items",)

    def __init__(self, items: Iterable[KnowledgeItem] | None = None):
        self._items: dict[str, KnowledgeItem] = {}

        if items is not None:
            for item in items:
                self.store(item)

    @classmethod
    def empty(cls) -> "KnowledgeBase":
        """Return an empty knowledge base."""

        return cls()

    def store(self, item: KnowledgeItem) -> None:
        """Insert or replace a knowledge item by key."""

        self._items[item.key] = item

    def get(self, key: str) -> KnowledgeItem | None:
        """Return the knowledge item stored for a key, if any."""

        return self._items.get(key)

    def contains(self, key: str) -> bool:
        """Return whether the key exists in the knowledge base."""

        return key in self._items

    def list(self) -> tuple[KnowledgeItem, ...]:
        """Return all stored knowledge items in insertion order."""

        return tuple(self._items.values())

    @property
    def count(self) -> int:
        """Return the number of stored items."""

        return len(self._items)

    def __len__(self) -> int:
        return self.count

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, KnowledgeBase):
            return NotImplemented

        return self.list() == other.list()