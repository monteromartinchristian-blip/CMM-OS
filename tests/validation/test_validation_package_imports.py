from cmm.validation import (
    ValidationStatus,
    ValidationSeverity,
    ValidationStepType,
    ValidationContractError,
    ValidationFinding,
    ValidationArtifact,
    ValidationStep,
    ValidationStepResult,
    ValidationContext,
    ValidationResult,
    StaticAnalysisPlan,
    StaticAnalysisScope,
)


def test_package_exports_exist():
    # Simply assert names are importable
    assert ValidationStatus is not None
    assert ValidationSeverity is not None
    assert ValidationStepType is not None
    assert ValidationContractError is not None
    assert ValidationFinding is not None
    assert ValidationArtifact is not None
    assert ValidationStep is not None
    assert ValidationStepResult is not None
    assert ValidationContext is not None
    assert ValidationResult is not None
    assert StaticAnalysisPlan is not None
    assert StaticAnalysisScope is not None
