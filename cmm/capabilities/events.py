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
    """What the product enabled for one run (never how it is implemented).

    ``computer_use`` accepts the legacy boolean (True=force task, False=off)
    and the intent-routing vocabulary ``auto``/``on``/``off``; it is always
    normalized to the string form.
    """

    web_search: str = "off"  # "auto" | "on" | "off"
    computer_use: bool | str = False

    def __post_init__(self) -> None:
        if self.web_search not in ("auto", "on", "off"):
            raise ValueError("web_search must be auto, on or off")
        normalized: str
        if isinstance(self.computer_use, bool):
            normalized = "on" if self.computer_use else "off"
        elif isinstance(self.computer_use, str) and self.computer_use in (
            "auto",
            "on",
            "off",
        ):
            normalized = self.computer_use
        else:
            raise ValueError("computer_use must be a bool or auto/on/off")
        object.__setattr__(self, "computer_use", normalized)

    @property
    def computer_mode(self) -> str:
        return str(self.computer_use)
