"""A deliberately tiny schema: dotted key -> Field(type, required)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .flatten import lookup


@dataclass(frozen=True)
class Field:
    type: type | tuple[type, ...]
    required: bool = True


Schema = dict[str, Field]


def validate(config: Any, schema: Schema) -> list[str]:
    """Return human-readable problems with *config*; an empty list means valid."""
    if not isinstance(config, dict):
        return ["config must be a JSON object"]
    problems: list[str] = []
    for key in sorted(schema):
        field = schema[key]
        try:
            value = lookup(config, key)
        except KeyError:
            if field.required:
                problems.append(f"{key}: required")
            continue
        if not _matches(value, field.type):
            problems.append(f"{key}: expected {_type_name(field.type)}, got {type(value).__name__}")
    return problems


def _matches(value: Any, expected: type | tuple[type, ...]) -> bool:
    types = expected if isinstance(expected, tuple) else (expected,)
    if isinstance(value, bool):
        # JSON true/false must not satisfy an int or float field.
        return bool in types
    return isinstance(value, types)


def _type_name(expected: type | tuple[type, ...]) -> str:
    types = expected if isinstance(expected, tuple) else (expected,)
    return " or ".join(t.__name__ for t in types)
