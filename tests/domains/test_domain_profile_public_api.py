"""Phase 10.11 – Tests for Domain Profile public API exports.

Verifies exact symbol identity (no re-exported aliases), absence of suffixed
aliases and private helpers, deterministic ``__all__`` content and stability
of previous Phase 10 public APIs.
"""

from __future__ import annotations

import cmm.domains
import cmm.domains.enums
import cmm.domains.errors
import cmm.domains.profile_composition
import cmm.domains.profile_contracts
import cmm.domains.profile_registry
import cmm.domains.profile_resolver

_ENUM_EXPORTS = (
    "DomainProfileResolutionStatus",
    "DomainProfileSource",
    "DomainProfileDecisionCode",
    "DomainProfileConflictSeverity",
    "DomainReasoningDepth",
)

_CONTRACT_EXPORTS = (
    "DomainQuestionPolicy",
    "DomainPresentationPolicy",
    "DomainMemoryPolicy",
    "DomainTemporalPolicy",
    "DomainProductionPolicy",
    "DomainProfileDefinition",
    "DomainProfileOverlay",
    "DomainProfileResolutionRequest",
    "DomainProfileModification",
    "DomainProfileConflict",
    "DomainProfileRejection",
    "DomainProfileDecision",
    "DomainProfileDraft",
    "ResolvedDomainProfile",
    "DomainProfileCompositionResult",
    "DomainProfileResolution",
)

_REGISTRY_EXPORTS = (
    "DomainProfileRegistry",
    "InMemoryDomainProfileRegistry",
    "INITIAL_DOMAIN_PROFILE_NAMES",
)

_COMPOSER_EXPORTS = (
    "DomainProfileComposer",
    "DefaultDomainProfileComposer",
)

_RESOLVER_EXPORTS = (
    "DomainProfileResolver",
    "DefaultDomainProfileResolver",
)

_ERROR_EXPORTS = (
    "DomainProfileError",
    "DomainProfileContractError",
    "DomainProfileSerializationError",
    "DomainProfileConfigurationError",
    "DomainProfileRegistryError",
    "DomainProfileCompositionError",
    "DomainProfileResolutionError",
)

_ALL_PROFILE_EXPORTS = (
    _ENUM_EXPORTS
    + _CONTRACT_EXPORTS
    + _REGISTRY_EXPORTS
    + _COMPOSER_EXPORTS
    + _RESOLVER_EXPORTS
    + _ERROR_EXPORTS
)

_MODULE_BY_GROUP = (
    (_ENUM_EXPORTS, cmm.domains.enums),
    (_CONTRACT_EXPORTS, cmm.domains.profile_contracts),
    (_REGISTRY_EXPORTS, cmm.domains.profile_registry),
    (_COMPOSER_EXPORTS, cmm.domains.profile_composition),
    (_RESOLVER_EXPORTS, cmm.domains.profile_resolver),
    (_ERROR_EXPORTS, cmm.domains.errors),
)


class TestDomainProfileExports:
    def test_all_profile_symbols_exported(self) -> None:
        for name in _ALL_PROFILE_EXPORTS:
            assert hasattr(cmm.domains, name), f"Missing export: {name}"
            assert name in cmm.domains.__all__, f"Missing from __all__: {name}"

    def test_exact_symbol_identity_per_module(self) -> None:
        for names, module in _MODULE_BY_GROUP:
            for name in names:
                exported = getattr(cmm.domains, name)
                origin = getattr(module, name)
                assert exported is origin, f"{name} is not the exact module symbol"

    def test_no_aliased_symbol_names(self) -> None:
        # Every exported class/protocol/enum keeps its own __name__: the
        # package never re-exports a symbol under a different (suffixed) name.
        for name in _ALL_PROFILE_EXPORTS:
            symbol = getattr(cmm.domains, name)
            if isinstance(symbol, type):
                assert symbol.__name__ == name

    def test_no_suffixed_profile_aliases_in_all(self) -> None:
        legacy = {"EffectiveReasoningProfile"}
        expected = {
            name
            for name in _ALL_PROFILE_EXPORTS
            if "Profile" in name or "PROFILE" in name
        } | legacy
        profile_like = {
            name
            for name in cmm.domains.__all__
            if "Profile" in name or "PROFILE" in name
        }
        assert profile_like == expected

    def test_no_private_helpers_exported(self) -> None:
        assert all(not name.startswith("_") for name in cmm.domains.__all__)
        internal_helpers = {
            "_fold_permissions",
            "_fold_restrictive_constraint",
            "_ordered_union",
            "_ordered_intersection",
            "_ordered_difference",
            "_overlay_sort_key",
            "_is_overlay_relevant",
            "_is_overlay_mandatory",
            "_contribution_from_definition",
            "_contribution_from_overlay",
        }
        assert internal_helpers.isdisjoint(set(cmm.domains.__all__))

    def test_module_level_helpers_not_promoted_to_package(self) -> None:
        # Public-in-module but deliberately not part of the approved package
        # export list.
        not_exported = {
            "merge_question_policy",
            "merge_presentation_policy",
            "merge_memory_policy",
            "merge_temporal_policy",
            "merge_production_policy",
            "DETAIL_LEVEL_ORDER",
            "RETENTION_SCOPE_ORDER",
        }
        assert not_exported.isdisjoint(set(cmm.domains.__all__))

    def test_all_is_deterministic(self) -> None:
        first = list(cmm.domains.__all__)
        second = list(cmm.domains.__all__)
        assert first == second
        assert len(first) == len(set(first))
        assert all(isinstance(name, str) for name in first)

    def test_initial_domain_profile_names_exact(self) -> None:
        assert cmm.domains.INITIAL_DOMAIN_PROFILE_NAMES == (
            "GeneralProfile",
            "HealthProfile",
            "RelationshipProfile",
            "UniversityProfile",
            "OppositionProfile",
            "ReflectionProfile",
            "ConcernProfile",
            "LanguageProfile",
            "NilProfile",
            "SportProfile",
            "LifePlanProfile",
            "ProjectProfile",
        )


