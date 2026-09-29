"""Lifecycle and locality truth for discovered local runtimes.

These cover the behaviour a machine actually exhibits: a runtime that is
restarting, a proxy that answers on loopback but forwards to a vendor cloud, a
tag the runtime marks as hosted, and a model that really was uninstalled.  The
distinction the whole module exists to preserve is between "not usable right
now" and "not here", and between both of those and "gone".
"""

from __future__ import annotations

import json
from typing import Any, Mapping

import pytest

from kernel.llm.local_runtime_discovery import (
    ABSENCE_CONFIRMATIONS,
    LocalRuntimeEndpoint,
    LocalRuntimeSnapshot,
    discover_local_runtimes,
    load_endpoints,
    load_snapshot,
    state_path,
    store_snapshot,
)

JAN = LocalRuntimeEndpoint(
    name="jan-llamacpp",
    base_url="http://127.0.0.1:60407/v1",
    protocol="openai",
    own_identities=frozenset({"llamacpp", "llama.cpp"}),
)

OLLAMA = LocalRuntimeEndpoint(
    name="ollama",
    base_url="http://127.0.0.1:11434",
    protocol="ollama",
    own_identities=frozenset({"ollama"}),
)

QWEN_NORMAL = "Qwen3_5-4B-Q4_K_M"
QWEN_UNCENSORED = "Qwen3_5-4B-Uncensored-HauhauCS-Aggressive-Q4_K_M"
QWEN_IQ4 = "Qwen3_5-4B-IQ4_XS"


def jan_listing(*ids: str) -> dict[str, Any]:
    return {
        "object": "list",
        "data": [
            {"id": model_id, "object": "model", "owned_by": "llamacpp"} for model_id in ids
        ],
    }


def ollama_tags(*entries: tuple[str, bool]) -> dict[str, Any]:
    """Build an Ollama ``/api/tags`` payload; the bool marks a hosted tag."""

    models = []
    for name, hosted in entries:
        model: dict[str, Any] = {
            "name": name,
            "size": 300 if hosted else 2_700_000_000,
            "details": {"family": "qwen3", "parameter_size": "4.0B", "quantization_level": "Q4_K_M"},
        }
        if hosted:
            model["remote_host"] = "https://ollama.com"
        models.append(model)
    return {"models": models}


class Transport:
    """A scripted loopback runtime, addressed by URL fragment."""

    def __init__(self, **routes: dict[str, Any] | Exception) -> None:
        self.routes = routes
        self.calls: list[str] = []

    def __call__(self, url: str, headers: Mapping[str, str]) -> Any:
        self.calls.append(url)
        for fragment, response in self.routes.items():
            if fragment in url:
                if isinstance(response, Exception):
                    raise response
                return response
        raise RuntimeError(f"no route for {url}")


# ── Discovery and locality ──────────────────────────────────────────────────


def test_it_finds_the_installed_qwen_variants_and_keeps_them_local() -> None:
    transport = Transport(**{":60407": jan_listing(QWEN_NORMAL, QWEN_UNCENSORED, QWEN_IQ4)})
    snapshot = discover_local_runtimes([JAN], fetch_json=transport)

    found = {m.id: m for m in snapshot.models}
    assert set(found) == {QWEN_NORMAL, QWEN_UNCENSORED, QWEN_IQ4}
    assert all(m.locality == "local" for m in snapshot.models)
    assert all(snapshot.status_of(m) == "available" for m in found)


def test_a_loopback_entry_the_runtime_does_not_claim_is_not_local() -> None:
    """The endpoint is on 127.0.0.1, so the process is local. The data is not."""

    payload = {
        "data": [
            {"id": "qwen3-4b", "owned_by": "llamacpp"},
            {"id": "qwen3.8-27b-fp8", "owned_by": "remote"},
        ]
    }
    snapshot = discover_local_runtimes([JAN], fetch_json=Transport(**{":60407": payload}))
    found = {m.id: m for m in snapshot.models}
    assert found["qwen3-4b"].locality == "local"
    assert found["qwen3.8-27b-fp8"].locality == "remote"


def test_ollama_hosted_tags_are_never_local() -> None:
    transport = Transport(
        **{":11434": ollama_tags(("qwen3:4b", False), ("glm-5.2:cloud", True))}
    )
    snapshot = discover_local_runtimes([OLLAMA], fetch_json=transport)
    found = {m.id: m for m in snapshot.models}
    assert found["qwen3:4b"].locality == "local"
    assert found["glm-5.2:cloud"].locality == "remote"


def test_a_runtime_without_declared_identity_claims_nothing() -> None:
    """Without an identity to compare against, ownership cannot be proven."""

    undeclared = LocalRuntimeEndpoint(
        name="mystery", base_url="http://127.0.0.1:9999/v1", own_identities=frozenset()
    )
    payload = {"data": [{"id": "something", "owned_by": "whatever"}]}
    snapshot = discover_local_runtimes([undeclared], fetch_json=Transport(**{":9999": payload}))
    assert [m.locality for m in snapshot.models] == ["remote"]


