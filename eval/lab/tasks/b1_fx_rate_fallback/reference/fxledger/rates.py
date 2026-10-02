import bisect
from decimal import Decimal


class RateTable:
    """Daily FX rates: 1 unit of `base` buys `rate` units of `quote`."""

    def __init__(self):
        self._dates = {}  # (base, quote) -> sorted list of dates
        self._rates = {}  # (base, quote, date) -> rate

    def add(self, on_date, base, quote, rate):
        if (base, quote, on_date) not in self._rates:
            bisect.insort(self._dates.setdefault((base, quote), []), on_date)
        self._rates[(base, quote, on_date)] = Decimal(str(rate))

    def _latest(self, on_date, base, quote):
        """(date, rate) of the most recent quote on or before on_date, or None."""
        dates = self._dates.get((base, quote), [])
        i = bisect.bisect_right(dates, on_date)
        if i == 0:
            return None
        found = dates[i - 1]
        return found, self._rates[(base, quote, found)]

    def get(self, on_date, base, quote):
        """Rate for base->quote as of on_date.

        Falls back to the latest earlier rate (never a later one) and to the
        inverse of quote->base when the direct pair isn't quoted. If both are
        available the more recent one wins; the direct rate wins ties.
        """
        direct = self._latest(on_date, base, quote)
        inverse = self._latest(on_date, quote, base)
        if direct is None and inverse is None:
            raise KeyError((on_date, base, quote))
        if inverse is None or (direct is not None and direct[0] >= inverse[0]):
            return direct[1]
        return Decimal(1) / inverse[1]
