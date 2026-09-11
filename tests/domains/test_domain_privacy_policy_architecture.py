"""Phase 10.50 – architecture and anti-fragmentation guards.

AST-based guards over the Phase 10.50 declarative Domain privacy surface.  They
prove that the new surface only *declares* a restrictive privacy default and
never grows a parallel privacy engine/resolver/registry/store/runtime, a second
``PrivacyPolicy``/``SensitivityLevel``, a cross-domain privacy authority, or a
provider/model routing subsystem.

Guards are AST-based rather than prose-based, so documentation that merely
*describes* prohibited behaviour does not trip them.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from cmm.cognitive.privacy import PrivacyPolicy
from cmm.domains.privacy_policy_contracts import DomainPrivacyPolicy
from cmm.domains.trace_contracts import (
    DomainTrace,
    DomainTraceReference,
    PrivacyDecisionTraceEvidence,
)
from cmm.domains.validation_fragmentation import analyze_fragmentation

_REPO_ROOT = Path(__file__).resolve().parents[2]
_DOMAINS_DIR = _REPO_ROOT / "cmm" / "domains"
_COGNITIVE_DIR = _REPO_ROOT / "cmm" / "cognitive"

# The canonical Phase 10.50 production modules.
PHASE_10_50_CANONICAL_MODULES = (_DOMAINS_DIR / "privacy_policy_contracts.py",)

# The first-party declarative privacy modules.
FIRST_PARTY_PRIVACY_MODULES = tuple(sorted(_DOMAINS_DIR.glob("*/privacy.py")))

_PHASE_10_50_SURFACE = PHASE_10_50_CANONICAL_MODULES + FIRST_PARTY_PRIVACY_MODULES

PROHIBITED_PRODUCTION_NAMES = frozenset(
    {
        "DomainPrivacyEngine",
        "DomainPrivacyResolver",
        "DomainPrivacyRegistry",
        "DomainPrivacyStore",
        "DomainPrivacyRuntime",
        "DomainPrivacyTrace",
        "DomainPrivacyTraceStore",
        "DomainPrivacyTraceRegistry",
        "DomainPrivacyTraceAssembler",
        "PrivacyDecisionTraceStore",
        "PrivacyDecisionTraceRegistry",
        "PrivacyDecisionTraceResolver",
        "PrivacyDecisionTraceAssembler",
    }
)

# The safe, closed audit projection fields of a real PrivacyDecision.
SAFE_PRIVACY_EVIDENCE_FIELDS = frozenset(
    {
        "decision_id",
        "domain_id",
        "operation",
        "allowed",
        "status",
        "reason_code",
        "requires_redaction",
        "requires_approval",
        "excluded",
    }
)

PROHIBITED_MODULE_FILENAMES = frozenset(
    {
        "privacy_engine.py",
        "privacy_resolver.py",
        "privacy_registry.py",
        "privacy_store.py",
        "privacy_runtime.py",
    }
)

# Symbols that must only ever be owned by the canonical Phase 8 Cognitive layer.
PROHIBITED_REDEFINED_SYMBOLS = frozenset(
    {
        "PrivacyPolicy",
        "PrivacyMetadata",
        "SensitivityLevel",
        "ProcessingLocation",
        "PrivacyOperation",
        "PrivacyDecision",
        "PrivacyDecisionStatus",
    }
)

FORBIDDEN_AUTHORITY_TOKENS = frozenset(
    {
        "allow_cross_domain",
        "allow_cross_domain_access",
        "cross_domain_authority",
    }
)

FORBIDDEN_ROUTING_TOKENS = frozenset(
    {
        "model_id",
        "model_ids",
        "model_router",
        "provider_id",
        "provider_ids",
        "provider_registry",
        "routing_weight",
        "routing_weights",
    }
)

FORBIDDEN_IMPORT_PREFIXES = (
    "cmm.domains.model_gateway",
    "cmm.domains.providers",
    "cmm.gateway",
    "cmm.providers",
    "cmm.runtime",
)


# ── Helpers ───────────────────────────────────────────────────────────────────


def _parse(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def _relative(path: Path) -> str:
    return str(path.relative_to(_REPO_ROOT))


def _iter_domain_sources() -> list[Path]:
    return sorted(_DOMAINS_DIR.rglob("*.py"))


def _defined_names(tree: ast.Module) -> list[str]:
    names: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            names.append(node.name)
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    names.append(target.id)
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            names.append(node.target.id)
    return names


def _imported_modules(tree: ast.Module) -> list[str]:
    modules: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.append(node.module)
    return modules


def _string_literals(tree: ast.Module) -> list[str]:
    return [
        node.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant) and isinstance(node.value, str)
    ]


# ── Prohibited parallel infrastructure ────────────────────────────────────────


def test_domain_sources_never_define_prohibited_privacy_names() -> None:
    violations: list[str] = []
    for path in _iter_domain_sources():
        for name in _defined_names(_parse(path)):
            if name in PROHIBITED_PRODUCTION_NAMES:
                violations.append(f"{_relative(path)}::{name}")

    assert violations == [], violations


def test_no_prohibited_privacy_owner_files_exist() -> None:
    found = sorted(
        _relative(path)
        for path in _DOMAINS_DIR.rglob("*.py")
        if path.name in PROHIBITED_MODULE_FILENAMES
    )

    assert found == [], found


def test_phase_10_50_surface_never_redefines_canonical_privacy_symbols() -> None:
    violations: list[str] = []
    for path in _PHASE_10_50_SURFACE:
        for name in _defined_names(_parse(path)):
            if name in PROHIBITED_REDEFINED_SYMBOLS:
                violations.append(f"{_relative(path)}::{name}")

    assert violations == [], violations


def test_phase_10_50_surface_declares_no_cross_domain_authority() -> None:
    violations: list[str] = []
    for path in _PHASE_10_50_SURFACE:
        tree = _parse(path)
        for name in _defined_names(tree):
            if name in FORBIDDEN_AUTHORITY_TOKENS:
                violations.append(f"{_relative(path)}::{name}")
        for literal in _string_literals(tree):
            if literal in FORBIDDEN_AUTHORITY_TOKENS:
                violations.append(f"{_relative(path)}:{literal}")

    assert violations == [], violations


def test_first_party_privacy_modules_declare_no_provider_or_model_routing() -> None:
    violations: list[str] = []
    for path in FIRST_PARTY_PRIVACY_MODULES:
        tree = _parse(path)
        for name in _defined_names(tree):
            if name in FORBIDDEN_ROUTING_TOKENS:
                violations.append(f"{_relative(path)}::{name}")
        for literal in _string_literals(tree):
            if literal in FORBIDDEN_ROUTING_TOKENS:
                violations.append(f"{_relative(path)}:{literal}")

    assert violations == [], violations


def test_phase_10_50_surface_imports_no_gateway_or_provider_module() -> None:
    violations: list[str] = []
    for path in _PHASE_10_50_SURFACE:
        for module in _imported_modules(_parse(path)):
            if module.startswith(FORBIDDEN_IMPORT_PREFIXES):
                violations.append(f"{_relative(path)}:{module}")

    assert violations == [], violations


def test_cognitive_layer_does_not_depend_on_domains() -> None:
    violations: list[str] = []
    for path in sorted(_COGNITIVE_DIR.rglob("*.py")):
        for module in _imported_modules(_parse(path)):
            if module == "cmm.domains" or module.startswith("cmm.domains."):
                violations.append(f"{_relative(path)}:{module}")

    assert violations == [], violations


def test_first_party_privacy_modules_are_domain_local_declarations() -> None:
    expected = {
        "health",
        "relationships",
        "reflection",
        "concerns",
        "parenthood",
        "sport",
        "life_plan",
        "university",
        "oppositions",
        "languages",
        "project",
    }
    found = {path.parent.name for path in FIRST_PARTY_PRIVACY_MODULES}

    assert found == expected
    assert not (_DOMAINS_DIR / "general" / "privacy.py").exists()


@pytest.mark.parametrize("path", _PHASE_10_50_SURFACE, ids=lambda p: _relative(p))
def test_canonical_fragmentation_owner_reports_no_findings(path: Path) -> None:
    """Reuse the canonical ``domain.fragmentation`` owner; never a parallel one."""
    findings = analyze_fragmentation(path.read_text(encoding="utf-8"), _relative(path))

    assert findings == [], findings


# ── Remediation V1 guards ─────────────────────────────────────────────────────


def test_privacy_policy_has_no_sensitive_member() -> None:
    assert not hasattr(PrivacyPolicy, "SENSITIVE")
    assert "SENSITIVE" not in {member.name for member in PrivacyPolicy}


def test_domain_privacy_policy_has_no_cross_domain_authority_field() -> None:
    fields = set(DomainPrivacyPolicy.__dataclass_fields__)

    assert "allow_cross_domain" not in fields
    assert not any("cross_domain" in name for name in fields)


def test_domain_trace_carries_no_raw_privacy_metadata_field() -> None:
    fields = set(DomainTrace.__dataclass_fields__)

    assert "privacy_metadata" not in fields
    assert not any("privacy" in name for name in fields)


def test_domain_trace_reference_has_no_decision_payload_fields() -> None:
    assert set(DomainTraceReference.__dataclass_fields__) == {
        "ref_id",
        "kind",
        "domain_id",
    }


def test_privacy_decision_trace_evidence_is_a_closed_safe_projection() -> None:
    fields = set(PrivacyDecisionTraceEvidence.__dataclass_fields__)

    assert fields == SAFE_PRIVACY_EVIDENCE_FIELDS
    for forbidden in ("reasons", "metadata", "privacy_metadata", "actor_id"):
        assert forbidden not in fields
