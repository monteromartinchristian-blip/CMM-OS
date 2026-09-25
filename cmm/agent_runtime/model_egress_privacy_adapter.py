"""Canonical privacy egress gate for the Model Gateway (Phase 11.21).

The Model Gateway lives in ``kernel.llm`` and must not depend on the cognitive
layer, so it consumes privacy through an injected narrow gate.  This module is
that gate's canonical implementation: it owns **no** privacy policy of its own
and delegates every decision to the canonical cognitive evaluator
(:func:`cmm.cognitive.privacy.evaluate_privacy_operation`), projecting the
result into the gateway's safe decision contract.

Two properties are structural, not conventional:

* ``LOCAL_ONLY`` can never authorize remote transmission — the canonical
  evaluator checks policy before approval, so no caller can widen the refusal;
* Phase 11.21 has no approval authority at all.  A policy that requires approval
  therefore yields ``approval_required`` and stays denied, because approval
  belongs to the canonical approval seam, not to the model gateway.
"""

from __future__ import annotations

from typing import Any

from cmm.cognitive.privacy import (
    PrivacyMetadata,
    PrivacyOperation,
    PrivacyOperationContext,
    ProcessingLocation,
    evaluate_privacy_operation,
)
from kernel.llm.model_gateway_contracts import PrivacyEgressDecision

__all__ = ["PRIVACY_ADAPTER_VERSION", "CanonicalPrivacyEgressGate"]

#: Boundary version of this adapter; it never replaces a canonical version.
PRIVACY_ADAPTER_VERSION = "1.0.0"


class CanonicalPrivacyEgressGate:
    """Delegate model-call egress decisions to the canonical privacy evaluator."""

    __slots__ = ("_is_premium",)

    def __init__(self, *, is_premium: bool = False) -> None:
        self._is_premium = bool(is_premium)

    def evaluate_egress(
        self,
        *,
        privacy: object | None,
        provider_id: str,
        is_remote: bool,
        is_premium: bool = False,
    ) -> PrivacyEgressDecision:
        """Return the canonical decision for one model-call egress attempt."""

        normalized_provider = str(provider_id).strip().lower()
        details: dict[str, Any] = {"provider_id": normalized_provider}

        if privacy is None:
            if is_remote:
                return PrivacyEgressDecision(
                    allowed=False,
                    reason_code="privacy_metadata_required",
                    details=details,
                )
            return PrivacyEgressDecision(
                allowed=True,
                reason_code="not_required",
                details=details,
            )

        operation = (
            PrivacyOperation.TRANSMIT_TO_PROVIDER
            if is_remote
            else PrivacyOperation.PROCESS_LOCAL
        )
        context = PrivacyOperationContext(
            provider_id=normalized_provider,
            processing_location=(
                ProcessingLocation.REMOTE if is_remote else ProcessingLocation.LOCAL
            ),
            is_premium=self._is_premium or bool(is_premium),
            approval_granted=False,
            redaction_applied=False,
        )
        decision = evaluate_privacy_operation(privacy, operation, context)

        details["canonical_status"] = decision.status.value
        details["canonical_reason_code"] = decision.reason_code
        details["excluded"] = bool(decision.excluded)
        return PrivacyEgressDecision(
            allowed=bool(decision.allowed),
            reason_code=decision.reason_code,
            requires_approval=bool(decision.requires_approval),
            requires_redaction=bool(decision.requires_redaction),
            details=details,
        )


def is_canonical_privacy_metadata(value: object) -> bool:
    """Return whether ``value`` is canonical privacy metadata."""

    return isinstance(value, PrivacyMetadata)
