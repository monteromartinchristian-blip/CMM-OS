"""Phase 10.39 — AT-DP-039 connected fragmentation acceptance test.

Proves the canonical domain validation chain end-to-end:

  Domain Pack source
  → DomainValidationRequest
  → PipelineDomainValidator
  → domain.fragmentation
  → DomainFragmentationValidator
  → DomainValidationResult.fragmentation_valid
  → ensure_domain_validation_allows_install(...)

Legitimate canonical reuse is accepted.  Representative architectural
fragmentation is blocked.  Untrusted pack code is never executed.
"""

from __future__ import annotations

import json

import pytest

from cmm.domains.errors import DomainValidationBlocked
from cmm.domains.validation import (
    PipelineDomainValidator,
    ensure_domain_validation_allows_install,
)
from cmm.domains.validation_contracts import DomainValidationRequest
from tests.domains._loader_helpers import make_pack

# ── Helpers ───────────────────────────────────────────────────────────────────


def _validation_request(tmp_path, source: str) -> DomainValidationRequest:
    """Write *source* into a minimal domain pack and return a validation request."""
    domain_dir = tmp_path / "test-domain"
    domain_dir.mkdir(parents=True, exist_ok=True)

    manifest = {
        "id": "test-domain",
        "version": "1.0.0",
        "author": "tester",
        "license": "MIT",
    }
    (domain_dir / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    (domain_dir / "probe.py").write_text(source, encoding="utf-8")

    pack = make_pack("test-domain", "1.0.0", root_path=str(domain_dir))

    return DomainValidationRequest(
        pack=pack,
        root_path=str(domain_dir),
        strict=False,
        run_tests=False,
    )


# ── Positive: canonical reuse accepted ────────────────────────────────────────


@pytest.mark.parametrize(
    "source",
    (
        (
            "from cmm.planner import TaskPlanner\n"
            "class GuardedPlannerAdapter(TaskPlanner):\n"
            "    pass\n"
        ),
        (
            "import cmm.planner\n"
            "class GuardedPlannerAdapter(cmm.planner.TaskPlanner):\n"
            "    pass\n"
        ),
    ),
)
def test_at_dp039_canonical_reuse_passes_fragmentation_and_install_gate(
    tmp_path,
    source: str,
) -> None:
    """A pack that legitimately extends a canonical base must pass fragmentation.

    Uses the real ``cmm.planner.TaskPlanner`` canonical class
    (Phase 10.39 remediation: replaced fictional ``BasePlanner``).
    """
    result = PipelineDomainValidator().validate(_validation_request(tmp_path, source))

    assert result.fragmentation_valid is True

    frag_findings = [
        f for f in result.findings if (f.code or "").startswith("DOMAIN_FRAGMENTATION_")
    ]
    assert len(frag_findings) == 0

    # Must not raise
    ensure_domain_validation_allows_install(result)


# ── Negative: connected rejection matrix ──────────────────────────────────────

VIOLATIONS: list[tuple[str, str]] = [
    (
        "class MemoryStore:\n    pass\n",
        "DOMAIN_FRAGMENTATION_MEMORY_DUPLICATION",
    ),
    (
        "class KnowledgeStore:\n    pass\n",
        "DOMAIN_FRAGMENTATION_KNOWLEDGE_STORE_DUPLICATION",
    ),
    (
        "class KnowledgeGraph:\n    pass\n",
        "DOMAIN_FRAGMENTATION_KNOWLEDGE_GRAPH_DUPLICATION",
    ),
    (
        "class Planner:\n    pass\n",
        "DOMAIN_FRAGMENTATION_PLANNER_DUPLICATION",
    ),
    (
        "class AgentRuntime:\n    pass\n",
        "DOMAIN_FRAGMENTATION_AGENT_RUNTIME_DUPLICATION",
    ),
    (
        "class HealthReasoningEngine:\n    pass\n",
        "DOMAIN_FRAGMENTATION_REASONING_ENGINE_DUPLICATION",
    ),
    (
        "class UniversityWorkflowEngine:\n    pass\n",
        "DOMAIN_FRAGMENTATION_WORKFLOW_ENGINE_DUPLICATION",
    ),
    (
        "class HealthPermissionSystem:\n    pass\n",
        "DOMAIN_FRAGMENTATION_PERMISSION_SYSTEM_DUPLICATION",
    ),
    (
        "class HealthSessionStore:\n    pass\n",
        "DOMAIN_FRAGMENTATION_SESSION_INFRASTRUCTURE_DUPLICATION",
    ),
    (
        "class DomainOperationResult:\n    pass\n",
        "DOMAIN_FRAGMENTATION_OPERATION_RESULT_DUPLICATION",
    ),
    (
        "class KnowledgeItem:\n    pass\n",
        "DOMAIN_FRAGMENTATION_CONTRACT_REDEFINITION",
    ),
    (
        "import sqlite3\n",
        "DOMAIN_FRAGMENTATION_DIRECT_PERSISTENCE_ACCESS",
    ),
    (
        "open('state.json', 'w').write('{}')\n",
        "DOMAIN_FRAGMENTATION_DIRECT_WRITE",
    ),
    (
        "skip_validation = True\n",
        "DOMAIN_FRAGMENTATION_POLICY_BYPASS",
    ),
    # ── BLOCKER-01 regressions: unrelated official base must not grant immunity ──
    (
        (
            "from cmm.domains.pack import DomainPack\n"
            "class EvilMemoryStore(DomainPack):\n"
            "    pass\n"
        ),
        "DOMAIN_FRAGMENTATION_MEMORY_DUPLICATION",
    ),
    (
        (
            "from cmm.domains.pack import DomainPack\n"
            "class EvilPlanner(DomainPack):\n"
            "    pass\n"
        ),
        "DOMAIN_FRAGMENTATION_PLANNER_DUPLICATION",
    ),
    (
        (
            "from cmm.domains.pack import DomainPack\n"
            "class EvilWorkflowEngine(DomainPack):\n"
            "    pass\n"
        ),
        "DOMAIN_FRAGMENTATION_WORKFLOW_ENGINE_DUPLICATION",
    ),
    # ── MAJOR-01 regressions: recreated canonical services ─────────────────────
    (
        "class HealthDomainRegistry:\n    pass\n",
        "DOMAIN_FRAGMENTATION_REGISTRY_DUPLICATION",
    ),
    (
        "class HealthEventBus:\n    pass\n",
        "DOMAIN_FRAGMENTATION_EVENT_BUS_DUPLICATION",
    ),
    # ── MAJOR-01 regressions: attribute/annotated policy bypass ────────────────
    (
        "class Config: pass\nconfig = Config()\nconfig.skip_validation = True\n",
        "DOMAIN_FRAGMENTATION_POLICY_BYPASS",
    ),
    (
        "skip_validation: bool = True\n",
        "DOMAIN_FRAGMENTATION_POLICY_BYPASS",
    ),
    # ── MAJOR-01 regressions: ImportFrom persistence ───────────────────────────
    (
        "from shelve import open\n",
        "DOMAIN_FRAGMENTATION_DIRECT_PERSISTENCE_ACCESS",
    ),
    (
        "from sqlite3 import connect\n",
        "DOMAIN_FRAGMENTATION_DIRECT_PERSISTENCE_ACCESS",
    ),
    # ── V2 BLOCKER-01: rebound canonical binding must not grant immunity ───────
    (
        (
            "from cmm.planner import TaskPlanner\n"
            "TaskPlanner = object\n"
            "class EvilPlanner(TaskPlanner):\n"
            "    pass\n"
        ),
        "DOMAIN_FRAGMENTATION_PLANNER_DUPLICATION",
    ),
]


@pytest.mark.parametrize(("source", "expected_code"), VIOLATIONS)
def test_at_dp039_fragmented_pack_fails_closed_at_install_gate(
    tmp_path,
    source: str,
    expected_code: str,
) -> None:
    """Every representative violation blocks fragmentation and the install gate."""
    result = PipelineDomainValidator().validate(_validation_request(tmp_path, source))

    codes = {finding.code for finding in result.findings}

    assert expected_code in codes, (
        f"Expected finding code {expected_code} but got {codes}"
    )
    assert result.fragmentation_valid is False

    with pytest.raises(DomainValidationBlocked) as exc_info:
        ensure_domain_validation_allows_install(result)

    assert "fragmentation_invalid" in exc_info.value.details["reason_codes"]


# ── No-code-execution proof ──────────────────────────────────────────────────


def test_at_dp039_pack_code_is_not_executed_during_validation(tmp_path) -> None:
    """Validation must never execute untrusted Domain Pack code."""
    result = PipelineDomainValidator().validate(
        _validation_request(
            tmp_path,
            "raise RuntimeError('DOMAIN PACK CODE MUST NOT EXECUTE DURING VALIDATION')\n",
        )
    )
    # Validation completes without raising RuntimeError
    assert result.fragmentation_valid is True


# ── Side-effect proof ─────────────────────────────────────────────────────────


def test_at_dp039_validation_does_not_touch_filesystem(tmp_path) -> None:
    """Validation must not execute code that creates filesystem side effects."""
    source = "from pathlib import Path\nPath('EXECUTED_MARKER').touch()\n"
    result = PipelineDomainValidator().validate(_validation_request(tmp_path, source))
    domain_dir = tmp_path / "test-domain"
    assert not (domain_dir / "EXECUTED_MARKER").exists()
    assert result.fragmentation_valid is True
