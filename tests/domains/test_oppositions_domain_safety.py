"""Phase 10.23 — Opposition Domain safety / genericity / clean-import tests."""

from __future__ import annotations

import pathlib

from cmm.domains import oppositions


def test_no_forbidden_parallel_infrastructure_imported():
    package_dir = pathlib.Path(oppositions.__file__).resolve().parent
    concat = "\n".join(p.read_text(encoding="utf-8") for p in package_dir.glob("*.py"))
    # No custom engine/store/scraper/scheduler/connector declarations.
    for name in (
        "OppositionMemoryStore",
        "OppositionScheduler",
        "OppositionNotifier",
        "OppositionVectorStore",
        "OppositionReasoningEngine",
        "OppositionSourceResolver",
    ):
        assert f"class {name}" not in concat


def test_no_external_connector_code():
    package_dir = pathlib.Path(oppositions.__file__).resolve().parent
    concat = "\n".join(p.read_text(encoding="utf-8") for p in package_dir.glob("*.py"))
    for marker in (
        "import requests",
        "import httpx",
        "import selenium",
        "urlopen",
        "scrapy",
        "polling_loop",
    ):
        assert marker not in concat


def test_no_user_specific_opposition_facts_hardcoded():
    """No personal targets/bodies/deadlines/scores become domain constants."""
    package_dir = pathlib.Path(oppositions.__file__).resolve().parent
    concat = "\n".join(p.read_text(encoding="utf-8") for p in package_dir.glob("*.py"))
    for marker in (
        "GACE",
        "Administrativo del Estado",
        "Cos Superior",
        "body:primary",  # 'primary' is generic; this marker intentionally absent
    ):
        assert marker not in concat


def test_no_jurisdiction_specific_universal_portal():
    package_dir = pathlib.Path(oppositions.__file__).resolve().parent
    concat = "\n".join(p.read_text(encoding="utf-8") for p in package_dir.glob("*.py"))
    for marker in ("boe.es", "doge", "bop", "gob.es"):
        assert marker not in concat.lower()


def test_clean_import_no_side_effects():
    """Import must cause no registration/file/network/memory/model side effects."""
    assert not hasattr(oppositions, "_GLOBAL_REGISTRIES")


def test_no_automatic_registration_submission_payment():
    policy = oppositions.build_oppositions_permission_policy()
    from cmm.agent_runtime.domain_permission_contracts import PermissionCapability

    assert PermissionCapability.FINANCIAL_SPEND in policy.prohibited_capabilities
    assert PermissionCapability.COMMUNICATION_EXTERNAL in policy.prohibited_capabilities
    assert PermissionCapability.IRREVERSIBLE_CHANGE in policy.prohibited_capabilities


def test_no_calendar_mutation_without_approval():
    policy = oppositions.build_oppositions_permission_policy()
    assert "schedule.modify" in policy.approval_requirements
    assert "task.create" in policy.approval_requirements


def test_no_provider_coupling():
    package_dir = pathlib.Path(oppositions.__file__).resolve().parent
    concat = "\n".join(p.read_text(encoding="utf-8") for p in package_dir.glob("*.py"))
    assert "openai" not in concat.lower()
    assert "anthropic" not in concat.lower()
