from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

# ISO 4217 minor units for currencies that don't use 2 decimals.
MINOR_UNITS = {"JPY": 0, "KRW": 0, "ISK": 0, "KWD": 3, "BHD": 3, "JOD": 3, "OMR": 3, "TND": 3}


@dataclass(frozen=True)
class Money:
    amount: Decimal
    currency: str

    def __post_init__(self):
        if not isinstance(self.amount, Decimal):
            object.__setattr__(self, "amount", Decimal(str(self.amount)))

    def __add__(self, other):
        if not isinstance(other, Money):
            return NotImplemented
        if other.currency != self.currency:
            raise ValueError(f"cannot add {self.currency} and {other.currency}")
        return Money(self.amount + other.amount, self.currency)


def minor_units(currency: str) -> int:
    return MINOR_UNITS.get(currency, 2)


def quantize(amount: Decimal, currency: str) -> Decimal:
    """Round half-up to the currency's minor units."""
    exponent = Decimal(1).scaleb(-minor_units(currency))
    return amount.quantize(exponent, rounding=ROUND_HALF_UP)
