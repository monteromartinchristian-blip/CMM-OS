# Phase 11 Bots and Platform Capabilities Roadmap Amendment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Integrate the approved Phase 11 Bots / Platform Capabilities / Web-Browser-Computer-Use architecture into the canonical CMM OS planning documentation, explicitly position CMMChat as the first-party conversational client/UI already under active development, preserve all Phase 9/10 canonical ownership boundaries, and finish with a verified fast-forward synchronization of the current feature branch to GitHub.

**Architecture:** This is a documentation-only roadmap amendment. It extends the existing Phase 11 detailed roadmap with subphases 11.59–11.61 and updates the concise roadmap, Phase 11 requirements entries, and public README without implementing production contracts or changing CMMChat code. The amendment must preserve the canonical Agent Runtime, Operation Registry, approvals, autonomy, budgets, validation, DomainCapability semantics, Domain permissions, and all independently audited Phase 10 boundaries.

**Tech Stack:** Markdown, Git, shell (`bash` compatible with macOS Bash 3.2), `rg`, `grep`, `sed`, `awk`, `shasum`, existing repository validation/test infrastructure.

**Spec:** `docs/superpowers/specs/2026-09-07-phase-11-bots-platform-capabilities-design.md`

**Planning baseline:**
- Branch: `feature/phase-10-domain-intelligence`
- Phase 10.44 closure HEAD: `35ca06dfc72b2fbe470375f53c7fd1ac6868b431`
- Phase 11 amendment spec commit: `b24a68925e0132b1c52b819669b1fc734fa454ce`
- Canonical spec SHA-256: `f340d627bb44e51c05a98232a64c8c146495bffcfdeb6554736430f44c90cde5`
- Phase 10.44: closed after final independent re-audit V4 `PASS`
- Quarantine stash: `quarantine: post-audit phase 10.32 uncommitted changes`
- Push/merge state at plan creation: no push, no merge
- Phase 11 remains `Planned`

## Global Constraints

- This plan is **documentation-only**. Do not modify production Python, tests, fixtures, runtime configuration, CMMChat source, generated application assets, or historical audit artifacts.
- Do not begin production implementation of 11.59, 11.60, or 11.61 in this plan.
- Preserve `Bot != Agent`.
- Preserve `PlatformCapability != DomainCapability`.
- Preserve `Capability != ToolImplementation != Operation`.
- Preserve the Phase 9 Agent Runtime as the sole canonical persistent agent runtime.
- Preserve the canonical Phase 9/10 operation registration and execution path. Do not introduce a second executable Tool Registry.
- Preserve canonical Phase 9 approvals, autonomy, action/economic budgets, checkpoint/recovery, runtime events, and security ownership.
- Preserve the Phase 7 Validation System as the authoritative validation owner.
- Preserve existing DomainCapability semantics and Domain permission semantics.
- Domain policy may narrow platform authority; it must never silently broaden global authority.
- Requested capabilities are not effective permissions.
- Agent binding never grants permissions, autonomy, budgets, approvals, secrets, or Computer Use.
- Model/provider output is data, not policy authority.
- Fallback may never widen privacy, permissions, approval requirements, autonomy, budgets, or resource scope.
- `web.search`, browser access, authenticated browser access, and `computer.use` remain independently authorized capabilities.
- Computer Use remains high-impact, least-privilege, auditable, cancellable, human-takeover capable, and approval-gated for sensitive/irreversible effects.
- Imported Bot definitions never carry effective privileged authority or secrets.
- CMMChat is described as a **first-party client/UI**, not as an authority owner and not as a dependency of CMM OS Core/Runtime.
- CMMChat UI implementation remains outside this repository and outside this plan.
- Do not modify Phase 8, Phase 9, or closed Phase 10 historical specs/audits solely to reflect this future Phase 11 amendment.
- Do not use `git stash`, `stash pop/apply/drop`, `git reset`, `git clean`, or `git worktree`.
- Preserve the quarantine stash exactly.
- No merge.
- Push is allowed only at the final synchronization task, after all amendment commits are complete and the worktree is clean.
- Push must be a normal fast-forward push. Never use `--force` or `--force-with-lease`.
- Every commit must have a single clear scope.
- Worktree must be clean after the plan commit and after the amendment implementation commit.
- The detailed Phase 11 roadmap remains the canonical source for Phase 11 architecture; `ROADMAP.md` and `README.md` stay concise.
- Any requirements-matrix hash that fingerprints the Phase 11 roadmap must be recalculated from the final exact file bytes after the detailed roadmap edit is complete.
- No `DP-059`, `DP-060`, or `DP-061` may be marked implemented, verified, audited, or closed by this documentation amendment. They are planned design points only.
- No `AT-DP-059`, `AT-DP-060`, or `AT-DP-061` may be marked PASS before real future implementation and independent audit.
- Phase 11 status remains `Planned`.

---

# File Map

## Create

`docs/superpowers/plans/2026-09-08-phase-11-bots-platform-capabilities-roadmap-amendment-plan.md`

Purpose:
- canonical execution plan for this documentation amendment;
- committed separately before roadmap/matrix/README changes.

## Modify

`docs/roadmap/phase-11-stable-integrated-platform.md`

Purpose:
- canonical detailed Phase 11 architecture;
- append 11.59–11.61 after existing 11.58;
- amend existing cross-cutting sections where Bots/capabilities materially affect responsibilities;
- add CMMChat first-party client boundary;
- preserve Phase 11 status as planned.

`ROADMAP.md`

Purpose:
- concise public roadmap;
- add short Phase 11 capability bullets for Bots, Platform Capabilities, Web/Browser/Computer Use, and CMMChat first-party client;
- preserve concise format and Phase 11 `Planned` status;
- retain Phase 10.44 closure and Phase 10.45-not-started truth.

`docs/reference/domain-intelligence-requirements-matrix.md`

Purpose:
- add Phase 11 future requirements `F11-008` through `F11-013`;
- add acceptance identifiers `AT-F11-BOT-01`, `AT-F11-CAP-01`, `AT-F11-TOOL-01`, `AT-F11-WEB-01`, `AT-F11-CU-01`, `AT-F11-BOT-PORT-01`;
- preserve all closed Phase 10 requirements and audit evidence;
- refresh the canonical `SRC-R11` fingerprint if the matrix stores the Phase 11 detailed-roadmap hash.

`README.md`

Purpose:
- concise public positioning;
- mention configurable user-facing Bots, provider-independent capabilities, controlled tool execution, and the first-party CMMChat client;
- avoid duplicating the Phase 11 roadmap;
- preserve provider-independent/local-first positioning.

## Explicitly Do Not Modify

- `cmm/**`
- `kernel/**`
- `tests/**`
- `cmm_agent/**`
- CMMChat repository/source
- `docs/audits/**`
- closed Phase 8/9/10 design specs
- Phase 10 implementation references unless an actual broken forward reference is discovered and separately justified

---

# Required Final Documentation Shape

The final detailed Phase 11 roadmap must contain these canonical headings exactly:

