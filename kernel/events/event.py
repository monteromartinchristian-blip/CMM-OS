from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass(slots=True)
class Event:

    name: str

    payload: Any = None

    timestamp: datetime = field(default_factory=datetime.now)
