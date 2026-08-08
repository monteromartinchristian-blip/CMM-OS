# Experimental OmniRoute Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Register OmniRoute as an experimental, disabled-by-default OpenAI-compatible provider that can expose multiple explicitly configured models without introducing a new provider abstraction.

**Architecture:** Reuse `ProviderRegistry`, `ModelCatalog`, `ProviderFactory`, `OpenAICompatibleClient` and `OpenAICompatibleProvider`. OmniRoute-specific code contains only declarative registration defaults and explicit model registration.

**Tech Stack:** Python 3, pytest, existing `kernel.llm` contracts, OpenAI-compatible Chat Completions.

## Global Constraints

- Provider id: `omniroute`
- Default endpoint: `http://localhost:20128/v1`
- Base URL override: `CMM_OMNIROUTE_BASE_URL`
- Optional API key: `CMM_OMNIROUTE_API_KEY`
- Disabled by default
- Initial verified model: `cp/cline-pass/deepseek-v4-flash`
- No OmniRoute-specific `LLMProvider`
- No model discovery
- No routing-policy changes
- No fallback changes
- No dependency on Claude Desktop port 20129
- No direct Cline CLI integration
- Tests must work without OmniRoute or internet access

## Files

Create:

- `kernel/llm/experimental_omniroute.py`
- `tests/llm/test_experimental_omniroute.py`

Modify:

- `kernel/llm/__init__.py`

## Task 1 — Declarative OmniRoute registration

Create constants:

- `OMNIROUTE_PROVIDER_ID = "omniroute"`
- `OMNIROUTE_DEFAULT_BASE_URL = "http://localhost:20128/v1"`
- `OMNIROUTE_BASE_URL_ENV = "CMM_OMNIROUTE_BASE_URL"`
- `OMNIROUTE_API_KEY_ENV = "CMM_OMNIROUTE_API_KEY"`
- `OMNIROUTE_DEEPSEEK_V4_FLASH = "cp/cline-pass/deepseek-v4-flash"`

Create `register_experimental_omniroute(...)` with:

- `provider_registry: ProviderRegistry`
- `model_catalog: ModelCatalog`
- `enabled: bool = False`
- `model_ids: tuple[str, ...]` defaulting to DeepSeek V4 Flash

Behavior:

- reject empty `model_ids` before mutating registries;
- register one local `ProviderSpec`;
- use `api_style="chat_completions"`;
- set `base_url`, `base_url_env`, and `api_key_env`;
- declare `ProviderCapabilities(chat_completions=True)`;
- preserve `enabled`;
- register every supplied model id unchanged;
- reuse existing duplicate validation.

Tests:

- disabled by default;
- explicit enable;
- default base URL;
- environment override;
- optional API key;
- initial DeepSeek model;
- multiple models;
- empty model list rejected.

Commit: `feat(llm): register experimental OmniRoute provider`

## Task 2 — ProviderFactory execution

Using a fake compatible client, prove that the existing `ProviderFactory`:

- constructs `OpenAICompatibleProvider`;
- passes `cp/cline-pass/deepseek-v4-flash` unchanged;
- normalizes result into `LLMResponse`;
- exposes `provider_id="omniroute"`;
- rejects the disabled provider;
- rejects provider/model mismatch.

No production code is expected for this task.

Commit: `test(llm): verify OmniRoute compatible execution`

## Task 3 — Public API and regression validation

Expose through `kernel.llm`:

- `OMNIROUTE_PROVIDER_ID`
- `OMNIROUTE_DEFAULT_BASE_URL`
- `OMNIROUTE_BASE_URL_ENV`
- `OMNIROUTE_API_KEY_ENV`
- `OMNIROUTE_DEEPSEEK_V4_FLASH`
- `register_experimental_omniroute`

Run:

- `.venv/bin/python -m pytest -q tests/llm`
- `.venv/bin/python -m compileall -q kernel/llm`
- `ruff check kernel/llm tests/llm`
- `git diff --check`
- `.venv/bin/python -m pytest -q`

Commit: `feat(llm): expose experimental OmniRoute integration`

## Acceptance Criteria

- OmniRoute remains disabled unless explicitly enabled.
- Default endpoint is `http://localhost:20128/v1`.
- Environment override works.
- API key remains optional and environment-only.
- CMM OS stores no ClinePass credentials.
- Multiple OmniRoute models can coexist.
- Model IDs reach OmniRoute unchanged.
- Execution reuses `OpenAICompatibleProvider`.
- Existing routing behavior is unchanged.
- Port 20129 is not part of the integration.
- No direct Cline CLI integration is introduced.
- LLM tests, global suite, Ruff, compileall and `git diff --check` are green.
