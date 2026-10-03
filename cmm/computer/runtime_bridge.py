"""Computer Use runtime over the native macOS Computer Bridge.

The PRODUCT runtime. macOS observation and action execute inside the signed
``CMM Computer Use`` helper (the grantable TCC identity), so the permission
state reported here is measured on the process that will actually perform
the operation — never on this Python interpreter.

The direct PyObjC runtime (:mod:`cmm.computer.runtime_macos`) is retained
only for explicit development use (``CMM_COMPUTER_MODE=direct``): a bare
Python interpreter has no useful grantable application identity, so it must
never be the product path.
"""

from __future__ import annotations

import base64
import binascii
import sys
import tempfile
import time
from typing import Any

from cmm.computer.bridge import (
    BridgeClient,
    BridgeUnavailable,
    default_bridge_executable,
)
from cmm.computer.contracts import (
    Action,
    ActionResult,
    ElementInfo,
    Observation,
    PermissionState,
    WindowInfo,
)
from cmm.computer.errors import ComputerUseError

__all__ = ["BridgeComputerRuntime"]

#: A screenshot larger than this (after base64 decode) is refused.
SCREENSHOT_BYTES_MAX = 24_000_000

#: Bridge failure codes the planner can adapt to. Returned as failed action
#: results instead of raised, so the Computer Use loop replans rather than
#: dying on the first refused native action. Everything else — approval
#: rejections, permission loss, runtime death, protocol violations — raises
#: and terminates, because none of those can be planned around or retried.
_RECOVERABLE_BRIDGE_CODES = frozenset(
    {"ACTION_FAILED", "COMPUTER_TARGET_UNAVAILABLE"}
)


def _failure_detail(error: ComputerUseError) -> str:
    """Planner feedback that keeps the code and the safe detail."""

    detail = f"{error.message} [{error.code}]"
    if error.detail:
        detail = f"{detail} {error.detail}"
    return detail[:500]


class BridgeComputerRuntime:
    """The same runtime surface as :class:`MacComputerRuntime`, via the bridge."""

    def __init__(self, client: BridgeClient | None = None) -> None:
        self._client = client
        self._client_owned = client is None

    def close(self) -> None:
        if self._client_owned and self._client is not None:
            self._client.close()

    # ── availability / permissions ────────────────────────────────────

    def available(self) -> bool:
        """True only when OUR signed helper answers its own ping."""

        if sys.platform != "darwin":
            return False
        try:
            self._client_or_raise().ping()
        except ComputerUseError:
            return False
        except Exception:  # noqa: BLE001 - unavailable is the honest answer
            return False
        return True

    def wait_until_ready(
        self,
        *,
        timeout: float = 12.0,
        interval: float = 1.0,
        cancel_event: Any | None = None,
    ) -> bool:
        """True once the helper answers ping; tolerates a restart window.

        The Mac app supervises the helper (relaunch on death or stale view):
        the relaunch beat plus socket rebind reads as briefly unavailable.
        That window is seconds, never minutes, so a bounded wait rejoins it
        instead of failing the run — while a genuinely absent helper still
        fails honestly after the bound. Never raises; cancellation aborts.
        """

        deadline = time.monotonic() + max(0.0, timeout)
        while True:
            if self.available():
                return True
            if cancel_event is not None and cancel_event.is_set():
                return False
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return False
            time.sleep(min(interval, remaining))

    def permissions(self) -> PermissionState:
        """Trust state of the helper process itself, not this interpreter."""

        try:
            result = self._client_or_raise().request("permissions.status")
        except ComputerUseError:
            raise
        except Exception as error:  # noqa: BLE001 - normalized below
            raise BridgeUnavailable(
                "The computer bridge permission state could not be read.",
                detail=type(error).__name__,
            ) from error
        return _permission_state(result)

    def request_accessibility(self) -> PermissionState:
        """Ask the HELPER to make the canonical Accessibility prompt."""

        try:
            result = self._client_or_raise().request(
                "permissions.request_accessibility"
            )
        except ComputerUseError:
            raise
        except Exception as error:  # noqa: BLE001 - normalized below
            raise BridgeUnavailable(
                "The computer bridge could not request Accessibility.",
                detail=type(error).__name__,
            ) from error
        return _permission_state(result)

    def request_screen_recording(self) -> PermissionState:
        """Ask the HELPER to make the canonical Screen Recording request."""

        try:
            result = self._client_or_raise().request(
                "permissions.request_screen_recording"
            )
        except ComputerUseError:
            raise
        except Exception as error:  # noqa: BLE001 - normalized below
            raise BridgeUnavailable(
                "The computer bridge could not request Screen Recording.",
                detail=type(error).__name__,
            ) from error
        return _permission_state(result)

    # ── observation ───────────────────────────────────────────────────

    def observe(self, *, include_screenshot: bool = False) -> Observation:
        try:
            result = self._client_or_raise().request(
                "observation.describe",
                {"include_screenshot": bool(include_screenshot)},
            )
        except ComputerUseError:
            raise
        except Exception as error:  # noqa: BLE001 - normalized below
            raise BridgeUnavailable(
                "The computer bridge observation could not be completed.",
                detail=type(error).__name__,
            ) from error
        return _observation(result, include_screenshot=include_screenshot)

    def capture_screenshot(self) -> str:
        """Capture the screen into an ephemeral temp PNG (caller deletes)."""

        try:
            result = self._client_or_raise().request(
                "observation.capture_screen", {}
            )
        except ComputerUseError:
            raise
        except Exception as error:  # noqa: BLE001 - normalized below
            raise BridgeUnavailable(
                "The computer bridge screenshot could not be captured.",
                detail=type(error).__name__,
            ) from error
        if not isinstance(result, dict):
            raise BridgeUnavailable(
                "The computer bridge screenshot arrived outside the protocol."
            )
        return _write_screenshot(result.get("screenshot_base64"))

    # ── execution ─────────────────────────────────────────────────────

    def execute(
        self, action: Action, observation: Observation | None = None
    ) -> ActionResult:
        _ = observation  # element refs live in the helper across requests
        try:
            result = self._client_or_raise().request(
                "action.execute",
                {"kind": action.kind, "params": dict(action.params)},
            )
        except ComputerUseError as error:
            # Recoverable native failures rejoin the loop as failed results so
            # the planner can adapt on the next step; previously every
            # ok:false raised straight out of run_task and one refused action
            # killed the whole run. Fatal conditions still raise: an approval
            # rejection must stand (never retried as a plain failure),
            # permission loss and runtime death cannot be planned around.
            if error.code in _RECOVERABLE_BRIDGE_CODES:
                return ActionResult(False, _failure_detail(error))
            raise
        except Exception as error:  # noqa: BLE001 - normalized below
            raise BridgeUnavailable(
                "The computer bridge action could not be executed.",
                detail=type(error).__name__,
            ) from error
        if not isinstance(result, dict):
            raise BridgeUnavailable(
                "The computer bridge action arrived outside the protocol."
            )
        return ActionResult(
            bool(result.get("ok", False)),
            str(result.get("message", ""))[:500],
        )

    # ── internals ─────────────────────────────────────────────────────

    def _client_or_raise(self) -> BridgeClient:
        if self._client is None:
            self._client = BridgeClient(default_bridge_executable())
        return self._client


