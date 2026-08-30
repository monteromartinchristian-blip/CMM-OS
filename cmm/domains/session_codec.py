"""Phase 10.34 — Domain Session Codec.

Narrow adapter boundary between DomainSessionContext and shared Phase 8 Session Context persistence representation.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from cmm.domains.errors import DomainSessionSerializationError
from cmm.domains.session_contracts import DomainSessionContext

DOMAIN_SESSION_EXTENSION_KEY: str = "domain_session"


class DomainSessionCodec:
    """Encodes and decodes DomainSessionContext to/from shared SessionContext envelopes."""

    def __init__(self, extension_key: str = DOMAIN_SESSION_EXTENSION_KEY) -> None:
        self._extension_key = extension_key

    @property
    def extension_key(self) -> str:
        return self._extension_key

    def is_domain_session_attached(self, session_context: Any) -> bool:
        """Return True if a domain session extension payload is present."""
        if isinstance(session_context, Mapping):
            if self._extension_key in session_context:
                return True
            metadata = session_context.get("metadata")
            if isinstance(metadata, Mapping) and self._extension_key in metadata:
                return True
        elif hasattr(session_context, "metadata"):
            metadata = getattr(session_context, "metadata", None)
            if isinstance(metadata, Mapping) and self._extension_key in metadata:
                return True
        return False

    def extract_from_session(self, session_context: Any) -> DomainSessionContext | None:
        """Extract and deserialize DomainSessionContext from session context, or None if absent."""
        payload: Any = None
        if isinstance(session_context, Mapping):
            if self._extension_key in session_context:
                payload = session_context[self._extension_key]
            elif "metadata" in session_context and isinstance(
                session_context["metadata"], Mapping
            ):
                payload = session_context["metadata"].get(self._extension_key)
        elif hasattr(session_context, "metadata"):
            metadata = getattr(session_context, "metadata", None)
            if isinstance(metadata, Mapping):
                payload = metadata.get(self._extension_key)

        if payload is None:
            return None

        if isinstance(payload, DomainSessionContext):
            return payload

        if not isinstance(payload, Mapping):
            raise DomainSessionSerializationError(
                f"Domain session payload must be a mapping, got {type(payload).__name__}",
                field=self._extension_key,
            )

        return DomainSessionContext.from_dict(payload)

    def attach_to_session(
        self, session_context: dict[str, Any], domain_session: DomainSessionContext
    ) -> dict[str, Any]:
        """Attach serialized DomainSessionContext into session dictionary."""
        if not isinstance(domain_session, DomainSessionContext):
            raise DomainSessionSerializationError(
                f"domain_session must be DomainSessionContext, got {type(domain_session).__name__}",
                field="domain_session",
            )
        updated = dict(session_context)
        updated[self._extension_key] = domain_session.to_dict()
        return updated

    def detach_from_session(self, session_context: dict[str, Any]) -> dict[str, Any]:
        """Remove domain session extension from session dictionary."""
        updated = dict(session_context)
        updated.pop(self._extension_key, None)
        if "metadata" in updated and isinstance(updated["metadata"], dict):
            updated["metadata"] = dict(updated["metadata"])
            updated["metadata"].pop(self._extension_key, None)
        return updated


__all__ = [
    "DOMAIN_SESSION_EXTENSION_KEY",
    "DomainSessionCodec",
]
