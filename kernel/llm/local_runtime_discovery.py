"""Discovery and lifecycle for real on-device model runtimes.

The canonical composition registers a small set of declared lanes, and the local
one used to
be an explicit list of model ids written by the launcher.  That design cannot
describe a machine: the ids went stale the moment a model was installed, and a
runtime that was down was never even asked, so its models silently disappeared
from the catalog while the rest of the product carried on.

This module replaces the id list with **runtime discovery**.  A launcher
declares which local runtimes exist and which wire they speak; the runtimes
themselves say which models they hold.  Three properties matter and are
enforced here rather than left to each call site:

*Truthfulness of locality.*  A model is ``local`` only when the runtime itself
says the weights are on this machine.  A loopback endpoint proves where the
process is, never where the context goes, so a runtime that fronts hosted
upstreams — a proxy, or a tag the runtime marks as hosted — is reported as
``remote`` even though it answers on 127.0.0.1.

*Truthfulness of identity.*  A model is identified by the runtime's own name
for it.  Nothing here reconstructs a name from an id, and no table of known
models exists: adding a model to the catalog is a matter of installing it.

*Survival of transient failure.*  Discovery runs against a persisted
last-known snapshot.  A runtime that is restarting, or that answers with an
empty body, keeps its models with a truthful status; only a *confirmed*
absence retires a descriptor.  The difference between "not running right now"
and "uninstalled" is real, and one sample cannot tell them apart, so removal is
confirmed before it is acted on.
"""

from __future__ import annotations

import json
import os
import tempfile
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

__all__ = [
    "LOCAL_RUNTIME_ENDPOINTS_ENV",
    "LOCAL_RUNTIME_STATE_PATH_ENV",
    "LocalRuntimeEndpoint",
    "LocalRuntimeModel",
    "LocalRuntimeSnapshot",
    "discover_local_runtimes",
    "discover_local_runtimes_throttled",
    "load_endpoints",
    "load_snapshot",
    "store_snapshot",
]

#: Launcher declaration of the local runtimes that exist on this machine.  The
#: value is a JSON array of endpoint objects; see :func:`load_endpoints`.  It
#: declares *runtimes*, never model ids, so a newly installed model is visible
#: without editing configuration.
LOCAL_RUNTIME_ENDPOINTS_ENV = "CMM_LOCAL_RUNTIME_ENDPOINTS_JSON"

#: Where the last-known catalog is persisted, so a restart of this process does
#: not erase the identity of a model that is still installed.
LOCAL_RUNTIME_STATE_PATH_ENV = "CMM_LOCAL_RUNTIME_STATE_PATH"

#: Default state location.  Kept beside the product's other machine-local state
#: rather than in the working directory, so it is not lost to a `cd`.
_DEFAULT_STATE_PATH = Path.home() / "Library" / "Application Support" / "CMM" / "local-runtime-catalog.json"

#: How many consecutive successful discoveries must report a model as absent
#: before that model is retired.  A runtime that is still starting, or that
#: answers an empty body while it swaps a model in, is indistinguishable from
#: one that was uninstalled after a single sample.
ABSENCE_CONFIRMATIONS = 2

#: A discovery is retried no more often than this, so a hot catalog read cannot
#: turn into a stream of runtime spawns.
MIN_REFRESH_INTERVAL_SECONDS = 15.0

#: Bounded per-probe timeout.  A local runtime that has wedged must not hold
#: the product's catalog hostage.
PROBE_TIMEOUT_SECONDS = 4.0

RuntimeProtocol = Literal["openai", "ollama"]

#: The lifecycle a selector must be able to distinguish.  ``available`` and the
#: rest are all "this model exists"; they differ in whether it can be used now.
ModelStatus = Literal["available", "starting", "offline", "unavailable", "error"]


