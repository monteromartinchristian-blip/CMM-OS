# CMM OS Repository Instructions

## Scope and Identity

- This repository contains CMM OS, the product and system under development.
- CMM Code is the separate development and programming system. Reuse its Global Engineering Profile, including the global Engineer, Architect, Debugger, Auditor, Researcher, Global Engineering instructions, and safety policy, rather than cloning them in this repository.
- Do not confuse repository customization agents with CMM OS product/runtime agents under `cmm_agent/` or `cmm/agent_runtime/`.
- Before an architectural change, inspect the relevant implementation, tests, roadmap, specifications, and existing plans.
- Respect existing subsystem boundaries and abstractions. Do not introduce a parallel mechanism when the repository already has one that owns the responsibility.

## Development Discipline

- Keep changes focused on the requested scope and preserve unrelated work.
- Fix the root cause before changing symptoms or surrounding documentation.
- Preserve public contracts and compatibility unless a contract change has been explicitly designed.
- Avoid unrelated refactors and architecture debt.

## TDD and Verification

- Functional behavior changes use a real RED, minimal implementation, GREEN, and proportional regression.
- A missing dependency, import failure, syntax error, collection failure, or configuration error does not count as a behavioral RED.
- Completion claims require current verification evidence.
- Phase and remediation work must run the focused suites that prove the changed contract plus broader regression proportional to impact.

## Specifications, Plans, and Phases

- Material architecture or scope changes follow design/spec -> review -> implementation plan -> implementation -> verification.
- `docs/superpowers/specs/` and `docs/superpowers/plans/` are design history, not runtime policy.
- Roadmap status must reflect verified implementation state.
- Implementation existence alone does not close a phase; required gates, regression evidence, documentation, and audit requirements must also pass.

## Independent Audit

- An independent audit reconstructs requirements from authoritative repository evidence before judging implementation.
- Findings must be reproducible, classified, and separated from inference.
- Remediation addresses the root cause of each finding.
- Do not approve by intent or rewrite historical audit evidence to make a past result appear green.
- Preserve useful closure suites as permanent regression coverage.

## Git and Human Control

- Keep commits coherent and scoped.
- In controlled workflows, never use `git add .` or `git add -A`; stage explicit paths only.
- Preserve unrelated dirty work.
- Push, merge, tag, release, credentials, permission changes, and irreversible external actions remain human-controlled.
- Never commit secrets.