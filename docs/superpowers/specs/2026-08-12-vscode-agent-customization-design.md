# VS Code Agent Customization — Design

Date: 2026-08-12  
Status: Approved  
Scope: Personal/global development environment + CMM OS workspace specialization

## 1. Objective

Turn VS Code Agent Customizations into an operational development environment for CMM OS rather than a passive collection of prompts, skills, agents, and hooks.

The environment must:

- reduce manual orchestration;
- allow long autonomous implementation cycles;
- preserve human control at sensitive boundaries;
- enforce testing and Git policies deterministically;
- maintain independent architecture and audit review;
- reuse a global personal engineering layer across repositories;
- specialize behavior for CMM OS without duplicating global definitions;
- keep agent roles, skills, prompts, instructions, hooks, and MCP responsibilities distinct.

## 2. Conceptual Model

```text
Instructions = how work must always be performed
Skills       = reusable procedures for specific classes of work
Prompts      = explicit high-level actions initiated by the user
Agents       = roles responsible for performing work
Hooks        = deterministic invariants that cannot be bypassed
MCP          = external capabilities and data sources
```

## 3. Configuration Layers

Two configuration layers will be maintained.

### 3.1 Global personal layer

Reusable across repositories.

Contains:

- global engineering instructions;
- generic engineering agents;
- reusable engineering skills;
- global safety hooks;
- external MCP capabilities that are useful across projects.

### 3.2 CMM OS workspace layer

Versioned with CMM OS.

Contains:

- CMM-specific agent specializations;
- architecture and engineering rules;
- testing policy;
- Git and safety policy;
- CMM-specific skills;
- operational prompts;
- deterministic workspace hooks;
- workspace-specific MCP configuration when necessary.

Workspace configuration must add CMM OS knowledge and policy rather than copy the complete global configuration.

## 4. Agent Architecture

### 4.1 Global agents

```text
Engineer
Architect
Debugger
Auditor
Researcher
```

### 4.2 CMM OS agents

```text
CMM Engineer
CMM Architect
CMM Debugger
CMM Auditor
CMM Researcher
```

There is no assumed formal inheritance mechanism between global and CMM agents.

Reuse is achieved through shared global instructions and thin CMM-specific agent definitions.

## 5. Agent Responsibilities

### 5.1 CMM Engineer

Primary entry point and autonomous worker.

Responsibilities:

- inspect repository state;
- understand requested work;
- identify existing implementation before creating new components;
- implement changes;
- edit and create files;
- run tests and validation;
- repair failures;
- delegate specialist work;
- integrate specialist results;
- update documentation when required;
- commit completed work after the commit gate passes.

It may autonomously:

- inspect;
- edit;
- create;
- perform non-critical deletion;
- test;
- lint;
- format;
- run diagnostics;
- delegate;
- repair;
- inspect Git state and diffs;
- commit after validation.

It may not autonomously:

- push;
- merge;
- publish releases;
- create release tags;
- expose or modify secrets;
- perform material destructive operations;
- perform irreversible external actions;
- materially broaden permissions.

### 5.2 CMM Architect

Automatic architectural gate for structurally significant work.

Triggers include:

- new public contracts;
- new architectural layers;
- new subsystems;
- provider/model abstractions;
- persistence or migrations;
- registries;
- cross-phase dependencies;
- cross-domain changes;
- transversal changes;
- suspected duplication of existing architecture.

It does not implement.

Allowed decisions:

```text
APPROVE
APPROVE_WITH_CONSTRAINTS
BLOCK
```

### 5.3 CMM Debugger

Strong diagnostic specialist.

Triggered automatically for:

- difficult test failures;
- regressions;
- flaky tests;
- behavior inconsistent with contracts;
- failed Engineer repair attempts;
- symptoms suggesting a common underlying cause.

It diagnoses before suggesting repair and does not modify code.

Output should include:

- reproduction;
- root cause;
- affected boundary;
- evidence;
- recommended fix;
- regression tests;
- confidence.

