"""Public LLM contracts for provider-independent multimodel execution."""

from kernel.llm.capabilities import ModelCapabilities, ProviderCapabilities
from kernel.llm.credential_store import (
    SERVICE_NAME,
    CredentialStore,
    InMemoryCredentialStore,
    MacOSKeychainCredentialStore,
    credential_ref,
)
from kernel.llm.exceptions import LLMError, ParserError, ProviderError
from kernel.llm.experimental_omniroute import (
    OMNIROUTE_API_KEY_ENV,
    OMNIROUTE_BASE_URL_ENV,
    OMNIROUTE_DEEPSEEK_V4_FLASH,
    OMNIROUTE_DEFAULT_BASE_URL,
    OMNIROUTE_PROVIDER_ID,
    register_experimental_omniroute,
)
from kernel.llm.first_wave_providers import (
    provider_spec_from_manifest,
    register_first_wave_manifests,
    register_first_wave_providers,
)
from kernel.llm.model_catalog import ModelCatalog, ModelSpec
from kernel.llm.model_discovery import (
    DiscoverableModelClient,
    ModelDiscoveryResult,
    discover_models,
)
from kernel.llm.model_ranking import ModelRankingPolicy, RankingStrategy
from kernel.llm.model_router import (
    ModelRouter,
    RejectedModel,
    RoutingCandidate,
    RoutingDecision,
)
from kernel.llm.model_routes import (
    CapabilityConfidence,
    ModelRoute,
    ModelRouteCatalog,
    RouteCapabilityState,
)
from kernel.llm.model_selection import (
    ModelRequirements,
    PrivacyPolicy,
    find_matching_models,
    model_matches_requirements,
    select_model,
)
from kernel.llm.models import LLMRequest, LLMResponse
from kernel.llm.openai_compatible_provider import OpenAICompatibleProvider
from kernel.llm.parser import OperationPlanParser
from kernel.llm.prompt import PromptBuilder
from kernel.llm.provider import LLMProvider
from kernel.llm.provider_candidates import CandidateRisk, ProviderCandidate
from kernel.llm.provider_connections import (
    BillingClass,
    ConnectionStatus,
    ProviderConnection,
    ProviderConnectionRegistry,
)
from kernel.llm.provider_detectors import (
    AntigravityDetector,
    ClaudeCodeDetector,
    CodexDetector,
    DetectorFailure,
    EnvironmentApiCredentialDetector,
    ProviderDetector,
    QwenTokenPlanDetector,
    default_approved_detectors,
    default_environment_detectors,
    detect_all,
)
from kernel.llm.provider_events import (
    MODEL_AVAILABLE,
    MODEL_CAPABILITIES_CHANGED,
    MODEL_DISCOVERED,
    MODEL_UNAVAILABLE,
    PROVIDER_CONNECTED,
    PROVIDER_DETECTED,
    PROVIDER_DISCONNECTED,
    PROVIDER_EVENT_NAMES,
    PROVIDER_VALIDATION_CHANGED,
    ModelRouteSnapshot,
    ProviderConnectionSnapshot,
    ProviderInventorySnapshot,
    RouteCapabilitySnapshot,
    build_inventory_snapshot,
    connection_snapshot_from_connection,
    connection_snapshot_from_proposal,
    route_snapshot_from_route,
)
from kernel.llm.provider_factory import ProviderFactory
from kernel.llm.provider_manifests import (
    FIRST_WAVE_AUTH_SCHEME,
    KNOWN_API_STYLES,
    ProviderManifest,
    ProviderManifestRegistry,
)
from kernel.llm.provider_onboarding import (
    ConnectionProposal,
    ProviderIsolationError,
    ProviderOnboardingService,
)
from kernel.llm.provider_registry import ProviderRegistry, ProviderSpec
from kernel.llm.provider_state import (
    SCHEMA_VERSION as PROVIDER_STATE_SCHEMA_VERSION,
)
from kernel.llm.provider_state import (
    ProviderRegistryAuditRecord,
    ProviderRegistryState,
    ProviderStateError,
    ProviderStateSchemaError,
    ProviderStateSerializationError,
)
from kernel.llm.provider_state_repository import (
    FileProviderRegistryStateRepository,
    InMemoryProviderRegistryStateRepository,
    ProviderRegistryStateRepository,
    RestoredProviderRegistryState,
    capture_provider_registry_state,
    restore_provider_registry_state,
)
from kernel.llm.subscription_profiles import (
    ANTIGRAVITY_PAYG_STRIP_ENV,
    CLAUDE_PAYG_STRIP_ENV,
    CodexAuthRequiredError,
    CodexProfileOutcome,
    SubscriptionProfileDescriptor,
    SubscriptionProfileManager,
    SubscriptionProfileOutcome,
    create_codex_profile,
)

