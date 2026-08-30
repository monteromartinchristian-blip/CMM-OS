"""Phase 10.34 V3 — Domain Session Shared Persistence Adapter (BLOCKER-02).

Narrow adapter binding Domain Sessions to the real shared session
infrastructure owned by ``cmm.runtime`` (``SessionStore`` /
``SharedSessionState``).

Architecture (dependency direction is mandatory):

    cmm.runtime (shared session infrastructure — generic, no domain knowledge)
            ↑
    cmm.domains.session_persistence (this adapter)
            ↑
    cmm.domains.session_resumer

No independent ``DomainSessionRepository`` is created: the shared session
store remains the single persistence authority, and domain sessions travel
inside the generic ``extensions`` surface under the canonical
``domain_session`` key.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from cmm.domains.errors import DomainSessionSerializationError
from cmm.domains.session_codec import DOMAIN_SESSION_EXTENSION_KEY
from cmm.domains.session_contracts import DomainSessionContext
from cmm.runtime.sessions import SessionStore

if TYPE_CHECKING:
    from cmm.runtime.sessions import SharedSessionState

__all__ = [
    "DOMAIN_SESSION_EXTENSION_KEY",
    "SharedSessionDomainAdapter",
]


class SharedSessionDomainAdapter:
    """Loads/saves DomainSessionContext through the shared session store.

    The shared ``SessionStore`` is the authoritative persistence boundary;
    this adapter only translates between the generic shared envelope and the
    typed domain extension. All durability/atomicity/revision semantics are
    owned by the shared store.
    """

    def __init__(
        self, store: SessionStore, extension_key: str = DOMAIN_SESSION_EXTENSION_KEY
    ) -> None:
        if store is None:
            raise ValueError("store (shared SessionStore) is required")
        for required in ("load", "save"):
            if not callable(getattr(store, required, None)):
                raise TypeError(f"store must implement {required}()")
        self._store = store
        self._extension_key = extension_key

    @property
    def store(self) -> SessionStore:
        return self._store

    @property
    def extension_key(self) -> str:
        return self._extension_key

    def load_shared_session(self, session_id: str) -> SharedSessionState | None:
        """Load the raw shared session state by ID."""
        return self._store.load(session_id)

    def load_domain_session(self, session_id: str) -> DomainSessionContext | None:
        """Load and validate the domain extension of a shared session."""
        shared = self._store.load(session_id)
        if shared is None:
            return None
        raw = shared.extensions.get(self._extension_key)
        if raw is None:
            return None
        context = DomainSessionContext.from_dict(dict(raw))
        if context.session_id != session_id:
            raise DomainSessionSerializationError(
                "Session ID mismatch between shared envelope "
                f"'{session_id}' and domain session '{context.session_id}'",
                field="session_id",
            )
        return context

    def save_domain_session(
        self, context: DomainSessionContext
    ) -> DomainSessionContext:
        """Attach the domain extension and commit through the shared store.

        Returns the committed context (unchanged content-wise; the shared
        envelope's revision/history records the commit).
        """
        if not isinstance(context, DomainSessionContext):
            raise DomainSessionSerializationError(
                f"Expected DomainSessionContext, got {type(context).__name__}",
                field="context",
            )
        shared = self._store.load(context.session_id)
        if shared is None:
            from cmm.runtime.sessions import SharedSessionState

            shared = SharedSessionState(session_id=context.session_id)
        updated = shared.with_extension(
            self._extension_key, context.to_dict(), reason="domain-session:update"
        )
        committed = self._store.save(updated)
        # Fail closed if the commit did not durably carry the extension
        raw = committed.extensions.get(self._extension_key)
        if raw is None:
            raise DomainSessionSerializationError(
                "Shared session commit did not persist the domain extension",
                field=self._extension_key,
            )
        return DomainSessionContext.from_dict(dict(raw))

    def update_domain_session(
        self,
        session_id: str,
        updater,
    ) -> DomainSessionContext:
        """Load–modify–commit cycle through the shared store."""
        current = self.load_domain_session(session_id)
        if current is None:
            from cmm.runtime.sessions import SessionNotFoundError

            raise SessionNotFoundError(session_id)
        updated = updater(current)
        if not isinstance(updated, DomainSessionContext):
            raise DomainSessionSerializationError(
                "Updater must return a DomainSessionContext",
                field="updater",
            )
        if updated.session_id != session_id:
            raise DomainSessionSerializationError(
                "Updater must preserve session_id",
                field="session_id",
            )
        return self.save_domain_session(updated)
