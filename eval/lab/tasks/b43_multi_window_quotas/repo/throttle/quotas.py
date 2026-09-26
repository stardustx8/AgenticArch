"""Quota configuration: tiers of named windows and per-user overrides."""

from dataclasses import dataclass

from .errors import QuotaError, UnknownTierError


@dataclass(frozen=True)
class Window:
    """At most ``limit`` units of cost within any ``seconds``-long stretch."""

    name: str
    limit: int
    seconds: float


def make_window(name: str, limit: int, seconds: float) -> Window:
    if not isinstance(name, str) or not name:
        raise QuotaError('window name must be a non-empty string')
    if not isinstance(limit, int) or limit < 1:
        raise QuotaError(f'window {name!r}: limit must be a positive integer')
    if seconds <= 0:
        raise QuotaError(f'window {name!r}: seconds must be positive')
    return Window(name, limit, float(seconds))


class QuotaPolicy:
    """Maps users to the windows that limit them."""

    def __init__(self, default_tier: str = 'free') -> None:
        self.default_tier = default_tier
        self._tiers: dict[str, tuple[Window, ...]] = {}
        self._assignments: dict[str, str] = {}
        self._overrides: dict[str, tuple[Window, ...]] = {}

    def define_tier(self, tier: str, windows: dict[str, tuple[int, float]]) -> None:
        """Define ``tier`` from ``{window name: (limit, seconds)}``."""
        self._tiers[tier] = _build(windows)

    def assign(self, user: str, tier: str) -> None:
        if tier not in self._tiers:
            raise UnknownTierError(f'unknown tier: {tier!r}')
        self._assignments[user] = tier

    def override(self, user: str, windows: dict[str, tuple[int, float]]) -> None:
        """Give ``user`` custom ``{window name: (limit, seconds)}`` limits."""
        self._overrides[user] = _build(windows)

    def clear_override(self, user: str) -> None:
        self._overrides.pop(user, None)

    def tier_of(self, user: str) -> str:
        return self._assignments.get(user, self.default_tier)

    def windows_for(self, user: str) -> tuple[Window, ...]:
        """Return the windows limiting ``user``."""
        override = self._overrides.get(user)
        if override is not None:
            return override
        return self._tier_windows(user)

    def _tier_windows(self, user: str) -> tuple[Window, ...]:
        tier = self.tier_of(user)
        try:
            return self._tiers[tier]
        except KeyError:
            raise UnknownTierError(f'unknown tier: {tier!r}') from None


def _build(windows: dict[str, tuple[int, float]]) -> tuple[Window, ...]:
    if not windows:
        raise QuotaError('at least one window is required')
    if len(windows) > 1:
        raise QuotaError('only one window per tier is supported for now')
    return tuple(make_window(name, limit, seconds) for name, (limit, seconds) in windows.items())
