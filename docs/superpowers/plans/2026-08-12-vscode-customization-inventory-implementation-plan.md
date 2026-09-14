# VS Code Customization Inventory Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Produce a complete, read-only inventory and KEEP / MOVE / MERGE / RETIRE classification of the user's current VS Code/Copilot customizations before any migration or deletion occurs.

**Architecture:** Add one small repository utility that discovers workspace and user-level customization files without modifying them, serializes a normalized inventory, and renders a Markdown report. Run it against the real Mac environment, then inspect the discovered contents and create a reviewed classification report that becomes the input to later implementation plans.

**Tech Stack:** Python 3 via `.venv/bin/python`, stdlib only (`argparse`, `dataclasses`, `json`, `pathlib`), pytest, Git.

## Global Constraints

- No existing customization may be deleted, moved, renamed, or edited during this plan.
- Current working-tree changes related to Phase 10.22 must remain untouched.
- Git staging must use explicit paths; never use `git add .` or `git add -A`.
- User-level discovery must include `~/.copilot` and VS Code profile user data when present.
- Workspace discovery must include `.github`, `.vscode/mcp.json`, `.claude`, and `.agents` only where those paths actually exist.
- Prompt/profile paths must be discovered rather than assumed when VS Code stores them in profile-specific user data.
- Inventory output must never include secret values; MCP configuration is summarized structurally and credential-like values are redacted.
- The utility is read-only with respect to scanned customization locations.
- Every discovered item must record scope, kind, path, purpose evidence, and later disposition.
- Allowed dispositions are exactly `KEEP`, `MOVE`, `MERGE`, and `RETIRE`.
- No migration work begins until the classification report has been reviewed.

---

## File Structure

### Create

- `scripts/agent/inventory_vscode_customizations.py`
  - Read-only scanner and report renderer.
  - Owns path discovery, customization-kind classification, safe text metadata extraction, and MCP redaction.
- `tests/agent/test_inventory_vscode_customizations.py`
  - Unit tests for discovery, classification, redaction, workspace/user scope, and no-mutation behavior.
- `docs/development/vscode-customizations-inventory.json`
  - Machine-readable snapshot produced from the real environment.
- `docs/development/vscode-customizations-inventory.md`
  - Human-readable inventory with one row per discovered customization.
- `docs/development/vscode-customizations-classification.md`
  - Reviewed KEEP / MOVE / MERGE / RETIRE decision table.

### Do not modify in this plan

- Existing agent files.
- Existing skills.
- Existing instructions.
- Existing prompt files.
- Existing hook files.
- Existing MCP configuration.
- Existing plugins/extensions.
- Phase 10.22 remediation/test artifacts.
- The approved design spec.

---

### Task 1: Build the read-only customization inventory collector

**Files:**
- Create: `scripts/agent/inventory_vscode_customizations.py`
- Create: `tests/agent/test_inventory_vscode_customizations.py`

**Interfaces:**
- Consumes:
  - zero or more user roots;
  - one workspace root;
  - filesystem paths only.
- Produces:
  - `InventoryItem` records;
  - JSON serialization;
  - Markdown inventory rendering;
  - no mutations outside requested output files.

Required public interfaces:

```python
@dataclass(frozen=True)
class InventoryItem:
    scope: str
    kind: str
    name: str
    path: str
    source_root: str
    metadata: dict[str, object]

def discover_default_user_roots(home: Path) -> tuple[Path, ...]: ...

def scan_customizations(
    *,
    workspace_root: Path,
    user_roots: tuple[Path, ...],
) -> list[InventoryItem]: ...

def render_markdown(items: list[InventoryItem]) -> str: ...

def serialize_inventory(items: list[InventoryItem]) -> list[dict[str, object]]: ...
```

Supported normalized kinds:

```text
agent
skill
instruction
prompt
hook
mcp
plugin_candidate
```

Recognized file/layout signals:

```text
*.agent.md
*/SKILL.md
*.instructions.md
*.prompt.md
.github/hooks/*.json
~/.copilot/hooks/*.json
.vscode/mcp.json
profile-level mcp.json
~/.copilot/plugins/*
```

User-root discovery must consider existing paths under:

```text
~/.copilot
~/Library/Application Support/Code/User
~/Library/Application Support/Code - Insiders/User
```

It must also inspect profile subdirectories beneath VS Code `User/profiles/` when they exist.

