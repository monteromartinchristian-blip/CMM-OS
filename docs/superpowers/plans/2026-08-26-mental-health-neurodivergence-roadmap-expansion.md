# Mental Health + Neurodivergence Roadmap Expansion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Amend the live CMM OS roadmap/specifications so Phase 10 appends `10.52 — Mental Health Domain` and `10.53 — Neurodivergence Domain`, while preserving all existing Phase 0–9 closures, Phase 10 numbering/status history, and Phase 11 architecture.

**Architecture:** This is a documentation/specification change only. `domain:health`, `domain:mental-health`, and `domain:neurodivergence` become sibling Domain Packs that reuse the existing Phase 8 Cognitive Layer, Phase 9 Agent Runtime, and Phase 10 cross-domain contracts; no new engine/runtime/store is introduced. Phase 11 remains generic and is updated only where examples/catalog surfaces must recognize the two new canonical domains.

**Tech Stack:** Markdown roadmap/specification files, Git, Python 3 verification scripts, ripgrep, existing pytest suite.

**Spec:** `docs/superpowers/specs/2026-08-26-mental-health-neurodivergence-domain-expansion-design.md`

## Global Constraints

- Append **10.52** and **10.53**; do not renumber any existing Phase 10 section.
- `domain:health`, `domain:mental-health`, and `domain:neurodivergence` are sibling domains.
- `domain:mental-health` uses `MentalHealthProfile`.
- `domain:neurodivergence` uses `NeurodivergenceProfile`.
- Both new domains default to `SENSITIVE`.
- Phase 0–9 implementation remains closed; no production or test code from those phases is changed.
- Phase 8 keeps one shared Knowledge Model/Cognitive Layer; no domain-specific cognitive engine.
- Phase 9 keeps one shared Agent Runtime; no domain-specific runtime.
- Existing Health 10.20 implementation is not reopened or rewritten.
- Existing completed/audited Phase 10 status/history must never be downgraded.
- Preserve current live Phase 10.29+ repository progress exactly; the uploaded snapshots are reference material only.
- Do not silently migrate, duplicate, or reclassify existing Health knowledge.
- Cross-domain transfer preserves provenance, epistemic kind, temporal validity, uncertainty, sensitivity, purpose limitation, permissions, and source-domain authority.
- `parenthood` is canonical; do not reintroduce `domain:nil`.
- In Phase 11 examples, `domain="medical"` means the canonical Health domain and must become `domain="health"`.
- No production implementation of 10.52/10.53 is part of this plan.
- No push and no merge.
- Do not hard-code historical test counts; record fresh results.

---

## File Map

**Create**
- `docs/superpowers/specs/2026-08-26-mental-health-neurodivergence-domain-expansion-design.md`

**Modify**
- `docs/roadmap/phase-10-domain-intelligence.md`
- `docs/roadmap/phase-11-stable-integrated-platform.md`
- `docs/reference/domain-intelligence-requirements-matrix.md`
- `docs/audits/phase-10.15-prompts-preflight.md`
- `ROADMAP.md`

**Do not modify**
- `cmm/**`
- `tests/**` except running existing tests
- Phase 0–9 implementation/reference files unless a stale *forward reference only* names a fixed Phase 10 domain catalog. If such a forward-reference exists, stop and report it before editing; do not broaden scope silently.

---

### Task 1: Preflight the live repository and install the approved design spec

**Files:**
- Create: `docs/superpowers/specs/2026-08-26-mental-health-neurodivergence-domain-expansion-design.md`
- Preserve/add: `docs/superpowers/plans/2026-08-26-mental-health-neurodivergence-roadmap-expansion.md`
- Read only: all target files from the File Map

**Interfaces:**
- Consumes: approved design artifact supplied by the user.
- Produces: a frozen in-repo design spec and a recorded live baseline for later tasks.

- [ ] **Step 1: Record live baseline**

Run:

```bash
cd "/Users/chris/CMM OS"
set -euo pipefail

test "$(git branch --show-current)" = "feature/phase-10-domain-intelligence"

BASE_HEAD="$(git rev-parse HEAD)"
BASE_HEAD_SHORT="$(git rev-parse --short HEAD)"
printf '%s\n' "$BASE_HEAD" > /tmp/cmm-roadmap-expansion-base-head.txt

echo "BASE_HEAD=$BASE_HEAD"
echo "BASE_HEAD_SHORT=$BASE_HEAD_SHORT"
git status --short --branch
git log -12 --oneline --decorate
```

