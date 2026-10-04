"""Three states for a reasoning-effort capability, kept apart end to end.

A model whose effort capability nobody stated, a model known to expose no effort
control, and a model with an exact ladder are three different answers. The wire
and the projection used to carry only two, so the first two arrived identical:
``_declared_reasoning_efforts`` returned ``()`` for both an absent key and an
empty list, and ``reasoning=bool(declared_efforts)`` then turned an undeclared
capability into a declared absence.

The invariant these tests exist to protect is ``None != ()``.
"""

from __future__ import annotations

from typing import Any

import pytest

from cmm.model_execution.composition import (
    _declared_reasoning_efforts,
    _derive_reasoning,
)
from kernel.llm.capabilities import ModelCapabilities, ReasoningEffort


# --- projection: what the authority said becomes what CMM OS holds ----------


def test_absent_declaration_is_unknown_not_empty() -> None:
    # UNKNOWN: no key at all.
    assert _declared_reasoning_efforts({}) is None
    assert _declared_reasoning_efforts({"id": "x"}) is None


def test_explicit_null_is_unknown() -> None:
    assert _declared_reasoning_efforts({"reasoning_efforts": None}) is None


def test_empty_list_is_known_none_not_unknown() -> None:
    # KNOWN_NONE. This is the case that used to be indistinguishable from
    # UNKNOWN, and it is the one that matters: a model known to expose no
    # effort control must not behave as merely unstated.
    assert _declared_reasoning_efforts({"reasoning_efforts": []}) == ()


def test_empty_does_not_become_none_and_none_does_not_become_empty() -> None:
    unknown = _declared_reasoning_efforts({})
    known_none = _declared_reasoning_efforts({"reasoning_efforts": []})
    assert unknown is not known_none
    assert unknown is None
    assert known_none is not None
    assert known_none == ()


@pytest.mark.parametrize("wrong", [5, "low", {"a": 1}, True])
def test_non_sequence_declaration_is_an_honest_unknown(wrong: Any) -> None:
    # Not something to invent a ladder from, and not something to call an
    # explicit absence either.
    assert _declared_reasoning_efforts({"reasoning_efforts": wrong}) is None


# --- derivation: reasoning is derived from the ladder, never from truthiness --


def test_reasoning_is_tri_state() -> None:
    assert _derive_reasoning(None) is None
    assert _derive_reasoning(()) is False
    assert _derive_reasoning(("low",)) is True


def test_unknown_reasoning_is_not_false() -> None:
    # The regression: bool(()) collapsed this to False.
    assert _derive_reasoning(None) is not False


# --- translation: exact, and the two top rungs stay distinct ----------------


def test_provider_ladder_translates_exactly() -> None:
    assert _declared_reasoning_efforts(
        {"reasoning_efforts": ["low", "medium", "high"]}
    ) == ("low", "medium", "high")


def test_five_level_claude_ladder_keeps_extra_high_and_max_distinct() -> None:
    # Claude Opus 5.5 declares five rungs; `xhigh` is the provider spelling of
    # `extra_high`, and `max` is a rung of its own.
    declared = _declared_reasoning_efforts(
        {"reasoning_efforts": ["low", "medium", "high", "xhigh", "max"]}
    )
    assert declared == ("low", "medium", "high", "extra_high", "max")


def test_canonical_spelling_survives_translation() -> None:
    assert _declared_reasoning_efforts({"reasoning_efforts": ["extra_high"]}) == (
        "extra_high",
    )


def test_extra_high_and_max_are_different_rungs() -> None:
    ladder = _declared_reasoning_efforts(
        {"reasoning_efforts": ["xhigh", "max"]}
    )
    assert ladder == ("extra_high", "max")
    assert ladder[0] != ladder[1]
    assert len(set(ladder)) == 2


def test_four_level_ladder_omits_extra_high_entirely() -> None:
    # Claude Opus 4.6 and Sonnet 4.6 declare four rungs with no xhigh at all.
    declared = _declared_reasoning_efforts(
        {"reasoning_efforts": ["low", "medium", "high", "max"]}
    )
    assert declared == ("low", "medium", "high", "max")
    assert "extra_high" not in declared


def test_untranslatable_level_is_dropped_rather_than_invented() -> None:
    declared = _declared_reasoning_efforts(
        {"reasoning_efforts": ["low", "banana", "high"]}
    )
    assert declared == ("low", "high")


# --- concrete fixtures -----------------------------------------------------


def test_haiku_fixture_is_known_none() -> None:
    # The account declares thinking.type "none" with no effort options, and
    # both runtimes report supportsEffort absent. The Router publishes no
    # ladder, so CMM OS sees an absent key -- which is UNKNOWN, not the
    # KNOWN_NONE that the evidence would support. That gap is exactly what the
    # Router-side [] must close; until then this fixture documents what
    # actually arrives rather than what should.
    assert _declared_reasoning_efforts({"id": "claude/claude-haiku-4-5-20251001"}) is None


