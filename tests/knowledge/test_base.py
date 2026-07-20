from __future__ import annotations

from kernel.knowledge import KnowledgeBase, KnowledgeItem


def test_empty_knowledge_base() -> None:
    base = KnowledgeBase.empty()

    assert base.count == 0
    assert len(base) == 0
    assert base.list() == ()


def test_store_item_and_retrieve_it_by_key() -> None:
    item = KnowledgeItem(key="system.name", value="CMM OS")
    base = KnowledgeBase.empty()

    base.store(item)

    assert base.count == 1
    assert base.get("system.name") == item


def test_contains_reports_existing_key() -> None:
    base = KnowledgeBase([KnowledgeItem(key="status", value="active")])

    assert base.contains("status") is True
    assert base.contains("missing") is False


def test_list_returns_all_items() -> None:
    first = KnowledgeItem(key="language", value="Python")
    second = KnowledgeItem(key="version", value="3.14")
    base = KnowledgeBase([first, second])

    assert base.list() == (first, second)


def test_count_matches_number_of_items() -> None:
    base = KnowledgeBase(
        [
            KnowledgeItem(key="a", value=1),
            KnowledgeItem(key="b", value=2),
            KnowledgeItem(key="c", value=3),
        ]
    )

    assert base.count == 3
    assert len(base) == 3


def test_get_returns_none_for_missing_key() -> None:
    base = KnowledgeBase.empty()

    assert base.get("does-not-exist") is None