@dataclass(frozen=True, slots=True)
class LocalRuntimeEndpoint:
    """One declared local runtime.

    ``own_identities`` is the set of names the runtime uses for **itself** in a
    listing.  A model whose declared owner is one of these is served by weights
    on this machine; any other owner is an upstream the runtime forwards to, and
    is therefore not local.  Declaring the runtime's own identity is a fact
    about the runtime, not an inventory of models.
    """

    name: str
    base_url: str
    protocol: RuntimeProtocol = "openai"
    own_identities: frozenset[str] = frozenset()
    api_key_env: str | None = None
    enabled: bool = True
    #: The OpenAI-compatible root used to *invoke* this runtime.
    #:
    #: It is a separate field because discovery and inference are not always
    #: served from the same root. Ollama answers its native API — the one that
    #: actually reports a model's size, quantisation and hosted tags — at the
    #: bare port, and its OpenAI-compatible chat at ``<root>/v1``. Using the
    #: discovery root for chat would post to a path that does not exist and fail
    #: every request against a model the catalog had just listed as available.
    chat_base_url: str | None = None

    def __post_init__(self) -> None:
        normalized = self.name.strip().lower()
        if not normalized:
            raise ValueError("A local runtime endpoint needs a name")
        object.__setattr__(self, "name", normalized)

        base = self.base_url.strip().rstrip("/")
        if not base:
            raise ValueError(f"Local runtime {self.name!r} needs a base URL")
        object.__setattr__(self, "base_url", base)

        if self.protocol not in ("openai", "ollama"):
            raise ValueError(
                f"Local runtime {self.name!r} has unsupported protocol {self.protocol!r}"
            )
        object.__setattr__(
            self, "own_identities", frozenset(i.strip().lower() for i in self.own_identities if i.strip())
        )

        if self.chat_base_url is not None:
            chat = self.chat_base_url.strip().rstrip("/")
            if not chat:
                raise ValueError(f"Local runtime {self.name!r} has a blank chat base URL")
            object.__setattr__(self, "chat_base_url", chat)

    @property
    def provider_base_url(self) -> str:
        """The root the chat transport must address.

        For a runtime whose discovery is already OpenAI-compatible the two
        roots are the same. For a runtime with a separate native discovery API
        the OpenAI-compatible root sits under it, which is the documented layout
        of that protocol rather than a per-model assumption.
        """

        if self.chat_base_url:
            return self.chat_base_url
        if self.protocol == "ollama":
            return f"{self.base_url}/v1"
        return self.base_url


@dataclass(frozen=True, slots=True)
class LocalRuntimeModel:
    """One model a local runtime says it holds, with its real egress class."""

    id: str
    runtime: str
    display_name: str
    locality: Literal["local", "remote"]
    vendor: str | None = None
    version: str | None = None
    context_window: int | None = None
    size_bytes: int | None = None
    parameters: str | None = None
    quantization: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "id", self.id.strip())
        object.__setattr__(self, "runtime", self.runtime.strip().lower())
        object.__setattr__(self, "display_name", self.display_name.strip() or self.id.strip())
        if self.locality not in ("local", "remote"):
            raise ValueError(f"Locality must be 'local' or 'remote', got {self.locality!r}")


@dataclass(frozen=True, slots=True)
class LocalRuntimeSnapshot:
    """The reconciled catalog: what is installed, and what can be used now."""

    models: tuple[LocalRuntimeModel, ...] = ()
    statuses: Mapping[str, ModelStatus] = field(default_factory=dict)
    runtime_states: Mapping[str, str] = field(default_factory=dict)
    #: Consecutive discoveries that did not report a previously known model.
    #: Persisted so a confirmed removal is still a confirmed removal after a
    #: restart, rather than silently resetting to "seen once".
    absences: Mapping[str, int] = field(default_factory=dict)
    last_refresh_at: float = 0.0
    last_success_at: float | None = None

    def status_of(self, model_id: str) -> ModelStatus:
        return self.statuses.get(model_id, "available")

    def local_models(self) -> tuple[LocalRuntimeModel, ...]:
        return tuple(m for m in self.models if m.locality == "local")


# ── Declaration ─────────────────────────────────────────────────────────────


