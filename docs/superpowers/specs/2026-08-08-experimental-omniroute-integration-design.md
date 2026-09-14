# Experimental OmniRoute Integration — Design

## Objective

Integrate OmniRoute into the existing CMM OS LLM infrastructure as an
experimental OpenAI-compatible provider without introducing a parallel
provider abstraction or prematurely implementing the Phase 11 Model Gateway.

The integration must allow CMM OS to use multiple models exposed by OmniRoute,
including ClinePass-backed models such as:

`cp/cline-pass/deepseek-v4-flash`

The model identifier is configuration/catalog data, not provider-specific code.

## Architectural Decision

CMM OS will reuse the existing LLM stack:

ProviderRegistry
→ ProviderSpec(provider="omniroute")
→ ModelCatalog
→ ProviderFactory
→ OpenAICompatibleClient
→ OpenAICompatibleProvider
→ OmniRoute

No `ExperimentalOmniRouteProvider` class will be created in this iteration.

The existing `OpenAICompatibleProvider` already provides the required
provider-independent execution contract. A dedicated OmniRoute adapter will
only be introduced later if OmniRoute requires behavior that cannot be
represented through the existing compatible-provider contract.

## Provider Definition

Provider identifier:

`omniroute`

Initial properties:

- provider_type = local
- api_style = chat_completions
- enabled = false by default
- base_url = http://localhost:20128/v1
- base_url_env = CMM_OMNIROUTE_BASE_URL
- api_key_env = CMM_OMNIROUTE_API_KEY

The API key is optional.

No credentials, ClinePass tokens, or provider secrets may be hard-coded or
persisted in provider metadata.

## Models

OmniRoute models are normal `ModelSpec` entries owned by the existing
`ModelCatalog`.

Initial verified target:

`cp/cline-pass/deepseek-v4-flash`

The architecture must permit additional OmniRoute models to be registered
without modifying provider execution code.

Model discovery is explicitly out of scope for this iteration.

## Feature Status

OmniRoute support is experimental and disabled by default.

Enabling the provider must be an explicit configuration action.

An unavailable or disabled OmniRoute instance must fail through the existing
structured `ProviderError` path and must not silently fall back to another
provider.

Routing behavior is not changed in this iteration.

## Transport

CMM OS communicates directly with OmniRoute's OpenAI-compatible endpoint:

`http://localhost:20128/v1`

The Claude Desktop alias proxy on port `20129` is not part of CMM OS.

It exists only to satisfy Claude Desktop's Anthropic-model-name restrictions
and must remain independent from the CMM OS provider integration.

## Responsibilities

Existing infrastructure remains responsible for provider registration, model
catalog registration, provider/model compatibility, provider construction,
request normalization, response normalization, token usage, finish reason,
provider errors, and model routing.

OmniRoute remains responsible for upstream provider authentication, ClinePass
integration, concrete provider/model routing behind its exposed model
identifier, provider-specific connections, and upstream availability.

CMM OS must not store ClinePass credentials, impersonate Anthropic model
identifiers, depend on the Claude Desktop alias proxy, execute unrestricted
terminal commands, introduce a second model-routing system, or duplicate
`OpenAICompatibleProvider`.

## Configuration

Supported environment override:

`CMM_OMNIROUTE_BASE_URL`

Optional credential:

`CMM_OMNIROUTE_API_KEY`

Default base URL:

`http://localhost:20128/v1`

The configuration must be testable without a running OmniRoute installation.

## Error Handling

Existing `ProviderError` semantics are reused.

Minimum verified cases:

- provider disabled;
- provider unavailable;
- unknown model;
- provider/model mismatch;
- connection failure;
- timeout;
- authentication failure;
- rate limit;
- empty response.

No OmniRoute-specific exception hierarchy is introduced.

## Testing

Tests must not depend on OmniRoute being installed, ClinePass being
authenticated, localhost port 20128 being available, or external network
connectivity.

Tests use injected/mock compatible clients.

Required coverage:

1. OmniRoute `ProviderSpec` registration.
2. Base URL default.
3. Environment base URL override.
4. Optional API key resolution.
5. Disabled-by-default behavior.
6. OmniRoute model catalog registration.
7. Multiple OmniRoute models can coexist.
8. `ProviderFactory` creates an `OpenAICompatibleProvider`.
9. The selected OmniRoute model ID is passed unchanged to the client.
10. Provider response is normalized to `LLMResponse`.
11. Provider/model mismatch is rejected.
12. Disabled/unavailable provider is rejected.
13. Existing OpenAI-compatible providers remain unaffected.

## Phase Boundary

This work is an early provider integration, not the Phase 11 Model Gateway.

Deferred to Phase 11:

- provider discovery;
- automatic OmniRoute model discovery;
- provider health polling;
- cost accounting;
- routing-policy changes;
- fallback policies;
- provider cache integration;
- model evaluation;
- provider dashboard;
- direct `ClineCliProvider`;
- execution profiles such as `repository_worker` and `personal_assistant`.

The future Model Gateway must be able to consume this provider through the
existing registry/catalog/factory contracts without rewriting it.

## Success Criterion

The iteration is complete when CMM OS can construct and execute an
OpenAI-compatible provider for an explicitly registered OmniRoute model while
OmniRoute remains disabled by default and the existing LLM provider contracts
remain unchanged.
