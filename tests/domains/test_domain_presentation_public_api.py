"""Phase 10.16 public API is limited to presentation planning and validation."""

from __future__ import annotations

from cmm import domains


def test_expected_phase_10_16_exports_present():
    expected = (
        "DomainOutputIntent", "DomainOutputIntentType", "DomainPresentationRequest",
        "DomainPresentationItemRef", "DomainPresentationSectionPlan",
        "DomainPresentationComponentDescriptor", "DomainPresentationPlan",
        "DomainPresentationValidationCode", "DomainPresentationValidationResult", "DomainPresentationPlanner",
        "DefaultDomainPresentationPlanner", "DomainPresentationPreservationValidator",
        "DefaultDomainPresentationPreservationValidator", "DomainPresentationError",
        "DomainPresentationContractError", "DomainPresentationPreservationError",
    )
    for name in expected:
        assert hasattr(domains, name), f"missing export: {name}"
        assert name in domains.__all__


def test_forbidden_renderer_and_cognitive_surfaces_are_absent():
    for name in (
        "DomainPresentationRenderer", "DomainPresentationPdfRenderer",
        "DomainPresentationQuestionDecider", "DomainPresentationUrgencyClassifier",
        "DomainPresentationWorkflowExecutor", "DomainPresentationMemoryStore",
    ):
        assert not hasattr(domains, name)


def test_presentation_modules_do_not_depend_on_cognitive_or_agent_runtime():
    for module_name in (
        "cmm.domains.presentation_contracts",
        "cmm.domains.presentation_planner",
        "cmm.domains.presentation_validation",
    ):
        module = __import__(module_name, fromlist=["__name__"])
        source = str(vars(module))
        assert "cmm.cognitive" not in source
        assert "cmm.agent_runtime" not in source
