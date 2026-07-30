"""Phase 10.5 – Domain Validation Context.

Builds a Phase 7 ValidationContext from a DomainValidationRequest.
"""

from __future__ import annotations

from pathlib import Path

from cmm.domains.validation_contracts import DomainValidationRequest
from cmm.validation.context import ValidationContext


def build_domain_validation_context(
    request: DomainValidationRequest,
    *,
    actor: str = "domain-validator",
) -> ValidationContext:
    """Build a ValidationContext for domain validation.

    Resolves root_path, sets metadata with domain validation information
    (not the pack object itself), and configures the context for internal
    domain validation steps.

    Args:
        request: The domain validation request.
        actor: The actor identifier for the context.

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
    context = ValidationContext(
        project_root=resolved_root,
        changed_files=(),
        change_type="domain_validation",
        execution_mode="local",
        requested_steps=request.requested_steps,
        excluded_steps=request.excluded_steps,
        allow_commit=False,
        requested_policy="domain_validation",
        actor=actor,
        metadata={
            "domain_validation": domain_meta,
            "security_profile": "validation",
        },
    )

    return context


__all__ = [
    "build_domain_validation_context",
]
