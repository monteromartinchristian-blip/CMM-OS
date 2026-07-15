from dataclasses import dataclass, field

from kernel.actions.base import Action


@dataclass
class Plan:

    version: int = 1

    actions: list[Action] = field(default_factory=list)
