from cmm.validation.enums import ValidationStatus, ValidationSeverity


def test_validation_status_values():
    expected = [
        "pending",
        "running",
        "passed",
        "failed",
        "warning",
        "skipped",
        "cancelled",
        "timed_out",
        "error",
    ]
    assert [s.value for s in ValidationStatus] == expected


def test_validation_severity_values():
    expected = ["info", "warning", "error", "critical"]
    assert [s.value for s in ValidationSeverity] == expected
