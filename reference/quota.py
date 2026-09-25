"""Observe subscription consumption without inferring it from dollar prices.

Units are provider-specific. Never add an OpenAI percentage to a Claude percentage.
Missing, rounded, concurrent, reset or stale observations are not attributable usage.
"""
from dataclasses import dataclass
import math


@dataclass(frozen=True)
class QuotaSnapshot:
    account: str
    bucket: str
    window_id: str
    units: str
    used: float
    observed_at: float
    measured_at: float
    exact: bool = False


def attributable_delta(before: QuotaSnapshot, after: QuotaSnapshot, *,
                       exclusive: bool, max_staleness: float = 60.0) -> float | None:
    if exclusive is not True or before.exact is not True or after.exact is not True:
        return None
    if not before.account or not before.bucket or not before.window_id or not before.units:
        return None
    if (before.account, before.bucket, before.window_id, before.units) != (
            after.account, after.bucket, after.window_id, after.units):
        return None
    values = (before.used, after.used, before.observed_at, after.observed_at,
              before.measured_at, after.measured_at, max_staleness)
    if any(type(x) not in (float, int) or not math.isfinite(x) for x in values):
        return None
    if max_staleness < 0 or before.used < 0 or after.used < before.used:
        return None
    if after.measured_at <= before.measured_at or after.observed_at <= before.observed_at:
        return None
    if any(not 0 <= s.observed_at - s.measured_at <= max_staleness for s in (before, after)):
        return None
    return after.used - before.used


def api_cost_to_quota(*_args, **_kwargs):
    raise ValueError('No provider-independent conversion exists; collect actual quota observations')
