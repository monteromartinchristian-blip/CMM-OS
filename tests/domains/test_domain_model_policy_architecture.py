"""Phase 10.46 – architecture guards for the model-agnostic domain policy.

These guards protect DP-046 against future fragmentation: domain policies must
stay free of concrete model/provider selection, ``kernel.llm`` must stay
ignorant of ``cmm.domains``, and Phase 10.46 must not introduce parallel
routing/registry/catalog/fallback/gateway infrastructure.
"""

from __future__ import annotations

import ast
import re
from dataclasses import fields
from pathlib import Path

import pytest

from cmm.domains.errors import DomainSerializationError
from cmm.domains.model_policy_contracts import DomainModelPolicy

_REPO_ROOT = Path(__file__).resolve().parents[2]

_POLICY_CONTRACT_PATH = _REPO_ROOT / "cmm" / "domains" / "model_policy_contracts.py"
_ADAPTER_PATH = _REPO_ROOT / "cmm" / "agent_runtime" / "domain_model_policy_adapter.py"

_PHASE_10_46_PRODUCTION_PATHS = (_POLICY_CONTRACT_PATH, _ADAPTER_PATH)

_APPROVED_POLICY_FIELDS = (
    "domain_id",
    "require_reasoning",
    "require_tool_calling",
    "require_structured_output",
    "require_json_mode",
    "require_json_schema",
    "require_vision",
    "require_audio_input",
    "require_audio_output",
    "require_embeddings",
    "minimum_context_window",
    "require_context_validation",
    "require_response_validation",
    "fallback_policy",
    "metadata",
)

_FORBIDDEN_POLICY_FIELDS = (
    "preferred_models",
    "prohibited_models",
    "preferred_providers",
    "prohibited_providers",
    "local_models",
    "minimum_quality",
    "latency_tolerance",
    "recommended_budget_eur",
)

_FORBIDDEN_ROUTING_IMPORT_PREFIXES = (
    "kernel.llm.model_router",
    "kernel.llm.provider_registry",
    "kernel.llm.model_catalog",
    "kernel.llm.clients",
    "kernel.llm.provider_factory",
    "kernel.llm.openai_provider",
    "kernel.llm.openai_compatible_provider",
    "kernel.llm.ollama_provider",
)

_PARALLEL_OWNER_PATTERN = re.compile(
    r"(ModelRouter|ProviderRegistry|ModelCatalog|FallbackEngine|ModelGateway)$"
)


def _imported_modules(tree: ast.AST) -> set[str]:
    """Return every absolutely imported module name in an AST."""
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            modules.add(node.module)
    return modules


def _imported_modules_from_file(path: Path) -> set[str]:
    return _imported_modules(ast.parse(path.read_text(encoding="utf-8")))


def _class_names(tree: ast.AST) -> set[str]:
    return {node.name for node in ast.walk(tree) if isinstance(node, ast.ClassDef)}


def _domain_imports(modules: set[str]) -> set[str]:
    return {
        module
        for module in modules
        if module == "cmm.domains" or module.startswith("cmm.domains.")
    }


# ── DomainModelPolicy surface ─────────────────────────────────────────────────


def test_policy_declares_only_the_approved_field_set() -> None:
    assert {field.name for field in fields(DomainModelPolicy)} == set(
        _APPROVED_POLICY_FIELDS
    )


def test_policy_serialized_payload_excludes_forbidden_selection_fields() -> None:
    payload = DomainModelPolicy(domain_id="domain:health").to_dict()

    assert set(payload) == set(_APPROVED_POLICY_FIELDS)
    assert set(_FORBIDDEN_POLICY_FIELDS).isdisjoint(payload)


@pytest.mark.parametrize("field_name", _FORBIDDEN_POLICY_FIELDS)
def test_policy_rejects_forbidden_selection_fields(field_name: str) -> None:
    with pytest.raises(DomainSerializationError):
        DomainModelPolicy.from_dict(
            {"domain_id": "domain:health", field_name: ["vendor:model"]}
        )


# ── Import direction ──────────────────────────────────────────────────────────


def test_policy_contract_avoids_routing_infrastructure_imports() -> None:
    imports = _imported_modules_from_file(_POLICY_CONTRACT_PATH)

    offending = sorted(
        module
        for module in imports
        if module.startswith(_FORBIDDEN_ROUTING_IMPORT_PREFIXES)
    )

    assert offending == []


def test_adapter_avoids_routing_infrastructure_imports() -> None:
    imports = _imported_modules_from_file(_ADAPTER_PATH)

    offending = sorted(
        module
        for module in imports
        if module.startswith(_FORBIDDEN_ROUTING_IMPORT_PREFIXES)
    )

    assert offending == []


def test_kernel_llm_never_imports_domains() -> None:
    offenders: list[tuple[str, str]] = []

    for path in sorted((_REPO_ROOT / "kernel" / "llm").rglob("*.py")):
        for module in _domain_imports(_imported_modules_from_file(path)):
            offenders.append((path.relative_to(_REPO_ROOT).as_posix(), module))

    assert offenders == []


