import pytest

from cmm.validation import ValidationRegistry, ValidationRegistryError
from cmm.validation.protocols import InternalValidator
from cmm.validation.context import ValidationContext
from cmm.validation.steps import ValidationStep, ValidationStepType, ValidationStepResult
from cmm.validation.enums import ValidationStatus
from pathlib import Path


class DummyValidator:
    name = "dummy"

    def validate(self, context: ValidationContext, step: ValidationStep) -> ValidationStepResult:
        return ValidationStepResult(name=step.name, status=ValidationStatus.PASSED)


def test_registry_basic():
    r = ValidationRegistry()
    v = DummyValidator()
    r.register("dummy", v)
    assert r.has("dummy")
    assert r.get("dummy") is v
    assert "dummy" in r.names()
    r.unregister("dummy")
    assert not r.has("dummy")


def test_registry_errors():
    r = ValidationRegistry()
    with pytest.raises(ValidationRegistryError):
        r.register("", DummyValidator())
    r.register("dummy", DummyValidator())
    with pytest.raises(ValidationRegistryError):
        r.register("dummy", DummyValidator())
    with pytest.raises(ValidationRegistryError):
        r.get("")
    with pytest.raises(ValidationRegistryError):
        r.get("missing")
