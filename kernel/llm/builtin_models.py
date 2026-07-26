"""Built-in catalog entries for verified external LLM models."""

from __future__ import annotations

from decimal import Decimal

from kernel.llm.model_catalog import ModelSpec, register_model
from kernel.llm.provider_capabilities import ProviderCapabilities


def register_builtin_models() -> None:
    """Register the stable model entries bundled with CMM OS."""

    register_model(
        ModelSpec(
            id="z-ai/glm-5.2",
            provider="nvidia",
            context_window=1_000_000,
            aliases=("glm-5.2", "nvidia-glm-5.2"),
            capabilities=ProviderCapabilities(
                streaming=True,
                tool_calling=True,
                reasoning=True,
                json_mode=True,
                json_schema=True,
                max_context_tokens=1_000_000,
            ),
        ),
        replace=True,
    )

    register_model(
        ModelSpec(
            id="llama-3.3-70b-versatile",
            provider="groq",
            context_window=131_072,
            aliases=("groq-llama-3.3-70b",),
            capabilities=ProviderCapabilities(
                streaming=True,
                tool_calling=True,
                json_mode=True,
                max_context_tokens=131_072,
            ),
            input_cost_per_million=Decimal("0.59"),
            output_cost_per_million=Decimal("0.79"),
        ),
        replace=True,
    )

    register_model(
        ModelSpec(
            id="meta-llama/Llama-3.3-70B-Instruct-Turbo",
            provider="together",
            context_window=131_072,
            aliases=("together-llama-3.3-70b",),
            capabilities=ProviderCapabilities(
                streaming=True,
                tool_calling=True,
                json_mode=True,
                json_schema=True,
                max_context_tokens=131_072,
            ),
        ),
        replace=True,
    )
