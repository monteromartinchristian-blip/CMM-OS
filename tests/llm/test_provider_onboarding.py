"""Hybrid provider onboarding tests (Plan 3 Task 5).

Detect is not connect: ``propose()`` resolves a canonical endpoint
and records what acceptance would do, while only ``accept()`` stores
secrets, builds isolation profiles, and mutates the registry.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path

import pytest

from kernel.llm.credential_store import InMemoryCredentialStore
from kernel.llm.first_wave_providers import (
    DEEPSEEK_BASE_URL,
    register_first_wave_manifests,
)
from kernel.llm.provider_candidates import CandidateRisk, ProviderCandidate
from kernel.llm.provider_connections import (
    BillingClass,
    ConnectionStatus,
    ProviderConnectionRegistry,
)
from kernel.llm.provider_manifests import (
    FIRST_WAVE_AUTH_SCHEME,
    ProviderManifest,
    ProviderManifestRegistry,
)
from kernel.llm.provider_onboarding import (
    ConnectionProposal,
    ProviderOnboardingService,
)
from kernel.llm.subscription_profiles import SubscriptionProfileManager

_DECOY_URL = "http://127.0.0.1:9999/v1"
_MARKER = "17841"
_CODEX_MANIFEST_URL = "https://api.openai.com/v1"
_SECRET = "sk-deepseek-test-secret-value"


def _service(
    tmp_path: Path,
    validator: Callable[[ConnectionProposal], bool] | None = None,
) -> tuple[ProviderOnboardingService, ProviderConnectionRegistry]:
    """Build a service wired to fresh registries and an in-memory store."""
    connections = ProviderConnectionRegistry()
    manifests = ProviderManifestRegistry()
    register_first_wave_manifests(manifests)
    manifests.register(
        ProviderManifest(
            provider_id="codex",
            display_name="Codex",
            billing_class=BillingClass.SUBSCRIPTION,
            default_base_url=_CODEX_MANIFEST_URL,
            auth_scheme=FIRST_WAVE_AUTH_SCHEME,
        )
    )
    service = ProviderOnboardingService(
        connections=connections,
        manifests=manifests,
        credentials=InMemoryCredentialStore(),
        profiles=SubscriptionProfileManager(),
        profiles_root=tmp_path / "cmm-profiles",
        validator=validator,
    )
    return service, connections


def _deepseek_candidate() -> ProviderCandidate:
    """API candidate carrying a decoy URL that must never become endpoint."""
    return ProviderCandidate(
        provider_id="deepseek",
        source="env-credential",
        detected=True,
        auth_available=True,
        external_config_present=False,
        external_endpoint_override_present=False,
        risks=(),
        metadata=(
            ("env_key", "DEEPSEEK_API_KEY"),
            ("evidence_url", _DECOY_URL),
        ),
    )


def _write_contaminated_source(source: Path) -> None:
    """Mirror a user Codex home with auth plus an override config."""
    source.mkdir(parents=True, exist_ok=True)
    (source / "auth.json").write_text(
        json.dumps({"openai_api_key": "sub-key"}), encoding="utf-8"
    )
    (source / "config.toml").write_text(
        f'model = "gpt-5"\nopenai_base_url = "http://127.0.0.1:{_MARKER}/v1"\n',
        encoding="utf-8",
    )


def _codex_candidate(source: Path) -> ProviderCandidate:
    """Subscription candidate flagged with an external endpoint override."""
    return ProviderCandidate(
        provider_id="codex",
        source="codex-home",
        detected=True,
        auth_available=True,
        external_config_present=True,
        external_endpoint_override_present=True,
        risks=(CandidateRisk.EXTERNAL_ENDPOINT_OVERRIDE,),
        metadata=(("codex_home", str(source)),),
    )


def test_proposal_is_frozen() -> None:
    """ConnectionProposal carries no mutators; it is evidence, not state."""
    proposal = ConnectionProposal(
        provider_id="deepseek",
        display_name="DeepSeek API",
        billing_class=BillingClass.PAYG,
        endpoint=DEEPSEEK_BASE_URL,
    )
    with pytest.raises(AttributeError):
        proposal.endpoint = _DECOY_URL  # type: ignore[misc]


def test_api_onboarding_stores_secret_and_uses_manifest_endpoint(
    tmp_path: Path,
) -> None:
    """DeepSeek secret lands in the store; endpoint is the manifest URL."""
    service, _ = _service(tmp_path)
    proposal = service.propose(_deepseek_candidate())

    assert proposal.endpoint == DEEPSEEK_BASE_URL
    assert proposal.endpoint != _DECOY_URL
    assert _DECOY_URL not in proposal.endpoint

    connection = service.accept(proposal, credential=_SECRET)

    assert connection.endpoint == DEEPSEEK_BASE_URL
    assert connection.credential_ref is not None
    assert connection.credential_ref.startswith("keychain://")
    assert "sk-" not in connection.credential_ref
    assert _SECRET not in connection.credential_ref
    assert _DECOY_URL not in connection.endpoint
    assert not hasattr(connection, "api_key")
    assert _SECRET not in repr(connection)


def test_contaminated_codex_onboarding_uses_isolation_profile(
    tmp_path: Path,
) -> None:
    """Override config stays behind; connection points at a CMM profile."""
    source = tmp_path / "user-codex"
    _write_contaminated_source(source)
    service, _ = _service(tmp_path)

    proposal = service.propose(_codex_candidate(source))
    connection = service.accept(proposal)

    assert connection.isolation_profile_ref is not None
    assert connection.endpoint == _CODEX_MANIFEST_URL
    assert _MARKER not in connection.endpoint
    assert _MARKER not in connection.isolation_profile_ref

    profile_home = Path(connection.isolation_profile_ref)
    assert profile_home != source
    assert (profile_home / "auth.json").is_file()
    assert not (profile_home / "config.toml").exists()
    hits = [
        path
        for path in sorted(profile_home.rglob("*"))
        if path.is_file() and _MARKER in path.read_text(encoding="utf-8")
    ]
    assert hits == []
    # Source home is evidence only: the override file is untouched.
    assert _MARKER in (source / "config.toml").read_text(encoding="utf-8")


def test_propose_registers_nothing_accept_registers_one(
    tmp_path: Path,
) -> None:
    """Explicit acceptance: propose() is pure, accept() registers exactly one."""
    service, registry = _service(tmp_path)
    candidate = _deepseek_candidate()

    assert registry.list() == ()
    assert registry.get("deepseek:main") is None

    proposal = service.propose(candidate)

    assert registry.list() == ()
    assert registry.get("deepseek:main") is None

    connection = service.accept(proposal, credential=_SECRET)

    assert registry.list() == (connection,)
    assert registry.get("deepseek:main") == connection


def test_status_without_validation_is_never_connected(tmp_path: Path) -> None:
    """No validation hook means AUTH_REQUIRED (or WARNING), never CONNECTED."""
    service, _ = _service(tmp_path)
    api_connection = service.accept(
        service.propose(_deepseek_candidate()), credential=_SECRET
    )
    assert api_connection.status == ConnectionStatus.AUTH_REQUIRED

    source = tmp_path / "user-codex"
    _write_contaminated_source(source)
    override_connection = service.accept(service.propose(_codex_candidate(source)))
    assert override_connection.status == ConnectionStatus.WARNING


def test_status_with_successful_validation_is_connected(
    tmp_path: Path,
) -> None:
    """A passing administrative validation promotes the status to CONNECTED."""
    service, _ = _service(tmp_path, validator=lambda proposal: True)
    connection = service.accept(
        service.propose(_deepseek_candidate()), credential=_SECRET
    )
    assert connection.status == ConnectionStatus.CONNECTED


def test_failed_validation_is_never_connected(tmp_path: Path) -> None:
    """A failing validation keeps the connection out of CONNECTED."""
    service, _ = _service(tmp_path, validator=lambda proposal: False)
    connection = service.accept(
        service.propose(_deepseek_candidate()), credential=_SECRET
    )
    assert connection.status != ConnectionStatus.CONNECTED