```text
# 11.59 — Bot Identity and Configuration Layer
# 11.60 — Platform Capability Catalog and Tool Resolution
# 11.61 — Web, Browser and Computer Use
```

The final requirements matrix must contain these planned requirements:

```text
F11-008
F11-009
F11-010
F11-011
F11-012
F11-013
```

and these future acceptance identifiers:

```text
AT-F11-BOT-01
AT-F11-CAP-01
AT-F11-TOOL-01
AT-F11-WEB-01
AT-F11-CU-01
AT-F11-BOT-PORT-01
```

The detailed roadmap must also preserve future implementation DPs:

```text
DP-059
AT-DP-059
DP-060
AT-DP-060
DP-061
AT-DP-061
```

with planned/not-yet-implemented semantics.

---

# CMMChat Architectural Reference

Use this meaning consistently across the amendment:

```text
CMM OS
= canonical intelligence/runtime/data/capability/permission/agent/tool authority

CMMChat
= first-party conversational product and client UI
```

Required dependency direction:

```text
CMMChat
    ↓ consumes versioned contracts
CMM OS API / application contracts
    ↓
CMM OS canonical runtime
```

Forbidden dependency direction:

```text
CMM OS Core/Runtime
    X
must not depend on CMMChat implementation
```

The documentation may state that the **new CMMChat UI is already under active development**, but it must not:
- claim that the Phase 11 runtime contracts are already implemented;
- claim CMMChat is already integrated with 11.59–11.61;
- couple Phase 11 completion to current CMMChat visual implementation;
- modify CMMChat code in this repository amendment.

Recommended concise wording:

> **CMMChat** is the first-party conversational client/UI for CMM OS and is already under active interface development. It consumes versioned CMM OS application contracts; CMM OS remains authoritative for intelligence, capabilities, tools, permissions, Agents, data, validation, privacy, approvals, and execution. CMM OS Core/Runtime must not depend on the CMMChat implementation.

---

# Task 1: Commit This Amendment Plan Separately

**Files:**
- Create: `docs/superpowers/plans/2026-09-08-phase-11-bots-platform-capabilities-roadmap-amendment-plan.md`
- Read: `docs/superpowers/specs/2026-09-07-phase-11-bots-platform-capabilities-design.md`

**Interfaces:**
- Consumes: approved design spec at commit `b24a68925e0132b1c52b819669b1fc734fa454ce`
- Produces: committed, immutable execution plan for the documentation amendment

- [ ] **Step 1: Verify the repository is still at the spec commit**

Run:

```bash
cd "/Users/chris/CMM OS"
test "$(git branch --show-current)" = "feature/phase-10-domain-intelligence"
test "$(git rev-parse HEAD)" = "b24a68925e0132b1c52b819669b1fc734fa454ce"
test -z "$(git status --porcelain)"
git stash list | grep -Fq "quarantine: post-audit phase 10.32 uncommitted changes"
```

Expected:
- every command exits `0`;
- worktree is clean;
- quarantine stash remains present.

- [ ] **Step 2: Verify the design spec is exact**

Run:

```bash
SPEC="docs/superpowers/specs/2026-09-07-phase-11-bots-platform-capabilities-design.md"

test -f "$SPEC"
test "$(shasum -a 256 "$SPEC" | awk '{print $1}')" = \
  "f340d627bb44e51c05a98232a64c8c146495bffcfdeb6554736430f44c90cde5"

grep -Fq '11.59 — Bot Identity and Configuration Layer' "$SPEC"
grep -Fq '11.60 — Platform Capability Catalog and Tool Resolution' "$SPEC"
grep -Fq '11.61 — Web, Browser and Computer Use' "$SPEC"
grep -Fq 'NO_PARALLEL_OPERATION_REGISTRY' "$SPEC"
```

Expected: all checks pass.

- [ ] **Step 3: Copy this downloaded plan into the canonical plan path**

Source expected in iCloud Downloads:

```text
$HOME/Library/Mobile Documents/com~apple~CloudDocs/Downloads/2026-09-08-phase-11-bots-platform-capabilities-roadmap-amendment-plan.md
```

Destination:

```text
docs/superpowers/plans/2026-09-08-phase-11-bots-platform-capabilities-roadmap-amendment-plan.md
```

Before copying, verify the destination does not exist.

- [ ] **Step 4: Verify plan-only scope**

Run:

```bash
git status --short
git diff --check
```

Expected:
- exactly one untracked/changed file;
- that file is the plan;
- `git diff --check` passes.

- [ ] **Step 5: Stage and verify exactly one plan file**

Run:

```bash
git add -- docs/superpowers/plans/2026-09-08-phase-11-bots-platform-capabilities-roadmap-amendment-plan.md

test "$(git diff --cached --name-only)" = \
  "docs/superpowers/plans/2026-09-08-phase-11-bots-platform-capabilities-roadmap-amendment-plan.md"

git diff --cached --check
```

Expected: PASS.

- [ ] **Step 6: Commit the plan**

Run:

```bash
git commit -m "docs(phase11): plan bots capability roadmap amendment"
```

Expected:
- one-file plan commit;
- no roadmap/content implementation yet.

- [ ] **Step 7: Verify clean post-plan state**

Run:

```bash
git status --short --branch
git log -3 --oneline --decorate
test -z "$(git status --porcelain)"
git stash list | grep -Fq "quarantine: post-audit phase 10.32 uncommitted changes"
```

Expected:
- clean worktree;
- plan commit directly above `b24a689`;
- stash preserved.

---

# Task 2: Freeze the Exact Documentation Baseline Before Amendment

**Files:**
- Read: `docs/roadmap/phase-11-stable-integrated-platform.md`
- Read: `ROADMAP.md`
- Read: `docs/reference/domain-intelligence-requirements-matrix.md`
- Read: `README.md`
- Read: approved spec and committed plan

**Interfaces:**
- Consumes: current canonical docs
- Produces: exact pre-edit inventory and hashes used to prevent accidental scope drift

- [ ] **Step 1: Capture branch, HEAD and four-document hashes**

Run:

```bash
echo "BRANCH=$(git branch --show-current)"
echo "HEAD=$(git rev-parse HEAD)"

for f in \
  ROADMAP.md \
  README.md \
  docs/roadmap/phase-11-stable-integrated-platform.md \
  docs/reference/domain-intelligence-requirements-matrix.md
do
  test -f "$f"
  printf '%s  %s\n' "$(shasum -a 256 "$f" | awk '{print $1}')" "$f"
done
```

Expected:
- four hashes;
- worktree remains clean.

- [ ] **Step 2: Confirm 11.59–11.61 are not already canonical roadmap sections**

Run:

```bash
! rg -n '^# 11\.(59|60|61) — ' docs/roadmap/phase-11-stable-integrated-platform.md
```

Expected: exit `0` because these sections are not yet present.

- [ ] **Step 3: Confirm Bots are not already a canonical production contract**

Run:

```bash
! rg -n \
  'class BotDefinition|class PlatformCapabilityCatalog|BotDefinition\(' \
  cmm kernel \
  --glob '*.py'
```

Expected: exit `0`.

