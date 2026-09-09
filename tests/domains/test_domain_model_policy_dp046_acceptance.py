"""Phase 10.46 – AT-DP-046 real canonical model-policy boundary acceptance.

The scenarios use real canonical components and official in-memory
implementations only: the canonical Health domain definition, the immutable
``DomainModelPolicy``, the Agent Runtime requirements resolver, and the Kernel
``ProviderRegistry``/``ModelCatalog``/``ModelRouter``. No router, catalog, or
registry is mocked.
"""

from __future__ import annotations

import json
from dataclasses import replace
from decimal import Decimal

from cmm.agent_runtime.domain_model_policy_adapter import (
    domain_model_validation_requirements,
)
from cmm.agent_runtime.enums import (
    AgentValidationStage,
    ValidationRequirementKind,
)
from cmm.agent_runtime.model_requirements_resolver import (
    resolve_runtime_model_requirements,
)
from cmm.agent_runtime.operation_execution_contracts import OperationDescriptor
from cmm.agent_runtime.validation_integration_contracts import AgentValidationRequest
from cmm.domains.health.definition import build_health_domain_definition
from cmm.domains.model_policy_contracts import DomainModelPolicy
from kernel.llm.capabilities import ModelCapabilities
from kernel.llm.model_catalog import ModelCatalog, ModelSpec
from kernel.llm.model_router import ModelRouter
from kernel.llm.model_selection import ModelRequirements, model_matches_requirements
from kernel.llm.provider_registry import ProviderRegistry, ProviderSpec

_REASONING_AND_STRUCTURED = ModelCapabilities(
    reasoning=True,
    structured_output=True,
    tool_calling=False,
)
_REASONING_STRUCTURED_TOOLS = ModelCapabilities(
    reasoning=True,
    structured_output=True,
    tool_calling=True,
)
_REASONING_ONLY = ModelCapabilities(reasoning=True)


def _build_primary_inventory() -> tuple[ProviderRegistry, ModelCatalog]:
    providers = ProviderRegistry()
    providers.register(
        ProviderSpec(
            id="local-lab",
            provider_type="local",
            api_style="chat_completions",
            availability="available",
        )
    )
    providers.register(
        ProviderSpec(
            id="cloud-x",
            provider_type="remote",
            api_style="chat_completions",
            base_url="https://api.example.invalid/v1",
            availability="available",
        )
    )

    catalog = ModelCatalog(providers)
    catalog.register(
        ModelSpec(
            id="reasoner-local",
            provider_id="local-lab",
            context_window=128_000,
            capabilities=_REASONING_STRUCTURED_TOOLS,
            input_cost_per_million=Decimal("0.00"),
            output_cost_per_million=Decimal("0.00"),
            availability="available",
        )
    )
    catalog.register(
        ModelSpec(
            id="reasoner-cloud",
            provider_id="cloud-x",
            context_window=200_000,
            capabilities=_REASONING_AND_STRUCTURED,
            input_cost_per_million=Decimal("3.00"),
            output_cost_per_million=Decimal("9.00"),
            availability="available",
        )
    )
    catalog.register(
        ModelSpec(
            id="no-structured",
            provider_id="cloud-x",
            context_window=128_000,
            capabilities=_REASONING_ONLY,
            input_cost_per_million=Decimal("0.10"),
            availability="available",
        )
    )
    catalog.register(
        ModelSpec(
            id="unavailable-model",
            provider_id="cloud-x",
            context_window=128_000,
            capabilities=_REASONING_AND_STRUCTURED,
            input_cost_per_million=Decimal("0.01"),
            availability="unavailable",
        )
    )
    catalog.register(
        ModelSpec(
            id="expensive-model",
            provider_id="cloud-x",
            context_window=128_000,
            capabilities=_REASONING_AND_STRUCTURED,
            input_cost_per_million=Decimal("50.00"),
            availability="available",
        )
    )
    catalog.register(
        ModelSpec(
            id="small-context",
            provider_id="cloud-x",
            context_window=8_000,
            capabilities=_REASONING_AND_STRUCTURED,
            input_cost_per_million=Decimal("0.01"),
            availability="available",
        )
    )
    return providers, catalog


