from __future__ import annotations

from kernel.knowledge import KnowledgeBase, KnowledgeDelta, KnowledgeItem
from kernel.planner.merge_knowledge_operation import MergeKnowledgeOperation


def test_merge_knowledge_operation_applies_additions() -> None:
    base = KnowledgeBase.empty()
    delta = KnowledgeDelta(additions=(KnowledgeItem(key="language", value="Python"),))
    operation = MergeKnowledgeOperation(knowledge_base=base, delta=delta)

    result = operation.execute()

    assert isinstance(result, KnowledgeBase)
    assert result.get("language") == KnowledgeItem(key="language", value="Python")
    assert result.count == 1


def test_merge_knowledge_operation_applies_modifications() -> None:
    base = KnowledgeBase([KnowledgeItem(key="status", value="pending")])
    delta = KnowledgeDelta(
        modifications=(KnowledgeItem(key="status", value="active", previous_value="pending"),)
    )
    operation = MergeKnowledgeOperation(knowledge_base=base, delta=delta)

    result = operation.execute()

    assert result.get("status") == KnowledgeItem(key="status", value="active", previous_value="pending")


def test_merge_knowledge_operation_applies_removals() -> None:
    base = KnowledgeBase(
        [
            KnowledgeItem(key="keep", value=True),
            KnowledgeItem(key="remove", value=False),
        ]
    )
    delta = KnowledgeDelta(removals=(KnowledgeItem(key="remove", value=False),))
    operation = MergeKnowledgeOperation(knowledge_base=base, delta=delta)

    result = operation.execute()

    assert result.contains("keep") is True
    assert result.contains("remove") is False
    assert result.count == 1


def test_merge_knowledge_operation_handles_empty_delta() -> None:
    base = KnowledgeBase([KnowledgeItem(key="topic", value="knowledge")])
    operation = MergeKnowledgeOperation(knowledge_base=base, delta=KnowledgeDelta())

    result = operation.execute()

    assert result == base
    assert result is not base


def test_merge_knowledge_operation_returns_valid_knowledge_base() -> None:
    base = KnowledgeBase.empty()
    delta = KnowledgeDelta(additions=(KnowledgeItem(key="fact", value="value"),))

    result = MergeKnowledgeOperation(knowledge_base=base, delta=delta).execute()

    assert isinstance(result, KnowledgeBase)
    assert result.count == 1
    assert result.list()[0] == KnowledgeItem(key="fact", value="value")


def test_merge_knowledge_operation_does_not_modify_original_base() -> None:
    base = KnowledgeBase([KnowledgeItem(key="status", value="pending")])
    delta = KnowledgeDelta(modifications=(KnowledgeItem(key="status", value="active"),))
    before = base.list()

    result = MergeKnowledgeOperation(knowledge_base=base, delta=delta).execute()

    assert base.list() == before
    assert base.get("status") == KnowledgeItem(key="status", value="pending")
    assert result.get("status") == KnowledgeItem(key="status", value="active")