- [ ] **Step 4: Inventory existing Phase 11 cross-cutting sections**

Run:

```bash
rg -n '^# 11\.' docs/roadmap/phase-11-stable-integrated-platform.md
```

Expected:
- existing numbering through 11.58;
- no renumbering required.

- [ ] **Step 5: Inventory current Phase 11 requirements and source fingerprint**

Run:

```bash
rg -n \
  'SRC-R11|F11-[0-9]+|AT-F11-' \
  docs/reference/domain-intelligence-requirements-matrix.md
```

Expected:
- current F11 inventory visible;
- any `SRC-R11` Phase 11 detailed-roadmap checksum visible for later refresh.

- [ ] **Step 6: Record a no-mutation checkpoint**

Run:

```bash
test -z "$(git status --porcelain)"
echo "DOC_BASELINE_CAPTURED=YES"
```

Expected: `DOC_BASELINE_CAPTURED=YES`.

---

# Task 3: Amend the Detailed Phase 11 Roadmap

**Files:**
- Modify: `docs/roadmap/phase-11-stable-integrated-platform.md`
- Reference: `docs/superpowers/specs/2026-09-07-phase-11-bots-platform-capabilities-design.md`

**Interfaces:**
- Consumes: approved spec
- Produces: canonical detailed Phase 11 roadmap containing 11.59–11.61 and cross-cutting references

## Required cross-cutting sections to amend

Review and edit only where materially necessary:

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
11.51 MCP, REST, and Actions Adapters
11.52 Skills and Plugin Packaging
11.54 Exit and Portability Strategy
```

Do not mechanically edit every listed section. Edit only sections whose responsibilities, resources, interfaces, events, security rules, or completion criteria actually change.

- [ ] **Step 1: Add Bot-related public resources to 11.3 Application Backend**

The API/resource inventory must include:

```text
bots
capabilities
tools
```

Conceptual endpoints:

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

Document explicitly:

```text
/tools = implementation/availability inspection surface
/tools != second executable operation endpoint
```

- [ ] **Step 2: Add application-service responsibilities**

Where application services are enumerated, add conceptual:

```text
BotService
CapabilityService
ToolCatalogService
```

Document that these do not own canonical runtime execution authority.

- [ ] **Step 3: Amend Orchestration Layer capability resolution**

Add the effective resolution concept:

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

Required rules:
- explicit deny wins;
- missing sensitive/mutating authority fails closed;
- fallback cannot widen authority;
- provider/model payload cannot grant authority.

- [ ] **Step 4: Amend Conversational Interface**

Document that a conversation may optionally be associated with:

```text
bot_id
```

and that normal conversation remains possible without Agent binding.

Add user-facing transparency for:
- requested capabilities;
- effective capabilities;
- blocked capabilities;
- approval-required capability state;
- optional Agent backing.

- [ ] **Step 5: Amend Configuration Center**

Add sections:

```text
Bots
Tools / Capabilities
```

`Bots` includes:
- identity;
- instructions;
- Communication Profile;
- model policy;
- Domains;
- knowledge/memory scope;
- requested capabilities;
- autonomy preference;
- optional Agent binding;
- import/export.

`Tools / Capabilities` includes:
- catalog;
- availability;
- implementation/connection state;
- local/remote execution metadata;
- privacy;
- scopes;
- approvals;
- health;
- audit.

- [ ] **Step 6: Amend authentication/security boundaries**

Document:
- Bot configuration never grants effective permission;
- Bot secrets are forbidden;
- credentials/cookies remain outside Bot definitions;
- Agent binding cannot grant capability authority;
- Computer Use requires explicit authority;
- authenticated browser access is independently scoped;
- least privilege and human takeover requirements.

- [ ] **Step 7: Amend persistence/import/export**

Add persistence for:
- versioned Bot definitions;
- Bot capability requests;
- PlatformCapability descriptors;
- implementation references;
- effective-policy decision records.

Add export/import rule:

```text
portable Bot configuration != portable effective authority
```

Imported Bots must default to no privileged effective capability until canonical policy evaluation grants it.

- [ ] **Step 8: Amend Plugin/Integration/Model Gateway boundaries**

Document:
- plugins/integrations/adapters may implement capabilities;
- they do not own capability authorization;
- Model Gateway tool calls are normalized requests only;
- model/provider output is not policy;
- provider swapping must not change PlatformCapability semantics.

- [ ] **Step 9: Amend events/observability/audit**

Add representative future events:

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

Explicitly state:
- reuse canonical event architecture;
- no Bot-specific event bus.

- [ ] **Step 10: Amend UI Architecture**

Add modules:

```text
Bots
Tools / Capabilities
```

Keep:
- Agents as advanced/runtime operational surface;
- Bots as product/user-facing assistant identity.

Add the CMMChat boundary:

> **CMMChat** is the first-party conversational client/UI for CMM OS and is already under active interface development. It consumes versioned CMM OS application contracts; CMM OS remains authoritative for intelligence, capabilities, tools, permissions, Agents, data, validation, privacy, approvals, and execution. CMM OS Core/Runtime must not depend on the CMMChat implementation.

Do not claim 11.59–11.61 are implemented.

- [ ] **Step 11: Append 11.59 exactly as a planned subphase**

Required heading:

```markdown
# 11.59 — Bot Identity and Configuration Layer
```

Required conceptual contracts:

```text
BotDefinition
Bot configuration/lifecycle
CONVERSATIONAL
TOOL_ENABLED
AGENT_BACKED
optional Agent binding
```

Required invariants:
- Bot is product identity/configuration;
- Agent is runtime;
- binding never grants authority;
- secrets excluded;
- versioned/importable/exportable;
- Phase 11.59 remains planned.

Required Design Point:

```text
DP-059
```

Required future connected acceptance:

```text
AT-DP-059
```

Do not label the acceptance PASS.

- [ ] **Step 12: Append 11.60 exactly as a planned subphase**

Required heading:

```markdown
# 11.60 — Platform Capability Catalog and Tool Resolution
```

Required conceptual contract:

```text
PlatformCapabilityDescriptor
PlatformCapabilityCatalog
```

Required rule:

```text
PlatformCapabilityCatalog = descriptive/resolutive
PlatformCapabilityCatalog != executable Tool Registry
```

Required tool flow:

```text
PlatformCapability
→ effective capability resolution
→ compatible implementation
→ canonical Operation
→ canonical Runtime/Execution
```

Required distinction:

```text
PlatformCapability != DomainCapability
```

Required Design Point / future acceptance:

```text
DP-060
AT-DP-060
```

Do not label the acceptance PASS.

- [ ] **Step 13: Append 11.61 exactly as a planned subphase**

Required heading:

```markdown
# 11.61 — Web, Browser and Computer Use
```

Required independent capabilities:

```text
web.search
browser.navigate
browser.read
browser.read_authenticated
computer.use
```

Required non-implication:

```text
web.search
!= browser.navigate
!= browser.read_authenticated
!= computer.use
```

Computer Use requirements:
- explicit authorization;
- app/resource scope;
- least privilege;
- visible execution state;
- cancellation;
- human takeover;
- approval for sensitive/irreversible effects;
- credential isolation;
- audit;
- revalidation after human takeover/resume;
- Agent binding does not imply Computer Use.

Required Design Point / future acceptance:

```text
DP-061
AT-DP-061
```

Do not label the acceptance PASS.

- [ ] **Step 14: Add future testing criteria**

Phase 11 testing strategy must eventually include connected acceptance for:
- conversational Bot with no Agent;
- tool-enabled Bot using canonical operation path;
- Agent-backed Bot using canonical Agent Registry;
- restrictive capability intersection;
- no second executable registry;
- web allowed/browser denied;
- browser read-only/computer denied;
- Computer Use human handoff;
- authority revocation;
- approval gating;
- credential non-exposure.

- [ ] **Step 15: Run detailed-roadmap structural gate**

Run:

```bash
P11="docs/roadmap/phase-11-stable-integrated-platform.md"

