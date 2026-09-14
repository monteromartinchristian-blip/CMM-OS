"""Phase 10.5 – Domain Validation Context.

Builds a Phase 7 ValidationContext from a DomainValidationRequest.
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

from cmm.domains.validation_contracts import DomainValidationRequest
from cmm.validation.context import ValidationContext


def build_domain_validation_context(
    request: DomainValidationRequest,
    *,
    actor: str = "domain-validator",
    policy: object = None,
) -> ValidationContext:
    """Build a ValidationContext for domain validation.

    Resolves root_path, sets metadata with domain validation information
    (not the pack object itself), and configures the context for internal
    domain validation steps.

    When a canonical Phase 7 ``ValidationPolicy`` is supplied, the effective
    Domain step selection is bound into ``requested_steps`` and the policy
    identity is recorded in metadata. ``requested_policy`` intentionally
    stays ``None``: that field resolves names against the canonical Phase 7
    policy catalog, and Domain policy-family names are not catalog entries
    (setting it would make the canonical pipeline return an
    ``invalid_policy`` ERROR result instead of executing Domain steps).

    Args:
        request: The domain validation request.
        actor: The actor identifier for the context.
        policy: Optional canonical Phase 7 ``ValidationPolicy`` whose Domain
            step requirements control this execution.

    Returns:
        A configured ValidationContext ready for the Phase 7 pipeline.
    """
    resolved_root = Path(request.root_path).resolve()

    # Build domain validation metadata (JSON-safe, no runtime objects)
    domain_meta: dict[str, object] = {
        "domain_id": "",
        "version": "",
        "strict": request.strict,
        "allow_untrusted": request.allow_untrusted,
        "run_tests": request.run_tests,
    }

    # Extract domain_id and version from pack if available
    if request.pack is not None:
        if hasattr(request.pack, "definition") and request.pack.definition is not None:
            domain_meta["domain_id"] = str(request.pack.definition.id)
            domain_meta["version"] = request.pack.definition.version
        elif hasattr(request.pack, "manifest") and request.pack.manifest is not None:
            domain_meta["domain_id"] = str(request.pack.manifest.id)
            domain_meta["version"] = request.pack.manifest.version

    # Build context
    metadata: dict[str, object] = {
        "domain_validation": domain_meta,
        "security_profile": "validation",
    }
    if policy is not None:
        required_steps = tuple(getattr(policy, "required_steps", ()))
        policy_metadata = getattr(policy, "metadata", {}) or {}
        family = (
            policy_metadata.get("domain_policy_family")
            if isinstance(policy_metadata, Mapping)
            else None
        )
        metadata["domain_policy"] = {
            "name": str(getattr(policy, "name", "")),
            "family": str(family) if family is not None else "",
            "required_steps": [str(step) for step in required_steps],
        }
    context = ValidationContext(
        project_root=resolved_root,
        changed_files=(),
        change_type="domain_validation",
        execution_mode="local",
        requested_steps=request.requested_steps,
        excluded_steps=request.excluded_steps,
        allow_commit=False,
        requested_policy=None,
        actor=actor,
        metadata=metadata,
    )

    return context


__all__ = [
    "build_domain_validation_context",
]
