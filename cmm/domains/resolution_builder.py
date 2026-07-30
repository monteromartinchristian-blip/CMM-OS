"""Phase 10.6 – Domain Resolution Context Builder.

Constructs a ``DomainResolutionContext`` exclusively from snapshots
(no live registry, no store access, no LLM calls).

Phase 10.7 will consume the context to select domains.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from datetime import datetime, timezone
from types import MappingProxyType
from typing import Any
from uuid import uuid4

from cmm.domains.enums import DomainStatus
from cmm.domains.errors import (
    DomainResolutionContractError,
    DomainResolutionLimitExceeded,
    DomainResolutionSnapshotError,
)
from cmm.domains.identifiers import DomainId
from cmm.domains.registry_contracts import (
    DomainRegistryRecord,
    DomainRegistrySnapshot,
)
from cmm.domains.resolution_contracts import (
    DomainResolutionContext,
    DomainResolutionEntity,
    DomainResolutionEvent,
    DomainResolutionHistoryItem,
    DomainResolutionKnowledgeItem,
    DomainResolutionPolicy,
    DomainResolutionResource,
    DomainResolutionSignal,
    _freeze_domain_ids,
)

# ── Statuses excluded from available ─────────────────────────────────────────

_EXCLUDED_FROM_AVAILABLE: frozenset[DomainStatus] = frozenset(
    {
        DomainStatus.INVALID,
        DomainStatus.FAILED,
        DomainStatus.INCOMPATIBLE,
        DomainStatus.UNLOADED,
    }
)

# ── Statuses that contribute to active ───────────────────────────────────────

_ACTIVE_STATUSES: frozenset[DomainStatus] = frozenset(
    {
        DomainStatus.ACTIVE,
    }
)

_DEGRADED_STATUS: DomainStatus = DomainStatus.DEGRADED


def _validate_positive_int(value: Any, name: str) -> int:
    """Validate that a value is a positive (>0) integer, not a bool."""
    if isinstance(value, bool):
        raise DomainResolutionContractError(
            f"{name} must be a positive integer, not a boolean",
            field=name,
        )
    if not isinstance(value, int):
        raise DomainResolutionContractError(
            f"{name} must be a positive integer, got {type(value).__name__}",
            field=name,
        )
    if value <= 0:
        raise DomainResolutionContractError(
            f"{name} must be a positive integer, got {value}",
            field=name,
        )
    return value


class DomainResolutionContextBuilder:
    """Builds a ``DomainResolutionContext`` from immutable snapshots.

    The builder uses only the snapshots it receives.  It never consults
    a live registry, a store, or an external service.

    Optional ``clock`` and ``id_factory`` callables allow deterministic
    testing.
    """

    def __init__(
        self,
        *,
        clock: Callable[[], datetime] | None = None,
        id_factory: Callable[[], str] | None = None,
        max_input_chars: int = 100_000,
        max_objective_chars: int = 10_000,
        max_history_items: int = 100,
        max_signals: int = 500,
    ) -> None:
        self._clock = clock or (lambda: datetime.now(timezone.utc))

        # Default id_factory uses uuid4 for uniqueness, not clock
        self._id_factory = id_factory or (lambda: f"ctx-{uuid4()}")

        # Validate builder configuration limits
        self._max_input_chars = _validate_positive_int(
            max_input_chars, "max_input_chars"
        )
        self._max_objective_chars = _validate_positive_int(
            max_objective_chars, "max_objective_chars"
        )
        self._max_history_items = _validate_positive_int(
            max_history_items, "max_history_items"
        )
        self._max_signals = _validate_positive_int(max_signals, "max_signals")

    # ── Public build entry point ──────────────────────────────────────────

    def build(
        self,
        *,
        registry_snapshot: DomainRegistrySnapshot | None = None,
        # ── Optional explicit overrides ──────────────────────────────────
        user_input: str | None = None,
        objective: str | None = None,
        event: DomainResolutionEvent | None = None,
        goal_id: str | None = None,
        session_id: str | None = None,
        workflow_id: str | None = None,
        explicit_domains: tuple[DomainId, ...] | None = None,
        authorized_domains: tuple[DomainId, ...] | None = None,
        resources: tuple[DomainResolutionResource, ...] | None = None,
        entities: tuple[DomainResolutionEntity, ...] | None = None,
        knowledge_items: tuple[DomainResolutionKnowledgeItem, ...] | None = None,
        recent_history: tuple[DomainResolutionHistoryItem, ...] | None = None,
        kernel_events: tuple[DomainResolutionEvent, ...] | None = None,
        signals: tuple[DomainResolutionSignal, ...] | None = None,
        current_profile: str | None = None,
        current_workflow: str | None = None,
        intent: str | None = None,
        requested_operations: tuple[str, ...] | None = None,
        actor: str | None = None,
        permissions: tuple[str, ...] | None = None,
        temporal_reference: datetime | None = None,
        language: str | None = None,
        user_preferences: Mapping[str, Any] | None = None,
        system_policy: DomainResolutionPolicy | None = None,
        metadata: Mapping[str, Any] | None = None,
    ) -> DomainResolutionContext:
        """Build an immutable resolution context from the provided data.

        The registry snapshot is the canonical source for
        ``available_domains`` and ``active_domains``.  All other fields
        use explicit values when provided, empty defaults otherwise.
        """

        records: tuple[DomainRegistryRecord, ...] = (
            tuple(registry_snapshot.records) if registry_snapshot else ()
        )

        # ── Derive available / active from snapshot ─────────────────────
        available_ids = self._derive_available(records)
        active_ids = self._derive_active(records)

        # ── Validate no two active versions of the same domain ──────────
        self._validate_no_duplicate_active_versions(records)

        # ── Apply explicit overrides ────────────────────────────────────
        explicit_ids = _freeze_domain_ids(explicit_domains or (), "explicit_domains")

        # Authorized: if not explicitly provided, derives from policy + available
        # In 10.6 we only set it when explicitly given. 10.7 will expand.
        authorized_ids: tuple[DomainId, ...] = (
            _freeze_domain_ids(authorized_domains or (), "authorized_domains")
            if authorized_domains is not None
            else ()
        )

        # ── Validate and produce context ID ─────────────────────────────
        try:
            ctx_id = self._id_factory()
        except Exception as exc:
            raise DomainResolutionContractError(
                f"id_factory failed to produce an id: {exc}",
                field="id_factory",
            ) from exc
        if not isinstance(ctx_id, str):
            raise DomainResolutionContractError(
                f"id_factory must return a string, got {type(ctx_id).__name__}",
                field="id",
            )
        if not ctx_id.strip():
            raise DomainResolutionContractError(
                "id_factory must return a non-empty string",
                field="id",
            )

        # ── Enforce limits ──────────────────────────────────────────────
        cleaned_input = self._clean_and_limit_text(
            user_input, self._max_input_chars, field_name="user_input"
        )
        cleaned_objective = self._clean_and_limit_text(
            objective, self._max_objective_chars, field_name="objective"
        )

        # History limit: reject, don't truncate
        history = recent_history or ()
        if len(history) > self._max_history_items:
            raise DomainResolutionLimitExceeded(
                "Recent history exceeds configured item limit",
                field="recent_history",
                details={
                    "count": len(history),
                    "max_items": self._max_history_items,
                },
            )

        # Signals limit: reject, don't truncate
        sigs = signals or ()
        if len(sigs) > self._max_signals:
            raise DomainResolutionLimitExceeded(
                "Signals exceed configured item limit",
                field="signals",
                details={
                    "count": len(sigs),
                    "max_signals": self._max_signals,
                },
            )

        # ── Preserve version/status evidence in metadata ────────────────
        enriched_metadata = dict(metadata or {})
        enriched_metadata.update(self._build_registry_version_metadata(records))

        return DomainResolutionContext(
            id=ctx_id,
            objective=cleaned_objective,
            user_input=cleaned_input,
            event=event,
            goal_id=goal_id,
            session_id=session_id,
            workflow_id=workflow_id,
            explicit_domains=explicit_ids,
            available_domains=available_ids,
            authorized_domains=authorized_ids,
            active_domains=active_ids,
            resources=resources or (),
            entities=entities or (),
            knowledge_items=knowledge_items or (),
            recent_history=history,
            kernel_events=kernel_events or (),
            signals=sigs,
            current_profile=current_profile,
            current_workflow=current_workflow,
            intent=intent,
            requested_operations=requested_operations or (),
            actor=actor or "system",
            permissions=permissions or (),
            temporal_reference=temporal_reference,
            language=language or "und",
            user_preferences=MappingProxyType(user_preferences or {}),
            system_policy=system_policy,
            metadata=MappingProxyType(enriched_metadata),
            created_at=self._clock(),
        )

    # ── Registry derivation ──────────────────────────────────────────────

    def _derive_available(
        self, records: tuple[DomainRegistryRecord, ...]
    ) -> tuple[DomainId, ...]:
        """Derive available domains from registry records.

        Excludes INVALID, FAILED, INCOMPATIBLE, UNLOADED.
        DISABLED is included (installed but not active).
        Deduplicates by slug (first occurrence preserved).
        """
        seen: set[str] = set()
        result: list[DomainId] = []
        for record in records:
            defn = record.definition
            slug = defn.id.slug
            if slug in seen:
                continue
            if record.status in _EXCLUDED_FROM_AVAILABLE:
                continue
            seen.add(slug)
            result.append(defn.id)
        return tuple(result)

    def _derive_active(
        self, records: tuple[DomainRegistryRecord, ...]
    ) -> tuple[DomainId, ...]:
        """Derive active domains from registry records.

        Only ACTIVE contributes to active. DEGRADED is available
        but not actively selected. Record is kept in metadata.
        """
        seen: set[str] = set()
        result: list[DomainId] = []
        for record in records:
            defn = record.definition
            slug = defn.id.slug
            if slug in seen:
                continue
            if record.status == DomainStatus.ACTIVE:
                seen.add(slug)
                result.append(defn.id)
        return tuple(result)

    def _validate_no_duplicate_active_versions(
        self, records: tuple[DomainRegistryRecord, ...]
    ) -> None:
        """Reject when the same domain appears twice with ACTIVE status."""
        active_count: dict[str, int] = {}
        for record in records:
            slug = record.definition.id.slug
            if record.status == DomainStatus.ACTIVE:
                active_count[slug] = active_count.get(slug, 0) + 1
        duplicates = {slug for slug, count in active_count.items() if count > 1}
        if duplicates:
            raise DomainResolutionSnapshotError(
                f"Multiple ACTIVE versions for domain(s): {sorted(duplicates)}",
                field="registry_snapshot",
                details={"duplicates": sorted(duplicates)},
            )

    def _build_registry_version_metadata(
        self, records: tuple[DomainRegistryRecord, ...]
    ) -> dict[str, Any]:
        """Preserve version/status evidence in metadata."""
        per_domain: dict[str, list[dict[str, str]]] = {}
        for record in records:
            slug = record.definition.id.slug
            entry = {
                "version": record.definition.version,
                "status": record.status.value,
                "kind": record.definition.kind.value,
            }
            per_domain.setdefault(slug, []).append(entry)
        return {
            "_resolution_registry_versions": per_domain,
        }

    # ── Input sanitisation ───────────────────────────────────────────────

    @staticmethod
    def _clean_and_limit_text(
        raw: str | None, max_chars: int, *, field_name: str = "user_input"
    ) -> str | None:
        """Clean input text and enforce max length."""
        if raw is None:
            return None
        if not isinstance(raw, str):
            raise DomainResolutionContractError(
                f"{field_name} must be a string, got {type(raw).__name__}",
                field=field_name,
            )
        cleaned = raw.strip()
        if not cleaned:
            return None
        if len(cleaned) > max_chars:
            raise DomainResolutionLimitExceeded(
                f"{field_name} exceeds configured character limit",
                field=field_name,
                details={"length": len(cleaned), "max_chars": max_chars},
            )
        return cleaned


__all__ = [
    "DomainResolutionContextBuilder",
]
