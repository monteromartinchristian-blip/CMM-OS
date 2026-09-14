"""Phase 10.30 — Project Domain Memory Integration Tests."""

from __future__ import annotations

from cmm.domains.memory_contracts import (
    DomainMemoryProposalBinding,
    DomainMemoryProposalSnapshot,
    DomainMemoryViewRequest,
)
from cmm.domains.project.memory import (
    CANDIDATE_PROJECT_LONGITUDINAL_KINDS,
    build_project_memory_binding,
    build_project_memory_proposal,
    build_project_memory_view_request,
    validate_project_memory_proposal_content,
)


def test_memory_proposal_always_requires_confirmation() -> None:
    assert len(CANDIDATE_PROJECT_LONGITUDINAL_KINDS) > 0
    assert "decision_record" in CANDIDATE_PROJECT_LONGITUDINAL_KINDS
    proposal = build_project_memory_proposal(
        proposal_id="prop:1",
        affected_reference_ids=("ref:project:1",),
    )
    assert isinstance(proposal, DomainMemoryProposalSnapshot)
    assert proposal.requires_confirmation is True


def test_validate_project_memory_proposal_content_strict_confirmation() -> None:
    # Confirmed decision proposal is valid
    valid_content = {
        "kind": "decision",
        "status": "decision",
        "is_confirmed": True,
        "summary": "Adopt microkernel design",
    }
    res_valid = validate_project_memory_proposal_content(valid_content)
    assert res_valid["is_valid"] is True

    # Unconfirmed decision promotion is rejected
    unconf_content = {
        "kind": "decision",
        "status": "decision",
        "is_confirmed": False,
        "summary": "Adopt microkernel design",
    }
    res_unconf = validate_project_memory_proposal_content(unconf_content)
    assert res_unconf["is_valid"] is False
    assert res_unconf["reason"] == "prohibited_unconfirmed_decision_promotion"

    # Non-bool confirmation type rejected fail-closed
    truthy_content = {
        "kind": "decision",
        "status": "decision",
        "is_confirmed": "yes",
    }
    res_truthy = validate_project_memory_proposal_content(truthy_content)
    assert res_truthy["is_valid"] is False
    assert res_truthy["reason"] == "invalid_confirmation_evidence_type"


def test_validate_project_memory_proposal_content_rejects_code_dump() -> None:
    code_leak = {
        "kind": "architecture_note",
        "raw_source_code": "def secret_algorithm(): pass",
    }
    res_leak = validate_project_memory_proposal_content(code_leak)
    assert res_leak["is_valid"] is False
    assert res_leak["reason"] == "prohibited_raw_code_dump"


def test_project_memory_view_request_and_binding() -> None:
    req = build_project_memory_view_request(request_id="req:1")
    assert isinstance(req, DomainMemoryViewRequest)
    assert req.primary_domain == "domain:project"

    proposal = build_project_memory_proposal(
        proposal_id="prop:1",
        affected_reference_ids=("ref:1",),
    )

    from dataclasses import dataclass

    @dataclass
    class _FakeView:
        view_id: str = f"view:project:1:{'0' * 12}"
        primary_domain: str = "domain:project"
        content_digest: str = "0" * 64

    binding = build_project_memory_binding(
        proposal=proposal,
        view=_FakeView(),  # type: ignore[arg-type]
        trace_id="trace:1",
    )
    assert isinstance(binding, DomainMemoryProposalBinding)
    assert binding.domain_id == "domain:project"
    assert binding.trace_id == "trace:1"
    assert binding.view_id == f"view:project:1:{'0' * 12}"
    assert binding.memory_proposal_ids == ("prop:1",)