### 5.4 CMM Auditor

Independent adversarial reviewer.

It is read-only.

It reviews:

- implementation;
- specification compliance;
- contracts;
- architecture;
- tests;
- diffs;
- regressions;
- edge cases;
- closure evidence.

Results:

```text
PASS

or

FINDINGS
- critical
- high
- medium
- low
```

Blocking findings return control to CMM Engineer.

After remediation, CMM Auditor must independently revalidate.

### 5.5 CMM Researcher

External research specialist.

It is not automatically triggered by task type.

CMM Engineer invokes it explicitly when external evidence is required.

Typical uses:

- official documentation;
- APIs;
- libraries;
- standards;
- provider behavior;
- external technical decisions.

It should prioritize primary and official sources.

It does not modify repository code.

## 6. Delegation Model

```text
User
 ↓
CMM Engineer
 ├── CMM Architect   [automatic structural trigger]
 ├── CMM Debugger    [automatic failure trigger]
 ├── CMM Researcher  [explicit Engineer decision]
 └── CMM Auditor     [automatic closure trigger]
```

Specialists return results to CMM Engineer.

Specialists should not recursively create arbitrary specialist chains.

Subagent recursion remains disabled unless a future use case explicitly justifies it.

## 7. Autonomy Policy

The selected autonomy profile is productive/high-autonomy.

CMM Engineer is expected to complete normal implementation cycles without asking for routine confirmation.

The system must ask the user before:

- `git push`;
- merge;
- release or tag publication;
- significant destructive changes;
- secrets or credential changes;
- irreversible external actions;
- material permission changes.

A clean validated block may be committed automatically.

## 8. Model Routing Policy

Model use follows adaptive quality.

Routine or mechanical work should prefer abundant/low-cost models.

Escalation to stronger reasoning models is appropriate for:

- difficult architecture;
- ambiguous failures;
- high-impact changes;
- adversarial audit;
- large context;
- repeated failed attempts;
- uncertainty above the accepted threshold.

Routing is role- and task-aware rather than binding every agent permanently to one model.

Fallback must never weaken security, privacy, or operational restrictions.

## 9. Instructions

Four responsibility-separated instruction sets are required.

### Global

```text
Global Engineering Instructions
```

### CMM OS workspace

```text
CMM OS Engineering Instructions
CMM OS Safety & Git Policy
CMM OS Testing Policy
```

### 9.1 Global Engineering Instructions

Contain reusable engineering behavior:

- inspect before editing;
- understand root cause before patching;
- keep changes focused;
- preserve compatibility;
- avoid accidental architectural debt;
- validate claims with evidence;
- document proportionally;
- maintain clean commits.

### 9.2 CMM OS Engineering Instructions

Contain project-specific behavior:

- search for existing capabilities before adding new ones;
- do not duplicate kernel, memory, planners, runtime, validation, cognition, agents, domains, or other shared infrastructure;
- preserve established contracts;
- follow the active roadmap specification;
- correct deficiencies in their owning component rather than bypassing them elsewhere;
- maintain compatibility across completed phases;
- prefer implementation over extended architecture discussion.

### 9.3 CMM OS Safety & Git Policy

Defines operational boundaries and Git authorization.

### 9.4 CMM OS Testing Policy

Defines adaptive validation requirements.

## 10. Adaptive Validation

### Level 1 — Local change

Run directly affected tests and relevant static checks.

### Level 2 — Component change

Run component tests and related integrations.

### Level 3 — Transversal or contract change

Run consuming suites, integration tests, and architecture checks.

### Level 4 — Milestone / phase / release

Require expanded or global validation plus independent audit.

The full suite is mandatory for:

- phase closure;
- release closure;
- material transversal changes where partial evidence is insufficient.

The full suite is not required after every small edit.

## 11. Skills

Existing skills must be audited before new skills are added.

Every current skill receives one disposition:

