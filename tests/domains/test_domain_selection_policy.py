from dataclasses import FrozenInstanceError

import pytest

from cmm.domains.errors import (
    DomainContractValidationError,
    DomainSerializationError,
)
from cmm.domains.selection_contracts import DomainSelectionPolicy


def test_domain_selection_policy_defaults_are_canonical():
    policy = DomainSelectionPolicy()

    assert policy.name == "default"
    assert policy.explicit_domain_priority is True
    assert policy.session_domain_priority is True
    assert policy.goal_domain_priority is True
    assert policy.allow_multi_domain is True
    assert policy.maximum_supporting_domains == 3
    assert policy.minimum_primary_confidence == 0.70
    assert policy.minimum_supporting_confidence == 0.55
    assert str(policy.fallback_domain) == "domain:general"
    assert policy.ambiguity_strategy == "clarify_or_fallback"
    assert dict(policy.metadata) == {}


def test_domain_selection_policy_is_immutable():
    policy = DomainSelectionPolicy()

    with pytest.raises(FrozenInstanceError):
        policy.name = "other"


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("explicit_domain_priority", 1),
        ("session_domain_priority", 1),
        ("goal_domain_priority", 1),
        ("allow_multi_domain", 1),
        ("maximum_supporting_domains", True),
        ("minimum_primary_confidence", True),
        ("minimum_supporting_confidence", True),
    ],
)
def test_domain_selection_policy_rejects_bool_int_confusion(field, value):
    with pytest.raises(DomainContractValidationError):
        DomainSelectionPolicy(**{field: value})


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("minimum_primary_confidence", -0.01),
        ("minimum_primary_confidence", 1.01),
        ("minimum_supporting_confidence", -0.01),
        ("minimum_supporting_confidence", 1.01),
    ],
)
def test_domain_selection_policy_rejects_invalid_confidence(field, value):
    with pytest.raises(DomainContractValidationError):
        DomainSelectionPolicy(**{field: value})


def test_domain_selection_policy_rejects_negative_supporting_limit():
    with pytest.raises(DomainContractValidationError):
        DomainSelectionPolicy(maximum_supporting_domains=-1)


def test_domain_selection_policy_rejects_unknown_ambiguity_strategy():
    with pytest.raises(DomainContractValidationError):
        DomainSelectionPolicy(ambiguity_strategy="pick_first")


def test_domain_selection_policy_deep_freezes_metadata():
    policy = DomainSelectionPolicy(
        metadata={
            "source": "phase-10.31",
            "nested": {"enabled": True},
        }
    )

    with pytest.raises(TypeError):
        policy.metadata["source"] = "changed"

    with pytest.raises(TypeError):
        policy.metadata["nested"]["enabled"] = False


def test_domain_selection_policy_rejects_credential_like_metadata():
    with pytest.raises(DomainContractValidationError):
        DomainSelectionPolicy(
            metadata={
                "nested": {
                    "api_token": "must-not-be-stored",
                }
            }
        )


def test_domain_selection_policy_round_trip():
    policy = DomainSelectionPolicy(
        name="strict",
        explicit_domain_priority=True,
        session_domain_priority=False,
        goal_domain_priority=True,
        allow_multi_domain=False,
        maximum_supporting_domains=1,
        minimum_primary_confidence=0.80,
        minimum_supporting_confidence=0.60,
        fallback_domain="domain:general",
        ambiguity_strategy="clarify_or_fallback",
        metadata={"source": "test"},
    )

    restored = DomainSelectionPolicy.from_dict(policy.to_dict())

    assert restored.to_dict() == policy.to_dict()


def test_domain_selection_policy_from_dict_rejects_unknown_field():
    with pytest.raises(DomainSerializationError):
        DomainSelectionPolicy.from_dict(
            {
                "name": "default",
                "unknown_field": "forbidden",
            }
        )
