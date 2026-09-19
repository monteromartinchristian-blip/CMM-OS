"""macOS Computer Use runtime — real observation and real actions.

pyobjc is imported lazily so the package stays importable (and testable with
fake runtimes) on any platform.  Observations prefer structured Accessibility
data; screenshots are ephemeral temp files, never persisted by the runtime.
"""

from __future__ import annotations

import subprocess
import sys
import tempfile
import time
from typing import Any

from cmm.computer.contracts import (
    Action,
    ActionResult,
    ElementInfo,
    Observation,
    PermissionState,
    WindowInfo,
)
from cmm.computer.errors import ComputerUseError

__all__ = ["MacComputerRuntime"]

_INTERACTIVE_ROLES = frozenset(
    {
        "AXButton",
        "AXTextField",
        "AXTextArea",
        "AXSecureTextField",
        "AXCheckBox",
        "AXRadioButton",
        "AXPopUpButton",
        "AXMenuItem",
        "AXLink",
        "AXTab",
        "AXSlider",
        "AXSwitch",
    }
)
_MAX_ELEMENTS = 60
_MAX_DEPTH = 6

_KEYCODES = {
    "a": 0, "s": 1, "d": 2, "f": 3, "h": 4, "g": 5, "z": 6, "x": 7, "c": 8,
    "v": 9, "b": 11, "q": 12, "w": 13, "e": 14, "r": 15, "y": 16, "t": 17,
    "1": 18, "2": 19, "3": 20, "4": 21, "6": 22, "5": 23, "=": 24, "9": 25,
    "7": 26, "-": 27, "8": 28, "0": 29, "]": 30, "o": 31, "u": 32, "[": 33,
    "i": 34, "p": 35, "l": 37, "j": 38, "'": 39, "k": 40, ";": 41, "\\": 42,
    ",": 43, "/": 44, "n": 45, "m": 46, ".": 47,
    "return": 36, "enter": 36, "tab": 48, "space": 49, "delete": 51,
    "backspace": 51, "escape": 53, "esc": 53, "left": 123, "right": 124,
    "down": 125, "up": 126,
}
_MODIFIERS = {
    "cmd": "kCGEventFlagMaskCommand",
    "command": "kCGEventFlagMaskCommand",
    "shift": "kCGEventFlagMaskShift",
    "option": "kCGEventFlagMaskAlternate",
    "alt": "kCGEventFlagMaskAlternate",
    "ctrl": "kCGEventFlagMaskControl",
    "control": "kCGEventFlagMaskControl",
}


def _frameworks() -> tuple[Any, Any, Any]:
    if sys.platform != "darwin":
        raise ComputerUseError(
            "Computer Use requires macOS.", code="COMPUTER_RUNTIME_UNAVAILABLE"
        )
    try:
        import AppKit
        import ApplicationServices as AXS
        import Quartz
    except ImportError as error:
        raise ComputerUseError(
            "The macOS automation frameworks are not installed.",
            code="COMPUTER_RUNTIME_UNAVAILABLE",
        ) from error
    return AppKit, AXS, Quartz