If tracked or staged changes already exist, stop and report them. Pre-existing untracked audit bundles or `tmp/` may remain only if they are already part of the established workflow and are not staged.

- [ ] **Step 2: Inspect the live documents before mutation**

Run:

```bash
rg -n \
  '10\.51|10\.52|10\.53|domain:health|domain:parenthood|domain:nil|Mental Health|Neurodiverg|Implementation Order' \
  docs/roadmap/phase-10-domain-intelligence.md

rg -n \
  'DP-029|DP-030|DP-052|DP-053|10\.29|10\.30|10\.52|10\.53' \
  docs/reference/domain-intelligence-requirements-matrix.md

rg -n \
  'Neurodivergencia|Salud Mental|domain:health|domain:parenthood|domain:nil' \
  docs/audits/phase-10.15-prompts-preflight.md

rg -n \
  'domain="medical"|domain="health"|Domain Router|Timeline|Search|Model Evaluation|by_domain' \
  docs/roadmap/phase-11-stable-integrated-platform.md

rg -n \
  'Phase 10|Current progress|Initial domains|health|parenthood|nil|mental-health|neurodivergence' \
  ROADMAP.md
```

Confirm that live repository content is newer than or equal to the uploaded reference snapshots. Do not copy whole snapshot files over live files.

- [ ] **Step 3: Add the approved spec**

Copy the approved design artifact into:

```text
docs/superpowers/specs/2026-08-26-mental-health-neurodivergence-domain-expansion-design.md
docs/superpowers/plans/2026-08-26-mental-health-neurodivergence-roadmap-expansion.md
```

Then verify:

```bash
grep -Fq '10.52 — Mental Health Domain' \
  docs/superpowers/specs/2026-08-26-mental-health-neurodivergence-domain-expansion-design.md

grep -Fq '10.53 — Neurodivergence Domain' \
  docs/superpowers/specs/2026-08-26-mental-health-neurodivergence-domain-expansion-design.md

grep -Fq 'No implementation change and no reopening.' \
  docs/superpowers/specs/2026-08-26-mental-health-neurodivergence-domain-expansion-design.md
```

- [ ] **Step 4: Commit the frozen design**

```bash
git add -- \
  docs/superpowers/specs/2026-08-26-mental-health-neurodivergence-domain-expansion-design.md \
  docs/superpowers/plans/2026-08-26-mental-health-neurodivergence-roadmap-expansion.md

git diff --cached --check
git diff --cached --name-status

git commit -m "docs(domains): freeze mental health and neurodivergence expansion"
```

Expected scope: exactly the approved design spec and this implementation plan.

---

### Task 2: Correct prompt reconciliation and requirements ownership

**Files:**
- Modify: `docs/audits/phase-10.15-prompts-preflight.md`
- Modify: `docs/reference/domain-intelligence-requirements-matrix.md`

**Interfaces:**
- Consumes: approved domain boundaries from the design spec.
- Produces: authoritative planning/requirements ownership for `DP-052` and `DP-053`.

- [ ] **Step 1: Amend the Phase 10.15 prompt reconciliation without erasing history**

Preserve the original dated preflight decision as historical evidence. Append a clearly dated amendment section for **2026-08-26** stating that the earlier combined Health assignment is superseded for future Domain Pack ownership.

The amendment must preserve:

```text
Salud -> domain:health -> 10.20
Organización clínica Notion -> domain:health -> 10.20 + workflows
```

and establish the current mappings:

```text
Salud Mental -> domain:mental-health -> 10.52
Neurodivergencia -> domain:neurodivergence -> 10.53
```

If the live document contains an active/current summary table separate from the historical original table, update that current summary too. Do not delete the original mapping; label its ownership decision as superseded by the 2026-08-26 amendment.

The explanatory text must state:

```text
10.20 Health remains closed and authoritative for medical/clinical facts,
medication, diagnosis status, treatment and clinical documentation.

10.52 Mental Health and 10.53 Neurodivergence are later sibling Domain
Packs. This is a requirements reassignment, not a reopening of 10.20 or
10.11–10.15 infrastructure.
```

Also preserve the existing current `domain:parenthood` mapping. Do not restore `domain:nil`.

- [ ] **Step 2: Add explicit cross-domain requirements**

The preflight must record at least these invariants:

```text
Mental Health -> may consume purpose-minimized Health clinical context;
                must not inherit clinical presentation by default.

Neurodivergence -> may consume purpose-minimized Health medication/
                   diagnosis data and Mental Health emotional/therapy context.

Health -> remains authoritative for clinical diagnosis/treatment/medication.

Mental Health / Neurodivergence -> SENSITIVE.

No supporting domain may widen permissions or promote hypotheses to facts.
```

- [ ] **Step 3: Add `DP-052` and `DP-053` rows to the requirements matrix**

Follow the live table schema and current status vocabulary.

Add one row for each new Domain Pack:

```text
DP-052
Mental Health: emotional wellbeing, therapy continuity, therapy-session
analysis, non-clinical conversational support, emotional context,
uncertainty, safety escalation, cross-domain coordination.

Responsible phase: 10.52
Repository mapping: shared domain infrastructure; implementation pending
Mapping status: REQUIRES_PHASE_INSPECTION
Acceptance test: AT-DP-052
```

```text
DP-053
Neurodivergence: TDAH, possible/in-evaluation TEA/AACC/TERIA, dysgraphia,
developmental history, executive/sensory/social functioning,
neuropsychological assessment, differential overlap analysis and certainty
hierarchy.

Responsible phase: 10.53
Repository mapping: shared domain infrastructure; implementation pending
Mapping status: REQUIRES_PHASE_INSPECTION
Acceptance test: AT-DP-053
```

For the `Primary source` column, inspect the live source registry/table and reuse the existing source record(s) that correspond to the supplied Mental Health and Neurodivergence prompt corpus. If the current source registry only has a single combined prompt source, keep that provenance and distinguish the two requirements at DP level; do **not** invent an unsupported source ID.

- [ ] **Step 4: Extend any Phase 10 domain summary table**

If the matrix contains a Phase 10 domain summary table, append:

```text
10.52 | Mental Health
10.53 | Neurodivergence
```

Do not insert them between existing rows. Do not renumber 10.20–10.30 or 10.31–10.51.

- [ ] **Step 5: Verify conservative status**

Run:

```bash
python3 - <<'PY'
from pathlib import Path

p = Path("docs/reference/domain-intelligence-requirements-matrix.md")
text = p.read_text(encoding="utf-8")

for dp, phase, at in (
    ("DP-052", "10.52", "AT-DP-052"),
    ("DP-053", "10.53", "AT-DP-053"),
):
    rows = [line for line in text.splitlines() if line.startswith(f"| `{dp}` |")]
    assert len(rows) == 1, (dp, len(rows))
    row = rows[0]
    assert f"| {phase} |" in row
    assert "`REQUIRES_PHASE_INSPECTION`" in row
    assert f"`{at}`" in row
    assert "`VERIFIED_EXISTING`" not in row
    assert "`PASS`" not in row

preflight = Path("docs/audits/phase-10.15-prompts-preflight.md").read_text(
    encoding="utf-8"
)
assert "domain:mental-health" in preflight
assert "domain:neurodivergence" in preflight
assert "domain:parenthood" in preflight
print("REQUIREMENTS_OWNERSHIP=PASS")
PY
```

- [ ] **Step 6: Commit**

```bash
git diff --check

git add -- \
  docs/audits/phase-10.15-prompts-preflight.md \
  docs/reference/domain-intelligence-requirements-matrix.md

git diff --cached --check
git diff --cached --name-status

git commit -m "docs(domains): assign mental health and neurodivergence requirements"
```

---

### Task 3: Expand the Phase 10 specification without renumbering existing work

**Files:**
- Modify: `docs/roadmap/phase-10-domain-intelligence.md`

**Interfaces:**
- Consumes: `DP-052`, `DP-053`, approved domain-boundary spec.
- Produces: canonical Phase 10 planning specification for later independent implementation of both Domain Packs.

