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
            "DomainCompositionInput",
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
            "DomainSelectionPolicy",
            "DomainSelectionTransition",
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
            "build_domain_selection_transition",
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
            "DefaultDomainKnowledgeAuthority",
            "DefaultDomainResourceAuthority",
            "DefaultDomainResourceResolver",
            "DefaultDomainResourceValidator",
            "DomainKnowledgeAuthority",
            "DomainKnowledgeCurrentVerdict",
            "DomainResourceAuthority",
            "DomainResourceBinding",
            "DomainResourceChecksum",
            "DomainResourceConfigurationError",
            "DomainResourceContext",
            "DomainResourceCurrentVerdict",
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
        expected.update(
            {
                "DefaultDomainOperationOrchestrator",
                "DomainOperationApprovalRequiredError",
                "DomainOperationAvailability",
                "DomainOperationAvailabilityContext",
                "DomainOperationAvailabilityResolver",
                "DomainOperationCancellationError",
                "DomainOperationContext",
                "DomainOperationContractError",
                "DomainOperationDefinition",
                "DomainOperationError",
                "DomainOperationExecutionDelegate",
                "DomainOperationExecutionError",
                "DomainOperationPermissionDeniedError",
                "DomainOperationRegistryError",
                "DomainOperationRequest",
                "DomainOperationResolutionError",
                "DomainOperationResult",
                "DomainOperationRollbackError",
                "DomainOperationRollbackResult",
                "DomainOperationSerializationError",
                "DomainOperationStatus",
                "DomainOperationTraceEntry",
                "DomainOperationType",
                "DomainOperationUnavailableError",
                "DomainOperationValidationError",
                "INITIAL_DOMAIN_OPERATION_IDS",
                "InMemoryDomainOperationRegistry",
                "build_domain_operation_approval_requirement",
                "build_initial_domain_operation_catalog",
                "validate_domain_operation_transition",
            }
        )
        expected.update(
            {
                "CrossDomainDuration",
                "CrossDomainPermissionDecision",
                "CrossDomainPermissionRequest",
                "DomainOperationPermissionDecision",
                "DomainRulePermissionDecision",
                "DomainWorkflowPermissionDecision",
                "DomainAutonomyLimits",
                "DomainPermissionConflict",
                "DomainPermissionPolicy",
                "DomainPermissionRequest",
                "DomainPermissionRegistry",
                "DomainPermissionResolution",
                "DomainPermissionResolver",
                "DomainPermissionApprovalRequiredError",
                "DomainPermissionConflictError",
                "DomainPermissionContractError",
                "DomainPermissionCrossDomainError",
                "DomainPermissionDeniedError",
                "DomainPermissionError",
                "DomainPermissionEvaluationError",
                "DomainPermissionGate",
                "DomainPermissionRegistryError",
                "DomainPermissionResolutionError",
                "DomainPermissionSerializationError",
                "PermissionGateOutcome",
                "PermissionGateReason",
                "PermissionGateResult",
                "build_initial_permission_catalog",
                "evaluate_domain_policy",
                "evaluate_domain_operation",
                "evaluate_domain_rule",
                "evaluate_domain_workflow",
                "evaluate_domain_workflow_node",
                "request_for_operation",
                "request_for_rule_permission",
                "request_for_workflow",
            }
        )
        expected.update(
            {
                "DefaultDomainPresentationPlanner",
                "DefaultDomainPresentationPreservationValidator",
                "DomainOutputIntent",
                "DomainOutputIntentType",
                "DomainPresentationComponentDescriptor",
                "DomainPresentationConflict",
                "DomainPresentationConflictCode",
                "DomainPresentationConflictError",
                "DomainPresentationContractError",
                "DomainPresentationDecision",
                "DomainPresentationDecisionCode",
                "DomainPresentationEpistemicKind",
                "DomainPresentationError",
                "DomainPresentationItemRef",
                "DomainPresentationItemType",
                "DomainPresentationOutputIntentError",
                "DomainPresentationPlan",
                "DomainPresentationPlanner",
                "DomainPresentationPolicyError",
                "DomainPresentationPreservationError",
                "DomainPresentationPreservationValidator",
                "DomainPresentationRequest",
                "DomainPresentationRequiredSectionError",
                "DomainPresentationSectionPlan",
                "DomainPresentationSerializationError",
                "DomainPresentationTerminologyError",
                "DomainPresentationUnknownReferenceError",
                "DomainPresentationValidationCode",
                "DomainPresentationValidationResult",
                "DomainPresentationValidationState",
                "DomainPresentationWarningPriorityError",
                "DefaultDomainTraceReferenceValidator",
                "CrossDomainTraceReference",
                "DomainTrace",
                "DomainTraceAssembler",
                "DomainTraceAssemblyRequest",
                "DomainTraceContribution",
                "DomainTraceDomainSelection",
                "DomainTraceContractError",
                "DomainTraceError",
                "DomainTraceReference",
                "DomainTraceReferenceInventory",
                "DomainTraceReferenceKind",
                "DomainTraceReferenceValidator",
                "DomainTraceReferences",
                "DomainTraceRole",
                "DomainResultTraceReference",
                "DomainTraceSerializationError",
                "DomainTraceStatus",
                "DomainTraceValidationCode",
                "DomainTraceValidationError",
                "DomainTraceValidationResult",
                "DomainTraceValidationState",
            }
        )
        expected.update(
            {
                "DefaultDomainMemoryIntegrationValidator",
                "DefaultDomainMemoryViewResolver",
                "DomainMemoryApprovalDecisionSnapshot",
                "DomainMemoryApprovalRequestSnapshot",
                "DomainMemoryCapability",
                "DomainMemoryContractError",
                "DomainMemoryError",
                "DomainMemoryIntegrationValidator",
                "DomainMemoryPermissionDecisionSnapshot",
                "DomainMemoryPermissionError",
                "DomainMemoryPrivacyError",
                "DomainMemoryProposalBinding",
                "DomainMemoryProposalBindingError",
                "DomainMemoryProposalKind",
                "DomainMemoryProposalSnapshot",
                "DomainMemoryReference",
                "DomainMemoryReferenceInventory",
                "DomainMemoryReferenceKind",
                "DomainMemoryResolutionError",
                "DomainMemorySelectionDecision",
                "DomainMemorySelectionDecisionCode",
                "DomainMemorySensitivityLevel",
                "DomainMemorySerializationError",
                "DomainMemoryTemporalKind",
                "DomainMemoryTemporalSnapshot",
                "DomainMemoryTraceSnapshot",
                "DomainMemoryValidationError",
                "DomainMemoryValidationCode",
                "DomainMemoryValidationResult",
                "DomainMemoryView",
                "DomainMemoryViewRequest",
                "DomainMemoryViewResolver",
                "DomainMemoryViewSnapshot",
            }
        )
        expected.update(
            {
                "DomainConflictAuthority",
                "DomainConflictCase",
                "DomainConflictKind",
                "DomainConflictReasonCode",
                "DomainConflictReference",
                "DomainConflictResolution",
                "DomainConflictResolutionContractError",
                "DomainConflictResolutionPolicy",
                "DomainConflictResolutionSerializationError",
                "DomainConflictResolver",
                "DomainConflictSeverity",
                "DomainConflictSourceKind",
                "DomainConflictStatus",
                "DomainConflictStrategy",
            }
        )
        expected.update(
            {
                "CANONICAL_DOMAIN_EVENTS",
                "CANONICAL_DOMAIN_EVENTS_SET",
                "DEFAULT_DOMAIN_EVENT_REGISTRY",
                "DomainEvent",
                "DomainEventContractError",
                "DomainEventDeclaration",
                "DomainEventError",
                "DomainEventFactory",
                "DomainEventPublicationError",
                "DomainEventReference",
                "DomainEventRegistry",
                "DomainEventRegistryError",
                "DomainEventSerializationError",
                "DomainEventValidationError",
                "DomainKernelEventPublisher",
                "DomainLifecycleEventBridge",
                "adapt_approval_received",
                "adapt_approval_requested",
                "adapt_composition_created",
                "adapt_composition_updated",
                "adapt_conflict_detected",
                "adapt_conflict_resolution",
                "adapt_execution_completed",
                "adapt_execution_failed",
                "adapt_execution_started",
                "adapt_memory_proposed",
                "adapt_memory_updated",
                "adapt_operation_completed",
                "adapt_operation_failed",
                "adapt_operation_started",
                "adapt_permission_denied",
                "adapt_permission_requested",
                "adapt_resolution_result",
                "adapt_resolution_started",
                "adapt_workflow_completed",
                "adapt_workflow_paused",
                "adapt_workflow_resumed",
                "adapt_workflow_started",
                "get_canonical_domain_namespace",
                "is_canonical_general_event",
                "validate_event_type_syntax",
                "validate_specialized_event_namespace",
            }
        )
        expected.update(
            {
                "DOMAIN_SESSION_EXTENSION_KEY",
                "DOMAIN_SESSION_SCHEMA_VERSION",
                "DomainSessionCheck",
                "DomainSessionCheckStatus",
                "DomainSessionCodec",
                "DomainSessionContext",
                "DomainSessionContractError",
                "DomainSessionError",
                "DomainSessionResumeError",
                "DomainSessionResumeRequest",
                "DomainSessionResumeResult",
                "DomainSessionResumeStatus",
                "DomainSessionRevalidationError",
                "DomainSessionResumer",
                "DomainSessionSecurityError",
                "DomainSessionSerializationError",
                "DomainSessionTransition",
                "DomainWorkflowClassification",
                "revalidate_domains",
                "revalidate_resource_and_knowledge_drift",
                "revalidate_session_state",
                "revalidate_temporal",
                "revalidate_workflows",
            }
        )
        # Phase 10.36 – Domain API public coordination facade
        expected.update(
            {
                "DefaultDomainAPI",
                "DomainAPI",
            }
        )
        # Phase 10.37 – Domain Observability read-only projection
        expected.update(
            {
                "CANONICAL_DOMAIN_OBSERVABILITY_METRICS",
                "DomainHealthChecker",
                "DomainHealthFinding",
                "DomainHealthResult",
                "DomainHealthStatus",
                "DomainMetricBucket",
                "DomainMetricMeasurement",
                "DomainMetricStatus",
                "DomainMetricsCalculator",
                "DomainMetricsSnapshot",
                "DomainObservabilityEvidence",
                "DomainObservabilityLogEntry",
                "DomainObservabilityReport",
                "DomainObservabilityService",
                "InvalidDomainObservabilityContractError",
                "InvalidDomainObservabilityEvidenceError",
            }
        )
        # Phase 10.38 – Domain Trust (restrictive authority boundary)
        expected.update(
            {
                "DomainTrustDecision",
                "DomainTrustLevel",
                "DomainTrustPolicy",
                "evaluate_domain_trust",
            }
        )
        # Phase 10.42 – Domain Planner/Workflow Integration coordination boundary
        expected.update(
            {
                "DefaultDomainPlannerWorkflowIntegrator",
                "DomainPlannerWorkflowIntegrationRequest",
                "DomainPlannerWorkflowIntegrationResult",
                "DomainPlannerWorkflowIntegrator",
                "DomainPlanningCapabilityView",
            }
        )
        # Phase 10.43 – Domain Validation System integration (thin bindings)
        expected.update(
            {
                "CROSS_DOMAIN_EXECUTION_POLICY_NAME",
                "DOMAIN_OPERATION_POLICY_NAME",
                "DOMAIN_PACK_BASE_VALIDATION_IDS",
                "DOMAIN_PACK_INSTALLATION_POLICY_NAME",
                "DOMAIN_PACK_UPDATE_POLICY_NAME",
                "DOMAIN_WORKFLOW_POLICY_NAME",
                "PROJECT_DOMAIN_CHANGE_POLICY_NAME",
                "DomainValidationIntegrationError",
                "build_cross_domain_execution_policy",
                "build_domain_operation_policy",
                "build_domain_pack_installation_policy",
                "build_domain_pack_update_policy",
                "build_domain_workflow_policy",
                "build_project_domain_change_policy",
                "compose_required_validation_ids",
                "compose_effective_validation_ids",
                "build_operation_validation_requirements",
                "domain_operation_requires_validation",
                "is_ignored_caller_validation_metadata",
                "is_project_domain_code_mutation",
                "project_change_requires_validation",
                "require_canonical_validation_success",
                "resolve_domain_operation_validation_requirements",
                "build_domain_workflow_operation_adapter",
                "OrchestratedCrossDomainOperationPort",
                "validate_domain_specialized_result",
                "ensure_domain_validation_allows_update",
            }
        )
        # Phase 10.44 – Domain Memory and Knowledge Graph Integration
        expected.update(
            {
                "DefaultDomainMemoryKnowledgeIntegrator",
                "DomainMemoryKnowledgeAuthorizationError",
                "DomainMemoryKnowledgeContractError",
                "DomainMemoryKnowledgeContradictionRef",
                "DomainMemoryKnowledgeIntegrationError",
                "DomainMemoryKnowledgeIntegrator",
                "DomainMemoryKnowledgeInventory",
                "DomainMemoryKnowledgePath",
                "DomainMemoryKnowledgePathHop",
                "DomainMemoryKnowledgeProjection",
                "DomainMemoryKnowledgeProjectionCapability",
                "DomainMemoryKnowledgeProjectionError",
                "DomainMemoryKnowledgeProjectionRequest",
                "DomainMemoryKnowledgeRelationRef",
                "DomainMemoryKnowledgeSerializationError",
                "FORBIDDEN_PAYLOAD_FIELDS",
            }
        )
        # Phase 10.45 – Domain Interface Integration projection/intent seam
        expected.update(
            {
                "ConversationalDomainView",
                "CrossDomainInterfaceView",
                "DefaultDomainInterfaceIntegrator",
                "DomainCenterDomainView",
                "DomainCenterView",
                "DomainInterfaceAuthorityError",
                "DomainInterfaceContractError",
                "DomainInterfaceIntegrationError",
                "DomainInterfaceIntegrator",
                "DomainInterfaceIntent",
                "DomainInterfaceIntentError",
                "DomainInterfaceIntentKind",
                "DomainInterfaceIntentResult",
                "DomainInterfaceProjection",
                "DomainInterfaceProjectionRequest",
                "DomainInterfaceReference",
                "DomainInterfaceSerializationError",
                "DomainInterfaceStatus",
                "DomainInterfaceViewKind",
                "DomainInterfaceVisibilityError",
                "DomainReviewCenterView",
                "DomainReviewItemView",
                "DomainSelectorView",
            }
        )
        assert set(cmm.domains.__all__) == expected

    def test_all_symbols_accessible_from_package(self) -> None:
        """All __all__ symbols should be accessible as attributes."""
        for name in cmm.domains.__all__:
            assert hasattr(cmm.domains, name), f"Missing symbol: {name}"

    def test_no_unexpected_symbols_in_package(self) -> None:
        """Ensure we have exactly the right number of public symbols."""
        assert len(cmm.domains.__all__) == 610

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


