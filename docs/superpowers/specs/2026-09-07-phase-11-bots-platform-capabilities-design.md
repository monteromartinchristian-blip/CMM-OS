# CMM OS — Phase 11 Amendment Design
## Bots, Platform Capabilities, Web, Browser and Computer Use

**Date:** 2026-09-07
**Status:** APPROVED DESIGN SPEC — INTEGRATED FOR PHASE 11 PLANNING
**Target repository:** `/Users/chris/CMM OS`
**Inspected branch:** `feature/phase-10-domain-intelligence`
**Initial architecture inspection HEAD:** `c2be54d9f2b1ccbcad8b3afd9717c746caf45755`
**Integration baseline HEAD:** `35ca06dfc72b2fbe470375f53c7fd1ac6868b431`
**Current worktree at inspection:** clean
**Quarantine stash at inspection:** preserved
**Current Phase 11 status:** planned
**Phase 10.44 at integration:** complete, independently audited and closed after final independent re-audit V4 `PASS`; `DP-044=VERIFIED_EXISTING`; `AT-DP-044=PASS`; `CLOSURE_ELIGIBLE=YES`.
**Integration date:** 2026-09-08

---

# 1. Purpose

This design extends **Phase 11 — Stable Integrated Platform** so CMM OS can expose user-facing **Bots** and a platform-wide **capability/tool model** without introducing parallel runtimes, permission systems, operation registries, approval systems, autonomy systems, budget systems, memory stores, or domain infrastructure.

The amendment adds three new Phase 11 subphases:

```text
11.59 — Bot Identity and Configuration Layer
11.60 — Platform Capability Catalog and Tool Resolution
11.61 — Web, Browser and Computer Use
```

These subphases are intended to become the canonical CMM OS foundation behind the future CMMChat Bot Workspace and Tools / Capabilities Workspace.

This design does **not** modify CMMChat. CMMChat integration is a later client/product task.

---

# 2. Problem Statement

CMM OS already contains mature infrastructure for:

- Phase 9 Agent Runtime;
- Agent Registry and resolution;
- canonical operation registration and execution;
- approvals;
- autonomy;
- action budgets;
- policy evaluation;
- validation;
- recovery;
- eventing;
- Domain Intelligence;
- Domain capabilities;
- Domain permissions;
- Model Gateway planning;
- plugins;
- external integrations;
- MCP / REST / Actions adapters.

However, CMM OS does not yet have a canonical first-class abstraction for a user-facing **Bot**.

It also lacks a canonical platform-level abstraction that clearly separates:

```text
capability
from
tool implementation
from
operation
from
agent
from
domain capability
```

Web search, browser navigation, and computer use are not yet implemented as shared platform capabilities.

Without an explicit architectural boundary, future product work risks creating:

- a second agent abstraction hidden inside Bots;
- a second executable Tool Registry;
- duplicated permission logic;
- duplicated approvals;
- duplicated autonomy controls;
- duplicated tool execution paths;
- inconsistent semantics between DomainCapability and platform capabilities;
- overly broad Computer Use permissions;
- capability escalation through model prompts or bot configuration.

This amendment prevents those failure modes before implementation begins.

---

# 3. Scope

## 3.1 In Scope

This amendment defines:

1. a first-class `BotDefinition` product-facing contract;
2. bot configuration and lifecycle semantics;
3. explicit `Bot != Agent` separation;
4. three bot execution modes:
   - `CONVERSATIONAL`;
   - `TOOL_ENABLED`;
   - `AGENT_BACKED`;
5. platform capability identifiers;
6. a read/resolve-oriented `PlatformCapabilityCatalog`;
7. separation between capability declaration and concrete tool implementation;
8. binding of tool execution to canonical operation/runtime infrastructure;
9. effective capability resolution;
10. Web Search as an independent capability;
11. Browser navigation as an independent capability;
12. Computer Use as a high-impact independent capability;
13. human-in-the-loop requirements for Computer Use;
14. audit/event requirements;
15. persistence/versioning requirements;
16. API and UI-facing contracts needed by future clients;
17. roadmap updates;
18. requirements-matrix updates;
19. public documentation alignment.

## 3.2 Out of Scope

This amendment does not implement:

- CMMChat UI;
- Bot visual design;
- Bot marketplace/discovery;
- social sharing;
- public bot publishing;
- payments;
- billing products;
- a new Agent Runtime;
- a new workflow engine;
- a new planner;
- a new executable Tool Registry;
- a new approval service;
- a new autonomy manager;
- a new budget service;
- a new DomainCapability model;
- a new memory store;
- a new Knowledge Store;
- a new event bus;
- a new validation engine;
- provider-specific web-search SDKs;
- provider-specific browser automation;
- a concrete Computer Use provider;
- OpenBot integration;
- BrowserSkill integration;
- CMM X Operator integration;
- secrets storage inside Bot definitions.

