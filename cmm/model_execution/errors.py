"""CMMChat Wave E0 — fail-closed defects of the model execution seam.

The seam converts every provider, transport and response defect into a
normalized :class:`~cmm.model_execution.contracts.ModelExecutionResult` failure.
An exception therefore never escapes ``execute``.

:class:`ModelExecutionError` is the narrow exception for the seam's own
*internal* fail-closed conditions — currently the absence of the canonical
orchestration decision a turn's execution must be bound to.  It carries an
application-owned message and an optional safe reason code and never exposes
provider text, a response body, a credential, a filesystem path or a traceback.
"""

from __future__ import annotations

__all__ = ["ModelExecutionError"]

#: The safe reason code reported when the canonical decision a turn's execution
#: is bound to cannot be resolved from the canonical orchestration authority.
CANONICAL_DECISION_UNAVAILABLE = "CANONICAL_DECISION_UNAVAILABLE"


def _require_text(value: object, *, label: str) -> str:
    """Return a non-empty, stripped text value or fail closed."""

    if not isinstance(value, str):
        raise TypeError(f"{label} must be a string")
    normalized = value.strip()
    if not normalized:
        raise ValueError(f"{label} must be non-empty")
    return normalized


class ModelExecutionError(RuntimeError):
    """A fail-closed internal defect of the canonical model execution seam.

    The message and the code are application-owned constants.  The exception
    never wraps a provider error, so no upstream text can become public through
    it; the optional ``details`` mapping carries only safe identifiers.
    """

    def __init__(
        self,
        message: str,
        *,
        code: str = CANONICAL_DECISION_UNAVAILABLE,
        details: dict[str, str] | None = None,
    ) -> None:
        self.message = _require_text(message, label="message")
        self.code = _require_text(code, label="code")
        self.details: dict[str, str] = {
            key: value for key, value in (details or {}).items()
        }
        super().__init__(self.message)

    def to_dict(self) -> dict[str, object]:
        """Return the safe representation of this defect."""

        return {
            "code": self.code,
            "message": self.message,
            "details": dict(self.details),
        }