__all__ = [
    "ANTIGRAVITY_PAYG_STRIP_ENV",
    "CLAUDE_PAYG_STRIP_ENV",
    "FIRST_WAVE_AUTH_SCHEME",
    "KNOWN_API_STYLES",
    "MODEL_AVAILABLE",
    "MODEL_CAPABILITIES_CHANGED",
    "MODEL_DISCOVERED",
    "MODEL_UNAVAILABLE",
    "OMNIROUTE_API_KEY_ENV",
    "OMNIROUTE_BASE_URL_ENV",
    "OMNIROUTE_DEEPSEEK_V4_FLASH",
    "OMNIROUTE_DEFAULT_BASE_URL",
    "OMNIROUTE_PROVIDER_ID",
    "PROVIDER_CONNECTED",
    "PROVIDER_DETECTED",
    "PROVIDER_DISCONNECTED",
    "PROVIDER_EVENT_NAMES",
    "PROVIDER_STATE_SCHEMA_VERSION",
    "PROVIDER_VALIDATION_CHANGED",
    "SERVICE_NAME",
    "AntigravityDetector",
    "BillingClass",
    "CandidateRisk",
    "CapabilityConfidence",
    "ClaudeCodeDetector",
    "CodexAuthRequiredError",
    "CodexDetector",
    "CodexProfileOutcome",
    "ConnectionProposal",
    "ConnectionStatus",
    "CredentialStore",
    "DetectorFailure",
    "DiscoverableModelClient",
    "EnvironmentApiCredentialDetector",
    "FileProviderRegistryStateRepository",
    "InMemoryCredentialStore",
    "InMemoryProviderRegistryStateRepository",
    "LLMError",
    "LLMProvider",
    "LLMRequest",
    "LLMResponse",
    "MacOSKeychainCredentialStore",
    "ModelCapabilities",
    "ModelCatalog",
    "ModelDiscoveryResult",
    "ModelRankingPolicy",
    "ModelRequirements",
    "ModelRoute",
    "ModelRouteCatalog",
    "ModelRouteSnapshot",
    "ModelRouter",
    "ModelSpec",
    "OpenAICompatibleProvider",
    "OperationPlanParser",
    "ParserError",
    "PrivacyPolicy",
    "PromptBuilder",
    "ProviderCandidate",
    "ProviderCapabilities",
    "ProviderConnection",
    "ProviderConnectionRegistry",
    "ProviderConnectionSnapshot",
    "ProviderDetector",
    "ProviderError",
    "ProviderFactory",
    "ProviderInventorySnapshot",
    "ProviderIsolationError",
    "ProviderManifest",
    "ProviderManifestRegistry",
    "ProviderOnboardingService",
    "ProviderRegistry",
    "ProviderRegistryAuditRecord",
    "ProviderRegistryState",
    "ProviderRegistryStateRepository",
    "ProviderSpec",
    "ProviderStateError",
    "ProviderStateSchemaError",
    "ProviderStateSerializationError",
    "QwenTokenPlanDetector",
    "RankingStrategy",
    "RejectedModel",
    "RestoredProviderRegistryState",
    "RouteCapabilitySnapshot",
    "RouteCapabilityState",
    "RoutingCandidate",
    "RoutingDecision",
    "SubscriptionProfileDescriptor",
    "SubscriptionProfileManager",
    "SubscriptionProfileOutcome",
    "build_inventory_snapshot",
    "capture_provider_registry_state",
    "connection_snapshot_from_connection",
    "connection_snapshot_from_proposal",
    "create_codex_profile",
    "credential_ref",
    "default_approved_detectors",
    "default_environment_detectors",
    "detect_all",
    "discover_models",
    "find_matching_models",
    "model_matches_requirements",
    "provider_spec_from_manifest",
    "register_experimental_omniroute",
    "register_first_wave_manifests",
    "register_first_wave_providers",
    "restore_provider_registry_state",
    "route_snapshot_from_route",
    "select_model",
]