Those integrations may be introduced later as implementations of the contracts defined here.

---

# 4. Canonical Existing Infrastructure to Reuse

The amendment must reuse the existing canonical owners.

## 4.1 Agent Runtime

Canonical owner:

```text
cmm.agent_runtime
```

Bots may bind to an Agent, but must never own or replace:

- persistent goals;
- runtime state;
- planning;
- execution lifecycle;
- retries;
- re-observation;
- recovery;
- autonomy;
- budgets;
- checkpoints;
- approval state;
- event lifecycle.

## 4.2 Operation Registry and Execution

Canonical operation registration and execution remain the only executable operation path.

A platform tool may map to one or more canonical operations, but no new executable registry may bypass the existing operation infrastructure.

## 4.3 Approvals

Canonical Phase 9 approval infrastructure remains authoritative.

A Bot may request a lower-trust or stricter approval preference.

A Bot configuration must never weaken an approval requirement imposed by:

- global policy;
- user policy;
- session policy;
- Domain policy;
- operation policy;
- resource policy;
- sensitivity;
- security;
- autonomy;
- budget;
- integration policy.

## 4.4 Autonomy

Canonical autonomy remains owned by Phase 9.

Bot configuration may request an autonomy mode only within the effective canonical ceiling.

A Bot may never raise autonomy beyond the effective policy.

## 4.5 Budgets

Canonical Phase 9 action/economic budgets remain authoritative.

Bot-level limits may only:

- preserve;
- narrow;
- reduce.

They must never expand the effective budget.

## 4.6 Validation

Canonical Phase 7 Validation System remains authoritative.

Tool execution and Computer Use actions that mutate state must reuse validation where applicable.

## 4.7 Domain Intelligence

Existing DomainCapability and Domain permissions remain canonical for Domain specialization.

This amendment does not rename or replace `DomainCapability`.

The new platform capability layer must coexist with DomainCapability through explicit mapping and restrictive intersection.

## 4.8 Plugins, Integrations and Adapters

Existing/planned Phase 11 infrastructure remains responsible for concrete implementations:

- plugins;
- MCP;
- REST;
- Actions;
- external integrations;
- provider adapters;
- local adapters;
- remote adapters.

The capability layer describes what the platform can do.

Adapters provide how it is done.

---

# 5. Core Conceptual Model

```text
Bot
↓
User-facing identity and configuration
↓
Requested model/context/capability policy
↓
Effective policy resolution
↓
Optional Agent binding
↓
Canonical CMM OS execution/runtime path
↓
Canonical registered operation
↓
Plugin / Integration / Adapter / Provider
↓
External or local effect
```

The following concepts are distinct:

```text
Bot
Agent
PlatformCapability
DomainCapability
Operation
ToolImplementation
ModelCapability
Permission
Approval
Autonomy
Budget
```

No implementation may collapse these into one contract merely for convenience.

---

# 6. Terminology

## 6.1 Bot

A **Bot** is a user-facing AI identity and configuration.

It defines how a user-facing assistant is composed.

It may select or reference:

- identity;
- instructions;
- communication profile;
- model policy;
- reasoning preference;
- Domain context;
- knowledge scope;
- memory scope;
- requested platform capabilities;
- autonomy preference;
- optional Agent binding.

A Bot is not itself a runtime.

## 6.2 Agent

An **Agent** is a persistent execution/runtime entity owned by Phase 9.

An Agent may:

- pursue goals;
- observe;
- reason;
- plan;
- execute;
- recover;
- use budgets;
- request approvals;
- maintain runtime state.

A Bot may be backed by an Agent.

A Bot does not become an Agent merely because it can call tools.

## 6.3 Platform Capability

A **PlatformCapability** is a stable provider-independent identifier describing an ability CMM OS may expose.

Examples:

```text
web.search
browser.navigate
browser.read_authenticated
computer.use
files.read
files.write
code.execute
terminal.execute
image.generate
email.read
email.send
calendar.read
calendar.write
git.read
git.write
github.read
github.write
mcp.invoke
plugin.invoke
audio.ingest
```

A PlatformCapability is not executable by itself.

## 6.4 DomainCapability

Existing `DomainCapability` continues to describe capabilities declared by a Domain Pack.

Examples include reasoning, workflow, presentation, planning, reporting, or Domain-specific operations.

PlatformCapability and DomainCapability have different responsibilities.

Where they interact, effective permission is restrictive.

## 6.5 Tool Implementation

A **ToolImplementation** is a concrete implementation that can satisfy one or more PlatformCapabilities.

Examples:

