"""Wave F — one normalized capability execution surface for CMMChat.

``CapabilityExecution`` composes the canonical model-execution seam with the
web and computer capabilities and yields normalized ``CapabilityEvent``s for
the product surface (Hub persists and bridges them; Swift renders them). It
owns no provider, backend, registry or approval authority of its own.
"""

from cmm.capabilities.events import EVENT_KINDS, CapabilityEvent, CapabilityRequest
from cmm.capabilities.execution import CapabilityExecution

__all__ = [
    "EVENT_KINDS",
    "CapabilityEvent",
    "CapabilityExecution",
    "CapabilityRequest",
]