test "$(grep -c '^# 11\.59 — Bot Identity and Configuration Layer$' "$P11")" = "1"
test "$(grep -c '^# 11\.60 — Platform Capability Catalog and Tool Resolution$' "$P11")" = "1"
test "$(grep -c '^# 11\.61 — Web, Browser and Computer Use$' "$P11")" = "1"

for marker in \
  'DP-059' 'AT-DP-059' \
  'DP-060' 'AT-DP-060' \
  'DP-061' 'AT-DP-061' \
  'CONVERSATIONAL' 'TOOL_ENABLED' 'AGENT_BACKED' \
  'PlatformCapabilityCatalog' \
  'web.search' 'browser.navigate' 'computer.use' \
  'CMMChat'
do
  grep -Fq "$marker" "$P11"
done

git diff --check -- "$P11"
```

Expected: PASS.

- [ ] **Step 16: Prove no false implementation/closure claim**

Run:

```bash
! rg -n \
  'DP-059=VERIFIED|DP-060=VERIFIED|DP-061=VERIFIED|AT-DP-059=PASS|AT-DP-060=PASS|AT-DP-061=PASS|11\.59.*closed|11\.60.*closed|11\.61.*closed' \
  "$P11"
```

Expected: exit `0`.

---

# Task 4: Update the Concise Public ROADMAP.md

**Files:**
- Modify: `ROADMAP.md`
- Reference: detailed Phase 11 roadmap after Task 3

**Interfaces:**
- Consumes: canonical detailed Phase 11 architecture
- Produces: concise public Phase 11 summary aligned with it

- [ ] **Step 1: Preserve current status truth**

Before editing, verify:

```bash
grep -Fq '**Phase 10.44:** complete, independently audited and closed' ROADMAP.md
grep -A8 -F '## Phase 11 — Stable Integrated Platform' ROADMAP.md \
  | grep -Fq '**Status:** Planned.'
```

Expected: PASS.

- [ ] **Step 2: Add concise Bot/capability bullets**

Under Phase 11 `Main capabilities`, add concise entries equivalent to:

```text
- first-class configurable Bots with explicit Bot/Agent separation;
- provider-independent Platform Capability Catalog and restrictive effective-capability resolution;
- canonical tool binding through existing operations, adapters, permissions, approvals, validation, autonomy, and budgets;
- independently authorized Web Search, Browser, authenticated-browser, and Computer Use capabilities;
- human-in-the-loop Computer Use with explicit scope, cancellation, takeover, revalidation, and audit;
- Bot and Tools / Capabilities workspaces for first-party clients;
- CMMChat as the first-party conversational client/UI consuming versioned CMM OS contracts.
```

Keep wording concise.

- [ ] **Step 3: Preserve architectural authority wording**

The concise roadmap must make clear that:
- CMM OS owns runtime authority;
- CMMChat is a client;
- Bot configuration does not own runtime authority.

- [ ] **Step 4: Preserve Phase 11 status**

Run:

```bash
grep -A12 -F '## Phase 11 — Stable Integrated Platform' ROADMAP.md \
  | grep -Fq '**Status:** Planned.'
```

Expected: PASS.

- [ ] **Step 5: Run concise-roadmap gate**

Run:

```bash
for marker in \
  'Bots' \
  'Platform Capability' \
  'Web Search' \
  'Browser' \
  'Computer Use' \
  'CMMChat'
do
  grep -Fq "$marker" ROADMAP.md
done

git diff --check -- ROADMAP.md
```

Expected: PASS.

---

# Task 5: Update the Phase 11 Requirements Matrix and Exact SRC-R11 Fingerprint

**Files:**
- Modify: `docs/reference/domain-intelligence-requirements-matrix.md`
- Read/hash: `docs/roadmap/phase-11-stable-integrated-platform.md`

**Interfaces:**
- Consumes: final bytes of detailed Phase 11 roadmap from Task 3
- Produces: planned Phase 11 requirement/acceptance entries and exact canonical source fingerprint

- [ ] **Step 1: Compute the new exact Phase 11 roadmap SHA-256**

Run:

```bash
P11="docs/roadmap/phase-11-stable-integrated-platform.md"
NEW_R11_SHA="$(shasum -a 256 "$P11" | awk '{print $1}')"

echo "NEW_SRC_R11_SHA256=$NEW_R11_SHA"
test "${#NEW_R11_SHA}" = "64"
```

Expected:
- 64-character SHA-256.

- [ ] **Step 2: Update only the canonical SRC-R11 fingerprint field**

Locate the existing `SRC-R11` row/reference and replace its old detailed-roadmap hash with the exact value from Step 1.

Do not alter:
- historical Phase 10 source hashes;
- audit bundle hashes;
- historical evidence.

- [ ] **Step 3: Add F11-008**

Requirement meaning:

```text
F11-008
Bot identity/configuration and Bot != Agent separation.
```

Required semantics:
- first-class versioned Bot;
- conversational/tool-enabled/agent-backed modes;
- optional Agent binding;
- Bot cannot own or bypass runtime authority;
- no secrets in Bot definition.

Status:
```text
PLANNED
```

Future acceptance:
```text
AT-F11-BOT-01
```

- [ ] **Step 4: Add F11-009**

Requirement meaning:

```text
F11-009
Provider-independent Platform Capability Catalog and most-restrictive effective capability resolution.
```

Required semantics:
- catalog descriptive/resolutive only;
- requested != effective;
- deny wins;
- no permission widening.

Status:
```text
PLANNED
```

Future acceptance:
```text
AT-F11-CAP-01
```

- [ ] **Step 5: Add F11-010**

Requirement meaning:

```text
F11-010
Tool binding through canonical operation/runtime/adapters without a second executable registry.
```

Status:
```text
PLANNED
```

Future acceptance:
```text
AT-F11-TOOL-01
```

- [ ] **Step 6: Add F11-011**

Requirement meaning:

```text
F11-011
Web Search, Browser navigation, and authenticated browser access remain independently authorized capabilities.
```

Status:
```text
PLANNED
```

Future acceptance:
```text
AT-F11-WEB-01
```

- [ ] **Step 7: Add F11-012**

Requirement meaning:

```text
F11-012
Computer Use requires explicit least-privilege authorization, scoped targets, canonical approvals, visible execution, cancellation, human takeover, resume revalidation, credential isolation, and audit.
```

Status:
```text
PLANNED
```

Future acceptance:
```text
AT-F11-CU-01
```

- [ ] **Step 8: Add F11-013**

Requirement meaning:

```text
F11-013
Bot persistence/import/export/versioning remains portable but never transfers secrets or effective privileged authority.
```

Status:
```text
PLANNED
```

Future acceptance:
```text
AT-F11-BOT-PORT-01
```

- [ ] **Step 9: Add acceptance-test registry rows**

Add future acceptance rows for:

```text
AT-F11-BOT-01
AT-F11-CAP-01
AT-F11-TOOL-01
AT-F11-WEB-01
AT-F11-CU-01
AT-F11-BOT-PORT-01
```

Each must identify Phase 11 and must **not** claim PASS.

Use planned/pending wording consistent with the matrix's existing future Phase 11 entries.

- [ ] **Step 10: Validate exact uniqueness**

Run:

```bash
MATRIX="docs/reference/domain-intelligence-requirements-matrix.md"

