from __future__ import annotations

from kernel.knowledge import Evidence, KnowledgeDelta, KnowledgeItem


def test_empty_knowledge_delta() -> None:
    delta = KnowledgeDelta()

    assert delta.is_empty is True
    assert delta.additions == ()
    assert delta.modifications == ()
    assert delta.removals == ()
    assert delta.contradictions == ()
    assert delta.unresolved_questions == ()


def test_is_empty_changes_when_items_are_added() -> None:
    delta = KnowledgeDelta()
    delta = delta.add_addition(KnowledgeItem(key="topic", value="Python"))

    assert delta.is_empty is False
    assert len(delta.additions) == 1


def test_adding_elements_updates_expected_state() -> None:
    addition = KnowledgeItem(key="language", value="Python")
    modification = KnowledgeItem(key="language", value="Python 3", previous_value="Python")
    removal = KnowledgeItem(key="obsolete", value=None, previous_value="old-value")
    contradiction = KnowledgeItem(key="fact", value="A", previous_value="B")

    delta = KnowledgeDelta()
    delta = delta.add_addition(addition)
    delta = delta.add_modification(modification)
    delta = delta.add_removal(removal)
    delta = delta.add_contradiction(contradiction)
    delta = delta.add_unresolved_question("Which version is canonical?")

    assert delta.additions == (addition,)
    assert delta.modifications == (modification,)
    assert delta.removals == (removal,)
    assert delta.contradictions == (contradiction,)
    assert delta.unresolved_questions == ("Which version is canonical?",)


def test_previous_value_is_preserved() -> None:
    item = KnowledgeItem(key="status", value="active", previous_value="pending")

    assert item.previous_value == "pending"
    assert item.key == "status"
    assert item.value == "active"


def test_evidence_basic_behavior() -> None:
    evidence = Evidence(
        source="document.pdf",
        excerpt="User is active",
        location="page 2",
        confidence=0.9,
        metadata={"page": 2},
    )

    assert evidence.source == "document.pdf"
    assert evidence.excerpt == "User is active"
    assert evidence.location == "page 2"
    assert evidence.confidence == 0.9
    assert evidence.metadata["page"] == 2