- [ ] **Step 1: Update shared canonical domain catalogs**

Where the Phase 10 spec enumerates canonical/initial domains, ensure the current list includes:

```text
domain:general
domain:health
domain:relationships
domain:university
domain:oppositions
domain:reflection
domain:concerns
domain:languages
domain:parenthood
domain:sport
domain:life-plan
domain:project
domain:mental-health
domain:neurodivergence
```

Preserve any additional live domains that were added after the snapshot.

Do not remove historical narrative references inside audit/history sections unless they are active architecture claims. Active architecture must contain zero `domain:nil`.

- [ ] **Step 2: Update shared profile/composition/privacy surfaces**

Add both new domains anywhere the specification maintains a canonical list for:

- profile registry/examples;
- domain resolution examples;
- multi-domain composition;
- cross-domain coordination;
- domain resources;
- domain permissions;
- Domain Knowledge Packages;
- benchmark suites;
- quality metrics;
- privacy orientation;
- closure criteria.

Privacy orientation must include:

```text
Mental Health      -> SENSITIVE
Neurodivergence    -> SENSITIVE
```

Cross-domain examples must establish sibling ownership, including examples equivalent to:

```text
neurodivergence primary + health/mental-health supporting
mental-health primary + relationships/neurodivergence/health supporting
health primary + mental-health/neurodivergence supporting when relevant
```

No example may imply that Mental Health or Neurodivergence is nested under Health.

- [ ] **Step 3: Append `10.52 - Mental Health Domain` after the complete 10.51 section**

Do not insert before 10.51. Append after the existing 10.51 Implementation Order and its closure/outcome text.

The 10.52 section must contain these explicit subsections or equivalent headings:

```text
Objective
Canonical identity
Scope
Non-goals
Knowledge / epistemic requirements
Resources
Reasoning profile
Rules
Operations
Workflows
Permissions and approvals
Cross-domain coordination
Memory
Presentation
Traceability
Privacy
Knowledge Package
Benchmarks and quality metrics
AT-DP-052 acceptance contract
Implementation boundary
Completion criteria
```

Required semantic content:

```text
id = domain:mental-health
profile = MentalHealthProfile
privacy = SENSITIVE
```

Mental Health owns:

- emotional wellbeing;
- ordinary emotional conversation/support;
- therapy continuity;
- therapy-session transcript analysis;
- preparation before therapy;
- processing after therapy;
- longitudinal emotional context;
- emotionally relevant decisions;
- facts vs interpretations vs fears vs intuitions;
- loop/over-analysis detection without pathologizing ordinary conversation.

It must explicitly distinguish:

```text
ordinary emotional conversation
therapeutic reflection
clinical psychiatric information
actual immediate safety risk
```

It must explicitly prohibit:

```text
default medicalization of normal emotional conversation
diagnosis from conversation
treatment/dose changes
silent persistence of sensitive inference
silent cross-domain transfer
autonomous external communication
parallel MentalHealth runtime/planner/memory/knowledge engine
```

Health is authoritative for clinical diagnosis/treatment/medication.

- [ ] **Step 4: Append `10.53 - Neurodivergence Domain` after 10.52**

Use the same planning depth/structure as 10.52.

Required semantic content:

```text
id = domain:neurodivergence
profile = NeurodivergenceProfile
privacy = SENSITIVE
```

Neurodivergence owns:

- confirmed TDAH information;
- possible/in-evaluation TEA;
- possible/in-evaluation high intellectual abilities;
- possible/in-evaluation ARFID/TERIA;
- dysgraphia;
- developmental history;
- executive functioning;
- sensory functioning;
- academic/functional impact;
- social functioning through a neurodevelopmental lens;
- neuropsychological assessments;
- differential-overlap analysis.

The certainty hierarchy must explicitly preserve:

```text
CONFIRMED
IN EVALUATION
HYPOTHESIS
NOT CONFIRMED / RULED OUT / INSUFFICIENTLY SUPPORTED
```

It must explicitly prohibit:

```text
screening -> diagnosis promotion
self-report -> diagnosis promotion
isolated trait -> stable identity/diagnosis promotion
model inference -> confirmed diagnosis
automatic attribution of all difficulties to neurodivergence
treatment/dose changes
parallel Neurodivergence runtime/planner/memory/knowledge engine
```