Workspace discovery must inspect existing customization roots only:

```text
.github/agents
.github/skills
.github/instructions
.github/prompts
.github/hooks
.vscode/mcp.json
.claude/agents
.claude/skills
.claude/rules
.claude/settings.json
.claude/settings.local.json
.agents/skills
```

MCP metadata may include:

```text
server_names
server_count
has_inputs
config_keys
```

It must not include API keys, tokens, passwords, authorization headers, or raw environment-secret values.

- [ ] **Step 1: Create the test directory and write failing discovery tests**

Create `tests/agent/test_inventory_vscode_customizations.py` with tests that construct temporary user/workspace trees and assert:

```python
from __future__ import annotations

import json
from pathlib import Path

from scripts.agent.inventory_vscode_customizations import (
    discover_default_user_roots,
    render_markdown,
    scan_customizations,
    serialize_inventory,
)


def test_discovers_workspace_and_user_customizations(tmp_path: Path) -> None:
    home = tmp_path / "home"
    workspace = tmp_path / "repo"

    (home / ".copilot/agents").mkdir(parents=True)
    (home / ".copilot/skills/debugging").mkdir(parents=True)
    (home / ".copilot/instructions").mkdir(parents=True)
    (home / ".copilot/hooks").mkdir(parents=True)

    (home / ".copilot/agents/engineer.agent.md").write_text("# Engineer\n")
    (home / ".copilot/skills/debugging/SKILL.md").write_text("# Debugging\n")
    (home / ".copilot/instructions/global.instructions.md").write_text("# Global\n")
    (home / ".copilot/hooks/safety.json").write_text('{"hooks": {}}')

    (workspace / ".github/agents").mkdir(parents=True)
    (workspace / ".github/prompts").mkdir(parents=True)
    (workspace / ".vscode").mkdir(parents=True)

    (workspace / ".github/agents/cmm.agent.md").write_text("# CMM\n")
    (workspace / ".github/prompts/audit.prompt.md").write_text("# Audit\n")
    (workspace / ".vscode/mcp.json").write_text(
        json.dumps({"servers": {"github": {"type": "http", "url": "https://example.invalid"}}})
    )

    items = scan_customizations(
        workspace_root=workspace,
        user_roots=(home / ".copilot",),
    )

    assert {(item.scope, item.kind, item.name) for item in items} >= {
        ("user", "agent", "engineer"),
        ("user", "skill", "debugging"),
        ("user", "instruction", "global"),
        ("user", "hook", "safety"),
        ("workspace", "agent", "cmm"),
        ("workspace", "prompt", "audit"),
        ("workspace", "mcp", "mcp"),
    }


def test_inventory_is_deterministically_sorted(tmp_path: Path) -> None:
    workspace = tmp_path / "repo"
    (workspace / ".github/agents").mkdir(parents=True)
    (workspace / ".github/agents/z.agent.md").write_text("# Z\n")
    (workspace / ".github/agents/a.agent.md").write_text("# A\n")

    items = scan_customizations(workspace_root=workspace, user_roots=())

    keys = [(item.scope, item.kind, item.name, item.path) for item in items]
    assert keys == sorted(keys)


def test_mcp_secrets_are_not_serialized(tmp_path: Path) -> None:
    workspace = tmp_path / "repo"
    (workspace / ".vscode").mkdir(parents=True)
    (workspace / ".vscode/mcp.json").write_text(
        json.dumps(
            {
                "servers": {
                    "private": {
                        "type": "http",
                        "url": "https://example.invalid",
                        "headers": {"Authorization": "Bearer SUPER_SECRET"},
                        "env": {"API_KEY": "VERY_SECRET"},
                    }
                },
                "inputs": [{"id": "token", "type": "promptString", "password": True}],
            }
        )
    )

    items = scan_customizations(workspace_root=workspace, user_roots=())
    payload = json.dumps(serialize_inventory(items))

    assert "SUPER_SECRET" not in payload
    assert "VERY_SECRET" not in payload
    assert "private" in payload


def test_markdown_contains_scope_kind_name_and_path(tmp_path: Path) -> None:
    workspace = tmp_path / "repo"
    (workspace / ".github/agents").mkdir(parents=True)
    agent = workspace / ".github/agents/cmm-engineer.agent.md"
    agent.write_text("# Engineer\n")

    items = scan_customizations(workspace_root=workspace, user_roots=())
    rendered = render_markdown(items)

    assert "| workspace | agent | cmm-engineer |" in rendered
    assert ".github/agents/cmm-engineer.agent.md" in rendered


def test_default_user_roots_include_only_existing_supported_locations(tmp_path: Path) -> None:
    home = tmp_path / "home"
    (home / ".copilot").mkdir(parents=True)
    (home / "Library/Application Support/Code/User/profiles/profile-a").mkdir(parents=True)

    roots = discover_default_user_roots(home)

    assert home / ".copilot" in roots
    assert home / "Library/Application Support/Code/User" in roots
    assert home / "Library/Application Support/Code/User/profiles/profile-a" in roots
    assert all(path.exists() for path in roots)
```

