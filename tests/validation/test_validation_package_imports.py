from cmm.validation import (
    CommandPolicy,
    SecurityAnalysisPlan,
    SecurityScope,
    SecurityValidator,
    StaticAnalysisPlan,
    StaticAnalysisScope,
    ValidationArtifact,
    ValidationContext,
    ValidationContractError,
    ValidationFinding,
    ValidationResult,
    ValidationSeverity,
    ValidationStatus,
    ValidationStep,
    ValidationStepResult,
    ValidationStepType,
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
    assert CommandPolicy is not None
    assert SecurityAnalysisPlan is not None
    assert SecurityScope is not None
    assert SecurityValidator is not None