for marker in \
  'F11-008' \
  'F11-009' \
  'F11-010' \
  'F11-011' \
  'F11-012' \
  'F11-013' \
  'AT-F11-BOT-01' \
  'AT-F11-CAP-01' \
  'AT-F11-TOOL-01' \
  'AT-F11-WEB-01' \
  'AT-F11-CU-01' \
  'AT-F11-BOT-PORT-01'
do
  COUNT="$(grep -c "$marker" "$MATRIX")"
  test "$COUNT" -ge 1
done
```

Expected: all markers present.

- [ ] **Step 11: Validate SRC-R11 hash**

Run:

```bash
P11="docs/roadmap/phase-11-stable-integrated-platform.md"
MATRIX="docs/reference/domain-intelligence-requirements-matrix.md"
R11_SHA="$(shasum -a 256 "$P11" | awk '{print $1}')"

grep -Fq "$R11_SHA" "$MATRIX"
echo "SRC_R11_HASH_MATCH=PASS"
```

Expected: `SRC_R11_HASH_MATCH=PASS`.

- [ ] **Step 12: Preserve Phase 10.44 closure evidence**

Run:

```bash
grep -Fq 'DP-044' "$MATRIX"
grep -Fq 'AT-DP-044' "$MATRIX"
grep -Fq 'CLOSURE_ELIGIBLE=YES' "$MATRIX"
```

Expected: PASS.

- [ ] **Step 13: No false Phase 11 PASS**

Run:

```bash
! rg -n \
  'AT-F11-(BOT|CAP|TOOL|WEB|CU|BOT-PORT)-01.*PASS|F11-00(8|9).*VERIFIED_EXISTING|F11-01(0|1|2|3).*VERIFIED_EXISTING' \
  "$MATRIX"
```

Expected: exit `0`.

---

# Task 6: Update README with the First-Party CMMChat Boundary

**Files:**
- Modify: `README.md`

**Interfaces:**
- Consumes: Phase 11 public architecture
- Produces: concise product positioning without duplicating roadmap detail

- [ ] **Step 1: Locate existing public platform description**

Run:

```bash
rg -n \
  'models|tools|services|integrations|interfaces|Phase 11|platform|provider' \
  README.md
```

Expected:
- existing provider-independent positioning visible.

- [ ] **Step 2: Add one concise CMMChat paragraph**

Use meaning equivalent to:

> **CMMChat** is the first-party conversational client/UI for CMM OS and is already under active interface development. It consumes versioned CMM OS contracts while CMM OS remains authoritative for intelligence, memory, Domains, Agents, capabilities, tools, permissions, approvals, privacy, validation, and execution.

Follow with the boundary:

> CMM OS Core/Runtime does not depend on the CMMChat implementation; alternative clients remain supported through the same stable interfaces.

- [ ] **Step 3: Add concise Phase 11 future capability wording**

Mention:
- configurable Bots;
- provider-independent capabilities;
- controlled tools;
- Web/Browser/Computer Use.

Do not list all namespaces or duplicate the 11.59–11.61 spec.

- [ ] **Step 4: Preserve existing product principles**

Verify README still states concepts equivalent to:
- provider independence;
- tools/services/integrations outside the model;
- CMM OS as stable layer;
- local/private platform direction.

- [ ] **Step 5: README format gate**

Run:

```bash
grep -Fq 'CMMChat' README.md
grep -Fq 'first-party' README.md
grep -Fq 'Bots' README.md
grep -Fq 'Computer Use' README.md

git diff --check -- README.md
```

Expected: PASS.

---

# Task 7: Cross-Document Consistency Gate

**Files:**
- Validate:
  - `ROADMAP.md`
  - `README.md`
  - `docs/roadmap/phase-11-stable-integrated-platform.md`
  - `docs/reference/domain-intelligence-requirements-matrix.md`
- Must not modify other files

**Interfaces:**
- Consumes: Tasks 3–6 edits
- Produces: one coherent documentation amendment ready for commit

- [ ] **Step 1: Verify exact changed-file scope**

Run:

```bash
git status --short

CHANGED="$(
  git status --porcelain |
  sed 's/^...//' |
  sort
)"

EXPECTED="$(
  printf '%s\n' \
    README.md \
    ROADMAP.md \
    docs/reference/domain-intelligence-requirements-matrix.md \
    docs/roadmap/phase-11-stable-integrated-platform.md |
  sort
)"

test "$CHANGED" = "$EXPECTED"
```

Expected: exactly four modified files.

- [ ] **Step 2: Global whitespace gate**

Run:

```bash
git diff --check
```

Expected: no output, exit `0`.

- [ ] **Step 3: Verify canonical Phase 11 headings**

Run:

```bash
P11="docs/roadmap/phase-11-stable-integrated-platform.md"

for heading in \
  '# 11.59 — Bot Identity and Configuration Layer' \
  '# 11.60 — Platform Capability Catalog and Tool Resolution' \
  '# 11.61 — Web, Browser and Computer Use'
do
  test "$(grep -Fxc "$heading" "$P11")" = "1"
done
```

Expected: PASS.

- [ ] **Step 4: Verify permanent architectural invariants are represented**

Run:

```bash
P11="docs/roadmap/phase-11-stable-integrated-platform.md"

for marker in \
  'Bot' \
  'Agent' \
  'PlatformCapability' \
  'DomainCapability' \
  'Operation Registry' \
  'requested' \
  'effective' \
  'web.search' \
  'browser.navigate' \
  'computer.use' \
  'human' \
  'CMMChat'
do
  grep -Fiq "$marker" "$P11"