def _permission_state(result: Any) -> PermissionState:
    if not isinstance(result, dict):
        raise BridgeUnavailable(
            "The computer bridge permission state arrived outside the protocol."
        )
    try:
        return PermissionState(
            accessibility=bool(result["accessibility"]),
            screen_recording=bool(result["screen_recording"]),
            detail=str(result.get("detail", ""))[:500],
        )
    except KeyError as error:
        raise BridgeUnavailable(
            "The computer bridge permission state is incomplete.",
            detail=str(error)[:120],
        ) from error


def _observation(result: Any, *, include_screenshot: bool) -> Observation:
    if not isinstance(result, dict):
        raise BridgeUnavailable(
            "The computer bridge observation arrived outside the protocol."
        )
    try:
        windows = tuple(
            WindowInfo(
                title=str(item.get("title", ""))[:200],
                app=str(item.get("app", ""))[:200],
                x=int(item.get("x", 0)),
                y=int(item.get("y", 0)),
                width=int(item.get("width", 0)),
                height=int(item.get("height", 0)),
            )
            for item in (result.get("windows") or [])
            if isinstance(item, dict)
        )
        elements = tuple(
            ElementInfo(
                element_id=int(item.get("element_id", 0)),
                role=str(item.get("role", ""))[:80],
                title=str(item.get("title", ""))[:120],
                value=str(item.get("value", ""))[:120],
                x=int(item.get("x", 0)),
                y=int(item.get("y", 0)),
                width=int(item.get("width", 0)),
                height=int(item.get("height", 0)),
                pressable=bool(item.get("pressable", False)),
            )
            for item in (result.get("elements") or [])
            if isinstance(item, dict)
        )
    except (TypeError, ValueError) as error:
        raise BridgeUnavailable(
            "The computer bridge observation is not well-formed.",
            detail=type(error).__name__,
        ) from error
    screenshot_path: str | None = None
    if include_screenshot:
        screenshot_path = _write_screenshot(result.get("screenshot_base64"))
    try:
        captured_at = float(result.get("captured_at", 0.0) or 0.0)
    except (TypeError, ValueError):
        captured_at = 0.0
    return Observation(
        frontmost_app=str(result.get("frontmost_app", ""))[:200],
        frontmost_bundle=str(result.get("frontmost_bundle", ""))[:200],
        windows=windows,
        elements=elements,
        screenshot_path=screenshot_path,
        captured_at=captured_at,
    )


def _write_screenshot(payload: Any) -> str:
    """Decode one bounded base64 PNG into an ephemeral temp file."""

    if not isinstance(payload, str) or not payload:
        raise ComputerUseError(
            "The screen could not be captured.", code="ACTION_FAILED"
        )
    try:
        data = base64.b64decode(payload, validate=True)
    except (binascii.Error, ValueError) as error:
        raise BridgeUnavailable(
            "The computer bridge screenshot is not valid base64.",
            detail=type(error).__name__,
        ) from error
    if len(data) > SCREENSHOT_BYTES_MAX or len(data) < 8:
        raise BridgeUnavailable(
            "The computer bridge screenshot is outside the bounded size."
        )
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        raise BridgeUnavailable(
            "The computer bridge screenshot is not a PNG frame."
        )
    path = tempfile.mkstemp(prefix="cmm-computer-", suffix=".png")[1]
    with open(path, "wb") as handle:
        handle.write(data)
    return path
