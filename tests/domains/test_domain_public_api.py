"""Phase 10.1 – Tests for public API exports from cmm.domains."""

from __future__ import annotations

import cmm.domains


class TestPublicAPI:
    """Verify that all public symbols are exported from cmm.domains."""

    def test_errors_exported(self) -> None:
        assert hasattr(cmm.domains, "DomainError")
        assert hasattr(cmm.domains, "DomainContractError")
        assert hasattr(cmm.domains, "DomainContractValidationError")
        assert hasattr(cmm.domains, "DomainSerializationError")

    def test_enums_exported(self) -> None:
        assert hasattr(cmm.domains, "DomainStatus")
        assert hasattr(cmm.domains, "DomainKind")
        assert hasattr(cmm.domains, "DomainPackKind")
        assert hasattr(cmm.domains, "DomainPackStatus")

    def test_identifiers_exported(self) -> None:
        assert hasattr(cmm.domains, "DomainId")
        assert hasattr(cmm.domains, "DomainManifestId")
        assert hasattr(cmm.domains, "DomainResultId")

    def test_contracts_exported(self) -> None:
        assert hasattr(cmm.domains, "DomainMetadata")
        assert hasattr(cmm.domains, "DomainCapability")
        assert hasattr(cmm.domains, "DomainDependency")
        assert hasattr(cmm.domains, "DomainConflict")
        assert hasattr(cmm.domains, "DomainDefinition")
        assert hasattr(cmm.domains, "DomainResult")
        assert hasattr(cmm.domains, "DomainManifest")
        assert hasattr(cmm.domains, "DomainComponentReference")
        assert hasattr(cmm.domains, "DomainPermissionReference")
        assert hasattr(cmm.domains, "DomainCompatibility")
        assert hasattr(cmm.domains, "DomainPack")
        assert hasattr(cmm.domains, "ParsedDomainPack")

    def test_all_symbols_in_all(self) -> None:
        """Check that all expected symbols are in __all__."""
        expected = {
            "ALL_DOMAIN_STEPS",
            "DOMAIN_STATUS_PRECEDENCE",
            "KNOWN_CROSS_DOMAIN_PORTS",
            "CrossDomainAgentPort",
            "CrossDomainCognitivePort",
            "CrossDomainConfigurationError",
            "CrossDomainContextBuilder",
            "CrossDomainContextSnapshot",
            "CrossDomainContextTransfer",
            "CrossDomainContractError",
            "CrossDomainContradiction",
            "CrossDomainDecision",
            "CrossDomainDependency",
            "CrossDomainDomainResult",
            "CrossDomainEngine",
            "CrossDomainError",
            "CrossDomainExecutionError",
            "CrossDomainFinding",
            "CrossDomainGap",
            "CrossDomainKnowledgePort",
            "CrossDomainKnowledgeResult",
            "CrossDomainLimitError",
            "CrossDomainLimitTracker",
            "CrossDomainLimits",
            "CrossDomainOperationPort",
            "CrossDomainOperationResult",
            "CrossDomainPlanResult",
            "CrossDomainPlannerPort",
            "CrossDomainPolicy",
            "CrossDomainPortError",
            "CrossDomainQuestion",
            "CrossDomainRequest",
            "CrossDomainResult",
            "CrossDomainSerializationError",
            "CrossDomainSeverity",
            "CrossDomainStage",
            "CrossDomainStatus",
            "CrossDomainWorkflowPort",
            "CrossDomainWorkflowResult",
            "DeclarativeDomainLoader",
            "DefaultCrossDomainEngine",
            "DefaultDomainComposer",
            "DefaultDomainResolver",
            "DomainCandidate",
            "DomainCandidateInvalid",
            "DomainCandidateScore",
            "DomainCandidateScorer",
            "DomainCapability",
            "DomainCapabilityConflict",
            "DomainChecksumMismatch",
            "DomainCompatibility",
            "DomainComposer",
            "DomainComponentReference",
            "DomainComposition",
            "DomainCompositionConfigurationError",
            "DomainCompositionConflict",
            "DomainCompositionContractError",
            "DomainCompositionDecision",
            "DomainCompositionError",
            "DomainCompositionExecutionError",
            "DomainCompositionItem",
            "DomainCompositionPolicy",
            "DomainCompositionPort",
            "DomainCompositionSerializationError",
            "DomainCompositionStatus",
            "DomainConflict",
            "DomainConflictPolicy",
            "DomainContractError",
            "DomainContractValidationError",
            "DomainDefinition",
            "DomainDefinitionRegistryValidator",
            "DomainDependency",
            "DomainDependencyMissing",
            "DomainDiscovery",
            "DomainDiscoveryError",
            "DomainDiscoveryIssue",
            "DomainDiscoveryResult",
            "DomainDiscoverySourceError",
            "DomainError",
            "DomainId",
            "DomainKind",
            "DomainLoadFailed",
            "DomainLoadRejected",
            "DomainLoadResult",
            "DomainLoadRollbackFailed",
            "DomainLoadStatus",
            "DomainLoader",
            "DomainLoaderError",
            "DomainLoaderSnapshot",
            "DomainManifest",
            "DomainManifestId",
            "DomainManifestDocument",
            "DomainManifestReader",
            "DomainMetadata",
            "DomainPack",
            "DomainPackKind",
            "DomainPackStatus",
            "DomainPathEscape",
            "DomainPermissionReference",
            "DomainQuery",
            "DomainRegistry",
            "DomainRegistryConflict",
            "DomainRegistryError",
            "DomainRegistryNotFound",
            "DomainRegistryRecord",
            "DomainRegistrySnapshot",
            "DomainRegistryStoreSnapshot",
            "DomainRegistryStateError",
            "DomainRegistryStore",
            "DomainRegistryValidationError",
            "DomainRegistryVersionError",
            "DomainReloadFailed",
            "DomainReloadRollbackFailed",
            "DomainResolutionAmbiguityError",
            "DomainResolutionBlockedError",
            "DomainResolutionContext",
            "DomainResolutionContextBuilder",
            "DomainResolutionContextInvalid",
            "DomainResolutionContractError",
            "DomainResolutionEntity",
            "DomainResolutionError",
            "DomainResolutionEvent",
            "DomainResolutionHistoryItem",
            "DomainResolutionKnowledgeItem",
            "DomainResolutionLimitExceeded",
            "DomainResolutionPolicy",
            "DomainResolutionPolicyError",
            "DomainResolutionPort",
            "DomainResolutionReason",
            "DomainResolutionResource",
            "DomainResolutionResult",
            "DomainResolutionSerializationError",
            "DomainResolutionSignal",
            "DomainResolutionSnapshotError",
            "DomainResolutionStatus",
            "DomainResolutionUnsupportedError",
            "DomainResolver",
            "EffectiveReasoningProfile",
            "DomainResolverConfigurationError",
            "DomainResolverError",
            "DomainResolverExecutionError",
            "DomainResult",
            "DomainResultId",
            "DomainRollbackFailed",
            "DomainScoringPolicy",
            "DomainSerializationError",
            "DomainSource",
            "DomainSourceKind",
            "DomainSourceUntrusted",
            "DomainStatus",
            "DomainUnloadFailed",
            "DomainUnloadRollbackFailed",
            "DomainValidationBlocked",
            "DomainValidationContextInvalid",
            "DomainValidationError",
            "DomainValidationExecutionContext",
            "DomainValidationExecutionError",
            "DomainValidationRequest",
            "DomainValidationRequestInvalid",
            "DomainValidationResult",
            "DomainValidationResult10",
            "DomainValidationStatus",
            "DomainValidationStepMissing",
            "FileSystemDomainDiscovery",
            "InMemoryDomainRegistryStore",
            "JsonDomainManifestReader",
            "ParsedDomainPack",
            "PermissionComposition",
            "PipelineDomainValidator",
            "PresentationComposition",
            "build_domain_validation_context",
            "build_domain_validation_result",
            "build_domain_validation_steps",
            "derive_confidence",
            "derive_cross_domain_status",
            "ensure_domain_validation_allows_install",
            "merge_contradictions",
            "merge_dependencies",
            "merge_domain_results",
            "merge_findings",
            "merge_gaps",
            "merge_questions",
            "DefaultDomainResourceResolver",
            "DefaultDomainResourceValidator",
            "DomainResourceBinding",
            "DomainResourceChecksum",
            "DomainResourceConfigurationError",
            "DomainResourceContext",
            "DomainResourceContractError",
            "DomainResourceDecision",
            "DomainResourceDecisionCode",
            "DomainResourceDefinition",
            "DomainResourceDerivation",
            "DomainResourceDerivationError",
            "DomainResourceDerivationService",
            "DomainResourceError",
            "DomainResourceRegistry",
            "DomainResourceRegistryError",
            "DomainResourceRejection",
            "DomainResourceResolution",
            "DomainResourceResolutionError",
            "DomainResourceResolutionStatus",
            "DomainResourceResolver",
            "DomainResourceSerializationError",
            "DomainResourceTemporalPolicy",
            "DomainResourceValidationOperator",
            "DomainResourceValidationResult",
            "DomainResourceValidationRule",
            "DomainResourceValidationSeverity",
            "DomainResourceValidator",
            "InMemoryDomainResourceRegistry",
            "merge_recommendations",
            "INITIAL_DOMAIN_PROFILE_NAMES",
            "DefaultDomainProfileComposer",
            "DefaultDomainProfileResolver",
            "DomainMemoryPolicy",
            "DomainPresentationPolicy",
            "DomainProductionPolicy",
            "DomainProfileComposer",
            "DomainProfileCompositionError",
            "DomainProfileCompositionResult",
            "DomainProfileConfigurationError",
            "DomainProfileConflict",
            "DomainProfileConflictSeverity",
            "DomainProfileContractError",
            "DomainProfileDecision",
            "DomainProfileDecisionCode",
            "DomainProfileDefinition",
            "DomainProfileDraft",
            "DomainProfileError",
            "DomainProfileModification",
            "DomainProfileOverlay",
            "DomainProfileRegistry",
            "DomainProfileRegistryError",
            "DomainProfileRejection",
            "DomainProfileResolution",
            "DomainProfileResolutionError",
            "DomainProfileResolutionRequest",
            "DomainProfileResolutionStatus",
            "DomainProfileResolver",
            "DomainProfileSerializationError",
            "DomainProfileSource",
            "DomainQuestionPolicy",
            "DomainReasoningDepth",
            "DomainTemporalPolicy",
            "InMemoryDomainProfileRegistry",
            "ResolvedDomainProfile",
        }
        expected.update(
            {
                "DOMAIN_RULE_CONTRACT_VERSION",
                "DefaultDomainRuleExecutor",
                "DefaultDomainRuleSelector",
                "DomainReasoningRuleDefinition",
                "DomainRuleConfigurationError",
                "DomainRuleConflictSeverity",
                "DomainRuleContractError",
                "DomainRuleError",
                "DomainRuleExecutionError",
                "DomainRuleExecutionPlan",
                "DomainRuleExecutionPolicy",
                "DomainRuleExecutionResult",
                "DomainRuleExecutionStatus",
                "DomainRuleExecutor",
                "DomainRuleResult",
                "DomainRuleSelectionConflict",
                "DomainRuleSelectionDecision",
                "DomainRuleSelectionDecisionCode",
                "DomainRuleSelectionError",
                "DomainRuleSelectionPolicy",
                "DomainRuleSelectionStatus",
                "DomainRuleSelector",
                "DomainRuleSerializationError",
                "DomainRuleSource",
                "DomainRuleSourceRecord",
                "INITIAL_DOMAIN_REASONING_RULE_IDS",
                "InMemoryReasoningRuleRegistry",
                "SelectedReasoningRule",
                "build_initial_reasoning_rule_catalog",
            }
        )
        assert set(cmm.domains.__all__) == expected

    def test_all_symbols_accessible_from_package(self) -> None:
        """All __all__ symbols should be accessible as attributes."""
        for name in cmm.domains.__all__:
            assert hasattr(cmm.domains, name), f"Missing symbol: {name}"

    def test_no_unexpected_symbols_in_package(self) -> None:
        """Ensure we have exactly the right number of public symbols."""
        assert len(cmm.domains.__all__) == 276

    def test_domain_status_all_values(self) -> None:
        """Verify DomainStatus enum values via package access."""
        from cmm.domains import DomainStatus

        statuses = {v.value for v in DomainStatus}
        assert "active" in statuses
        assert "failed" in statuses
        assert "unloaded" in statuses

    def test_domain_kind_all_values(self) -> None:
        """Verify DomainKind enum values via package access."""
        from cmm.domains import DomainKind

        kinds = {v.value for v in DomainKind}
        assert "core" in kinds
        assert "experimental" in kinds

    def test_no_duplicate_exports(self) -> None:
        """Ensure __all__ has no duplicates."""
        assert len(cmm.domains.__all__) == len(set(cmm.domains.__all__))

    def test_discovery_and_loader_symbols_exported(self) -> None:
        assert hasattr(cmm.domains, "DomainSource")
        assert hasattr(cmm.domains, "DomainCandidate")
        assert hasattr(cmm.domains, "DomainDiscoveryIssue")
        assert hasattr(cmm.domains, "DomainDiscoveryResult")
        assert hasattr(cmm.domains, "DomainDiscovery")
        assert hasattr(cmm.domains, "FileSystemDomainDiscovery")
        assert hasattr(cmm.domains, "DomainManifestReader")
        assert hasattr(cmm.domains, "JsonDomainManifestReader")
        assert hasattr(cmm.domains, "DomainLoader")
        assert hasattr(cmm.domains, "DeclarativeDomainLoader")
        assert hasattr(cmm.domains, "DomainLoadResult")
        assert hasattr(cmm.domains, "DomainLoaderSnapshot")
        assert hasattr(cmm.domains, "DomainSourceKind")
        assert hasattr(cmm.domains, "DomainLoadStatus")

    def test_no_internal_helpers_exported(self) -> None:
        """Path, checksum, and parsing internals must never be public."""
        forbidden = {
            "_validate_safe_relative_path",
            "_walk_directories",
            "_extract_identity",
            "_compare_sources",
            "_compare_candidates",
            "_strip_internal_metadata",
        }
        assert forbidden.isdisjoint(set(cmm.domains.__all__))
