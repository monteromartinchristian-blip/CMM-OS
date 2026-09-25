"""Safe, provider-independent Model Gateway error taxonomy (Phase 11.21).

Every failure that can leave the gateway is expressed as one of a closed set of
safe codes.  Provider adapters translate provider-native failures into these
codes; nothing outside an adapter may propagate a raw provider exception,
credential value or payload fragment.

The details mapping is screened with the same JSON-safe, secret-free boundary
used by the gateway contracts, so an error can be logged or returned safely.
"""

from __future__ import annotations

from collections.abc import Mapping
from enum import Enum
from typing import Any

from kernel.llm.model_gateway_contracts import ensure_safe_metadata

__all__ = [
    "RETRYABLE_ERROR_CODES",
    "ModelGatewayError",
    "ModelGatewayErrorCode",
]


class ModelGatewayErrorCode(str, Enum):
    """Closed set of canonical, provider-independent gateway failures."""

    MODEL_NOT_FOUND = "MODEL_NOT_FOUND"
    PROVIDER_NOT_AVAILABLE = "PROVIDER_NOT_AVAILABLE"
    MODEL_UNAVAILABLE = "MODEL_UNAVAILABLE"
    CAPABILITY_UNSUPPORTED = "CAPABILITY_UNSUPPORTED"
    UNSUPPORTED_REASONING_EFFORT = "UNSUPPORTED_REASONING_EFFORT"
    INPUT_MODALITY_UNSUPPORTED = "INPUT_MODALITY_UNSUPPORTED"
    PRIVACY_DENIED = "PRIVACY_DENIED"
    PROVIDER_REQUEST_INVALID = "PROVIDER_REQUEST_INVALID"
    PROVIDER_TIMEOUT = "PROVIDER_TIMEOUT"
    PROVIDER_FAILURE = "PROVIDER_FAILURE"
    STREAM_FAILURE = "STREAM_FAILURE"
    MODEL_CALL_CANCELLED = "MODEL_CALL_CANCELLED"
    STRUCTURED_OUTPUT_INVALID = "STRUCTURED_OUTPUT_INVALID"
    TOOL_CALL_INVALID = "TOOL_CALL_INVALID"
    FALLBACK_EXHAUSTED = "FALLBACK_EXHAUSTED"


#: Only explicit transient transport/provider failures are ever retried.
#: Privacy denials, invalid requests, unsupported capabilities, unsupported
#: reasoning effort, cancellation and explicit model incompatibility are never
#: retried — retrying them could only widen a refusal or waste provider budget.
RETRYABLE_ERROR_CODES = frozenset(
    {
        ModelGatewayErrorCode.PROVIDER_TIMEOUT,
        ModelGatewayErrorCode.PROVIDER_FAILURE,
        ModelGatewayErrorCode.STREAM_FAILURE,
    }
)


class ModelGatewayError(Exception):
    """One safe, typed Model Gateway failure.

    ``message`` is a caller-safe description.  ``details`` carries only
    JSON-safe, secret-free descriptive values.  An adapter that knows a
    provider failure is permanent (for example a rejected credential) passes
    ``retryable=False``; otherwise retryability follows the canonical code set.
    """

    def __init__(
        self,
        code: ModelGatewayErrorCode,
        message: str,
        *,
        details: Mapping[str, Any] | None = None,
        retryable: bool | None = None,
    ) -> None:
        if not isinstance(code, ModelGatewayErrorCode):
            raise TypeError(
                f"code must be a ModelGatewayErrorCode, not {type(code).__name__}"
            )
        if not isinstance(message, str) or not message.strip():
            raise ValueError("message must be a non-empty string")

        self.code = code
        self.message = message.strip()
        self.details = ensure_safe_metadata(details or {}, label="error details")
        self.retryable = (
            code in RETRYABLE_ERROR_CODES if retryable is None else bool(retryable)
        )
        super().__init__(f"{code.value}: {self.message}")

    @property
    def is_retryable(self) -> bool:
        """Return whether a bounded transport retry may re-attempt this call."""

        return self.retryable

    def to_dict(self) -> dict[str, Any]:
        """Return the safe public representation of this failure."""

        return {
            "code": self.code.value,
            "message": self.message,
            "details": dict(self.details),
            "retryable": self.retryable,
        }
