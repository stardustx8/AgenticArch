from decimal import ROUND_HALF_UP, Decimal

from .models import LineItem

CENT = Decimal("0.01")


def to_decimal(value) -> Decimal:
    """Convert an int/float/str/Decimal to Decimal without binary float artefacts."""
    if isinstance(value, Decimal):
        return value
    if isinstance(value, float):
        return Decimal(repr(value))
    return Decimal(str(value).strip())


def _round_cents(value: Decimal) -> Decimal:
    return value.quantize(CENT, rounding=ROUND_HALF_UP)


def line_net(item: LineItem) -> Decimal:
    return _round_cents(to_decimal(item.unit_price) * item.quantity)


def line_tax(item: LineItem) -> Decimal:
    return _round_cents(line_net(item) * to_decimal(item.tax_rate))


def invoice_totals(items):
    net = sum((line_net(i) for i in items), Decimal("0.00"))
    tax = sum((line_tax(i) for i in items), Decimal("0.00"))
    return {"net": net, "tax": tax, "gross": net + tax}
