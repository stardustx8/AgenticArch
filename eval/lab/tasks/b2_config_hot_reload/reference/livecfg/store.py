"""In-process holder for the live service configuration."""

from __future__ import annotations

import copy
import itertools
import json
from typing import Any, Callable

from .errors import ConfigError
from .flatten import flatten, lookup
from .schema import Schema, validate

Source = Callable[[], str]
Callback = Callable[[str, Any, Any], None]
_MISSING = object()


class ConfigStore:
    """Loads JSON config from *source* and serves validated values by dotted key."""

    def __init__(self, source: Source, schema: Schema | None = None) -> None:
        self._source = source
        self._schema = schema or {}
        self._config: dict[str, Any] = {}
        self._loaded = False
        self._subscribers: dict[int, tuple[str, Callback]] = {}
        self._tokens = itertools.count()

    @property
    def loaded(self) -> bool:
        return self._loaded

    def load(self) -> None:
        """Read, parse and validate the source, replacing the current config."""
        self._config = self._read()
        self._loaded = True

    def reload(self) -> list[str]:
        """Swap in freshly read config and notify subscribers of changed leaves.

        Returns the sorted dotted keys that were added, removed or changed. If
        the source is unparsable or invalid, nothing changes and ConfigError
        propagates.
        """
        new_config = self._read()
        before = flatten(self._config)
        after = flatten(new_config)
        changed = sorted(
            key
            for key in before.keys() | after.keys()
            if _differs(before.get(key, _MISSING), after.get(key, _MISSING))
        )
        self._config = new_config
        self._loaded = True
        for key in changed:
            old, new = before.get(key), after.get(key)
            for prefix, callback in list(self._subscribers.values()):
                if _covers(prefix, key):
                    callback(key, old, new)
        return changed

    def subscribe(self, prefix: str, callback: Callback) -> Callable[[], None]:
        """Call ``callback(key, old, new)`` for changed leaves under *prefix*.

        Returns a function that removes the subscription.
        """
        token = next(self._tokens)
        self._subscribers[token] = (prefix, callback)

        def unsubscribe() -> None:
            self._subscribers.pop(token, None)

        return unsubscribe

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


def _differs(old: Any, new: Any) -> bool:
    # 1 == True in Python, but a JSON 1 turning into true is still a change.
    return type(old) is not type(new) or old != new


def _covers(prefix: str, key: str) -> bool:
    return not prefix or key == prefix or key.startswith(prefix + ".")
