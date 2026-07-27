"""Phase 9.23 – Agent Resolver.

The resolver is the only component that turns an
``AgentRequirement`` into an ``AgentResolution`` (a structured, ordered
list of candidates plus a deterministic selected descriptor, or
``None``).

The resolver is split into three pieces to keep responsibilities
clean:

* :class:`AgentCompatibilityChecker` – evaluates a single
  ``(descriptor, requirement)`` pair and produces an
  :class:`AgentCompatibilityResult` (no exceptions for normal
  incompatibilities).
* :class:`AgentCandidateScorer` – assigns a deterministic score to
  each compatible candidate using fixed, documented weights.
* :class:`AgentResolver` – combines the two, applies the chosen
  :class:`AgentResolutionStrategy` and returns the final
  :class:`AgentResolution`.

The resolver never creates instances, never executes agents, and never
makes policy decisions that are not explicit in the requirement.
"""

from __future__ import annotations

import threading
from datetime import datetime, timezone
from typing import Any

from cmm.agent_runtime.agent_registry_contracts import (
    AgentCompatibilityResult,
    AgentDescriptor,
    AgentRequirement,
    AgentResolution,
    AgentResolutionCandidate,
    AgentResolutionStrategy,
    AgentVersion,
)
from cmm.agent_runtime.agent_registry_enums import (
    AgentCompatibilityStatus,
    AgentLifecycle,
)
from cmm.agent_runtime.agent_registry_errors import (
    AgentRegistryError,
    AgentRegistryNotFoundError,
    AgentRegistryValidationError,
    AgentResolutionAmbiguousError,
    AgentResolutionNotFoundError,
)

# ── Scorer ──────────────────────────────────────────────────────────────────


class AgentCandidateScorer:
    """Assigns a deterministic score to a compatible candidate.

    The score is a sum of weighted components. The weights are fixed
    class-level constants to keep behaviour predictable.

    * matched capabilities (per name);
    * matched operations (per name);
    * matched required tags (per name);
    * preferred-agent bonus (one-shot);
    * exact agent_id match (one-shot);
    * exact version match (one-shot);
    * priority (descriptor.priority).
    """

    WEIGHT_MATCHED_CAPABILITY: int = 20
    WEIGHT_MATCHED_OPERATION: int = 10
    WEIGHT_MATCHED_TAG: int = 5
    WEIGHT_PREFERRED_AGENT: int = 50
    WEIGHT_EXACT_AGENT_ID: int = 100
    WEIGHT_EXACT_VERSION: int = 30

    def __init__(self) -> None:
        self._lock = threading.RLock()

    def score(
        self,
        descriptor: AgentDescriptor,
        requirement: AgentRequirement,
        compatibility: AgentCompatibilityResult,
    ) -> tuple[int, tuple[str, ...], tuple[str, ...], tuple[str, ...], tuple[str, ...]]:
        """Return ``(score, matched_caps, missing_caps, matched_ops, missing_ops)``."""
        if not compatibility.is_compatible:
            return (
                0,
                tuple(sorted(c for c in compatibility.missing_capabilities)),
                tuple(sorted(c for c in compatibility.missing_capabilities)),
                (),
                tuple(sorted(o for o in compatibility.missing_operations)),
            )
        with self._lock:
            # Capabilities
            required_caps = set(requirement.required_capabilities)
            available_caps = {c.name for c in descriptor.capabilities}
            matched_caps = tuple(sorted(required_caps & available_caps))
            missing_caps = tuple(sorted(required_caps - available_caps))
            # Operations
            required_ops = set(requirement.required_operations)
            available_ops = set(descriptor.supported_operations) | {
                op for c in descriptor.capabilities for op in c.operations
            }
            matched_ops = tuple(sorted(required_ops & available_ops))
            missing_ops = tuple(sorted(required_ops - available_ops))
            # Tags
            required_tags = set(requirement.required_tags)
            available_tags = set(descriptor.tags)
            matched_tags = tuple(sorted(required_tags & available_tags))

            score = 0
            score += len(matched_caps) * self.WEIGHT_MATCHED_CAPABILITY
            score += len(matched_ops) * self.WEIGHT_MATCHED_OPERATION
            score += len(matched_tags) * self.WEIGHT_MATCHED_TAG
            if (
                requirement.agent_id is not None
                and requirement.agent_id == descriptor.agent_id
            ):
                score += self.WEIGHT_EXACT_AGENT_ID
            if (
                requirement.version is not None
                and requirement.version == descriptor.version.canonical()
            ):
                score += self.WEIGHT_EXACT_VERSION
            if descriptor.agent_id in requirement.preferred_agents:
                score += self.WEIGHT_PREFERRED_AGENT
            score += descriptor.priority
            return score, matched_caps, missing_caps, matched_ops, missing_ops


