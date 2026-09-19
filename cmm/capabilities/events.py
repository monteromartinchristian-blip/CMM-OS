"""Normalized capability event grammar (roadmap 11.22 names)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

__all__ = ["EVENT_KINDS", "CapabilityEvent", "CapabilityRequest"]

EVENT_KINDS = frozenset(
    {
        "tool.requested",
        "tool.started",
        "tool.progress",
        "tool.completed",
        "tool.failed",
        "tool.cancelled",
        "approval.requested",
        "approval.resolved",
        "computer.observation",
        "message.delta",
        "run.summary",
    }
)


@dataclass(frozen=True, slots=True)
class CapabilityEvent:
    kind: str
    data: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.kind not in EVENT_KINDS:
            raise ValueError(f"unknown capability event kind: {self.kind}")


@dataclass(frozen=True, slots=True)
class CapabilityRequest:
    """What the product enabled for one run (never how it is implemented)."""

    web_search: str = "off"  # "auto" | "on" | "off"
    computer_use: bool = False

    def __post_init__(self) -> None:
        if self.web_search not in ("auto", "on", "off"):
            raise ValueError("web_search must be auto, on or off")
