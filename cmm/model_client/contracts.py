"""Public contracts of the stable CMMChat model-execution client boundary.

Everything a first-party client may see is declared here and nowhere else:
frozen descriptors carrying the full capability truth, the closed stream-event
grammar, and the closed error vocabulary the seam can raise.  No type in this
module may carry a provider implementation detail, and no client may reach past
it into ``cmm.model_execution`` or ``kernel.llm``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any, Mapping

#: The version of this boundary.  A client pins against it; a change that
#: removes or re-semanticizes a field must bump it.
#:
#: v2 adds ``version`` and ``status`` to :class:`ClientModelDescriptor`.  Both
#: are additive with honest ``None``/``"available"`` defaults, so a v1 client
#: keeps decoding a v2 payload; the bump marks that the descriptor now carries
#: facts a v1 client had no field to show.
MODEL_CLIENT_INTERFACE_VERSION = "2"

#: The closed error vocabulary the seam can raise.  Messages are the seam's own
#: and may carry upstream detail, so a client must map the *code* onto its own
#: user-safe text and never forward the message.
MODEL_CLIENT_ERROR_CODES = frozenset(
    {
        "CMM_OS_UNAVAILABLE",
        "NO_MODELS_AVAILABLE",
        "MODEL_UNAVAILABLE",
        "PROVIDER_UNAVAILABLE",
        "PROVIDER_FAILURE",
        "CHAT_PROMPT_INVALID",
        "UNSUPPORTED_REASONING_EFFORT",
        "TIMEOUT",
        "CANCELLED",
        "SEARCH_BACKEND_UNAVAILABLE",
        "SEARCH_TIMEOUT",
        "SEARCH_BLOCKED",
        "FETCH_FAILED",
        "SOURCE_BLOCKED",
        "COMPUTER_RUNTIME_UNAVAILABLE",
        "COMPUTER_PERMISSION_DENIED",
        "COMPUTER_TARGET_UNAVAILABLE",
        "ACTION_FAILED",
        "APPROVAL_REJECTED",
        "CAPABILITY_UNSUPPORTED",
        "TOOL_RUNTIME_ERROR",
    }
)


class ModelClientError(Exception):
    """A normalized seam failure carrying a closed code and the seam's message."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        if code not in MODEL_CLIENT_ERROR_CODES:
            raise ValueError(f"unknown model client error code: {code}")
        self.code = code
        self.message = message


@dataclass(frozen=True, slots=True)
class ClientModelDescriptor:
    """One model projected for a client selector, with its full capability truth."""

    id: str
    display_name: str
    availability: str
    locality: str
    provider_id: str
    #: The vendor the serving authority declared (an OpenAI-compatible listing's
    #: ``owned_by``), or ``None`` when it declared nothing.  Carried so a client
    #: shows the real provider rather than guessing one from the id's spelling.
    vendor: str | None = None
    capabilities: Mapping[str, bool] = field(default_factory=dict)
    reasoning_efforts: tuple[str, ...] = ()
    document_media_types: tuple[str, ...] = ()
    context_window: int | None = None
    streaming: bool = False
    #: The concrete version/family the serving authority declared, or ``None``
    #: when it declared none.  A rolling alias has no version to report and is
    #: never given an invented one, so a client can distinguish "this route is
    #: currently X" from "this route will be some Y".
    version: str | None = None
    #: Lifecycle state of this model.  ``availability`` stays the coarse
    #: usable/unusable answer a selector gates on; ``status`` says *why*, so a
    #: local model that is merely offline stays visible and honest instead of
    #: disappearing or being presented as working.
    status: str = "available"

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "capabilities", MappingProxyType(dict(self.capabilities))
        )
        object.__setattr__(self, "reasoning_efforts", tuple(self.reasoning_efforts))
        object.__setattr__(
            self, "document_media_types", tuple(self.document_media_types)
        )


@dataclass(frozen=True, slots=True)
class ClientResolvedModel:
    """One selection resolved against the canonical authorities.

    ``handle`` is opaque to the client: it is handed back to ``stream`` and
    never inspected.  ``supports_capability_plane`` states whether the model can
    complete the capability planner's strict-JSON handshake; ``supports_vision``
    whether it declares visual input.  Both come from the descriptor, never from
    a model name.
    """

    model_id: str
    display_name: str
    locality: str
    policy: str
    handle: Any = None
    supports_capability_plane: bool = True
    supports_vision: bool = False
    reasoning_efforts: tuple[str, ...] = ()
    document_media_types: tuple[str, ...] = ()
    capabilities: Mapping[str, bool] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "capabilities", MappingProxyType(dict(self.capabilities))
        )


@dataclass(frozen=True, slots=True)
class ClientStreamEvent:
    """One normalized event of a capability-plane run."""

    kind: str
    data: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "data", MappingProxyType(dict(self.data)))


@dataclass(frozen=True, slots=True)
class ClientStreamFacts:
    """What one stream imposed on the runtime.

    ``effective_reasoning_effort`` is ``None`` when the runtime cannot say what
    it applied — an honest unknown, never an echo of the request.
    """

    requested_reasoning_effort: str
    effective_reasoning_effort: str | None = None
