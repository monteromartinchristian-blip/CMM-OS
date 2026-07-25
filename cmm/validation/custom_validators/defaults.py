"""Default custom validator catalog functions for CMM OS."""

from __future__ import annotations

from typing import Tuple

from cmm.validation.custom import CustomValidator, CustomValidatorRegistry
from .contracts import ValidationContractValidator
from .manifest import ProjectManifestValidator
from .public_api import PublicApiValidator
from .test_layout import TestLayoutValidator


def default_custom_validators() -> Tuple[CustomValidator, ...]:
    """Return a tuple of fresh instances of all default CMM OS custom validators."""
    return (
        ProjectManifestValidator(),
        ValidationContractValidator(),
        PublicApiValidator(),
        TestLayoutValidator(),
    )


def build_default_custom_validator_registry() -> CustomValidatorRegistry:
    """Build and populate a CustomValidatorRegistry with default custom validators."""
    registry = CustomValidatorRegistry()
    for validator in default_custom_validators():
        registry.register(validator)
    return registry
