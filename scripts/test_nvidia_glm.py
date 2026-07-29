import os
import sys

from openai import OpenAI


def main() -> int:
    api_key = os.getenv("NVIDIA_API_KEY")
    if not api_key:
        print("Error: NVIDIA_API_KEY no está definida.", file=sys.stderr)
        return 1

    client = OpenAI(
        base_url="https://integrate.api.nvidia.com/v1",
        api_key=api_key,
    )

    response = client.chat.completions.create(
        model="z-ai/glm-5.2",
        messages=[
            {
                "role": "user",
                "content": (
                    "Responde exactamente con esta frase y nada más: "
                    "GLM-5.2 conectado correctamente con CMM OS"
                ),
            }
        ],
        temperature=0,
        max_tokens=100,
    )

    content = response.choices[0].message.content
    print(content or "")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