# ── Compatibility Checker ───────────────────────────────────────────────────


class AgentCompatibilityChecker:
    """Evaluate ``(descriptor, requirement)`` without raising.

    Incompatibilities are returned as a structured
    :class:`AgentCompatibilityResult` with explicit ``status`` and
    reasons. ``AgentFactoryNotFoundError`` is raised only when the
    factory registry is provided *and* the descriptor references a
    factory that does not exist (a contract violation, not a
    normal incompatibility).
    """

    def __init__(
        self,
        factory_registry: Any | None = None,
    ) -> None:
        self._factory_registry = factory_registry

    def check(
        self,
        descriptor: AgentDescriptor,
        requirement: AgentRequirement,
    ) -> AgentCompatibilityResult:
        reasons: list[str] = []
        missing_components: list[str] = []
        missing_permissions: list[str] = []
        missing_capabilities: list[str] = []
        missing_operations: list[str] = []

        # Exclusions
        if descriptor.agent_id in requirement.excluded_agents:
            return AgentCompatibilityResult(
                status=AgentCompatibilityStatus.EXCLUDED,
                reasons=("agent_excluded",),
            )

        # Lifecycle
        if descriptor.lifecycle == AgentLifecycle.DISABLED:
            return AgentCompatibilityResult(
                status=AgentCompatibilityStatus.INCOMPATIBLE_LIFECYCLE,
                reasons=("lifecycle_disabled",),
            )
        if descriptor.lifecycle == AgentLifecycle.RETIRED:
            return AgentCompatibilityResult(
                status=AgentCompatibilityStatus.INCOMPATIBLE_LIFECYCLE,
                reasons=("lifecycle_retired",),
            )
        if (
            descriptor.lifecycle == AgentLifecycle.DEPRECATED
            and not requirement.allow_deprecated
        ):
            return AgentCompatibilityResult(
                status=AgentCompatibilityStatus.INCOMPATIBLE_LIFECYCLE,
                reasons=("lifecycle_deprecated_not_allowed",),
            )
        if (
            descriptor.lifecycle == AgentLifecycle.EXPERIMENTAL
            and not requirement.allow_experimental
        ):
            return AgentCompatibilityResult(
                status=AgentCompatibilityStatus.INCOMPATIBLE_LIFECYCLE,
                reasons=("lifecycle_experimental_not_allowed",),
            )

        # Kind
        if requirement.kind is not None and descriptor.kind != requirement.kind:
            return AgentCompatibilityResult(
                status=AgentCompatibilityStatus.INCOMPATIBLE_RUNTIME,
                reasons=("kind_mismatch",),
            )

        # Version
        if requirement.version is not None:
            try:
                required_version = AgentVersion.parse(requirement.version)
            except AgentRegistryValidationError:
                return AgentCompatibilityResult(
                    status=AgentCompatibilityStatus.INCOMPATIBLE_VERSION,
                    reasons=("version_parse_error",),
                )
            if descriptor.version != required_version:
                return AgentCompatibilityResult(
                    status=AgentCompatibilityStatus.INCOMPATIBLE_VERSION,
                    reasons=("version_mismatch",),
                )

        # Capabilities
        available_caps = {c.name for c in descriptor.capabilities}
        for cap in requirement.required_capabilities:
            if cap not in available_caps:
                missing_capabilities.append(cap)
        if missing_capabilities:
            reasons.append("missing_capabilities")
            return AgentCompatibilityResult(
                status=AgentCompatibilityStatus.INCOMPATIBLE_CAPABILITY,
                reasons=tuple(reasons),
                missing_capabilities=tuple(sorted(set(missing_capabilities))),
            )

        # Operations
        available_ops = set(descriptor.supported_operations) | {
            op for c in descriptor.capabilities for op in c.operations
        }
        for op in requirement.required_operations:
            if op not in available_ops:
                missing_operations.append(op)
        if missing_operations:
            reasons.append("missing_operations")
            return AgentCompatibilityResult(
                status=AgentCompatibilityStatus.INCOMPATIBLE_OPERATION,
                reasons=tuple(reasons),
                missing_operations=tuple(sorted(set(missing_operations))),
            )

        # Tags
        available_tags = set(descriptor.tags)
        for tag in requirement.required_tags:
            if tag not in available_tags:
                missing_capabilities.append(f"tag:{tag}")
        if any(item.startswith("tag:") for item in missing_capabilities):
            return AgentCompatibilityResult(
                status=AgentCompatibilityStatus.INCOMPATIBLE_CAPABILITY,
                reasons=("missing_tags",),
                missing_capabilities=tuple(
                    item for item in missing_capabilities if item.startswith("tag:")
                ),
            )

        # Permissions
        for perm in requirement.required_permissions:
            if perm not in descriptor.required_permissions:
                missing_permissions.append(perm)
        if missing_permissions:
            return AgentCompatibilityResult(
                status=AgentCompatibilityStatus.INCOMPATIBLE_PERMISSION,
                reasons=("missing_permissions",),
                missing_permissions=tuple(sorted(set(missing_permissions))),
            )

        # Components
        available_components: set[str] = set()
        if self._factory_registry is not None:
            try:
                # The factory registry exposes ``_factories`` – we use a
                # defensive interface here to avoid hard-coupling.
                factories = self._factory_registry.list()
            except (AgentRegistryError, AttributeError):
                return AgentCompatibilityResult(
                    status=AgentCompatibilityStatus.FACTORY_UNAVAILABLE,
                    reasons=("factory_registry_unavailable",),
                )
            available_components = {getattr(f, "factory_id", "") for f in factories}
        for comp in descriptor.required_components:
            if comp not in available_components:
                missing_components.append(comp)
        if missing_components:
            return AgentCompatibilityResult(
                status=AgentCompatibilityStatus.INCOMPATIBLE_COMPONENT,
                reasons=("missing_components",),
                missing_components=tuple(sorted(set(missing_components))),
            )

        # Factory availability
        if self._factory_registry is not None:
            try:
                if not self._factory_registry.contains(descriptor.factory_id):
                    return AgentCompatibilityResult(
                        status=AgentCompatibilityStatus.FACTORY_UNAVAILABLE,
                        reasons=("factory_not_registered",),
                    )
                factory = self._factory_registry.get(descriptor.factory_id)
            except (AgentRegistryError, AttributeError):
                return AgentCompatibilityResult(
                    status=AgentCompatibilityStatus.FACTORY_UNAVAILABLE,
                    reasons=("factory_registry_unavailable",),
                )
            try:
                if not bool(factory.supports(descriptor)):
                    return AgentCompatibilityResult(
                        status=AgentCompatibilityStatus.FACTORY_UNAVAILABLE,
                        reasons=("factory_does_not_support",),
                    )
            except AgentRegistryError:
                return AgentCompatibilityResult(
                    status=AgentCompatibilityStatus.FACTORY_UNAVAILABLE,
                    reasons=("factory_supports_error",),
                )

        return AgentCompatibilityResult(
            status=AgentCompatibilityStatus.COMPATIBLE,
            reasons=(),
            missing_components=(),
            missing_permissions=(),
            missing_capabilities=(),
            missing_operations=(),
        )


