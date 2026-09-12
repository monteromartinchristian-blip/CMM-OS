"""Phase 10.46 — ``domain:mental-health`` model policy declaration.

An objective, typed, serializable declaration of the inference and validation
requirements intrinsic to Mental Health.  It contains no concrete model or
provider identifiers and performs no routing, ranking, selection, provider
construction or provider invocation.  Model choice remains user/session
controlled through the canonical runtime.
"""

from __future__ import annotations

from cmm.domains.model_policy_contracts import DomainModelPolicy

__all__ = ["build_mental_health_model_policy"]


def build_mental_health_model_policy() -> DomainModelPolicy:
    """Declare the approved ``domain:mental-health`` model requirements.

    Requirements, not selections:

    - ``require_structured_output``: emotional reviews produce structured
      sections (facts, interpretations, uncertainty) that must not be collapsed.
    - ``require_reasoning``: epistemic separation and proportionality need
      deliberate reasoning.
    - ``require_context_validation`` / ``require_response_validation``:
      sensitive context must be validated before and after inference.
    - ``minimum_context_window``: enough room for longitudinal authorized
      context plus source-separated therapy evidence.

    No provider or model is named: provider-specific clinical authority and any
    ranking/routing belong to existing or future shared layers.
    """
    return DomainModelPolicy(
        domain_id="domain:mental-health",
        require_reasoning=True,
        require_structured_output=True,
        require_context_validation=True,
        require_response_validation=True,
        minimum_context_window=32_768,
        metadata={"phase": "10.52"},
    )
