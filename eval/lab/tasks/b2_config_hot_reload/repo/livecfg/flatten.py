"""Helpers for addressing nested config with dotted keys."""

from __future__ import annotations

from typing import Any


def flatten(tree: dict[str, Any], prefix: str = "") -> dict[str, Any]:
    """Map every leaf of *tree* to its dotted path.

    Only dicts are descended into; lists and scalars are leaves and empty
    dicts contribute nothing.
    """
    flat: dict[str, Any] = {}
    for key, value in tree.items():
        path = f"{prefix}{key}"
        if isinstance(value, dict):
            flat.update(flatten(value, f"{path}."))
        else:
            flat[path] = value
    return flat


def lookup(tree: dict[str, Any], dotted: str) -> Any:
    """Return the value at *dotted*; raises KeyError if any segment is missing."""
    node: Any = tree
    for part in dotted.split("."):
        if not isinstance(node, dict) or part not in node:
            raise KeyError(dotted)
        node = node[part]
    return node
