"""Mock LLM provider for planner strategy tests."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from kernel.planner.llm_provider import LLMProvider


@dataclass(slots=True)
class MockLLMProvider(LLMProvider):
    """Return deterministic text and record received prompts."""

    response: str | None = None
    prompts: list[str] = field(default_factory=list, init=False)

    def complete(self, prompt: str) -> str:
        """Record the prompt and return the configured mock response."""

        self.prompts.append(prompt)
        if self.response is not None:
            return self.response

        return self._build_response(prompt)

    @staticmethod
    def _build_response(prompt: str) -> str:
        goal_match = re.search(r"^Goal:\s*(.+)$", prompt, re.MULTILINE)
        goal = goal_match.group(1).strip() if goal_match else prompt.strip()
        lowered_goal = goal.lower()

        class_name = MockLLMProvider._extract_class_name(goal)
        method_name = MockLLMProvider._extract_method_name(goal)
        module_name = MockLLMProvider._extract_module_name(goal)

        if (
            "create class" in lowered_goal and "with method" in lowered_goal
        ) or (
            re.search(r"\b(create|crea|crear)\b.*\b(class|clase)\b.*\b(with|con)\b.*\b(method|m[eé]todo)\b", lowered_goal)
        ):
            return (
                f"OPERATION create_class\n"
                f"NAME {class_name}\n\n"
                f"---\n\n"
                f"OPERATION insert_method\n"
                f"CLASS {class_name}\n"
                f"METHOD {method_name}\n"
                f"SOURCE_CODE def {method_name}(self):\n    pass"
            )

        if (
            re.search(r"\b(cra|crea|crear)\b.*\b(Logger)\b", goal, re.IGNORECASE)
            and re.search(r"\b(hello|saluda|saludar)\b.*\b(User)\b", goal, re.IGNORECASE)
        ) or ("logger" in lowered_goal and "hello" in lowered_goal and "user" in lowered_goal):
            return (
                "OPERATION create_class\n"
                "NAME Logger\n\n"
                "---\n\n"
                "OPERATION insert_method\n"
                "CLASS User\n"
                "METHOD hello\n"
                "SOURCE_CODE def hello(self):\n    pass"
            )

        if "create class" in lowered_goal or re.search(r"\b(create|crea|crear)\b.*\b(class|clase)\b", lowered_goal):
            return f"OPERATION create_class\nNAME {class_name}"

        if "replace method" in lowered_goal or re.search(r"\b(replace|reemplaza)\b.*\b(method|m[eé]todo)\b", lowered_goal):
            return (
                f"OPERATION replace_method\n"
                f"CLASS {class_name}\n"
                f"METHOD {method_name}\n"
                f"SOURCE_CODE def {method_name}(self): pass"
            )

        if (
            "insert method" in lowered_goal
            or re.search(r"\b(insert|add|añade|agrega|inserta|añadir|agregar)\b.*\b(method|m[eé]todo)\b", lowered_goal)
        ):
            return (
                f"OPERATION insert_method\n"
                f"CLASS {class_name}\n"
                f"METHOD {method_name}\n"
                f"SOURCE_CODE def {method_name}(self):\n    pass"
            )

        if "ensure import" in lowered_goal or "import" in lowered_goal or re.search(r"\b(ensure|asegura)\b.*\bimport\b", lowered_goal):
            return f"OPERATION ensure_import\nMODULE {module_name}"

        return f"OPERATION create_class\nCLASS {class_name}"

    @staticmethod
    def _extract_class_name(goal: str) -> str:
        match = re.search(r"\b(?:class|clase|to)\s+([A-Za-z_][A-Za-z0-9_]*)\b", goal, re.IGNORECASE)
        if match:
            return match.group(1)

        fallback = re.search(r"\b([A-Z][A-Za-z0-9_]*)\b", goal)
        if fallback:
            return fallback.group(1)

        return "User"

    @staticmethod
    def _extract_method_name(goal: str) -> str:
        match = re.search(r"\b(?:method|m[eé]todo)\s+([A-Za-z_][A-Za-z0-9_]*)\b", goal, re.IGNORECASE)
        if match:
            return match.group(1)

        fallback = re.search(r"\b([a-z_][A-Za-z0-9_]*)\s*(?:\(|$)", goal)
        if fallback:
            return fallback.group(1)

        return "hello"

    @staticmethod
    def _extract_module_name(goal: str) -> str:
        match = re.search(r"\bimport\s+([A-Za-z_][A-Za-z0-9_.]*)\b", goal, re.IGNORECASE)
        if match:
            return match.group(1)

        fallback = re.search(r"\b(?:module|modulo)\s+([A-Za-z_][A-Za-z0-9_.]*)\b", goal, re.IGNORECASE)
        if fallback:
            return fallback.group(1)

        return "requests"
