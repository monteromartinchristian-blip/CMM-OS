"""Transformation graph representation."""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping

from cmm.transformations.models import TransformationGraphNode


@dataclass(frozen=True)
class TransformationGraph:
    """Directed acyclic graph representation for transformation execution."""

    nodes: Mapping[str, TransformationGraphNode]

    def __post_init__(self) -> None:
        nodes = dict(self.nodes)
        for node_id, node in nodes.items():
            if node_id != node.step.id:
                raise ValueError(
                    "Transformation graph node key must match TransformationStep.id."
                )

        object.__setattr__(self, "nodes", MappingProxyType(nodes))