def load_endpoints(raw: str | None = None) -> tuple[LocalRuntimeEndpoint, ...]:
    """Parse the launcher's declaration of local runtimes.

    Absent or empty means "no local runtime is declared", which is a valid
    configuration and not an error: the product then has no on-device lane
    rather than an invented one.
    """

    text = raw if raw is not None else os.getenv(LOCAL_RUNTIME_ENDPOINTS_ENV, "")
    text = text.strip()
    if not text:
        return ()
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError as error:
        raise ValueError(
            f"{LOCAL_RUNTIME_ENDPOINTS_ENV} is not valid JSON"
        ) from error
    if not isinstance(parsed, list):
        raise ValueError(f"{LOCAL_RUNTIME_ENDPOINTS_ENV} must be a JSON array")

    endpoints: list[LocalRuntimeEndpoint] = []
    for entry in parsed:
        if not isinstance(entry, dict):
            raise ValueError(f"{LOCAL_RUNTIME_ENDPOINTS_ENV} entries must be objects")
        name = entry.get("name")
        base_url = entry.get("baseUrl") or entry.get("base_url")
        if not isinstance(name, str) or not isinstance(base_url, str):
            raise ValueError(
                f"{LOCAL_RUNTIME_ENDPOINTS_ENV} entries need a string 'name' and 'baseUrl'"
            )
        identities = entry.get("ownIdentities") or entry.get("own_identities") or []
        if not isinstance(identities, list) or not all(isinstance(i, str) for i in identities):
            raise ValueError(
                f"{LOCAL_RUNTIME_ENDPOINTS_ENV} 'ownIdentities' must be a list of strings"
            )
        protocol = entry.get("protocol", "openai")
        endpoints.append(
            LocalRuntimeEndpoint(
                name=name,
                base_url=base_url,
                protocol=protocol,
                own_identities=frozenset(identities),
                api_key_env=entry.get("apiKeyEnv") or entry.get("api_key_env"),
                enabled=bool(entry.get("enabled", True)),
                chat_base_url=entry.get("chatBaseUrl") or entry.get("chat_base_url"),
            )
        )
    return tuple(endpoints)


# ── Probing ─────────────────────────────────────────────────────────────────


def _declared_version(value: str | None) -> str | None:
    """The version a runtime's own metadata states, or ``None``.

    Read from a field the runtime sets for exactly that purpose.  A name is
    never mined for digits: a family such as a size or a quantisation token is
    not a version, and inventing one would be a product claim nobody made.
    """

    if not isinstance(value, str):
        return None
    text = value.strip()
    return text or None


def _classify(owner: str | None, endpoint: LocalRuntimeEndpoint) -> Literal["local", "remote"]:
    """Decide whether a listed model is served from this machine.

    The runtime's own identity list is the authority.  An owner outside it is
    an upstream the runtime forwards to, so the model is remote no matter how
    local the endpoint is.  When the runtime declares its own identity list,
    an owner it does not name is therefore unknown-but-not-ours, and is
    reported as remote: claiming "on this Mac" for a model whose weights we
    cannot see is the failure this classification exists to prevent.
    """

    if not endpoint.own_identities:
        # Without a declared identity the runtime cannot prove ownership, so
        # the only honest classification is the conservative one.
        return "remote"
    if owner is None:
        return "remote"
    return "local" if owner.strip().lower() in endpoint.own_identities else "remote"


def _probe_openai(
    endpoint: LocalRuntimeEndpoint,
    fetch_json: Callable[[str, Mapping[str, str]], Any],
) -> list[LocalRuntimeModel]:
    payload = fetch_json(f"{endpoint.base_url}/models", _headers(endpoint))
    data = payload.get("data") if isinstance(payload, Mapping) else None
    if not isinstance(data, list):
        raise ValueError("listing had no data array")

    models: list[LocalRuntimeModel] = []
    for item in data:
        if not isinstance(item, Mapping):
            continue
        model_id = item.get("id")
        if not isinstance(model_id, str) or not model_id.strip():
            continue
        owner = item.get("owned_by")
        models.append(
            LocalRuntimeModel(
                id=model_id,
                runtime=endpoint.name,
                display_name=_string_or(item.get("display_name"), model_id),
                locality=_classify(owner if isinstance(owner, str) else None, endpoint),
                vendor=owner.strip() if isinstance(owner, str) and owner.strip() else None,
                version=_declared_version(item.get("version")),
                context_window=_positive_int(item.get("context_window")),
            )
        )
    return models


