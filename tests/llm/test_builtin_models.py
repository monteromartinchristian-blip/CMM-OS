from decimal import Decimal

from kernel.llm.builtin_models import register_builtin_models
from kernel.llm.model_catalog import get_model_spec, list_model_specs


def test_registers_builtin_models() -> None:
    register_builtin_models()

    qualified_ids = {spec.qualified_id for spec in list_model_specs()}

    assert qualified_ids == {
        "groq:llama-3.3-70b-versatile",
        "nvidia:z-ai/glm-5.2",
        "together:meta-llama/Llama-3.3-70B-Instruct-Turbo",
    }


def test_registers_verified_nvidia_glm_metadata() -> None:
    register_builtin_models()

    spec = get_model_spec("glm-5.2")

    assert spec.provider == "nvidia"
    assert spec.context_window == 1_000_000
    assert spec.capabilities.reasoning
    assert spec.capabilities.tool_calling
    assert spec.capabilities.max_context_tokens == 1_000_000


def test_registers_verified_groq_llama_metadata() -> None:
    register_builtin_models()

    spec = get_model_spec("groq-llama-3.3-70b")

    assert spec.provider == "groq"
    assert spec.context_window == 131_072
    assert spec.capabilities.tool_calling
    assert spec.capabilities.json_mode
    assert spec.input_cost_per_million == Decimal("0.59")
    assert spec.output_cost_per_million == Decimal("0.79")


def test_registers_verified_together_llama_metadata() -> None:
    register_builtin_models()

    spec = get_model_spec("together-llama-3.3-70b")

    assert spec.provider == "together"
    assert spec.context_window == 131_072
    assert spec.capabilities.tool_calling
    assert spec.capabilities.json_schema


def test_builtin_registration_is_idempotent() -> None:
    register_builtin_models()
    register_builtin_models()

    assert len(list_model_specs()) == 3