class MacComputerRuntime:
    """One runtime owning observation and execution on this Mac."""

    def __init__(self) -> None:
        self._elements: dict[int, Any] = {}
        self._element_roles: dict[int, str] = {}

    # ── availability / permissions ────────────────────────────────────────

    @staticmethod
    def available() -> bool:
        if sys.platform != "darwin":
            return False
        try:
            _frameworks()
        except ComputerUseError:
            return False
        return True

    @staticmethod
    def permissions() -> PermissionState:
        _, AXS, Quartz = _frameworks()
        accessibility = bool(AXS.AXIsProcessTrusted())
        preflight = getattr(Quartz, "CGPreflightScreenCaptureAccess", None)
        screen = bool(preflight()) if callable(preflight) else False
        missing = []
        if not accessibility:
            missing.append("Accesibilidad")
        if not screen:
            missing.append("Grabación de pantalla")
        return PermissionState(
            accessibility=accessibility,
            screen_recording=screen,
            detail=", ".join(missing),
        )

    # ── observation ───────────────────────────────────────────────────────

    def observe(self, *, include_screenshot: bool = False) -> Observation:
        AppKit, AXS, Quartz = _frameworks()
        frontmost = AppKit.NSWorkspace.sharedWorkspace().frontmostApplication()
        app_name = str(frontmost.localizedName() or "") if frontmost else ""
        bundle = str(frontmost.bundleIdentifier() or "") if frontmost else ""
        pid = int(frontmost.processIdentifier()) if frontmost else 0

        windows: list[WindowInfo] = []
        infos = Quartz.CGWindowListCopyWindowInfo(
            Quartz.kCGWindowListOptionOnScreenOnly
            | Quartz.kCGWindowListExcludeDesktopElements,
            Quartz.kCGNullWindowID,
        ) or []
        for info in infos:
            # Normal application windows only: skip menu-bar/status layers and
            # zero-sized surfaces so the observation stays useful.
            if int(info.get("kCGWindowLayer", 0)) != 0:
                continue
            bounds = info.get("kCGWindowBounds") or {}
            width = int(bounds.get("Width", 0))
            height = int(bounds.get("Height", 0))
            if width < 40 or height < 40:
                continue
            title = str(info.get("kCGWindowName") or "")
            owner = str(info.get("kCGWindowOwnerName") or "")
            windows.append(
                WindowInfo(
                    title=title,
                    app=owner,
                    x=int(bounds.get("X", 0)),
                    y=int(bounds.get("Y", 0)),
                    width=width,
                    height=height,
                )
            )
        # The frontmost application's windows are the actionable ones.
        windows.sort(key=lambda window: 0 if window.app == app_name else 1)

        self._elements = {}
        self._element_roles = {}
        elements: list[ElementInfo] = []
        if pid and AXS.AXIsProcessTrusted():
            app_element = AXS.AXUIElementCreateApplication(pid)
            self._walk(AXS, app_element, elements, depth=0)

        screenshot = self.capture_screenshot() if include_screenshot else None
        return Observation(
            frontmost_app=app_name,
            frontmost_bundle=bundle,
            windows=tuple(windows),
            elements=tuple(elements),
            screenshot_path=screenshot,
            captured_at=time.time(),
        )

    def _walk(self, AXS: Any, element: Any, out: list[ElementInfo], depth: int) -> None:
        if depth > _MAX_DEPTH or len(out) >= _MAX_ELEMENTS:
            return
        role = str(self._attr(AXS, element, "AXRole") or "")
        if role in _INTERACTIVE_ROLES:
            element_id = len(out) + 1
            actions = self._attr(AXS, element, "AXActionNames") or []
            x, y = self._geometry(AXS, element, "AXPosition", point=True)
            width, height = self._geometry(AXS, element, "AXSize", point=False)
            label = ""
            for attribute in (
                "AXTitle",
                "AXValue",
                "AXDescription",
                "AXHelp",
                "AXRoleDescription",
                "AXIdentifier",
                "AXPlaceholderValue",
            ):
                candidate = str(self._attr(AXS, element, attribute) or "").strip()
                if candidate:
                    label = candidate
                    break
            self._elements[element_id] = element
            self._element_roles[element_id] = role
            out.append(
                ElementInfo(
                    element_id=element_id,
                    role=role,
                    title=label[:120],
                    value=str(self._attr(AXS, element, "AXValue") or "")[:120],
                    x=int(x),
                    y=int(y),
                    width=int(width),
                    height=int(height),
                    pressable="AXPress" in list(actions),
                )
            )
        children = self._attr(AXS, element, "AXChildren") or []
        for child in list(children)[:40]:
            self._walk(AXS, child, out, depth + 1)

    @staticmethod
    def _attr(AXS: Any, element: Any, name: str) -> Any:
        try:
            error, value = AXS.AXUIElementCopyAttributeValue(element, name, None)
        except Exception:  # noqa: BLE001 - observation degrades, never crashes
            return None
        return value if error == 0 else None

    @staticmethod
    def _geometry(AXS: Any, element: Any, name: str, *, point: bool) -> tuple[int, int]:
        value = MacComputerRuntime._attr(AXS, element, name)
        if value is None:
            return (0, 0)
        kind = AXS.kAXValueCGPointType if point else AXS.kAXValueCGSizeType
        try:
            ok, parsed = AXS.AXValueGetValue(value, kind, None)
        except Exception:  # noqa: BLE001
            return (0, 0)
        if not ok:
            return (0, 0)
        if point:
            return (int(parsed.x), int(parsed.y))
        return (int(parsed.width), int(parsed.height))

    @staticmethod
    def capture_screenshot() -> str:
        """Capture the screen into an ephemeral temp PNG (caller deletes)."""

        AppKit, _, Quartz = _frameworks()
        if not Quartz.CGPreflightScreenCaptureAccess():
            raise ComputerUseError(
                "Screen recording permission is required for screenshots.",
                code="COMPUTER_PERMISSION_DENIED",
                detail="Grabación de pantalla",
            )
        image = Quartz.CGWindowListCreateImage(
            Quartz.CGRectNull,
            Quartz.kCGWindowListOptionOnScreenOnly,
            Quartz.kCGNullWindowID,
            Quartz.kCGWindowImageBestResolution,
        )
        if image is None:
            raise ComputerUseError(
                "The screen could not be captured.", code="ACTION_FAILED"
            )
        rep = AppKit.NSBitmapImageRep.alloc().initWithCGImage_(image)
        data = rep.representationUsingType_properties_(
            AppKit.NSBitmapImageFileTypePNG, {}
        )
        path = tempfile.mkstemp(prefix="cmm-computer-", suffix=".png")[1]
        data.writeToFile_atomically_(path, True)
        return path

    # ── execution ─────────────────────────────────────────────────────────

    def execute(self, action: Action, observation: Observation | None = None) -> ActionResult:
        AppKit, AXS, Quartz = _frameworks()
        kind = action.kind
        params = action.params
        try:
            if kind == "app.open":
                return self._app_open(str(params.get("app", "")).strip())
            if kind == "app.activate":
                return self._app_activate(AppKit, str(params.get("app", "")).strip())
            if kind == "window.focus":
                return self._window_focus(
                    AppKit, AXS, str(params.get("title", "")).strip()
                )
            if kind == "ui.press":
                return self._ui_press(AXS, params)
            if kind == "ui.set_value":
                return self._ui_set_value(AXS, params)
            if kind == "keyboard.type":
                return self._keyboard_type(Quartz, str(params.get("text", "")))
            if kind == "keyboard.shortcut":
                return self._keyboard_shortcut(Quartz, str(params.get("keys", "")))
            if kind == "pointer.click":
                return self._pointer_click(
                    Quartz, float(params.get("x", 0)), float(params.get("y", 0))
                )
            if kind == "pointer.scroll":
                return self._pointer_scroll(Quartz, int(params.get("dy", -3)))
            if kind == "wait":
                time.sleep(min(5.0, max(0.1, float(params.get("seconds", 1.0)))))
                return ActionResult(True, "waited")
        except ComputerUseError:
            raise
        except Exception as error:  # noqa: BLE001 - normalized below
            raise ComputerUseError(
                "The computer action could not be executed.",
                code="ACTION_FAILED",
                detail=type(error).__name__,
            ) from None
        raise ComputerUseError(
            f"Unsupported action: {kind}", code="CAPABILITY_UNSUPPORTED"
        )

    @staticmethod
    def _await_frontmost(AppKit: Any, app: str, timeout: float = 3.0) -> bool:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            frontmost = AppKit.NSWorkspace.sharedWorkspace().frontmostApplication()
            name = str(frontmost.localizedName() or "") if frontmost else ""
            if name.lower() == app.lower():
                return True
            time.sleep(0.15)
        return False

    @classmethod
    def _app_open(cls, app: str) -> ActionResult:
        if not app:
            return ActionResult(False, "no application name")
        completed = subprocess.run(
            ["open", "-a", app], capture_output=True, timeout=15, check=False
        )
        if completed.returncode != 0:
            raise ComputerUseError(
                f"The application {app} could not be opened.",
                code="COMPUTER_TARGET_UNAVAILABLE",
            )
        import AppKit

        if not cls._await_frontmost(AppKit, app):
            return ActionResult(
                False, f"{app} opened but did not come to the front"
            )
        return ActionResult(True, f"opened {app}")

    @classmethod
    def _app_activate(cls, AppKit: Any, app: str) -> ActionResult:
        options = (
            AppKit.NSApplicationActivateIgnoringOtherApps
            | AppKit.NSApplicationActivateAllWindows
        )
        for candidate in AppKit.NSWorkspace.sharedWorkspace().runningApplications():
            if str(candidate.localizedName() or "").lower() == app.lower():
                candidate.activateWithOptions_(options)
                if cls._await_frontmost(AppKit, app, timeout=2.0):
                    return ActionResult(True, f"activated {app}")
                candidate.activateWithOptions_(options)
                if cls._await_frontmost(AppKit, app, timeout=2.0):
                    return ActionResult(True, f"activated {app}")
                return ActionResult(
                    False, f"activation did not bring {app} to the front"
                )
        return ActionResult(False, f"application not running: {app}")

    def _window_focus(self, AppKit: Any, AXS: Any, title: str) -> ActionResult:
        for candidate in AppKit.NSWorkspace.sharedWorkspace().runningApplications():
            if not candidate.isActive():
                continue
            app_element = AXS.AXUIElementCreateApplication(
                int(candidate.processIdentifier())
            )
            for window in list(self._attr(AXS, app_element, "AXWindows") or []):
                window_title = str(self._attr(AXS, window, "AXTitle") or "")
                if title and title.lower() in window_title.lower():
                    AXS.AXUIElementPerformAction(window, "AXRaise")
                    time.sleep(0.3)
                    return ActionResult(True, f"focused “{window_title}”")
        return ActionResult(False, f"window not found: {title}")

    def _ui_press(self, AXS: Any, params: dict[str, Any]) -> ActionResult:
        element = self._resolve_element(params)
        error = AXS.AXUIElementPerformAction(element, "AXPress")
        if error != 0:
            return ActionResult(False, f"AXPress failed ({error})")
        time.sleep(0.3)
        return ActionResult(True, "pressed")

    def _ui_set_value(self, AXS: Any, params: dict[str, Any]) -> ActionResult:
        element_id = params.get("element_id")
        element = self._resolve_element(params)
        if self._element_roles.get(int(element_id)) == "AXSecureTextField":
            return ActionResult(
                False, "secure fields are never modified automatically"
            )
        error = AXS.AXUIElementSetAttributeValue(
            element, "AXValue", str(params.get("text", ""))
        )
        if error != 0:
            return ActionResult(False, f"AXSetValue failed ({error})")
        return ActionResult(True, "value set")

    def _resolve_element(self, params: dict[str, Any]) -> Any:
        try:
            element_id = int(params.get("element_id"))
        except (TypeError, ValueError):
            raise ComputerUseError(
                "The action has no valid element reference.",
                code="COMPUTER_TARGET_UNAVAILABLE",
            ) from None
        element = self._elements.get(element_id)
        if element is None:
            raise ComputerUseError(
                "The referenced UI element is no longer on screen.",
                code="COMPUTER_TARGET_UNAVAILABLE",
            )
        return element

    @staticmethod
    def _keyboard_type(Quartz: Any, text: str) -> ActionResult:
        """Type text through the pasteboard: CGEventKeyboardSetUnicodeString is
        not delivered on current macOS, while cmd+v is reliable and fast. The
        user's previous clipboard content is restored afterwards."""

        import AppKit

        pasteboard = AppKit.NSPasteboard.generalPasteboard()
        previous = pasteboard.stringForType_(AppKit.NSPasteboardTypeString)
        pasteboard.clearContents()
        if not pasteboard.setString_forType_(text, AppKit.NSPasteboardTypeString):
            return ActionResult(False, "the text could not be placed on the pasteboard")
        for down in (True, False):
            event = Quartz.CGEventCreateKeyboardEvent(None, 9, down)  # keycode 9 = 'v'
            Quartz.CGEventSetFlags(event, Quartz.kCGEventFlagMaskCommand)
            Quartz.CGEventPost(Quartz.kCGHIDEventTap, event)
            time.sleep(0.02)
        time.sleep(0.4)
        pasteboard.clearContents()
        if previous is not None:
            pasteboard.setString_forType_(previous, AppKit.NSPasteboardTypeString)
        return ActionResult(True, f"typed {len(text)} characters")

    @staticmethod
    def _keyboard_shortcut(Quartz: Any, keys: str) -> ActionResult:
        parts = [part.strip().lower() for part in keys.replace("+", " ").split() if part.strip()]
        if not parts:
            return ActionResult(False, "empty shortcut")
        flags = 0
        main = None
        for part in parts:
            if part in _MODIFIERS:
                flags |= getattr(Quartz, _MODIFIERS[part])
            else:
                main = part
        if main is None or main not in _KEYCODES:
            return ActionResult(False, f"unsupported shortcut keys: {keys}")
        keycode = _KEYCODES[main]
        for down in (True, False):
            event = Quartz.CGEventCreateKeyboardEvent(None, keycode, down)
            Quartz.CGEventSetFlags(event, flags)
            Quartz.CGEventPost(Quartz.kCGHIDEventTap, event)
        time.sleep(0.2)
        return ActionResult(True, f"shortcut {keys}")

    @staticmethod
    def _pointer_click(Quartz: Any, x: float, y: float) -> ActionResult:
        point = Quartz.CGPointMake(x, y)
        move = Quartz.CGEventCreateMouseEvent(
            None, Quartz.kCGEventMouseMoved, point, Quartz.kCGMouseButtonLeft
        )
        Quartz.CGEventPost(Quartz.kCGHIDEventTap, move)
        time.sleep(0.05)
        for kind in (Quartz.kCGEventLeftMouseDown, Quartz.kCGEventLeftMouseUp):
            event = Quartz.CGEventCreateMouseEvent(None, kind, point, Quartz.kCGMouseButtonLeft)
            Quartz.CGEventPost(Quartz.kCGHIDEventTap, event)
            time.sleep(0.04)
        return ActionResult(True, f"clicked ({int(x)},{int(y)})")

    @staticmethod
    def _pointer_scroll(Quartz: Any, dy: int) -> ActionResult:
        event = Quartz.CGEventCreateScrollWheelEvent(
            None, Quartz.kCGScrollEventUnitLine, 1, dy
        )
        Quartz.CGEventPost(Quartz.kCGHIDEventTap, event)
        time.sleep(0.2)
        return ActionResult(True, f"scrolled {dy}")