# ── Lifecycle ───────────────────────────────────────────────────────────────


def test_a_runtime_that_is_offline_keeps_its_models_and_says_so() -> None:
    healthy = Transport(**{":60407": jan_listing(QWEN_NORMAL, QWEN_UNCENSORED)})
    first = discover_local_runtimes([JAN], fetch_json=healthy)
    assert len(first.models) == 2

    dead = Transport(**{":60407": RuntimeError("ECONNREFUSED")})
    second = discover_local_runtimes([JAN], previous=first, fetch_json=dead)

    assert {m.id for m in second.models} == {QWEN_NORMAL, QWEN_UNCENSORED}
    assert second.runtime_states["jan-llamacpp"] == "unreachable"
    assert all(second.status_of(m.id) == "offline" for m in second.models)
    assert all(m.locality == "local" for m in second.models)


def test_one_empty_answer_does_not_erase_a_known_catalog() -> None:
    healthy = Transport(**{":60407": jan_listing(QWEN_NORMAL, QWEN_UNCENSORED)})
    first = discover_local_runtimes([JAN], fetch_json=healthy)

    # A runtime that is still starting answers with an empty body.
    blank = Transport(**{":60407": {"object": "list", "data": []}})
    second = discover_local_runtimes([JAN], previous=first, fetch_json=blank)

    assert len(second.models) == 2, "a single empty answer must not retire anything"
    assert second.status_of(QWEN_NORMAL) == "error"


def test_a_confirmed_absence_does_retire_the_model() -> None:
    healthy = Transport(**{":60407": jan_listing(QWEN_NORMAL, QWEN_UNCENSORED)})
    snapshot = discover_local_runtimes([JAN], fetch_json=healthy)

    # The user uninstalls exactly one variant.
    reduced = Transport(**{":60407": jan_listing(QWEN_NORMAL)})
    after_one = discover_local_runtimes([JAN], previous=snapshot, fetch_json=reduced)
    assert len(after_one.models) == 2, "absence is not confirmed on the first miss"

    after_two = discover_local_runtimes([JAN], previous=after_one, fetch_json=reduced)
    assert [m.id for m in after_two.models] == [QWEN_NORMAL]
    assert after_two.absences[QWEN_UNCENSORED] >= ABSENCE_CONFIRMATIONS


def test_a_model_that_comes_back_is_listed_again_as_usable() -> None:
    healthy = Transport(**{":60407": jan_listing(QWEN_NORMAL, QWEN_UNCENSORED)})
    snapshot = discover_local_runtimes([JAN], fetch_json=healthy)

    reduced = Transport(**{":60407": jan_listing(QWEN_NORMAL)})
    gone = discover_local_runtimes([JAN], previous=snapshot, fetch_json=reduced)
    gone = discover_local_runtimes([JAN], previous=gone, fetch_json=reduced)
    assert len(gone.models) == 1

    returned = discover_local_runtimes([JAN], previous=gone, fetch_json=healthy)
    assert {m.id for m in returned.models} == {QWEN_NORMAL, QWEN_UNCENSORED}
    assert returned.status_of(QWEN_UNCENSORED) == "available"


def test_a_runtime_restarting_survives_a_down_up_cycle() -> None:
    transport = Transport(**{":60407": jan_listing(QWEN_NORMAL)})
    up = discover_local_runtimes([JAN], fetch_json=transport)

    down = Transport(**{":60407": RuntimeError("ECONNREFUSED")})
    fallen = discover_local_runtimes([JAN], previous=up, fetch_json=down)
    assert fallen.status_of(QWEN_NORMAL) == "offline"

    back = Transport(**{":60407": jan_listing(QWEN_NORMAL)})
    risen = discover_local_runtimes([JAN], previous=fallen, fetch_json=back)
    assert risen.status_of(QWEN_NORMAL) == "available"


def test_switching_local_to_cloud_to_local_keeps_both_facts() -> None:
    jan = Transport(**{":60407": jan_listing(QWEN_NORMAL)})
    oll = Transport(**{":11434": ollama_tags(("qwen3:4b", False), ("glm-5.2:cloud", True))})

    local_only = discover_local_runtimes([JAN], fetch_json=jan)
    assert {m.id for m in local_only.local_models()} == {QWEN_NORMAL}

    both = discover_local_runtimes([JAN, OLLAMA], previous=local_only, fetch_json=lambda u, h: jan(u, h) if "60407" in u else oll(u, h))
    local_ids = {m.id for m in both.local_models()}
    assert QWEN_NORMAL in local_ids
    assert "qwen3:4b" in local_ids
    assert "glm-5.2:cloud" not in local_ids

    back_to_local = discover_local_runtimes([JAN], previous=both, fetch_json=lambda u, h: jan(u, h) if "60407" in u else oll(u, h))
    assert QWEN_NORMAL in {m.id for m in back_to_local.local_models()}