def _probe_ollama(
    endpoint: LocalRuntimeEndpoint,
    fetch_json: Callable[[str, Mapping[str, str]], Any],
) -> list[LocalRuntimeModel]:
    payload = fetch_json(f"{endpoint.base_url}/api/tags", _headers(endpoint))
    entries = payload.get("models") if isinstance(payload, Mapping) else None
    if not isinstance(entries, list):
        raise ValueError("listing had no models array")

    models: list[LocalRuntimeModel] = []
    for item in entries:
        if not isinstance(item, Mapping):
            continue
        name = item.get("name") or item.get("model")
        if not isinstance(name, str) or not name.strip():
            continue
        details = item.get("details")
        details = details if isinstance(details, Mapping) else {}
        # A hosted tag is the runtime telling us the weights are not here. It
        # says so two ways: an explicit remote host, and the cloud tag suffix.
        remote_host = item.get("remote_host") or item.get("remoteHost")
        hosted = bool(remote_host) or name.strip().lower().endswith(":cloud")
        size = item.get("size")
        models.append(
            LocalRuntimeModel(
                id=name,
                runtime=endpoint.name,
                display_name=_string_or(item.get("name"), name),
                locality="remote" if hosted else _classify("ollama", endpoint),
                vendor="ollama",
                version=_declared_version(item.get("version")),
                context_window=_positive_int(item.get("context_length") or details.get("context_length")),
                size_bytes=_positive_int(size),
                parameters=_string_or(details.get("parameter_size"), None),
                quantization=_string_or(details.get("quantization_level"), None),
            )
        )
    return models


def _headers(endpoint: LocalRuntimeEndpoint) -> dict[str, str]:
    headers = {"Accept": "application/json"}
    if endpoint.api_key_env:
        secret = os.getenv(endpoint.api_key_env, "").strip()
        if secret:
            # A loopback runtime usually ignores this, but the OpenAI-compatible
            # transport requires a non-empty bearer, so the launcher supplies a
            # placeholder through the declared variable.
            headers["Authorization"] = f"Bearer {secret}"
    return headers


def _string_or(value: Any, fallback: str | None) -> str | None:
    if isinstance(value, str) and value.strip():
        return value.strip()
    return fallback


def _positive_int(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int) and value > 0:
        return value
    if isinstance(value, str):
        try:
            parsed = int(value)
        except ValueError:
            return None
        return parsed if parsed > 0 else None
    return None


# ── Reconciliation ──────────────────────────────────────────────────────────


def _reconcile(
    previous: LocalRuntimeSnapshot,
    discovered: Mapping[str, LocalRuntimeModel],
    runtime_states: Mapping[str, str],
    absences: Mapping[str, int],
) -> LocalRuntimeSnapshot:
    """Merge one discovery result into the last known catalog.

    A model that was present and is now missing is not retired on the first
    miss; it is marked and only removed once absence has been confirmed.  A
    runtime that failed entirely keeps everything it previously contributed.
    """

    now = time.time()
    models: list[LocalRuntimeModel] = []
    statuses: dict[str, ModelStatus] = {}
    last_success = previous.last_success_at
    any_runtime_answered = False

    for model_id, model in discovered.items():
        any_runtime_answered = True
        models.append(model)
        statuses[model_id] = _status_for(model, runtime_states.get(model.runtime, "available"))

    # Retain models this discovery did not report.
    for model in previous.models:
        if model.id in discovered:
            continue
        if model.runtime not in runtime_states:
            # The runtime is no longer declared at all: an explicit removal
            # by the launcher, which is a real removal and not an absence.
            continue
        if absences.get(model.id, 0) >= ABSENCE_CONFIRMATIONS:
            # Absence has now been confirmed; the model really is gone.
            continue
        models.append(model)
        statuses[model.id] = "offline" if runtime_states[model.runtime] == "unreachable" else "error"

    return LocalRuntimeSnapshot(
        models=tuple(sorted(models, key=lambda m: (m.runtime, m.id))),
        statuses=statuses,
        runtime_states=dict(runtime_states),
        absences=dict(absences),
        last_refresh_at=now,
        last_success_at=now if any_runtime_answered else last_success,
    )


