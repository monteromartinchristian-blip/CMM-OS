from cmm.validation.results import ValidationResult
from cmm.validation.enums import ValidationStatus


def test_validation_result_defaults_and_serialize():
    vr = ValidationResult(id="rid-1", status=ValidationStatus.PENDING)
    assert vr.can_commit is False
    s = vr.serialize()
    assert s["can_commit"] is False
    assert s["status"] == "pending"
