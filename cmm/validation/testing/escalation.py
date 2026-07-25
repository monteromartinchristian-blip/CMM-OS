from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

from cmm.validation.context import ValidationContext
from cmm.validation.errors import ValidationContractError
from .selection import TestSelection


@dataclass(frozen=True, slots=True)
class TestEscalationDecision:
    include_affected_tests: bool
    include_unit_tests: bool
    include_integration_tests: bool
    requires_full_suite: bool
    confidence: float
    reasons: tuple[str, ...] = ()
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not 0.0 <= self.confidence <= 1.0:
            raise ValidationContractError("TestEscalationDecision.confidence must be between 0.0 and 1.0")
        object.__setattr__(self, "reasons", tuple(self.reasons or ()))
        object.__setattr__(self, "metadata", dict(self.metadata or {}))

    @property
    def scope(self) -> str:
        if self.requires_full_suite:
            return "full"
        if self.include_integration_tests:
            return "affected+integration"
        if self.include_unit_tests:
            return "affected+unit"
        return "affected"

    def serialize(self) -> dict[str, Any]:
        return {
            "include_affected_tests": self.include_affected_tests,
            "include_unit_tests": self.include_unit_tests,
            "include_integration_tests": self.include_integration_tests,
            "requires_full_suite": self.requires_full_suite,
            "confidence": self.confidence,
            "reasons": list(self.reasons),
            "metadata": dict(self.metadata or {}),
        }


def decide_test_escalation(context: ValidationContext, selection: TestSelection) -> TestEscalationDecision:
    package_scopes = tuple(selection.metadata.get("package_scopes", ()))
    include_unit = bool(selection.selected_tests) and not selection.requires_full_suite
    include_integration = False
    reasons = list(selection.reasons)

    for scope in package_scopes:
        if scope in {"execution", "planner", "runtime"}:
            include_integration = True

    if selection.requires_full_suite:
        include_unit = False
        include_integration = False

    if context.requested_steps is not None and "full_suite" in context.requested_steps:
        return TestEscalationDecision(
            include_affected_tests=bool(selection.selected_tests),
            include_unit_tests=include_unit,
            include_integration_tests=include_integration,
            requires_full_suite=True,
            confidence=selection.confidence,
            reasons=tuple(dict.fromkeys(reasons + ["explicit_full_suite_request"])),
            metadata={"scope": "full", "selection": selection.serialize()},
        )

    if selection.confidence < 0.7 and selection.selected_tests:
        return TestEscalationDecision(
            include_affected_tests=True,
            include_unit_tests=False,
            include_integration_tests=False,
            requires_full_suite=True,
            confidence=selection.confidence,
            reasons=tuple(dict.fromkeys(reasons + ["low_confidence"])),
            metadata={"scope": "full", "selection": selection.serialize()},
        )

    return TestEscalationDecision(
        include_affected_tests=bool(selection.selected_tests),
        include_unit_tests=include_unit,
        include_integration_tests=include_integration,
        requires_full_suite=selection.requires_full_suite,
        confidence=selection.confidence,
        reasons=tuple(reasons),
        metadata={"scope": "full" if selection.requires_full_suite else "reduced", "selection": selection.serialize()},
    )