- [ ] **Step 2: Run the new test module and verify the import fails**

Run:

```bash
cd "/Users/chris/CMM OS"
.venv/bin/python -m pytest -q tests/agent/test_inventory_vscode_customizations.py
```

Expected result:

```text
ERROR ... ModuleNotFoundError or ImportError for scripts.agent.inventory_vscode_customizations
```

- [ ] **Step 3: Implement the minimal scanner**

Create `scripts/agent/inventory_vscode_customizations.py`.

Implementation requirements:

```python
from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable


@dataclass(frozen=True)
class InventoryItem:
    scope: str
    kind: str
    name: str
    path: str
    source_root: str
    metadata: dict[str, object]
```

Use deterministic traversal via sorted paths.

Derive names as:

```text
foo.agent.md        -> foo
foo.instructions.md -> foo
foo.prompt.md       -> foo
.../skills/foo/SKILL.md -> foo
foo.json hook       -> foo
mcp.json            -> mcp
```

For `mcp.json`, parse JSON when valid and retain only structural metadata:

```python
{
    "server_names": sorted(server names),
    "server_count": number of servers,
    "has_inputs": bool(inputs),
    "config_keys": sorted(top-level keys),
}
```

Never copy server configuration values into `metadata`.

For malformed JSON, record:

```python
{"parse_error": True}
```

Do not fail the whole inventory.

`render_markdown()` must return:

```markdown
# VS Code Customization Inventory

Generated from a read-only scan.

| Scope | Kind | Name | Path | Metadata |
| --- | --- | --- | --- | --- |
...
```

`serialize_inventory()` must use `dataclasses.asdict()`.

CLI:

```bash
.venv/bin/python scripts/agent/inventory_vscode_customizations.py \
  --workspace "/Users/chris/CMM OS" \
  --json-output docs/development/vscode-customizations-inventory.json \
  --markdown-output docs/development/vscode-customizations-inventory.md
```

CLI behavior:

- resolve the workspace path;
- call `discover_default_user_roots(Path.home())`;
- create only the parent directories for the two requested output files;
- write outputs atomically through temporary sibling files followed by `replace`;
- print counts by scope/kind;
- exit nonzero only for invalid CLI/output/workspace errors, not malformed individual customization files.

- [ ] **Step 4: Run the tests**

Run:

```bash
.venv/bin/python -m pytest -q tests/agent/test_inventory_vscode_customizations.py
```

Expected:

```text
5 passed
```

- [ ] **Step 5: Add a no-mutation regression test**

Append a test that hashes or snapshots every scanned input file before `scan_customizations()`, runs the scan, and asserts every byte sequence is identical afterwards.

Test shape:

```python
def test_scan_never_mutates_scanned_files(tmp_path: Path) -> None:
    workspace = tmp_path / "repo"
    source = workspace / ".github/agents/test.agent.md"
    source.parent.mkdir(parents=True)
    source.write_bytes(b"original bytes\n")

    before = source.read_bytes()

    scan_customizations(workspace_root=workspace, user_roots=())

    assert source.read_bytes() == before
```

- [ ] **Step 6: Run the complete inventory test module**

Run:

```bash
.venv/bin/python -m pytest -q tests/agent/test_inventory_vscode_customizations.py
```

Expected:

```text
6 passed
```

- [ ] **Step 7: Commit only the collector and tests**

Run:

```bash
git add \
  scripts/agent/inventory_vscode_customizations.py \
  tests/agent/test_inventory_vscode_customizations.py

git diff --cached --check
git diff --cached --stat
git status --short

git commit -m "feat(dev): add VS Code customization inventory"
```

