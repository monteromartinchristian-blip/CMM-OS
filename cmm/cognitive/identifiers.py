from __future__ import annotations

import re
from dataclasses import dataclass
from uuid import uuid4

from cmm.cognitive.errors import InvalidCognitiveIdentifierError

_IDENTIFIER_PART_PATTERN = re.compile(r"^[a-z0-9][a-z0-9._-]*$")


@dataclass(frozen=True, slots=True)
class CognitiveIdentifier:
    namespace: str
    kind: str
    value: str

    def __post_init__(self) -> None:
        for field_name, field_value in (
            ("namespace", self.namespace),
            ("kind", self.kind),
            ("value", self.value),
        ):
            if not isinstance(field_value, str) or not field_value:
                raise InvalidCognitiveIdentifierError(
                    f"{field_name} must be a non-empty string"
                )
            if not _IDENTIFIER_PART_PATTERN.fullmatch(field_value):
                raise InvalidCognitiveIdentifierError(
                    f"{field_name} contains invalid characters: {field_value!r}"
                )

    def __str__(self) -> str:
        return f"{self.namespace}:{self.kind}:{self.value}"

    def to_dict(self) -> dict[str, str]:
        return {
            "namespace": self.namespace,
            "kind": self.kind,
            "value": self.value,
            "id": str(self),
        }

    @classmethod
    def parse(cls, raw: str) -> CognitiveIdentifier:
        if not isinstance(raw, str):
            raise InvalidCognitiveIdentifierError(
                "identifier must be provided as a string"
            )

        parts = raw.split(":")
        if len(parts) != 3:
            raise InvalidCognitiveIdentifierError(
                "identifier must use namespace:kind:value format"
            )

        return cls(
            namespace=parts[0],
            kind=parts[1],
            value=parts[2],
        )

    @classmethod
    def generate(
        cls,
        namespace: str,
        kind: str,
    ) -> CognitiveIdentifier:
        return cls(
            namespace=namespace,
            kind=kind,
            value=uuid4().hex,
        )


def generate_cognitive_id(namespace: str, kind: str) -> str:
    return str(CognitiveIdentifier.generate(namespace, kind))
