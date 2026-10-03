"""Frozen data contracts of the Computer Use capability."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

__all__ = [
    "ACTION_KINDS",
    "HUMAN_STATES",
    "Action",
    "ActionResult",
    "ApprovalProposal",
    "ComputerTaskOutcome",
    "ComputerUseLimits",
    "ContentInfo",
    "ElementInfo",
    "Observation",
    "PermissionState",
    "WindowInfo",
]

#: The normalized action vocabulary (roadmap 11.61 human-control states).
ACTION_KINDS = frozenset(
    {
        "app.open",
        "app.activate",
        "window.focus",
        "ui.press",
        "ui.set_value",
        "keyboard.type",
        "keyboard.shortcut",
        "pointer.click",
        "pointer.scroll",
        "wait",
        "finish",
    }
)

HUMAN_STATES = frozenset(
    {
        "RUNNING_AUTOMATED",
        "WAITING_FOR_HUMAN",
        "HUMAN_CONTROL",
        "RESUMING_AUTOMATION",
        "COMPLETED",
        "FAILED",
        "CANCELLED",
    }
)


@dataclass(frozen=True, slots=True)
class PermissionState:
    accessibility: bool
    screen_recording: bool
    detail: str = ""

    @property
    def satisfied(self) -> bool:
        return self.accessibility


@dataclass(frozen=True, slots=True)
class ContentInfo:
    """One read-only node of visible content (never an actionable target)."""

    role: str
    text: str
    x: int = 0
    y: int = 0
    width: int = 0
    height: int = 0


@dataclass(frozen=True, slots=True)
class ElementInfo:
    element_id: int
    role: str
    title: str
    value: str
    x: int
    y: int
    width: int
    height: int
    pressable: bool


@dataclass(frozen=True, slots=True)
class WindowInfo:
    title: str
    app: str
    x: int
    y: int
    width: int
    height: int


@dataclass(frozen=True, slots=True)
class Observation:
    frontmost_app: str
    frontmost_bundle: str
    windows: tuple[WindowInfo, ...]
    elements: tuple[ElementInfo, ...]
    #: Ordinary visible content: text and values a person can read but
    #: cannot act on (file names, table rows, message bodies). Kept separate
    #: from ``elements`` because sharing one budget meant a content area
    #: never reached the planner once the surrounding toolbars filled it.
    content: tuple[ContentInfo, ...] = ()
    screenshot_path: str | None = None
    captured_at: float = 0.0

    def render(self, *, max_elements: int = 40) -> str:
        """Structured text observation for the planner (no screenshots needed)."""

        lines = [f"Frontmost application: {self.frontmost_app}"]
        if self.windows:
            lines.append("Windows on screen:")
            for window in self.windows[:8]:
                lines.append(
                    f"- {window.app} / “{window.title}” "
                    f"({window.x},{window.y} {window.width}x{window.height})"
                )
        if self.content:
            lines.append(
                f"Visible content of the frontmost application "
                f"({len(self.content)} items, read-only):"
            )
            for item in self.content[: max_elements * 3]:
                lines.append(f"- {item.role} “{item.text[:120]}”")
        if self.elements:
            lines.append("Interactive elements of the frontmost application:")
            for element in self.elements[:max_elements]:
                label = element.title or element.value
                lines.append(
                    f"[{element.element_id}] {element.role} “{label[:80]}” "
                    f"({element.x},{element.y} {element.width}x{element.height})"
                    + (" pressable" if element.pressable else "")
                )
        else:
            lines.append("Interactive elements: none detected")
        return "\n".join(lines)


@dataclass(frozen=True, slots=True)
class Action:
    kind: str
    params: dict[str, Any] = field(default_factory=dict)
    target_description: str = ""

    def __post_init__(self) -> None:
        if self.kind not in ACTION_KINDS:
            raise ValueError(f"unknown computer action kind: {self.kind}")

    def describe(self, observation: Observation | None = None) -> str:
        app = str(self.params.get("app", "")).strip()
        if self.kind == "app.open":
            return f"Abrir la aplicación {app}"
        if self.kind == "app.activate":
            return f"Activar la aplicación {app}"
        if self.kind == "window.focus":
            return f"Enfocar la ventana “{self.params.get('title', '')}”"
        if self.kind in ("ui.press", "ui.set_value"):
            element = _find_element(observation, self.params.get("element_id"))
            label = element.title or element.value if element else ""
            verb = "Pulsar" if self.kind == "ui.press" else "Rellenar"
            text = (
                f" con «{self.params.get('text', '')}»"
                if self.kind == "ui.set_value"
                else ""
            )
            return f"{verb} “{label or self.params.get('element_id')}”{text}"
        if self.kind == "keyboard.type":
            preview = str(self.params.get("text", ""))
            return f"Escribir «{preview[:40]}{'…' if len(preview) > 40 else ''}»"
        if self.kind == "keyboard.shortcut":
            return f"Pulsar el atajo {self.params.get('keys', '')}"
        if self.kind == "pointer.click":
            return f"Hacer clic en ({self.params.get('x')},{self.params.get('y')})"
        if self.kind == "pointer.scroll":
            return "Desplazar la vista"
        if self.kind == "wait":
            return "Esperar"
        return "Finalizar la tarea"


def _find_element(
    observation: Observation | None, element_id: Any
) -> ElementInfo | None:
    if observation is None:
        return None
    try:
        wanted = int(element_id)
    except (TypeError, ValueError):
        return None
    return next(
        (item for item in observation.elements if item.element_id == wanted), None
    )


@dataclass(frozen=True, slots=True)
class ActionResult:
    ok: bool
    detail: str = ""
    executed: bool = True


@dataclass(frozen=True, slots=True)
class ApprovalProposal:
    tool_run_id: str
    action_description: str
    app: str
    reason: str
    consequence: str
    egress: str  # "none" | "screen_content"


@dataclass(frozen=True, slots=True)
class ComputerUseLimits:
    max_steps: int = 12


@dataclass(frozen=True, slots=True)
class ComputerTaskOutcome:
    summary: str
    steps: int
    actions: tuple[str, ...]
    approvals: int = 0
    rejections: int = 0
    warnings: tuple[str, ...] = ()
