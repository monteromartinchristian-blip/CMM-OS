"""Phase 10.47 — Concerns domain benchmark assets.

Declarative benchmark cases derived from the audited Concerns Domain rules
(``concerns.understand_before_intervene``, ``concerns.support_need_calibration``,
``concerns.evidence_calibrated_reassurance``, ``concerns.proportional_risk``,
``concerns.no_catastrophic_escalation``, ``concerns.no_false_reassurance``) and
its existing resource catalog. These assets are data only: they never create a
risk engine and never grant medical or mental-health authority.
"""

from __future__ import annotations

from cmm.domains.benchmark_contracts import (
    DomainBenchmarkCase,
    DomainBenchmarkSuite,
)


def build_concerns_benchmark_suites() -> tuple[DomainBenchmarkSuite, ...]:
    """Build the deterministic ``benchmark-suite:concerns:core`` suite."""
    return (
        DomainBenchmarkSuite(
            id="benchmark-suite:concerns:core",
            domain_id="domain:concerns",
            schema_version="1",
            version="1",
            cases=(
                DomainBenchmarkCase(
                    id="benchmark-case:concerns:understanding-and-support-001",
                    domain_id="domain:concerns",
                    objective=(
                        "Respond to a personal concern by understanding it before "
                        "intervening and calibrating support to the declared need"
                    ),
                    input_resource_refs=(
                        "concerns.user_message",
                        "concerns.conversation",
                        "concerns.note",
                    ),
                    expected_elements=(
                        "understanding precedes intervention",
                        "support need is calibrated",
                        "emotional validation is offered without inflating facts",
                        "materially useful questions are asked",
                        "directness stays grounded",
                    ),
                    required_constraints=(
                        "validate the experience without asserting unverified facts",
                        "keep the response proportionate to the declared need",
                    ),
                    prohibited_behaviors=(
                        "intervene before understanding",
                        "inflate an interpretation into a fact",
                        "pressure the user toward an action",
                    ),
                    evaluation_criteria=(
                        "understanding before intervention",
                        "support-need calibration",
                        "emotional validation without fact inflation",
                        "materially useful questions",
                        "grounded directness",
                    ),
                    required_format="structured",
                    metadata={
                        "fixture_kind": "synthetic",
                        "roadmap_area": "understanding-and-support",
                    },
                ),
                DomainBenchmarkCase(
                    id="benchmark-case:concerns:separation-and-reassurance-002",
                    domain_id="domain:concerns",
                    objective=(
                        "Separate reality, interpretation, fear and scenario when "
                        "reassuring a recurring concern"
                    ),
                    input_resource_refs=(
                        "concerns.journal_entry",
                        "concerns.event",
                        "concerns.memory_entry",
                    ),
                    expected_elements=(
                        "reality, interpretation, fear and scenario are separated",
                        "reassurance is calibrated to evidence",
                        "uncertainty is preserved",
                        "recurrence is described without automatic pathologizing",
                    ),
                    required_constraints=(
                        "do not offer false reassurance",
                        "do not pathologize recurrence automatically",
                    ),
                    prohibited_behaviors=(
                        "give false reassurance",
                        "promote fear to fact",
                        "pathologize a recurring concern",
                    ),
                    evaluation_criteria=(
                        "reality / interpretation / fear / scenario separation",
                        "evidence-calibrated reassurance",
                        "uncertainty preservation",
                        "no false reassurance",
                        "recurrence without automatic pathologization",
                    ),
                    required_format="structured",
                    metadata={
                        "fixture_kind": "synthetic",
                        "roadmap_area": "separation-and-reassurance",
                    },
                ),
                DomainBenchmarkCase(
                    id="benchmark-case:concerns:risk-and-action-003",
                    domain_id="domain:concerns",
                    objective=(
                        "Assess a declared risk proportionally and hand off "
                        "factual or risk questions to the owning domain"
                    ),
                    input_resource_refs=(
                        "concerns.external_source",
                        "concerns.domain_result",
                        "concerns.decision",
                    ),
                    expected_elements=(
                        "risk is assessed proportionally",
                        "catastrophic escalation is avoided",
                        "proposed action is proportional",
                        "factual and risk questions are handed off to the owning domain",
                    ),
                    required_constraints=(
                        "avoid catastrophic escalation",
                        "route factual or risk questions to the owning domain",
                    ),
                    prohibited_behaviors=(
                        "escalate catastrophically",
                        "issue medical or mental-health authority",
                        "retain cross-domain factual questions without handoff",
                    ),
                    evaluation_criteria=(
                        "proportional risk",
                        "no catastrophic escalation",
                        "proportional action",
                        "cross-domain factual and risk handoff",
                    ),
                    required_format="structured",
                    metadata={
                        "fixture_kind": "synthetic",
                        "roadmap_area": "risk-and-action",
                    },
                ),
            ),
            metadata={"source": "first-party", "phase": "10.47"},
        ),
    )