done
```

Expected: PASS.

- [ ] **Step 5: Verify CMMChat boundary across public docs**

Run:

```bash
grep -Fq 'CMMChat' README.md
grep -Fq 'CMMChat' ROADMAP.md
grep -Fq 'CMMChat' docs/roadmap/phase-11-stable-integrated-platform.md
```

Expected: PASS.

- [ ] **Step 6: Verify no CMMChat source is being changed**

Run:

```bash
! git status --porcelain | grep -Ei 'CMMChat|cmmchat'
```

Expected: exit `0`.

- [ ] **Step 7: Verify Phase 11 remains planned**

Run:

```bash
grep -A12 -F '## Phase 11 — Stable Integrated Platform' ROADMAP.md \
  | grep -Fq '**Status:** Planned.'
```

Expected: PASS.

- [ ] **Step 8: Verify Phase 10.44 closure remains intact**

Run:

```bash
grep -Fq '**Phase 10.44:** complete, independently audited and closed' ROADMAP.md

grep -Fq \
  'docs/audits/phase-10.44-independent-final-reaudit-v4.md' \
  docs/reference/domain-intelligence-requirements-matrix.md
```

Expected: PASS.

- [ ] **Step 9: Verify no false future audit claims**

Run:

```bash
! rg -n \
  'DP-05(9|60|61)=VERIFIED_EXISTING|AT-DP-05(9|60|61)=PASS|11\.5(9|60|61).*independently audited|11\.5(9|60|61).*closed' \
  ROADMAP.md \
  README.md \
  docs/roadmap/phase-11-stable-integrated-platform.md \
  docs/reference/domain-intelligence-requirements-matrix.md
```

Expected: exit `0`.

- [ ] **Step 10: Verify requirements markers**

Run:

```bash
MATRIX="docs/reference/domain-intelligence-requirements-matrix.md"

for marker in \
  F11-008 F11-009 F11-010 F11-011 F11-012 F11-013 \
  AT-F11-BOT-01 AT-F11-CAP-01 AT-F11-TOOL-01 \
  AT-F11-WEB-01 AT-F11-CU-01 AT-F11-BOT-PORT-01
do
  grep -Fq "$marker" "$MATRIX"
done
```

Expected: PASS.

- [ ] **Step 11: Verify detailed-roadmap fingerprint**

Run:

```bash
P11="docs/roadmap/phase-11-stable-integrated-platform.md"
MATRIX="docs/reference/domain-intelligence-requirements-matrix.md"

P11_SHA="$(shasum -a 256 "$P11" | awk '{print $1}')"

grep -Fq "$P11_SHA" "$MATRIX"

echo "P11_SHA256=$P11_SHA"
echo "SRC_R11_HASH_MATCH=PASS"
```

Expected: PASS.

- [ ] **Step 12: Run documentation-related repository tests if present**

Discover:

```bash
find tests \
  -type f \
  | grep -Ei 'roadmap|documentation|docs|requirements|reference' \
  | sort
```

If matching canonical repository tests exist, run all discovered files with:

```bash
DOC_TEST_FILES="$(
  find tests \
    -type f \
    | grep -Ei 'roadmap|documentation|docs|requirements|reference' \
    | sort \
    | tr '\n' ' '
)"

if [ -n "${DOC_TEST_FILES// }" ]; then
  .venv/bin/python -m pytest $DOC_TEST_FILES -q
  echo "DOC_TESTS=PASS"
else
  echo "DOC_TESTS=NOT_APPLICABLE_NO_CANONICAL_TESTS_FOUND"
fi
```

Expected: PASS.

If no matching tests exist, record:

```text
DOC_TESTS=NOT_APPLICABLE_NO_CANONICAL_TESTS_FOUND
```

Do not invent a new test suite in this documentation-only amendment.

- [ ] **Step 13: Run lightweight final gates**

Run:

```bash
git diff --check

test -f docs/superpowers/specs/2026-09-07-phase-11-bots-platform-capabilities-design.md
test -f docs/superpowers/plans/2026-09-08-phase-11-bots-platform-capabilities-roadmap-amendment-plan.md

echo "DOC_AMENDMENT_GATES=PASS"
```

Expected: `DOC_AMENDMENT_GATES=PASS`.

---

# Task 8: Commit the Four-Document Phase 11 Amendment

**Files:**
- Commit exactly:
  - `README.md`
  - `ROADMAP.md`
  - `docs/roadmap/phase-11-stable-integrated-platform.md`
  - `docs/reference/domain-intelligence-requirements-matrix.md`

**Interfaces:**
- Consumes: verified documentation amendment
- Produces: one committed Phase 11 roadmap amendment, worktree clean

- [ ] **Step 1: Stage exactly four files**

Run:

```bash
git add -- \
  README.md \
  ROADMAP.md \
  docs/roadmap/phase-11-stable-integrated-platform.md \
  docs/reference/domain-intelligence-requirements-matrix.md
```

- [ ] **Step 2: Verify staged scope exactly**

Run:

```bash
git diff --cached --name-only | sort
```

Expected exactly:

```text
README.md
ROADMAP.md
docs/reference/domain-intelligence-requirements-matrix.md
docs/roadmap/phase-11-stable-integrated-platform.md
```

Verify:

```bash
test "$(git diff --cached --name-only | wc -l | tr -d ' ')" = "4"
test -z "$(git diff --name-only)"
git diff --cached --check
```

Expected: PASS.

- [ ] **Step 3: Review staged summary**

Run:

```bash
git diff --cached --stat
git diff --cached -- ROADMAP.md | sed -n '1,220p'
git diff --cached -- README.md | sed -n '1,220p'
```

Also review all new `11.59–11.61` headings and matrix entries:

```bash
git diff --cached -- docs/roadmap/phase-11-stable-integrated-platform.md \
  | grep -E '^\+.*(11\.59|11\.60|11\.61|DP-059|DP-060|DP-061|CMMChat|computer\.use|PlatformCapability)'

git diff --cached -- docs/reference/domain-intelligence-requirements-matrix.md \
  | grep -E '^\+.*(F11-008|F11-009|F11-010|F11-011|F11-012|F11-013|AT-F11-|SRC-R11)'
```

Expected:
- only intended architecture/documentation additions.

- [ ] **Step 4: Commit**

Run:

```bash
git commit -m "docs(phase11): extend roadmap for bots and capabilities"
```

- [ ] **Step 5: Verify commit scope**

Run:

```bash
AMENDMENT_COMMIT="$(git rev-parse HEAD)"

git diff-tree --no-commit-id --name-only -r "$AMENDMENT_COMMIT" | sort
git show --check --oneline "$AMENDMENT_COMMIT"

test -z "$(git status --porcelain)"
git stash list | grep -Fq "quarantine: post-audit phase 10.32 uncommitted changes"

echo "AMENDMENT_COMMIT=$AMENDMENT_COMMIT"
echo "WORKTREE=CLEAN"
echo "QUARANTINE_STASH=PRESERVED"
```

Expected: four-file commit and clean worktree.

---

# Task 9: Final Local Verification Before GitHub Synchronization

**Files:**
- Read-only verification of repository

**Interfaces:**
- Consumes: plan commit + amendment commit
- Produces: verified local HEAD eligible for normal fast-forward push

- [ ] **Step 1: Confirm commit sequence**

Run:

```bash
git log -7 --oneline --decorate
```

Expected top sequence:

```text
the new roadmap-amendment commit: `docs(phase11): extend roadmap for bots and capabilities`
the immediately preceding plan commit: `docs(phase11): plan bots capability roadmap amendment`
b24a689: `docs(phase11): design bots and platform capabilities`
35ca06d: `docs(domains): close phase 10.44 memory knowledge integration`
2587563: `docs(audit): record phase 10.44 final reaudit v4 pass`
```

- [ ] **Step 2: Confirm worktree and quarantine**

Run:

```bash
test -z "$(git status --porcelain)"

