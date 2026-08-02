# Phase 10.16 — Domain Presentation Implementation Plan

1. Extend `DomainPresentationPolicy` additively and merge its new structural
   fields with monotonic multi-domain safety semantics.
2. Add typed, frozen, strict domain-presentation contracts, closed enums,
   deterministic canonical serialization/digests, and a presentation error
   hierarchy.
3. Add a deterministic planner that uses only references and resolved metadata
   to plan sections, warnings, components, terminology, visibility, and logical
   output intent.
4. Add a preservation validator that blocks illegal reference, ordering,
   visibility, output-intent, provenance, and epistemic changes.
5. Export only the contracts, planner, validator, and errors through
   `cmm.domains`; retain the no Cognitive/Agent Runtime dependency boundary.
6. Add focused contract, composition, planner, validator, serialization,
   public-API, and dependency-direction tests.  Run focal and full validation.
7. Update Phase 10 roadmaps only after all tests pass, then stage only the
   Phase 10.16 files without committing or pushing.

The implementation is constrained by
[domain-presentation.md](../../reference/domain-presentation.md) and by the
canonical requirement matrix; it does not design renderers or Phase 11
Communication Profiles.