The commit must not include Phase 10.22 working-tree files.

---

### Task 2: Capture the real customization inventory

**Files:**
- Create: `docs/development/vscode-customizations-inventory.json`
- Create: `docs/development/vscode-customizations-inventory.md`

**Interfaces:**
- Consumes:
  - `scan_customizations(...)` from Task 1;
  - the actual user-level and workspace customization locations on the Mac.
- Produces:
  - immutable snapshot reports only;
  - no customization mutations.

- [ ] **Step 1: Inspect which supported roots actually exist**

Run:

```bash
cd "/Users/chris/CMM OS"

printf '%s\n' "=== USER ROOT CANDIDATES ==="

for path in \
  "$HOME/.copilot" \
  "$HOME/Library/Application Support/Code/User" \
  "$HOME/Library/Application Support/Code - Insiders/User"
do
  if [ -e "$path" ]; then
    echo "FOUND  $path"
  else
    echo "ABSENT $path"
  fi
done

printf '%s\n' "=== WORKSPACE ROOT CANDIDATES ==="

for path in \
  ".github/agents" \
  ".github/skills" \
  ".github/instructions" \
  ".github/prompts" \
  ".github/hooks" \
  ".vscode/mcp.json" \
  ".claude/agents" \
  ".claude/skills" \
  ".claude/rules" \
  ".claude/settings.json" \
  ".claude/settings.local.json" \
  ".agents/skills"
do
  if [ -e "$path" ]; then
    echo "FOUND  $path"
  fi
done
```

Expected: informational output only.

- [ ] **Step 2: Run the real inventory**

Run:

```bash
.venv/bin/python scripts/agent/inventory_vscode_customizations.py \
  --workspace "/Users/chris/CMM OS" \
  --json-output docs/development/vscode-customizations-inventory.json \
  --markdown-output docs/development/vscode-customizations-inventory.md
```

Expected:

- both report files created;
- counts printed;
- no source customization changed.

- [ ] **Step 3: Compare inventory counts with the VS Code UI baseline**

The approved design recorded this visible baseline:

```text
Agents        2
Skills       32
Instructions 2
Prompts       7
Hooks         4
MCP Servers   2
Plugins       1
```

Run:

```bash
cat docs/development/vscode-customizations-inventory.md
```

Then compare discovered counts.

A mismatch is not automatically a bug because:

- extension-contributed customizations may appear in the UI without a local user file;
- profile-scoped files may live in a VS Code profile-specific user-data location;
- plugin-contributed skills may be extension/plugin resources.

If a category is under-counted, do not modify anything. Locate the missing source first through VS Code's customization UI/source tooltip or profile storage and rerun the collector with that root.

- [ ] **Step 4: Check inventory outputs for accidental secrets**

Run:

```bash
rg -n -i \
  '(api[_-]?key|authorization|bearer[[:space:]]+[A-Za-z0-9._-]+|password|secret|token[=:][^"< ]+)' \
  docs/development/vscode-customizations-inventory.json \
  docs/development/vscode-customizations-inventory.md \
  || true
```

Review any matches manually.

Allowed matches include structural words such as `has_inputs` or the literal metadata key `password` only if no secret value appears.

- [ ] **Step 5: Commit the read-only inventory snapshot**

Run:

```bash
git add \
  docs/development/vscode-customizations-inventory.json \
  docs/development/vscode-customizations-inventory.md

git diff --cached --check
git diff --cached --stat
git status --short

git commit -m "docs(dev): inventory VS Code customizations"
```

Again, use explicit paths only.

---

### Task 3: Classify every discovered customization

**Files:**
- Create: `docs/development/vscode-customizations-classification.md`
- Read: `docs/development/vscode-customizations-inventory.json`
- Read: every discovered customization file that is locally readable
- Read: `docs/superpowers/specs/2026-08-12-vscode-agent-customization-design.md`

**Interfaces:**
- Consumes:
  - the real inventory snapshot;
  - the approved design rules.
- Produces:
  - one complete classification table;
  - no mutation of existing customizations.

Each row must contain:

```text
Kind
Name
Scope
Current path/source
Purpose
Trigger
Tool/permission profile
Overlap
Decision
Target
Reason
```

`Decision` must be one of:

```text
KEEP
MOVE
MERGE
RETIRE
```