```text
web.search
→ search integration adapter

browser.navigate
→ browser automation adapter

computer.use
→ approved computer-control adapter

email.send
→ email integration adapter
```

A ToolImplementation does not define user authority.

## 6.6 Operation

An **Operation** is the canonical executable contract used by CMM OS.

Tool implementations must ultimately execute through authorized canonical operation/runtime paths where side effects or controlled execution are involved.

---

# 7. Phase 11.59 — Bot Identity and Configuration Layer

## 7.1 Objective

Introduce a first-class product-facing Bot abstraction without duplicating Agent Runtime behavior.

## 7.2 Bot Modes

Canonical modes:

```text
CONVERSATIONAL
TOOL_ENABLED
AGENT_BACKED
```

### CONVERSATIONAL

A Bot may use:

- model/routing;
- instructions;
- Communication Profile;
- Domain context;
- knowledge;
- memory;
- normal conversation.

It has no persistent Agent execution requirement.

### TOOL_ENABLED

A Bot may request authorized PlatformCapabilities through the canonical execution path.

Tool access alone does not create an Agent.

### AGENT_BACKED

A Bot is user-facing while persistent execution is delegated to a bound canonical Phase 9 Agent.

The Bot remains a product identity.

The Agent remains the runtime authority.

## 7.3 BotDefinition Contract

Conceptual contract:

```python
BotDefinition(
    id="bot:research",
    display_name="CMM Research",
    slug="research",
    avatar_ref=None,
    description="Research assistant",
    instructions_ref="bot-instructions:research:v1",
    communication_profile_id="calm_authority",
    model_policy_id="model-policy:research",
    domain_ids=("domain:general",),
    knowledge_scope={},
    memory_scope={},
    requested_capability_ids=("web.search", "browser.navigate"),
    autonomy_mode="TOOL_ENABLED",
    agent_binding_id=None,
    status="active",
    version="1.0",
    created_by="user:...",
    metadata={},
)
```

## 7.4 Required Properties

Bot definitions must be:

- versioned;
- serializable;
- auditable;
- permission-aware;
- import/export compatible;
- recoverable;
- stable across provider changes;
- independent of UI implementation;
- independent of concrete tool providers.

## 7.5 Forbidden Bot Responsibilities

A Bot must not store:

- provider credentials;
- API keys;
- refresh tokens;
- cookies;
- unrestricted filesystem permissions;
- operating-system authorization tokens;
- arbitrary executable code;
- approval decisions;
- hidden permission grants;
- raw secrets.

## 7.6 Bot Lifecycle

Initial lifecycle:

```text
draft
active
disabled
archived
invalid
incompatible
```

Operations:

```text
create
read
update
duplicate
disable
enable
archive
export
import
```

Deletion policy should be defined later with preservation/audit requirements.

## 7.7 Agent Binding

`agent_binding_id` is optional.

Binding rules:

1. Binding does not grant permissions.
2. Binding does not increase autonomy.
3. Binding does not expand budgets.
4. Binding does not bypass approvals.
5. Binding does not bypass Domain restrictions.
6. Binding does not automatically enable Computer Use.
7. Binding does not transfer secrets.
8. Effective runtime authority is always recomputed.

---

# 8. Design Point DP-059

```text
DP-059
```

CMM OS must support a first-class Bot definition that is user-facing, versioned, provider-independent, optionally Agent-backed, and incapable of owning or bypassing canonical runtime authority.

A Bot must remain distinct from:

- Agent Runtime;
- Domain;
- Operation;
- PlatformCapability;
- ToolImplementation;
- Model provider.

The presence of tools or Agent binding must never itself grant executable authority.

## 8.1 Connected Acceptance

```text
AT-DP-059
```

The acceptance must prove through canonical in-memory implementations that:

1. a conversational Bot can exist with no Agent binding;
2. a tool-enabled Bot can request capabilities without becoming an Agent;
3. an agent-backed Bot resolves to an existing canonical Agent;
4. invalid Agent bindings fail closed;
5. binding cannot widen permissions;
6. binding cannot widen autonomy;
7. binding cannot widen budgets;
8. binding cannot remove required approvals;
9. secrets are absent from Bot serialization;
10. versioned Bot definitions round-trip deterministically.

---

# 9. Phase 11.60 — Platform Capability Catalog and Tool Resolution

## 9.1 Objective

Introduce a canonical provider-independent capability catalog without creating a second execution registry.

## 9.2 PlatformCapabilityDescriptor

Conceptual contract:

```python
PlatformCapabilityDescriptor(
    id="web.search",
    display_name="Web Search",
    category="web",
    description="Search authorized external information sources",
    risk_level="low",
    sensitivity="normal",
    mutating=False,
    external=True,
    available=True,
    requires_approval_by_default=False,
    execution_modes=("local", "remote"),
    implementation_refs=(),
    metadata={},
)
```

