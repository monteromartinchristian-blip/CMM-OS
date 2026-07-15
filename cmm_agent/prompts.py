from pathlib import Path

ROOT = Path(__file__).resolve().parent
PROMPTS = ROOT / "prompts"


def load_prompt(name: str) -> str:

    file = PROMPTS / f"{name}.md"

    if not file.exists():
        raise FileNotFoundError(f"Prompt not found: {file}")

    return file.read_text(encoding="utf-8")
