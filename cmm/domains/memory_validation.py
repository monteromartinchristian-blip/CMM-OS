"""Phase 10.18 — Domain Memory Integration Validator.

Pure, fail-closed integration validator for domain memory views and proposal bindings.
Receives external reference inventory explicitly.
Never queries memory stores, graphs, adapters or networks.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from cmm.domains.memory_contracts import (
    _DIGEST_PREFIX_LENGTH,
    DomainMemoryProposalBinding,
    DomainMemoryReferenceInventory,
    DomainMemorySelectionDecisionCode,
    DomainMemoryValidationCode,
    DomainMemoryValidationResult,
    DomainMemoryView,
    DomainMemoryViewRequest,
    _contains_private_marker,
)
from cmm.domains.memory_view import (
    DefaultDomainMemoryViewResolver,
)


@runtime_checkable
class DomainMemoryIntegrationValidator(Protocol):
    """Protocol for pure reference-only domain memory integration validators."""

    def validate_view(
        self,
        view: DomainMemoryView,
        request: DomainMemoryViewRequest,
        inventory: DomainMemoryReferenceInventory,
    ) -> DomainMemoryValidationResult:
        """Validate a DomainMemoryView against its request and reference inventory."""
        ...

    def validate_binding(
        self,
        binding: DomainMemoryProposalBinding,
        inventory: DomainMemoryReferenceInventory,
    ) -> DomainMemoryValidationResult:
        """Validate a DomainMemoryProposalBinding against canonical proposal inventory."""
        ...


class DefaultDomainMemoryIntegrationValidator:
    """Pure, fail-closed default implementation of DomainMemoryIntegrationValidator."""

    def validate_view(
        self,
        view: DomainMemoryView,
        request: DomainMemoryViewRequest,
        inventory: DomainMemoryReferenceInventory,
    ) -> DomainMemoryValidationResult:
        try:
            if not isinstance(view, DomainMemoryView) or not isinstance(
                request, DomainMemoryViewRequest
            ):
                return DomainMemoryValidationResult(
                    is_valid=False,
                    code=DomainMemoryValidationCode.INVALID_STRUCTURE,
                    codes=(DomainMemoryValidationCode.INVALID_STRUCTURE,),
                )

            if not isinstance(inventory, DomainMemoryReferenceInventory):
                return DomainMemoryValidationResult(
                    is_valid=False,
                    code=DomainMemoryValidationCode.INVALID_STRUCTURE,
                    codes=(DomainMemoryValidationCode.INVALID_STRUCTURE,),
                )

            if (
                str(view.request_id) != str(request.request_id)
                or str(view.primary_domain) != str(request.primary_domain)
                or view.trace_id != request.trace_id
                or view.temporal_reference != request.temporal_reference
                or view.request_digest != request.digest
            ):
                return DomainMemoryValidationResult(
                    is_valid=False,
                    code=DomainMemoryValidationCode.INVALID_TRACE_VIEW_MISMATCH,
                    codes=(DomainMemoryValidationCode.INVALID_TRACE_VIEW_MISMATCH,),
                )

            inventory_permission_ids = {
                decision.decision_id
                for decision in inventory.permission_decisions
            }
            unknown_permission_ids = tuple(
                sorted(
                    set(request.permission_decision_ids)
                    - inventory_permission_ids
                )
            )
            if unknown_permission_ids:
                return DomainMemoryValidationResult(
                    is_valid=False,
                    code=DomainMemoryValidationCode.INVALID_PERMISSION_DENIED,
                    codes=(
                        DomainMemoryValidationCode.INVALID_PERMISSION_DENIED,
                    ),
                    affected_object_ids=unknown_permission_ids,
                )

            # Content-bound view_id validation
            expected_prefix = f"view:{request.request_id}:"
            if not view.view_id.startswith(expected_prefix):
                return DomainMemoryValidationResult(
                    is_valid=False,
                    code=DomainMemoryValidationCode.INVALID_DIGEST_TAMPERED,
                    codes=(DomainMemoryValidationCode.INVALID_DIGEST_TAMPERED,),
                )

            view_suffix = view.view_id[len(expected_prefix):]
            if view_suffix != view.content_digest[:_DIGEST_PREFIX_LENGTH]:
                return DomainMemoryValidationResult(
                    is_valid=False,
                    code=DomainMemoryValidationCode.INVALID_DIGEST_TAMPERED,
                    codes=(DomainMemoryValidationCode.INVALID_DIGEST_TAMPERED,),
                )

            if request.trace_id:
                trace_map = {tr.trace_id: tr for tr in inventory.traces}
                if request.trace_id not in trace_map:
                    return DomainMemoryValidationResult(
                        is_valid=False,
                        code=DomainMemoryValidationCode.INVALID_TRACE_VIEW_MISMATCH,
                        codes=(DomainMemoryValidationCode.INVALID_TRACE_VIEW_MISMATCH,),
                    )
                trace_snap = trace_map[request.trace_id]
                if str(trace_snap.primary_domain) != str(request.primary_domain):
                    return DomainMemoryValidationResult(
                        is_valid=False,
                        code=DomainMemoryValidationCode.INVALID_TRACE_VIEW_MISMATCH,
                        codes=(DomainMemoryValidationCode.INVALID_TRACE_VIEW_MISMATCH,),
                    )

            # Re-evaluate policy via resolver to ensure strict 1-to-1 match
            expected_view = DefaultDomainMemoryViewResolver().resolve(request, inventory)

            if (
                view.view_id != expected_view.view_id
                or view.request_id != expected_view.request_id
                or str(view.primary_domain) != str(expected_view.primary_domain)
                or len(view.selection_decisions) != len(expected_view.selection_decisions)
                or len(view.selected_references) != len(expected_view.selected_references)
            ):
                return DomainMemoryValidationResult(
                    is_valid=False,
                    code=DomainMemoryValidationCode.INVALID_REFERENCE_INTEGRITY,
                    codes=(DomainMemoryValidationCode.INVALID_REFERENCE_INTEGRITY,),
                )

            # Verify selection_decisions exact match
            for v_dec, e_dec in zip(view.selection_decisions, expected_view.selection_decisions):
                if (
                    v_dec.reference_id != e_dec.reference_id
                    or v_dec.code != e_dec.code
                    or v_dec.related_reference_ids != e_dec.related_reference_ids
                    or v_dec.permission_decision_ids != e_dec.permission_decision_ids
                ):
                    code = DomainMemoryValidationCode.INVALID_REFERENCE_INTEGRITY
                    if e_dec.code == DomainMemorySelectionDecisionCode.EXCLUDED_PERMISSION_DENIED:
                        code = DomainMemoryValidationCode.INVALID_PERMISSION_DENIED
                    elif e_dec.code == DomainMemorySelectionDecisionCode.EXCLUDED_SENSITIVITY_RESTRICTED:
                        code = DomainMemoryValidationCode.INVALID_PRIVACY_BREACH
                    return DomainMemoryValidationResult(
                        is_valid=False,
                        code=code,
                        codes=(code,),
                        affected_reference_ids=(v_dec.reference_id,),
                    )

            # Verify full canonical projection matching against both request candidate and inventory reference
            req_cand_map = {c.reference_id: c for c in request.candidates}
            inventory_ref_map = {r.reference_id: r for r in inventory.references}

            for r in view.selected_references:
                if r.reference_id not in req_cand_map or r.reference_id not in inventory_ref_map:
                    return DomainMemoryValidationResult(
                        is_valid=False,
                        code=DomainMemoryValidationCode.INVALID_REFERENCE_INTEGRITY,
                        codes=(DomainMemoryValidationCode.INVALID_REFERENCE_INTEGRITY,),
                        affected_reference_ids=(r.reference_id,),
                    )

                req_c = req_cand_map[r.reference_id]
                inv_r = inventory_ref_map[r.reference_id]

                if r != req_c or r != inv_r or r.digest != req_c.digest or r.digest != inv_r.digest:
                    return DomainMemoryValidationResult(
                        is_valid=False,
                        code=DomainMemoryValidationCode.INVALID_REFERENCE_INTEGRITY,
                        codes=(DomainMemoryValidationCode.INVALID_REFERENCE_INTEGRITY,),
                        affected_reference_ids=(r.reference_id,),
                    )

                for k in r.metadata:
                    if _contains_private_marker(k):
                        return DomainMemoryValidationResult(
                            is_valid=False,
                            code=DomainMemoryValidationCode.INVALID_PRIVACY_BREACH,
                            codes=(DomainMemoryValidationCode.INVALID_PRIVACY_BREACH,),
                            affected_reference_ids=(r.reference_id,),
                        )

            return DomainMemoryValidationResult(
                is_valid=True,
                code=DomainMemoryValidationCode.VALID,
                codes=(DomainMemoryValidationCode.VALID,),
            )
        except Exception:  # noqa: BLE001
            return DomainMemoryValidationResult(
                is_valid=False,
                code=DomainMemoryValidationCode.INVALID_STRUCTURE,
                codes=(DomainMemoryValidationCode.INVALID_STRUCTURE,),
            )

    def validate_binding(
        self,
        binding: DomainMemoryProposalBinding,
        inventory: DomainMemoryReferenceInventory,
    ) -> DomainMemoryValidationResult:
        try:
            if not isinstance(binding, DomainMemoryProposalBinding) or not isinstance(
                inventory, DomainMemoryReferenceInventory
            ):
                return DomainMemoryValidationResult(
                    is_valid=False,
                    code=DomainMemoryValidationCode.INVALID_STRUCTURE,
                    codes=(DomainMemoryValidationCode.INVALID_STRUCTURE,),
                )

            # Content-bound binding_id validation
            expected_prefix = (
                f"binding:{binding.domain_id}:{binding.trace_id}:{binding.view_id}:"
            )
            if not binding.binding_id.startswith(expected_prefix):
                return DomainMemoryValidationResult(
                    is_valid=False,
                    code=DomainMemoryValidationCode.INVALID_DIGEST_TAMPERED,
                    codes=(DomainMemoryValidationCode.INVALID_DIGEST_TAMPERED,),
                )

            binding_suffix = binding.binding_id[len(expected_prefix):]
            if binding_suffix != binding.content_digest[:_DIGEST_PREFIX_LENGTH]:
                return DomainMemoryValidationResult(
                    is_valid=False,
                    code=DomainMemoryValidationCode.INVALID_DIGEST_TAMPERED,
                    codes=(DomainMemoryValidationCode.INVALID_DIGEST_TAMPERED,),
                )

            # 1. View verification against inventory.views
            view_map = {vw.view_id: vw for vw in inventory.views}
            if binding.view_id not in view_map:
                return DomainMemoryValidationResult(
                    is_valid=False,
                    code=DomainMemoryValidationCode.INVALID_TRACE_VIEW_MISMATCH,
                    codes=(DomainMemoryValidationCode.INVALID_TRACE_VIEW_MISMATCH,),
                )

            view_snap = view_map[binding.view_id]
            if binding.view_digest != view_snap.view_digest:
                return DomainMemoryValidationResult(
                    is_valid=False,
                    code=DomainMemoryValidationCode.INVALID_DIGEST_TAMPERED,
                    codes=(
                        DomainMemoryValidationCode.INVALID_DIGEST_TAMPERED,
                    ),
                )

            if str(view_snap.primary_domain) != str(binding.domain_id):
                return DomainMemoryValidationResult(
                    is_valid=False,
                    code=DomainMemoryValidationCode.INVALID_TRACE_VIEW_MISMATCH,
                    codes=(DomainMemoryValidationCode.INVALID_TRACE_VIEW_MISMATCH,),
                )

            # View trace_id must be non-null and equal to binding.trace_id
            if view_snap.trace_id is None or view_snap.trace_id != binding.trace_id:
                return DomainMemoryValidationResult(
                    is_valid=False,
                    code=DomainMemoryValidationCode.INVALID_TRACE_VIEW_MISMATCH,
                    codes=(DomainMemoryValidationCode.INVALID_TRACE_VIEW_MISMATCH,),
                )

            # 2. Trace verification against inventory.traces
            trace_map = {tr.trace_id: tr for tr in inventory.traces}
            if binding.trace_id not in trace_map:
                return DomainMemoryValidationResult(
                    is_valid=False,
                    code=DomainMemoryValidationCode.INVALID_TRACE_VIEW_MISMATCH,
                    codes=(DomainMemoryValidationCode.INVALID_TRACE_VIEW_MISMATCH,),
                )

            trace_snap = trace_map[binding.trace_id]
            if str(trace_snap.primary_domain) != str(binding.domain_id):
                return DomainMemoryValidationResult(
                    is_valid=False,
                    code=DomainMemoryValidationCode.INVALID_TRACE_VIEW_MISMATCH,
                    codes=(DomainMemoryValidationCode.INVALID_TRACE_VIEW_MISMATCH,),
                )

            # 3. Proposal verification & classification against inventory.proposals
            if (
                not binding.memory_proposal_ids
                and not binding.agent_knowledge_proposal_ids
            ):
                return DomainMemoryValidationResult(
                    is_valid=False,
                    code=DomainMemoryValidationCode.INVALID_PROPOSAL_COVERAGE,
                    codes=(DomainMemoryValidationCode.INVALID_PROPOSAL_COVERAGE,),
                )

            proposal_map = {p.proposal_id: p for p in inventory.proposals}

            # Check classification of memory proposals
            for pid in binding.memory_proposal_ids:
                if pid not in proposal_map:
                    return DomainMemoryValidationResult(
                        is_valid=False,
                        code=DomainMemoryValidationCode.INVALID_PROPOSAL_COVERAGE,
                        codes=(DomainMemoryValidationCode.INVALID_PROPOSAL_COVERAGE,),
                        affected_object_ids=(pid,),
                    )
                p_snap = proposal_map[pid]
                p_kind = (
                    p_snap.proposal_kind.value
                    if hasattr(p_snap.proposal_kind, "value")
                    else str(p_snap.proposal_kind)
                )
                if p_kind != "memory_update":
                    return DomainMemoryValidationResult(
                        is_valid=False,
                        code=DomainMemoryValidationCode.INVALID_PROPOSAL_KIND_MISMATCH,
                        codes=(
                            DomainMemoryValidationCode.INVALID_PROPOSAL_KIND_MISMATCH,
                        ),
                        affected_object_ids=(pid,),
                    )

            # Check classification of agent knowledge proposals
            for pid in binding.agent_knowledge_proposal_ids:
                if pid not in proposal_map:
                    return DomainMemoryValidationResult(
                        is_valid=False,
                        code=DomainMemoryValidationCode.INVALID_PROPOSAL_COVERAGE,
                        codes=(DomainMemoryValidationCode.INVALID_PROPOSAL_COVERAGE,),
                        affected_object_ids=(pid,),
                    )
                p_snap = proposal_map[pid]
                p_kind = (
                    p_snap.proposal_kind.value
                    if hasattr(p_snap.proposal_kind, "value")
                    else str(p_snap.proposal_kind)
                )
                if p_kind != "agent_knowledge_update":
                    return DomainMemoryValidationResult(
                        is_valid=False,
                        code=DomainMemoryValidationCode.INVALID_PROPOSAL_KIND_MISMATCH,
                        codes=(
                            DomainMemoryValidationCode.INVALID_PROPOSAL_KIND_MISMATCH,
                        ),
                        affected_object_ids=(pid,),
                    )

            bound_proposal_ids = tuple(binding.memory_proposal_ids) + tuple(
                binding.agent_knowledge_proposal_ids
            )
            bound_proposals = [proposal_map[pid] for pid in bound_proposal_ids]
            proposal_affected_ids: set[str] = set()
            for p_snap in bound_proposals:
                proposal_affected_ids.update(p_snap.affected_reference_ids)

            if set(binding.affected_reference_ids) != proposal_affected_ids:
                return DomainMemoryValidationResult(
                    is_valid=False,
                    code=DomainMemoryValidationCode.INVALID_PROPOSAL_COVERAGE,
                    codes=(DomainMemoryValidationCode.INVALID_PROPOSAL_COVERAGE,),
                )

            # 4. Scoped operation capability verification (Defecto 1)
            perm_map = {pd.decision_id: pd for pd in inventory.permission_decisions}

            unknown_permission_ids = tuple(
                sorted(
                    set(binding.permission_decision_ids)
                    - set(perm_map)
                )
            )
            if unknown_permission_ids:
                return DomainMemoryValidationResult(
                    is_valid=False,
                    code=DomainMemoryValidationCode.INVALID_PERMISSION_DENIED,
                    codes=(
                        DomainMemoryValidationCode.INVALID_PERMISSION_DENIED,
                    ),
                    affected_object_ids=unknown_permission_ids,
                )

            for p_snap in bound_proposals:
                # No fallback: required_capabilities must be explicit and non-empty
                req_caps_objs = set(p_snap.required_capabilities)
                if not req_caps_objs:
                    return DomainMemoryValidationResult(
                        is_valid=False,
                        code=DomainMemoryValidationCode.INVALID_PERMISSION_DENIED,
                        codes=(DomainMemoryValidationCode.INVALID_PERMISSION_DENIED,),
                        affected_object_ids=(p_snap.proposal_id,),
                    )

                req_caps_str = {
                    c.value if hasattr(c, "value") else str(c).upper()
                    for c in req_caps_objs
                }
                authorized = False
                unscoped_found = False

                for pid in binding.permission_decision_ids:
                    if pid in perm_map:
                        pd_snap = perm_map[pid]
                        if pd_snap.allowed is True:
                            pd_caps_str = {
                                c.value if hasattr(c, "value") else str(c).upper()
                                for c in pd_snap.capabilities
                            }
                            if req_caps_str.issubset(pd_caps_str):
                                tgt = (
                                    str(pd_snap.target_domain_id)
                                    if pd_snap.target_domain_id
                                    else None
                                )
                                if tgt is None:
                                    unscoped_found = True
                                elif tgt == str(binding.domain_id):
                                    authorized = True
                                    break

                if not authorized:
                    code = (
                        DomainMemoryValidationCode.INVALID_PERMISSION_UNSCOPED
                        if unscoped_found
                        else DomainMemoryValidationCode.INVALID_PERMISSION_DENIED
                    )
                    return DomainMemoryValidationResult(
                        is_valid=False,
                        code=code,
                        codes=(code,),
                        affected_object_ids=(p_snap.proposal_id,),
                    )

            # 5. 1-to-1 Approval request & decision verification
            bound_app_req_ids = set(binding.approval_request_ids)
            bound_app_dec_ids = set(binding.approval_decision_ids)

            used_app_req_ids: set[str] = set()
            used_app_dec_ids: set[str] = set()

            for p_snap in bound_proposals:
                if p_snap.requires_confirmation:
                    # Find approval request for this specific proposal
                    matching_reqs = [
                        ar
                        for ar in inventory.approval_requests
                        if ar.request_id in bound_app_req_ids
                        and ar.proposal_id == p_snap.proposal_id
                    ]
                    if not matching_reqs:
                        return DomainMemoryValidationResult(
                            is_valid=False,
                            code=DomainMemoryValidationCode.INVALID_APPROVAL_REQUIRED,
                            codes=(
                                DomainMemoryValidationCode.INVALID_APPROVAL_REQUIRED,
                            ),
                            affected_object_ids=(p_snap.proposal_id,),
                        )

                    req_chain_found = False
                    for ar in matching_reqs:
                        # Find approval decision for this request
                        matching_decs = [
                            ad
                            for ad in inventory.approval_decisions
                            if ad.decision_id in bound_app_dec_ids
                            and ad.request_id == ar.request_id
                            and ad.approved is True
                        ]
                        if matching_decs:
                            req_chain_found = True
                            used_app_req_ids.add(ar.request_id)
                            used_app_dec_ids.add(matching_decs[0].decision_id)
                            break

                    if not req_chain_found:
                        return DomainMemoryValidationResult(
                            is_valid=False,
                            code=DomainMemoryValidationCode.INVALID_APPROVAL_REQUIRED,
                            codes=(
                                DomainMemoryValidationCode.INVALID_APPROVAL_REQUIRED,
                            ),
                            affected_object_ids=(p_snap.proposal_id,),
                        )

            # Ensure no extra unlinked approval requests or decisions are bound
            if bound_app_req_ids != used_app_req_ids or bound_app_dec_ids != used_app_dec_ids:
                return DomainMemoryValidationResult(
                    is_valid=False,
                    code=DomainMemoryValidationCode.INVALID_APPROVAL_COVERAGE_MISMATCH,
                    codes=(
                        DomainMemoryValidationCode.INVALID_APPROVAL_COVERAGE_MISMATCH,
                    ),
                )

            return DomainMemoryValidationResult(
                is_valid=True,
                code=DomainMemoryValidationCode.VALID,
                codes=(DomainMemoryValidationCode.VALID,),
            )
        except Exception:  # noqa: BLE001
            return DomainMemoryValidationResult(
                is_valid=False,
                code=DomainMemoryValidationCode.INVALID_STRUCTURE,
                codes=(DomainMemoryValidationCode.INVALID_STRUCTURE,),
            )