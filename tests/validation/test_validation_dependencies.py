import pytest

from cmm.validation.steps import ValidationStep, ValidationStepType
from cmm.validation.pipeline import _topological_sort, _subset_with_dependencies


def test_topological_sort_and_missing_dep():
    a = ValidationStep(name="a", command=("echo",), dependencies=())
    b = ValidationStep(name="b", command=("echo",), dependencies=("a",))
    c = ValidationStep(name="c", command=("echo",), dependencies=("b",))
    ordered = _topological_sort((a, b, c))
    assert [s.name for s in ordered] == ["a", "b", "c"]

    # missing dependency
    with pytest.raises(Exception):
        _topological_sort((ValidationStep(name="x", command=("echo",), dependencies=("missing",)),))


def test_cycle_and_duplicates():
    a = ValidationStep(name="a", command=("echo",), dependencies=("c",))
    b = ValidationStep(name="b", command=("echo",), dependencies=("a",))
    c = ValidationStep(name="c", command=("echo",), dependencies=("b",))
    with pytest.raises(Exception):
        _topological_sort((a, b, c))

    d1 = ValidationStep(name="d", command=("echo",))
    d2 = ValidationStep(name="d", command=("echo",))
    with pytest.raises(Exception):
        _topological_sort((d1, d2))


def test_subset_with_dependencies():
    a = ValidationStep(name="a", command=("echo",))
    b = ValidationStep(name="b", command=("echo",), dependencies=("a",))
    c = ValidationStep(name="c", command=("echo",), dependencies=("b",))
    all_steps = (a, b, c)

    subset = _subset_with_dependencies(all_steps, ("c",))
    assert [s.name for s in subset] == ["a", "b", "c"]

    with pytest.raises(Exception):
        _subset_with_dependencies(all_steps, ("missing",))
