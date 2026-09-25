"""Phase 11.21 — model gateway architecture and anti-fragmentation guards.

These guards freeze *ownership* before any behaviour exists.  They are
deliberately source-level checks: their job is to fail loudly if a later change
re-introduces a parallel authority (a second provider registry, model catalog,
routing policy engine, privacy engine, validation engine, tool executor,
conversation/session store or application backend) or smuggles an unsanctioned
capability (provider-name dispatch, UI/CMMChat coupling, arbitrary filesystem or
network loading, hidden reasoning) into the Model Gateway.

The canonical owners below are the already-closed Phase 11.34 / 11.1-11.5
authorities.  Phase 11.21 introduces exactly one new authority — provider
independent model-call normalization and execution — and must reuse these.
"""

from __future__ import annotations

import dataclasses
import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
PRODUCTION_ROOTS = ("kernel", "cmm", "cmm_agent")

GATEWAY_DIR = REPO_ROOT / "kernel" / "llm"
GATEWAY_MODULE_NAMES = (
    "model_gateway_contracts",
    "model_gateway_errors",
    "model_provider_adapter",
    "model_streaming",
    "model_gateway",
)
GATEWAY_MODULE_PATHS = tuple(
    GATEWAY_DIR / f"{name}.py" for name in GATEWAY_MODULE_NAMES
)

#: Canonical authority -> the one production module allowed to define it.
CANONICAL_AUTHORITIES = {
    "ProviderRegistry": "kernel/llm/provider_registry.py",
    "ProviderSpec": "kernel/llm/provider_registry.py",
    "ModelCatalog": "kernel/llm/model_catalog.py",
    "ModelRouter": "kernel/llm/model_router.py",
    "ModelRouteCatalog": "kernel/llm/model_routes.py",
    "ModelFallbackDecisionEngine": (
        "cmm/agent_runtime/model_fallback_decision_engine.py"
    ),
    "ModelFallbackPolicy": "cmm/agent_runtime/model_fallback_contracts.py",
    "ValidationApplicationService": "cmm/validation/interfaces/application.py",
    "ApplicationGateway": "cmm/application/gateway.py",
    "ConversationService": "cmm/conversation/service.py",
    "ExecutorRegistry": "cmm/execution/executor_registry.py",
}

#: Module files that must never appear: they would be parallel authorities.
FORBIDDEN_PARALLEL_MODULES = (
    "cmm/provider_registry.py",
    "cmm/model_catalog.py",
    "cmm/model_router.py",
    "cmm/model_runtime.py",
    "cmm/model_store.py",
    "cmm/model_event_bus.py",
    "cmm/model_validation_engine.py",
    "cmm/model_gateway_registry.py",
    "cmm/model_gateway_store.py",
    "cmm/model_gateway_event_bus.py",
    "kernel/llm/model_runtime.py",
    "kernel/llm/model_store.py",
    "kernel/llm/model_event_bus.py",
    "kernel/llm/model_validation_engine.py",
    "kernel/llm/model_gateway_registry.py",
    "kernel/llm/privacy.py",
    "kernel/llm/privacy_engine.py",
    "kernel/llm/validation_engine.py",
    "kernel/llm/tool_executor.py",
    "kernel/llm/conversation_store.py",
    "kernel/llm/session_store.py",
    "kernel/llm/artifact_store.py",
    "kernel/llm/file_store.py",
)

#: Provider-name dispatch inside the gateway core is prohibited: translation
#: belongs inside provider adapters, never in policy-free core code.
PROVIDER_DISPATCH_PATTERNS = (
    re.compile(r"provider(?:_id)?\s*==\s*[\"']"),
    re.compile(r"provider(?:_id)?\s*!=\s*[\"']"),
    re.compile(r"provider(?:_id)?\s+in\s+\{"),
    re.compile(r"elif\s+provider\b"),
    re.compile(r"model_id\.startswith\("),
    re.compile(r"startswith\(\s*[\"']gpt-"),
    re.compile(r"startswith\(\s*[\"']claude"),
    re.compile(r"startswith\(\s*[\"']qwen"),
    re.compile(r"startswith\(\s*[\"']ollama"),
    re.compile(r"[\"']vision[\"']\s+in\s+"),
    re.compile(r"[\"']image[\"']\s+in\s+model"),
)

