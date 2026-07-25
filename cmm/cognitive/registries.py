"""Phase 8.3 – In-memory registries for adapters and extractors.

Public surface
--------------
ResourceAdapterRegistry
KnowledgeExtractorRegistry
"""

from __future__ import annotations

from typing import Any

from cmm.cognitive.adapters import (
    AdaptationContext,
    ResourceAdaptationResult,
    ResourceAdapter,
    ResourceInput,
)
from cmm.cognitive.errors import (
    ComponentNotCompatibleError,
    ComponentNotFoundError,
    DuplicateRegistryEntryError,
    InvalidAdapterContractError,
)
from cmm.cognitive.extraction import (
    ExtractionContext,
    KnowledgeExtractionResult,
    KnowledgeExtractor,
)
from cmm.cognitive.resources import Resource

# ── Validation helpers ────────────────────────────────────────────────────────


def _validate_adapter(adapter: Any) -> None:
    """Verify that *adapter* satisfies the ResourceAdapter protocol."""
    for attr in ("name", "version", "supports", "adapt"):
        if not hasattr(adapter, attr):
            raise InvalidAdapterContractError(
                f"adapter is missing required attribute '{attr}'"
            )
    if not isinstance(adapter.name, str) or not adapter.name.strip():
        raise InvalidAdapterContractError("adapter name must be a non-empty string")
    if not isinstance(adapter.version, str) or not adapter.version.strip():
        raise InvalidAdapterContractError("adapter version must be a non-empty string")


def _validate_extractor(extractor: Any) -> None:
    """Verify that *extractor* satisfies the KnowledgeExtractor protocol."""
    for attr in ("name", "version", "supports", "extract"):
        if not hasattr(extractor, attr):
            raise InvalidAdapterContractError(
                f"extractor is missing required attribute '{attr}'"
            )
    if not isinstance(extractor.name, str) or not extractor.name.strip():
        raise InvalidAdapterContractError("extractor name must be a non-empty string")
    if not isinstance(extractor.version, str) or not extractor.version.strip():
        raise InvalidAdapterContractError(
            "extractor version must be a non-empty string"
        )


# ── ResourceAdapterRegistry ───────────────────────────────────────────────────


class ResourceAdapterRegistry:
    """In-memory registry of :class:`~cmm.cognitive.adapters.ResourceAdapter` instances.

    Adapters are ordered by registration time.  When multiple adapters support
    a given input the first-registered compatible adapter wins, providing a
    deterministic resolution strategy.  A higher explicit priority can be
    assigned at registration time to override insertion order.
    """

    def __init__(self) -> None:
        # Stores (priority, adapter) ordered by (–priority, insertion_order)
        self._adapters: dict[str, ResourceAdapter] = {}
        self._priorities: dict[str, int] = {}
        self._insertion_order: dict[str, int] = {}
        self._counter: int = 0

    # ── Mutation ──────────────────────────────────────────────────────────────

    def register(
        self,
        adapter: ResourceAdapter,
        *,
        priority: int = 0,
        replace: bool = False,
    ) -> None:
        """Register an adapter.

        Parameters
        ----------
        adapter:
            The adapter to register.
        priority:
            Higher values are preferred during auto-resolution.
        replace:
            When *True* an existing adapter with the same name is silently
            replaced.  When *False* (default) a
            :exc:`~cmm.cognitive.errors.DuplicateRegistryEntryError` is raised.
        """
        _validate_adapter(adapter)
        name = adapter.name
        if name in self._adapters and not replace:
            raise DuplicateRegistryEntryError(
                f"an adapter named {name!r} is already registered; "
                "use replace=True to overwrite it"
            )
        self._adapters[name] = adapter
        self._priorities[name] = priority
        if name not in self._insertion_order:
            self._insertion_order[name] = self._counter
            self._counter += 1

    def unregister(self, name: str) -> None:
        """Remove an adapter by name."""
        if name not in self._adapters:
            raise ComponentNotFoundError(f"no adapter named {name!r} is registered")
        del self._adapters[name]
        del self._priorities[name]

    # ── Query ─────────────────────────────────────────────────────────────────

    def get(self, name: str) -> ResourceAdapter:
        """Return the adapter registered under *name*."""
        if name not in self._adapters:
            raise ComponentNotFoundError(f"no adapter named {name!r} is registered")
        return self._adapters[name]

    def contains(self, name: str) -> bool:
        """Return *True* when an adapter named *name* is registered."""
        return name in self._adapters

    def list_adapters(self) -> list[ResourceAdapter]:
        """Return all adapters in deterministic priority order."""
        return self._sorted_adapters()

    def resolve(self, source: ResourceInput) -> ResourceAdapter:
        """Find the best adapter for *source*.

        Resolution is deterministic: adapters are checked in descending
        priority order, with ties broken by insertion order (earliest wins).
        """
        for adapter in self._sorted_adapters():
            if adapter.supports(source):
                return adapter
        raise ComponentNotCompatibleError(
            f"no registered adapter supports input {source.id!r}"
        )

    # ── Convenience ───────────────────────────────────────────────────────────

    def adapt(
        self,
        source: ResourceInput,
        *,
        context: AdaptationContext | None = None,
    ) -> ResourceAdaptationResult:
        """Resolve and run the appropriate adapter for *source*."""
        adapter = self.resolve(source)
        return adapter.adapt(source, context=context)

    # ── Internal ──────────────────────────────────────────────────────────────

    def _sorted_adapters(self) -> list[ResourceAdapter]:
        """Return adapters sorted by (-priority, insertion_order)."""
        return sorted(
            self._adapters.values(),
            key=lambda a: (
                -self._priorities.get(a.name, 0),
                self._insertion_order.get(a.name, 0),
            ),
        )

    def __len__(self) -> int:
        return len(self._adapters)

    def __repr__(self) -> str:
        names = [a.name for a in self._sorted_adapters()]
        return f"{self.__class__.__name__}({names!r})"


