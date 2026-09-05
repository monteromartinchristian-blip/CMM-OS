# CMM OS engineering instructions

## Policy layers

The user's general development policy is maintained in the portable
`Desarrollo/agent-policy/AGENTS.md`; its installer exposes it through
`$CODEX_HOME/AGENTS.md` (default `~/.codex/AGENTS.md`). Codex loads that global layer separately from
this repository. Other hosts should read it if present and not already loaded,
then apply this file. Do not depend on inheritance from a parent `Desarrollo`
folder. On another user's machine, use their own host/user policy; do not install
or copy this owner's configuration. See [host setup and validation](docs/development/agent-instructions.md).

This file adds CMM-specific requirements. [CONTRIBUTING.md](CONTRIBUTING.md)
owns setup, commands and contribution conventions; [SECURITY.md](SECURITY.md)
owns applicable security obligations. CLAUDE.md and the Copilot entry point are
thin routes here. There are no additional subdirectory instruction policies.

## Product boundary and historical material

`cmm_agent` prompts, Kernel/planner rules and runtime documentation describe the
**CMM product**, not Codex/Claude/Copilot developing it. Preserve canonical
contracts and existing infrastructure; do not weaken product safeguards to
facilitate development. Invoking `ProvisionalCommitService` still requires its
`CommitAuthorization` and all service checks; these are not host Git permissions
or evidence that a developer hook is installed.

Files under `docs/superpowers/specs` and `plans` are task records, not global
policy. Follow [their scope convention](docs/superpowers/README.md). Reading a
historical phase plan does not revive its frozen HEAD, no-commit/commit rules,
quarantine stash, bundle or audit instructions. Explicit adoption requires
checking current phase, code and task acceptance; an approved design is not proof
of implementation or installed hooks. Requirements references do not activate
other plans' execution workflows. Do not relabel old phases without evidence.

## Project checks and delivery

Use Python 3.10+ and the declared setuptools/pip environment, preferably `.venv`.
Follow [project checks](CONTRIBUTING.md#running-tests): focused tests during code
changes, affected integration checks and full suite at code-change completion
and before PR submission, plus applicable static/security/phase gates. Pure local
documentation changes use relevant document/example/scenario checks, unless the
task explicitly requires more. Reuse valid evidence under the general policy;
never waive a required red gate or claim a wider validation scope than observed.

A CMM phase with required independent audit remains AUDIT_READY until that audit
passes; implementation self-review cannot certify it. A task solely preparing
an audit bundle may finish at its requested handoff. Exact-HEAD archives, hashes,
commits and stash preservation apply only when the current task requires them.
Do not infer those deliverables from a global model profile or historical example.