Cross-domain boundaries:

```text
Health -> clinical diagnosis status, medication, treatment, medical data
Mental Health -> emotional/therapy context
University -> academic/functional context
Relationships -> social/relational context
General -> fallback
```

All supporting data is purpose-minimized and permission-filtered.

- [ ] **Step 5: Add future acceptance identities**

The spec must reserve:

```text
DP-052 / AT-DP-052
DP-053 / AT-DP-053
```

Do not define either acceptance test as PASS. They are future implementation gates.

- [ ] **Step 6: Extend Phase 10 closure/outcome text**

Where Phase 10 lists required functional Domain Packs, add:

```text
Mental Health Domain
Neurodivergence Domain
```

Add outcome examples showing that CMM OS may:

```text
support emotional/therapy continuity without turning all conversation clinical;
organize longitudinal neurodivergence evidence without promoting hypotheses to diagnosis.
```

Preserve all existing completed-domain closure evidence.

- [ ] **Step 7: Verify numbering and canonical identity**

Run:

```bash
python3 - <<'PY'
from pathlib import Path

p = Path("docs/roadmap/phase-10-domain-intelligence.md")
text = p.read_text(encoding="utf-8")

markers = {
    "10.51": text.find("10.51"),
    "10.52": text.find("10.52"),
    "10.53": text.find("10.53"),
}
assert all(v >= 0 for v in markers.values()), markers
assert markers["10.51"] < markers["10.52"] < markers["10.53"], markers

assert "domain:mental-health" in text
assert "MentalHealthProfile" in text
assert "domain:neurodivergence" in text
assert "NeurodivergenceProfile" in text
assert "AT-DP-052" in text
assert "AT-DP-053" in text
assert "Mental Health" in text and "SENSITIVE" in text
assert "Neurodivergence" in text and "SENSITIVE" in text

print("PHASE10_APPEND_ORDER=PASS")
PY

if git grep -n -I -E \
  'domain:nil|nil\.' \
  -- docs/roadmap/phase-10-domain-intelligence.md
then
  echo "ERROR: active legacy Nil architecture remains in Phase 10 roadmap"
  exit 1
fi
```

If a historical quotation is the only remaining `Nil` hit, do not blindly rewrite it; document why it is historical and ensure active canonical sections use Parenthood.

- [ ] **Step 8: Commit**

```bash
git diff --check

git add -- docs/roadmap/phase-10-domain-intelligence.md

git diff --cached --check
git diff --cached --name-status

git commit -m "docs(domains): append phase 10.52 and 10.53 specifications"
```

---

### Task 4: Update the public ROADMAP without regressing live progress

**Files:**
- Modify: `ROADMAP.md`

**Interfaces:**
- Consumes: live Phase 10 progress and new canonical domain list.
- Produces: concise public roadmap consistent with detailed Phase 10/11 specifications.

- [ ] **Step 1: Preserve live status first**

Read the current top-level Phase table, current release, `Next milestone`, and Phase 10 progress text.

Do **not** replace them with the old uploaded snapshot values.

Do not change the current 10.29/10.30 implementation/audit status except where wording such as “remaining work through 10.30” must now acknowledge later 10.52/10.53 planned work.

- [ ] **Step 2: Update the public Phase 10 domain list**

The active list must contain:

```text
general
health
relationships
university
oppositions
reflection
concerns
languages
parenthood
sport
life-plan
project
mental-health
neurodivergence
```

Preserve any other canonical live domain entries.

There must be no active `nil` entry.

- [ ] **Step 3: Explain sibling-domain relationship concisely**

Add one concise sentence equivalent to:

```text
Health, Mental Health, and Neurodivergence are independent sibling Domain
Packs with explicit cross-domain projections; Health retains authority for
clinical medical facts and treatment.
```

- [ ] **Step 4: Preserve Phase 11 genericity**

Do not hard-code Mental Health/Neurodivergence into Phase 11 architecture diagrams. Phase 11 should continue to consume Domain Intelligence generically.

- [ ] **Step 5: Verify public roadmap consistency**