# ── KnowledgeExtractorRegistry ────────────────────────────────────────────────


class KnowledgeExtractorRegistry:
    """In-memory registry of :class:`~cmm.cognitive.extraction.KnowledgeExtractor`
    instances.

    Follows the same deterministic resolution strategy as
    :class:`ResourceAdapterRegistry`.
    """

    def __init__(self) -> None:
        self._extractors: dict[str, KnowledgeExtractor] = {}
        self._priorities: dict[str, int] = {}
        self._insertion_order: dict[str, int] = {}
        self._counter: int = 0

    # ── Mutation ──────────────────────────────────────────────────────────────

    def register(
        self,
        extractor: KnowledgeExtractor,
        *,
        priority: int = 0,
        replace: bool = False,
    ) -> None:
        """Register an extractor."""
        _validate_extractor(extractor)
        name = extractor.name
        if name in self._extractors and not replace:
            raise DuplicateRegistryEntryError(
                f"an extractor named {name!r} is already registered; "
                "use replace=True to overwrite it"
            )
        self._extractors[name] = extractor
        self._priorities[name] = priority
        if name not in self._insertion_order:
            self._insertion_order[name] = self._counter
            self._counter += 1

    def unregister(self, name: str) -> None:
        """Remove an extractor by name."""
        if name not in self._extractors:
            raise ComponentNotFoundError(f"no extractor named {name!r} is registered")
        del self._extractors[name]
        del self._priorities[name]

    # ── Query ─────────────────────────────────────────────────────────────────

    def get(self, name: str) -> KnowledgeExtractor:
        """Return the extractor registered under *name*."""
        if name not in self._extractors:
            raise ComponentNotFoundError(f"no extractor named {name!r} is registered")
        return self._extractors[name]

    def contains(self, name: str) -> bool:
        """Return *True* when an extractor named *name* is registered."""
        return name in self._extractors

    def list_extractors(self) -> list[KnowledgeExtractor]:
        """Return all extractors in deterministic priority order."""
        return self._sorted_extractors()

    def resolve(self, resource: Resource) -> KnowledgeExtractor:
        """Find the best extractor for *resource*."""
        for extractor in self._sorted_extractors():
            if extractor.supports(resource):
                return extractor
        raise ComponentNotCompatibleError(
            f"no registered extractor supports resource {resource.id!r}"
        )

    # ── Convenience ───────────────────────────────────────────────────────────

    def extract(
        self,
        resource: Resource,
        *,
        context: ExtractionContext | None = None,
        extractor_name: str | None = None,
    ) -> KnowledgeExtractionResult:
        """Run an extractor against *resource*.

        When *extractor_name* is given that specific extractor is used;
        otherwise the most compatible one is resolved automatically.
        """
        if extractor_name is not None:
            extractor = self.get(extractor_name)
        else:
            extractor = self.resolve(resource)
        return extractor.extract(resource, context=context)

    # ── Internal ──────────────────────────────────────────────────────────────

    def _sorted_extractors(self) -> list[KnowledgeExtractor]:
        return sorted(
            self._extractors.values(),
            key=lambda e: (
                -self._priorities.get(e.name, 0),
                self._insertion_order.get(e.name, 0),
            ),
        )

    def __len__(self) -> int:
        return len(self._extractors)

    def __repr__(self) -> str:
        names = [e.name for e in self._sorted_extractors()]
        return f"{self.__class__.__name__}({names!r})"