class TestPhase1038PublicSurface:
    """Phase 10.38 — trust contracts are exposed; internals are not."""

    def test_trust_contracts_exported(self) -> None:
        assert hasattr(cmm.domains, "DomainTrustLevel")
        assert hasattr(cmm.domains, "DomainTrustPolicy")
        assert hasattr(cmm.domains, "DomainTrustDecision")

    def test_pure_evaluator_exported(self) -> None:
        # Existing Domain conventions export comparable pure evaluators,
        # so evaluate_domain_trust is exported at the top level.
        from cmm.domains.trust_evaluator import evaluate_domain_trust

        assert cmm.domains.evaluate_domain_trust is evaluate_domain_trust
        assert "evaluate_domain_trust" in cmm.domains.__all__

    def test_trust_levels_in_all(self) -> None:
        assert "DomainTrustLevel" in cmm.domains.__all__
        assert "DomainTrustPolicy" in cmm.domains.__all__
        assert "DomainTrustDecision" in cmm.domains.__all__

    def test_internal_trust_helpers_not_exported(self) -> None:
        """Private trust internals must never be public."""
        forbidden_public = {
            "_denied_capabilities_for",
            "_CODE_EXECUTION_CAPABILITIES",
            "_EXTERNAL_ACCESS_CAPABILITIES",
            "_MEMORY_WRITE_CAPABILITIES",
            "_SENSITIVE_RESOURCE_CAPABILITIES",
            "_DESTRUCTIVE_OPERATION_CAPABILITIES",
            "evaluate_domain_trust_permission",
        }
        assert forbidden_public.isdisjoint(set(cmm.domains.__all__))