```bash
python3 - <<'PY'
from pathlib import Path

text = Path("ROADMAP.md").read_text(encoding="utf-8")

for item in (
    "mental-health",
    "neurodivergence",
    "parenthood",
):
    assert item in text, item

assert "\nnil\n" not in text

phase10 = text.index("## Phase 10")
phase11 = text.index("## Phase 11", phase10)
section = text[phase10:phase11]

assert "mental-health" in section
assert "neurodivergence" in section
assert "parenthood" in section

print("PUBLIC_ROADMAP_DOMAIN_CATALOG=PASS")
PY
```

- [ ] **Step 6: Commit**

```bash
git diff --check
git add -- ROADMAP.md
git diff --cached --check
git diff --cached --name-status
git commit -m "docs(roadmap): add mental health and neurodivergence domains"
```

---

### Task 5: Integrate the new domains into the planned Phase 11 platform

**Files:**
- Modify: `docs/roadmap/phase-11-stable-integrated-platform.md`

**Interfaces:**
- Consumes: canonical domain IDs and Phase 11's existing generic platform contracts.
- Produces: Phase 11 examples/integration requirements that do not assume a single monolithic medical domain.

- [ ] **Step 1: Normalize legacy `medical` domain examples**

Replace example values that mean the Phase 10 Health domain:

```python
domain="medical"
```

with:

```python
domain="health"
```

For profile examples, use the live canonical Health profile name from the repository. Do not invent a new profile name if the current Phase 10 Health spec defines one.

At minimum inspect and normalize examples in:

- OrchestrationResult;
- TimelineEvent;
- SearchResult;
- any other actual domain-ID examples.

Do not rewrite ordinary prose such as “medical appointment” or “medical decision” when it is not a domain identifier.

- [ ] **Step 2: Extend Domain Router / Context Resolver requirements**

Explicitly require the router to distinguish:

```text
health
mental-health
neurodivergence
```

and to support primary/supporting compositions among them.

No new router class is introduced.

- [ ] **Step 3: Extend generic platform surfaces**

Where Phase 11 enumerates required behavior, ensure the two new domains are naturally supported by:

- domain configuration and enable/disable;
- per-domain privacy/autonomy policy;
- Timeline filtering;
- Search filtering/facets;
- Knowledge Explorer domain filtering;
- Memory Workspace isolation/retention;
- Workflow routing/templates;
- model-routing policy;
- Model Evaluation Framework;
- Cost Management / by-domain dashboard;
- provider evaluation by domain;
- Knowledge Package export;
- audit/tracing;
- E2E domain routing and cross-domain isolation tests.

Phrase these as generic “all installed domains, including …” requirements where examples improve clarity. Do not fork Phase 11 into domain-specific infrastructure.

- [ ] **Step 4: Add E2E coverage requirements**

Add at least these future acceptance scenarios to the relevant Phase 11 testing section without renumbering existing scenarios unless the live document's style requires appended items:

```text
Mental Health request routes to domain:mental-health without inheriting
Health clinical presentation by default.

Neurodivergence request routes to domain:neurodivergence and may receive
only authorized/minimized Health clinical projections.

A mixed request can select one primary domain plus explicit supporting
health / mental-health / neurodivergence domains under restrictive
permission intersection.

Search/Timeline/domain dashboards keep the three domain identities
distinct.

Provider/model routing cannot weaken SENSITIVE privacy for either new
domain.
```

- [ ] **Step 5: Verify no canonical `medical` ID remains**

Run:

```bash
if rg -n 'domain="medical"|domain:medical|\bprimary_domain="medical"\b' \
  docs/roadmap/phase-11-stable-integrated-platform.md
then
  echo "ERROR: legacy canonical medical domain identifier remains"
  exit 1
fi

grep -Fq 'domain="health"' \
  docs/roadmap/phase-11-stable-integrated-platform.md

grep -Fq 'mental-health' \
  docs/roadmap/phase-11-stable-integrated-platform.md

grep -Fq 'neurodivergence' \
  docs/roadmap/phase-11-stable-integrated-platform.md
```

- [ ] **Step 6: Commit**

```bash
git diff --check
git add -- docs/roadmap/phase-11-stable-integrated-platform.md
git diff --cached --check
git diff --cached --name-status
git commit -m "docs(platform): integrate new phase 10 domains"
```

