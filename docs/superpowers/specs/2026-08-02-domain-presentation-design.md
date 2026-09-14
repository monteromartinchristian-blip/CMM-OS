# Phase 10.16 — Domain Presentation Design

## Approved design

Phase 10.16 introduces a deterministic Domain Presentation layer over
structured, already-resolved domain results.  It has no authority over
reasoning, workflow, execution, memory, source selection, or rendering.

`DomainPresentationPlanner` receives a `DomainPresentationRequest` carrying
the effective `DomainPresentationPolicy`, `PresentationComposition`, logical
`DomainOutputIntent`, and reference-only upstream items.  It returns a
`DomainPresentationPlan`.  `DomainPresentationPreservationValidator` compares
the plan to the request and returns `DomainPresentationValidationResult` with
`VALID` or `BLOCKED` state.

The policy extension is additive at the end of the existing frozen
`DomainPresentationPolicy`, preserving previous payloads and positional
construction.  It covers required/optional/suppressible sections, preferred
order, protected terminology and glosses, components/views, warning position,
and allowed/preferred logical outputs.  It deliberately excludes tone,
personality, channel, question selection, urgency, escalation, cognitive
strategy, and execution.

The logical output taxonomy is closed: `HUMAN_READABLE`, `STRUCTURED`,
`UI_COMPONENTS`, `ARTIFACT_REQUEST`.  PDF/DOCX/HTML are preferences under
`ARTIFACT_REQUEST`; they neither render files nor authorize production.
`DomainProductionPolicy` remains the separate contract for draft/final,
review, validation, and external-action controls.

`DomainPresentationItemRef` transports IDs and minimum safe, resolved metadata
only.  It has no content, evidence body, prompt, provider payload, or mutable
claim value.  This avoids coupling to Cognitive and Agent Runtime while
allowing references to findings, gaps, warnings, contradictions, questions,
approvals, escalations, workflows, and memory proposals.

Multi-domain reconciliation is monotonic for safety: required sections,
visibility obligations, and protected terms are unioned.  Incompatible glosses
or components become typed conflicts.  Primary-domain preferences cannot hide
supporting safety information.  Deterministic canonical ordering removes input
mapping-order effects.

Warning priority is not recomputed: it is optional upstream metadata.  The
planner uses it where available and otherwise preserves `source_order`.

The preservation validator is the phase boundary.  It detects reference loss
or invention, illegal duplicates, suppression of required content, reordering
that violates upstream warning priority, provenance loss, and all prohibited
epistemic mutations.  It cannot recover or inspect source content.

## Interfaces and dependency direction

The public surface is in `cmm.domains`.  Presentation modules may depend on
domain contracts and the standard library, but not `cmm.cognitive` or
`cmm.agent_runtime`.  Existing upstream systems adapt their resolved objects to
item references at their boundary.

No new Claim model, Knowledge Store, Knowledge Graph, provenance system,
temporal engine, persistent memory, renderer, document generator, or provider
integration is created.
