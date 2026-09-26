from decimal import Decimal


class RateTable:
    """Daily FX rates: 1 unit of `base` buys `rate` units of `quote`."""

    def __init__(self):
        self._rates = {}

    def add(self, on_date, base, quote, rate):
        self._rates[(on_date, base, quote)] = Decimal(str(rate))

    def get(self, on_date, base, quote):
        return self._rates[(on_date, base, quote)]
