import importlib

DEFAULT_MODEL = "qwen2.5-coder:7b"


class OllamaProvider:

    def __init__(self, model=DEFAULT_MODEL):
        self.model = model

    def chat(self, prompt: str) -> str:
        try:
            ollama = importlib.import_module("ollama")
        except ModuleNotFoundError as error:
            raise RuntimeError(
                "The legacy Ollama provider requires the optional 'ollama' package."
            ) from error

        response = ollama.chat(
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
