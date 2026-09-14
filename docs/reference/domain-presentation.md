# Domain Presentation (Phase 10.16)

## Purpose and boundary

Phase 10.16 transforms an already-resolved domain result into an immutable,
structured presentation plan.  It does not reason, retrieve, execute, render,
or persist information.

The boundary is:

```text
structured upstream references + PresentationComposition + DomainPresentationPolicy
    + logical output intent
→ DomainPresentationPlanner
→ DomainPresentationPlan
→ DomainPresentationPreservationValidator
→ VALID | BLOCKED
```

The plan contains only identifiers, categorisations already resolved upstream,
ordering, visibility obligations, terminology/gloss instructions, and logical
component descriptors.  It never contains rendered prose or copied claim,
finding, evidence, prompt, or provider values.

## Architectural rules

- Presentation may render a question, warning, escalation, approval, workflow,
  or memory proposal already resolved upstream; it must not decide any of them.
- It must not create facts, alter epistemic kind or confidence, elevate a
  recommendation to a decision, or turn a hypothesis into a diagnosis.
- Required sections cannot be suppressed.  Optional sections can be omitted
  when empty.  Suppressible sections can be hidden only when they are not
  required by the effective policy or composition.
- Protected terminology is preserved verbatim.  A glossary is an explanatory
  complement and never substitutes a protected term.
- Warning priority is upstream data.  Warnings order by that priority when
  present and otherwise by the original `source_order`; their severity is never
  inferred or changed here.
- A logical request for PDF, DOCX, or HTML produces `ARTIFACT_REQUEST`, not a
  file.  Artifact lifecycle and real renderers remain Phase 11.
- `DomainPresentationPolicy` controls domain structure and visibility.
  `CommunicationProfile` (Phase 11.55) controls language, warmth, personality,
  rhythm, and channel.  Phase 11 renderers produce text/UI/artifacts.
- No Phase 8 cognitive, knowledge, provenance, temporal, or memory contract is
  duplicated.  This phase transports stable references only.

## Effective policy and composition

`DomainPresentationPolicy` is an additive profile contract.  Its presentation
fields describe required, optional, and suppressible sections; preferred order;
protected terminology and glosses; compatible components/views; warning
placement; and allowed/preferred logical output types.

`PresentationComposition` remains the effective multi-domain mapping created
by Phase 10.8.  The planner interprets its known presentation keys through a
typed view and records an explicit conflict when values cannot be reconciled.
It does not introduce a new free-form composition model.

For multiple domains, safety obligations are unioned; a primary preference
cannot remove a supporting safety obligation.  Required/suppressible overlaps,
incompatible protected-term glosses, and incompatible views are typed
conflicts.  Ordering is canonical and independent of input mapping order.

## Contracts

The public contracts are deliberately generic and do not import Cognitive or
Agent Runtime types:

- `DomainPresentationRequest` carries safe source IDs, the effective policy and
  composition references, and ordered `DomainPresentationItemRef` values.
- `DomainPresentationItemRef` identifies an upstream object and retains only
  minimum, already-resolved metadata: kind, epistemic kind, confidence band,
  provenance requirement, visibility, warning priority, and source order.
- `DomainOutputIntent` is a closed logical taxonomy: `HUMAN_READABLE`,
  `STRUCTURED`, `UI_COMPONENTS`, and `ARTIFACT_REQUEST`.
- `DomainPresentationSectionPlan`, `DomainPresentationComponentDescriptor`,
  `DomainPresentationConflict`, and `DomainPresentationDecision` make choices
  inspectable without copying content.
- `DomainPresentationPlan` contains sections, references, components,
  terminology/glosses, conflicts, decisions, visibility obligations, and
  reference-only downstream objects.
- `DomainPresentationValidationResult` reports deterministic preservation
  checks and returns `VALID` or `BLOCKED` without chain-of-thought or sensitive
  content.

All contracts are frozen, strictly validated, deterministically serializable,
and round-trip through `to_dict`/`from_dict`.

## Validation

The preservation validator blocks unknown, lost, or introduced references;
mandatory-section suppression; incompatible output intent; illegal duplicates;
warning priority reordering; lost required provenance; and semantic mutations
to upstream metadata (including confidence, epistemic kind,
recommendation/decision, or hypothesis/diagnosis).  A blocked result carries
safe codes and IDs only.

## Non-goals

This phase does not select a Socratic/directive/reflexive/analytic mode,
identify gaps, choose questions, classify urgency, select escalation, select or
run workflows/operations, access memory, make approval decisions, retrieve
sources, create documents, or communicate with a provider.

The canonical requirement and source-coverage evidence remains the
[Domain Intelligence Requirements Matrix](domain-intelligence-requirements-matrix.md)
and [Domain Prompt Clause Coverage](../audits/domain-prompt-clause-coverage.md).