def _status_for(model: LocalRuntimeModel, runtime_state: str) -> ModelStatus:
    if runtime_state == "unreachable":
        return "offline"
    if runtime_state == "error":
        return "error"
    return "available"


def discover_local_runtimes(
    endpoints: Sequence[LocalRuntimeEndpoint],
    *,
    previous: LocalRuntimeSnapshot | None = None,
    fetch_json: Callable[[str, Mapping[str, str]], Any] | None = None,
) -> LocalRuntimeSnapshot:
    """Probe every declared runtime and reconcile the result.

    ``fetch_json`` is the injection seam for tests; production uses a bounded
    loopback HTTP read.  A runtime that cannot be reached never removes
    anything: its previous models are retained and marked ``offline``.
    """

    prior = previous or LocalRuntimeSnapshot()
    probe = fetch_json or _default_fetch_json
    absence_counts = dict(prior.absences)
    reported_any: set[str] = set()

    discovered: dict[str, LocalRuntimeModel] = {}
    runtime_states: dict[str, str] = {}

    for endpoint in endpoints:
        if not endpoint.enabled:
            continue
        try:
            found = (
                _probe_ollama(endpoint, probe)
                if endpoint.protocol == "ollama"
                else _probe_openai(endpoint, probe)
            )
        except Exception:  # noqa: BLE001 - any runtime defect is one state
            # An unreachable runtime removes nothing: every model it
            # contributed keeps its identity and is marked offline.
            runtime_states[endpoint.name] = "unreachable"
            reported_any.update(
                m.id for m in prior.models if m.runtime == endpoint.name
            )
            continue

        runtime_states[endpoint.name] = "available"
        seen_here: set[str] = set()
        for model in found:
            discovered[model.id] = model
            seen_here.add(model.id)
            reported_any.add(model.id)
            absence_counts.pop(model.id, None)
        for model in prior.models:
            if model.runtime == endpoint.name and model.id not in seen_here:
                absence_counts[model.id] = absence_counts.get(model.id, 0) + 1

    return _reconcile(prior, discovered, runtime_states, absence_counts)


# ── Persistence ─────────────────────────────────────────────────────────────


def state_path() -> Path:
    override = os.getenv(LOCAL_RUNTIME_STATE_PATH_ENV, "").strip()
    return Path(override).expanduser() if override else _DEFAULT_STATE_PATH


def load_snapshot(path: Path | None = None) -> LocalRuntimeSnapshot:
    """Read the last known catalog.

    A missing or unreadable state file is an empty catalog, not a failure: the
    first ever run has nothing to retain, and a corrupt file must not take the
    product down.
    """

    target = path or state_path()
    try:
        raw = target.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return LocalRuntimeSnapshot()
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return LocalRuntimeSnapshot()
    if not isinstance(parsed, Mapping):
        return LocalRuntimeSnapshot()

    models: list[LocalRuntimeModel] = []
    for entry in parsed.get("models", []) or []:
        if not isinstance(entry, Mapping):
            continue
        try:
            models.append(
                LocalRuntimeModel(
                    id=str(entry["id"]),
                    runtime=str(entry["runtime"]),
                    display_name=str(entry.get("display_name") or entry["id"]),
                    locality="local" if entry.get("locality") == "local" else "remote",
                    vendor=entry.get("vendor"),
                    version=entry.get("version"),
                    context_window=_positive_int(entry.get("context_window")),
                    size_bytes=_positive_int(entry.get("size_bytes")),
                    parameters=entry.get("parameters"),
                    quantization=entry.get("quantization"),
                )
            )
        except (KeyError, ValueError):
            continue

    statuses = parsed.get("statuses")
    runtime_states = parsed.get("runtime_states")
    absences = parsed.get("absences")
    last_success = parsed.get("last_success_at")
    return LocalRuntimeSnapshot(
        models=tuple(models),
        statuses={str(k): str(v) for k, v in statuses.items()} if isinstance(statuses, Mapping) else {},
        runtime_states={str(k): str(v) for k, v in runtime_states.items()} if isinstance(runtime_states, Mapping) else {},
        absences={str(k): int(v) for k, v in absences.items()} if isinstance(absences, Mapping) else {},
        last_refresh_at=float(parsed.get("last_refresh_at") or 0.0),
        last_success_at=float(last_success) if isinstance(last_success, (int, float)) else None,
    )


