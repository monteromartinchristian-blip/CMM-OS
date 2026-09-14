# Domain Rules (Phase 10.12)

Domain Rules provide one rule infrastructure for global, security and domain reasoning. The common executable contract and registry belong to `cmm.cognitive`; `cmm.domains` converts an already-resolved Phase 10.11 profile into a plan and executes it while preserving Phase 10.8 domain precedence.

## Common Cognitive API

`ReasoningRuleDefinition` is the serialized rule identity and policy. Executable implementations satisfy the structural `ReasoningRule` protocol:

```python
class ReasoningRule(Protocol):
    @property
    def definition(self) -> ReasoningRuleDefinition: ...

    def evaluate(self, context: ReasoningRuleContext) -> ReasoningRuleResult: ...
```

Definitions are registered in an explicit `InMemoryReasoningRuleRegistry`. The registry supports multiple SemVer versions, retains disabled versions for inspection and resolves the highest enabled version semantically. It does not discover files, persist state or execute a rule during registration.

`ReasoningRuleContext` is immutable and contains only explicit cognitive/domain data, permissions, risk, sensitivity, an aware timestamp and JSON-safe metadata. Results use typed findings, recommendations, escalation, gaps and audit trace entries. Produced knowledge and contradictions reuse the Phase 8 `KnowledgeItem` and `Contradiction` contracts.

## Domain Selection

`DefaultDomainRuleSelector.select()` requires:

- the common registry;
- a `ResolvedDomainProfile` from Phase 10.11;
- optional `DomainComposition` output from Phase 10.8;
- explicit global mandatory and security references;
- explicit effective permissions;
- optional requested references and selection policy.

References use `rule.id` for active resolution or `rule.id@1.2.3` for an exact version. Selection order is global mandatory, security, primary domain, supporting domains, optional and presentation. Priority descends within a group; domain precedence, rule ID and semantic version break ties deterministically.

Required missing, disabled, prohibited, wrong-domain or permission-denied references block the plan. Equivalent optional failures produce `partial` and a traced omission. A prohibited global mandatory rule creates a blocking conflict and is never silently removed. References resolving to the same ID/version are deduplicated while all source records remain attached.

## Domain Execution

`DefaultDomainRuleExecutor.execute()` receives a plan, the original immutable context, the common registry and an optional execution policy. It executes only exact planned ID/version pairs, sequentially, and validates every result against the registered definition.

Aggregate status precedence is:

```text
blocked > failed > partial > completed > no_applicable_rules
```

A controlled required failure stops execution. A controlled optional failure is recorded and later rules continue. Every rule receives the same original context; outputs are aggregated in plan order. Confidence deltas remain individual, are summed and clamped to the configured bound, and never mutate `KnowledgeItem.confidence`.

## Initial Catalog

`build_initial_reasoning_rule_catalog()` returns a new registry instance with the declared global, security, health, university, relationship and project IDs. Global/security rules and a small set of conservative structured domain rules are enabled. Future Domain Pack rules remain registered but disabled, and return no false success if directly inspected/evaluated.

The catalog does not contain callbacks, provider clients, workflows, operations, stores, persistence or external I/O.

## Example

```python
registry = build_initial_reasoning_rule_catalog()
plan = DefaultDomainRuleSelector(clock=clock, id_factory=plan_id).select(
    registry=registry,
    profile=resolved_profile,
    global_mandatory_rules=("global.distinguish_fact_inference_hypothesis",),
    security_rules=("security.respect_sensitivity",),
    effective_permissions=("knowledge.health.read",),
)
result = DefaultDomainRuleExecutor(clock=clock, id_factory=result_id).execute(
    plan=plan,
    context=context,
    registry=registry,
)
```

Clocks and ID factories are injected in deterministic tests. Production defaults generate aware UTC timestamps and UUID-based IDs.
