# Domain Trace

Phase 10.17 records which domains participated in an execution without copying
the execution's semantic content.  It is a final, frozen, deterministic and
JSON-serializable domain aggregate.  It is neither a store nor a runtime event.

## Boundary

`DomainTraceAssemblyRequest` accepts a `request_id`, optional `goal_id`,
primary/supporting domains, per-domain reference contributions, global typed
references, upstream result pairings, timestamps, final status and safe
metadata.  `DomainTraceAssembler` is pure: it does not query a registry, store,
network, memory, Cognitive Layer or Agent Runtime.  It sorts supporting domains
and references, canonically sorts DomainResult pairings by domain/result/trace,
derives `duration_ms`, and derives a canonical SHA-256 digest and
`domain-trace:<digest-prefix>` ID. Its mapping interface consumes the exact
serialized form returned by `DomainTraceAssemblyRequest.to_dict()`.
`DomainTrace` applies the same canonicalization and participant invariants in
its own constructor and `from_dict()`, so direct reconstruction cannot bypass
ordering, role, uniqueness or exact-coverage rules.

There is exactly one primary contribution and one contribution for each
supporting domain.  Contributions can reference resource resolutions, profiles
and profile traces, rule plans/results/traces, operation results, workflow
runs/results, permission decisions, approvals, findings, gaps, contradictions,
warnings and DomainResults.  `DomainTraceReferences` is the closed global
reference surface for resolution context/result, composition, AgentTrace,
cognitive results, reasoning traces, Knowledge Packages, cross-domain results,
cross-domain traces, and Phase 10.16 presentation plans and validation results.

`DomainTraceReferenceInventory` is supplied by the caller to validate a trace.
It records each allowed reference's ID, category and owning domain, plus the
authoritative `DomainResult → DomainTrace` and `CrossDomainResult → DomainTrace`
pairings. Both members of a cross-domain pairing resolve independently as
`CROSS_DOMAIN_RESULT` and `CROSS_DOMAIN_TRACE`; IDs are not interchangeable
across categories.

The inventory is authoritative for participation: it carries expected
primary/supporting domains and selections from the resolution result and
composition. Each selection binds an explicit `source_id` to its domains, and
that ID must equal the trace's resolution-result or composition reference. A
self-consistent trace cannot override those upstream values. A
reference ID has exactly one category/domain identity, including the
global/domain boundary. Domain-result references in contributions must exactly
equal the `DomainResultTraceReference` pairing set.

`CrossDomainTraceReference` preserves the existing upstream trace ID for its
cross-domain result. That ID is distinct from `DomainTrace.id`; the assembler
only normalizes ordering and never rewrites the pairing. Both `result_id` and
`trace_id` are mandatory safe IDs; legacy payloads missing either are rejected.

## Validation and privacy

`DefaultDomainTraceReferenceValidator` blocks missing, unexpected and duplicate
references; category/domain mismatches; participation errors; invalid result
pairings; unsafe timestamps or duration; and changed ID/digest.  It also
revalidates recursive bounded JSON metadata.  Prompts, messages, objective
text, content/payloads, secrets, credentials, PII, chain-of-thought, raw
reasoning/resources, and tool/provider request-response data are rejected even
when written with spaces, hyphens, underscores or different case.  Safe IDs
are tokenized across snake/kebab case, spaces, camelCase and PascalCase. Safe
reference keys such as `reasoning_trace_id`, `knowledge_package_id`,
`provider_audit_id` and `cross_domain_trace_id` remain valid.

Validation reconstructs and compares the complete final `trace.to_dict()`
representation, not only metadata. It revalidates all IDs, domains, nested
references, source selections, timestamps and collections after defensive
mutation, detects injected fields such as `correlation_id`, and reports inline
content without copying the sensitive value into diagnostics. Deserializers
require string keys before checking unknown fields, so heterogeneous mappings
fail with a closed serialization error rather than an incidental `TypeError`.

Final states are `COMPLETED`, `PARTIAL`, `BLOCKED`, `FAILED`, and `CANCELLED`;
there is no running state. Validation fails closed for corrupted frozen objects
and returns stable codes rather than accidental attribute errors. Invalid IDs
in diagnostics are replaced with stable, non-revealing digest labels. Its result
reports categorized reference differences, invariant failures, trace digest,
and canonical `inventory_digest`: SHA-256 over normalized inventory references,
ownership, upstream domain selections, and both pairing sets.
Validation results reject contradictory `valid`/failure combinations.

This phase creates no cross-domain transfer trace type, AgentTrace, ReasoningTrace,
KnowledgePackage, persistence layer, event stream, provider audit, or runtime
dependency.  In particular, `cmm.agent_runtime` does not import `cmm.domains`.