def test_one_runtime_failing_never_touches_another() -> None:
    transport = lambda u, h: (  # noqa: E731
        RuntimeError("ECONNREFUSED") if "60407" in u else ollama_tags(("qwen3:4b", False))
    )
    snapshot = discover_local_runtimes([JAN, OLLAMA], fetch_json=transport)

    assert snapshot.runtime_states["jan-llamacpp"] == "unreachable"
    assert snapshot.runtime_states["ollama"] == "available"
    assert [m.id for m in snapshot.models] == ["qwen3:4b"]


def test_removing_a_runtime_from_the_declaration_drops_its_models() -> None:
    """An explicit removal is a real removal, not an absence to confirm."""

    transport = lambda u, h: (  # noqa: E731
        jan_listing(QWEN_NORMAL) if "60407" in u else ollama_tags(("qwen3:4b", False))
    )
    both = discover_local_runtimes([JAN, OLLAMA], fetch_json=transport)
    assert len(both.models) == 2

    only_jan = discover_local_runtimes([JAN], previous=both, fetch_json=transport)
    assert [m.id for m in only_jan.models] == [QWEN_NORMAL]


# ── Persistence ─────────────────────────────────────────────────────────────


def test_a_snapshot_survives_a_process_restart(tmp_path) -> None:
    path = tmp_path / "catalog.json"
    transport = Transport(**{":60407": jan_listing(QWEN_NORMAL, QWEN_UNCENSORED)})
    snapshot = discover_local_runtimes([JAN], fetch_json=transport)
    store_snapshot(snapshot, path)

    # A new process starts while the runtime is down.
    revived = load_snapshot(path)
    assert {m.id for m in revived.models} == {QWEN_NORMAL, QWEN_UNCENSORED}

    dead = Transport(**{":60407": RuntimeError("ECONNREFUSED")})
    after_restart = discover_local_runtimes([JAN], previous=revived, fetch_json=dead)
    assert len(after_restart.models) == 2
    assert after_restart.status_of(QWEN_NORMAL) == "offline"


def test_a_confirmed_absence_is_still_confirmed_after_a_restart(tmp_path) -> None:
    path = tmp_path / "catalog.json"
    transport = Transport(**{":60407": jan_listing(QWEN_NORMAL, QWEN_UNCENSORED)})
    snapshot = discover_local_runtimes([JAN], fetch_json=transport)
    store_snapshot(snapshot, path)

    reduced = Transport(**{":60407": jan_listing(QWEN_NORMAL)})
    once = discover_local_runtimes([JAN], previous=load_snapshot(path), fetch_json=reduced)
    store_snapshot(once, path)

    # Restart between the two confirmations: the counter must not reset.
    twice = discover_local_runtimes([JAN], previous=load_snapshot(path), fetch_json=reduced)
    assert [m.id for m in twice.models] == [QWEN_NORMAL]


def test_a_corrupt_state_file_is_an_empty_catalog_not_a_failure(tmp_path) -> None:
    path = tmp_path / "catalog.json"
    path.write_text("{not json", encoding="utf-8")
    assert load_snapshot(path).models == ()


def test_the_state_file_is_written_atomically(tmp_path) -> None:
    path = tmp_path / "nested" / "catalog.json"
    transport = Transport(**{":60407": jan_listing(QWEN_NORMAL)})
    store_snapshot(discover_local_runtimes([JAN], fetch_json=transport), path)
    assert path.exists()
    assert json.loads(path.read_text(encoding="utf-8"))["models"]
    assert not list(path.parent.glob("*.tmp"))


def test_the_default_state_path_is_machine_local(monkeypatch) -> None:
    monkeypatch.delenv("CMM_LOCAL_RUNTIME_STATE_PATH", raising=False)
    assert "Application Support" in str(state_path())


# ── Declaration ─────────────────────────────────────────────────────────────


def test_no_declared_runtimes_is_a_valid_configuration() -> None:
    assert load_endpoints("") == ()
    assert load_endpoints("[]") == ()
    assert discover_local_runtimes([]).models == ()


def test_the_declaration_names_runtimes_and_never_model_ids() -> None:
    parsed = load_endpoints(
        json.dumps(
            [
                {
                    "name": "Jan-LlamaCPP",
                    "baseUrl": "http://127.0.0.1:60407/v1/",
                    "ownIdentities": ["llamacpp"],
                }
            ]
        )
    )
    assert len(parsed) == 1
    assert parsed[0].name == "jan-llamacpp"
    assert parsed[0].base_url == "http://127.0.0.1:60407/v1"
    assert parsed[0].own_identities == frozenset({"llamacpp"})
    assert not hasattr(parsed[0], "model_ids")


def test_a_malformed_declaration_fails_closed() -> None:
    with pytest.raises(ValueError):
        load_endpoints("{not json")
    with pytest.raises(ValueError):
        load_endpoints(json.dumps([{"name": "x"}]))
    with pytest.raises(ValueError):
        load_endpoints(json.dumps([{"name": "x", "baseUrl": "http://h", "protocol": "grpc"}]))