def test_phase_10_46_runtime_surfaces_never_import_domains() -> None:
    offenders: list[tuple[str, str]] = []

    for path in (
        _ADAPTER_PATH,
        _REPO_ROOT / "cmm" / "agent_runtime" / "model_requirements_resolver.py",
    ):
        for module in _domain_imports(_imported_modules_from_file(path)):
            offenders.append((path.name, module))

    assert offenders == []


# ── Anti-fragmentation ────────────────────────────────────────────────────────


def test_phase_10_46_production_defines_no_parallel_owner_classes() -> None:
    offenders: list[tuple[str, str]] = []

    for path in _PHASE_10_46_PRODUCTION_PATHS:
        for name in _class_names(ast.parse(path.read_text(encoding="utf-8"))):
            if _PARALLEL_OWNER_PATTERN.search(name):
                offenders.append((path.name, name))

    assert offenders == []


def test_no_production_domain_pack_was_retrofitted_with_a_model_policy() -> None:
    allowed_names = {"model_policy_contracts.py", "contracts.py", "__init__.py"}
    offenders: list[str] = []

    for path in sorted((_REPO_ROOT / "cmm" / "domains").rglob("*.py")):
        if path.name in allowed_names:
            continue
        if "DomainModelPolicy" in path.read_text(encoding="utf-8"):
            offenders.append(path.relative_to(_REPO_ROOT).as_posix())

    assert offenders == []


# ── Detector calibration ──────────────────────────────────────────────────────


def test_import_detector_flags_forbidden_kernel_modules() -> None:
    imports = _imported_modules(
        ast.parse("from kernel.llm.model_router import ModelRouter\n")
    )

    assert any(
        module.startswith(_FORBIDDEN_ROUTING_IMPORT_PREFIXES) for module in imports
    )


def test_import_detector_flags_kernel_to_domains_import() -> None:
    imports = _imported_modules(
        ast.parse("from cmm.domains.contracts import DomainDefinition\n")
    )

    assert _domain_imports(imports) == {"cmm.domains.contracts"}


def test_parallel_owner_detector_flags_duplicate_infrastructure() -> None:
    names = _class_names(
        ast.parse(
            "class DomainModelRouter:\n    pass\n"
            "class DomainProviderRegistry:\n    pass\n"
            "class DomainModelCatalog:\n    pass\n"
            "class DomainFallbackEngine:\n    pass\n"
            "class DomainModelGateway:\n    pass\n"
        )
    )

    assert sum(1 for name in names if _PARALLEL_OWNER_PATTERN.search(name)) == 5


def test_parallel_owner_detector_accepts_canonical_names() -> None:
    names = _class_names(ast.parse("class DomainModelPolicy:\n    pass\n"))

    assert not any(_PARALLEL_OWNER_PATTERN.search(name) for name in names)


# ── Remediation V1 – premium participation boundaries ─────────────────────────


_RESOLVER_PATH = _REPO_ROOT / "cmm" / "agent_runtime" / "model_requirements_resolver.py"


def test_resolver_has_no_source_kind_premium_special_case() -> None:
    tree = ast.parse(_RESOLVER_PATH.read_text(encoding="utf-8"))
    offenders: list[str] = []

    for node in ast.walk(tree):
        if isinstance(node, ast.Compare):
            for operand in (node.left, *node.comparators):
                if isinstance(operand, ast.Attribute) and operand.attr == "source_kind":
                    offenders.append(operand.attr)

    assert offenders == []


def test_domain_adapter_explicitly_abstains_from_premium() -> None:
    tree = ast.parse(_ADAPTER_PATH.read_text(encoding="utf-8"))
    values: list[object] = []

    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            for keyword in node.keywords:
                if keyword.arg == "contributes_premium_permission":
                    values.append(keyword.value)

    assert len(values) == 1
    value = values[0]
    assert isinstance(value, ast.Constant)
    assert value.value is False


def test_kernel_llm_has_no_premium_participation_logic() -> None:
    offenders: list[str] = []

    for path in sorted((_REPO_ROOT / "kernel" / "llm").rglob("*.py")):
        if "contributes_premium_permission" in path.read_text(encoding="utf-8"):
            offenders.append(path.name)

    assert offenders == []


def test_kernel_premium_flag_remains_plain_bool() -> None:
    from kernel.llm.model_selection import ModelRequirements

    premium_field = next(
        field for field in fields(ModelRequirements) if field.name == "premium_allowed"
    )

    assert str(premium_field.type) == "bool"
    assert ModelRequirements().premium_allowed is False


def test_premium_special_case_detector_is_calibrated() -> None:
    tree = ast.parse("if source.source_kind == 'domain':\n    pass\n")
    offenders = [
        operand.attr
        for node in ast.walk(tree)
        if isinstance(node, ast.Compare)
        for operand in (node.left, *node.comparators)
        if isinstance(operand, ast.Attribute) and operand.attr == "source_kind"
    ]

    assert offenders == ["source_kind"]