---

### Task 6: Cross-document consistency and no-reopen verification

**Files:**
- No intended edits unless a verification failure identifies a documentation inconsistency within the approved scope.

**Interfaces:**
- Consumes: all documentation changes.
- Produces: evidence that the roadmap modification is internally consistent and did not change implementation.

- [ ] **Step 1: Verify exact changed-file scope since baseline**

Run:

```bash
BASE_HEAD="$(cat /tmp/cmm-roadmap-expansion-base-head.txt)"

git diff --name-status "$BASE_HEAD..HEAD"
```

Allowed committed paths:

```text
ROADMAP.md
docs/audits/phase-10.15-prompts-preflight.md
docs/reference/domain-intelligence-requirements-matrix.md
docs/roadmap/phase-10-domain-intelligence.md
docs/roadmap/phase-11-stable-integrated-platform.md
docs/superpowers/specs/2026-08-26-mental-health-neurodivergence-domain-expansion-design.md
```

No `cmm/**` or `tests/**` file may be changed by these commits.

- [ ] **Step 2: Run cross-document semantic gate**

```bash
python3 - <<'PY'
from pathlib import Path

phase10 = Path("docs/roadmap/phase-10-domain-intelligence.md").read_text(encoding="utf-8")
phase11 = Path("docs/roadmap/phase-11-stable-integrated-platform.md").read_text(encoding="utf-8")
matrix = Path("docs/reference/domain-intelligence-requirements-matrix.md").read_text(encoding="utf-8")
preflight = Path("docs/audits/phase-10.15-prompts-preflight.md").read_text(encoding="utf-8")
roadmap = Path("ROADMAP.md").read_text(encoding="utf-8")

for canonical in ("domain:mental-health", "domain:neurodivergence"):
    assert canonical in phase10
    assert canonical in preflight

for public in ("mental-health", "neurodivergence"):
    assert public in roadmap
    assert public in phase11

for dp, at, phase in (
    ("DP-052", "AT-DP-052", "10.52"),
    ("DP-053", "AT-DP-053", "10.53"),
):
    assert dp in matrix
    assert at in matrix
    assert phase in matrix
    assert dp in phase10
    assert at in phase10

assert phase10.find("10.51") < phase10.find("10.52") < phase10.find("10.53")
assert 'domain="medical"' not in phase11

print("CROSS_DOCUMENT_CONSISTENCY=PASS")
PY
```

- [ ] **Step 3: Verify Phase 0–9 were not reopened**

Run:

```bash
git diff --name-only "$BASE_HEAD..HEAD" -- \
  'cmm/**' \
  'tests/**' \
  'docs/roadmap/phase-[0-9]-*.md' \
  'docs/reference/*phase-[0-9]*' \
  | tee /tmp/cmm-domain-expansion-forbidden-scope.txt

test ! -s /tmp/cmm-domain-expansion-forbidden-scope.txt
echo "PHASE_0_9_REOPENED=NO"
```

If this gate fails, revert the out-of-scope changes rather than justifying them.

- [ ] **Step 4: Verify Parenthood stays canonical**

Run:

```bash
git grep -q 'domain:parenthood' -- ROADMAP.md docs/roadmap docs/reference

if git grep -n -I -E \
  'domain:nil|nil\.' \
  -- ROADMAP.md docs/roadmap docs/reference
then
  echo "ERROR: active legacy Nil architecture detected"
  exit 1
fi

echo "PARENTHOOD_CANON=PASS"
```

Historical audit quotations may be exempt only if clearly historical and not an active contract. If an exemption is necessary, document it in the final report rather than altering audit evidence.

- [ ] **Step 5: Verify no premature implementation/closure claim**

Run:

