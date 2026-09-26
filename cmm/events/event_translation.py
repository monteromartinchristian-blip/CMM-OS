"""Phase 11.22 — explicit source-to-platform event translation.

Phase 11.22 transports lifecycle facts owned by other subsystems.  A platform
event name that differs from the owning subsystem's own event name is reached
only through an explicit, one-way mapping declared here.

Translation is allowed only when:

1. the semantic mapping is explicit and one-way;
2. no authority is added;
3. no payload content is invented;
4. correlation/causation is preserved;
5. duplicate semantic delivery is controlled.

This module is a *table*, not a registry and not a publisher: it answers
``source_event_type -> platform_event_type | None`` and nothing else.  An
unmapped source event is never guessed, and the production adapters use the same
table rather than each carrying a private mapping.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from types import MappingProxyType

from cmm.agent_runtime.runtime_event_contracts import EventSensitivity
from cmm.agent_runtime.runtime_event_types import EventType
from cmm.events.event_catalog import PlatformEventSpec, catalog_spec

__all__ = [
    "KERNEL_SOURCE_TRANSLATIONS",
    "ORCHESTRATION_SOURCE_TRANSLATIONS",
    "SOURCE_SENSITIVITY_TRANSLATIONS",
    "SourceTranslation",
    "kernel_translation_table",
    "orchestration_translation_table",
    "translate_kernel_event",
    "translate_orchestration_event",
    "translate_source_sensitivity",
    "translated_platform_event_types",
]


@dataclass(frozen=True, slots=True)
class SourceTranslation:
    """One explicit one-way mapping from a producer event to a platform event.

    ``fact_keys`` names the payload keys the mapping may read from the source
    event.  A translation never invents a field: a fact key absent from the
    source payload is absent from the translated payload.

    ``nested_fact_keys`` names the subset of ``fact_keys`` that a closed-phase
    source stores inside its own structural ``payload`` container rather than at
    the top level of its serialization.  A Phase 10.33 ``DomainEvent.to_dict()``
    is exactly such a shape: lifecycle facts such as ``execution_id``, ``status``,
    ``approval_id`` or ``approved`` live under ``payload``.  Only the keys named
    here may ever be read from that container — the container is never flattened
    generically — and every nested key must itself be inside the bounded platform
    payload vocabulary.
    """

    source_event_type: str
    platform_event_type: str
    fact_keys: tuple[str, ...]
    rationale: str
    nested_fact_keys: tuple[str, ...] = field(default=())

    def __post_init__(self) -> None:
        if not self.source_event_type:
            raise ValueError("source_event_type is required")
        if not self.platform_event_type:
            raise ValueError("platform_event_type is required")
        if not self.rationale:
            raise ValueError("translation rationale is required")
        unsupported = set(self.nested_fact_keys) - set(self.fact_keys)
        if unsupported:
            raise ValueError(
                f"nested_fact_keys must be a subset of fact_keys: {sorted(unsupported)}"
            )
        # Fail closed at import time if a mapping targets an unknown catalog name.
        catalog_spec(self.platform_event_type)


#: Orchestration lifecycle facts Phase 11.2 already owns, mapped one-way.
ORCHESTRATION_SOURCE_TRANSLATIONS: tuple[SourceTranslation, ...] = (
    SourceTranslation(
        source_event_type="orchestration.request_received",
        platform_event_type="message.received",
        fact_keys=("channel", "session_id"),
        rationale=(
            "an accepted inbound orchestration request is the platform's "
            "message.received lifecycle fact"
        ),
    ),
    SourceTranslation(
        source_event_type="orchestration.intent_resolved",
        platform_event_type="intent.resolved",
        fact_keys=("intent", "needs_clarification"),
        rationale="the Orchestrator owns intent resolution and reports it directly",
    ),
    SourceTranslation(
        source_event_type="orchestration.domain_resolved",
        platform_event_type="domain.selected",
        fact_keys=("status", "primary_domain", "supporting_domains"),
        rationale=(
            "the Orchestrator owns domain route resolution and reports the selected "
            "canonical domain"
        ),
    ),
    SourceTranslation(
        source_event_type="orchestration.approval_required",
        platform_event_type="approval.requested",
        fact_keys=("status", "primary_domain", "approval_refs"),
        rationale=(
            "a policy disposition of REQUIRE_APPROVAL is the platform's "
            "approval.requested lifecycle fact"
        ),
    ),
)

#: Kernel Event names already owned by closed phases, mapped one-way.
#:
#: ``validation.*`` comes from the Phase 7 ``KernelEventPublisher``; ``domain.*``
#: comes from the Phase 10.33 ``DomainKernelEventPublisher``; ``workflow.*`` comes
#: from the canonical workflow subsystem's ``WorkflowEvent`` contract as projected
#: onto the Kernel Event boundary.
KERNEL_SOURCE_TRANSLATIONS: tuple[SourceTranslation, ...] = (
    SourceTranslation(
        source_event_type="validation.completed",
        platform_event_type="validation.completed",
        fact_keys=("validation_id", "status", "policy", "duration_ms", "workflow_id"),
        rationale="the Phase 7 validation publisher owns this lifecycle completion",
    ),
    SourceTranslation(
        source_event_type="validation.failed",
        platform_event_type="validation.completed",
        fact_keys=("validation_id", "status", "policy", "duration_ms", "workflow_id"),
        rationale=(
            "a failed validation is still a completed validation lifecycle, carrying "
            "its own status rather than a fabricated success"
        ),
    ),
    SourceTranslation(
        source_event_type="domain.execution.completed",
        platform_event_type="operation.executed",
        fact_keys=("domain_id", "status", "execution_id", "duration_ms"),
        rationale=(
            "a completed canonical domain execution is the platform's "
            "operation.executed lifecycle fact"
        ),
        nested_fact_keys=("execution_id", "status"),
    ),
    SourceTranslation(
        source_event_type="domain.resolution.completed",
        platform_event_type="domain.selected",
        fact_keys=("domain_id", "status"),
        rationale="a completed canonical domain resolution selects that domain",
        nested_fact_keys=("status",),
    ),
    SourceTranslation(
        source_event_type="domain.approval.requested",
        platform_event_type="approval.requested",
        fact_keys=("domain_id", "status", "approval_id"),
        rationale="the canonical Phase 10.33 approval request lifecycle fact",
        nested_fact_keys=("approval_id",),
    ),
    SourceTranslation(
        source_event_type="domain.approval.received",
        platform_event_type="approval.resolved",
        fact_keys=("domain_id", "status", "approval_id", "approved"),
        rationale=(
            "the canonical Phase 10.33 approval decision lifecycle fact, carrying "
            "its own bounded resolution fact and never an invented status"
        ),
        nested_fact_keys=("approval_id", "approved"),
    ),
    SourceTranslation(
        source_event_type="domain.memory.updated",
        platform_event_type="memory.updated",
        fact_keys=("domain_id", "status"),
        rationale="the canonical Phase 10.33 memory update lifecycle fact",
        nested_fact_keys=("status",),
    ),
    SourceTranslation(
        source_event_type="workflow.started",
        platform_event_type="workflow.started",
        fact_keys=("workflow_id", "run_id", "status"),
        rationale="the canonical workflow subsystem owns workflow start",
    ),
    SourceTranslation(
        source_event_type="workflow.running",
        platform_event_type="workflow.started",
        fact_keys=("workflow_id", "run_id", "status"),
        rationale=(
            "the canonical workflow engine names its start fact workflow.running; the "
            "platform catalog names the same fact workflow.started"
        ),
    ),
    SourceTranslation(
        source_event_type="workflow.paused",
        platform_event_type="workflow.paused",
        fact_keys=("workflow_id", "run_id", "status", "node_id"),
        rationale="the canonical workflow subsystem owns workflow pause",
    ),
    SourceTranslation(
        source_event_type="workflow.completed",
        platform_event_type="workflow.completed",
        fact_keys=("workflow_id", "run_id", "status"),
        rationale="the canonical workflow subsystem owns workflow completion",
    ),
    SourceTranslation(
        source_event_type="workflow.failed",
        platform_event_type="workflow.failed",
        fact_keys=("workflow_id", "run_id", "status", "error_code"),
        rationale="the canonical workflow subsystem owns workflow failure",
    ),
)

#: Explicit source-sensitivity classification → platform classification mapping.
#:
#: Phase 10.33 ``DomainEvent.sensitivity`` is a free-form classification string,
#: while the platform header uses the four-class ``EventSensitivity`` vocabulary.
#: Every entry here maps to a platform class that is at least as restrictive as its
#: source class, so a source classification is never silently downgraded.  A source
#: classification absent from this table has no explicitly mapped platform class,
#: and the caller must fail closed rather than guess one.
SOURCE_SENSITIVITY_TRANSLATIONS: tuple[tuple[str, EventSensitivity], ...] = (
    ("public", EventSensitivity.PUBLIC),
    ("internal", EventSensitivity.INTERNAL),
    ("personal", EventSensitivity.CONFIDENTIAL),
    ("confidential", EventSensitivity.CONFIDENTIAL),
    ("sensitive", EventSensitivity.CONFIDENTIAL),
    ("highly_sensitive", EventSensitivity.RESTRICTED),
    ("highlysensitive", EventSensitivity.RESTRICTED),
    ("restricted", EventSensitivity.RESTRICTED),
)

_SOURCE_SENSITIVITY_TABLE = MappingProxyType(dict(SOURCE_SENSITIVITY_TRANSLATIONS))

_ORCHESTRATION_TABLE = MappingProxyType(
    {
        translation.source_event_type: translation
        for translation in ORCHESTRATION_SOURCE_TRANSLATIONS
    }
)

_KERNEL_TABLE = MappingProxyType(
    {
        translation.source_event_type: translation
        for translation in KERNEL_SOURCE_TRANSLATIONS
    }
)


def translate_source_sensitivity(
    source_sensitivity: str,
) -> EventSensitivity | None:
    """Return the platform classification for an explicit source classification.

    ``None`` means the source classification has no explicitly mapped platform
    class.  The caller must then fail closed: choosing a class for an unknown
    classification would either downgrade real sensitivity or invent a
    classification the source never asserted.
    """

    if not isinstance(source_sensitivity, str):
        return None
    normalized = source_sensitivity.strip().lower().replace("-", "_")
    return _SOURCE_SENSITIVITY_TABLE.get(normalized)


def orchestration_translation_table() -> MappingProxyType:
    """Return the immutable orchestration translation table."""

    return _ORCHESTRATION_TABLE


def kernel_translation_table() -> MappingProxyType:
    """Return the immutable kernel event translation table."""

    return _KERNEL_TABLE


def translate_orchestration_event(
    source_event_type: str,
) -> SourceTranslation | None:
    """Return the translation for an orchestration event, or ``None`` if unmapped.

    ``None`` means the orchestration fact has no Phase 11.22 platform event.  It
    is never guessed at, and the caller must not fabricate one.
    """

    return _ORCHESTRATION_TABLE.get(source_event_type)


def translate_kernel_event(source_event_type: str) -> SourceTranslation | None:
    """Return the translation for a kernel event name, or ``None`` if unmapped."""

    return _KERNEL_TABLE.get(source_event_type)


def translated_platform_event_types() -> tuple[str, ...]:
    """Return the distinct platform event names reachable through translation."""

    names = {
        translation.platform_event_type
        for translation in (
            *ORCHESTRATION_SOURCE_TRANSLATIONS,
            *KERNEL_SOURCE_TRANSLATIONS,
        )
    }
    return tuple(sorted(names))


def translation_spec(platform_event_type: str) -> PlatformEventSpec:
    """Return the catalog row for a translated platform event name."""

    return catalog_spec(platform_event_type)


def is_canonical_runtime_event(event_type: str) -> bool:
    """Return whether *event_type* is already a canonical Phase 9 runtime event."""

    return event_type in {
        EventType.GOAL_CREATED,
        EventType.GOAL_UPDATED,
        EventType.OPERATION_EXECUTED,
        EventType.VALIDATION_COMPLETED,
    }
