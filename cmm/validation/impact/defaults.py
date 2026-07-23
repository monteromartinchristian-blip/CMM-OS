from __future__ import annotations

from cmm.validation.context import ValidationContext

from .validation import change_impact_step


def default_impact_steps(context: ValidationContext):
    return (change_impact_step(context),)
