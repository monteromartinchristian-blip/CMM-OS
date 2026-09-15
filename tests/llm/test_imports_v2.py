"""Import regression for the route-aware provider registry contracts."""

from __future__ import annotations

import ast
from pathlib import Path
from unittest.mock import patch

from kernel import llm
from kernel.llm import (
    ANTIGRAVITY_PAYG_STRIP_ENV,
    CLAUDE_PAYG_STRIP_ENV,
    FIRST_WAVE_AUTH_SCHEME,
    KNOWN_API_STYLES,
    PROVIDER_STATE_SCHEMA_VERSION,
    SERVICE_NAME,
    AntigravityDetector,
    BillingClass,
    CandidateRisk,
    CapabilityConfidence,
    ClaudeCodeDetector,
    CodexAuthRequiredError,
    CodexDetector,
    CodexProfileOutcome,
    ConnectionProposal,
    ConnectionStatus,
    CredentialStore,
    DetectorFailure,
    DiscoverableModelClient,
    EnvironmentApiCredentialDetector,
    FileProviderRegistryStateRepository,
    InMemoryCredentialStore,
    InMemoryProviderRegistryStateRepository,
    MacOSKeychainCredentialStore,
    ModelDiscoveryResult,
    ModelRoute,
    ModelRouteCatalog,
    ProviderCandidate,
    ProviderConnection,
    ProviderConnectionRegistry,
    ProviderDetector,
    ProviderIsolationError,
    ProviderManifest,
    ProviderManifestRegistry,
    ProviderOnboardingService,
    ProviderRegistryAuditRecord,
    ProviderRegistryState,
    ProviderRegistryStateCoordinator,
    ProviderRegistryStateRepository,
    ProviderStateCoherenceError,
    ProviderStateError,
    ProviderStateSchemaError,
    ProviderStateSerializationError,
    QwenTokenPlanDetector,
    RestoredProviderRegistryState,
    RouteCapabilityState,
    SubscriptionProfileDescriptor,
    SubscriptionProfileManager,
    SubscriptionProfileOutcome,
    capture_provider_registry_state,
    create_codex_profile,
    credential_ref,
    default_approved_detectors,
    default_environment_detectors,
    detect_all,
    discover_models,
    provider_spec_from_manifest,
    register_first_wave_manifests,
    register_first_wave_providers,
    register_subscription_bridge_providers,
    restore_provider_registry_state,
)
from kernel.llm.credential_store import InMemoryCredentialStore as _MemStore
from kernel.llm.first_wave_providers import (
    register_first_wave_manifests as _register_first_wave,
)
from kernel.llm.provider import LLMProvider
from kernel.llm.provider_connections import (
    ProviderConnectionRegistry as _Connections,
)
from kernel.llm.provider_detectors import (
    default_approved_detectors as _default_detectors,
)
from kernel.llm.provider_detectors import detect_all as _detect_all
from kernel.llm.provider_manifests import ProviderManifestRegistry as _Manifests
from kernel.llm.provider_onboarding import ProviderOnboardingService as _Onboarding
from kernel.llm.provider_registry import ProviderRegistry as _Providers
from kernel.llm.provider_state import SCHEMA_VERSION as _STATE_SCHEMA_VERSION
from kernel.llm.subscription_profiles import SubscriptionProfileManager as _Profiles

REGISTRY_CONTRACTS = {
    "BillingClass": BillingClass,
    "ConnectionStatus": ConnectionStatus,
    "ProviderConnection": ProviderConnection,
    "ProviderConnectionRegistry": ProviderConnectionRegistry,
    "CapabilityConfidence": CapabilityConfidence,
    "RouteCapabilityState": RouteCapabilityState,
    "ModelRoute": ModelRoute,
    "ModelRouteCatalog": ModelRouteCatalog,
}

