from kernel.llm.mock_provider import MockProvider
from kernel.llm.models import LLMRequest, LLMResponse
from kernel.llm.prompt import PromptBuilder


def test_total_tokens_property() -> None:
    response = LLMResponse(
        content="hello",
        model="test-model",
        usage_prompt_tokens=3,
        usage_completion_tokens=5,
    )

    assert response.total_tokens == 8


def test_prompt_builder_combines_system_and_user_prompts() -> None:
    builder = PromptBuilder(system_prompt="system", user_prompt="user")

    assert builder.build_system_prompt() == "system"
    assert builder.build_user_prompt() == "user"
    assert builder.build() == "system\n\nuser"


def test_mock_provider_returns_mock_response() -> None:
    provider = MockProvider(response="mock output")
    request = LLMRequest(prompt="hello")

    response = provider.generate(request)

    assert isinstance(response, LLMResponse)
    assert response.content == "mock output"
    assert response.model == "mock"
    assert response.usage_prompt_tokens == 0
    assert response.usage_completion_tokens == 0