def _build_replacement_inventory() -> tuple[ProviderRegistry, ModelCatalog]:
    providers = ProviderRegistry()
    providers.register(
        ProviderSpec(
            id="alt-local",
            provider_type="local",
            api_style="chat_completions",
            availability="available",
        )
    )
    providers.register(
        ProviderSpec(
            id="alt-cloud",
            provider_type="remote",
            api_style="chat_completions",
            base_url="https://api.alt.invalid/v1",
            availability="available",
        )
    )

    catalog = ModelCatalog(providers)
    catalog.register(
        ModelSpec(
            id="alt-reasoner",
            provider_id="alt-local",
            context_window=64_000,
            capabilities=_REASONING_AND_STRUCTURED,
            input_cost_per_million=Decimal("0.00"),
            availability="available",
        )
    )
    catalog.register(
        ModelSpec(
            id="alt-cloud-model",
            provider_id="alt-cloud",
            context_window=300_000,
            capabilities=_REASONING_AND_STRUCTURED,
            input_cost_per_million=Decimal("0.50"),
            availability="available",
        )
    )
    return providers, catalog


def _representative_health_definition():
    """Derive a representative Health definition without editing Health policy."""
    return replace(
        build_health_domain_definition(),
        model_policy=DomainModelPolicy(
            domain_id="domain:health",
            require_reasoning=True,
            require_structured_output=True,
            minimum_context_window=32_768,
            require_context_validation=True,
            require_response_validation=True,
        ),
    )


def _assert_policy_names_no_concrete_inventory(policy, *catalogs) -> None:
    serialized = json.dumps(policy.to_dict(), sort_keys=True)

    assert "preferred_models" not in serialized
    assert "preferred_providers" not in serialized
    for catalog in catalogs:
        for model in catalog.list():
            assert model.id not in serialized
            assert model.provider_id not in serialized


# ── Scenario A — explicit compatible model ────────────────────────────────────


def test_scenario_a_explicit_compatible_model() -> None:
    providers, catalog = _build_primary_inventory()
    health = _representative_health_definition()

    resolved = resolve_runtime_model_requirements(
        domain_policies=(health.model_policy,)
    )
    explicit_model = catalog.get("reasoner-local", provider_id="local-lab")

    assert model_matches_requirements(
        explicit_model,
        provider_registry=providers,
        requirements=resolved.effective,
    )
    assert any(
        source.source_kind == "domain" and source.source_id == "domain:health"
        for source in resolved.sources
    )
    _assert_policy_names_no_concrete_inventory(health.model_policy, catalog)
    assert resolved.effective.structured_output is True
    assert resolved.effective.minimum_context_window == 32_768


# ── Scenario B — explicit incompatible model ──────────────────────────────────


def test_scenario_b_explicit_incompatible_model_is_rejected_without_substitution() -> (
    None
):
    providers, catalog = _build_primary_inventory()
    health = _representative_health_definition()

    resolved = resolve_runtime_model_requirements(
        domain_policies=(health.model_policy,)
    )
    missing_capability = catalog.get("no-structured", provider_id="cloud-x")
    insufficient_context = catalog.get("small-context", provider_id="cloud-x")

    assert (
        model_matches_requirements(
            missing_capability,
            provider_registry=providers,
            requirements=resolved.effective,
        )
        is False
    )
    assert (
        model_matches_requirements(
            insufficient_context,
            provider_registry=providers,
            requirements=resolved.effective,
        )
        is False
    )
    # The constraint survives resolution; nothing is weakened to fit a model.
    assert resolved.effective.structured_output is True
    assert resolved.effective.minimum_context_window == 32_768


# ── Scenario C — AUTO routing ─────────────────────────────────────────────────


def test_scenario_c_auto_routing_uses_canonical_router() -> None:
    providers, catalog = _build_primary_inventory()
    health = _representative_health_definition()

    operation = OperationDescriptor(
        name="llm.reason",
        description="Reason over health context",
        model_requirements=ModelRequirements(
            maximum_input_cost_per_million=Decimal("1.00"),
        ),
    )

    resolved = resolve_runtime_model_requirements(
        operation=operation,
        domain_policies=(health.model_policy,),
    )
    decision = ModelRouter(
        provider_registry=providers,
        model_catalog=catalog,
    ).decide(resolved.effective)

    assert decision.status == "selected"
    assert decision.selected_model_id == "reasoner-local"
    assert resolved.effective.maximum_input_cost_per_million == Decimal("1.00")

    rejected = {
        model.qualified_model_id: set(model.reasons)
        for model in decision.rejected_models
    }
    assert "missing_capability" in rejected["cloud-x:no-structured"]
    assert "insufficient_context" in rejected["cloud-x:small-context"]
    assert "model_unavailable" in rejected["cloud-x:unavailable-model"]
    assert "input_cost_exceeded" in rejected["cloud-x:reasoner-cloud"]
    assert "input_cost_exceeded" in rejected["cloud-x:expensive-model"]

    _assert_policy_names_no_concrete_inventory(health.model_policy, catalog)


