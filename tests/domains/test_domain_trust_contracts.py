"""Phase 10.38 — Domain Trust contracts tests (RED target for Task 1).

Proves the immutable/JSON-safe/serialization semantics of:

- ``DomainTrustLevel`` (exactly six approved values, no numeric authority)
- ``DomainTrustPolicy`` (immutable, restrictive defaults, strict validation)
- ``DomainTrustDecision`` (evidence only, never an authorization token)
"""

from __future__ import annotations

from types import MappingProxyType

import pytest

from cmm.agent_runtime.domain_permission_contracts import PermissionCapability
from cmm.domains.enums import DomainTrustLevel
from cmm.domains.errors import (
    DomainContractValidationError,
    DomainSerializationError,
)
from cmm.domains.trust_contracts import DomainTrustDecision, DomainTrustPolicy


class TestDomainTrustLevel:
    def test_exactly_six_approved_values(self) -> None:
        assert tuple(item.value for item in DomainTrustLevel) == (
            "trusted",
            "verified",
            "internal",
            "community",
            "untrusted",
            "blocked",
        )

    def test_levels_are_string_enums(self) -> None:
        assert DomainTrustLevel.TRUSTED.value == "trusted"
        assert DomainTrustLevel.VERIFIED.value == "verified"
        assert DomainTrustLevel.INTERNAL.value == "internal"
        assert DomainTrustLevel.COMMUNITY.value == "community"
        assert DomainTrustLevel.UNTRUSTED.value == "untrusted"
        assert DomainTrustLevel.BLOCKED.value == "blocked"

    def test_no_numeric_authority_surface(self) -> None:
        # Members must not be numerically ordered in a way that grants
        # progressively broader authority: the enum has no numeric value.
        for item in DomainTrustLevel:
            assert not isinstance(item.value, int)


