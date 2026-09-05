# Scope of specs and implementation plans

The engineering policy is [AGENTS.md](../../AGENTS.md). Files in `specs/` and
`plans/` record requirements and procedures for particular tasks, not global
instructions for the assistant developing the repository.

Discovery is not adoption. A search hit, reference link, `Approved` status or
open checkbox does not authorize execution. The current task must explicitly
adopt a document for execution; inspect current code, task scope and Git state
before applying its steps. Old no-commit/commit rules, frozen HEADs, quarantine
stashes, bundle formats and audit handoffs belong to their original task.
Do not silently revive them for a new fix or waive a still-applicable audit gate.

For new or substantively revised documents, record the task/phase, intended
deliverable, status (`draft`, `approved`, `completed`, `superseded` or `unknown`),
and any superseding document or completion evidence. `Approved` describes a
decision, not implementation, host installation or permission for future tasks.
Never infer completion from a date or mechanically close historical checkboxes.
Existing unlabelled files remain reference material until explicitly adopted;
no bulk rewrite of historical evidence is needed.

An adopted plan may reference other documents for requirements. Those references
do not transitively activate their execution workflows. Preserve the original
task's independent audit boundary where it remains part of current acceptance.
