# Phase 9.29 — Model Requirements per Operation

## Scope

Phase 9.29 allows model-assisted Agent Runtime operations to declare hard
execution requirements without selecting a concrete model or provider.

It reuses the canonical `kernel.llm.model_selection.ModelRequirements`
contract and does not introduce a parallel model registry, router, gateway,
provider abstraction, privacy model, or cost model.

## Runtime declaration points

Model requirements may be declared at the following runtime layers:

- `AgentDescriptor`;
- `Goal`;
- `AgentWorkflowPlan`;
- `AgentWorkflowOperation`;
- `OperationDescriptor`;
- explicit policy restrictions;
- explicit human-approval parameters.

Every field is optional. Existing runtime contracts and serialized payloads
remain backward compatible when no requirements are declared.

## Effective resolution

`resolve_runtime_model_requirements()` collects the declared requirements and
produces one `ResolvedModelRequirements`.

Sources are ordered deterministically:

| Source | Priority |
| --- | ---: |
| Agent | 10 |
| Goal | 20 |
| Workflow | 30 |
| Operation | 40 |
| Policy | 50 |
| Approval | 60 |

Priority preserves provenance and deterministic ordering. It does not allow a
later source to weaken an earlier hard constraint.

Effective requirements use restrictive merging:

- required capability flags are combined with logical OR;
- minimum context window uses the highest declared minimum;
- maximum input cost uses the lowest declared ceiling;
- allowed providers use intersection;
- excluded providers use union;
- privacy uses the strictest declared policy;
- premium use remains allowed only when every source allows it.

Provider intersections that become empty fail with a structured
`ModelRequirementsConflictError`.

## Policy integration

Policy constraints are translated only when a `PolicyRestriction` explicitly
uses `kind = "model_requirements"`.

The restriction `parameters` mapping must contain a serialized
`ModelRequirements` payload.

Descriptions, reasons, advice, obligations, and other free text are never
parsed or inferred as model requirements.

## Approval integration

Approval constraints are translated only from
`approved_parameters["model_requirements"]`.

The approval must be satisfied and executable. Requirements attached to a
rejected or non-executable resolution fail closed with
`ModelRequirementsResolutionError`.

Approval conditions and comments are not interpreted as model requirements.

## Public API

Phase 9.29 exposes:

- `ModelRequirementsSource`;
- `ResolvedModelRequirements`;
- `model_requirements_to_dict`;
- `model_requirements_from_dict`;
- `resolve_model_requirements`;
- `resolve_runtime_model_requirements`;
- `policy_model_requirement_sources`;
- `approval_model_requirement_sources`;
- structured requirement contract, conflict, and resolution errors.

## Architectural boundaries

Phase 9.29 does not:

- select a model;
- call a provider;
- bypass the future Model Gateway;
- authorize premium execution by itself;
- weaken inherited privacy restrictions;
- ignore cost ceilings;
- infer model capabilities;
- implement fallback or escalation behavior.

Concrete model routing remains a later Phase 11 responsibility. Workflow
fallback and escalation policies belong to Phase 9.30.

## Validation

The implementation was validated with:

- 5,326 repository tests passing;
- focused Ruff checks passing;
- Python compilation passing for `cmm` and `kernel`;
- `git diff --check` passing.
