"""Phase 10.46 — ``domain:neurodivergence`` model policy declaration.

An objective, typed, serializable declaration of the inference and validation
requirements intrinsic to Neurodivergence reasoning.  It contains no concrete
model or provider identifiers and performs no routing, ranking, selection,
provider construction or provider invocation.  Model choice remains
user/session controlled through the canonical runtime, and no model choice can
weaken the effective Neurodivergence privacy or permission constraints.
"""

from __future__ import annotations

from cmm.domains.model_policy_contracts import DomainModelPolicy

__all__ = ["build_neurodivergence_model_policy"]


def build_neurodivergence_model_policy() -> DomainModelPolicy:
    """Declare the approved ``domain:neurodivergence`` model requirements.

    Requirements, not selections:

    - ``require_structured_output``: evidence organization produces structured
      sections (certainty, provenance, alternatives, contradictions) that must
      not be collapsed into unstructured prose.
    - ``require_reasoning``: certainty preservation, exploration-friendly
      differential reasoning and the diagnostic non-promotion boundary need
      deliberate reasoning rather than pattern completion.
    - ``require_context_validation`` / ``require_response_validation``:
      sensitive developmental and assessment context must be validated before
      and after inference.
    - ``minimum_context_window``: enough room for longitudinal, multi-source,
      multi-period evidence plus authorized cross-domain projections.

    No provider or model is named: model selection remains user-controlled and
    any routing belongs to the canonical model routing layer.
    """
    return DomainModelPolicy(
        domain_id="domain:neurodivergence",
        require_reasoning=True,
        require_structured_output=True,
        require_context_validation=True,
        require_response_validation=True,
        minimum_context_window=32_768,
        metadata={
            "phase": "10.53",
            # Declared reasoning needs, expressed provider-neutrally.
            "reasoning_requirements": (
                "structured_reasoning",
                "uncertainty_preservation",
                "source_provenance_fidelity",
                "longitudinal_comparison",
                "differential_comparison",
            ),
            "provider_agnostic": True,
            "routing_owned_by": "canonical_model_routing",
            "user_model_choice_preserved": True,
        },
    )