def store_snapshot(snapshot: LocalRuntimeSnapshot, path: Path | None = None) -> None:
    """Persist the reconciled catalog so the next process starts informed."""

    target = path or state_path()
    payload = {
        "last_refresh_at": snapshot.last_refresh_at,
        "last_success_at": snapshot.last_success_at,
        "runtime_states": dict(snapshot.runtime_states),
        "statuses": dict(snapshot.statuses),
        "absences": dict(snapshot.absences),
        "models": [
            {
                "id": m.id,
                "runtime": m.runtime,
                "display_name": m.display_name,
                "locality": m.locality,
                "vendor": m.vendor,
                "version": m.version,
                "context_window": m.context_window,
                "size_bytes": m.size_bytes,
                "parameters": m.parameters,
                "quantization": m.quantization,
            }
            for m in snapshot.models
        ],
    }
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        # Write-then-rename so a crash mid-write cannot leave a half file that
        # reads as "the catalog is empty".
        with tempfile.NamedTemporaryFile(
            "w", encoding="utf-8", dir=str(target.parent), delete=False, suffix=".tmp"
        ) as handle:
            json.dump(payload, handle, indent=2, sort_keys=True)
            handle.flush()
            os.fsync(handle.fileno())
            temporary = Path(handle.name)
        temporary.replace(target)
    except OSError:
        # Persistence is a convenience, never a correctness requirement: the
        # live discovery result is already in hand.
        return


def _default_fetch_json(url: str, headers: Mapping[str, str]) -> Any:
    """Bounded loopback HTTP read of one JSON document."""

    import urllib.error
    import urllib.request

    request = urllib.request.Request(url, headers=dict(headers), method="GET")
    try:
        with urllib.request.urlopen(request, timeout=PROBE_TIMEOUT_SECONDS) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        raise RuntimeError(f"local runtime returned HTTP {error.code}") from error
    except Exception as error:  # noqa: BLE001
        raise RuntimeError(f"local runtime unreachable: {type(error).__name__}") from error


#: Process-level memo of the last reconciliation, as ``(monotonic time,
#: snapshot)``.  Catalog reads are frequent and a probe per read would turn a
#: selector refresh into a stream of runtime calls, so discovery is throttled
#: rather than repeated.  The window is short enough that a model installed a
#: moment ago is still seen on the next refresh.
_THROTTLE: tuple[float, "LocalRuntimeSnapshot"] | None = None


def discover_local_runtimes_throttled(
    *,
    now: Callable[[], float] = time.monotonic,
) -> "LocalRuntimeSnapshot":
    """Reconcile the declared local runtimes at most once per refresh window.

    The reconciled result is persisted, so a process that starts while a
    runtime is down still presents the models that runtime holds.
    """

    global _THROTTLE
    moment = now()
    cached = _THROTTLE
    if cached is not None and moment - cached[0] < MIN_REFRESH_INTERVAL_SECONDS:
        return cached[1]

    snapshot = discover_local_runtimes(load_endpoints(), previous=load_snapshot())
    store_snapshot(snapshot)
    _THROTTLE = (moment, snapshot)
    return snapshot
