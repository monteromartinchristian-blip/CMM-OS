"""Local-first persistence for the Provider Registry aggregate (MAJOR-02).

One focused persistence contract for the Phase 11.34 aggregate — not another
provider registry, and not a general storage framework. Three pieces:

* :class:`ProviderRegistryStateRepository` — the two-method protocol
  (``load``/``save``) every backend honors;
* :class:`InMemoryProviderRegistryStateRepository` — the official in-memory
  backend for tests and ephemeral runtimes;
* :class:`FileProviderRegistryStateRepository` — the durable backend: one
  deterministic UTF-8 JSON document written with a same-directory temporary
  file, an explicit ``fsync``, and :func:`os.replace` for the atomic swap, so
  a crash or a failed replace leaves the previous durable state byte-for-byte
  intact.

Reconstruction is separate from storage: :func:`capture_provider_registry_state`
reads the live canonical components and
:func:`restore_provider_registry_state` rebuilds them in dependency order
(providers → manifests → models → connections → routes). Referential failures
are never caught and downgraded — an orphan connection, model, manifest or
route rejects the whole restore instead of exposing a partial aggregate.

Secret boundary: persisted bytes carry only opaque ``credential_ref`` values.
The credential store remains the only owner of secret material, and the state
envelope's own guards reject any secret-shaped ref or audit detail before it
reaches disk.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, runtime_checkable

from kernel.llm.model_catalog import ModelCatalog
from kernel.llm.model_routes import ModelRouteCatalog
from kernel.llm.provider_connections import ProviderConnectionRegistry
from kernel.llm.provider_manifests import ProviderManifestRegistry
from kernel.llm.provider_registry import ProviderRegistry
from kernel.llm.provider_state import (
    SCHEMA_VERSION,
    ProviderRegistryAuditRecord,
    ProviderRegistryState,
    ProviderStateCoherenceError,
    ProviderStateSerializationError,
)

_JSON_KWARGS: dict[str, object] = {
    "ensure_ascii": False,
    "indent": 2,
    "sort_keys": True,
}


@runtime_checkable
class ProviderRegistryStateRepository(Protocol):
    """Persistence boundary for the Provider Registry aggregate."""

    def load(self) -> ProviderRegistryState | None:
        """Return the persisted state, or ``None`` when nothing is stored."""
        ...

    def save(self, state: ProviderRegistryState) -> None:
        """Persist ``state``, replacing any previous document atomically."""
        ...


def _require_state(value: object, *, label: str) -> ProviderRegistryState:
    """Reject anything that is not a state envelope before touching storage."""
    if not isinstance(value, ProviderRegistryState):
        raise TypeError(f"{label} must be a ProviderRegistryState")
    return value


class InMemoryProviderRegistryStateRepository:
    """In-memory backend holding the exact state object it was given."""

    def __init__(self) -> None:
        """Create an empty repository."""
        self._state: ProviderRegistryState | None = None

    def load(self) -> ProviderRegistryState | None:
        """Return the stored state, or ``None`` before the first save."""
        return self._state

    def save(self, state: ProviderRegistryState) -> None:
        """Store ``state``; the envelope is immutable, so no copy is needed."""
        self._state = _require_state(state, label="state")


def _document(state: ProviderRegistryState) -> str:
    """Render the envelope as deterministic, newline-terminated JSON text."""
    return json.dumps(state.to_dict(), **_JSON_KWARGS) + "\n"


class FileProviderRegistryStateRepository:
    """Durable backend: one deterministic JSON document with atomic replace."""

    def __init__(self, path: str | os.PathLike[str]) -> None:
        """Bind the repository to the document path it owns."""
        if not isinstance(path, (str, os.PathLike)):
            raise TypeError("path must be a path")
        text = os.fspath(path).strip()
        if not text:
            raise ValueError("path cannot be empty")
        self._path = Path(text)

    @property
    def path(self) -> Path:
        """Return the document path this repository owns."""
        return self._path

    def load(self) -> ProviderRegistryState | None:
        """Read and validate the document; absence is not an error.

        A malformed document, an unsupported schema version or an invalid field
        raises instead of returning partial state.
        """
        try:
            text = self._path.read_text(encoding="utf-8")
        except FileNotFoundError:
            return None
        try:
            payload = json.loads(text)
        except json.JSONDecodeError as error:
            raise ProviderStateSerializationError(
                f"provider registry state is not valid JSON: {self._path.name}"
            ) from error
        return ProviderRegistryState.from_dict(payload)

    def save(self, state: ProviderRegistryState) -> None:
        """Write the document atomically; a failed swap leaves it untouched.

        The temporary file lives in the same directory as the target so the
        final :func:`os.replace` is a same-filesystem rename. If anything after
        the temporary file is created fails, the temporary file is removed
        best-effort and the original document stays intact.
        """
        document = _document(_require_state(state, label="state"))
        path = self._path
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_name(f"{path.name}.tmp")
        try:
            with temporary.open("w", encoding="utf-8", newline="\n") as handle:
                handle.write(document)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, path)
        except Exception:
            _remove_quietly(temporary)
            raise


def _remove_quietly(path: Path) -> None:
    """Best-effort removal of a temporary artifact; never mask the real error."""
    try:
        path.unlink()
    except FileNotFoundError:
        return
    except OSError:
        return


@dataclass(frozen=True, slots=True)
class RestoredProviderRegistryState:
    """Canonical runtime components rebuilt from one persisted aggregate."""

    providers: ProviderRegistry
    manifests: ProviderManifestRegistry
    models: ModelCatalog
    connections: ProviderConnectionRegistry
    routes: ModelRouteCatalog
    revision: int
    audit_log: tuple[ProviderRegistryAuditRecord, ...]


def capture_provider_registry_state(
    providers: ProviderRegistry,
    manifests: ProviderManifestRegistry,
    models: ModelCatalog,
    connections: ProviderConnectionRegistry,
    routes: ModelRouteCatalog,
    *,
    revision: int,
    audit_log: tuple[ProviderRegistryAuditRecord, ...] = (),
) -> ProviderRegistryState:
    """Read the live canonical components into one aggregate envelope.

    Every component is read through its own public enumeration, and every
    component is type-checked first so a caller cannot silently capture a
    partially wired graph. Manifest enumeration is active-only
    (``ProviderManifestRegistry.list()`` drops metadata whose canonical
    provider identity is gone or was replaced), so an orphan manifest cannot
    normally reach this function at all.

    Coherence guard (MAJOR-V2-01): because "normally" is not a guarantee,
    capture then rejects *any* enumerated manifest whose provider id is absent
    from the providers being captured, raising
    :class:`~kernel.llm.provider_state.ProviderStateCoherenceError`. The
    behavior choice is deterministic and documented: metadata without a
    canonical provider is an error, never a silent omission, and no state
    envelope is produced — so a captured aggregate is always one that
    :func:`restore_provider_registry_state` can rebuild.
    """
    if not isinstance(providers, ProviderRegistry):
        raise TypeError("providers must be a ProviderRegistry")
    if not isinstance(manifests, ProviderManifestRegistry):
        raise TypeError("manifests must be a ProviderManifestRegistry")
    if not isinstance(models, ModelCatalog):
        raise TypeError("models must be a ModelCatalog")
    if not isinstance(connections, ProviderConnectionRegistry):
        raise TypeError("connections must be a ProviderConnectionRegistry")
    if not isinstance(routes, ModelRouteCatalog):
        raise TypeError("routes must be a ModelRouteCatalog")
    provider_specs = providers.list()
    active_manifests = manifests.list()
    canonical_provider_ids = {spec.id for spec in provider_specs}
    orphans = sorted(
        manifest.provider_id
        for manifest in active_manifests
        if manifest.provider_id not in canonical_provider_ids
    )
    if orphans:
        raise ProviderStateCoherenceError(
            "manifest metadata without canonical provider identity: " + orphans[0]
        )
    return ProviderRegistryState(
        schema_version=SCHEMA_VERSION,
        revision=revision,
        providers=provider_specs,
        manifests=active_manifests,
        models=models.list(),
        connections=connections.list(),
        routes=routes.list(),
        audit_log=tuple(audit_log),
    )


def restore_provider_registry_state(
    state: ProviderRegistryState,
) -> RestoredProviderRegistryState:
    """Rebuild the canonical component graph from one aggregate envelope.

    Dependency order is mandatory and matches ``ProviderRegistry`` →
    ``ProviderManifestRegistry`` → ``ModelCatalog`` →
    ``ProviderConnectionRegistry`` → ``ModelRouteCatalog``, because each
    component resolves its dependencies through the previous one. Routes are
    inserted with ``restore()`` rather than ``register()`` so a restart never
    rewrites availability or timestamps.

    Raises the underlying referential error (``ProviderError`` for an orphan
    provider, ``ValueError`` for an orphan connection) and returns nothing in
    that case — a partially rebuilt aggregate is never handed to a caller.
    """
    if not isinstance(state, ProviderRegistryState):
        raise TypeError("state must be a ProviderRegistryState")

    providers = ProviderRegistry()
    for spec in state.providers:
        providers.register(spec)

    manifests = ProviderManifestRegistry(providers)
    for manifest in state.manifests:
        manifests.register(manifest)

    models = ModelCatalog(providers)
    for spec in state.models:
        models.register(spec)

    connections = ProviderConnectionRegistry(providers)
    for connection in state.connections:
        connections.register(connection)

    routes = ModelRouteCatalog(connections)
    for route in state.routes:
        routes.restore(route)

    return RestoredProviderRegistryState(
        providers=providers,
        manifests=manifests,
        models=models,
        connections=connections,
        routes=routes,
        revision=state.revision,
        audit_log=state.audit_log,
    )
