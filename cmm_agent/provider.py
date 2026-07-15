from ollama import chat

DEFAULT_MODEL = "qwen2.5-coder:7b"


class OllamaProvider:

    def __init__(self, model=DEFAULT_MODEL):
        self.model = model

    def chat(self, prompt: str) -> str:

        response = chat(
            model=self.model,
            messages=[
                {
                    "role": "user",
                    "content": prompt,
                }
            ],
            format="json",
        )

        return response.message.content