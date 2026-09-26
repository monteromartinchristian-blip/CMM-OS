"""The stable client facade over CMM OS model execution.

One import path, one version, one closed vocabulary.  A first-party client
imports :mod:`cmm.model_client` and nothing else: the provenance-checked loader,
the canonical composition and the capability facade all live behind this
facade, so no client ever touches ``cmm.model_execution`` internals or
``kernel.llm`` directly.

Capability truth is read from the canonical catalog projection and never
re-derived from a model or provider name.  Failures leave as
:class:`~cmm.model_client.contracts.ModelClientError` carrying a closed code;
the seam's own message is deliberately not part of the client contract, because
it may carry upstream detail a client must never forward.
"""

from __future__ import annotations

import logging
import os
import sys
import threading
from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from cmm.model_client.contracts import (
    ClientModelDescriptor,
    ClientResolvedModel,
    ClientStreamEvent,
    ClientStreamFacts,
    ModelClientError,
)

_logger = logging.getLogger(__name__)

AUTO_MODEL = "cmm-auto"

#: Seam codes that pass through unchanged: they are already closed and safe.
_PASSTHROUGH_CODES = frozenset(
    {
        "NO_MODELS_AVAILABLE",
        "MODEL_UNAVAILABLE",
        "PROVIDER_UNAVAILABLE",
        "PROVIDER_FAILURE",
        "CHAT_PROMPT_INVALID",
        "UNSUPPORTED_REASONING_EFFORT",
    }
)

#: Deeper canonical failure classes, matched by name so this boundary never
#: needs an eager import of the layers below it.
_CLASS_ERROR_CODES = {
    "ProviderError": "PROVIDER_FAILURE",
    "LLMError": "PROVIDER_FAILURE",
    "TimeoutError": "TIMEOUT",
}

_CAPABILITY_ERROR_CLASSES = frozenset({"WebCapabilityError", "ComputerUseError"})

_CAPABILITY_ERROR_CODES = frozenset(
    {
        "SEARCH_BACKEND_UNAVAILABLE",
        "SEARCH_TIMEOUT",
        "SEARCH_BLOCKED",
        "FETCH_FAILED",
        "SOURCE_BLOCKED",
        "COMPUTER_RUNTIME_UNAVAILABLE",
        "COMPUTER_PERMISSION_DENIED",
        "COMPUTER_TARGET_UNAVAILABLE",
        "ACTION_FAILED",
        "APPROVAL_REJECTED",
        "CAPABILITY_UNSUPPORTED",
        "CANCELLED",
        "TOOL_RUNTIME_ERROR",
    }
)

#: Emitted before the deltas of a visual turn that runs on the plain chat path,
#: so a capability the user enabled is never dropped without saying so.
CAPABILITY_DEGRADED_EVENT = "capability.degraded"


def _default_os_path() -> str:
    return os.environ.get("CMM_OS_PATH") or str(
        Path.home() / "CMM OS" / ".worktrees" / "cmmchat-wave-f-first-usable"
    )


def _obsolete_os_path() -> str:
    return os.environ.get("CMM_OBSOLETE_OS_PATH") or str(Path.home() / "CMM-OS")


@dataclass(frozen=True, slots=True)
class _Seam:
    """The canonical callables plus the proven-provenance source root."""

    build_local_model_execution: Any
    provider_registry_class: Any
    capability_execution_class: Any
    capability_request_class: Any
    image_input_class: Any
    source_root: str


#: Process-wide cache of the proven seam import.  Python caches failed package
#: lookups per interpreter, so the seam is imported exactly once, from the first
#: client whose provenance check passes.
_SEAM: _Seam | None = None