class TestPhase1038ImportSafety:
    """Fresh import must not discover, read, validate, or mutate anything."""

    def test_fresh_import_is_side_effect_free(self, tmp_path) -> None:
        import subprocess
        import sys
        from pathlib import Path

        before = sorted(p.name for p in Path(tmp_path).iterdir())
        code = (
            "import cmm.domains\n"
            "import cmm.domains.trust_contracts\n"
            "import cmm.domains.trust_evaluator\n"
            "print('OK')\n"
        )
        result = subprocess.run(
            [sys.executable, "-c", code],
            cwd=tmp_path,
            capture_output=True,
            text=True,
            check=False,
            env={"PYTHONDONTWRITEBYTECODE": "1", "PATH": "/usr/bin:/bin"},
        )
        assert result.returncode == 0, result.stderr
        assert "OK" in result.stdout
        after = sorted(p.name for p in Path(tmp_path).iterdir())
        assert after == before

    def test_import_creates_no_registry_state(self) -> None:
        assert not hasattr(cmm.domains, "_trust_registry")
        assert not hasattr(cmm.domains, "_trust_store")
        assert not hasattr(cmm.domains, "_security_engine")


class TestPhase1038NoParallelInfrastructure:
    """The Phase 10.38 production surface owns no parallel security infra."""

    def test_no_parallel_security_classes_in_production(self) -> None:
        import re
        from pathlib import Path

        forbidden = {
            "DomainSecurityEngine",
            "DomainSecurityRuntime",
            "DomainSecurityStore",
            "DomainSecurityRegistry",
            "DomainTrustStore",
            "DomainTrustRegistry",
            "DomainSecurityLoader",
            "DomainTrustLoader",
            "DomainSecurityEventBus",
            "DomainSecurityTraceStore",
        }
        pattern = re.compile(r"class\s+(" + "|".join(forbidden) + r")\b")
        production_files = sorted(Path("cmm/domains").glob("*.py"))
        for path in production_files:
            text = path.read_text(encoding="utf-8")
            assert not pattern.search(text), f"{path} declares parallel infra"

    def test_canonical_owners_still_imported(self) -> None:
        from cmm.domains.loader import DeclarativeDomainLoader
        from cmm.domains.permission_gate import DomainPermissionGate
        from cmm.domains.permission_resolution import DomainPermissionResolver
        from cmm.domains.validation import PipelineDomainValidator

        assert DeclarativeDomainLoader is not None
        assert PipelineDomainValidator is not None
        assert DomainPermissionResolver is not None
        assert DomainPermissionGate is not None