## 9.3 Catalog Responsibilities

`PlatformCapabilityCatalog` may:

- register descriptors;
- resolve descriptors;
- list descriptors;
- query by category;
- query by availability;
- expose implementation references;
- report health;
- report connection state;
- expose risk/privacy metadata;
- expose approval defaults.

It must not:

- execute tools;
- grant permissions;
- persist secrets;
- own approval state;
- own runtime state;
- replace the canonical operation registry.

## 9.4 Effective Capability Resolution

A requested capability must be intersected with all relevant restrictions:

```text
Bot requested capabilities
∩ user policy
∩ session policy
∩ Domain permissions
∩ resource permissions
∩ privacy policy
∩ sensitivity rules
∩ integration availability
∩ operation availability
∩ autonomy ceiling
∩ budget limits
∩ approval policy
= effective capability set
```

Most-restrictive semantics apply.

Explicit deny wins.

Missing authority fails closed for sensitive or mutating capabilities.

## 9.5 Capability States

Canonical user-facing/effective states:

```text
AVAILABLE
UNAVAILABLE
DISCONNECTED
BLOCKED_BY_POLICY
REQUIRES_APPROVAL
DEGRADED
UNSUPPORTED
```

These states describe capability resolution and availability.

They do not replace operation execution state.

## 9.6 Tool Resolution

Conceptual resolution:

```text
PlatformCapability
↓
Capability resolution
↓
Compatible implementation candidates
↓
Policy-compatible implementation
↓
Canonical operation
↓
Canonical runtime/execution
```

A concrete tool provider may be replaced without changing the Bot contract.

## 9.7 Initial Capability Groups

### Web

```text
web.search
browser.navigate
browser.read
browser.read_authenticated
```

### Computer

```text
computer.use
computer.application_interact
computer.human_handoff
```

### Files and Code

```text
files.read
files.write
code.execute
terminal.execute
```

### Productivity

```text
email.read
email.send
calendar.read
calendar.write
storage.read
storage.write
```

### Development

```text
git.read
git.write
github.read
github.write
```

### AI and Media

```text
image.generate
audio.ingest
audio.transcribe
```

### Extensions

```text
mcp.invoke
plugin.invoke
integration.invoke
```

This is an initial namespace only.

It is not a permanent closed list.

---

# 10. Design Point DP-060

```text
DP-060
```

CMM OS must expose a provider-independent Platform Capability Catalog that describes capabilities and resolves effective availability without executing them directly or replacing the canonical Operation Registry.

The effective capability set must always be no broader than every applicable permission, privacy, Domain, resource, autonomy, budget, approval, availability, and security constraint.

## 10.1 Connected Acceptance

```text
AT-DP-060
```

The acceptance must prove with canonical in-memory infrastructure that:

1. a capability descriptor can be registered and resolved;
2. duplicate incompatible capability definitions fail closed;
3. a Bot-requested capability does not imply authorization;
4. Domain policy can restrict a Bot capability;
5. user/session policy can restrict a Bot capability;
6. explicit deny wins;
7. missing required authorization fails closed;
8. approval-required state remains visible without becoming allowed;
9. an unavailable implementation remains unavailable;
10. a resolved tool executes only through a canonical operation/runtime path;
11. no second executable registry is introduced;
12. replacing the implementation does not change the Bot contract.

---

# 11. Phase 11.61 — Web, Browser and Computer Use

## 11.1 Objective

Introduce Web Search, Browser, and Computer Use as separate platform capabilities with progressively stronger authority and safety requirements.

They must not be represented as one generic `web` or `computer` boolean.

## 11.2 Separation

```text
web.search
!=
browser.navigate
!=
browser.read_authenticated
!=
computer.use
```

Granting one must never implicitly grant another.

## 11.3 Web Search

`web.search` is intended for:

- search queries;
- discovery;
- authorized retrieval;
- source listing;
- external information lookup.

It does not imply:

- browser control;
- authenticated sessions;
- downloads;
- filesystem write;
- arbitrary network requests;
- Computer Use.

## 11.4 Browser Navigate

`browser.navigate` is intended for:

- controlled page navigation;
- page reading;
- browser-backed interaction where authorized.

It does not imply:

- full operating-system control;
- unrestricted authenticated access;
- arbitrary credential use;
- external communication;
- file mutation.

## 11.5 Authenticated Browser

Authenticated-session use requires stronger policy.

Minimum requirements:

- explicit authorized session;
- scoped target/site access;
- credential/token isolation;
- no credential disclosure to the model;
- origin restrictions where supported;
- audit;
- user takeover;
- approval for sensitive effects.

## 11.6 Computer Use

`computer.use` is a high-impact capability.

Minimum controls:

