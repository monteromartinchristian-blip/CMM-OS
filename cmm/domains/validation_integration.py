"""Phase 10.43 — Thin Domain validation integration helpers.

Reuses canonical Phase 7 ``ValidationResult`` truth and existing Domain
contracts. No executor, registry, pipeline, store, history, event bus,
commit gate, runtime, or result model is introduced here.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any

from cmm.validation.enums import ValidationStatus
from cmm.validation.results import ValidationResult

_SUCCESS_STEP_STATUSES = frozenset({ValidationStatus.PASSED, ValidationStatus.WARNING})
_SUCCESS_RESULT_STATUSES = frozenset(
    {ValidationStatus.PASSED, ValidationStatus.WARNING}
)
_FAIL_STEP_STATUSES = frozenset(
    {
        ValidationStatus.FAILED,
        ValidationStatus.ERROR,
        ValidationStatus.TIMED_OUT,
        ValidationStatus.CANCELLED,
    }
)

_IGNORED_CALLER_METADATA_KEYS = frozenset(
    {
        "skip_validation",
        "validation_passed",
        "required_validation_ids",
        "trust",
        "approval",
    }
)


class DomainValidationIntegrationError(Exception):
    """Fail-closed error owned by the thin Phase 10.43 binding layer."""

    def __init__(self, message: str, *, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.details: dict[str, Any] = dict(details or {})


def _clean_required_ids(required: tuple[str, ...] | list[str]) -> tuple[str, ...]:
    if required is None:  # type: ignore[unreachable]
        raise DomainValidationIntegrationError(
            "required_validation_ids must not be None",
            details={"reason": "missing_required_ids"},
        )
    if isinstance(required, (str, bytes)):
        raise DomainValidationIntegrationError(
            "required_validation_ids must be a tuple of strings",
            details={"reason": "malformed_required_ids"},
        )
    try:
        items = tuple(required)
    except TypeError as exc:
        raise DomainValidationIntegrationError(
            "required_validation_ids must be iterable",
            details={"reason": "malformed_required_ids"},
        ) from exc
    for item in items:
        if not isinstance(item, str) or not item:
            raise DomainValidationIntegrationError(
                "required validation ids must be non-empty strings",
                details={"reason": "malformed_required_id", "value": str(item)},
            )
    # Deterministic dedup for lookup; order preserved via sorted for evidence return.
    return tuple(sorted(set(items)))


def require_canonical_validation_success(
    *,
    required_validation_ids: tuple[str, ...],
    canonical_results: tuple[ValidationResult, ...],
) -> tuple[str, ...]:
    """Require canonical Phase 7 evidence for every required validation ID.

    Returns deterministic canonical result IDs that supplied the evidence.
    Never synthesizes a passing result. Fails closed on missing, unknown,
    malformed, unavailable, failed, errored, timed-out, or cancelled evidence.
    """
    required = _clean_required_ids(required_validation_ids)
    if not required:
        return ()
    if canonical_results is None or not isinstance(canonical_results, (tuple, list)):
        raise DomainValidationIntegrationError(
            "canonical_results must be a tuple of ValidationResult",
            details={"reason": "missing_evidence"},
        )
    results = tuple(canonical_results)
    if not results:
        raise DomainValidationIntegrationError(
            "missing mandatory validation evidence",
            details={"reason": "missing_evidence", "required": list(required)},
        )
    for res in results:
        if not isinstance(res, ValidationResult):
            raise DomainValidationIntegrationError(
                "malformed canonical validation result",
                details={"reason": "malformed_result", "type": type(res).__name__},
            )
        if not res.id:
            raise DomainValidationIntegrationError(
                "malformed canonical validation result without id",
                details={"reason": "malformed_result"},
            )

    # Index steps by name across all canonical results.
    steps_by_name: dict[str, list[tuple[ValidationResult, Any]]] = {}
    for res in results:
        for step in res.steps:
            steps_by_name.setdefault(step.name, []).append((res, step))

    evidence_ids: set[str] = set()
    for req_id in required:
        entries = steps_by_name.get(req_id, [])
        if not entries:
            # Also accept aggregate-level evidence: a canonical result whose
            # policy name matches the required ID and itself succeeded.
            aggregate = [
                res
                for res in results
                if res.policy == req_id and res.status in _SUCCESS_RESULT_STATUSES
            ]
            if aggregate and not any(res.has_blockers for res in aggregate):
                for res in aggregate:
                    evidence_ids.add(res.id)
                continue
            raise DomainValidationIntegrationError(
                f"missing mandatory validation evidence for '{req_id}'",
                details={"reason": "missing_evidence", "required_id": req_id},
            )
        # Fail closed if any matching step is blocking/failed.
        passing: list[ValidationResult] = []
        for res, step in entries:
            if getattr(step, "blocking", False):
                pass
            # Blocking findings on the step fail the requirement.
            if any(getattr(f, "blocking", False) for f in step.findings):
                raise DomainValidationIntegrationError(
                    f"validation '{req_id}' has blocking findings",
                    details={"reason": "blocking_finding", "required_id": req_id},
                )
            if step.status in _FAIL_STEP_STATUSES:
                raise DomainValidationIntegrationError(
                    f"required validation '{req_id}' did not succeed",
                    details={
                        "reason": "validation_unsuccessful",
                        "required_id": req_id,
                        "step_status": step.status.value,
                    },
                )
            if step.status not in _SUCCESS_STEP_STATUSES:
                raise DomainValidationIntegrationError(
                    f"required validation '{req_id}' has no successful evidence",
                    details={
                        "reason": "validation_unsuccessful",
                        "required_id": req_id,
                        "step_status": step.status.value,
                    },
                )
            # Overall canonical result must itself be successful and blocker-free
            # for the evidence to count (no success after required failure).
            if res.status not in _SUCCESS_RESULT_STATUSES or res.has_blockers:
                raise DomainValidationIntegrationError(
                    f"required validation '{req_id}' canonical result unsuccessful",
                    details={
                        "reason": "validation_unsuccessful",
                        "required_id": req_id,
                        "result_status": res.status.value,
                    },
                )
            passing.append(res)
        if not passing:
            raise DomainValidationIntegrationError(
                f"missing mandatory validation evidence for '{req_id}'",
                details={"reason": "missing_evidence", "required_id": req_id},
            )
        for res in passing:
            evidence_ids.add(res.id)
    return tuple(sorted(evidence_ids))


def _extract_field(result: object, names: tuple[str, ...]) -> Any:
    if isinstance(result, Mapping):
        for name in names:
            if name in result:
                return result[name]
        return None
    for name in names:
        if hasattr(result, name):
            return getattr(result, name)
    return None


def _is_json_safe(value: Any) -> bool:
    try:
        json.dumps(value)
        return True
    except (TypeError, ValueError):
        return False


def _ensure_json_safe_mapping(payload: Mapping[str, Any]) -> None:
    try:
        encoded = json.dumps(payload, sort_keys=True)
    except (TypeError, ValueError) as exc:
        raise DomainValidationIntegrationError(
            "specialized result is not JSON-safe serializable",
            details={"reason": "serialization_invalid", "error": str(exc)},
        ) from exc
    try:
        decoded = json.loads(encoded)
    except ValueError as exc:
        raise DomainValidationIntegrationError(
            "specialized result round-trip failed",
            details={"reason": "serialization_invalid"},
        ) from exc
    if not isinstance(decoded, dict):
        raise DomainValidationIntegrationError(
            "specialized result round-trip contract violated",
            details={"reason": "serialization_invalid"},
        )


def validate_domain_specialized_result(
    *,
    result: object,
    expected_domain_id: str,
    expected_operation_id: str | None = None,
    expected_workflow_id: str | None = None,
    required_validation_ids: tuple[str, ...] = (),
    canonical_validation_results: tuple[ValidationResult, ...] = (),
) -> tuple[str, ...]:
    """Validate structural invariants of a specialized Domain result.

    Checks identity coherence, JSON-safe serialization, approval/validation
    reference preservation, and canonical validation evidence. Never rewrites
    factual content, raises confidence, or infers missing facts.
    Returns canonical validation result references.
    """
    if not isinstance(expected_domain_id, str) or not expected_domain_id:
        raise DomainValidationIntegrationError(
            "expected_domain_id must be a non-empty string",
            details={"reason": "malformed_expected_identity"},
        )
    # Structural identity coherence.
    domain_value = _extract_field(result, ("domain_id", "primary_domain", "domainId"))
    if domain_value is not None:
        domain_str = str(domain_value)
        # Support DomainId-like objects with slug attribute.
        slug = getattr(domain_value, "slug", None)
        if isinstance(slug, str) and slug:
            # Canonical DomainId slug omits the "domain:" prefix.
            candidates = {domain_str, f"domain:{slug}", slug}
        else:
            candidates = {domain_str}
        if expected_domain_id not in candidates and domain_str != expected_domain_id:
            raise DomainValidationIntegrationError(
                "specialized result domain identity mismatch",
                details={
                    "reason": "identity_mismatch",
                    "expected": expected_domain_id,
                    "actual": domain_str,
                },
            )
    elif expected_domain_id:
        # A mapping result without any domain identity cannot be accepted as
        # a coherent specialized outcome when an expectation exists.
        if isinstance(result, Mapping):
            raise DomainValidationIntegrationError(
                "specialized result missing domain identity",
                details={"reason": "identity_mismatch"},
            )

    if expected_operation_id is not None:
        op_value = _extract_field(
            result, ("operation_id", "operationId", "operation_name")
        )
        if op_value is not None and str(op_value) != expected_operation_id:
            raise DomainValidationIntegrationError(
                "specialized result operation identity mismatch",
                details={
                    "reason": "identity_mismatch",
                    "expected": expected_operation_id,
                    "actual": str(op_value),
                },
            )
        if op_value is None and isinstance(result, Mapping):
            raise DomainValidationIntegrationError(
                "specialized result missing operation identity",
                details={"reason": "identity_mismatch"},
            )

    if expected_workflow_id is not None:
        wf_value = _extract_field(
            result, ("workflow_id", "workflowId", "workflow_name")
        )
        if wf_value is not None and str(wf_value) != expected_workflow_id:
            raise DomainValidationIntegrationError(
                "specialized result workflow identity mismatch",
                details={
                    "reason": "identity_mismatch",
                    "expected": expected_workflow_id,
                    "actual": str(wf_value),
                },
            )
        if wf_value is None and isinstance(result, Mapping):
            raise DomainValidationIntegrationError(
                "specialized result missing workflow identity",
                details={"reason": "identity_mismatch"},
            )

    # JSON-safe serialization where the contract supports it.
    if isinstance(result, Mapping):
        _ensure_json_safe_mapping(result)
    elif hasattr(result, "to_dict") and callable(result.to_dict):
        try:
            payload = result.to_dict()
        except Exception as exc:
            raise DomainValidationIntegrationError(
                "specialized result serialization failed",
                details={"reason": "serialization_invalid"},
            ) from exc
        if not isinstance(payload, Mapping):
            raise DomainValidationIntegrationError(
                "specialized result to_dict must return a mapping",
                details={"reason": "serialization_invalid"},
            )
        _ensure_json_safe_mapping(payload)
        # Round-trip contract where supported.
        from_dict = getattr(result, "from_dict", None)
        if callable(from_dict):
            try:
                rebuilt = from_dict(dict(payload))
            except Exception as exc:
                raise DomainValidationIntegrationError(
                    "specialized result round-trip failed",
                    details={"reason": "serialization_invalid"},
                ) from exc
            try:
                if rebuilt.to_dict() != dict(payload):
                    raise DomainValidationIntegrationError(
                        "specialized result round-trip contract violated",
                        details={"reason": "serialization_invalid"},
                    )
            except DomainValidationIntegrationError:
                raise
            except Exception as exc:
                raise DomainValidationIntegrationError(
                    "specialized result round-trip failed",
                    details={"reason": "serialization_invalid"},
                ) from exc
    else:
        # Non-mapping, non-contract results must still be JSON-safe when they
        # claim to be structured outcomes (dict-like). Scalars accepted as-is.
        if not _is_json_safe(result) and isinstance(result, (dict, list)):
            raise DomainValidationIntegrationError(
                "specialized result is not JSON-safe serializable",
                details={"reason": "serialization_invalid"},
            )

    # Confidence/status coherence where constrained: malformed confidence rejected.
    confidence = _extract_field(result, ("confidence",))
    if confidence is not None:
        try:
            conf_value = float(confidence)  # type: ignore[arg-type]
        except (TypeError, ValueError) as exc:
            raise DomainValidationIntegrationError(
                "specialized result has malformed confidence",
                details={"reason": "malformed_confidence"},
            ) from exc
        if not (0.0 <= conf_value <= 1.0):
            raise DomainValidationIntegrationError(
                "specialized result has malformed confidence",
                details={"reason": "malformed_confidence", "value": str(confidence)},
            )

    # Required canonical validation evidence (no success after failure).
    required = _clean_required_ids(tuple(required_validation_ids or ()))
    if required:
        references = require_canonical_validation_success(
            required_validation_ids=required,
            canonical_results=tuple(canonical_validation_results or ()),
        )
        # Status/result consistency: a result claiming success without
        # successful required validation is impossible (already proven above,
        # but an explicit success claim with empty references is rejected).
        status_value = _extract_field(result, ("status",))
        if (
            status_value is not None
            and str(status_value).lower()
            in (
                "success",
                "passed",
                "ok",
                "completed",
            )
            and not references
        ):
            raise DomainValidationIntegrationError(
                "specialized result claims success without validation evidence",
                details={"reason": "missing_evidence"},
            )
        # Validation references preserved where the contract carries them.
        for field_name in ("validation_result_ids", "validation_ids"):
            carried = _extract_field(result, (field_name,))
            if carried is not None:
                try:
                    carried_set = {str(item) for item in tuple(carried)}
                except TypeError as exc:
                    raise DomainValidationIntegrationError(
                        "specialized result has malformed validation references",
                        details={"reason": "malformed_validation_references"},
                    ) from exc
                # References must preserve canonical evidence: every
                # canonical reference must be present in the carried set.
                if not set(references) <= carried_set:
                    raise DomainValidationIntegrationError(
                        "specialized result dropped validation references",
                        details={
                            "reason": "validation_references_dropped",
                        },
                    )
        return references

    # No required validation: still enforce no impossible success claim tied
    # to explicit failure markers in the payload.
    status_value = _extract_field(result, ("status",))
    validation_failed = _extract_field(
        result, ("validation_failed", "validationFailed")
    )
    if (
        validation_failed is True
        and status_value is not None
        and str(status_value).lower() in ("success", "passed", "ok", "completed")
    ):
        raise DomainValidationIntegrationError(
            "specialized result claims success after validation failure",
            details={"reason": "status_result_inconsistent"},
        )
    return ()


def compose_effective_validation_ids(
    *,
    global_required: tuple[str, ...] = (),
    primary_required: tuple[str, ...] = (),
    supporting_required: tuple[str, ...] = (),
    operation_required: tuple[str, ...] = (),
    workflow_required: tuple[str, ...] = (),
    dependency_required: tuple[str, ...] = (),
    project_required: tuple[str, ...] = (),
) -> tuple[str, ...]:
    """Deterministic monotonic union for cross-domain execution.

    Thin helper over the canonical ``compose_required_validation_ids`` so
    cross-domain call sites share one restrictive composition rule. Caller
    metadata is never consulted here; hosts must only pass host-derived
    requirement sets.
    """
    from cmm.domains.validation_policy_bindings import (
        compose_required_validation_ids,
    )

    return compose_required_validation_ids(
        tuple(global_required or ()),
        tuple(primary_required or ()),
        tuple(supporting_required or ()),
        tuple(operation_required or ()),
        tuple(workflow_required or ()),
        tuple(dependency_required or ()),
        tuple(project_required or ()),
    )


def is_ignored_caller_validation_metadata(key: str) -> bool:
    """Whether a caller-supplied metadata key can never downgrade validation."""
    return str(key) in _IGNORED_CALLER_METADATA_KEYS


def domain_operation_requires_validation(
    definition_or_policy_id: object,
) -> bool:
    """Whether a Domain operation mandates canonical validation.

    Accepts a ``DomainOperationDefinition`` (reads ``validation_policy_id``)
    or a raw policy-id string. Empty/None means no mandated validation.
    """
    policy_id: object = None
    if isinstance(definition_or_policy_id, str):
        policy_id = definition_or_policy_id
    else:
        try:
            policy_id = definition_or_policy_id.validation_policy_id  # type: ignore[attr-defined]
        except AttributeError:
            policy_id = None
    if policy_id is None:
        return False
    return bool(str(policy_id).strip())


def build_operation_validation_requirements(
    *,
    validation_policy_id: str | None = None,
    required_validation_ids: tuple[str, ...] = (),
    stage: str = "pre_execution",
    operation_name: str = "",
    operation_version: str = "1",
    resource_scope: tuple[str, ...] = (),
) -> tuple[Any, ...]:
    """Build Phase 9 ``ValidationRequirement`` objects for a Domain operation.

    Thin binding: preserves every host-derived required ID as a required,
    blocking requirement so unknown mandatory IDs fail closed in the
    canonical adapter (which raises for unknown required validators).
    Known Phase 7 validator IDs execute canonically; the operation's own
    ``validation_policy_id`` is carried as requirement policy identity.
    ``resource_scope`` carries host-declared changed files (e.g. the mutated
    files of a Project code change) so the canonical adapter can scope
    affected-test selection without consulting caller metadata. Caller
    metadata is never consulted.
    """
    from cmm.agent_runtime.enums import (
        AgentValidationStage,
        ValidationRequirementKind,
    )
    from cmm.agent_runtime.validation_integration_contracts import (
        ValidationRequirement,
    )

    try:
        agent_stage = AgentValidationStage(stage)
    except ValueError as exc:
        raise DomainValidationIntegrationError(
            f"unknown validation stage '{stage}'",
            details={"reason": "malformed_stage"},
        ) from exc

    cleaned = _clean_required_ids(tuple(required_validation_ids or ()))
    requirements: list[Any] = []
    Kind = ValidationRequirementKind
    for req_id in cleaned:
        lowered = req_id.lower()
        if "syntax" in lowered:
            kind = Kind.SYNTAX
        elif "ast" in lowered:
            kind = Kind.AST
        elif "test" in lowered:
            kind = Kind.UNIT_TEST
        elif "security" in lowered:
            kind = Kind.SECURITY
        elif "commit" in lowered:
            kind = Kind.COMMIT_GATE
        else:
            kind = Kind.CUSTOM
        requirements.append(
            ValidationRequirement(
                requirement_id=f"req-domain-{operation_name or 'op'}-{req_id}",
                validation_kind=kind,
                stage=agent_stage,
                required=True,
                blocking=True,
                policy_id=validation_policy_id,
                validator_ids=(req_id,),
                resource_scope=resource_scope,
                operation_name=operation_name,
                operation_version=operation_version,
                metadata={"domain_validation_id": req_id},
            )
        )
    # The operation policy itself is an obligation even when no explicit
    # required IDs are listed: without this, an operation declaring only a
    # policy ID would project no executable requirement.
    if validation_policy_id and not cleaned:
        requirements.append(
            ValidationRequirement(
                requirement_id=f"req-domain-{operation_name or 'op'}-policy",
                validation_kind=Kind.CUSTOM,
                stage=agent_stage,
                required=True,
                blocking=True,
                policy_id=validation_policy_id,
                validator_ids=(validation_policy_id,),
                resource_scope=resource_scope,
                operation_name=operation_name,
                operation_version=operation_version,
                metadata={"domain_validation_policy": validation_policy_id},
            )
        )
    return tuple(requirements)


PROJECT_CODE_MUTATION_OPERATION_IDS: tuple[str, ...] = ("project.modify_code",)

#: Registration-time declaration key on ``DomainOperationDefinition.metadata``
#: for host-declared executable Phase 9 validator IDs. Definition authority
#: (pack registration), never per-request caller metadata.
DEFINITION_VALIDATION_REQUIREMENT_IDS_KEY = "domain_validation_requirement_ids"

#: Host-derived executable Phase 9 validator IDs per Domain operation.
#: Only operations with a canonical executable mapping produce runnable
#: requirements; every other operation carrying a validation policy ID keeps
#: its policy identity as the requirement so the canonical adapter fails
#: closed on the unresolvable validator instead of silently passing.
OPERATION_EXECUTABLE_VALIDATION_IDS: dict[str, tuple[str, ...]] = {
    "project.modify_code": ("syntax_validator", "ast_validator"),
}

#: Deterministic mapping from canonical Phase 7 change-policy step IDs to the
#: executable Phase 9 validator IDs the canonical ``AgentValidationAdapter``
#: can run. Steps without an entry have no executable counterpart in the
#: runtime, so a Project change policy that mandates them fails closed (the
#: resolver raises) rather than silently dropping the obligation. Covers the
#: full ``small_change`` baseline; stronger impacts (structural/public/full)
#: contain custom validators the runtime cannot execute and therefore also
#: fail closed, which proves escalation is never downgraded to ``small``.
PROJECT_PHASE7_STEP_EXECUTABLE_VALIDATOR_IDS: dict[str, tuple[str, ...]] = {
    "formatter_check": ("formatter_check",),
    "lint": ("lint",),
    "syntax": ("syntax_validator",),
    "ast": ("ast_validator",),
    "affected_tests": ("affected_tests_step",),
}

#: Impact values that escalate to the strongest canonical ``full`` policy.
_PROJECT_FULL_IMPACT_KEYS = frozenset({"broad", "high", "full"})


def resolve_operation_validation_ids(
    definition: object,
    additional_ids: tuple[str, ...] = (),
) -> tuple[str, ...]:
    """Resolve the effective executable validation ID set for an operation.

    Deterministic monotonic union of: registration-time declared IDs from
    the canonical operation definition, the built-in executable mapping for
    well-known operations, or the operation's own validation policy identity
    (fail-closed in the canonical adapter when no capable step exists); plus
    host-computed ``additional_ids`` from workflow, dependency, cross-domain,
    or Project composition. Duplicates collapse to one obligation. Malformed
    IDs fail closed here, never downstream.
    """
    policy_id = getattr(definition, "validation_policy_id", None)
    if policy_id is None or not str(policy_id).strip():
        if additional_ids:
            return _clean_required_ids(tuple(additional_ids))
        return ()
    policy_id_str = str(policy_id).strip()
    declared: tuple[str, ...] = ()
    metadata = getattr(definition, "metadata", None)
    if isinstance(metadata, Mapping):
        raw_declared = metadata.get(DEFINITION_VALIDATION_REQUIREMENT_IDS_KEY, ())
        if raw_declared:
            declared = _clean_required_ids(tuple(raw_declared))
    operation_id = str(getattr(definition, "operation_id", "") or "")
    executable = OPERATION_EXECUTABLE_VALIDATION_IDS.get(operation_id, ())
    if declared:
        base = declared
    elif executable:
        base = tuple(executable)
    else:
        base = (policy_id_str,)
    return _clean_required_ids(tuple(base) + tuple(additional_ids or ()))


def resolve_project_domain_change_validation_ids(
    definition: object,
    additional_ids: tuple[str, ...] = (),
    impact: str | None = None,
) -> tuple[str, ...]:
    """Resolve executable validation IDs from the canonical Project change policy.

    Authority is the host-owned impact (never caller metadata) selecting a
    canonical Phase 7 ``ValidationPolicy`` via
    ``build_project_domain_change_policy``. Each required policy step is
    mapped to its executable Phase 9 validator ID(s); mandatory steps without
    an executable counterpart fail closed here (raise) rather than being
    silently dropped. The result replaces the old fixed syntax+AST mapping
    as the authoritative Project mutation obligation set.
    """
    from cmm.domains.validation_policy_bindings import (
        build_project_domain_change_policy,
    )

    effective_impact = impact if impact and str(impact).strip() else "small"
    policy = build_project_domain_change_policy(impact=effective_impact)
    executable: list[str] = []
    for step in policy.required_steps:
        mapped = PROJECT_PHASE7_STEP_EXECUTABLE_VALIDATOR_IDS.get(step)
        if mapped is None:
            raise DomainValidationIntegrationError(
                f"project change policy step '{step}' has no executable "
                "Phase 9 validator mapping: refusing to downgrade the "
                "canonical policy",
                details={
                    "reason": "unmapped_mandatory_policy_step",
                    "policy_step": step,
                    "impact": effective_impact,
                },
            )
        executable.extend(mapped)
    return _clean_required_ids(tuple(executable) + tuple(additional_ids or ()))
def resolve_domain_operation_validation_requirements(
    definition: object,
    additional_ids: tuple[str, ...] = (),
    *,
    impact: str | None = None,
    changed_files: tuple[str, ...] = (),
) -> tuple[Any, ...]:
    """Resolve host-derived runtime validation requirements for a Domain operation.

    Source of authority is the canonical operation definition (operation ID,
    ``validation_policy_id``, registration-time declared requirement IDs)
    plus host-computed composition IDs (workflow/dependency/cross-domain),
    never caller metadata. Operations without a validation policy ID and
    without additional IDs carry no obligation. ``project.modify_code``
    resolves to the canonical Project change-policy executable set
    (impact-sensitive, fail-closed on unmappable steps); any other operation
    mandating validation resolves to a policy-identity requirement that the
    canonical ``AgentValidationAdapter`` rejects fail-closed when no capable
    step exists.
    """
    policy_id = getattr(definition, "validation_policy_id", None)
    if (policy_id is None or not str(policy_id).strip()) and not additional_ids:
        return ()
    policy_id_str = str(policy_id).strip() if policy_id is not None else ""
    operation_id = str(getattr(definition, "operation_id", "") or "")
    if operation_id in PROJECT_CODE_MUTATION_OPERATION_IDS:
        required_ids = resolve_project_domain_change_validation_ids(
            definition,
            additional_ids,
            impact=impact,
        )
    else:
        required_ids = resolve_operation_validation_ids(definition, additional_ids)
    if not required_ids:
        return ()
    operation_version = str(getattr(definition, "version", "1") or "1")
    resource_scope = tuple(changed_files) if changed_files else ()
    pre = build_operation_validation_requirements(
        validation_policy_id=policy_id_str or None,
        required_validation_ids=required_ids,
        stage="pre_execution",
        operation_name=operation_id,
        operation_version=operation_version,
        resource_scope=resource_scope,
    )
    post = build_operation_validation_requirements(
        validation_policy_id=policy_id_str or None,
        required_validation_ids=required_ids,
        stage="post_execution",
        operation_name=operation_id,
        operation_version=operation_version,
        resource_scope=resource_scope,
    )
    return tuple(pre) + tuple(post)


def is_project_domain_code_mutation(operation_id: object) -> bool:
    """Whether an operation ID is a Project Domain code mutation.

    Semantic capability check, not caller metadata: only canonical Project
    code-mutating operation IDs count. Unknown IDs fail closed by returning
    False here and being rejected at the declaration/availability boundary.
    """
    return (
        isinstance(operation_id, str)
        and operation_id in PROJECT_CODE_MUTATION_OPERATION_IDS
    )


def project_change_requires_validation(operation_id: object) -> bool:
    """Project code mutations always require canonical Phase 7 validation."""
    return is_project_domain_code_mutation(operation_id)


__all__ = [
    "DEFINITION_VALIDATION_REQUIREMENT_IDS_KEY",
    "OPERATION_EXECUTABLE_VALIDATION_IDS",
    "PROJECT_CODE_MUTATION_OPERATION_IDS",
    "PROJECT_PHASE7_STEP_EXECUTABLE_VALIDATOR_IDS",
    "DomainValidationIntegrationError",
    "build_operation_validation_requirements",
    "compose_effective_validation_ids",
    "domain_operation_requires_validation",
    "is_ignored_caller_validation_metadata",
    "is_project_domain_code_mutation",
    "project_change_requires_validation",
    "require_canonical_validation_success",
    "resolve_domain_operation_validation_requirements",
    "resolve_operation_validation_ids",
    "resolve_project_domain_change_validation_ids",
    "validate_domain_specialized_result",
]
