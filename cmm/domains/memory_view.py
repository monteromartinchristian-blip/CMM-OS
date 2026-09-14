"""Phase 10.18 — Domain Memory View Resolver.

Pure, deterministic memory view resolution protocols and default implementation.
Receives all candidate references explicitly via DomainMemoryViewRequest.
Receives authoritative reference inventory explicitly via DomainMemoryReferenceInventory.
Never queries memory stores, graphs, adapters or networks.
"""

from __future__ import annotations

from datetime import datetime
from typing import Protocol, runtime_checkable

from cmm.domains.errors import DomainMemoryResolutionError
from cmm.domains.memory_contracts import (
    DIGEST_PREFIX_LENGTH,
    DomainMemoryPermissionDecisionSnapshot,
    DomainMemoryReference,
    DomainMemoryReferenceInventory,
    DomainMemoryReferenceKind,
    DomainMemorySelectionDecision,
    DomainMemorySelectionDecisionCode,
    DomainMemoryTemporalKind,
    DomainMemoryTemporalSnapshot,
    DomainMemoryView,
    DomainMemoryViewRequest,
    sha256_digest,
)


@runtime_checkable
class DomainMemoryViewResolver(Protocol):
    """Protocol for pure reference-only domain memory view resolvers."""

    def resolve(
        self,
        request: DomainMemoryViewRequest,
        inventory: DomainMemoryReferenceInventory,
    ) -> DomainMemoryView:
        """Resolve a candidate memory view request into a reference-only DomainMemoryView."""
        ...


def _evaluate_temporal(
    temporal: DomainMemoryTemporalSnapshot | None,
    reference_time: str | None,
) -> DomainMemorySelectionDecisionCode | None:
    """Evaluate temporal snapshot fail-closed.

    Returns None if valid/selected, or the specific exclusion code if excluded.
    """
    if temporal is None:
        return None

    if temporal.invalidated:
        return DomainMemorySelectionDecisionCode.EXCLUDED_INVALIDATED

    if temporal.expires_at is not None:
        if reference_time is None:
            return DomainMemorySelectionDecisionCode.EXCLUDED_TEMPORAL_INVALID
        ref_dt = datetime.fromisoformat(reference_time.replace("Z", "+00:00"))
        exp_dt = datetime.fromisoformat(temporal.expires_at.replace("Z", "+00:00"))
        if ref_dt > exp_dt:
            return DomainMemorySelectionDecisionCode.EXCLUDED_TEMPORAL_EXPIRED

    if temporal.kind == DomainMemoryTemporalKind.TIMELESS:
        return None

    if temporal.kind == DomainMemoryTemporalKind.UNKNOWN:
        return DomainMemorySelectionDecisionCode.EXCLUDED_TEMPORAL_UNKNOWN

    if temporal.kind == DomainMemoryTemporalKind.SAFETY:
        return DomainMemorySelectionDecisionCode.EXCLUDED_TEMPORAL_INVALID

    if temporal.kind == DomainMemoryTemporalKind.INTERVAL:
        if reference_time is None:
            return DomainMemorySelectionDecisionCode.EXCLUDED_TEMPORAL_INVALID
        if temporal.valid_from is None or temporal.valid_to is None:
            return DomainMemorySelectionDecisionCode.EXCLUDED_TEMPORAL_INVALID
        from_dt = datetime.fromisoformat(temporal.valid_from.replace("Z", "+00:00"))
        to_dt = datetime.fromisoformat(temporal.valid_to.replace("Z", "+00:00"))
        ref_dt = datetime.fromisoformat(reference_time.replace("Z", "+00:00"))
        if from_dt > to_dt or not (from_dt <= ref_dt <= to_dt):
            return DomainMemorySelectionDecisionCode.EXCLUDED_TEMPORAL_INVALID
        return None

    if temporal.kind == DomainMemoryTemporalKind.POINT_IN_TIME:
        if reference_time is None:
            return DomainMemorySelectionDecisionCode.EXCLUDED_TEMPORAL_INVALID
        if temporal.observed_at is None:
            return DomainMemorySelectionDecisionCode.EXCLUDED_TEMPORAL_INVALID
        obs_dt = datetime.fromisoformat(temporal.observed_at.replace("Z", "+00:00"))
        ref_dt = datetime.fromisoformat(reference_time.replace("Z", "+00:00"))
        if obs_dt != ref_dt:
            return DomainMemorySelectionDecisionCode.EXCLUDED_TEMPORAL_INVALID
        return None

    return DomainMemorySelectionDecisionCode.EXCLUDED_TEMPORAL_INVALID