- explicit capability grant;
- fail-closed authorization;
- application/resource scope;
- least privilege;
- visible active state;
- cancellation;
- human takeover;
- approval before sensitive or irreversible actions;
- credential isolation;
- session isolation where possible;
- audit trail;
- timeout;
- recovery after interruption;
- validation after mutations where applicable;
- no unrestricted shell access by implication;
- no permission inheritance merely from Agent binding.

## 11.7 Human-in-the-Loop

Computer Use must support a canonical human-handoff state.

Conceptual states:

```text
RUNNING_AUTOMATED
WAITING_FOR_HUMAN
HUMAN_CONTROL
RESUMING_AUTOMATION
COMPLETED
FAILED
CANCELLED
```

Human takeover must not corrupt execution authority.

On resume, effective permissions must be recomputed.

## 11.8 Side-Effect Classification

Computer/browser operations must classify effects.

Example:

```text
READ_ONLY
REVERSIBLE_MUTATION
EXTERNAL_COMMUNICATION
DESTRUCTIVE
FINANCIAL
SECURITY_SENSITIVE
CREDENTIAL_SENSITIVE
```

Higher-impact classes may require stronger approvals.

## 11.9 Provider Independence

The design must support future implementations such as:

- native browser adapters;
- browser-control frameworks;
- OpenBot;
- Tencent BrowserSkill;
- platform-specific Computer Use providers;
- remote desktop adapters;
- local automation runtimes.

None of these may become the core contract.

---

# 12. Design Point DP-061

```text
DP-061
```

CMM OS must implement Web Search, Browser, and Computer Use as separate, independently authorized capabilities, with Computer Use subject to explicit least-privilege authorization, human takeover, cancellation, audit, and stronger approval rules.

No capability may silently imply another.

## 12.1 Connected Acceptance

```text
AT-DP-061
```

The connected acceptance must prove:

1. `web.search` can be allowed while browser is denied;
2. browser can be read-only while Computer Use is denied;
3. authenticated browser access requires separate authority;
4. Computer Use requires explicit authority;
5. Agent binding alone cannot activate Computer Use;
6. Computer Use can enter human-handoff state;
7. automation can resume only after authority is revalidated;
8. sensitive/irreversible action requires canonical approval;
9. cancellation prevents further automated actions;
10. revoked authority blocks subsequent actions;
11. credential material is not exposed in Bot/tool/model payload serialization;
12. every action produces canonical audit/event evidence;
13. implementation swapping does not alter capability semantics.

---

# 13. Bot Capability Configuration

Bots may declare requested capabilities:

```python
BotCapabilityRequest(
    bot_id="bot:research",
    capability_id="web.search",
    requested_enabled=True,
    approval_preference="default",
    requested_scope={},
    metadata={},
)
```

This is a request.

It is not effective authority.

The platform must expose both:

```text
requested capability
effective capability
```

to avoid UI ambiguity.

Example:

```text
Requested:
computer.use = ON

Effective:
computer.use = BLOCKED_BY_POLICY
```

---

# 14. Model Interaction

Models may request tool/capability use only through normalized structured requests.

Model output cannot:

- grant capabilities;
- change permissions;
- widen scopes;
- lower approval requirements;
- alter budgets;
- activate Computer Use;
- bind a different Agent;
- install tools;
- store secrets;
- change Domain permissions.

Provider payloads are data, not policy.

Fallback providers must preserve or strengthen the original effective policy.

---

# 15. Domain Intelligence Interaction

## 15.1 DomainCapability Remains

Existing:

```text
DomainCapability
```

remains unchanged in purpose.

A Domain may declare:

- reasoning;
- workflow;
- presentation;
- validation;
- reporting;
- planning;
- operation-related capability.

## 15.2 Mapping

A Domain may require PlatformCapabilities.

Example:

```text
Oppositions Domain
requires
web.search
for
official-source verification
```

or:

```text
Project Domain
requires
files.read
git.read
code.execute
for
specific authorized operations
```

The Domain does not own the implementation.

## 15.3 Restrictive Composition

When a Domain participates:

```text
Bot request
∩ Domain effective permissions
∩ Platform capability policy
= final requested/effective capability envelope
```

Domain policy may narrow.

Domain policy may not silently broaden global authority.

---

# 16. Agent Runtime Interaction

Agent capability requirements must be mapped to PlatformCapabilities where appropriate without changing Phase 9 runtime ownership.

Agent capability matching must remain distinct from Bot UX configuration.

Conceptual flow:

```text
BotDefinition
↓
optional agent_binding_id
↓
canonical AgentRegistry resolution
↓
Agent requirements
↓
PlatformCapability effective resolution
↓
canonical operation execution
```

