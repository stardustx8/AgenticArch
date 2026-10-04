from dataclasses import dataclass
from decimal import ROUND_HALF_EVEN, Decimal


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


def quantize(amount: Decimal, currency: str) -> Decimal:
    return amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_EVEN)
