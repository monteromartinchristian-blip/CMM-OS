from dataclasses import dataclass, field


@dataclass(slots=True)
class Component:

    id: str
    name: str
    type: str
    status: str


@dataclass(slots=True)
class Service:

    name: str


@dataclass(slots=True)
class Tool:

    name: str


@dataclass(slots=True)
class Architecture:

    components: list[Component] = field(default_factory=list)

    services: list[Service] = field(default_factory=list)

    tools: list[Tool] = field(default_factory=list)