def _evaluate_candidate(
    request: DomainMemoryViewRequest,
    cand: DomainMemoryReference,
    inventory: DomainMemoryReferenceInventory,
) -> DomainMemorySelectionDecision:
    """Pure, deterministic evaluation of a single candidate reference against request and inventory policy."""
    ref_id = cand.reference_id
    primary_str = str(request.primary_domain)
    supporting_strs = {str(d) for d in request.supporting_domains}

    # 0. Check inventory backing
    inv_ref_map: dict[str, DomainMemoryReference] = {
        ref.reference_id: ref for ref in inventory.references
    }
    if ref_id not in inv_ref_map:
        return DomainMemorySelectionDecision(
            reference_id=ref_id,
            code=DomainMemorySelectionDecisionCode.EXCLUDED_MISSING_REFERENCE,
        )

    inv_ref = inv_ref_map[ref_id]
    if cand != inv_ref or cand.digest != inv_ref.digest:
        return DomainMemorySelectionDecision(
            reference_id=ref_id,
            code=DomainMemorySelectionDecisionCode.EXCLUDED_REFERENCE_MISMATCH,
        )

    # 1. Kind check
    if request.requested_kinds and cand.kind not in request.requested_kinds:
        return DomainMemorySelectionDecision(
            reference_id=ref_id,
            code=DomainMemorySelectionDecisionCode.EXCLUDED_UNSUPPORTED_KIND,
        )

    # 2. Domain applicability check
    cand_domain = str(cand.domain_id)
    cand_app = {str(d) for d in cand.applicable_domains} | {cand_domain}
    is_primary = primary_str in cand_app
    is_supporting = bool(supporting_strs & cand_app)

    if not is_primary and not is_supporting:
        return DomainMemorySelectionDecision(
            reference_id=ref_id,
            code=DomainMemorySelectionDecisionCode.EXCLUDED_DOMAIN_INAPPLICABLE,
        )

    # 3. Read permission check
    inv_decisions_map: dict[str, DomainMemoryPermissionDecisionSnapshot] = {
        dec.decision_id: dec for dec in inventory.permission_decisions
    }

    if any(pid not in inv_decisions_map for pid in request.permission_decision_ids):
        return DomainMemorySelectionDecision(
            reference_id=ref_id,
            code=DomainMemorySelectionDecisionCode.EXCLUDED_PERMISSION_DENIED,
        )

    scoped_read_decisions: list[DomainMemoryPermissionDecisionSnapshot] = []
    for pid in request.permission_decision_ids:
        if pid in inv_decisions_map:
            dec = inv_decisions_map[pid]
            if dec.allowed is not True:
                continue
            caps_str = {
                c.value if hasattr(c, "value") else str(c).upper()
                for c in dec.capabilities
            }
            if "READ" not in caps_str:
                continue

            tgt = str(dec.target_domain_id) if dec.target_domain_id else None
            src = str(dec.source_domain_id) if dec.source_domain_id else None

            if tgt is None or tgt != primary_str:
                continue

            if cand_domain == primary_str:
                if src is None or src == primary_str:
                    scoped_read_decisions.append(dec)
            else:
                if src is not None and src == cand_domain:
                    scoped_read_decisions.append(dec)

    if not scoped_read_decisions:
        return DomainMemorySelectionDecision(
            reference_id=ref_id,
            code=DomainMemorySelectionDecisionCode.EXCLUDED_PERMISSION_DENIED,
        )

    # 4. Sensitivity level check
    cand_sens = cand.sensitivity_level.upper() if cand.sensitivity_level else "NORMAL"
    if cand_sens in ("RESTRICTED", "SECRET", "HIGH"):
        sensitivity_authorized = False
        for dec in scoped_read_decisions:
            dec_sens = {
                s.value if hasattr(s, "value") else str(s).upper()
                for s in dec.sensitivity_levels
            }
            if cand_sens in dec_sens:
                sensitivity_authorized = True
                break

        if not sensitivity_authorized:
            return DomainMemorySelectionDecision(
                reference_id=ref_id,
                code=DomainMemorySelectionDecisionCode.EXCLUDED_SENSITIVITY_RESTRICTED,
            )

    # 5. Temporal check
    if cand.temporal is not None:
        temporal_code = _evaluate_temporal(cand.temporal, request.temporal_reference)
        if temporal_code is not None:
            return DomainMemorySelectionDecision(
                reference_id=ref_id,
                code=temporal_code,
            )

    # 6. Provenance & evidence check for Knowledge Items
    if cand.kind == DomainMemoryReferenceKind.KNOWLEDGE_ITEM:
        if not cand.evidence_ids:
            return DomainMemorySelectionDecision(
                reference_id=ref_id,
                code=DomainMemorySelectionDecisionCode.EXCLUDED_EVIDENCE_MISSING,
            )
        if not cand.resource_ids:
            return DomainMemorySelectionDecision(
                reference_id=ref_id,
                code=DomainMemorySelectionDecisionCode.EXCLUDED_PROVENANCE_MISSING,
            )

    # 7. Supersession check
    if cand.superseded_by_id:
        return DomainMemorySelectionDecision(
            reference_id=ref_id,
            code=DomainMemorySelectionDecisionCode.EXCLUDED_SUPERSEDED,
            related_reference_ids=(cand.superseded_by_id,),
        )

    # 8. Unresolved conflict check
    if cand.has_unresolved_conflict:
        return DomainMemorySelectionDecision(
            reference_id=ref_id,
            code=DomainMemorySelectionDecisionCode.EXCLUDED_PRESERVED_CONFLICT,
        )

    # 9. Unknown ordering check
    if cand.has_unknown_ordering:
        return DomainMemorySelectionDecision(
            reference_id=ref_id,
            code=DomainMemorySelectionDecisionCode.EXCLUDED_ORDERING_UNKNOWN,
        )

    # Candidate selected!
    perm_ids_used = tuple(sorted({dec.decision_id for dec in scoped_read_decisions}))
    return DomainMemorySelectionDecision(
        reference_id=ref_id,
        code=DomainMemorySelectionDecisionCode.SELECTED,
        permission_decision_ids=perm_ids_used,
    )


