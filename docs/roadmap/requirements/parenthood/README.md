# Paternidad — Fuentes funcionales de requisitos

## Canonical domain

```text
domain:parenthood
```

Public name:

```text
Paternidad
```

## Functional requirement sources

### Camino a la Paternidad

Repository target:

```text
docs/roadmap/requirements/parenthood/camino-a-la-paternidad.md
```

Scope:

```text
parenthood.journey
```

Purpose:

- define the expected behavior of the assistant during the process of becoming a parent;
- cover legal, medical, financial, logistical, ethical and planning needs;
- preserve critical decisions and current project constraints;
- require current verification for changing external information;
- keep external actions supervised.

### Paternidad por hijo

Repository target:

```text
docs/roadmap/requirements/parenthood/paternidad.md
```

Scope:

```text
parenthood.child:<child_id>
```

Purpose:

- define the expected behavior of the assistant in the exercise of parenting;
- organize each child independently;
- adapt reasoning to developmental stage;
- support health, education, autonomy, relationships, routines and family organization;
- preserve the child's dignity, autonomy, privacy and individual history.

## Architectural rule

These prompts are **functional requirement sources**, not executable policy and not independent Domain Packs.

They may inform:

- resources;
- rules;
- operations;
- workflows;
- questions;
- presentation expectations;
- acceptance tests.

They may not override:

- Kernel contracts;
- Cognitive Layer epistemic rules;
- Agent Runtime policies;
- validation;
- permissions;
- privacy;
- approval requirements;
- cross-domain restrictions;
- memory policy.

## Naming rule

Public structure:

```text
Paternidad
├── Camino a la Paternidad
└── <nombre visible de cada hijo>
```

Canonical structure:

```text
domain:parenthood
├── parenthood.journey
└── parenthood.child:<child_id>
```

Personal names are presentation data only.

The legacy personal project identifier and the legacy route-specific abbreviation must not be used as public or architectural identifiers.

The full descriptive term for a reproductive route may still appear inside private functional requirements where it is semantically necessary.

## Traceability

Implementation of Phase 10.27 should be traceable from requirements to:

```text
Prompt requirement
↓
Domain rule / operation / workflow
↓
Test or acceptance scenario
```

Material behavior added from these prompt sources should have at least one corresponding test or explicit acceptance criterion.