DISCOVERY_CONTRACTS = {
    "FIRST_WAVE_AUTH_SCHEME": FIRST_WAVE_AUTH_SCHEME,
    "KNOWN_API_STYLES": KNOWN_API_STYLES,
    "ProviderManifest": ProviderManifest,
    "ProviderManifestRegistry": ProviderManifestRegistry,
    "register_first_wave_manifests": register_first_wave_manifests,
    "register_first_wave_providers": register_first_wave_providers,
    "register_subscription_bridge_providers": register_subscription_bridge_providers,
    "provider_spec_from_manifest": provider_spec_from_manifest,
    "DiscoverableModelClient": DiscoverableModelClient,
    "ModelDiscoveryResult": ModelDiscoveryResult,
    "discover_models": discover_models,
}


def test_registry_contracts_are_importable() -> None:
    for name in REGISTRY_CONTRACTS:
        assert getattr(llm, name) is not None


def test_registry_contracts_are_public() -> None:
    expected = set(REGISTRY_CONTRACTS)

    assert expected <= set(llm.__all__)


def test_discovery_contracts_are_importable() -> None:
    for name in DISCOVERY_CONTRACTS:
        assert getattr(llm, name) is not None


def test_discovery_contracts_are_public() -> None:
    expected = set(DISCOVERY_CONTRACTS)

    assert expected <= set(llm.__all__)


HYBRID_CONTRACTS = {
    "CandidateRisk": CandidateRisk,
    "ProviderCandidate": ProviderCandidate,
    "ProviderDetector": ProviderDetector,
    "DetectorFailure": DetectorFailure,
    "detect_all": detect_all,
    "CodexDetector": CodexDetector,
    "ClaudeCodeDetector": ClaudeCodeDetector,
    "AntigravityDetector": AntigravityDetector,
    "QwenTokenPlanDetector": QwenTokenPlanDetector,
    "EnvironmentApiCredentialDetector": EnvironmentApiCredentialDetector,
    "default_environment_detectors": default_environment_detectors,
    "default_approved_detectors": default_approved_detectors,
    "CredentialStore": CredentialStore,
    "InMemoryCredentialStore": InMemoryCredentialStore,
    "MacOSKeychainCredentialStore": MacOSKeychainCredentialStore,
    "SERVICE_NAME": SERVICE_NAME,
    "credential_ref": credential_ref,
    "SubscriptionProfileManager": SubscriptionProfileManager,
    "SubscriptionProfileDescriptor": SubscriptionProfileDescriptor,
    "SubscriptionProfileOutcome": SubscriptionProfileOutcome,
    "CodexProfileOutcome": CodexProfileOutcome,
    "CodexAuthRequiredError": CodexAuthRequiredError,
    "create_codex_profile": create_codex_profile,
    "CLAUDE_PAYG_STRIP_ENV": CLAUDE_PAYG_STRIP_ENV,
    "ANTIGRAVITY_PAYG_STRIP_ENV": ANTIGRAVITY_PAYG_STRIP_ENV,
    "ConnectionProposal": ConnectionProposal,
    "ProviderIsolationError": ProviderIsolationError,
    "ProviderOnboardingService": ProviderOnboardingService,
}


STATE_CONTRACTS = {
    "PROVIDER_STATE_SCHEMA_VERSION": PROVIDER_STATE_SCHEMA_VERSION,
    "ProviderRegistryAuditRecord": ProviderRegistryAuditRecord,
    "ProviderRegistryState": ProviderRegistryState,
    "ProviderRegistryStateCoordinator": ProviderRegistryStateCoordinator,
    "ProviderStateCoherenceError": ProviderStateCoherenceError,
    "ProviderStateError": ProviderStateError,
    "ProviderStateSchemaError": ProviderStateSchemaError,
    "ProviderStateSerializationError": ProviderStateSerializationError,
    "FileProviderRegistryStateRepository": FileProviderRegistryStateRepository,
    "InMemoryProviderRegistryStateRepository": (
        InMemoryProviderRegistryStateRepository
    ),
    "ProviderRegistryStateRepository": ProviderRegistryStateRepository,
    "RestoredProviderRegistryState": RestoredProviderRegistryState,
    "capture_provider_registry_state": capture_provider_registry_state,
    "restore_provider_registry_state": restore_provider_registry_state,
}


def test_state_contracts_are_importable() -> None:
    for name in STATE_CONTRACTS:
        assert getattr(llm, name) is not None