# ── Resolver ────────────────────────────────────────────────────────────────


class AgentResolver:
    """Resolve a requirement against the descriptors held by an
    :class:`AgentRegistry`.
    """

    DEFAULT_STRATEGY: AgentResolutionStrategy = AgentResolutionStrategy.BEST_MATCH

    def __init__(
        self,
        registry: Any,
        compatibility_checker: AgentCompatibilityChecker | None = None,
        scorer: AgentCandidateScorer | None = None,
    ) -> None:
        self._registry = registry
        self._checker = compatibility_checker or AgentCompatibilityChecker()
        self._scorer = scorer or AgentCandidateScorer()
        self._lock = threading.RLock()
        self._attempts: int = 0
        self._successes: int = 0
        self._failures: int = 0

    # ── Statistics ─────────────────────────────────────────────────────────

    @property
    def attempts(self) -> int:
        with self._lock:
            return self._attempts

    @property
    def successes(self) -> int:
        with self._lock:
            return self._successes

    @property
    def failures(self) -> int:
        with self._lock:
            return self._failures

    def stats(self) -> dict[str, int]:
        with self._lock:
            return {
                "resolution_attempts": self._attempts,
                "resolution_successes": self._successes,
                "resolution_failures": self._failures,
            }

    # ── Public API ────────────────────────────────────────────────────────

    def resolve(
        self,
        requirement: AgentRequirement,
        *,
        strategy: AgentResolutionStrategy | None = None,
        request_id: str | None = None,
    ) -> AgentResolution:
        """Return a structured :class:`AgentResolution` for ``requirement``.

        Raises :class:`AgentResolutionNotFoundError` when no compatible
        descriptor is found (and the strategy was ``EXACT``), and
        :class:`AgentResolutionAmbiguousError` when an exact
        ``agent_id`` resolves to more than one compatible candidate.
        """
        if not isinstance(requirement, AgentRequirement):
            raise AgentRegistryNotFoundError(
                "resolve() requires an AgentRequirement",
                {"type": type(requirement).__name__},
            )
        with self._lock:
            self._attempts += 1
            strategy = strategy or self.DEFAULT_STRATEGY
            try:
                candidate_descriptors = list(self._iter_candidates(requirement))
            except AgentRegistryNotFoundError:
                self._failures += 1
                raise

            candidates: list[AgentResolutionCandidate] = []
            for descriptor in candidate_descriptors:
                compat = self._checker.check(descriptor, requirement)
                score, matched_caps, missing_caps, matched_ops, missing_ops = (
                    self._scorer.score(descriptor, requirement, compat)
                )
                rejection_reasons = tuple(r for r in compat.reasons if r != "")
                candidate = AgentResolutionCandidate(
                    descriptor=descriptor,
                    compatibility=compat.status,
                    score=score,
                    matched_capabilities=matched_caps,
                    missing_capabilities=tuple(
                        sorted(set(missing_caps) | set(compat.missing_capabilities))
                    ),
                    matched_operations=matched_ops,
                    missing_operations=tuple(
                        sorted(set(missing_ops) | set(compat.missing_operations))
                    ),
                    rejection_reasons=rejection_reasons,
                )
                candidates.append(candidate)

            candidates.sort(key=self._candidate_sort_key)

            # EXACT strategy: if agent_id was given, the first
            # compatible candidate must be unique.
            compatible = [
                c
                for c in candidates
                if c.compatibility == AgentCompatibilityStatus.COMPATIBLE
            ]
            if (
                requirement.agent_id is not None
                and strategy == AgentResolutionStrategy.EXACT
            ):
                if not compatible:
                    self._failures += 1
                    raise AgentResolutionNotFoundError(
                        "No compatible descriptor found for exact requirement",
                        {"agent_id": requirement.agent_id},
                    )
                if len(compatible) > 1:
                    # Should never happen because we filter by agent_id,
                    # but raise defensively.
                    self._failures += 1
                    raise AgentResolutionAmbiguousError(
                        "Exact requirement matched multiple descriptors",
                        {
                            "agent_id": requirement.agent_id,
                            "count": len(compatible),
                        },
                    )
                selected = compatible[0].descriptor
                self._successes += 1
                return AgentResolution(
                    selected=selected,
                    candidates=tuple(candidates),
                    strategy=strategy,
                    resolved_at=datetime.now(timezone.utc),
                    request_id=request_id,
                )

            if strategy == AgentResolutionStrategy.HIGHEST_PRIORITY:
                if compatible:
                    top = max(compatible, key=lambda c: c.descriptor.priority)
                    selected = top.descriptor
                else:
                    selected = None
            elif strategy == AgentResolutionStrategy.HIGHEST_VERSION:
                if compatible:
                    top = max(
                        compatible,
                        key=lambda c: c.descriptor.version,
                    )
                    selected = top.descriptor
                else:
                    selected = None
            elif strategy == AgentResolutionStrategy.CAPABILITY_MATCH:
                if compatible:
                    top = max(
                        compatible,
                        key=lambda c: (
                            len(c.matched_capabilities),
                            len(c.matched_operations),
                            c.descriptor.priority,
                            c.descriptor.agent_id,
                        ),
                    )
                    selected = top.descriptor
                else:
                    selected = None
            else:
                # BEST_MATCH (default) – pick by score, with stable
                # tiebreakers.
                if compatible:
                    top = compatible[0]
                    # Detect ambiguous tie.
                    top_score = top.score
                    tied = [
                        c
                        for c in compatible[1:]
                        if c.score == top_score
                        and len(c.matched_capabilities) == len(top.matched_capabilities)
                        and len(c.matched_operations) == len(top.matched_operations)
                        and c.descriptor.priority == top.descriptor.priority
                        and c.descriptor.version == top.descriptor.version
                    ]
                    if tied:
                        self._failures += 1
                        raise AgentResolutionAmbiguousError(
                            "Two candidates tied with the same score and shape",
                            {
                                "agent_ids": sorted(
                                    {
                                        top.descriptor.agent_id,
                                        tied[0].descriptor.agent_id,
                                    }
                                )
                            },
                        )
                    selected = top.descriptor
                else:
                    selected = None

            if selected is None:
                self._failures += 1
            else:
                self._successes += 1
            return AgentResolution(
                selected=selected,
                candidates=tuple(candidates),
                strategy=strategy,
                resolved_at=datetime.now(timezone.utc),
                request_id=request_id,
            )

    # ── Internal helpers ──────────────────────────────────────────────────

    def _iter_candidates(self, requirement: AgentRequirement):
        """Yield the candidate descriptors from the registry."""
        if requirement.agent_id is not None:
            # Resolve via agent_id first; fall back to alias.
            d = self._registry.get(requirement.agent_id)
            if d is None:
                aliases = self._registry.find_by_alias(requirement.agent_id)
                if not aliases:
                    raise AgentRegistryNotFoundError(
                        "Agent not found by agent_id or alias",
                        {"agent_id": requirement.agent_id},
                    )
                # If alias resolves to multiple versions, let the
                # strategy decide below.
                yield from aliases
            else:
                yield d
        else:
            # No agent_id – use kind/capability/tag as a pre-filter.
            # Capability/tag filtering is delegated to the
            # compatibility checker; we only pre-filter on ``kind``
            # to avoid loading obviously-irrelevant candidates.
            seen: set = set()
            for d in self._registry.list():
                if requirement.kind is not None and d.kind != requirement.kind:
                    continue
                identity = (d.agent_id, d.version.canonical())
                if identity in seen:
                    continue
                seen.add(identity)
                yield d

    @staticmethod
    def _candidate_sort_key(
        candidate: AgentResolutionCandidate,
    ) -> tuple[int, int, int, int, str, str]:
        # 1) compatible first
        # 2) higher score
        # 3) more matched capabilities
        # 4) more matched operations
        # 5) higher priority
        # 6) lower version canonical
        # 7) lexicographic agent_id
        return (
            0 if candidate.compatibility == AgentCompatibilityStatus.COMPATIBLE else 1,
            -candidate.score,
            -len(candidate.matched_capabilities),
            -len(candidate.matched_operations),
            -candidate.descriptor.priority,
            candidate.descriptor.version.canonical(),
            candidate.descriptor.agent_id,
        )


__all__ = [
    "AgentCandidateScorer",
    "AgentCompatibilityChecker",
    "AgentResolver",
]