```text
KEEP
MOVE
MERGE
RETIRE
```

A skill must represent a reusable procedure.

Rules:

- permanent behavior belongs in Instructions;
- one-shot user actions generally belong in Prompts;
- duplicate procedures are merged;
- obsolete or redundant procedures are retired;
- triggers and outputs must be explicit.

Initial CMM skill targets:

```text
cmm-phase-implementation
cmm-architecture-review
cmm-audit
cmm-validation
cmm-milestone-close
cmm-provider-integration
```

These are targets, not permission to duplicate useful existing skills.

## 12. Prompts

Seven explicit user-facing operational prompts:

```text
/implement
/audit
/close-milestone
/review-architecture
/diagnose
/phase-status
/release-check
```

Prompts must remain thin.

They invoke an appropriate agent/workflow rather than duplicating methodology.

Example:

```text
/close-milestone 10.23
        ↓
CMM Engineer
        ↓
adaptive validation
        ↓
CMM Auditor
        ↓
remediation if required
        ↓
revalidation
        ↓
commit gate
        ↓
commit
```

## 13. Hooks

Hooks provide deterministic enforcement.

Initial workspace hooks:

```text
safety
git-policy
commit-gate
agent-audit
```

### Safety

Block:

- workspace escapes;
- dangerous destructive commands;
- prohibited file operations;
- unauthorized modification of protected guardrail files.

### Git policy

Block autonomous:

- push;
- merge;
- tags;
- releases;
- destructive repository resets.

### Commit gate

Intercept commit attempts and require validation evidence appropriate to the impact level.

A model statement such as "tests passed" is not sufficient evidence.

### Agent audit

Record lightweight specialist lifecycle information:

- agent;
- task;
- delegation reason;
- model when available;
- start;
- finish;
- result.

Guardrail scripts must themselves be protected against unauthorized self-modification.

## 14. Loop Protection

Autonomy must not become uncontrolled iteration.

Initial limits:

```text
Engineer repair attempts before Debugger: 2

Auditor remediation cycles: 3

Architect redesign after BLOCK: 1
Second material BLOCK: escalate to user
```

Limits may later become configuration values.

## 15. Tool Boundaries

### CMM Engineer

```text
read
search
edit
terminal
git inspection
tests
subagents
commit subject to gate
```

### CMM Architect

```text
read
search
diff inspection
NO normal edit
NO commit
```

### CMM Debugger

```text
read
search
terminal
tests
diff inspection
NO edit
NO commit
```

### CMM Auditor

```text
read
search
tests where appropriate
diff inspection
NO edit
NO commit
```

### CMM Researcher

```text
read
search
external documentation/research
NO edit
NO commit
```

Least privilege is preferred over exposing every tool to every agent.

## 16. MCP Policy

MCP use is selective.

Initial priorities:

- GitHub where it provides meaningful repository capability;
- external technical documentation/research.

Before adding MCP servers:

1. inspect the two existing servers;
2. determine actual usage;
3. keep only capabilities that justify maintenance and security cost.

Do not add databases, browser automation, observability, n8n, or other MCP servers preemptively.

Add them when concrete CMM OS work requires them.

Credentials must never be stored in versioned MCP configuration.

## 17. Target Physical Structure

### Global

```text
~/.copilot/
├── agents/
│   ├── engineer.agent.md
│   ├── architect.agent.md
│   ├── debugger.agent.md
│   ├── auditor.agent.md
│   └── researcher.agent.md
├── instructions/
│   └── global-engineering.instructions.md
├── skills/
│   └── ...
└── hooks/
    └── global-safety.json
```

Exact user-level paths must be verified against the installed VS Code/Copilot version before migration.

### CMM OS workspace