#: Gateway core may not own arbitrary I/O or unconfined loading.
FORBIDDEN_GATEWAY_IMPORTS = (
    "socket",
    "urllib",
    "http.client",
    "requests",
    "httpx",
    "aiohttp",
    "ftplib",
    "smtplib",
    "subprocess",
    "shutil",
    "tempfile",
    "pathlib",
    "pickle",
    "importlib",
    "yaml",
    "os.path",
    "os.walk",
)

FORBIDDEN_OPEN_CALL = re.compile(r"(?<![\w.])open\s*\(")

#: Public gateway contracts may never carry hidden chain-of-thought.
FORBIDDEN_CONTRACT_FIELD_FRAGMENTS = (
    "chain_of_thought",
    "chainofthought",
    "cot_trace",
    "scratchpad",
    "hidden_reasoning",
    "raw_reasoning",
    "reasoning_trace",
    "internal_reasoning",
    "thinking",
    "thoughts",
)

#: Layers the gateway must not depend on.
FORBIDDEN_LAYER_IMPORTS = (
    "cmm.conversation",
    "cmm.application",
    "cmmchat",
    "cmm_chat",
    "cmm.bots",
    "tkinter",
    "PyQt",
    "PySide",
)


def _gateway_sources() -> dict[str, str]:
    missing = [str(path) for path in GATEWAY_MODULE_PATHS if not path.exists()]
    assert not missing, f"Phase 11.21 gateway modules are missing: {missing}"
    return {
        path.stem: path.read_text(encoding="utf-8") for path in GATEWAY_MODULE_PATHS
    }


def _production_python_files() -> tuple[Path, ...]:
    files: list[Path] = []
    for root in PRODUCTION_ROOTS:
        files.extend(sorted((REPO_ROOT / root).rglob("*.py")))
    return tuple(files)


def _strip_comments_and_docstrings(source: str) -> str:
    """Remove comments and string literals so scans read executable intent.

    Module and function docstrings legitimately *name* the prohibited concepts
    ("no chain-of-thought"); executable code must not contain them.  Analysis
    keeps line structure so a reported match still points at a real line.
    """

    without_docstrings = re.sub(
        r'"""(?:[^"\\]|\\.|"(?!""))*"""',
        '""',
        source,
    )
    without_docstrings = re.sub(
        r"'''(?:[^'\\]|\\.|'(?!''))*'''",
        "''",
        without_docstrings,
    )
    return re.sub(r"#[^\n]*", "", without_docstrings)


def test_gateway_modules_exist_and_reuse_canonical_authorities() -> None:
    """The gateway must depend on the canonical registry and catalog owners."""

    sources = _gateway_sources()
    joined = "\n".join(sources.values())

    assert "kernel.llm.provider_registry" in joined
    assert "kernel.llm.model_catalog" in joined
    assert "ProviderRegistry" in joined
    assert "ModelCatalog" in joined


def test_gateway_does_not_define_a_second_canonical_authority() -> None:
    sources = _gateway_sources()
    for name, source in sources.items():
        code = _strip_comments_and_docstrings(source)
        for authority in CANONICAL_AUTHORITIES:
            assert not re.search(rf"^class\s+{authority}\b", code, re.MULTILINE), (
                f"{name} must not redefine canonical authority {authority}"
            )


