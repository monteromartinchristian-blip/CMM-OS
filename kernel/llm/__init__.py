"""Public LLM contracts for provider-independent multimodel execution."""

from kernel.llm.capabilities import ModelCapabilities, ProviderCapabilities
from kernel.llm.exceptions import LLMError, ParserError, ProviderError
from kernel.llm.experimental_omniroute import (
    OMNIROUTE_API_KEY_ENV,
    OMNIROUTE_BASE_URL_ENV,
    OMNIROUTE_DEEPSEEK_V4_FLASH,
    OMNIROUTE_DEFAULT_BASE_URL,
    OMNIROUTE_PROVIDER_ID,
    register_experimental_omniroute,
)
from kernel.llm.first_wave_providers import register_first_wave_manifests
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
from kernel.llm.provider_connections import (
    BillingClass,
    ConnectionStatus,
    ProviderConnection,
    ProviderConnectionRegistry,
)
from kernel.llm.provider_factory import ProviderFactory
from kernel.llm.provider_manifests import (
    FIRST_WAVE_AUTH_SCHEME,
    KNOWN_API_STYLES,
    ProviderManifest,
    ProviderManifestRegistry,
)
from kernel.llm.provider_registry import ProviderRegistry, ProviderSpec

__all__ = [
    "FIRST_WAVE_AUTH_SCHEME",
    "KNOWN_API_STYLES",
    "OMNIROUTE_API_KEY_ENV",
    "OMNIROUTE_BASE_URL_ENV",
    "OMNIROUTE_DEEPSEEK_V4_FLASH",
    "OMNIROUTE_DEFAULT_BASE_URL",
    "OMNIROUTE_PROVIDER_ID",
    "BillingClass",
    "CapabilityConfidence",
    "ConnectionStatus",
    "DiscoverableModelClient",
    "LLMError",
    "LLMProvider",
    "LLMRequest",
    "LLMResponse",
    "ModelCapabilities",
    "ModelCatalog",
    "ModelDiscoveryResult",
    "ModelRankingPolicy",
    "ModelRequirements",
    "ModelRoute",
    "ModelRouteCatalog",
    "ModelRouter",
    "ModelSpec",
    "OpenAICompatibleProvider",
    "OperationPlanParser",
    "ParserError",
    "PrivacyPolicy",
    "PromptBuilder",
    "ProviderCapabilities",
    "ProviderConnection",
    "ProviderConnectionRegistry",
    "ProviderError",
    "ProviderFactory",
    "ProviderManifest",
    "ProviderManifestRegistry",
    "ProviderRegistry",
    "ProviderSpec",
    "RankingStrategy",
    "RejectedModel",
    "RouteCapabilityState",
    "RoutingCandidate",
    "RoutingDecision",
    "discover_models",
    "find_matching_models",
    "model_matches_requirements",
    "register_experimental_omniroute",
    "register_first_wave_manifests",
    "select_model",
]
