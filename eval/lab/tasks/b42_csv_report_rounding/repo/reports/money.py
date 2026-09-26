from decimal import ROUND_HALF_EVEN, Decimal, InvalidOperation

CENT = Decimal('0.01')


class AmountError(ValueError):
    pass


def parse_amount(text):
    """Parse '1,234.50', '-3' or '(12.00)' (accounting negative) into a Decimal."""
    raw = text.strip()
    negative = raw.startswith('(') and raw.endswith(')')
    if negative:
        raw = raw[1:-1].strip()
    try:
        value = Decimal(raw.replace(',', ''))
    except InvalidOperation:
        raise AmountError(f'not an amount: {text!r}') from None
    if not value.is_finite():
        raise AmountError(f'not an amount: {text!r}')
    return -value if negative else value


def round_cents(value):
    """Round to whole cents with banker's rounding (round-half-even)."""
    return value.quantize(CENT, rounding=ROUND_HALF_EVEN)


def format_money(value, currency):
    return f'{currency} {value:,.2f}'