def test_gateway_has_no_provider_name_dispatch_chain() -> None:
    sources = _gateway_sources()
    for name, source in sources.items():
        code = _strip_comments_and_docstrings(source)
        for pattern in PROVIDER_DISPATCH_PATTERNS:
            match = pattern.search(code)
            assert match is None, (
                f"{name} contains provider-name dispatch {pattern.pattern!r}: "
                f"{match.group(0)!r}"
            )


def test_gateway_does_not_depend_on_conversation_application_or_ui() -> None:
    sources = _gateway_sources()
    for name, source in sources.items():
        code = _strip_comments_and_docstrings(source)
        for forbidden in FORBIDDEN_LAYER_IMPORTS:
            assert not re.search(
                rf"^\s*(?:from|import)\s+{re.escape(forbidden)}\b",
                code,
                re.MULTILINE,
            ), f"{name} must not import {forbidden}"
        assert "cmm." not in code, (
            f"{name} must stay below the cmm layer; canonical privacy is "
            "reached through an injected gate, not a kernel import"
        )


def test_gateway_owns_no_arbitrary_filesystem_or_network_loading() -> None:
    sources = _gateway_sources()
    for name, source in sources.items():
        code = _strip_comments_and_docstrings(source)
        for forbidden in FORBIDDEN_GATEWAY_IMPORTS:
            assert not re.search(
                rf"^\s*(?:from|import)\s+{re.escape(forbidden)}\b",
                code,
                re.MULTILINE,
            ), f"{name} must not import {forbidden}"
        assert FORBIDDEN_OPEN_CALL.search(code) is None, (
            f"{name} must not open filesystem paths"
        )


def test_gateway_adapter_layer_never_holds_provider_metadata() -> None:
    """The adapter registry resolves execution only — it is not a registry."""

    source = (GATEWAY_DIR / "model_provider_adapter.py").read_text(encoding="utf-8")
    assert "ProviderSpec" not in source, (
        "the adapter layer must not store provider metadata; provider identity "
        "belongs to kernel.llm.provider_registry.ProviderRegistry"
    )
    assert "ProviderRegistry" not in source


def test_no_parallel_authority_module_exists() -> None:
    offenders = [
        relative
        for relative in FORBIDDEN_PARALLEL_MODULES
        if (REPO_ROOT / relative).exists()
    ]
    assert offenders == [], f"parallel authorities introduced: {offenders}"


def test_no_cmm_module_is_named_after_the_gateway() -> None:
    """The gateway lives once, in ``kernel/llm``.

    This also preserves the closed Phase 10.51 guard, which rejects any ``cmm``
    module stem starting with ``model_gateway``.
    """

    offenders = sorted(
        str(path.relative_to(REPO_ROOT))
        for path in (REPO_ROOT / "cmm").rglob("*.py")
        if path.name.removesuffix(".py").startswith("model_gateway")
    )
    assert offenders == [], f"gateway must not be duplicated under cmm: {offenders}"


def test_canonical_authorities_have_exactly_one_definition() -> None:
    files = _production_python_files()
    offenders: dict[str, list[str]] = {}
    for authority, canonical in CANONICAL_AUTHORITIES.items():
        pattern = re.compile(rf"^class\s+{authority}\b", re.MULTILINE)
        found = {
            str(path.relative_to(REPO_ROOT))
            for path in files
            if pattern.search(path.read_text(encoding="utf-8"))
        }
        if found != {canonical}:
            offenders[authority] = sorted(found)
    assert offenders == {}, f"duplicate canonical authorities: {offenders}"


def test_single_canonical_privacy_engine() -> None:
    """Phase 11.21 reuses the cognitive privacy evaluator, never a second one."""

    pattern = re.compile(r"^def\s+evaluate_privacy_operation\b", re.MULTILINE)
    found = {
        str(path.relative_to(REPO_ROOT))
        for path in _production_python_files()
        if pattern.search(path.read_text(encoding="utf-8"))
    }
    assert found == {"cmm/cognitive/privacy.py"}

    for path in GATEWAY_MODULE_PATHS:
        code = _strip_comments_and_docstrings(path.read_text(encoding="utf-8"))
        assert "evaluate_privacy_operation" not in code, (
            f"{path.name} must delegate privacy to the canonical evaluator"
        )


