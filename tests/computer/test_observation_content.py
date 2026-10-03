"""Observation carries visible content, not only actionable controls.

Regression coverage for the production defect behind OBSERVATION_COVERAGE
= INSUFFICIENT. The helper reported only nodes whose accessibility role was
in an interactive allowlist, so ordinary visible content — file names, table
rows, message bodies, exposed as AXStaticText / AXCell / AXImage — never
reached the planner. A real run answered "I could not count the visible
elements" while 636 labelled non-interactive nodes existed on screen.

These tests pin the contract that fixes it: content is carried separately
from elements, rendered into the planner prompt, and never presented as an
actionable target.
"""

from __future__ import annotations

from cmm.computer.contracts import (
    ContentInfo,
    ElementInfo,
    Observation,
    WindowInfo,
)
from cmm.computer.runtime_bridge import _observation


def make_observation(**overrides) -> Observation:
    base = {
        "frontmost_app": "Finder",
        "frontmost_bundle": "com.apple.finder",
        "windows": (WindowInfo(title="CMMChat-E2E-Probe", app="Finder", x=0, y=0,
                               width=800, height=600),),
        "elements": (),
        "content": (),
    }
    base.update(overrides)
    return Observation(**base)


def test_content_nodes_are_parsed_from_the_bridge_response():
    """The helper's separate content list reaches the observation."""

    result = {
        "frontmost_app": "Finder",
        "frontmost_bundle": "com.apple.finder",
        "windows": [{"title": "probe", "app": "Finder", "x": 1, "y": 2,
                     "width": 3, "height": 4}],
        "elements": [{"element_id": 1, "role": "AXButton", "title": "Atrás",
                      "value": "", "x": 5, "y": 6, "width": 7, "height": 8,
                      "pressable": True}],
        "content": [
            {"role": "AXStaticText", "text": "informe.pdf", "x": 10, "y": 20,
             "width": 30, "height": 40},
            {"role": "AXImage", "text": "captura.png", "x": 50, "y": 60,
             "width": 70, "height": 80},
        ],
    }
    obs = _observation(result, include_screenshot=False)

    assert len(obs.elements) == 1
    assert len(obs.content) == 2
    assert obs.content[0] == ContentInfo(
        role="AXStaticText", text="informe.pdf", x=10, y=20, width=30, height=40
    )
    assert obs.content[1].role == "AXImage"


def test_absent_content_key_is_treated_as_empty_not_an_error():
    """An older helper that sends no content list still parses."""

    obs = _observation(
        {"frontmost_app": "Finder", "frontmost_bundle": "", "windows": [],
         "elements": []},
        include_screenshot=False,
    )
    assert obs.content == ()


def test_content_is_rendered_into_the_planner_prompt():
    """The planner must actually see the content, not merely hold it."""

    obs = make_observation(
        content=tuple(ContentInfo(role="AXStaticText", text=f"item-{i}")
                      for i in range(7))
    )
    rendered = obs.render()

    assert "Visible content" in rendered
    for i in range(7):
        assert f"item-{i}" in rendered


def test_content_survives_an_empty_element_list():
    """The failing case: controls are gone, content is all that remains."""

    obs = make_observation(
        elements=(),
        content=tuple(ContentInfo(role="AXStaticText", text=f"file-{i}")
                      for i in range(3)),
    )
    rendered = obs.render()
    assert "file-0" in rendered
    assert "Interactive elements: none detected" in rendered


def test_content_is_never_rendered_as_an_actionable_target():
    """Content is readable, not pressable: it must carry no element id."""

    obs = make_observation(
        elements=(ElementInfo(element_id=1, role="AXButton", title="Atrás",
                              value="", x=0, y=0, width=10, height=10,
                              pressable=True),),
        content=(ContentInfo(role="AXStaticText", text="solo-lectura"),),
    )
    rendered = obs.render()
    content_line = next(
        line for line in rendered.splitlines() if "solo-lectura" in line
    )
    assert "pressable" not in content_line
    assert not content_line.strip().startswith("[1]")


def test_render_bounds_content_to_a_bounded_number_of_lines():
    """A huge content area must not produce an unbounded planner prompt."""

    obs = make_observation(
        content=tuple(ContentInfo(role="AXStaticText", text=f"n-{i}")
                      for i in range(500))
    )
    rendered = obs.render(max_elements=10)
    assert rendered.count("- AXStaticText") == 30
    assert "n-499" not in rendered


def test_malformed_content_entries_are_refused_as_before():
    import pytest

    from cmm.computer.bridge import BridgeUnavailable

    with pytest.raises(BridgeUnavailable):
        _observation(
            {"frontmost_app": "F", "frontmost_bundle": "", "windows": [],
             "elements": [], "content": [{"role": "AXStaticText",
                                          "text": "x", "width": "wide"}]},
            include_screenshot=False,
        )