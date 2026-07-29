# Multimodel Foundation

## Status

Implemented on `feature/multimodel-foundation-v2`.

This document describes the provider-independent multimodel foundation recovered and rebuilt after Phase 9.

## Objectives

The foundation must:

- register providers and models without import-time global state;
- separate provider capabilities from model capabilities;
- represent privacy, capability, context, and cost requirements;
- filter and rank candidates deterministically;
- produce auditable routing decisions;
- preserve ordered fallback candidates;
- instantiate compatible providers only after routing;
- keep `kernel` independent from `cmm.development`;
- avoid hard-coded provider and model catalogs.

## Architecture

```text
ProviderRegistry
        +
ModelCatalog
        ↓
ModelRequirements
        ↓
Deterministic filtering and ranking
        ↓
RoutingDecision
        ↓
ProviderFactory
        ↓
LLMProvider
```

## Provider Registry

`ProviderRegistry` is instance-scoped and owned by the application container.

A `ProviderSpec` contains provider-level metadata:

- identifier;
- local or remote type;
- API style;
- credential environment reference;
- base URL and optional environment override;
- enabled state;
- region;
- data policy;
- availability;
- provider transport capabilities.

Importing the module does not register any provider.

## Model Catalog

`ModelCatalog` is bound explicitly to a `ProviderRegistry`.

A `ModelSpec` contains model-level metadata:

- model identifier;
- provider identifier;
- context window;
- model capabilities;
- aliases;
- input, output, and cached-input prices;
- availability;
- version.

The catalog rejects models whose provider is not registered.

## Capabilities

Provider capabilities describe transport-level support, such as:

- Chat Completions;
- Responses API;
- streaming;
- embeddings.

Model capabilities describe model behavior, such as:

- reasoning;
- tool calling;
- structured output;
- JSON mode and JSON Schema;
- vision;
- audio;
- embeddings.

Capabilities default to unsupported. Unknown support must never be treated as available.

## Model Requirements

`ModelRequirements` defines hard constraints for one model-assisted operation:

- minimum context window;
- required capabilities;
- privacy policy;
- allowed providers;
- excluded providers;
- maximum unit prices;
- premium permission.

Initial privacy policies are:

```text
LOCAL_ONLY
LOCAL_PREFERRED
REMOTE_ALLOWED
PREMIUM_ALLOWED
SENSITIVE
```

`LOCAL_ONLY` and `SENSITIVE` reject remote providers in the current foundation. Broader policy composition belongs to the later Model Gateway.

## Deterministic Selection

Selection has two stages:

1. Filter models against hard requirements.
2. Rank matching models through a deterministic policy.

Initial ranking strategies are:

- lowest cost;
- largest context;
- provider preference.

Stable qualified identifiers break ties, so identical inputs and configuration produce identical ordering.

## Routing Decisions

`ModelRouter` does not execute provider clients.

It produces a `RoutingDecision` containing:

- selected provider and model;
- all matching candidates in rank order;
- rejected models;
- explicit rejection reasons;
- requirements;
- ranking policy;
- configuration version;
- metadata;
- reason codes.

Fallback candidates are derived from the preserved candidate ordering.

## Provider Factory

`ProviderFactory` converts a selected `RoutingDecision` into an executable `LLMProvider`.

The router therefore remains independent from:

- SDK clients;
- API credentials;
- development planning adapters;
- concrete provider construction.

The initial factory supports OpenAI-compatible Chat Completions endpoints through `OpenAICompatibleClient` and `OpenAICompatibleProvider`.

The existing native OpenAI provider continues to use the Responses API separately.

## Deliberately Excluded

This foundation does not hard-code:

- OpenRouter;
- Groq;
- Together;
- NVIDIA;
- provider prices;
- current model names;
- built-in model rankings;
- environment variables for specific providers.

These are changing configuration data and must be introduced through versioned configuration after verification.

## Validation

The implementation is covered by unit and integration tests for:

- instance isolation;
- normalization;
- duplicates and replacement;
- conservative capabilities;
- aliases and collisions;
- pricing and versions;
- privacy filtering;
- context and capability filtering;
- cost filtering;
- deterministic ranking;
- rejection reasons;
- fallback ordering;
- provider construction;
- OpenAI-compatible response normalization;
- absence of `kernel` dependencies on `cmm.development`.