Decision semantics:

```text
KEEP
  The customization has a clear unique responsibility and remains in its current conceptual role.

MOVE
  The content is useful but belongs to a different customization type or scope.

MERGE
  Its useful behavior overlaps another retained customization and should be consolidated there.

RETIRE
  It is obsolete, redundant, unused, or provides no distinct value after the new architecture.
```

- [ ] **Step 1: Create the classification document header and complete table**

Use this exact document structure:

```markdown
# VS Code Customization Classification

Date: 2026-08-12
Source inventory: `docs/development/vscode-customizations-inventory.json`
Design: `docs/superpowers/specs/2026-08-12-vscode-agent-customization-design.md`

## Decision Rules

- `KEEP`: unique responsibility, correct scope and customization type.
- `MOVE`: useful content, wrong scope or customization type.
- `MERGE`: useful but overlapping; consolidate into another retained item.
- `RETIRE`: redundant, obsolete, unused, or no longer justified.

## Classification

| Kind | Name | Scope | Current source | Purpose | Trigger | Tools / permissions | Overlap | Decision | Target | Reason |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
```

Add one row for every item in the inventory.

No row may have an empty `Decision`, `Target`, or `Reason`.

For `KEEP`, `Target` is the normalized retained path/role.

For `RETIRE`, `Target` is `—`.

- [ ] **Step 2: Apply the design's separation rules**

During review enforce:

```text
Permanent rule                -> Instruction
Reusable procedure            -> Skill
Manual high-level action      -> Prompt
Distinct role/tools/model     -> Agent
Deterministic invariant       -> Hook
External capability/data      -> MCP
```

Flag any current item that violates this model for MOVE or MERGE.

- [ ] **Step 3: Detect direct overlaps**

At minimum compare:

- every skill against other skills with similar descriptions/triggers;
- each prompt against any skill containing the same workflow;
- instructions against skill content that behaves like an always-on rule;
- agents with indistinguishable roles/tool access;
- hooks that merely remind rather than enforce;
- MCP servers that duplicate built-in/local capabilities without adding external access.

Record the overlap target explicitly.

- [ ] **Step 4: Reconcile the classification with the target architecture**

The report must identify whether the existing inventory already satisfies, partially satisfies, or lacks each target:

```text
Global Engineer
Global Architect
Global Debugger
Global Auditor
Global Researcher

CMM Engineer
CMM Architect
CMM Debugger
CMM Auditor
CMM Researcher

Global Engineering Instructions

CMM OS Engineering Instructions
CMM OS Safety & Git Policy
CMM OS Testing Policy

/implement
/audit
/close-milestone
/review-architecture
/diagnose
/phase-status
/release-check

safety hook
git-policy hook
commit-gate hook
agent-audit hook
```

Append:

```markdown
## Gaps Against Target Architecture

| Target | Existing coverage | Gap | Next plan |
| --- | --- | --- | --- |
...
```

`Next plan` should name only the implementation block that owns the gap:

```text
Instructions
Agents
Skills & Prompts
Hooks
MCP
```

- [ ] **Step 5: Self-review the classification**

Run:

```bash
rg -n '\|[[:space:]]*(TBD|TODO|UNKNOWN)[[:space:]]*\|' \
  docs/development/vscode-customizations-classification.md \
  && {
    echo "ERROR: unresolved classification entries remain"
    exit 1
  } || true
```

Then manually verify:

```text
inventory item count == classification row count
```

No migration is allowed if any discovered customization lacks a classification.

- [ ] **Step 6: Commit the classification only**

Run:

```bash
git add docs/development/vscode-customizations-classification.md

git diff --cached --check
git diff --cached --stat
git status --short

git commit -m "docs(dev): classify VS Code customizations"
```

---

## Plan Acceptance Gate

This plan is complete only when all of the following are true:

- the scanner tests are green;
- the real inventory is captured;
- no scanned source customization has been mutated;
- inventory outputs contain no exposed secrets;
- UI/discovered-count differences have been investigated;
- every discovered item has exactly one KEEP / MOVE / MERGE / RETIRE decision;
- gaps against the approved target architecture are explicit;
- Phase 10.22 working-tree files remain untouched;
- no existing customization has yet been migrated or deleted.

The resulting classification report becomes the sole input for the next implementation plan: **Instruction Foundation**.
