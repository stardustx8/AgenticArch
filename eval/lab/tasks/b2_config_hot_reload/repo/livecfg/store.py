"""In-process holder for the live service configuration."""

from __future__ import annotations

import copy
import json
from typing import Any, Callable

from .errors import ConfigError
from .flatten import lookup
from .schema import Schema, validate

Source = Callable[[], str]


class ConfigStore:
    """Loads JSON config from *source* and serves validated values by dotted key."""

    def __init__(self, source: Source, schema: Schema | None = None) -> None:
        self._source = source
        self._schema = schema or {}
        self._config: dict[str, Any] = {}
        self._loaded = False

    @property
    def loaded(self) -> bool:
        return self._loaded

    def load(self) -> None:
        """Read, parse and validate the source, replacing the current config."""
        self._config = self._read()
        self._loaded = True

    def get(self, key: str, default: Any = None) -> Any:
        try:
            return lookup(self._config, key)
        except KeyError:
            return default

    def snapshot(self) -> dict[str, Any]:
        return copy.deepcopy(self._config)

    def _read(self) -> dict[str, Any]:
        text = self._source()
        try:
            config = json.loads(text)
        except json.JSONDecodeError as exc:
            raise ConfigError(f"config is not valid JSON: {exc}") from None
        problems = validate(config, self._schema)
        if problems:
            raise ConfigError("invalid config: " + "; ".join(problems), problems)
        return config