class TestDomainTrustPolicy:
    def test_defaults_are_restrictive(self) -> None:
        policy = DomainTrustPolicy(
            domain_id="domain:external-example",
            trust_level=DomainTrustLevel.COMMUNITY,
            authorized_source_ids=("source:community",),
        )
        assert policy.domain_id == "domain:external-example"
        assert policy.trust_level is DomainTrustLevel.COMMUNITY
        assert policy.authorized_source_ids == ("source:community",)
        assert policy.allow_code_execution is False
        assert policy.allow_external_access is False
        assert policy.allow_memory_write is False
        assert policy.allow_sensitive_resources is False
        assert policy.allow_destructive_operations is False
        assert policy.require_manual_enable is True
        assert policy.require_signature is False
        assert policy.metadata == MappingProxyType({})

    def test_all_fields_settable(self) -> None:
        policy = DomainTrustPolicy(
            domain_id="domain:example",
            trust_level=DomainTrustLevel.TRUSTED,
            authorized_source_ids=("a", "b"),
            allow_code_execution=True,
            allow_external_access=True,
            allow_memory_write=True,
            allow_sensitive_resources=True,
            allow_destructive_operations=True,
            require_manual_enable=False,
            require_signature=True,
            metadata={"owner": "platform"},
        )
        assert policy.allow_code_execution is True
        assert policy.allow_external_access is True
        assert policy.allow_memory_write is True
        assert policy.allow_sensitive_resources is True
        assert policy.allow_destructive_operations is True
        assert policy.require_manual_enable is False
        assert policy.require_signature is True
        assert dict(policy.metadata) == {"owner": "platform"}

    def test_blocked_is_a_valid_declaration(self) -> None:
        policy = DomainTrustPolicy(
            domain_id="domain:blocked-example",
            trust_level=DomainTrustLevel.BLOCKED,
        )
        assert policy.trust_level is DomainTrustLevel.BLOCKED

    def test_bool_fields_reject_non_bool(self) -> None:
        for kwargs in (
            {"allow_code_execution": 1},
            {"allow_external_access": "true"},
            {"allow_memory_write": 0},
            {"allow_sensitive_resources": "yes"},
            {"allow_destructive_operations": 1},
            {"require_manual_enable": "no"},
            {"require_signature": 1},
        ):
            with pytest.raises(DomainContractValidationError):
                DomainTrustPolicy(
                    domain_id="domain:example",
                    trust_level=DomainTrustLevel.UNTRUSTED,
                    **kwargs,  # type: ignore[arg-type]
                )

    def test_blank_domain_id_rejected(self) -> None:
        with pytest.raises(DomainContractValidationError):
            DomainTrustPolicy(domain_id="  ", trust_level=DomainTrustLevel.UNTRUSTED)

    def test_blank_source_id_rejected(self) -> None:
        with pytest.raises(DomainContractValidationError):
            DomainTrustPolicy(
                domain_id="domain:example",
                trust_level=DomainTrustLevel.UNTRUSTED,
                authorized_source_ids=("valid", "  "),
            )

    def test_string_source_ids_rejected(self) -> None:
        with pytest.raises(DomainContractValidationError):
            DomainTrustPolicy(
                domain_id="domain:example",
                trust_level=DomainTrustLevel.UNTRUSTED,
                authorized_source_ids="source:single",  # type: ignore[arg-type]
            )

    def test_unknown_trust_level_rejected(self) -> None:
        with pytest.raises(DomainContractValidationError):
            DomainTrustPolicy(
                domain_id="domain:example",
                trust_level="super-trusted",  # type: ignore[arg-type]
            )

    def test_authorized_source_ids_uniqueness(self) -> None:
        with pytest.raises(DomainContractValidationError):
            DomainTrustPolicy(
                domain_id="domain:example",
                trust_level=DomainTrustLevel.UNTRUSTED,
                authorized_source_ids=("dup", "dup"),
            )

    def test_caller_metadata_mutation_cannot_mutate_contract(self) -> None:
        meta = {"owner": "platform"}
        policy = DomainTrustPolicy(
            domain_id="domain:example",
            trust_level=DomainTrustLevel.COMMUNITY,
            metadata=meta,
        )
        meta["owner"] = "attacker"
        assert dict(policy.metadata) == {"owner": "platform"}

    def test_nested_metadata_frozen(self) -> None:
        nested = {"owner": {"name": "platform"}}
        policy = DomainTrustPolicy(
            domain_id="domain:example",
            trust_level=DomainTrustLevel.COMMUNITY,
            metadata=nested,
        )
        assert isinstance(policy.metadata, MappingProxyType)
        with pytest.raises(TypeError):
            policy.metadata["owner"]["name"] = "attacker"  # type: ignore[index]

    def test_non_json_metadata_rejected(self) -> None:
        with pytest.raises(DomainContractValidationError):
            DomainTrustPolicy(
                domain_id="domain:example",
                trust_level=DomainTrustLevel.COMMUNITY,
                metadata={"when": __import__("datetime").datetime.now()},
            )

    def test_sensitive_metadata_key_rejected(self) -> None:
        with pytest.raises(DomainContractValidationError):
            DomainTrustPolicy(
                domain_id="domain:example",
                trust_level=DomainTrustLevel.COMMUNITY,
                metadata={"api_key": "super-secret"},
            )

    def test_frozen(self) -> None:
        policy = DomainTrustPolicy(
            domain_id="domain:example", trust_level=DomainTrustLevel.UNTRUSTED
        )
        with pytest.raises(Exception):  # noqa: B017
            policy.allow_code_execution = True  # type: ignore[misc]

    def test_to_dict_round_trip(self) -> None:
        policy = DomainTrustPolicy(
            domain_id="domain:external-example",
            trust_level=DomainTrustLevel.COMMUNITY,
            authorized_source_ids=("source:community", "source:other"),
            allow_code_execution=True,
            metadata={"owner": "platform", "review": ["a", "b"]},
        )
        restored = DomainTrustPolicy.from_dict(policy.to_dict())
        assert restored == policy

    def test_to_dict_is_json_safe(self) -> None:
        policy = DomainTrustPolicy(
            domain_id="domain:example",
            trust_level=DomainTrustLevel.TRUSTED,
            metadata={"owner": "platform"},
        )
        data = policy.to_dict()
        assert isinstance(data["domain_id"], str)
        assert isinstance(data["trust_level"], str)
        assert isinstance(data["authorized_source_ids"], list)
        assert isinstance(data["allow_code_execution"], bool)
        assert isinstance(data["metadata"], dict)

    def test_from_dict_rejects_unknown_fields(self) -> None:
        data = DomainTrustPolicy(
            domain_id="domain:example", trust_level=DomainTrustLevel.UNTRUSTED
        ).to_dict()
        data["totally_unknown"] = True
        with pytest.raises(DomainSerializationError):
            DomainTrustPolicy.from_dict(data)

    def test_from_dict_rejects_invalid_trust_level(self) -> None:
        data = DomainTrustPolicy(
            domain_id="domain:example", trust_level=DomainTrustLevel.UNTRUSTED
        ).to_dict()
        data["trust_level"] = "super-trusted"
        with pytest.raises(DomainSerializationError):
            DomainTrustPolicy.from_dict(data)

    def test_from_dict_strict_booleans(self) -> None:
        data = DomainTrustPolicy(
            domain_id="domain:example", trust_level=DomainTrustLevel.UNTRUSTED
        ).to_dict()
        data["allow_code_execution"] = 1
        with pytest.raises(DomainSerializationError):
            DomainTrustPolicy.from_dict(data)


