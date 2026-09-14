# Phase 10.17 — Domain Trace Design

## Approved design

Phase 10.17 records an immutable, deterministic and serializable account of
domain participation in an already-completed execution.  `DomainTrace` does
not retain an objective, prompt, payload, claim, finding body, reasoning text,
or any other upstream value.  It refers only to stable identifiers.  Request
and goal identity are references (`request_id` and optional `goal_id`).

`DomainTraceAssemblyRequest` receives primary and supporting domain IDs,
reference-only per-domain contributions, typed global references, existing
result/trace pairings, timestamps, final status, and metadata.  It has no
dependency on persistence, registries, network, memory, Cognitive, or Agent
Runtime.  `DomainTraceAssembler` canonicalizes valid input, derives duration,
digest and ID, and returns the final aggregate. Both contract and serialized
mapping inputs are equivalent, and DomainResult pairings are sorted by stable
domain/result/trace identity before hashing. `DomainTrace` itself shares the
participant invariant function with the request and assembler, and canonicalizes
supporting domains, contributions, nested references, global collections and
pairings during direct construction and deserialization.

Each `DomainTraceContribution` has exactly one domain and role.  There is one
primary contribution first and one supporting contribution for every supporting
domain in deterministic ID order.  `DomainTraceReferences` is a closed,
typed set of global reference categories: resolution context/result,
composition, optional AgentTrace, cognitive results, reasoning traces,
Knowledge Packages, cross-domain result/trace pairings, and Phase 10.16 plans
and validation results.  Per-domain contributions carry resource resolution,
profile/profile-trace, rule plan/result/trace, operation result, workflow
run/result, permission decision, approval request/decision, finding, gap,
contradiction, warning, and DomainResult IDs.

`DomainTraceReferenceInventory` is the validator's external, typed evidence:
it indexes each ID by category and owning domain and records valid upstream
cross-domain-result-to-trace and DomainResult-to-trace pairings.  An ID in a
different category is not interchangeable.  `DomainTraceReferenceValidator`
compares a trace with this inventory and blocks missing, unexpected, duplicate,
misclassified, misattributed, and incorrectly paired references, invalid
timestamps/durations/statuses, unsafe metadata/inline content, and altered
digest/ID.

The inventory carries authoritative primary/supporting selections from the
resolution result and composition. Each selection includes the source ID and
must match the corresponding trace reference. It rejects an ID repeated across category or
domain identities, requires exact DomainResult contribution/pairing coverage,
and preserves the original upstream cross-domain trace ID rather than replacing
it with the Domain Trace ID. The result and trace IDs in that pairing resolve as
distinct `CROSS_DOMAIN_RESULT` and `CROSS_DOMAIN_TRACE` categories.
Both pairing IDs are mandatory; an absent or invalid upstream trace ID is a
contract/serialization failure and is never converted into a partial trace.

Metadata is bounded, deeply immutable JSON data.  It rejects recursively
normalized private keys and values including prompts, raw content/payloads,
credentials, chain-of-thought, raw reasoning, and provider/tool traffic while
allowing safe reference names such as `reasoning_trace_id`,
`knowledge_package_id`, `provider_audit_id`, and `cross_domain_trace_id`.
Tokenization recognizes separators, camelCase and PascalCase without applying
an indiscriminate substring ban.

Final states are `COMPLETED`, `PARTIAL`, `BLOCKED`, `FAILED`, and `CANCELLED`.
The validator fails closed for mutated frozen objects and returns categorized
reference differences, invariant failures, trace digest, and canonical
inventory digest. Corrupt diagnostic values are represented by stable digest
labels rather than copied verbatim, and contradictory validation states are
rejected by the result contract.
The validator also reconstructs the complete final structural payload and the
external inventory in isolated fail-closed blocks. All deserializers reject
non-string or unknown keys without sorting heterogeneous types or echoing
payload values.

No cross-domain transfer trace type, additional `AgentTrace`, `ReasoningTrace`,
`KnowledgePackage`, store, streaming interface, provider/model audit, or
runtime dependency is created.
