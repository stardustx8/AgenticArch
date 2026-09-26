"""Load service configuration: built-in defaults overlaid with a JSON document."""

from __future__ import annotations

import copy
import json
from typing import Any

from .defaults import DEFAULTS
from .errors import ConfigError


def load_config(text: str | None = None) -> dict[str, Any]:
    """Return DEFAULTS deep-merged with the JSON object in *text* (if any)."""
    config = copy.deepcopy(DEFAULTS)
    if text:
        try:
            overrides = json.loads(text)
        except json.JSONDecodeError as exc:
            raise ConfigError(f"invalid JSON config: {exc}") from None
        if not isinstance(overrides, dict):
            raise ConfigError("config document must be a JSON object")
        _merge(config, overrides, path="")
    return config


def get(config: dict[str, Any], dotted: str, default: Any = None) -> Any:
    """Look up a dotted key such as ``db.port``."""
    node: Any = config
    for part in dotted.split("."):
        if not isinstance(node, dict) or part not in node:
            return default
        node = node[part]
    return node


def _merge(base: dict[str, Any], overrides: dict[str, Any], path: str) -> None:
    for key, value in overrides.items():
        where = f"{path}{key}"
        if key not in base:
            raise ConfigError(f"unknown config key: {where}")
        if isinstance(base[key], dict):
            if not isinstance(value, dict):
                raise ConfigError(f"{where} must be an object")
            _merge(base[key], value, path=f"{where}.")
        else:
            base[key] = value
