# Custom Validations Architecture in CMM OS

Phase 7.9 introduces custom validations into the CMM OS continuous validation engine. Custom validators extend built-in structural, impact, static, security, and testing validations with project-specific rules while maintaining strict contract isolation, determinism, and serializability.

---

## 1. Core Architecture Components

- **`CustomValidator` Interface**: Any Python class providing a `.name` string attribute and a `.validate(context: ValidationContext) -> ValidationStepResult` method.
- **`CustomValidatorRegistry`**: An in-memory, isolated registry mapping logical validator names to `CustomValidator` instances.
- **`CustomValidatorAdapter`**: Adapts a `CustomValidator` instance to an `INTERNAL` `ValidationStep` execution handler registered within `ValidationRegistry`.
- **`ValidationPlan`**: An immutable plan representing the resolved set of built-in and custom `ValidationStep`s alongside their registered `ValidationRegistry` step handlers and resolved `ValidationPolicy`.

---

## 2. Default Custom Validator Catalog

CMM OS provides four pre-packaged custom validators accessible via `default_custom_validators()` and `build_default_custom_validator_registry()`:

| Logical Name | Canonical Step Name | Description |
| :--- | :--- | :--- |
| `project_manifest` | `custom.project_manifest` | Validates `pyproject.toml` layout, mandatory metadata, and dependencies. |
| `validation_contract` | `custom.validation_contract` | Verifies validation module integrity and strict contract adherence. |
| `public_api` | `custom.public_api` | Enforces public export contracts and `__all__` consistency in `cmm/`. |
| `test_layout` | `custom.test_layout` | Verifies test directory mirror structures and naming conventions. |

The aggregate alias **`custom_checks`** expands to all four default canonical custom step names in order: `custom.project_manifest`, `custom.validation_contract`, `custom.public_api`, `custom.test_layout`.

---

## 3. Validation Policies & Step Selection

Custom validators are integrated directly into `DEFAULT_VALIDATION_POLICIES` using canonical step names:

- **`small_change`**, **`imports_change`**:
  - `optional_steps`: `custom_checks`
- **`structural_change`**, **`kernel_change`**, **`release`**, **`full`**, **`autonomous_execution`**:
  - `required_steps`: `custom_checks`
- **`public_api_change`**:
  - `required_steps`: `custom.project_manifest`, `custom.validation_contract`, `custom.public_api`
  - `optional_steps`: `custom.test_layout`

---

## 4. Usage Example

```python
from pathlib import Path
from cmm.validation import (
    ValidationContext,
    build_default_validation_plan,
    ValidationPipeline,
)

# Initialize context
context = ValidationContext(
    project_root=Path("/path/to/project"),
    requested_policy="small_change",
)

# Build plan (links steps, custom handlers, and policy)
plan = build_default_validation_plan(context)

# Run pipeline using plan steps and plan registry
pipeline = ValidationPipeline()
result = pipeline.execute(
    context,
    steps=plan.steps,
    registry=plan.registry,
)

print(f"Status: {result.status.value}, Can Commit: {result.can_commit}")
```

---

## 5. Explicit Step Selection & Exclusion

- **Explicit Selection**: Specify `context.requested_steps` using canonical step names (e.g. `requested_steps=("custom.project_manifest", "lint")`). Unprefixed custom names (e.g. `"project_manifest"`) are rejected to avoid ambiguity.
- **Explicit Exclusion**: Specify `context.excluded_steps` (e.g. `excluded_steps=("custom.test_layout",)`). Excluding an optional step successfully removes it from the plan; attempting to exclude a policy-required step raises a `ValidationContractError`.

---

## 6. Architectural Boundaries

- **No Global Registry**: Custom validators and step handlers are instantiated per plan/execution without global mutable state.
- **No Automatic File Discovery**: Validators must be explicitly registered via `CustomValidatorRegistry`.
- **No Remote Config / Plugins**: Configuration is fully expressed through Python contracts (`ValidationContext` and `ValidationPolicy`).

---

## 7. Pipeline Execution Semantics (Required, Optional & ERROR)

`ValidationPipeline` maintains its strict historical execution contract:
- Any `ValidationStatus.ERROR` represents an internal execution failure and halts pipeline execution.
- Optional step status (`required=False`) applies non-blocking status transitions only to `FAILED`, `TIMED_OUT`, and `CANCELLED` results; an internal `ERROR` is not automatically converted to a `WARNING`.
- Custom validators specify domain severity (`blocking=True/False`); the `ValidationPlan` defines step requirement (`required=True/False`), and `ValidationPipeline` enforces deterministic execution.
