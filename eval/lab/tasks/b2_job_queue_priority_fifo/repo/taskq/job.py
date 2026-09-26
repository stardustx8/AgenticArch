from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class Job:
    """A unit of work. Lower ``priority`` values run first."""

    id: str
    payload: dict[str, Any] = field(default_factory=dict)
    priority: int = 0

    def __post_init__(self) -> None:
        if not self.id:
            raise ValueError("job id must be a non-empty string")
        if not isinstance(self.priority, int):
            raise TypeError(f"priority must be an int, got {type(self.priority).__name__}")
