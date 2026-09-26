from decimal import Decimal

from .money import Money, quantize


def convert(money, to_currency, on_date, rates):
    if money.currency == to_currency:
        return money
    rate = rates.get(on_date, money.currency, to_currency)
    return Money(quantize(money.amount * rate, to_currency), to_currency)


def ledger_total(entries, currency, rates):
    """Sum (date, Money) entries into a single Money in `currency`."""
    total = Decimal("0")
    for on_date, money in entries:
        if money.currency == currency:
            total += money.amount
        else:
            total += money.amount * rates.get(on_date, money.currency, currency)
    return Money(quantize(total, currency), currency)
