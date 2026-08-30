"""Phase 10.35 — Isolated Domain Test Harness."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from cmm.agent_runtime.operation_registry import InMemoryAgentOperationRegistry
from cmm.cognitive.reasoning_rule_registry import InMemoryReasoningRuleRegistry
from cmm.domains.enums import DomainValidationStatus
from cmm.domains.errors import DomainError
from cmm.domains.operation_registry import InMemoryDomainOperationRegistry
from cmm.domains.pack import DomainPack
from cmm.domains.permission_registry import DomainPermissionRegistry
from cmm.domains.profile_registry import InMemoryDomainProfileRegistry
from cmm.domains.registry import DomainRegistry
from cmm.domains.resource_registry import InMemoryDomainResourceRegistry
from cmm.domains.sdk.fixtures import DomainFixtureLoader
from cmm.domains.sdk.validation import validate_domain_path
from cmm.domains.validation_contracts import DomainValidationResult
from cmm.domains.workflow_registry import InMemoryDomainWorkflowRegistry


class DomainHarnessError(DomainError):
    """Raised when test harness execution or preparation fails."""


@dataclass(frozen=True, slots=True)
class DomainHarnessContext:
    """Isolated canonical registry and runtime context for Domain Pack testing."""

    pack_root: Path
    domain_pack: DomainPack | None
    domain_registry: DomainRegistry
    resource_registry: InMemoryDomainResourceRegistry
    profile_registry: InMemoryDomainProfileRegistry
    rule_registry: InMemoryReasoningRuleRegistry
    operation_registry: InMemoryDomainOperationRegistry
    workflow_registry: InMemoryDomainWorkflowRegistry
    permission_registry: DomainPermissionRegistry


class DomainTestHarness:
    """Public isolated test harness for Domain Pack development."""

    def __init__(self) -> None:
        self._fixture_loader = DomainFixtureLoader()

    def validate(self, pack_root: Path | str) -> DomainValidationResult:
        """Canonically validate the domain pack."""
        return validate_domain_path(pack_root)

    def load_fixture(self, pack_root: Path | str, fixture: str = "sample.json") -> Any:
        """Load fixture data safely without executing code."""
        return self._fixture_loader.load(pack_root, fixture)

    def prepare(self, pack_root: Path | str) -> DomainHarnessContext:
        """Prepare an isolated canonical runtime context for the pack."""
        root = Path(pack_root).resolve()
        validation_result = self.validate(root)

        blocking = [
            f for f in validation_result.findings if getattr(f, "blocking", False)
        ]
        if (
            validation_result.status
            in (DomainValidationStatus.FAILED, DomainValidationStatus.ERROR)
            or blocking
        ):
            raise DomainHarnessError(
                f"Cannot prepare harness: domain validation failed with status={validation_result.status.value}"
            )

        # Isolated canonical in-memory registries
        domain_registry = DomainRegistry()
        resource_registry = InMemoryDomainResourceRegistry()
        profile_registry = InMemoryDomainProfileRegistry()
        rule_registry = InMemoryReasoningRuleRegistry()
        operation_registry = InMemoryDomainOperationRegistry(
            InMemoryAgentOperationRegistry()
        )
        workflow_registry = InMemoryDomainWorkflowRegistry()
        permission_registry = DomainPermissionRegistry()

        return DomainHarnessContext(
            pack_root=root,
            domain_pack=None,
            domain_registry=domain_registry,
            resource_registry=resource_registry,
            profile_registry=profile_registry,
            rule_registry=rule_registry,
            operation_registry=operation_registry,
            workflow_registry=workflow_registry,
            permission_registry=permission_registry,
        )
