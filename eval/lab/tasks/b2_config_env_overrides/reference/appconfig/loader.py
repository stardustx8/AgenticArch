"""Load service configuration: defaults, then a JSON document, then APP_* env vars."""

from __future__ import annotations

import copy
import json
import os
from collections.abc import Mapping
from typing import Any

from .defaults import DEFAULTS
from .errors import ConfigError

ENV_PREFIX = "APP_"
_TRUE = frozenset({"true", "yes", "1"})
_FALSE = frozenset({"false", "no", "0"})


def load_config(text: str | None = None, env: Mapping[str, str] | None = None) -> dict[str, Any]:
    """Return DEFAULTS deep-merged with the JSON object in *text* (if any).

    ``APP_*`` variables from *env* (``os.environ`` by default) are applied last;
    ``__`` separates nesting levels, e.g. ``APP_DB__PORT``.
    """
    config = copy.deepcopy(DEFAULTS)
    if text:
        try:
            overrides = json.loads(text)
        except json.JSONDecodeError as exc:
            raise ConfigError(f"invalid JSON config: {exc}") from None
        if not isinstance(overrides, dict):
            raise ConfigError("config document must be a JSON object")
        _merge(config, overrides, path="")
    _apply_env(config, os.environ if env is None else env)
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


def _apply_env(config: dict[str, Any], env: Mapping[str, str]) -> None:
    for name, raw in env.items():
        if not name.startswith(ENV_PREFIX):
            continue
        target = _resolve(config, name[len(ENV_PREFIX):].split("__"))
        if target is None:
            continue
        section, key = target
        section[key] = _coerce(name, raw, section[key])


def _resolve(config: dict[str, Any], parts: list[str]) -> tuple[dict[str, Any], str] | None:
    """Find the section and real key of the leaf addressed by *parts*, ignoring case."""
    section = config
    for depth, part in enumerate(parts, start=1):
        key = _match_key(section, part)
        if key is None:
            return None
        value = section[key]
        if depth == len(parts):
            return None if isinstance(value, dict) else (section, key)
        if not isinstance(value, dict):
            return None
        section = value
    return None


def _match_key(section: dict[str, Any], wanted: str) -> str | None:
    wanted = wanted.lower()
    for key in section:
        if key.lower() == wanted:
            return key
    return None


def _coerce(name: str, raw: str, current: Any) -> Any:
    # Check bool first: isinstance(True, int) is also true.
    if isinstance(current, bool):
        lowered = raw.strip().lower()
        if lowered in _TRUE:
            return True
        if lowered in _FALSE:
            return False
        raise ConfigError(f"{name}: expected a boolean, got {raw!r}")
    if isinstance(current, (int, float)):
        try:
            return type(current)(raw)
        except ValueError:
            kind = "an integer" if isinstance(current, int) else "a number"
            raise ConfigError(f"{name}: expected {kind}, got {raw!r}") from None
    return raw