No reverse dependency should cause the Agent Runtime core to depend on Bot presentation contracts unless a narrow generic seam is explicitly designed and reviewed.

---

# 17. Persistence

Canonical persistence requirements:

- versioned Bot definitions;
- versioned Bot capability requests;
- capability descriptors;
- implementation references;
- effective-policy decision records;
- audit records.

Secrets remain outside these stores.

Material changes requiring audit include:

- enabling/disabling a capability;
- changing Computer Use scope;
- changing autonomy preference;
- changing Agent binding;
- changing Domain binding;
- changing privacy-relevant knowledge/memory scope;
- changing approval preferences;
- importing a Bot definition.

---

# 18. Import and Export

Bot export must contain only safe declarative configuration.

May include:

- Bot metadata;
- instructions references or exportable instructions;
- Communication Profile references;
- model policy references/configuration where portable;
- requested capabilities;
- safe scopes;
- Domain references;
- knowledge references where authorized;
- memory policy references;
- Agent binding metadata only when portable and authorized.

Must not include:

- credentials;
- tokens;
- cookies;
- secrets;
- operating-system permission tokens;
- hidden approval decisions;
- raw private provider configuration.

Imported Bots default to no privileged effective authority until canonical policy evaluation grants it.

---

# 19. API Surface

Conceptual Phase 11 API additions:

```text
GET    /bots
POST   /bots
GET    /bots/{id}
PATCH  /bots/{id}
POST   /bots/{id}/duplicate
POST   /bots/{id}/archive

GET    /capabilities
GET    /capabilities/{id}

GET    /tools
GET    /tools/{id}
```

`/tools` is an implementation/availability view.

It is not a second executable operation endpoint.

Mutating endpoints must reuse:

- authentication;
- authorization;
- idempotency;
- validation;
- audit;
- error contracts;
- versioning.

---

# 20. UI Architecture Consequences

Phase 11 User Interface Architecture must eventually expose:

```text
Conversation
Bots
Tools / Capabilities
Goals
Workflows
Review Center
Timeline
Knowledge Explorer
Memory
Domains
Agents
Configuration
System Health
```

Bots is the user-facing assistant/product abstraction.

Agents remains the advanced runtime/operational abstraction.

Tools / Capabilities is the global capability and implementation-status view.

Clients must not be allowed to grant effective authority directly.

---

# 21. Configuration Center Consequences

Add configuration areas:

## Bots

- definitions;
- templates;
- model policy;
- Communication Profile;
- Domains;
- requested capabilities;
- autonomy preference;
- Agent binding;
- budgets/limits;
- import/export.

## Tools / Capabilities

- capability catalog;
- implementation availability;
- connection state;
- provider/adapters;
- privacy;
- local/remote execution;
- approvals;
- scopes;
- health;
- audit.

---

# 22. Audit and Events

Minimum events:

```text
bot.created
bot.updated
bot.disabled
bot.enabled
bot.archived
bot.imported
bot.exported

bot.agent_binding.updated
bot.capability.requested
bot.capability.updated

capability.resolution.completed
capability.allowed
capability.blocked
capability.approval_required

tool.selected
tool.execution.started
tool.execution.completed
tool.execution.failed

computer_use.started
computer_use.waiting_for_human
computer_use.human_control
computer_use.resumed
computer_use.cancelled
computer_use.completed
computer_use.failed
```

Events must reuse the platform/canonical event architecture.

No Bot-specific parallel event bus is allowed.

---

# 23. Error Semantics

Representative structured errors:

```text
BOT_NOT_FOUND
BOT_INVALID
BOT_AGENT_BINDING_INVALID
CAPABILITY_NOT_FOUND
CAPABILITY_UNAVAILABLE
CAPABILITY_BLOCKED_BY_POLICY
CAPABILITY_APPROVAL_REQUIRED
TOOL_IMPLEMENTATION_UNAVAILABLE
COMPUTER_USE_SCOPE_DENIED
COMPUTER_USE_APPROVAL_REQUIRED
COMPUTER_USE_AUTHORITY_REVOKED
```

Errors must reuse the Phase 11 common error contract.

---

# 24. Security Invariants

The following are permanent invariants.

```text
NO_PARALLEL_AGENT_RUNTIME
NO_PARALLEL_OPERATION_REGISTRY
NO_PARALLEL_WORKFLOW_ENGINE
NO_PARALLEL_PLANNER
NO_PARALLEL_APPROVAL_SYSTEM
NO_PARALLEL_AUTONOMY_SYSTEM
NO_PARALLEL_BUDGET_SYSTEM
NO_PARALLEL_VALIDATION_SYSTEM
NO_PARALLEL_MEMORY_STORE
NO_PARALLEL_KNOWLEDGE_STORE
NO_PARALLEL_EVENT_BUS
NO_BOT_OWNED_SECRETS
NO_BOT_OWNED_TOOL_IMPLEMENTATIONS
NO_DOMAINCAPABILITY_REPLACEMENT
NO_PERMISSION_WIDENING
NO_APPROVAL_WEAKENING
NO_AUTONOMY_WIDENING
NO_BUDGET_WIDENING
NO_FALLBACK_PERMISSION_WIDENING
NO_AGENT_BINDING_PERMISSION_WIDENING
NO_COMPUTER_USE_BY_IMPLICATION
NO_PROVIDER_PAYLOAD_AS_POLICY
```

