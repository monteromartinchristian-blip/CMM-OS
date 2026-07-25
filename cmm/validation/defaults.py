"""Convenience helpers for building the default validation pipeline."""

from __future__ import annotations

from cmm.validation.catalog import build_default_validation_registry
from cmm.validation.executor import ValidationExecutor
from cmm.validation.pipeline import ValidationPipeline


def build_default_pipeline() -> ValidationPipeline:
    return ValidationPipeline(executor=ValidationExecutor(), registry=build_default_validation_registry())


def build_default_validation_pipeline() -> ValidationPipeline:
    return build_default_pipeline()