def test_haiku_with_explicit_empty_list_is_known_none() -> None:
    assert (
        _declared_reasoning_efforts(
            {"id": "claude/claude-haiku-4-5-20251001", "reasoning_efforts": []}
        )
        == ()
    )


def test_claude_five_level_fixture() -> None:
    assert _declared_reasoning_efforts(
        {
            "id": "claude/claude-opus-5-5",
            "reasoning_efforts": ["low", "medium", "high", "xhigh", "max"],
        }
    ) == ("low", "medium", "high", "extra_high", "max")


def test_claude_four_level_fixture() -> None:
    assert _declared_reasoning_efforts(
        {
            "id": "claude/claude-opus-4-6",
            "reasoning_efforts": ["low", "medium", "high", "max"],
        }
    ) == ("low", "medium", "high", "max")


def test_chatgpt_declared_ladder_is_preserved() -> None:
    # The Codex effort catalog declares a ladder for these models, so CMM OS
    # receives one and must publish reasoning=True.
    assert _declared_reasoning_efforts(
        {"id": "chatgpt/gpt-5.5", "reasoning_efforts": ["low", "medium", "high"]}
    ) == ("low", "medium", "high")


def test_genuinely_unknown_model_is_unknown() -> None:
    assert _declared_reasoning_efforts({"id": "some/unlisted-model"}) is None


# --- the capability object itself ------------------------------------------


def test_capabilities_default_to_unknown() -> None:
    capabilities = ModelCapabilities()
    assert capabilities.reasoning_efforts is None
    assert capabilities.reasoning is None


def test_capabilities_distinguish_known_empty_from_unknown() -> None:
    unknown = ModelCapabilities()
    known_none = ModelCapabilities(reasoning_efforts=(), reasoning=False)
    assert unknown.reasoning_efforts is None
    assert known_none.reasoning_efforts == ()
    assert unknown.reasoning_efforts != known_none.reasoning_efforts


def test_capabilities_normalize_a_declared_ladder() -> None:
    capabilities = ModelCapabilities(
        reasoning_efforts=(ReasoningEffort.LOW, ReasoningEffort.EXTRA_HIGH)
    )
    assert capabilities.reasoning_efforts == (
        ReasoningEffort.LOW,
        ReasoningEffort.EXTRA_HIGH,
    )


def test_capabilities_still_reject_duplicates() -> None:
    with pytest.raises(ValueError, match="unique"):
        ModelCapabilities(
            reasoning_efforts=(ReasoningEffort.LOW, ReasoningEffort.LOW)
        )


def test_undeclared_ladder_fails_closed_for_every_level() -> None:
    # Unchanged behaviour: a missing declaration was projected to () before and
    # refused everything then too. Failing closed is the safe direction.
    unknown = ModelCapabilities()
    for effort in (ReasoningEffort.LOW, ReasoningEffort.EXTRA_HIGH, ReasoningEffort.MAX):
        assert unknown.supports_reasoning_effort(effort) is False


def test_known_none_refuses_every_level_too() -> None:
    known_none = ModelCapabilities(reasoning_efforts=())
    for effort in (ReasoningEffort.LOW, ReasoningEffort.EXTRA_HIGH):
        assert known_none.supports_reasoning_effort(effort) is False


def test_declared_ladder_refuses_a_level_it_does_not_declare() -> None:
    capabilities = ModelCapabilities(reasoning_efforts=(ReasoningEffort.LOW,))
    assert capabilities.supports_reasoning_effort(ReasoningEffort.LOW) is True
    assert capabilities.supports_reasoning_effort(ReasoningEffort.MAX) is False


def test_default_is_always_acceptable_and_never_stored() -> None:
    capabilities = ModelCapabilities(reasoning_efforts=(ReasoningEffort.LOW,))
    assert capabilities.supports_reasoning_effort(ReasoningEffort.DEFAULT) is True
    assert ReasoningEffort.DEFAULT not in capabilities.reasoning_efforts


def test_no_default_level_is_invented_anywhere() -> None:
    # `none` exists in the enum but must never be published as a declared rung:
    # a model with no effort levels carries the empty ladder instead, so a
    # client can tell "no levels" from "the level literally called none".
    assert ModelCapabilities().reasoning_efforts is None
    assert ModelCapabilities(reasoning_efforts=()).reasoning_efforts == ()
    declared = _declared_reasoning_efforts(
        {"reasoning_efforts": ["low", "none", "high"]}
    )
    assert "none" not in declared