git stash list | grep -Fq \
  "quarantine: post-audit phase 10.32 uncommitted changes"

echo "WORKTREE=CLEAN"
echo "QUARANTINE_STASH=PRESERVED"
```

Expected: PASS.

- [ ] **Step 3: Re-run final documentation invariants**

Run:

```bash
P11="docs/roadmap/phase-11-stable-integrated-platform.md"
MATRIX="docs/reference/domain-intelligence-requirements-matrix.md"

for heading in \
  '# 11.59 — Bot Identity and Configuration Layer' \
  '# 11.60 — Platform Capability Catalog and Tool Resolution' \
  '# 11.61 — Web, Browser and Computer Use'
do
  test "$(grep -Fxc "$heading" "$P11")" = "1"
done

P11_SHA="$(shasum -a 256 "$P11" | awk '{print $1}')"
grep -Fq "$P11_SHA" "$MATRIX"

grep -Fq 'CMMChat' "$P11"
grep -Fq 'CMMChat' ROADMAP.md
grep -Fq 'CMMChat' README.md

git diff --check
```

Expected: PASS.

- [ ] **Step 4: Record local sync candidate**

Run:

```bash
LOCAL_HEAD="$(git rev-parse HEAD)"
echo "LOCAL_SYNC_CANDIDATE=$LOCAL_HEAD"
```

Expected: one exact 40-character commit.

---

# Task 10: Fetch and Prove Fast-Forward Safety

**Files:**
- No file modifications

**Interfaces:**
- Consumes: clean committed local branch
- Produces: verified relationship between local branch and GitHub before push

- [ ] **Step 1: Fetch only; do not merge/rebase**

Run:

```bash
git fetch origin feature/phase-10-domain-intelligence
```

Expected:
- remote-tracking reference refreshed;
- no worktree mutation.

- [ ] **Step 2: Capture local and remote HEADs**

Run:

```bash
LOCAL_HEAD="$(git rev-parse HEAD)"
REMOTE_HEAD="$(git rev-parse origin/feature/phase-10-domain-intelligence)"

echo "LOCAL_HEAD=$LOCAL_HEAD"
echo "REMOTE_HEAD=$REMOTE_HEAD"
```

- [ ] **Step 3: Prove remote is an ancestor of local**

Run:

```bash
git merge-base --is-ancestor \
  origin/feature/phase-10-domain-intelligence \
  HEAD
```

Expected: exit `0`.

If this fails:
- **STOP**;
- do not push;
- do not merge;
- do not rebase;
- inspect divergence separately.

- [ ] **Step 4: Show divergence counts**

Run:

```bash
git rev-list --left-right --count \
  origin/feature/phase-10-domain-intelligence...HEAD
```

Expected shape:

```text
0    N

where `N` is the number of local commits not yet present on the remote and must be greater than or equal to 1 before the push.
```

The left count must be `0`.

- [ ] **Step 5: Reconfirm clean worktree**

Run:

```bash
test -z "$(git status --porcelain)"
git stash list | grep -Fq "quarantine: post-audit phase 10.32 uncommitted changes"
```

Expected: PASS.

---

# Task 11: Push the Feature Branch and Verify Exact Remote Synchronization

**Files:**
- No repository file modifications
- Remote Git reference update only

**Interfaces:**
- Consumes: fast-forward-safe local branch
- Produces: GitHub remote branch at exact local HEAD

- [ ] **Step 1: Perform normal push**

Run:

```bash
git push origin feature/phase-10-domain-intelligence
```

Forbidden:

```text
--force
--force-with-lease
```

Expected:
- normal fast-forward update succeeds.

- [ ] **Step 2: Fetch remote state after push**

Run:

```bash
git fetch origin feature/phase-10-domain-intelligence
```

Expected: PASS.

- [ ] **Step 3: Verify local tracking ref parity**

Run:

```bash
LOCAL_HEAD="$(git rev-parse HEAD)"
TRACKING_HEAD="$(git rev-parse origin/feature/phase-10-domain-intelligence)"

test "$LOCAL_HEAD" = "$TRACKING_HEAD"

echo "LOCAL_HEAD=$LOCAL_HEAD"
echo "TRACKING_HEAD=$TRACKING_HEAD"
echo "LOCAL_TRACKING_PARITY=PASS"
```

Expected: `LOCAL_TRACKING_PARITY=PASS`.

- [ ] **Step 4: Verify GitHub advertised branch SHA**

Run:

```bash
REMOTE_ADVERTISED_HEAD="$(
  git ls-remote \
    origin \
    refs/heads/feature/phase-10-domain-intelligence \
  | awk '{print $1}'
)"

LOCAL_HEAD="$(git rev-parse HEAD)"

test "$REMOTE_ADVERTISED_HEAD" = "$LOCAL_HEAD"

echo "REMOTE_ADVERTISED_HEAD=$REMOTE_ADVERTISED_HEAD"
echo "REMOTE_EXACT_HEAD=PASS"
```

Expected: `REMOTE_EXACT_HEAD=PASS`.

- [ ] **Step 5: Verify branch is no longer ahead/behind**

Run:

```bash
git status --short --branch
```

Expected:
- no `[ahead N]`;
- no `[behind N]`;
- clean branch.

- [ ] **Step 6: Preserve quarantine stash after network operation**

Run:

```bash
git stash list | grep -Fq \
  "quarantine: post-audit phase 10.32 uncommitted changes"

echo "QUARANTINE_STASH=PRESERVED"
```

Expected: PASS.

---

# Task 12: Final Synchronization Report

**Files:**
- No mutations

**Interfaces:**
- Consumes: exact synchronized branch
- Produces: auditable final state for the user

- [ ] **Step 1: Capture final identities**

Run:

```bash
FINAL_HEAD="$(git rev-parse HEAD)"
REMOTE_HEAD="$(git rev-parse origin/feature/phase-10-domain-intelligence)"
SPEC_COMMIT="b24a68925e0132b1c52b819669b1fc734fa454ce"

PLAN_COMMIT="$(
  git log \
    --format='%H %s' \
    --grep='^docs(phase11): plan bots capability roadmap amendment$' \
    -1 \
  | awk '{print $1}'
)"

AMENDMENT_COMMIT="$(
  git log \
    --format='%H %s' \
    --grep='^docs(phase11): extend roadmap for bots and capabilities$' \
    -1 \
  | awk '{print $1}'
)"

