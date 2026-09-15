"""Explicit acceptance that turns candidates into CMM-owned connections.

Detection is evidence, not authority: :meth:`ProviderOnboardingService.propose`
resolves the canonical endpoint from the provider manifest and records what
acceptance would do, without mutating the registry, storing secrets, or
building isolation profiles. Only :meth:`ProviderOnboardingService.accept`
persists a secret via the credential store (keeping only the returned ref),
builds a CMM-owned isolation profile for externally configured providers, and
registers the resulting :class:`ProviderConnection`.

Authority rule: onboarding resolves the provider through the canonical
:class:`~kernel.llm.provider_registry.ProviderRegistry` before anything else,
so neither a candidate nor a leftover manifest can authorize a provider the
authority does not hold. The manifest (provider-bound metadata) supplies only
transport/auth/billing defaults.

Endpoint rule: the connection endpoint always comes from the canonical
manifest, never from candidate metadata, so decoy URLs observed during
detection can never become the connection target.

Status rule: no connection becomes ``CONNECTED`` until administrative auth
validation succeeds. Without a passing validator the status stays
``AUTH_REQUIRED``, or ``WARNING`` when the candidate carried an external
endpoint override.

Isolation rule (MAJOR-03): when the proposal requires isolation, a successful
CMM-owned isolation outcome is a prerequisite for acceptance. Missing source
evidence, a failed profile build, or an unusable outcome raises
:class:`ProviderIsolationError` *before* any connection is registered, so a
passing validator can never promote an unisolated connection to ``CONNECTED``.

Commit rule (MAJOR-V2-02): this service owns no persistence of its own. When a
:class:`~kernel.llm.provider_state_coordinator.ProviderRegistryStateCoordinator`
is wired, registration is followed by
``coordinator.persist_connection_acceptance()`` — the one seam that captures,
saves and publishes the Provider Registry revision and audit log. A failed save
propagates into the acceptance compensation path below, and the service keeps
owning proposal creation, isolation preflight, credential creation, connection
construction/registration and compensation of operation-owned side effects.
"""

from __future__ import annotations

import os
import shutil
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from kernel.llm.credential_store import CredentialStore
from kernel.llm.exceptions import ProviderError
from kernel.llm.provider_candidates import ProviderCandidate
from kernel.llm.provider_connections import (
    BillingClass,
    ConnectionStatus,
    ProviderConnection,
    ProviderConnectionRegistry,
)
from kernel.llm.provider_manifests import ProviderManifestRegistry
from kernel.llm.provider_registry import ProviderRegistry
from kernel.llm.provider_state_coordinator import ProviderRegistryStateCoordinator
from kernel.llm.subscription_profiles import SubscriptionProfileManager

Validator = Callable[["ConnectionProposal"], bool]


