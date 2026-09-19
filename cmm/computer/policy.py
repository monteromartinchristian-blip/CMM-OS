"""Computer Use action policy: what auto-executes, what needs approval,
what is denied outright.  One policy authority for the capability."""

from __future__ import annotations

import re
from dataclasses import dataclass

from cmm.computer.contracts import Action, Observation

__all__ = ["PolicyDecision", "classify_action"]

_SENSITIVE_LABEL = re.compile(
    r"\b(send|enviar|publish|publicar|delete|eliminar|remove|quitar|install"
    r"|instalar|uninstall|desinstalar|purchase|comprar|pay|pagar|buy|subscribe"
    r"|suscri|accept|aceptar|confirm|confirmar|force quit|forzar|reset"
    r"|restablecer|erase|borrar|empty trash|vaciar|sign out|cerrar sesion"
    r"|cerrar sesión|log out|upload|subir|share|compartir)\b",
    re.IGNORECASE,
)
_COMMUNICATION_APPS = frozenset(
    {
        "mail",
        "messages",
        "mensajes",
        "whatsapp",
        "telegram",
        "slack",
        "discord",
        "signal",
        "wechat",
    }
)
_DENY_SHORTCUTS = frozenset(
    {"cmd+option+esc", "command+option+esc", "cmd+shift+option+esc"}
)


@dataclass(frozen=True, slots=True)
class PolicyDecision:
    decision: str  # "auto" | "approval" | "deny"
    reason: str = ""
    consequence: str = ""
    egress: str = "none"


def classify_action(
    action: Action, observation: Observation | None = None
) -> PolicyDecision:
    """Classify one normalized action against the approval policy."""

    kind = action.kind
    params = action.params

    if kind in ("wait", "finish", "pointer.scroll", "app.activate", "window.focus"):
        return PolicyDecision("auto")

    if kind == "app.open":
        return PolicyDecision(
            "auto",
            consequence="Se abrirá una aplicación en el Mac.",
        )

    if kind == "keyboard.shortcut":
        keys = str(params.get("keys", "")).strip().lower().replace("⌘", "cmd+")
        if keys in _DENY_SHORTCUTS:
            return PolicyDecision(
                "approval",
                reason="El atajo puede forzar la salida de aplicaciones.",
                consequence="Una aplicación podría cerrarse perdiendo cambios.",
            )
        return PolicyDecision("auto")

    if kind in ("keyboard.type", "ui.set_value"):
        text = str(params.get("text", ""))
        if observation is not None and _frontmost_is_communication(observation):
            return PolicyDecision(
                "approval",
                reason="La aplicación activa permite enviar mensajes a otras personas.",
                consequence="El texto escrito podría enviarse a terceros.",
                egress="screen_content",
            )
        if _SENSITIVE_LABEL.search(text):
            return PolicyDecision(
                "approval",
                reason="El texto a escribir menciona una operación sensible.",
                consequence="Podría registrar o enviar información sensible.",
                egress="screen_content",
            )
        return PolicyDecision("auto", egress="screen_content")

    if kind in ("ui.press", "pointer.click"):
        label = _target_label(action, observation)
        if _SENSITIVE_LABEL.search(label):
            return PolicyDecision(
                "approval",
                reason=f"El control “{label[:60]}” realiza una acción sensible.",
                consequence="La acción puede enviar, publicar, eliminar o comprar.",
                egress="screen_content",
            )
        return PolicyDecision("auto")

    return PolicyDecision("approval", reason="Acción no reconocida por la política.")


def _target_label(action: Action, observation: Observation | None) -> str:
    label = str(action.params.get("label", "") or action.target_description or "")
    if observation is not None:
        try:
            wanted = int(action.params.get("element_id"))
        except (TypeError, ValueError):
            wanted = None
        if wanted is not None:
            element = next(
                (item for item in observation.elements if item.element_id == wanted),
                None,
            )
            if element is not None:
                label = f"{label} {element.title} {element.value}".strip()
    return label or " "


def _frontmost_is_communication(observation: Observation) -> bool:
    name = (observation.frontmost_app or "").strip().lower()
    return name in _COMMUNICATION_APPS
