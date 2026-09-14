"""Explicit acceptance that turns candidates into CMM-owned connections.

Detection is evidence, not authority: :meth:`ProviderOnboardingService.propose`
resolves the canonical endpoint from the provider manifest and records what
acceptance would do, without mutating the registry, storing secrets, or
building isolation profiles. Only :meth:`ProviderOnboardingService.accept`
persists a secret via the credential store (keeping only the returned ref),
builds a CMM-owned isolation profile for externally configured providers, and
registers the resulting :class:`ProviderConnection`.

Endpoint rule: the connection endpoint always comes from the canonical
manifest, never from candidate metadata, so decoy URLs observed during
detection can never become the connection target.

Status rule: no connection becomes ``CONNECTED`` until administrative auth
validation succeeds. Without a passing validator the status stays
``AUTH_REQUIRED``, or ``WARNING`` when the candidate carried an external
endpoint override.
"""

from __future__ import annotations

import os
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from kernel.llm.credential_store import CredentialStore
from kernel.llm.provider_candidates import ProviderCandidate
from kernel.llm.provider_connections import (
    BillingClass,
    ConnectionStatus,
    ProviderConnection,
    ProviderConnectionRegistry,
)
from kernel.llm.provider_manifests import ProviderManifestRegistry
from kernel.llm.subscription_profiles import SubscriptionProfileManager

Validator = Callable[["ConnectionProposal"], bool]


def _normalize_identifier(value: str, *, label: str) -> str:
    """Strip and lowercase an identifier; reject blank input."""
    normalized = value.strip().lower()
    if not normalized:
        raise ValueError(f"{label} cannot be empty")
    return normalized


def _coerce_dir(value: str | os.PathLike[str], *, label: str) -> Path:
    """Coerce a path-like input to a ``Path``; reject blanks."""
    if isinstance(value, (str, os.PathLike)):
        text = os.fspath(value).strip()
    else:
        raise TypeError(f"{label} must be a path")
    if not text:
        raise ValueError(f"{label} cannot be empty")
    return Path(text)


@dataclass(frozen=True, slots=True)
class ConnectionProposal:
    """Evidence record describing what acceptance would connect.

    A proposal is not state: it carries the manifest-resolved endpoint and
    the isolation requirement, but no credential material and no registry
    side effects.
    """

    provider_id: str
    display_name: str
    billing_class: BillingClass
    endpoint: str
    account: str = "main"
    source_home: str | None = None
    requires_isolation: bool = False

    def __post_init__(self) -> None:
        """Normalize identifiers and reject blank endpoints."""
        object.__setattr__(
            self,
            "provider_id",
            _normalize_identifier(self.provider_id, label="Provider id"),
        )
        if not self.display_name.strip():
            raise ValueError("display_name cannot be empty")
        object.__setattr__(self, "billing_class", BillingClass(self.billing_class))
        normalized_endpoint = self.endpoint.strip()
        if not normalized_endpoint:
            raise ValueError("endpoint cannot be empty")
        object.__setattr__(self, "endpoint", normalized_endpoint)
        object.__setattr__(
            self, "account", _normalize_identifier(self.account, label="Account")
        )
        if not isinstance(self.requires_isolation, bool):
            raise TypeError("requires_isolation must be a bool")


class ProviderOnboardingService:
    """Propose canonical endpoints; accept candidates into connections."""

    def __init__(
        self,
        *,
        connections: ProviderConnectionRegistry,
        manifests: ProviderManifestRegistry,
        credentials: CredentialStore,
        profiles: SubscriptionProfileManager,
        profiles_root: str | os.PathLike[str],
        validator: Validator | None = None,
    ) -> None:
        """Wire the service to registries, storage, and an optional validator."""
        if not isinstance(connections, ProviderConnectionRegistry):
            raise TypeError("connections must be a ProviderConnectionRegistry")
        if not isinstance(manifests, ProviderManifestRegistry):
            raise TypeError("manifests must be a ProviderManifestRegistry")
        if not isinstance(profiles, SubscriptionProfileManager):
            raise TypeError("profiles must be a SubscriptionProfileManager")
        if validator is not None and not callable(validator):
            raise TypeError("validator must be callable or None")
        self._connections = connections
        self._manifests = manifests
        self._credentials = credentials
        self._profiles = profiles
        self._profiles_root = _coerce_dir(profiles_root, label="Profiles root")
        self._validator = validator

    def propose(self, candidate: ProviderCandidate) -> ConnectionProposal:
        """Resolve the canonical endpoint; register nothing.

        Raises :class:`ValueError` for a provider with no manifest.
        """
        if not isinstance(candidate, ProviderCandidate):
            raise TypeError("candidate must be a ProviderCandidate")
        manifest = self._manifests.get(candidate.provider_id)
        if manifest is None:
            raise ValueError(f"unknown provider: {candidate.provider_id}")
        source_home: str | None = None
        for key, value in candidate.metadata:
            if key == "codex_home":
                source_home = value
        requires_isolation = bool(
            candidate.external_config_present
            or candidate.external_endpoint_override_present
        )
        return ConnectionProposal(
            provider_id=manifest.provider_id,
            display_name=manifest.display_name,
            billing_class=manifest.billing_class,
            endpoint=manifest.default_base_url,
            source_home=source_home,
            requires_isolation=requires_isolation,
        )

    def accept(
        self, proposal: ConnectionProposal, credential: str | None = None
    ) -> ProviderConnection:
        """Store secrets, build isolation, and register one connection."""
        if not isinstance(proposal, ConnectionProposal):
            raise TypeError("proposal must be a ConnectionProposal")
        credential_ref: str | None = None
        if credential is not None:
            credential_ref = self._credentials.put(
                proposal.provider_id, proposal.account, credential
            )
        isolation_profile_ref: str | None = None
        if proposal.requires_isolation and proposal.source_home is not None:
            target = self._profiles_root / proposal.provider_id
            outcome = self._profiles.create_codex_profile(proposal.source_home, target)
            if outcome.status == "ok":
                isolation_profile_ref = str(target)
        if proposal.requires_isolation:
            status = ConnectionStatus.WARNING
        else:
            status = ConnectionStatus.AUTH_REQUIRED
        if self._validator is not None and self._validator(proposal):
            status = ConnectionStatus.CONNECTED
        connection = ProviderConnection(
            connection_id=f"{proposal.provider_id}:{proposal.account}",
            provider_id=proposal.provider_id,
            display_name=proposal.display_name,
            billing_class=proposal.billing_class,
            credential_ref=credential_ref,
            endpoint=proposal.endpoint,
            isolation_profile_ref=isolation_profile_ref,
            status=status,
        )
        return self._connections.register(connection)
