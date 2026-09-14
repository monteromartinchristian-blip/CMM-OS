"""Isolated subscription profile builders (Plan 3 Task 3).

Codex profiles copy ONLY ``auth.json`` into a CMM-owned target home:
``config.toml`` (which may carry an external ``openai_base_url``
override) is never inherited. Claude/Antigravity descriptors carry an
isolated home plus an explicit env-strip list for PAYG isolation.
All filesystem inputs are injectable; tests never touch real homes.
"""

import json
import os
import stat
from pathlib import Path

import pytest

from kernel.llm.subscription_profiles import (
    SubscriptionProfileManager,
    create_codex_profile,
)

_MARKER = "17841"
_OVERRIDE_URL = f"http://127.0.0.1:{_MARKER}/v1"

_AUTH_PAYLOAD = {"openai_api_key": "sub-key", "tokens": {}}


def _write_source(source: Path, *, with_auth: bool = True) -> None:
    source.mkdir(parents=True, exist_ok=True)
    if with_auth:
        (source / "auth.json").write_text(json.dumps(_AUTH_PAYLOAD), encoding="utf-8")
    (source / "config.toml").write_text(
        f'model = "gpt-5"\nopenai_base_url = "{_OVERRIDE_URL}"\n',
        encoding="utf-8",
    )


def _snapshot(tree: Path) -> dict[str, bytes]:
    return {
        p.relative_to(tree).as_posix(): p.read_bytes()
        for p in sorted(tree.rglob("*"))
        if p.is_file()
    }


def _assert_no_marker(target: Path) -> None:
    hits = [
        p
        for p in sorted(target.rglob("*"))
        if p.is_file() and _MARKER in p.read_text(encoding="utf-8")
    ]
    assert hits == []


def test_codex_profile_copies_only_auth_json(tmp_path: Path) -> None:
    source, target = tmp_path / "source", tmp_path / "target"
    _write_source(source)
    before = _snapshot(source)

    result = create_codex_profile(source, target)

    assert result == target / "auth.json"
    assert (target / "auth.json").is_file()
    assert not (target / "config.toml").exists()
    assert [p.name for p in sorted(target.iterdir())] == ["auth.json"]
    assert _snapshot(source) == before


def test_codex_profile_auth_has_restrictive_permissions(
    tmp_path: Path,
) -> None:
    source, target = tmp_path / "source", tmp_path / "target"
    _write_source(source)

    result = create_codex_profile(source, target)

    mode = stat.S_IMODE(os.stat(result).st_mode)
    assert mode == 0o600


def test_codex_profile_target_free_of_external_override(
    tmp_path: Path,
) -> None:
    source, target = tmp_path / "source", tmp_path / "target"
    _write_source(source)
    before = _snapshot(source)

    create_codex_profile(source, target)

    _assert_no_marker(target)
    assert _snapshot(source) == before


def test_codex_profile_without_auth_returns_auth_required(
    tmp_path: Path,
) -> None:
    source, target = tmp_path / "source", tmp_path / "target"
    _write_source(source, with_auth=False)

    outcome = SubscriptionProfileManager().create_codex_profile(source, target)

    assert outcome.status == "auth_required"
    assert outcome.target_home is None
    assert not target.exists()


def test_create_codex_profile_without_auth_raises(tmp_path: Path) -> None:
    source, target = tmp_path / "source", tmp_path / "target"
    _write_source(source, with_auth=False)

    with pytest.raises(ValueError, match="auth_required"):
        create_codex_profile(source, target)
    assert not target.exists()


def test_claude_descriptor_carries_isolated_home_and_strip_list(
    tmp_path: Path,
) -> None:
    home = tmp_path / "claude-profile"

    descriptor = SubscriptionProfileManager().claude_descriptor(home)

    assert descriptor.provider_id == "claude"
    assert descriptor.home == home
    assert len(descriptor.env_strip) > 0
    assert all(name.strip() for name in descriptor.env_strip)


def test_antigravity_descriptor_carries_isolated_home_and_strip_list(
    tmp_path: Path,
) -> None:
    home = tmp_path / "antigravity-profile"

    descriptor = SubscriptionProfileManager().antigravity_descriptor(home)

    assert descriptor.provider_id == "antigravity"
    assert descriptor.home == home
    assert len(descriptor.env_strip) > 0
    assert all(name.strip() for name in descriptor.env_strip)


def test_env_strip_removes_payg_names_from_copied_mapping(
    tmp_path: Path,
) -> None:
    manager = SubscriptionProfileManager()
    descriptor = manager.claude_descriptor(tmp_path / "claude-profile")
    payg_name = descriptor.env_strip[0]
    env = {payg_name: "sk-payg-secret", "PATH": "/usr/bin", "HOME": "/x"}

    isolated = descriptor.isolated_env(env)

    assert payg_name not in isolated
    assert isolated["PATH"] == "/usr/bin"
    assert env[payg_name] == "sk-payg-secret"


def test_manager_codex_success_returns_ok_outcome(tmp_path: Path) -> None:
    source, target = tmp_path / "source", tmp_path / "target"
    _write_source(source)

    outcome = SubscriptionProfileManager().create_codex_profile(source, target)

    assert outcome.status == "ok"
    assert outcome.target_home == target / "auth.json"
    _assert_no_marker(target)