class ProviderIsolationError(ProviderError):
    """A required CMM-owned isolation outcome could not be produced.

    Raised before registration: an isolation-required provider that cannot be
    isolated never becomes a connection, let alone ``CONNECTED``.
    """


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
        providers: ProviderRegistry,
        connections: ProviderConnectionRegistry,
        manifests: ProviderManifestRegistry,
        credentials: CredentialStore,
        profiles: SubscriptionProfileManager,
        profiles_root: str | os.PathLike[str],
        validator: Validator | None = None,
        state_coordinator: ProviderRegistryStateCoordinator | None = None,
    ) -> None:
        """Wire the service to registries, an optional validator, and the commit seam.

        ``state_coordinator`` (MAJOR-V2-02) owns revision/audit persistence:
        after a successful registration the coordinator captures and saves the
        coherent aggregate. Wiring one is optional — an ephemeral runtime
        accepts connections without durable state — but there is deliberately
        no second, service-local persistence configuration.
        """
        if not isinstance(providers, ProviderRegistry):
            raise TypeError("providers must be a ProviderRegistry")
        if not isinstance(connections, ProviderConnectionRegistry):
            raise TypeError("connections must be a ProviderConnectionRegistry")
        if not isinstance(manifests, ProviderManifestRegistry):
            raise TypeError("manifests must be a ProviderManifestRegistry")
        if not isinstance(profiles, SubscriptionProfileManager):
            raise TypeError("profiles must be a SubscriptionProfileManager")
        if validator is not None and not callable(validator):
            raise TypeError("validator must be callable or None")
        if state_coordinator is not None and not isinstance(
            state_coordinator, ProviderRegistryStateCoordinator
        ):
            raise TypeError(
                "state_coordinator must be a ProviderRegistryStateCoordinator"
            )
        self._providers = providers
        self._connections = connections
        self._manifests = manifests
        self._credentials = credentials
        self._profiles = profiles
        self._profiles_root = _coerce_dir(profiles_root, label="Profiles root")
        self._validator = validator
        self._state_coordinator = state_coordinator

    @property
    def revision(self) -> int:
        """Return the durable revision owned by the coordinator, or zero.

        The service keeps no revision of its own: without a coordinator there
        is no durable state to version, so this reports an ephemeral zero.
        """
        coordinator = self._state_coordinator
        return 0 if coordinator is None else coordinator.revision

    def propose(self, candidate: ProviderCandidate) -> ConnectionProposal:
        """Resolve the canonical endpoint; register nothing.

        Raises ``ProviderError`` for a provider absent from the canonical
        registry (metadata alone never authorizes onboarding) and
        :class:`ValueError` for a registered provider with no manifest.
        """
        if not isinstance(candidate, ProviderCandidate):
            raise TypeError("candidate must be a ProviderCandidate")
        self._providers.get(candidate.provider_id)
        manifest = self._manifests.get(candidate.provider_id)
        if manifest is None:
            raise ValueError(f"unknown provider: {candidate.provider_id}")
        # One normalized isolation input: detectors publish ``source_home``
        # (with ``source_home_kind`` as origin evidence), so onboarding has no
        # provider-specific extraction branch (MAJOR-03, spec §6.1).
        source_home: str | None = None
        for key, value in candidate.metadata:
            if key == "source_home":
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
        """Prepare isolation, store secrets, and register one connection.

        Atomic from the caller's perspective (MAJOR-04, spec §7): the
        connection identity is preflighted *before* any side effect, so a
        duplicate never overwrites an existing credential. If any step after
        the first side effect fails, only the side effects this call created
        are compensated — a newly written credential is deleted, a newly
        created CMM-owned profile is removed, and a newly registered
        connection is removed — while pre-existing state stays untouched. The
        persisted aggregate advances its revision only after every step
        succeeds.
        """
        if not isinstance(proposal, ConnectionProposal):
            raise TypeError("proposal must be a ConnectionProposal")
        connection_id = f"{proposal.provider_id}:{proposal.account}"
        # Preflight before any side effect: an existing identity is rejected
        # here, never after a credential or profile has been mutated.
        if self._connections.get(connection_id) is not None:
            raise ValueError(f"duplicate connection_id: {connection_id}")

        isolation_target: Path | None = None
        isolation_profile_ref: str | None = None
        credential_ref: str | None = None
        registered: ProviderConnection | None = None
        try:
            if proposal.requires_isolation:
                target = self._profiles_root / proposal.provider_id
                existed_before = target.exists()
                isolation_profile_ref = self._isolate(proposal)
                if not existed_before:
                    isolation_target = target
            if credential is not None:
                credential_ref = self._credentials.put(
                    proposal.provider_id, proposal.account, credential
                )
            if proposal.requires_isolation:
                status = ConnectionStatus.WARNING
            else:
                status = ConnectionStatus.AUTH_REQUIRED
            if self._validator is not None and self._validator(proposal):
                status = ConnectionStatus.CONNECTED
            connection = ProviderConnection(
                connection_id=connection_id,
                provider_id=proposal.provider_id,
                display_name=proposal.display_name,
                billing_class=proposal.billing_class,
                credential_ref=credential_ref,
                endpoint=proposal.endpoint,
                isolation_profile_ref=isolation_profile_ref,
                status=status,
            )
            registered = self._connections.register(connection)
            if self._state_coordinator is not None:
                self._state_coordinator.persist_connection_acceptance(registered)
            return registered
        except Exception:
            # Compensation path: undo only what this call created, then let the
            # original error propagate unchanged. A coordinator save failure
            # lands here too, so a failed commit never leaves runtime state
            # behind.
            if registered is not None:
                self._connections.remove(registered.connection_id)
            if credential_ref is not None:
                self._credentials.delete(credential_ref)
            if isolation_target is not None:
                shutil.rmtree(isolation_target, ignore_errors=True)
            raise

    def _isolate(self, proposal: ConnectionProposal) -> str:
        """Produce the CMM-owned isolation reference, or raise.

        Fail-closed rule (MAJOR-03, spec §6.2): missing source evidence, a
        non-``ok`` profile outcome, or an outcome without a target home all
        raise before the connection is registered. There is deliberately no
        path that continues with a warning connection instead.
        """
        if proposal.source_home is None:
            raise ProviderIsolationError(
                "isolation requires source evidence for provider: "
                f"{proposal.provider_id}"
            )
        target = self._profiles_root / proposal.provider_id
        outcome = self._profiles.create_profile(
            proposal.provider_id, proposal.source_home, target
        )
        if outcome.status != "ok" or outcome.target_home is None:
            raise ProviderIsolationError(
                "isolation profile was not produced for provider "
                f"{proposal.provider_id}: {outcome.status} ({outcome.detail})"
            )
        return str(outcome.target_home)