class TestDomainTrustDecision:
    def test_decision_is_evidence_only(self) -> None:
        decision = DomainTrustDecision(
            domain_id="domain:example",
            candidate_id="candidate-x",
            source_id="source:community",
            trust_level=DomainTrustLevel.COMMUNITY,
            activation_allowed=True,
            manual_enable_required=True,
            denied_capabilities=(PermissionCapability.MEMORY_WRITE.value,),
            # Manual enablement was satisfied by the explicit activation call;
            # an allowed decision carries no activation-blocking reason code.
            reason_codes=(),
            metadata={"checked_at": "2026-09-01T00:00:00Z"},
        )
        assert decision.domain_id == "domain:example"
        assert decision.candidate_id == "candidate-x"
        assert decision.source_id == "source:community"
        assert decision.trust_level is DomainTrustLevel.COMMUNITY
        assert decision.activation_allowed is True
        assert decision.manual_enable_required is True
        assert decision.denied_capabilities == ("memory.write",)
        assert decision.reason_codes == ()

    def test_decision_frozen(self) -> None:
        decision = DomainTrustDecision(
            domain_id="domain:example",
            candidate_id="candidate-x",
            source_id="source:community",
            trust_level=DomainTrustLevel.COMMUNITY,
            activation_allowed=True,
            manual_enable_required=True,
        )
        with pytest.raises(Exception):  # noqa: B017
            decision.activation_allowed = False  # type: ignore[misc]

    def test_unknown_reason_strings_rejected_by_construction(self) -> None:
        # Reason codes must be stable strings from a closed set; arbitrary
        # free-form text is not accepted as a reason code.
        with pytest.raises(DomainContractValidationError):
            DomainTrustDecision(
                domain_id="domain:example",
                candidate_id="candidate-x",
                source_id="source:community",
                trust_level=DomainTrustLevel.BLOCKED,
                activation_allowed=False,
                manual_enable_required=True,
                reason_codes=("totally-freeform-reason-text",),
            )

    def test_activation_allowed_conflicts_with_blocking_reason(self) -> None:
        with pytest.raises(DomainContractValidationError):
            DomainTrustDecision(
                domain_id="domain:example",
                candidate_id="candidate-x",
                source_id="source:community",
                trust_level=DomainTrustLevel.BLOCKED,
                activation_allowed=True,
                manual_enable_required=True,
                reason_codes=("trust.blocked",),
            )

    def test_denied_capabilities_must_be_canonical_capability_values(self) -> None:
        with pytest.raises(DomainContractValidationError):
            DomainTrustDecision(
                domain_id="domain:example",
                candidate_id="candidate-x",
                source_id="source:community",
                trust_level=DomainTrustLevel.COMMUNITY,
                activation_allowed=True,
                manual_enable_required=True,
                denied_capabilities=("not.a.capability",),
            )

    def test_denied_capabilities_unique(self) -> None:
        with pytest.raises(DomainContractValidationError):
            DomainTrustDecision(
                domain_id="domain:example",
                candidate_id="candidate-x",
                source_id="source:community",
                trust_level=DomainTrustLevel.COMMUNITY,
                activation_allowed=True,
                manual_enable_required=True,
                denied_capabilities=(
                    PermissionCapability.MEMORY_WRITE.value,
                    PermissionCapability.MEMORY_WRITE.value,
                ),
            )

    def test_round_trip(self) -> None:
        decision = DomainTrustDecision(
            domain_id="domain:example",
            candidate_id="candidate-x",
            source_id="source:community",
            trust_level=DomainTrustLevel.BLOCKED,
            activation_allowed=False,
            manual_enable_required=True,
            denied_capabilities=(PermissionCapability.FILE_MODIFY.value,),
            reason_codes=("trust.blocked",),
            metadata={"evidence_ref": "trace:abc"},
        )
        restored = DomainTrustDecision.from_dict(decision.to_dict())
        assert restored == decision

    def test_from_dict_rejects_unknown_fields(self) -> None:
        data = DomainTrustDecision(
            domain_id="domain:example",
            candidate_id="candidate-x",
            source_id="source:community",
            trust_level=DomainTrustLevel.COMMUNITY,
            activation_allowed=True,
            manual_enable_required=True,
        ).to_dict()
        data["unknown_extra"] = "x"
        with pytest.raises(DomainSerializationError):
            DomainTrustDecision.from_dict(data)

    def test_decision_has_no_prompt_or_secret_field(self) -> None:
        decision = DomainTrustDecision(
            domain_id="domain:example",
            candidate_id="candidate-x",
            source_id="source:community",
            trust_level=DomainTrustLevel.COMMUNITY,
            activation_allowed=True,
            manual_enable_required=True,
        )
        fields = set(decision.__dataclass_fields__)
        assert "prompt" not in fields
        assert "content" not in fields
        assert "manifest" not in fields
        assert "signature" not in fields
        assert "secret" not in fields
        assert "payload" not in fields
