from decimal import Decimal


class MissingRateError(KeyError):
    pass


class RateTable:
    """Conversion rates into one base currency: 1 unit of ``code`` = rate units of base."""

    def __init__(self, base, rates):
        self.base = base.upper()
        self._rates = {code.upper(): Decimal(str(rate)) for code, rate in rates.items()}
        self._rates[self.base] = Decimal(1)

    def convert(self, amount, currency):
        try:
            rate = self._rates[currency.upper()]
        except KeyError:
            raise MissingRateError(currency) from None
        return amount * rate