P11_SHA="$(
  shasum -a 256 \
    docs/roadmap/phase-11-stable-integrated-platform.md \
  | awk '{print $1}'
)"
```

- [ ] **Step 2: Assert final invariants**

Run:

```bash
test "$FINAL_HEAD" = "$REMOTE_HEAD"
test -n "$PLAN_COMMIT"
test -n "$AMENDMENT_COMMIT"
test -z "$(git status --porcelain)"

git stash list | grep -Fq \
  "quarantine: post-audit phase 10.32 uncommitted changes"

grep -A12 -F '## Phase 11 — Stable Integrated Platform' ROADMAP.md \
  | grep -Fq '**Status:** Planned.'
```

Expected: PASS.

- [ ] **Step 3: Print final report**

Required report:

```text
PHASE10_44=CLOSED
FINAL_INDEPENDENT_REAUDIT_V4=PASS

PHASE11=PLANNED

PHASE11_AMENDMENT_SPEC=COMMITTED
PHASE11_AMENDMENT_PLAN=COMMITTED
PHASE11_ROADMAP_AMENDMENT=COMMITTED

DP_059=DESIGNED_PLANNED
DP_060=DESIGNED_PLANNED
DP_061=DESIGNED_PLANNED

AT_DP_059=NOT_YET_IMPLEMENTED
AT_DP_060=NOT_YET_IMPLEMENTED
AT_DP_061=NOT_YET_IMPLEMENTED

CMMCHAT_FIRST_PARTY_CLIENT_REFERENCE=DOCUMENTED
CMMCHAT_CODE_MODIFIED=NO

P11_SHA256=$P11_SHA
SPEC_COMMIT=$SPEC_COMMIT
PLAN_COMMIT=$PLAN_COMMIT
AMENDMENT_COMMIT=$AMENDMENT_COMMIT

LOCAL_HEAD=$FINAL_HEAD
REMOTE_HEAD=$REMOTE_HEAD
LOCAL_REMOTE_PARITY=PASS

WORKTREE=CLEAN
QUARANTINE_STASH=PRESERVED

PUSH=PASS
MERGE=NO
FORCE_PUSH=NO
```

---

# Acceptance Criteria for This Documentation Amendment

The amendment is complete only when every statement below is true.

## Architecture

- [ ] `Bot != Agent` is explicit.
- [ ] `PlatformCapability != DomainCapability` is explicit.
- [ ] `Capability != ToolImplementation != Operation` is explicit.
- [ ] No second executable Tool Registry is introduced.
- [ ] Existing Agent Runtime remains authoritative.
- [ ] Existing approvals remain authoritative.
- [ ] Existing autonomy remains authoritative.
- [ ] Existing budgets remain authoritative.
- [ ] Existing validation remains authoritative.
- [ ] Domain permissions can only narrow effective platform authority.
- [ ] `requested capability != effective permission` is explicit.
- [ ] Agent binding cannot grant Computer Use.
- [ ] Provider/model output cannot grant authority.
- [ ] Import/export cannot carry secrets or effective privileged authority.

## Phase 11 Structure

- [ ] 11.59 exists exactly once.
- [ ] 11.60 exists exactly once.
- [ ] 11.61 exists exactly once.
- [ ] DP-059 is documented as future/planned.
- [ ] DP-060 is documented as future/planned.
- [ ] DP-061 is documented as future/planned.
- [ ] AT-DP-059 is documented but not PASS.
- [ ] AT-DP-060 is documented but not PASS.
- [ ] AT-DP-061 is documented but not PASS.
- [ ] Phase 11 remains `Planned`.

## Web / Browser / Computer Use

- [ ] `web.search` is separate.
- [ ] browser navigation is separate.
- [ ] authenticated browser authority is separate.
- [ ] `computer.use` is separate.
- [ ] Computer Use requires explicit authority.
- [ ] Computer Use supports cancellation.
- [ ] Computer Use supports human takeover.
- [ ] Resume requires authority revalidation.
- [ ] sensitive/irreversible effects use canonical approval.
- [ ] credentials are isolated from Bot/model payloads.

## Requirements Matrix

- [ ] F11-008 exists.
- [ ] F11-009 exists.
- [ ] F11-010 exists.
- [ ] F11-011 exists.
- [ ] F11-012 exists.
- [ ] F11-013 exists.
- [ ] AT-F11-BOT-01 exists and is not PASS.
- [ ] AT-F11-CAP-01 exists and is not PASS.
- [ ] AT-F11-TOOL-01 exists and is not PASS.
- [ ] AT-F11-WEB-01 exists and is not PASS.
- [ ] AT-F11-CU-01 exists and is not PASS.
- [ ] AT-F11-BOT-PORT-01 exists and is not PASS.
- [ ] `SRC-R11` SHA-256 matches exact final detailed Phase 11 roadmap bytes.
- [ ] DP-044 / AT-DP-044 V4 closure evidence remains intact.

## CMMChat

- [ ] README identifies CMMChat as first-party client/UI.
- [ ] ROADMAP identifies CMMChat as first-party client/UI.
- [ ] detailed Phase 11 roadmap identifies CMMChat as first-party client/UI.
- [ ] documentation states CMMChat UI is already under active development.
- [ ] CMM OS remains authority owner.
- [ ] CMM OS Core/Runtime does not depend on CMMChat implementation.
- [ ] no CMMChat code is modified.

## Git / Repository

- [ ] design spec commit remains dedicated.
- [ ] plan commit is dedicated.
- [ ] roadmap amendment commit contains exactly four documentation files.
- [ ] worktree is clean.
- [ ] quarantine stash is preserved.
- [ ] no merge occurs.
- [ ] final push is normal fast-forward.
- [ ] no force push occurs.
- [ ] local HEAD equals tracking HEAD.
- [ ] local HEAD equals GitHub advertised branch HEAD.

---

# Future Work Explicitly Deferred

After this amendment and GitHub synchronization, **do not** treat 11.59–11.61 as implemented.

When Phase 11 formally begins, prepare separate design/implementation execution plans as needed:

```text
11.59 — Bot Identity and Configuration Layer
11.60 — Platform Capability Catalog and Tool Resolution
11.61 — Web, Browser and Computer Use
```

Each future subphase must independently follow:

```text
INSPECTION
→ exact scope
→ spec where needed
→ plan
→ TDD
→ focused tests
→ regression suites
→ global suite
→ Ruff
→ format
→ compileall
→ git diff --check
→ implementation commit
→ clean exact HEAD
→ audit bundle
→ independent audit
→ remediation if required
→ PASS
→ docs-only closure commit
```

No future implementation may reinterpret this amendment by creating parallel canonical owners.

---

# Final Expected State

After executing this plan successfully:

```text
Phase 10.44
= CLOSED / independently audited V4 PASS

Phase 11
= PLANNED

11.59
= DESIGNED / PLANNED

11.60
= DESIGNED / PLANNED

11.61
= DESIGNED / PLANNED

CMMChat
= first-party conversational client/UI
= interface development already active
= no source changes from this CMM OS amendment

CMM OS
= canonical runtime and authority owner

Git
= worktree clean
= quarantine stash preserved
= local feature branch exactly synchronized with GitHub
= no merge
= no force push
```