class DefaultDomainMemoryViewResolver:
    """Pure, deterministic default implementation of DomainMemoryViewResolver."""

    def resolve(
        self,
        request: DomainMemoryViewRequest,
        inventory: DomainMemoryReferenceInventory,
    ) -> DomainMemoryView:
        if not isinstance(request, DomainMemoryViewRequest):
            raise DomainMemoryResolutionError(
                "request must be a DomainMemoryViewRequest"
            )
        if not isinstance(inventory, DomainMemoryReferenceInventory):
            raise DomainMemoryResolutionError(
                "inventory must be a DomainMemoryReferenceInventory"
            )

        decisions: list[DomainMemorySelectionDecision] = []
        selected: list[DomainMemoryReference] = []

        for cand in request.candidates:
            decision = _evaluate_candidate(request, cand, inventory)
            decisions.append(decision)
            if decision.code == DomainMemorySelectionDecisionCode.SELECTED:
                selected.append(cand)

        # Content-bound view_id: view:<request_id>:<digest_prefix>
        content_payload = {
            "request_id": request.request_id,
            "primary_domain": str(request.primary_domain),
            "request_digest": request.digest,
            "selection_decisions": [d.to_dict() for d in decisions],
            "selected_references": [r.to_dict() for r in selected],
        }
        if request.trace_id is not None:
            content_payload["trace_id"] = request.trace_id
        if request.temporal_reference is not None:
            content_payload["temporal_reference"] = request.temporal_reference
        content_digest = sha256_digest(content_payload)
        view_id = f"view:{request.request_id}:{content_digest[:DIGEST_PREFIX_LENGTH]}"

        return DomainMemoryView(
            view_id=view_id,
            request_id=request.request_id,
            primary_domain=request.primary_domain,
            request_digest=request.digest,
            trace_id=request.trace_id,
            temporal_reference=request.temporal_reference,
            selection_decisions=tuple(decisions),
            selected_references=tuple(selected),
        )