def test_state_contracts_are_public() -> None:
    expected = set(STATE_CONTRACTS)

    assert expected <= set(llm.__all__)
    # The public alias must expose the module's own schema version, so a
    # consumer can never read a stale copy of the persisted contract.
    assert PROVIDER_STATE_SCHEMA_VERSION == _STATE_SCHEMA_VERSION


def test_hybrid_contracts_are_importable() -> None:
    for name in HYBRID_CONTRACTS:
        assert getattr(llm, name) is not None


def test_hybrid_contracts_are_public() -> None:
    expected = set(HYBRID_CONTRACTS)

    assert expected <= set(llm.__all__)


HYBRID_ADMIN_MODULES = (
    "kernel/llm/provider_candidates.py",
    "kernel/llm/provider_detectors.py",
    "kernel/llm/credential_store.py",
    "kernel/llm/subscription_profiles.py",
    "kernel/llm/provider_onboarding.py",
    "kernel/llm/provider_state_coordinator.py",
)

_FORBIDDEN_INFERENCE_CALLS = frozenset(
    {
        "generate",
        "chat",
        "complete",
        "embed",
        "infer",
        "generate_text",
        "create_completion",
    }
)

_FORBIDDEN_INFERENCE_IMPORTS = frozenset(
    {
        "openai",
        "anthropic",
        "torch",
        "transformers",
        "diffusers",
        "litellm",
        "ollama",
        "google",
    }
)


def _called_names(tree: ast.AST) -> set[str]:
    names: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if isinstance(func, ast.Name):
            names.add(func.id)
        elif isinstance(func, ast.Attribute):
            names.add(func.attr)
    return names


def _imported_roots(tree: ast.AST) -> set[str]:
    roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                roots.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom) and node.module:
            roots.add(node.module.split(".")[0])
    return roots


def test_hybrid_admin_paths_have_no_inference_calls() -> None:
    """Static audit: no model-generation call lives in Task 1-5 modules."""
    repo_root = Path(__file__).resolve().parents[2]
    violations: list[str] = []
    for rel in HYBRID_ADMIN_MODULES:
        tree = ast.parse((repo_root / rel).read_text(encoding="utf-8"))
        hits = _called_names(tree) & _FORBIDDEN_INFERENCE_CALLS
        if hits:
            violations.append(f"{rel}: {sorted(hits)}")
    assert violations == [], f"inference calls in admin paths: {violations}"


def test_hybrid_admin_paths_have_no_inference_imports() -> None:
    """Static audit: Task 1-5 modules import no model-inference libraries."""
    repo_root = Path(__file__).resolve().parents[2]
    violations: list[str] = []
    for rel in HYBRID_ADMIN_MODULES:
        tree = ast.parse((repo_root / rel).read_text(encoding="utf-8"))
        hits = _imported_roots(tree) & _FORBIDDEN_INFERENCE_IMPORTS
        if hits:
            violations.append(f"{rel}: {sorted(hits)}")
    assert violations == [], f"inference imports in admin paths: {violations}"


def test_detection_and_onboarding_invoke_zero_inference(tmp_path: Path) -> None:
    """Dynamic audit: the full administrative flow never calls generate()."""

    def _boom(*args: object, **kwargs: object) -> object:
        raise AssertionError("inference path invoked during admin flow")

    providers = _Providers()
    connections = _Connections(providers)
    manifests = _Manifests(providers)
    _register_first_wave(manifests)
    service = _Onboarding(
        providers=providers,
        connections=connections,
        manifests=manifests,
        credentials=_MemStore(),
        profiles=_Profiles(),
        profiles_root=tmp_path / "cmm-profiles",
    )
    detectors = _default_detectors(env={"DEEPSEEK_API_KEY": "placeholder"})
    seen_failures: list[object] = []
    with patch.object(LLMProvider, "generate", _boom):
        candidates = _detect_all(detectors, on_error=seen_failures.append)
        assert seen_failures == []
        assert candidates, "expected at least one detected candidate"
        proposal = service.propose(candidates[0])
        service.accept(proposal, credential="placeholder-secret")
    assert len(connections.list()) == 1
