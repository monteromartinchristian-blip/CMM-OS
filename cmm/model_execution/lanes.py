"""Model-lane identities and the honest egress class of each lane.

A *lane* is the composition seam a chat model reaches the world through: the
CMMChat Router subscription lane, or a local model runtime.  Both run as
loopback processes on this device, so where the *process* lives says nothing
about where the *context* goes — the router forwards to vendor subscription
clouds, and a runtime that tunnels to a hosted endpoint also leaves this
device.

This module is a leaf on purpose: :mod:`cmm.model_execution.composition`
imports :mod:`cmm.model_execution.executor`, so the executor cannot import the
composition module back.  Both need the lane identities and the egress answer,
so the answer lives here and the composition module re-exports it.
"""

from __future__ import annotations

import os

__all__ = [
    "CHAT_ONLY_ROUTER_PROVIDER_ID",
    "LOCAL_RUNTIME_EGRESS_ENV",
    "LOCAL_RUNTIME_PROVIDER_ID",
    "lane_egress_class",
    "lane_locality",
]

#: The one provider identity the CMMChat Router holds inside CMM OS.
CHAT_ONLY_ROUTER_PROVIDER_ID = "cmmchat-router"

#: The provider identity of a local model runtime lane.
LOCAL_RUNTIME_PROVIDER_ID = "local-runtime"

#: Honest egress class of the local-runtime lane: ``local`` only when the
#: launcher declares the runtime processes data on this device (a tunneled or
#: remote runtime must be declared ``remote``).
LOCAL_RUNTIME_EGRESS_ENV = "CMM_LOCAL_RUNTIME_EGRESS"


def lane_egress_class(provider_id: str) -> str:
    """Return ``local`` or ``remote``: does context leave this device?"""

    if provider_id == LOCAL_RUNTIME_PROVIDER_ID:
        declared = os.getenv(LOCAL_RUNTIME_EGRESS_ENV, "local").strip().lower()
        return "remote" if declared == "remote" else "local"
    return "remote"


def lane_locality(provider_id: str) -> str:
    """Return the catalog locality a lane's models honestly report.

    ``locality`` is the selector's answer to "does my context stay on this
    Mac?", which is the egress question, never where the serving process
    happens to run.  ``ProviderSpec.provider_type`` answers a different
    question (the privacy gates read it) and describes process placement, so a
    loopback lane that forwards to a vendor cloud is ``remote`` there and must
    still be ``cloud`` here.
    """

    return "local" if lane_egress_class(provider_id) == "local" else "cloud"