```bash
python3 - <<'PY'
from pathlib import Path

matrix = Path("docs/reference/domain-intelligence-requirements-matrix.md").read_text(encoding="utf-8")
phase10 = Path("docs/roadmap/phase-10-domain-intelligence.md").read_text(encoding="utf-8")

for dp in ("DP-052", "DP-053"):
    rows = [x for x in matrix.splitlines() if x.startswith(f"| `{dp}` |")]
    assert len(rows) == 1
    row = rows[0]
    assert "REQUIRES_PHASE_INSPECTION" in row
    assert "VERIFIED_EXISTING" not in row

for forbidden in (
    "Phase 10.52 — Complete",
    "Phase 10.53 — Complete",
    "DP-052=VERIFIED_EXISTING",
    "DP-053=VERIFIED_EXISTING",
    "AT-DP-052 — PASS",
    "AT-DP-053 — PASS",
):
    assert forbidden not in phase10

print("NO_PREMATURE_CLOSURE=PASS")
PY
```

- [ ] **Step 6: Documentation hygiene**

```bash
git diff --check "$BASE_HEAD..HEAD"
git status --short --branch
```

Tracked tree should be clean after commits.

- [ ] **Step 7: Run existing tests**

Because production code is unchanged, run the live suite once as a regression guard:

```bash
.venv/bin/python -m pytest -q
```

Record fresh result. Do not modify production code to chase unrelated pre-existing failures; if a failure is unrelated to the documentation commits, report it with evidence.

- [ ] **Step 8: Final report**

Report exactly this structure with fresh values:

```text
ROADMAP_DOMAIN_EXPANSION=COMPLETE|INCOMPLETE
BASE_HEAD=<sha>
HEAD=<sha>

PHASE_0_9_IMPLEMENTATION_CHANGED=NO
HEALTH_10_20_REOPENED=NO
PHASE10_RENUMBERED=NO

PHASE10_52=PLANNED
DOMAIN_10_52=domain:mental-health
PROFILE_10_52=MentalHealthProfile
DP_052=REQUIRES_PHASE_INSPECTION
AT_DP_052=PLANNED

PHASE10_53=PLANNED
DOMAIN_10_53=domain:neurodivergence
PROFILE_10_53=NeurodivergenceProfile
DP_053=REQUIRES_PHASE_INSPECTION
AT_DP_053=PLANNED

PARENTHOOD_CANON=PASS
PHASE11_CANONICAL_HEALTH_ID=PASS
CROSS_DOCUMENT_CONSISTENCY=PASS
GLOBAL_TESTS=<fresh result>
GIT_DIFF_CHECK=PASS
WORKTREE=<clean or exact pre-existing untracked state>

PUSH=NO
MERGE=NO
NEXT=RESUME_CURRENT_PHASE_10_WORK
```

---

# Plan Self-Review

## Spec coverage

| Approved design requirement | Task(s) |
|---|---|
| Append 10.52 / 10.53 without renumbering | 3, 6 |
| Mental Health independent sibling domain | 2, 3, 4, 5 |
| Neurodivergence independent sibling domain | 2, 3, 4, 5 |
| Health remains medical/clinical authority | 2, 3, 4 |
| No Phase 0–9 reopening | 1, 6 |
| Reuse Phase 8 Cognitive Layer | 3, 6 |
| Reuse Phase 9 Agent Runtime | 3, 6 |
| SENSITIVE privacy | 2, 3, 5 |
| Cross-domain minimum projections | 2, 3, 5 |
| No silent migration/reclassification | 3 |
| Update Phase 10 catalogs/closure criteria | 3 |
| DP-052 / AT-DP-052 | 2, 3, 6 |
| DP-053 / AT-DP-053 | 2, 3, 6 |
| Update public ROADMAP | 4 |
| Parenthood canonical | 2, 3, 4, 6 |
| Phase 11 generic integration | 5 |
| `medical` -> canonical `health` IDs | 5, 6 |
| Preserve live Phase 10 progress | 1, 4, 6 |
| No premature implementation/audit claim | 2, 3, 6 |

## Placeholder scan

No `TBD`, `TODO`, or deferred implementation placeholders are permitted in the modified roadmap/specification content. The two Domain Packs are intentionally **planned**, but their planning sections must contain concrete requirements rather than empty stubs.

## Scope lock

This plan modifies documentation/specification only. It does **not** implement `cmm/domains/mental_health/` or `cmm/domains/neurodivergence/`, create their test suites, build audit bundles, or independently audit either domain.

After this plan is complete, resume the currently active Phase 10 work. Implement 10.52 and 10.53 only when the established Phase 10 sequence reaches them.