class TestDomainProfileEnumSurface:
    def test_resolution_status_exact_values(self) -> None:
        values = {v.value for v in cmm.domains.DomainProfileResolutionStatus}
        assert values == {"resolved", "partial", "blocked", "failed"}

    def test_profile_source_exact_values(self) -> None:
        values = [v.value for v in cmm.domains.DomainProfileSource]
        assert values == [
            "global_policy",
            "primary_domain",
            "supporting_domain",
            "workflow",
            "operation",
            "risk",
            "actor",
            "autonomy",
            "explicit_request",
        ]

    def test_reasoning_depth_is_ordered_shallowest_first(self) -> None:
        values = [v.value for v in cmm.domains.DomainReasoningDepth]
        assert values == ["shallow", "standard", "deep", "exhaustive"]

    def test_conflict_severity_exact_values(self) -> None:
        values = {v.value for v in cmm.domains.DomainProfileConflictSeverity}
        assert values == {"warning", "error", "blocking"}

    def test_decision_code_minimum_values(self) -> None:
        values = {v.value for v in cmm.domains.DomainProfileDecisionCode}
        assert {
            "profile_applied",
            "overlay_applied",
            "overlay_skipped",
            "mandatory_rule_preserved",
            "prohibited_rule_prevailed",
            "resource_restricted",
            "confidence_raised",
            "limit_restricted",
            "inference_prohibited",
            "action_prohibited",
            "permission_restricted",
            "escalation_added",
            "policy_restricted",
            "conflict_recorded",
        } <= values


class TestDomainProfileErrorSurface:
    def test_error_hierarchy(self) -> None:
        base = cmm.domains.DomainProfileError
        for name in _ERROR_EXPORTS[1:]:
            assert issubclass(getattr(cmm.domains, name), base)
        assert issubclass(base, cmm.domains.DomainError)

    def test_contract_error_is_value_error(self) -> None:
        assert issubclass(cmm.domains.DomainProfileContractError, ValueError)

    def test_error_codes_stable(self) -> None:
        assert cmm.domains.DomainProfileError.code == "DOMAIN_PROFILE_ERROR"
        assert (
            cmm.domains.DomainProfileContractError.code
            == "DOMAIN_PROFILE_CONTRACT_ERROR"
        )
        assert (
            cmm.domains.DomainProfileSerializationError.code
            == "DOMAIN_PROFILE_SERIALIZATION_ERROR"
        )
        assert (
            cmm.domains.DomainProfileConfigurationError.code
            == "DOMAIN_PROFILE_CONFIGURATION_ERROR"
        )
        assert (
            cmm.domains.DomainProfileRegistryError.code
            == "DOMAIN_PROFILE_REGISTRY_ERROR"
        )
        assert (
            cmm.domains.DomainProfileCompositionError.code
            == "DOMAIN_PROFILE_COMPOSITION_ERROR"
        )
        assert (
            cmm.domains.DomainProfileResolutionError.code
            == "DOMAIN_PROFILE_RESOLUTION_ERROR"
        )


class TestPreviousPhaseApisRemain:
    def test_foundational_exports_remain(self) -> None:
        for name in (
            "DomainError",
            "DomainStatus",
            "DomainKind",
            "DomainId",
            "DomainRegistry",
            "DomainDefinition",
        ):
            assert hasattr(cmm.domains, name)
            assert name in cmm.domains.__all__

    def test_later_phase_exports_remain(self) -> None:
        for name in (
            "DefaultCrossDomainEngine",
            "DefaultDomainResolver",
            "DefaultDomainResourceResolver",
            "InMemoryDomainRegistryStore",
            "InMemoryDomainResourceRegistry",
            "PipelineDomainValidator",
        ):
            assert hasattr(cmm.domains, name)
            assert name in cmm.domains.__all__