def test_gateway_does_not_own_tool_execution_or_validation() -> None:
    for path in GATEWAY_MODULE_PATHS:
        code = _strip_comments_and_docstrings(path.read_text(encoding="utf-8"))
        assert "ExecutorRegistry" not in code
        assert "ValidationApplicationService" not in code
        for pattern in (
            r"def\s+execute_tool\b",
            r"def\s+invoke_tool\b",
            r"def\s+run_tool\b",
            r"def\s+validate_domain\b",
        ):
            assert re.search(pattern, code) is None, (
                f"{path.name} must not own {pattern!r}"
            )


def test_public_gateway_contracts_expose_no_hidden_reasoning() -> None:
    from kernel.llm import model_gateway_contracts as contracts

    public_contracts = (
        contracts.ModelGatewayRequest,
        contracts.ModelGatewayResponse,
        contracts.ModelInputPart,
        contracts.ModelExecutionFacts,
        contracts.ModelStreamEvent,
        contracts.ModelToolCall,
        contracts.ModelToolDefinition,
        contracts.StructuredOutputRequirement,
        contracts.ModelUsage,
    )

    for contract in public_contracts:
        for field in dataclasses.fields(contract):
            name = field.name.lower()
            for fragment in FORBIDDEN_CONTRACT_FIELD_FRAGMENTS:
                assert fragment not in name, (
                    f"{contract.__name__}.{field.name} exposes hidden reasoning"
                )


def test_hidden_reasoning_cannot_be_constructed_on_public_contracts() -> None:
    from kernel.llm import model_gateway_contracts as contracts

    with pytest.raises(TypeError):
        contracts.ModelStreamEvent(  # type: ignore[call-arg]
            event_type=contracts.ModelStreamEventType.STARTED,
            request_id="model-request-1",
            sequence=0,
            reasoning_trace="hidden",
        )


def test_gateway_core_does_not_leak_raw_provider_exceptions() -> None:
    """Public gateway errors must be typed and safe, never raw provider text."""

    from kernel.llm.model_gateway_errors import ModelGatewayError, ModelGatewayErrorCode

    error = ModelGatewayError(
        ModelGatewayErrorCode.PROVIDER_FAILURE,
        "provider call failed",
    )
    assert error.code is ModelGatewayErrorCode.PROVIDER_FAILURE
    assert "provider call failed" in str(error)
    assert "Traceback" not in str(error)
    assert set(ModelGatewayErrorCode) >= {
        ModelGatewayErrorCode.MODEL_NOT_FOUND,
        ModelGatewayErrorCode.PROVIDER_NOT_AVAILABLE,
        ModelGatewayErrorCode.MODEL_UNAVAILABLE,
        ModelGatewayErrorCode.CAPABILITY_UNSUPPORTED,
        ModelGatewayErrorCode.UNSUPPORTED_REASONING_EFFORT,
        ModelGatewayErrorCode.INPUT_MODALITY_UNSUPPORTED,
        ModelGatewayErrorCode.PRIVACY_DENIED,
        ModelGatewayErrorCode.PROVIDER_REQUEST_INVALID,
        ModelGatewayErrorCode.PROVIDER_TIMEOUT,
        ModelGatewayErrorCode.PROVIDER_FAILURE,
        ModelGatewayErrorCode.STREAM_FAILURE,
        ModelGatewayErrorCode.MODEL_CALL_CANCELLED,
        ModelGatewayErrorCode.STRUCTURED_OUTPUT_INVALID,
        ModelGatewayErrorCode.TOOL_CALL_INVALID,
        ModelGatewayErrorCode.FALLBACK_EXHAUSTED,
    }