# ── Scenario D — catalog replacement ──────────────────────────────────────────


def test_scenario_d_catalog_replacement_keeps_domain_policy_unchanged() -> None:
    _, primary_catalog = _build_primary_inventory()
    replacement_providers, replacement_catalog = _build_replacement_inventory()
    health = _representative_health_definition()
    policy_before = health.model_policy.to_dict()

    resolved = resolve_runtime_model_requirements(
        domain_policies=(health.model_policy,)
    )
    decision = ModelRouter(
        provider_registry=replacement_providers,
        model_catalog=replacement_catalog,
    ).decide(resolved.effective)

    assert decision.status == "selected"
    assert decision.selected_model_id == "alt-reasoner"
    assert health.model_policy.to_dict() == policy_before
    _assert_policy_names_no_concrete_inventory(
        health.model_policy,
        primary_catalog,
        replacement_catalog,
    )


# ── Scenario E — multi-domain restrictive composition ─────────────────────────


def test_scenario_e_multi_domain_composition_is_conservative() -> None:
    providers, catalog = _build_primary_inventory()
    health_policy = DomainModelPolicy(
        domain_id="domain:health",
        require_reasoning=True,
        require_structured_output=True,
        minimum_context_window=32_768,
    )
    law_policy = DomainModelPolicy(
        domain_id="domain:law",
        require_tool_calling=True,
        minimum_context_window=131_072,
    )

    resolved = resolve_runtime_model_requirements(
        domain_policies=(health_policy, law_policy)
    )

    assert resolved.effective.reasoning is True
    assert resolved.effective.structured_output is True
    assert resolved.effective.tool_calling is True
    assert resolved.effective.minimum_context_window == 131_072

    decision = ModelRouter(
        provider_registry=providers,
        model_catalog=catalog,
    ).decide(resolved.effective)

    assert decision.status == "no_match"
    assert decision.selected_model_id is None
    assert resolved.effective.minimum_context_window == 131_072
    _assert_policy_names_no_concrete_inventory(health_policy, catalog)
    _assert_policy_names_no_concrete_inventory(law_policy, catalog)


# ── Validation connection ─────────────────────────────────────────────────────


def test_validation_bindings_connect_to_canonical_stages() -> None:
    health = _representative_health_definition()

    requirements = domain_model_validation_requirements(health.model_policy)

    assert len(requirements) == 2
    context_requirement, response_requirement = requirements

    assert context_requirement.requirement_id == (
        "domain-model-policy:domain:health:context"
    )
    assert context_requirement.validation_kind is ValidationRequirementKind.CUSTOM
    assert context_requirement.stage is AgentValidationStage.PRE_EXECUTION
    assert context_requirement.required is True
    assert context_requirement.blocking is True
    assert context_requirement.metadata["phase"] == "10.46"
    assert context_requirement.metadata["semantic_kind"] == "context_validation"

    assert response_requirement.requirement_id == (
        "domain-model-policy:domain:health:response"
    )
    assert (
        response_requirement.validation_kind is ValidationRequirementKind.POST_CONDITION
    )
    assert response_requirement.stage is AgentValidationStage.POST_EXECUTION
    assert response_requirement.required is True
    assert response_requirement.blocking is True
    assert response_requirement.metadata["phase"] == "10.46"
    assert response_requirement.metadata["semantic_kind"] == "response_validation"

    pre_execution_request = AgentValidationRequest(
        id="validation-request-context",
        run_id="run-dp046",
        iteration_id="iteration-1",
        operation_request_id="operation-request-1",
        stage=AgentValidationStage.PRE_EXECUTION,
        requirements=(context_requirement,),
    )
    post_execution_request = AgentValidationRequest(
        id="validation-request-response",
        run_id="run-dp046",
        iteration_id="iteration-1",
        operation_request_id="operation-request-1",
        stage=AgentValidationStage.POST_EXECUTION,
        requirements=(response_requirement,),
    )

    assert pre_execution_request.fingerprint
    assert post_execution_request.fingerprint
    assert pre_execution_request.stage is AgentValidationStage.PRE_EXECUTION
    assert post_execution_request.stage is AgentValidationStage.POST_EXECUTION
