"""Tests for Phase 10.18 Domain Memory proposal bindings and permission separation."""

import pytest

from cmm.domains.errors import (
    DomainMemoryContractError,
)
from cmm.domains.memory_contracts import (
    _DIGEST_PREFIX_LENGTH,
    DomainMemoryProposalBinding,
    _sha256_digest,
)

_VIEW_DIGEST1 = "abc123def456" + ("0" * 52)
_VID1 = (
    "view:req:1:"
    f"{_VIEW_DIGEST1[:_DIGEST_PREFIX_LENGTH]}"
)


def _make_binding_id(
    *,
    domain_id: str = "domain:health",
    trace_id: str = "trace:1",
    view_id: str = _VID1,
    view_digest: str = _VIEW_DIGEST1,
    memory_proposal_ids: tuple[str, ...] = (),
    agent_knowledge_proposal_ids: tuple[str, ...] = (),
    affected_reference_ids: tuple[str, ...] = (),
    permission_decision_ids: tuple[str, ...] = (),
    approval_request_ids: tuple[str, ...] = (),
    approval_decision_ids: tuple[str, ...] = (),
) -> str:
    content_digest = _sha256_digest(
        {
            "domain_id": domain_id,
            "trace_id": trace_id,
            "view_id": view_id,
            "view_digest": view_digest,
            "memory_proposal_ids": sorted(set(memory_proposal_ids)),
            "agent_knowledge_proposal_ids": sorted(
                set(agent_knowledge_proposal_ids)
            ),
            "affected_reference_ids": sorted(set(affected_reference_ids)),
            "permission_decision_ids": sorted(set(permission_decision_ids)),
            "approval_request_ids": sorted(set(approval_request_ids)),
            "approval_decision_ids": sorted(set(approval_decision_ids)),
        }
    )
    return (
        f"binding:{domain_id}:{trace_id}:{view_id}:"
        f"{content_digest[:_DIGEST_PREFIX_LENGTH]}"
    )



def test_proposal_binding_creation_and_immutability() -> None:
    binding_id = _make_binding_id(
        memory_proposal_ids=("prop:mem:1",),
        agent_knowledge_proposal_ids=("prop:agent:1",),
        affected_reference_ids=("ref:knowledge:1",),
        permission_decision_ids=("perm:propose:1",),
        approval_request_ids=("app_req:1",),
        approval_decision_ids=("app_dec:1",),
    )
    binding = DomainMemoryProposalBinding(
        binding_id=binding_id,
        domain_id="domain:health",
        trace_id="trace:1",
        view_id=_VID1,
        view_digest=_VIEW_DIGEST1,
        memory_proposal_ids=("prop:mem:1",),
        agent_knowledge_proposal_ids=("prop:agent:1",),
        affected_reference_ids=("ref:knowledge:1",),
        permission_decision_ids=("perm:propose:1",),
        approval_request_ids=("app_req:1",),
        approval_decision_ids=("app_dec:1",),
    )

    assert binding.binding_id == binding_id
    assert str(binding.domain_id) == "domain:health"
    assert binding.trace_id == "trace:1"
    assert binding.view_id == _VID1
    assert binding.memory_proposal_ids == ("prop:mem:1",)
    assert binding.agent_knowledge_proposal_ids == ("prop:agent:1",)
    assert binding.affected_reference_ids == ("ref:knowledge:1",)
    assert binding.permission_decision_ids == ("perm:propose:1",)
    assert binding.digest is not None

    with pytest.raises(AttributeError):
        binding.trace_id = "trace:2"  # type: ignore[misc]



def test_proposal_binding_requires_at_least_one_proposal() -> None:
    binding_id = _make_binding_id()

    with pytest.raises(DomainMemoryContractError):
        DomainMemoryProposalBinding(
            binding_id=binding_id,
            domain_id="domain:health",
            trace_id="trace:1",
            view_id=_VID1,
        view_digest=_VIEW_DIGEST1,
            memory_proposal_ids=(),
            agent_knowledge_proposal_ids=(),
        )



def test_proposal_binding_serialization_roundtrip() -> None:
    binding_id = _make_binding_id(
        memory_proposal_ids=("prop:mem:1",),
        affected_reference_ids=("ref:1", "ref:2"),
    )
    binding = DomainMemoryProposalBinding(
        binding_id=binding_id,
        domain_id="domain:health",
        trace_id="trace:1",
        view_id=_VID1,
        view_digest=_VIEW_DIGEST1,
        memory_proposal_ids=("prop:mem:1",),
        affected_reference_ids=("ref:1", "ref:2"),
    )
    serialized = binding.to_dict()
    deserialized = DomainMemoryProposalBinding.from_dict(serialized)

    assert deserialized == binding
    assert deserialized.digest == binding.digest



def test_proposal_binding_order_independence() -> None:
    binding_id_1 = _make_binding_id(
        memory_proposal_ids=("prop:mem:1", "prop:mem:2"),
        affected_reference_ids=("ref:2", "ref:1"),
    )
    binding_id_2 = _make_binding_id(
        memory_proposal_ids=("prop:mem:2", "prop:mem:1"),
        affected_reference_ids=("ref:1", "ref:2"),
    )

    b1 = DomainMemoryProposalBinding(
        binding_id=binding_id_1,
        domain_id="domain:health",
        trace_id="trace:1",
        view_id=_VID1,
        view_digest=_VIEW_DIGEST1,
        memory_proposal_ids=("prop:mem:1", "prop:mem:2"),
        affected_reference_ids=("ref:2", "ref:1"),
    )
    b2 = DomainMemoryProposalBinding(
        binding_id=binding_id_2,
        domain_id="domain:health",
        trace_id="trace:1",
        view_id=_VID1,
        view_digest=_VIEW_DIGEST1,
        memory_proposal_ids=("prop:mem:2", "prop:mem:1"),
        affected_reference_ids=("ref:1", "ref:2"),
    )

    assert binding_id_1 == binding_id_2
    assert b1.digest == b2.digest
    assert b1.to_dict() == b2.to_dict()


def test_binding_id_suffix_must_match_content_digest() -> None:
    view_digest = "abc123def456" + ("0" * 52)
    view_id = (
        "view:req:1:"
        f"{view_digest[:_DIGEST_PREFIX_LENGTH]}"
    )

    with pytest.raises(
        DomainMemoryContractError,
        match="binding_id suffix must match content_digest prefix",
    ):
        DomainMemoryProposalBinding(
            binding_id=(
                "binding:domain:health:trace:1:"
                f"{view_id}:deadbeefdead"
            ),
            domain_id="domain:health",
            trace_id="trace:1",
            view_id=view_id,
            view_digest=view_digest,
            memory_proposal_ids=("prop:mem:1",),
        )


def test_proposal_binding_requires_full_view_digest() -> None:
    binding_id = _make_binding_id(
        memory_proposal_ids=("prop:mem:view-digest",),
    )

    with pytest.raises(
        DomainMemoryContractError,
        match="view_digest must be a full SHA-256 hex digest",
    ):
        DomainMemoryProposalBinding(
            binding_id=binding_id,
            domain_id="domain:health",
            trace_id="trace:1",
            view_id=_VID1,
            memory_proposal_ids=("prop:mem:view-digest",),
        )
