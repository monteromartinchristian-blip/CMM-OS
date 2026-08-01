# Phase 10.12 Domain Rules Design

## Status

Approved by the Phase 10.12 implementation brief for autonomous execution.

## Objective

Provide one deterministic, provider-independent rule infrastructure that registers and executes global, security and domain reasoning rules through the Phase 8 Cognitive Layer. Phase 10.11 remains declarative: `ResolvedDomainProfile` says which rules are required, optional or prohibited; Phase 10.12 resolves those references into an auditable execution plan and evaluates it without persistence or side effects.

## Approaches Considered

1. **One cognitive registry with thin domain specializations (selected).** A common `ReasoningRule` protocol, definition, context, result, registry and engine live in `cmm.cognitive`. Domain contracts add domain identity and selection/execution orchestration without owning a second registry. This preserves one cognitive layer and allows domain rules to satisfy the common protocol structurally.
2. **Separate cognitive and domain registries.** Rejected because active versions, collision handling and inspection would diverge and domain execution could bypass global rules.
3. **Compile rules into Phase 10.11 profiles.** Rejected because it would mix serializable configuration with executable implementations and duplicate the profile resolver.

## Architecture

```text
ResolvedDomainProfile (10.11) + optional DomainComposition (10.8)
             + explicit global/security/request references
             + effective permissions + selection policy
                              |
                              v
                     DomainRuleSelector
                              |
                   DomainRuleExecutionPlan
                              |
           ReasoningRuleRegistry + immutable context
                              |
                              v
                   DomainRuleExecutor
                              |
                  DomainRuleExecutionResult
```

`cmm.cognitive` never imports `cmm.domains`. The cognitive engine can execute an explicit ordered tuple of registered rules; it has no hidden registry and catches only the typed controlled failure raised by a rule. Domain selection and domain aggregate execution remain separate services.

## Cognitive Contracts

`ReasoningRuleDefinition` is the single versioned definition for all rules. It contains canonical ID, name, SemVer, scope, optional domain ID, category, status, priority, permissions, risk, determinism, description and deeply immutable JSON-safe metadata. `DomainReasoningRuleDefinition` is a validating specialization, not a copy.

`ReasoningRuleContext` contains immutable Phase 8 `KnowledgeItem` and `Contradiction` tuples, typed reasoning gaps, active/primary/supporting domain IDs, explicit permissions, risk/sensitivity, aware timestamp and metadata. It contains no clients, stores, callbacks or runtime objects.

Findings, recommendations, escalation, gaps and trace entries are small typed contracts with stable codes, safe messages, source rule/domain, references and immutable metadata. `ReasoningRuleResult` preserves Phase 8 knowledge and contradictions. `DomainRuleResult` adds mandatory domain identity while retaining common result semantics.

## Registry and Versioning

`InMemoryReasoningRuleRegistry` stores executable implementations keyed by `(id, version)`, validates the operational protocol without executing a rule, rejects collisions, and resolves the highest enabled semantic version. Listings return deterministic tuples and definitions only when inspecting. Disabled versions remain registered. No singleton, discovery, filesystem or persistence exists.

Rule references accept `id` or `id@version`; parsing is internal and exact versions use strict SemVer. Active resolution uses semantic, never lexical, ordering.

## Selection

The selector consumes an explicit registry, a resolved 10.11 profile, optional 10.8 composition, explicit global mandatory/security/requested IDs, permissions and a policy. It never accesses a profile/domain registry or recomposes either input.

Selection groups are: global mandatory, security, primary domain, supporting domains, optional and presentation. Within a group, rules sort by descending priority, domain precedence, ID and semantic version. Exact duplicates collapse while retaining all `DomainRuleSource` records.

Required missing, disabled, prohibited, domain-mismatched or permission-denied rules create blocking conflicts. Optional failures create traced exclusions and `partial`. Prohibited overrides optional; attempting to prohibit a global mandatory rule blocks and never removes it silently. A ready plan contains only executable, compatible definitions.

## Execution

The executor rejects blocked/failed plans without running rules. Every selected rule receives the same original immutable context. Registry resolution must exactly match the planned ID/version and each returned result must match ID/name/version/domain.

Controlled `ReasoningRuleExecutionError` becomes a failed individual result with a stable safe code. Contract/programming errors propagate. Required failure stops execution and yields `failed`; optional failure continues and yields `partial`. Aggregate precedence is `blocked > failed > partial > completed > no_applicable_rules`. Per-rule confidence delta is bounded to `[-1, 1]`; aggregate delta is clamped to `[-1, 1]` without modifying knowledge confidence.

## Initial Catalog

The catalog exposes production-grade definitions for all IDs named in the brief. Global and security rules have conservative structural implementations. Domain-pack rules remain disabled unless their semantics can be expressed safely from common contracts; no stub reports false success. Reference rules demonstrate non-applicability, a gap, escalation and permission blocking without model calls or text-generation heuristics.

## Error Handling and Safety

Cognitive and domain rule errors follow existing hierarchies with stable codes, `field` and deeply frozen safe `details`. Expected selection conflicts are serialized results. Broad exception catches, exception-string leakage, arbitrary callbacks, I/O, operations, workflows, persistence and model providers are forbidden.

## Testing

Tests cover strict construction/serialization, deep immutability, registry versions and collisions, 10.11 required/optional/prohibited integration, 10.8 ordering/provenance, global/security preservation, permissions, deterministic plans, execution isolation and mismatch checks, aggregate states, catalog behavior, public API/import order and forbidden dependencies. Focused suites precede cognitive/domain/validation/runtime/global suites, Ruff, compileall and diff checks.

## Scope Boundary

Phase 10.12 proposes knowledge but never persists it. It does not implement Domain Operations, Workflows, runtime authorization, presentation rendering, persistent Domain Trace, full Domain Packs, SDK, API/CLI, Agent Runtime integration, LLM calls, filesystem discovery or networking.
