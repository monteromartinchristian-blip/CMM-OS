python - <<'PY'
from pathlib import Path

content = """# Multimodel LLM routing

## Purpose

CMM OS provides a provider-independent routing layer for selecting and
constructing executable LLM clients.

The subsystem separates:

1. provider configuration;
2. provider and model capabilities;
3. model metadata and pricing;
4. requirement filtering and ranking;
5. executable route construction.

## Architecture

```text
ProviderSpec
    ↓
ProviderCapabilities
    ↓
ModelSpec / ModelCatalog
    ↓
ModelRequirements
    ↓
ModelRankingPolicy
    ↓
ModelRouter
    ↓
Executable planning provider
Providers
The initial registry includes:
NVIDIA API;
OpenRouter;
Groq;
Together AI.
They share the OpenAI-compatible planning implementation while preserving
their own base URLs, credentials and model identifiers.
Model catalog
ModelSpec stores:
provider and model identifier;
context window;
aliases;
capabilities;
optional input and output prices per million tokens.
Models can be resolved by a qualified identifier:
provider:model-id
or by a registered alias.
Selection
ModelRequirements filters models using:
minimum context window;
required capabilities;
allowed and excluded providers;
local-only execution;
maximum input and output cost.
Unknown prices are rejected whenever a maximum cost is required.
Ranking
Supported ranking strategies:
lowest_cost;
largest_context;
provider_preference.
Ranking is deterministic and uses the qualified model identifier as the final
tie-breaker.
Routing and fallbacks
ModelRouter.route() returns the highest-ranked executable route.
ModelRouter.route_candidates() returns ordered alternatives suitable for
fallback execution.
The current implementation builds fallback candidates but does not yet execute
automatic retries or provider health checks.
Built-in models
Registration is explicit and idempotent:
from kernel.llm import register_builtin_models

register_builtin_models()
The built-in catalog is deliberately small. Dynamic routing aliases are not
treated as stable model entries.
Example
from kernel.llm import (
    ModelRequirements,
    ModelRouter,
    register_builtin_models,
)

register_builtin_models()

route = ModelRouter().route(
    ModelRequirements(
        minimum_context_window=100_000,
        reasoning=True,
        tool_calling=True,
    )
)

print(route.qualified_model)
Future extensions
The architecture supports future additions such as:
automatic retries;
provider health tracking;
latency-aware ranking;
privacy and locality policies;
dynamic pricing;
budget accounting;
quality evaluations;
cognitive cache integration.
"""
path = Path("docs/architecture/multimodel-llm-routing.md")
path.parent.mkdir(parents=True, exist_ok=True)
path.write_text(content, encoding="utf-8")
print(f"Creado: {path}")
PY
