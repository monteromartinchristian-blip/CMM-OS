"""The stable CMMChat model-execution client boundary.

One import path for first-party clients::

    from cmm.model_client import (
        MODEL_CLIENT_INTERFACE_VERSION,
        ClientModelDescriptor,
        ClientResolvedModel,
        ClientStreamEvent,
        ClientStreamFacts,
        ModelClient,
        ModelClientError,
        normalize,
    )

Nothing below this package is part of the client contract: the canonical
composition, the provider registry and the kernel live behind the facade and
must not be imported by a client.
"""

from cmm.model_client.contracts import (
    MODEL_CLIENT_ERROR_CODES,
    MODEL_CLIENT_INTERFACE_VERSION,
    ClientModelDescriptor,
    ClientResolvedModel,
    ClientStreamEvent,
    ClientStreamFacts,
    ModelClientError,
)
from cmm.model_client.interface import (
    AUTO_MODEL,
    CAPABILITY_DEGRADED_EVENT,
    ModelClient,
    normalize,
)

__all__ = [
    "AUTO_MODEL",
    "CAPABILITY_DEGRADED_EVENT",
    "MODEL_CLIENT_ERROR_CODES",
    "MODEL_CLIENT_INTERFACE_VERSION",
    "ClientModelDescriptor",
    "ClientResolvedModel",
    "ClientStreamEvent",
    "ClientStreamFacts",
    "ModelClient",
    "ModelClientError",
    "normalize",
]