def normalize(error: BaseException) -> ModelClientError:
    """Map any seam failure onto the closed client vocabulary."""

    if isinstance(error, ModelClientError):
        return error
    if type(error).__name__ == "ModelExecutionError":
        code = getattr(error, "code", None)
        if isinstance(code, str) and code in _PASSTHROUGH_CODES:
            return ModelClientError(code, str(getattr(error, "message", error)))
    if type(error).__name__ in _CAPABILITY_ERROR_CLASSES:
        code = getattr(error, "code", None)
        if isinstance(code, str) and code in _CAPABILITY_ERROR_CODES:
            return ModelClientError(code, str(getattr(error, "message", error)))
        return ModelClientError("TOOL_RUNTIME_ERROR", str(error))
    for klass in type(error).__mro__:
        code = _CLASS_ERROR_CODES.get(klass.__name__)
        if code is not None:
            return ModelClientError(code, str(error))
    return ModelClientError("PROVIDER_FAILURE", str(error))


class ModelClient:
    """The one stable surface a first-party client uses for model execution."""

    def __init__(
        self,
        *,
        executor: Any | None = None,
        os_path: str | None = None,
        router_base_url: str | None = None,
    ) -> None:
        self._executor = executor
        self._os_path = os_path or _default_os_path()
        #: Loopback override for the CHAT_ONLY router lane, for tests and local
        #: E2E only.  ``None`` keeps the canonical pinned endpoint; the loopback
        #: rule still applies to any override.
        self._router_base_url = router_base_url
        self._lock = threading.Lock()
        self._facade: Any | None = None

    # ── Canonical loading ────────────────────────────────────────────────────

    def _seam(self) -> _Seam:
        """Import the canonical seam and prove where it was loaded from.

        The loaded root is derived from the imported module itself, never from
        the request, and must be exactly the configured source; a module that
        came from the obsolete clone fails the boundary closed.
        """

        global _SEAM
        expected_root = str(Path(self._os_path).resolve())
        if _SEAM is not None:
            if _SEAM.source_root != expected_root:
                raise ModelClientError(
                    "CMM_OS_UNAVAILABLE", "CMM OS is not reachable from this client."
                )
            return _SEAM

        if self._os_path not in sys.path:
            sys.path.insert(0, self._os_path)
        try:
            from cmm.capabilities import CapabilityExecution, CapabilityRequest
            from cmm.model_execution.composition import (
                build_local_model_execution,
            )
            from kernel.llm.models import ImageInput
            from kernel.llm.provider_registry import ProviderRegistry
        except Exception as error:
            raise ModelClientError(
                "CMM_OS_UNAVAILABLE", "CMM OS is not reachable from this client."
            ) from error

        composition = sys.modules[build_local_model_execution.__module__]
        source_root = str(Path(composition.__file__).resolve().parents[2])
        obsolete_root = str(Path(_obsolete_os_path()).resolve())

        offenders: list[str] = []
        obsolete_loaded: list[str] = []
        for name, module in list(sys.modules.items()):
            if not (
                name in {"cmm", "kernel"}
                or name.startswith("cmm.")
                or name.startswith("kernel.")
            ):
                continue
            module_file = getattr(module, "__file__", None)
            if module_file is None:
                continue
            resolved = str(Path(module_file).resolve())
            if resolved == obsolete_root or resolved.startswith(
                obsolete_root + os.sep
            ):
                obsolete_loaded.append(name)
            elif not resolved.startswith(expected_root + os.sep):
                offenders.append(name)
        if source_root != expected_root or obsolete_loaded or offenders:
            _logger.error(
                "CMM_OS_SOURCE_ROOT=%s OBSOLETE_CMM_OS_LOADED=%s offenders=%s",
                source_root,
                "YES" if obsolete_loaded else "NO",
                ",".join(sorted(set(obsolete_loaded + offenders)))
                or f"module:{source_root}",
            )
            raise ModelClientError(
                "CMM_OS_UNAVAILABLE", "CMM OS is not reachable from this client."
            )
        _logger.info(
            "CMM_OS_SOURCE_ROOT=%s OBSOLETE_CMM_OS_LOADED=NO", source_root
        )
        _SEAM = _Seam(
            build_local_model_execution=build_local_model_execution,
            provider_registry_class=ProviderRegistry,
            capability_execution_class=CapabilityExecution,
            capability_request_class=CapabilityRequest,
            image_input_class=ImageInput,
            source_root=source_root,
        )
        return _SEAM

    def _chat_executor(self) -> Any:
        """Return the composed canonical chat executor, building it once."""

        if self._executor is None:
            with self._lock:
                if self._executor is None:
                    seam = self._seam()
                    try:
                        built = seam.build_local_model_execution(
                            provider_registry=seam.provider_registry_class(),
                            base_url=self._router_base_url,
                        )
                    except Exception as error:
                        raise normalize(error) from error
                    self._executor = built.executor
        return self._executor

    def _capability_facade(self) -> Any:
        """Return the composed canonical capability facade, building it once."""

        if self._facade is None:
            # Built outside the lock: _chat_executor() takes the same lock and
            # it is not reentrant.
            executor = self._chat_executor()
            with self._lock:
                if self._facade is None:
                    seam = self._seam()
                    try:
                        self._facade = seam.capability_execution_class(
                            executor=executor
                        )
                    except Exception as error:
                        raise normalize(error) from error
        return self._facade

    # ── Client surface ───────────────────────────────────────────────────────

    def catalog(self) -> tuple[ClientModelDescriptor, ...]:
        """Return every routable model with its full capability truth."""

        try:
            models = self._chat_executor().catalog()
        except Exception as error:
            raise normalize(error) from error
        return tuple(
            ClientModelDescriptor(
                id=model.model_id,
                display_name=model.display_name,
                availability=model.availability,
                locality=model.locality,
                provider_id=model.provider_id,
                capabilities=dict(model.capabilities or {}),
                reasoning_efforts=tuple(model.reasoning_efforts or ()),
                document_media_types=tuple(model.document_media_types or ()),
                context_window=model.context_window,
                streaming=bool(model.streaming),
            )
            for model in models
        )

    def resolve(self, selection: str | None = None) -> ClientResolvedModel:
        """Resolve one selection against the canonical authorities."""

        requested = (selection or "").strip()
        try:
            resolved = self._chat_executor().resolve_chat(
                None if not requested or requested == AUTO_MODEL else requested
            )
        except Exception as error:
            raise normalize(error) from error
        model = resolved.model
        descriptor = self._descriptor_for(model.model_id)
        efforts = tuple(
            descriptor.reasoning_efforts if descriptor is not None else ()
        )
        documents = tuple(
            descriptor.document_media_types if descriptor is not None else ()
        )
        return ClientResolvedModel(
            model_id=model.model_id,
            display_name=model.display_name,
            locality=model.locality,
            policy=resolved.policy,
            handle=resolved,
            supports_capability_plane=bool(
                model.capabilities.get("tool_calling")
                or model.capabilities.get("structured_output")
            ),
            supports_vision=bool(model.capabilities.get("vision")),
            reasoning_efforts=efforts,
            document_media_types=documents,
            capabilities=dict(model.capabilities or {}),
        )

    def _descriptor_for(self, model_id: str) -> ClientModelDescriptor | None:
        try:
            declared = self.catalog()
        except Exception:  # noqa: BLE001 - an unreadable catalog must not disable
            return None
        for entry in declared:
            if entry.id == model_id:
                return entry
        return None

    def stream(
        self,
        resolved: ClientResolvedModel,
        *,
        prompt: str,
        system: str | None = None,
        history: Sequence[Mapping[str, str]] | None = None,
        images: Sequence[Mapping[str, Any]] | None = None,
        cancel_event: threading.Event | None = None,
        reasoning_effort: str = "default",
        facts_sink: Any | None = None,
    ) -> Iterator[str]:
        """Stream normalized content deltas for one resolved model."""

        try:
            image_inputs: tuple[Any, ...] = ()
            if images:
                seam = self._seam()
                image_inputs = tuple(
                    seam.image_input_class(
                        media_type=str(image["media_type"]),
                        data=image["data"],
                    )
                    for image in images
                )
            transcript = tuple(
                (turn["role"], turn["content"]) for turn in history or ()
            )

            def _facts(facts: Any) -> None:
                if facts_sink is not None:
                    facts_sink(
                        ClientStreamFacts(
                            requested_reasoning_effort=facts.requested_reasoning_effort,
                            effective_reasoning_effort=facts.effective_reasoning_effort,
                        )
                    )

            deltas = self._chat_executor().stream(
                resolved.handle,
                prompt=prompt,
                system=system,
                history=transcript,
                images=image_inputs,
                cancel_event=cancel_event,
                reasoning_effort=reasoning_effort,
                facts_sink=_facts if facts_sink is not None else None,
            )
        except Exception as error:
            raise normalize(error) from error
        return self._normalized_deltas(deltas)

    @staticmethod
    def _normalized_deltas(deltas: Iterator[str]) -> Iterator[str]:
        try:
            yield from deltas
        except Exception as error:
            raise normalize(error) from error

    def stream_with_capabilities(
        self,
        resolved: ClientResolvedModel,
        *,
        prompt: str,
        system: str | None = None,
        history: Sequence[Mapping[str, str]] | None = None,
        images: Sequence[Mapping[str, Any]] | None = None,
        cancel_event: threading.Event | None = None,
        reasoning_effort: str = "default",
        facts_sink: Any | None = None,
        capabilities: Mapping[str, Any] | None = None,
    ) -> Iterator[ClientStreamEvent]:
        """Stream normalized capability events for one product run.

        A visual turn runs on the plain chat path because the capability plane
        cannot carry image bytes; that downgrade is *declared* through a
        ``capability.degraded`` event instead of happening silently.
        """

        if images:
            def visual_events() -> Iterator[ClientStreamEvent]:
                yield ClientStreamEvent(
                    kind=CAPABILITY_DEGRADED_EVENT,
                    data={"reason": "visual_input"},
                )
                for delta in self.stream(
                    resolved,
                    prompt=prompt,
                    system=system,
                    history=history,
                    images=images,
                    cancel_event=cancel_event,
                    reasoning_effort=reasoning_effort,
                    facts_sink=facts_sink,
                ):
                    yield ClientStreamEvent(
                        kind="message.delta", data={"delta": delta}
                    )
                yield ClientStreamEvent(
                    kind="run.summary", data={"mode": "chat", "citations": []}
                )

            return visual_events()

        requested = dict(capabilities or {})
        web_search = requested.get("web_search", "off")
        computer_use = requested.get("computer_use", "off")
        if isinstance(computer_use, bool):
            computer_use = "on" if computer_use else "off"
        try:
            seam = self._seam()
            request = seam.capability_request_class(
                web_search=(
                    web_search if web_search in ("auto", "on", "off") else "off"
                ),
                computer_use=(
                    computer_use
                    if computer_use in ("auto", "on", "off")
                    else "off"
                ),
            )
            transcript = tuple(
                (turn["role"], turn["content"]) for turn in history or ()
            )
            events = self._capability_facade().stream(
                resolved.handle,
                prompt=prompt,
                system=system,
                history=transcript,
                cancel_event=cancel_event,
                capabilities=request,
            )
        except Exception as error:
            raise normalize(error) from error
        return self._normalized_events(events)

    @staticmethod
    def _normalized_events(events: Iterator[Any]) -> Iterator[ClientStreamEvent]:
        try:
            for event in events:
                yield ClientStreamEvent(kind=event.kind, data=dict(event.data or {}))
        except Exception as error:
            raise normalize(error) from error

    def resolve_approval(self, tool_run_id: str, decision: str) -> bool:
        """Deliver a product approval decision to the waiting capability."""

        try:
            return bool(
                self._capability_facade().resolve_approval(tool_run_id, decision)
            )
        except Exception as error:
            raise normalize(error) from error

    def capability_status(self) -> dict[str, Any]:
        """Normalized availability of the product capabilities."""

        try:
            return dict(self._capability_facade().capability_status())
        except Exception as error:
            raise normalize(error) from error