---

# 25. Roadmap Changes Required

The canonical detailed roadmap must gain:

```text
11.59 — Bot Identity and Configuration Layer
11.60 — Platform Capability Catalog and Tool Resolution
11.61 — Web, Browser and Computer Use
```

Existing Phase 11 sections must also be amended where necessary:

```text
11.1  Integration Core
11.2  Orchestration Layer
11.3  Application Backend
11.4  CLI
11.5  Conversational Interface
11.12 Configuration Center
11.13 Authentication and Authorization
11.14 Security and Secrets
11.15 Storage and Persistence
11.18 Import and Export
11.19 Plugin System
11.20 External Integrations
11.21 Model Gateway
11.22 Event System
11.23 Observability
11.24 Error Management and Recovery
11.26 User Interface Architecture
11.29 Audit Trail
11.30 Performance and Resource Management
11.31 Testing Strategy
11.32 Documentation
11.45 Platform Layer Boundaries
11.50 Reusable Backend Interfaces
11.51 MCP, REST and Actions Adapters
11.52 Skills and Plugin Packaging
11.54 Exit and Portability Strategy
```

The amendment must avoid unnecessary edits to sections whose semantics do not materially change.

---

# 26. Public ROADMAP.md Changes Required

`ROADMAP.md` Phase 11 must mention, at minimum:

- first-class Bots;
- Bot / Agent separation;
- platform capability catalog;
- Web Search;
- Browser;
- Computer Use;
- tool/provider-independent resolution;
- capability permissions and approvals;
- global Bot and Tools/Capabilities UI;
- safe human-in-the-loop Computer Use.

The concise roadmap must remain concise.

It must not replicate the detailed Phase 11 specification.

---

# 27. Requirements Matrix Changes Required

The Domain Intelligence Requirements Matrix already contains Phase 11 requirements and acceptance entries.

This amendment adds:

```text
F11-008 — Bot identity/configuration and Bot != Agent separation
F11-009 — Platform capability catalog and effective capability resolution
F11-010 — Tool binding through canonical operations/adapters
F11-011 — Web Search and Browser as distinct capabilities
F11-012 — Computer Use with strengthened authorization and HITL
F11-013 — Bot persistence/import/export/versioning
```

Proposed acceptance identifiers:

```text
AT-F11-BOT-01
AT-F11-CAP-01
AT-F11-TOOL-01
AT-F11-WEB-01
AT-F11-CU-01
AT-F11-BOT-PORT-01
```

The matrix must also be updated if it stores a hash/checksum of the detailed Phase 11 roadmap.

The new canonical hash must be computed only after the Phase 11 detailed roadmap amendment is finalized.

---

# 28. README Changes Required

README changes should be minimal.

The public architecture description should acknowledge that Phase 11 will provide:

- user-facing Bots;
- provider-independent capabilities;
- controlled tool execution;
- Web/Browser/Computer Use;
- canonical Agent-backed execution where required.

README must not become a duplicate roadmap.

---

# 29. Documentation Files in Scope

Expected canonical documentation update set:

```text
ROADMAP.md
README.md
docs/roadmap/phase-11-stable-integrated-platform.md
docs/reference/domain-intelligence-requirements-matrix.md
```

Historical audit artifacts must not be modified.

Closed Phase 8/9/10 design specs must not be rewritten.

Phase 10 documentation may only be changed if a direct forward-reference inconsistency is later proven during implementation planning.

---

# 30. Implementation Sequencing

This design must not be implemented while Phase 10.44 remains open.

Required sequence:

```text
Phase 10.44 final audit PASS
↓
Phase 10.44 docs-only closure commit
↓
verify clean worktree
↓
integrate this Phase 11 amendment spec
↓
commit spec only
↓
write implementation/documentation amendment plan
↓
commit plan only
↓
apply roadmap/matrix/README changes
↓
commit documentation amendment
↓
Phase 11 remains PLANNED
↓
no Phase 11 production code until Phase 11 execution formally starts
```

---

# 31. TDD and Acceptance Expectations for Future Implementation

When 11.59–11.61 are eventually implemented:

```text
TEST RED
↓
MINIMUM IMPLEMENTATION
↓
GREEN
↓
CONTROLLED REFACTOR
↓
NEXT BLOCK
```

Every subphase must have:

- focused tests;
- connected acceptance;
- subsystem regressions;
- global suite;
- Ruff;
- format;
- compileall;
- git diff --check;
- phase-specific gates.

No subphase is closed merely because implementation exists.

Independent audit remains mandatory.

---

# 32. Future Connected Acceptance Matrix

## 11.59

```text
DP-059
AT-DP-059
```

Real connected acceptance through:

- canonical Bot repository/service;
- official in-memory implementation;
- canonical Agent Registry;
- canonical permission/autonomy/budget/approval owners.

## 11.60

```text
DP-060
AT-DP-060
```

Real connected acceptance through:

- PlatformCapabilityCatalog;
- effective-policy resolver;
- Domain permission layer;
- canonical operation registry;
- official in-memory tool implementation adapter.

## 11.61

```text
DP-061
AT-DP-061
```

Real connected acceptance through:

- Web Search mock/in-memory official implementation;
- Browser official in-memory implementation;
- Computer Use official in-memory state machine/adapter;
- canonical approvals;
- canonical policy;
- canonical audit/event evidence;
- human-handoff flow.

Isolated mocks alone are insufficient.

---

# 33. Compatibility Requirements

The amendment must preserve:

- all closed Phase 9 contracts;
- all closed Phase 10 contracts;
- Domain Agent Runtime integration;
- Domain Planner/Workflow integration;
- Domain Validation integration;
- Domain capability semantics;
- Domain permission semantics;
- existing operation availability rules;
- provider/model capability semantics;
- Model Gateway independence;
- current Phase 11 numbering through 11.58.

No existing contract may be repurposed incompatibly merely to avoid introducing a narrowly-scoped new contract.

---

# 34. Non-Goals

The amendment does not attempt to decide:

- final CMMChat Bot gallery appearance;
- exact Bot editor visual design;
- GrokBot parity;
- marketplace;
- bot sharing;
- cloud hosting;
- multi-user bot publishing;
- final Web Search vendor;
- final browser-control vendor;
- final Computer Use vendor;
- OpenBot vs BrowserSkill;
- final permissions UX;
- mobile Computer Use UX.

Those decisions belong to later implementation/client specs.

---

# 35. Risks and Mitigations

## Risk: Bot becomes a second Agent

Mitigation:

```text
Bot = identity/configuration
Agent = runtime
```

Agent binding is optional and cannot grant authority.

## Risk: Capability catalog becomes second executable registry

Mitigation:

`PlatformCapabilityCatalog` is descriptive/resolutive only.

Execution remains canonical.

## Risk: DomainCapability collision

Mitigation:

Maintain separate names and semantics.

Use explicit mapping.

## Risk: Computer Use over-privilege

Mitigation:

Separate capability, explicit grant, scoped authority, HITL, cancellation, revalidation, audit.

## Risk: Tool provider lock-in

Mitigation:

Capability identifiers remain provider-independent.

## Risk: Imported Bot gains privileges

Mitigation:

Imported config does not carry effective authority.

## Risk: Model output changes policy

Mitigation:

Provider/model output is data, never policy authority.

## Risk: Phase 10 contamination

Mitigation:

Do not integrate until current Phase 10.44 closure is complete.

---

# 36. Completion Criteria for This Amendment Design

This design is ready for repository integration when:

- scope is approved;
- Bot / Agent separation is explicit;
- PlatformCapability / DomainCapability separation is explicit;
- no parallel runtime is introduced;
- no parallel executable registry is introduced;
- DP-059 / AT-DP-059 are defined;
- DP-060 / AT-DP-060 are defined;
- DP-061 / AT-DP-061 are defined;
- Computer Use safety boundaries are explicit;
- affected documentation is enumerated;
- requirements-matrix additions are enumerated;
- Phase 10.44 integration guard is explicit;
- no implementation work is included.

---

# 37. Final Architectural Decision

The canonical target is:

```text
CMMChat / Client
↓
Bot
↓
Bot configuration
↓
requested PlatformCapabilities
↓
CMM OS effective capability resolution
↓
optional canonical Agent binding
↓
canonical Operation Registry / Runtime
↓
Plugin / Integration / Adapter / Provider
↓
Web / Browser / Computer / Files / Email / Calendar / Git / MCP / etc.
```

with the permanent invariant:

```text
PRODUCT IDENTITY
!=
EXECUTION AUTHORITY
```

and:

```text
REQUESTED CAPABILITY
!=
EFFECTIVE PERMISSION
```

This separation is the foundation for safely turning CMM OS into the runtime behind configurable, tool-enabled and agent-backed Bots without fragmenting the architecture.