```text
.github/
├── agents/
│   ├── cmm-engineer.agent.md
│   ├── cmm-architect.agent.md
│   ├── cmm-debugger.agent.md
│   ├── cmm-auditor.agent.md
│   └── cmm-researcher.agent.md
├── instructions/
│   ├── cmm-engineering.instructions.md
│   ├── cmm-safety-git.instructions.md
│   └── cmm-testing.instructions.md
├── skills/
│   └── ...
├── prompts/
│   ├── implement.prompt.md
│   ├── audit.prompt.md
│   ├── close-milestone.prompt.md
│   ├── review-architecture.prompt.md
│   ├── diagnose.prompt.md
│   ├── phase-status.prompt.md
│   └── release-check.prompt.md
└── hooks/
    └── ...

.vscode/
└── mcp.json

scripts/
└── agent/
    └── guardrail and validation scripts
```

Exact VS Code schemas and supported paths must be verified before implementation.

## 18. Existing Customization Migration

Current visible baseline:

```text
Agents        2
Skills       32
Instructions 2
Prompts       7
Hooks         4
MCP Servers   2
Plugins       1
```

No existing component is deleted blindly.

Implementation begins with a complete inventory.

For every item record:

- name;
- scope;
- path;
- purpose;
- trigger;
- tools;
- overlap;
- current usefulness;
- disposition;
- migration target.

The objective is not to maximize counts.

Every remaining customization must have a clear reason to exist.

## 19. Testing

The customization layer itself must be tested.

Minimum validation:

- schemas parse;
- referenced files exist;
- agent definitions load;
- tool restrictions are effective;
- prohibited Git operations are blocked;
- allowed commands remain usable;
- commit gate accepts valid evidence;
- commit gate rejects insufficient evidence;
- guardrail scripts cannot be trivially bypassed through path manipulation;
- workspace boundary protection works;
- specialist delegation routes correctly;
- Auditor remains read-only;
- Debugger remains non-editing;
- global and workspace layers coexist without contradictory rules.

## 20. Documentation

The repository must document:

- available CMM agents;
- when each agent is invoked;
- prompts;
- skills;
- Git policy;
- validation levels;
- manual approval boundaries;
- troubleshooting;
- how to change the configuration safely.

## 21. Implementation Order

Implementation must be iterative.

### Block 1 — Inventory and classification

Inventory existing:

- agents;
- skills;
- instructions;
- prompts;
- hooks;
- MCP;
- plugin.

Classify each as KEEP / MOVE / MERGE / RETIRE.

No destructive migration yet.

### Block 2 — Instruction foundation

Create global and CMM instruction layers.

### Block 3 — Agent architecture

Create the five global and five CMM agent definitions.

Validate tool boundaries and delegation.

### Block 4 — Skills and prompts

Curate existing skills and implement only missing CMM procedures.

Normalize the seven prompts.

### Block 5 — Hooks

Implement deterministic safety, Git, commit-gate, and agent-audit hooks.

Add tests.

### Block 6 — MCP cleanup

Audit existing MCP servers and normalize scope/configuration.

### Block 7 — End-to-end validation

Execute representative flows:

1. normal implementation;
2. architecture gate;
3. failing test → debugger;
4. milestone → auditor;
5. audit findings → remediation → reaudit;
6. green autonomous commit;
7. blocked push;
8. blocked dangerous operation.

## 22. Success Criteria

The configuration is successful when the user can give CMM Engineer a concise implementation objective and the environment can autonomously:

```text
inspect
↓
understand
↓
consult architecture when needed
↓
implement
↓
test
↓
diagnose failures
↓
repair
↓
audit closure
↓
revalidate
↓
commit
```

without requiring routine orchestration from the user.

The user remains the mandatory decision-maker for sensitive or externally consequential boundaries.

## 23. Non-Goals

This iteration will not:

- maximize the number of customizations;
- create dozens of agents;
- add MCP servers without a concrete requirement;
- replace CMM OS internal architecture with VS Code automation;
- allow unrestricted autonomous Git publication;
- allow the Auditor to repair its own findings;
- build a new model gateway inside VS Code;
- duplicate roadmap or phase specifications inside permanent instructions.
